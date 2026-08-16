#!/usr/bin/env python3
"""Build or verify the deterministic package manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Sequence


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
EXCLUDED_PARTS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
}
EXCLUDED_NAMES = {".coverage", ".DS_Store"}
EXCLUDED_DERIVED_PATHS = [
    ".git",
    ".idea",
    ".DS_Store",
    ".venv",
    "__pycache__",
    "*.pyc",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
]
MANIFEST_METADATA = {
    "format_version": 1,
    "package_id": "subagent-orchestrator",
    "description": "Quality-first Codex subagent orchestration bundle",
}
TOP_LEVEL_KEYS = {*MANIFEST_METADATA, "package_version", "excluded_derived_paths", "files"}
FILE_KEYS = {"path", "sha256", "size"}
PACKAGE_VERSION_PATTERN = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\Z")


class ManifestError(ValueError):
    """Raised when a manifest is malformed or stale."""


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and path != MANIFEST
        and not EXCLUDED_PARTS.intersection(relative.parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix != ".pyc"
    )


def validate_package_version(package_version: object) -> str:
    if (
        not isinstance(package_version, str)
        or PACKAGE_VERSION_PATTERN.fullmatch(package_version) is None
    ):
        raise ManifestError("package_version must use YYYY.MM.DD")
    return package_version


def build_manifest(package_version: str) -> dict:
    validate_package_version(package_version)
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not included(path):
            continue
        content = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )

    return {
        **MANIFEST_METADATA,
        "package_version": package_version,
        "excluded_derived_paths": EXCLUDED_DERIVED_PATHS,
        "files": files,
    }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    document = {}
    for key, value in pairs:
        if key in document:
            raise ManifestError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def load_manifest(path: Path | None = None) -> dict:
    path = MANIFEST if path is None else path
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"manifest is unreadable: {error}") from error
    if not isinstance(document, dict):
        raise ManifestError("manifest root must be an object")
    return document


def validate_manifest_document(document: dict) -> None:
    if set(document) != TOP_LEVEL_KEYS:
        missing = sorted(TOP_LEVEL_KEYS - set(document))
        extra = sorted(set(document) - TOP_LEVEL_KEYS)
        raise ManifestError(f"manifest keys mismatch; missing={missing}; extra={extra}")

    for key, expected in MANIFEST_METADATA.items():
        if document[key] != expected or type(document[key]) is not type(expected):
            raise ManifestError(f"manifest metadata mismatch: {key}")
    validate_package_version(document["package_version"])

    if document["excluded_derived_paths"] != EXCLUDED_DERIVED_PATHS:
        raise ManifestError("manifest excluded_derived_paths mismatch")

    files = document["files"]
    if not isinstance(files, list):
        raise ManifestError("manifest files must be a list")

    seen = set()
    paths = []
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != FILE_KEYS:
            raise ManifestError(f"manifest file entry {index} has invalid keys")
        relative = item["path"]
        if not isinstance(relative, str) or not relative:
            raise ManifestError(f"manifest file entry {index} has invalid path")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative != pure.as_posix():
            raise ManifestError(f"unsafe manifest path: {relative!r}")
        if relative in seen:
            raise ManifestError(f"duplicate manifest path: {relative}")
        seen.add(relative)
        paths.append(relative)

        digest = item["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ManifestError(f"manifest file entry {relative!r} has invalid sha256")
        size = item["size"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ManifestError(f"manifest file entry {relative!r} has invalid size")

    if paths != sorted(paths):
        raise ManifestError("manifest files must be sorted by path")


def check_manifest(
    path: Path | None = None,
    package_version: str | None = None,
) -> None:
    path = MANIFEST if path is None else path
    actual = load_manifest(path)
    validate_manifest_document(actual)
    expected_version = actual["package_version"]
    if package_version is not None:
        expected_version = validate_package_version(package_version)
        if actual["package_version"] != expected_version:
            raise ManifestError(
                "manifest package_version does not match --package-version"
            )
    expected = build_manifest(expected_version)
    if actual != expected:
        actual_files = {item["path"]: item for item in actual["files"]}
        expected_files = {item["path"]: item for item in expected["files"]}
        missing = sorted(expected_files.keys() - actual_files.keys())
        undeclared = sorted(actual_files.keys() - expected_files.keys())
        changed = sorted(
            relative
            for relative in actual_files.keys() & expected_files.keys()
            if actual_files[relative] != expected_files[relative]
        )
        raise ManifestError(
            "manifest is stale; "
            f"missing={missing}; undeclared={undeclared}; changed={changed}"
        )


def managed_install_path(source_path: str) -> tuple[str, bool] | None:
    if source_path.startswith("payload/agents/") and source_path.endswith(".toml"):
        return source_path.removeprefix("payload/"), True
    skill_prefix = "payload/skills/subagent-orchestrator/"
    if source_path.startswith(skill_prefix):
        return source_path.removeprefix("payload/"), False
    return None


def build_migration_candidate(predecessor_path: Path) -> dict:
    predecessor_bytes = predecessor_path.read_bytes()
    predecessor = load_manifest(predecessor_path)
    validate_manifest_document(predecessor)
    if predecessor["package_id"] != MANIFEST_METADATA["package_id"]:
        raise ManifestError("predecessor package identity mismatch")
    current_paths = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if included(path)}
    candidates = []
    for item in predecessor["files"]:
        if item["path"] in current_paths:
            continue
        mapped = managed_install_path(item["path"])
        if mapped is None:
            continue
        installed_path, rendered = mapped
        candidates.append(
            {
                "accepted_sha256": [] if rendered else [item["sha256"]],
                "installed_path": installed_path,
                "requires_rendered_hash": rendered,
                "source_path": item["path"],
                "source_sha256": item["sha256"],
            }
        )
    return {
        "format_version": 1,
        "package_id": MANIFEST_METADATA["package_id"],
        "predecessor_manifest_sha256": hashlib.sha256(predecessor_bytes).hexdigest(),
        "predecessor_package_version": predecessor["package_version"],
        "retired_path_candidates": candidates,
        "review_required": True,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate manifest schema and fail if regeneration would change it",
    )
    parser.add_argument(
        "--package-version",
        metavar="YYYY.MM.DD",
        help="explicit package version; required when writing the manifest",
    )
    parser.add_argument(
        "--migration-candidate-from",
        type=Path,
        metavar="PREDECESSOR_MANIFEST",
        help="print a read-only retired-path candidate for human review",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.migration_candidate_from:
            if arguments.check or arguments.package_version:
                raise ManifestError(
                    "--migration-candidate-from cannot be combined with --check or "
                    "--package-version"
                )
            print(
                json.dumps(
                    build_migration_candidate(arguments.migration_candidate_from),
                    indent=2,
                    sort_keys=True,
                )
            )
        elif arguments.check:
            check_manifest(package_version=arguments.package_version)
            print(f"PASS: {MANIFEST} is valid and current")
        else:
            if arguments.package_version is None:
                raise ManifestError(
                    "--package-version is required when writing the manifest"
                )
            document = build_manifest(arguments.package_version)
            validate_manifest_document(document)
            MANIFEST.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(f"wrote {MANIFEST} with {len(document['files'])} files")
    except ManifestError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

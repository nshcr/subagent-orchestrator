#!/usr/bin/env python3
"""Validate package integrity, portability, installation, and bundled tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
}
EXCLUDED_NAMES = {".coverage", ".DS_Store"}


def fail(message: str) -> None:
    raise RuntimeError(message)


def package_files() -> dict[str, Path]:
    result = {}
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if (
            not path.is_file()
            or path == MANIFEST
            or EXCLUDED_PARTS.intersection(relative.parts)
            or path.name in EXCLUDED_NAMES
            or path.suffix == ".pyc"
        ):
            continue
        result[str(relative)] = path
    return result


def verify_manifest() -> None:
    try:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"manifest is unreadable: {error}")
    declared = {item["path"]: item for item in document.get("files", [])}
    actual = package_files()
    if set(declared) != set(actual):
        missing = sorted(set(declared) - set(actual))
        undeclared = sorted(set(actual) - set(declared))
        fail(f"manifest coverage mismatch; missing={missing}; undeclared={undeclared}")
    for relative, path in actual.items():
        content = path.read_bytes()
        if len(content) != declared[relative].get("size"):
            fail(f"manifest size mismatch: {relative}")
        digest = hashlib.sha256(content).hexdigest()
        if digest != declared[relative].get("sha256"):
            fail(f"manifest hash mismatch: {relative}")


def verify_portability() -> None:
    forbidden_patterns = (
        re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
        re.compile(rb"/home/[A-Za-z0-9._-]+/"),
        re.compile(rb"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._-]+\\\\"),
    )
    for relative, path in package_files().items():
        content = path.read_bytes()
        for pattern in forbidden_patterns:
            if pattern.search(content):
                fail(f"user-specific absolute path in {relative}")
    profile = json.loads((ROOT / "portable-profile.json").read_text(encoding="utf-8"))
    roles = {role["id"] for role in profile.get("roles", [])}
    expected = {
        "evidence_tester",
        "boundary_mapper",
        "risk_reviewer",
        "risk_reviewer_max",
    }
    if roles != expected:
        fail(f"portable profile role mismatch: {sorted(roles)}")
    if profile.get("primary") != {
        "model": "unconstrained",
        "reasoning_effort": "unconstrained",
        "owns": [
            "authorization",
            "scope",
            "single-writer-integration",
            "conflict-handling",
            "final-acceptance",
        ],
    }:
        fail("portable profile constrains or changes primary ownership")


def run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        fail(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed.stdout


def verify_hermetic_install() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        for language in ("en", "zh"):
            codex_home = Path(temporary) / f"codex-home-{language}"
            command = [
                sys.executable,
                "-B",
                str(ROOT / "install.py"),
                "--codex-home",
                str(codex_home),
                "--agents-language",
                language,
            ]
            check_output = run(command + ["--check"])
            if "WOULD_TOUCH" not in check_output:
                fail(f"{language}: empty-home preflight produced no touched-path hashes")
            run(command + ["--apply"])
            second_check = run(command + ["--check"])
            if "0 path(s) would change" not in second_check:
                fail(f"{language}: installer is not idempotent")
            validator = (
                codex_home
                / "skills"
                / "subagent-orchestrator"
                / "scripts"
                / "validate-routing-config.py"
            )
            run(
                [
                    sys.executable,
                    "-B",
                    str(validator),
                    "--codex-home",
                    str(codex_home),
                ]
            )
            tests = codex_home / "skills" / "subagent-orchestrator" / "tests"
            run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    str(tests),
                    "-p",
                    "test_*.py",
                ]
            )


def verify_package_tests() -> None:
    run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ]
    )


def main() -> int:
    try:
        verify_manifest()
        verify_portability()
        verify_package_tests()
        verify_hermetic_install()
    except (RuntimeError, OSError, UnicodeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "PASS: manifest, portability, package tests, safe install, "
        "routing policy, and bundled tests"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

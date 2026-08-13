#!/usr/bin/env python3
"""Rebuild the deterministic package manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and path != MANIFEST
        and not EXCLUDED_PARTS.intersection(relative.parts)
        and path.name not in EXCLUDED_NAMES
        and path.suffix != ".pyc"
    )


def build_manifest() -> dict:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not included(path):
            continue
        content = path.read_bytes()
        files.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )

    return {
        "format_version": 1,
        "package_id": "subagent-orchestrator",
        "package_version": "2026.08.13",
        "description": "Quality-first Codex subagent orchestration bundle",
        "excluded_derived_paths": [
            ".git",
            ".DS_Store",
            ".venv",
            "__pycache__",
            "*.pyc",
            ".coverage",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "htmlcov",
        ],
        "files": files,
    }


def main() -> None:
    document = build_manifest()
    MANIFEST.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {MANIFEST} with {len(document['files'])} files")


if __name__ == "__main__":
    main()

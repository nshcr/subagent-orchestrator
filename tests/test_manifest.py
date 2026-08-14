from importlib.util import module_from_spec, spec_from_file_location
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock


PACKAGE_ROOT = Path(__file__).parents[1]
PACKAGE_VERSION = "2026.08.14"


def load_module(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


BUILD_MANIFEST = load_module("subagent_orchestrator_manifest", PACKAGE_ROOT / "build_manifest.py")
VALIDATE = load_module("subagent_orchestrator_validate", PACKAGE_ROOT / "validate.py")


class ManifestBoundaryTest(unittest.TestCase):
    def test_repository_metadata_and_local_caches_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = root / ".github" / "workflows" / "ci.yml"
            expected.parent.mkdir(parents=True)
            expected.write_text("name: CI\n")
            source = root / "payload" / "example.txt"
            source.parent.mkdir()
            source.write_text("payload\n")

            excluded = (
                root / ".git" / "HEAD",
                root / ".venv" / "marker",
                root / ".pytest_cache" / "marker",
                root / "__pycache__" / "module.pyc",
                root / ".DS_Store",
            )
            for path in excluded:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"derived")

            manifest_path = root / "manifest.json"
            with (
                mock.patch.object(BUILD_MANIFEST, "ROOT", root),
                mock.patch.object(BUILD_MANIFEST, "MANIFEST", manifest_path),
            ):
                document = BUILD_MANIFEST.build_manifest(PACKAGE_VERSION)
            declared = {item["path"] for item in document["files"]}
            self.assertEqual(declared, {".github/workflows/ci.yml", "payload/example.txt"})

            manifest_path.write_text(json.dumps(document))
            with (
                mock.patch.object(VALIDATE, "ROOT", root),
                mock.patch.object(VALIDATE, "MANIFEST", manifest_path),
            ):
                actual = set(VALIDATE.package_files())
            self.assertEqual(actual, declared)

    def test_schema_rejects_duplicate_paths_and_metadata_drift(self):
        document = BUILD_MANIFEST.build_manifest(PACKAGE_VERSION)
        duplicate = copy.deepcopy(document)
        duplicate["files"].append(copy.deepcopy(duplicate["files"][0]))
        with self.assertRaisesRegex(BUILD_MANIFEST.ManifestError, "duplicate manifest path"):
            BUILD_MANIFEST.validate_manifest_document(duplicate)

        drifted = copy.deepcopy(document)
        drifted["description"] = "drifted"
        with self.assertRaisesRegex(BUILD_MANIFEST.ManifestError, "metadata mismatch"):
            BUILD_MANIFEST.validate_manifest_document(drifted)

        for invalid in ("2026-08-14", "2026.8.14", "release"):
            invalid_version = copy.deepcopy(document)
            invalid_version["package_version"] = invalid
            with self.subTest(version=invalid):
                with self.assertRaisesRegex(
                    BUILD_MANIFEST.ManifestError, "package_version"
                ):
                    BUILD_MANIFEST.validate_manifest_document(invalid_version)

    def test_loader_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = Path(temporary) / "manifest.json"
            manifest_path.write_text('{"format_version": 1, "format_version": 1}')
            with self.assertRaisesRegex(BUILD_MANIFEST.ManifestError, "duplicate JSON key"):
                BUILD_MANIFEST.load_manifest(manifest_path)

    def test_check_mode_detects_stale_manifest_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "payload.txt"
            source.write_text("before\n")
            manifest_path = root / "manifest.json"
            with (
                mock.patch.object(BUILD_MANIFEST, "ROOT", root),
                mock.patch.object(BUILD_MANIFEST, "MANIFEST", manifest_path),
            ):
                document = BUILD_MANIFEST.build_manifest(PACKAGE_VERSION)
                manifest_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
                self.assertEqual(BUILD_MANIFEST.main(["--check"]), 0)
                original_manifest = manifest_path.read_bytes()
                source.write_text("after\n")
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    self.assertEqual(BUILD_MANIFEST.main(["--check"]), 1)
                self.assertIn("manifest is stale", stderr.getvalue())
                self.assertEqual(manifest_path.read_bytes(), original_manifest)

    def test_write_requires_explicit_package_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "payload.txt").write_text("payload\n")
            manifest_path = root / "manifest.json"
            with (
                mock.patch.object(BUILD_MANIFEST, "ROOT", root),
                mock.patch.object(BUILD_MANIFEST, "MANIFEST", manifest_path),
            ):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    self.assertEqual(BUILD_MANIFEST.main([]), 1)
                self.assertIn("--package-version is required", stderr.getvalue())
                self.assertFalse(manifest_path.exists())
                self.assertEqual(
                    BUILD_MANIFEST.main(["--package-version", PACKAGE_VERSION]),
                    0,
                )
                document = json.loads(manifest_path.read_text())
                self.assertEqual(document["package_version"], PACKAGE_VERSION)

    def test_migration_candidate_maps_only_removed_managed_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "payload" / "agents" / "current.toml"
            current.parent.mkdir(parents=True)
            current.write_text("name = current\n")
            predecessor_path = root / "predecessor.json"
            predecessor = {
                **BUILD_MANIFEST.MANIFEST_METADATA,
                "package_version": "2026.08.13",
                "excluded_derived_paths": BUILD_MANIFEST.EXCLUDED_DERIVED_PATHS,
                "files": [
                    {
                        "path": "README.md",
                        "sha256": "1" * 64,
                        "size": 1,
                    },
                    {
                        "path": "payload/agents/retired.toml",
                        "sha256": "2" * 64,
                        "size": 2,
                    },
                    {
                        "path": "payload/skills/subagent-orchestrator/old.txt",
                        "sha256": "3" * 64,
                        "size": 3,
                    },
                ],
            }
            predecessor_path.write_text(
                json.dumps(predecessor, indent=2, sort_keys=True) + "\n"
            )
            with mock.patch.object(BUILD_MANIFEST, "ROOT", root):
                candidate = BUILD_MANIFEST.build_migration_candidate(predecessor_path)
            self.assertTrue(candidate["review_required"])
            self.assertEqual(
                [item["installed_path"] for item in candidate["retired_path_candidates"]],
                [
                    "agents/retired.toml",
                    "skills/subagent-orchestrator/old.txt",
                ],
            )
            role, skill = candidate["retired_path_candidates"]
            self.assertTrue(role["requires_rendered_hash"])
            self.assertEqual(role["accepted_sha256"], [])
            self.assertFalse(skill["requires_rendered_hash"])
            self.assertEqual(skill["accepted_sha256"], ["3" * 64])


if __name__ == "__main__":
    unittest.main()

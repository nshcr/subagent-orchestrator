from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PACKAGE_ROOT = Path(__file__).parents[1]


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
                document = BUILD_MANIFEST.build_manifest()
            declared = {item["path"] for item in document["files"]}
            self.assertEqual(declared, {".github/workflows/ci.yml", "payload/example.txt"})

            manifest_path.write_text(json.dumps(document))
            with (
                mock.patch.object(VALIDATE, "ROOT", root),
                mock.patch.object(VALIDATE, "MANIFEST", manifest_path),
            ):
                actual = set(VALIDATE.package_files())
            self.assertEqual(actual, declared)


if __name__ == "__main__":
    unittest.main()

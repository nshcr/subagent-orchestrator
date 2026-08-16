from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


PACKAGE_ROOT = Path(__file__).parents[1]
SPEC = spec_from_file_location(
    "subagent_orchestrator_profile_validate",
    PACKAGE_ROOT / "validate.py",
)
VALIDATE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = VALIDATE
SPEC.loader.exec_module(VALIDATE)


class PortableProfileContractTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        shutil.copy2(
            PACKAGE_ROOT / "portable-profile.json",
            self.root / "portable-profile.json",
        )
        shutil.copytree(
            PACKAGE_ROOT / "payload" / "agents",
            self.root / "payload" / "agents",
        )
        config = self.root / "payload" / "config.agents.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE_ROOT / "payload" / "config.agents.toml", config)
        contract = (
            self.root
            / "payload"
            / "skills"
            / "subagent-orchestrator"
            / "references"
            / "delegation-contracts.md"
        )
        contract.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            PACKAGE_ROOT
            / "payload"
            / "skills"
            / "subagent-orchestrator"
            / "references"
            / "delegation-contracts.md",
            contract,
        )
        routing = contract.with_name("routing-policy.md")
        shutil.copy2(
            PACKAGE_ROOT
            / "payload"
            / "skills"
            / "subagent-orchestrator"
            / "references"
            / "routing-policy.md",
            routing,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def profile(self) -> dict:
        return json.loads((self.root / "portable-profile.json").read_text())

    def write_profile(self, document: dict) -> None:
        (self.root / "portable-profile.json").write_text(
            json.dumps(document, indent=2) + "\n"
        )

    def validate(self) -> None:
        with mock.patch.object(VALIDATE, "ROOT", self.root):
            VALIDATE.verify_portability()

    def test_accepts_canonical_profile(self):
        self.validate()

    def test_rejects_role_runtime_drift(self):
        document = self.profile()
        document["roles"][0]["model_hint"] = "gpt-5.6-sol"
        self.write_profile(document)
        with self.assertRaisesRegex(RuntimeError, "model_hint mismatch"):
            self.validate()

    def test_rejects_handoff_schema_drift(self):
        document = self.profile()
        del document["handoff"]["required_typed_fields"]["named_invariants"]
        self.write_profile(document)
        with self.assertRaisesRegex(RuntimeError, "handoff contract mismatch"):
            self.validate()

    def test_rejects_bounded_peer_route_or_cap_drift(self):
        mutations = (
            ("route", lambda document: document["builtin_routes"][2].update(topology="leaf")),
            (
                "depth",
                lambda document: document["handoff"].update(
                    bounded_peer_delegation_depth=2
                ),
            ),
            (
                "descendant-cap",
                lambda document: document["concurrency"].update(
                    bounded_peer_leaf_descendant_cap=3
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                document = json.loads(
                    (PACKAGE_ROOT / "portable-profile.json").read_text(encoding="utf-8")
                )
                mutate(document)
                self.write_profile(document)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "built-in routes|handoff contract|concurrency",
                ):
                    self.validate()

    def test_rejects_duplicate_role_id(self):
        document = self.profile()
        document["roles"][1]["id"] = document["roles"][0]["id"]
        self.write_profile(document)
        with self.assertRaisesRegex(RuntimeError, "duplicate role ids"):
            self.validate()

    def test_rejects_role_class_and_eligibility_drift(self):
        for field in ("class", "eligibility"):
            document = json.loads(
                (PACKAGE_ROOT / "portable-profile.json").read_text(encoding="utf-8")
            )
            document["roles"][0][field] = "drifted"
            self.write_profile(document)
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError, f"role {field} mismatch"):
                    self.validate()

    def test_rejects_duplicate_template_and_adapter_drift(self):
        duplicate = self.profile()
        duplicate["roles"][1]["template"] = duplicate["roles"][0]["template"]
        self.write_profile(duplicate)
        with self.assertRaisesRegex(RuntimeError, "duplicate role templates"):
            self.validate()

        adapter = json.loads(
            (PACKAGE_ROOT / "portable-profile.json").read_text(encoding="utf-8")
        )
        adapter["adapter_requirements"].pop()
        self.write_profile(adapter)
        with self.assertRaisesRegex(RuntimeError, "adapter requirements mismatch"):
            self.validate()


if __name__ == "__main__":
    unittest.main()

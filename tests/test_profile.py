import copy
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
            PACKAGE_ROOT / "payload" / "en" / "agents",
            self.root / "payload" / "en" / "agents",
        )
        config = self.root / "payload" / "shared" / "config.agents.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE_ROOT / "payload" / "shared" / "config.agents.toml", config)
        contract = (
            self.root
            / "payload"
            / "en"
            / "skills"
            / "subagent-orchestrator"
            / "references"
            / "delegation-contracts.md"
        )
        contract.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            PACKAGE_ROOT
            / "payload"
            / "en"
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
            / "en"
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

    def test_rejects_spawn_defaults_or_host_fallback_drift(self):
        document = self.profile()
        mutations = (
            (
                "spawn-defaults",
                lambda item: item["spawn_model_defaults"].update(
                    model_hint="gpt-5.6-luna"
                ),
            ),
            (
                "host-fallback",
                lambda item: item["host_fallback"].update(route="spawn-default"),
            ),
            (
                "implicit-agent-type",
                lambda item: item["host_fallback"].update(
                    explicit_agent_type_required=False
                ),
            ),
            (
                "fallback-result",
                lambda item: item["host_fallback"].update(
                    fallback_result_route="accept"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                candidate = copy.deepcopy(document)
                mutate(candidate)
                self.write_profile(candidate)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "spawn model defaults|default host fallback",
                ):
                    self.validate()

    def test_rejects_expansion_checkpoint_drift(self):
        document = self.profile()
        document["handoff"]["later_wave_requires_expansion_checkpoint"] = False
        self.write_profile(document)
        with self.assertRaisesRegex(RuntimeError, "handoff contract mismatch"):
            self.validate()

    def test_rejects_review_role_update_drift(self):
        document = self.profile()
        mutations = (
            ("review_role_additional_work", "allowed"),
            ("context_scope", "unbounded"),
            ("cross_child_coordination", "allowed"),
            ("approval_rejection_route", "retry-after-primary-action"),
            ("repeated_approval_route", "retry-same-boundary"),
            ("approval_circuit_clearance", "parent-assertion"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                candidate = copy.deepcopy(document)
                candidate["handoff"][key] = value
                self.write_profile(candidate)
                with self.assertRaisesRegex(RuntimeError, "handoff contract mismatch"):
                    self.validate()

    def test_rejects_leaf_route_or_first_wave_cap_drift(self):
        mutations = (
            ("route", lambda document: document["builtin_routes"][0].update(topology="bounded-peer")),
            (
                "child-cap",
                lambda document: document["concurrency"].update(
                    ordinary_first_wave_child_cap=3
                ),
            ),
            (
                "admitted-delegation-child-count",
                lambda document: document["concurrency"].update(
                    admitted_delegation_initial_child_count=2
                ),
            ),
            (
                "second-child-admission",
                lambda document: document["concurrency"].update(
                    second_child_admission="capacity-available"
                ),
            ),
            (
                "writer-cap",
                lambda document: document["concurrency"].update(
                    ordinary_first_wave_writer_cap=2
                ),
            ),
            (
                "active-writer-cap",
                lambda document: document["concurrency"].update(
                    active_writer_cap=2
                ),
            ),
            (
                "later-wave-precondition",
                lambda document: document["concurrency"].update(
                    later_wave_precondition="none"
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

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).parents[1]
PACKAGE_PAYLOAD = SKILL_DIR.parents[1]
SPEC = spec_from_file_location(
    "routing_validator",
    SKILL_DIR / "scripts" / "validate-routing-config.py",
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RoutingContractTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.codex_home = Path(self.temporary.name) / "codex-home"
        self.codex_home.mkdir()
        source_agents = PACKAGE_PAYLOAD / "AGENTS.section.en.md"
        source_config = PACKAGE_PAYLOAD / "config.agents.toml"
        if not source_agents.is_file():
            source_agents = PACKAGE_PAYLOAD / "AGENTS.md"
            source_config = PACKAGE_PAYLOAD / "config.toml"
        shutil.copy2(source_agents, self.codex_home / "AGENTS.md")
        shutil.copy2(source_config, self.codex_home / "config.toml")
        shutil.copytree(PACKAGE_PAYLOAD / "agents", self.codex_home / "agents")
        (self.codex_home / "skills").mkdir()
        shutil.copytree(SKILL_DIR, self.codex_home / "skills" / SKILL_DIR.name)
        self.skill_dir = self.codex_home / "skills" / SKILL_DIR.name
        self.configured_skill_path = self.skill_dir / "SKILL.md"
        for role_path in (self.codex_home / "agents").glob("*.toml"):
            role_path.write_text(
                re.sub(
                    r'(?m)^path = ".*"$',
                    f'path = "{self.configured_skill_path}"',
                    role_path.read_text(),
                )
            )

    def tearDown(self):
        self.temporary.cleanup()

    def errors(self):
        return MODULE.validate(self.codex_home, self.configured_skill_path).errors

    def mutate(self, relative: str, old: str, new: str):
        path = self.codex_home / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_accepts_candidate(self):
        self.assertEqual(self.errors(), [])

    def test_rejects_missing_role(self):
        (self.codex_home / "agents" / "evidence_tester.toml").unlink()
        self.assertTrue(any("missing a required role" in error for error in self.errors()))

    def test_accepts_unrelated_role(self):
        (self.codex_home / "agents" / "project-specialist.toml").write_text('name = "project-specialist"\n')
        self.assertEqual(self.errors(), [])

    def test_rejects_role_runtime_or_instruction_drift(self):
        self.mutate(
            "agents/risk_reviewer.toml",
            'model_reasoning_effort = "xhigh"',
            'model_reasoning_effort = "high"',
        )
        self.assertTrue(any("risk_reviewer: effort mismatch" in error for error in self.errors()))

    def test_rejects_monkey_first_rule_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Prove the monkey before building",
            "Build the pedestal before proving",
        )
        self.assertTrue(any("monkey" in error.lower() for error in self.errors()))

    def test_rejects_user_checkpoint_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "without a user checkpoint",
            "without consulting the user",
        )
        self.assertTrue(any("user checkpoint" in error for error in self.errors()))

    def test_rejects_reviewer_designer_drift(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "is a terminal gate, not a continuing designer",
            "A reviewer continuously redesigns the implementation",
        )
        self.assertTrue(any("terminal gate" in error for error in self.errors()))

    def test_rejects_harness_claim_broadening(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "enforced the policy or that production became faster",
            "prove host enforcement and production speed",
        )
        self.assertTrue(any("do not prove" in error for error in self.errors()))

    def test_rejects_global_policy_boundary_removal(self):
        self.mutate(
            "AGENTS.md",
            "仍有 BLOCK 就把决定权交还用户" if "## 子代理与并行" in (self.codex_home / "AGENTS.md").read_text() else "another BLOCK returns control to the user",
            "continue until every reviewer passes",
        )
        self.assertTrue(any("BLOCK" in error for error in self.errors()))

    def test_rejects_missing_static_validator(self):
        (self.skill_dir / "scripts" / "validate-routing-config.py").unlink()
        self.assertTrue(any("missing skill file" in error for error in self.errors()))

    def test_rejects_undeclared_bytecode(self):
        derived = self.skill_dir / "scripts" / "__pycache__"
        derived.mkdir()
        (derived / "validator.pyc").write_bytes(b"derived")
        self.assertTrue(any("bytecode" in error for error in self.errors()))


if __name__ == "__main__":
    unittest.main()

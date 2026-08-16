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
            'model_reasoning_effort = "high"',
            'model_reasoning_effort = "xhigh"',
        )
        self.assertTrue(any("risk_reviewer: effort mismatch" in error for error in self.errors()))

    def test_rejects_runtime_cap_or_routine_effort_drift(self):
        for old, new, expected in (
            ("max_concurrent_threads_per_session = 3", "max_concurrent_threads_per_session = 16", "max_concurrent"),
            ('default_subagent_reasoning_effort = "medium"', 'default_subagent_reasoning_effort = "high"', "reasoning_effort"),
        ):
            with self.subTest(old=old):
                self.mutate("config.toml", old, new)
                self.assertTrue(any(expected in error for error in self.errors()))
                self.mutate("config.toml", new, old)

    def test_rejects_single_child_default_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Start one child by default",
            "Fill every available agent slot by default",
        )
        self.assertTrue(any("Start one child" in error for error in self.errors()))

    def test_rejects_monkey_first_rule_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Prove the monkey before building",
            "Build the pedestal before proving",
        )
        self.assertTrue(any("monkey" in error.lower() for error in self.errors()))

    def test_rejects_expansion_checkpoint_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "that exact expansion; otherwise use the primary or close without another child",
            "any expansion; start another child automatically",
        )
        self.assertTrue(any("exact expansion" in error for error in self.errors()))

    def test_rejects_writer_overlap(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "writer and never overlap write scopes",
            "writer and allow overlapping write scopes",
        )
        self.assertTrue(any("active writer" in error for error in self.errors()))

    def test_rejects_unintegrated_later_wave(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Before a later wave, collect every current required child to terminal state",
            "Start a later wave while current children are running",
        )
        self.assertTrue(any("later wave" in error for error in self.errors()))

    def test_rejects_moving_review_state(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "state change invalidates prior gate results",
            "state change preserves prior gate results",
        )
        self.assertTrue(any("state change" in error for error in self.errors()))

    def test_rejects_operational_blocker_as_preference(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "do not pose them as preferences",
            "ask the user to choose how to fix every blocker",
        )
        self.assertTrue(any("preferences" in error for error in self.errors()))

    def test_rejects_child_terminal_as_task_completion(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "proves neither task completion nor",
            "proves task completion and",
        )
        self.assertTrue(any("task completion" in error for error in self.errors()))

    def test_rejects_sub_boundary_as_task_acceptance(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "passing an install, load, child, test, or review sub-boundary cannot",
            "passing any lower-level sub-boundary is sufficient and can",
        )
        self.assertTrue(any("sub-boundary" in error for error in self.errors()))

    def test_rejects_reviewer_designer_drift(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "reviewer is a terminal gate, not a",
            "reviewer continuously redesigns the implementation and is a",
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
            "仍有 BLOCK 就停止继续评审" if "## 子代理与并行" in (self.codex_home / "AGENTS.md").read_text() else "another BLOCK stops further review",
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

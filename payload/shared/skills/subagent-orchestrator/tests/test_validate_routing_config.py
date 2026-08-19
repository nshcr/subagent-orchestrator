from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).parents[1]
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
        package_payload = SKILL_DIR.parents[2]
        installed_root = SKILL_DIR.parents[1]
        source_package = (package_payload / "en").is_dir()
        if source_package:
            source_agents = package_payload / "en" / "AGENTS.section.md"
            source_config = package_payload / "en" / "config.agents.toml"
            source_agents_dir = package_payload / "en" / "agents"
        else:
            source_agents = installed_root / "AGENTS.md"
            source_config = installed_root / "config.toml"
            source_agents_dir = installed_root / "agents"
        shutil.copy2(source_agents, self.codex_home / "AGENTS.md")
        shutil.copy2(source_config, self.codex_home / "config.toml")
        ignore_bytecode = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(
            source_agents_dir,
            self.codex_home / "agents",
            ignore=ignore_bytecode,
        )
        if source_package:
            (self.codex_home / "skills").mkdir()
            installed_skill = self.codex_home / "skills" / SKILL_DIR.name
            shutil.copytree(
                package_payload / "en" / "skills" / SKILL_DIR.name,
                installed_skill,
                ignore=ignore_bytecode,
            )
            shutil.copytree(
                SKILL_DIR,
                installed_skill,
                dirs_exist_ok=True,
                ignore=ignore_bytecode,
            )
            self.skill_dir = installed_skill
        else:
            (self.codex_home / "skills").mkdir()
            installed_skill = self.codex_home / "skills" / SKILL_DIR.name
            shutil.copytree(SKILL_DIR, installed_skill, ignore=ignore_bytecode)
            self.skill_dir = installed_skill
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
        pattern = re.compile(r"\s+".join(re.escape(part) for part in old.split()))
        self.assertRegex(text, pattern)
        path.write_text(pattern.sub(new, text, count=1))

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

    def test_rejects_reviewer_artifact_drift(self):
        self.mutate(
            "agents/risk_reviewer.toml",
            "`Artifact contract` is `none`",
            "`Artifact contract` names a writable review file",
        )
        self.assertTrue(any("Artifact contract" in error for error in self.errors()))

    def test_rejects_runtime_cap_or_routine_effort_drift(self):
        for old, new, expected in (
            ("max_concurrent_threads_per_session = 4", "max_concurrent_threads_per_session = 16", "max_concurrent"),
            (
                'default_subagent_reasoning_effort = "max"',
                'default_subagent_reasoning_effort = "high"',
                "reasoning_effort",
            ),
        ):
            with self.subTest(old=old):
                self.mutate("config.toml", old, new)
                self.assertTrue(any(expected in error for error in self.errors()))
                self.mutate("config.toml", new, old)

    def test_rejects_single_child_admission_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "When delegation is admitted, start one child",
            "Fill every available agent slot by default",
        )
        self.assertTrue(any("start one child" in error for error in self.errors()))

    def test_rejects_implicit_or_default_agent_type(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Name a non-`default` `agent_type`",
            "Let the host select any omitted agent type",
        )
        self.assertTrue(any("Name a non-`default`" in error for error in self.errors()))

    def test_rejects_eager_routing_reference_load(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "before a custom role, second child, or review",
            "before every routing decision",
        )
        self.assertTrue(any("before a custom role" in error for error in self.errors()))

    def test_rejects_default_fallback_routing(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/routing-policy.md",
            "Never route to the built-in `default`",
            "Route unmatched work to the built-in `default`",
        )
        self.assertTrue(
            any(
                "Never route to the built-in `default`" in error
                for error in self.errors()
            )
        )

    def test_rejects_handoff_without_explicit_agent_type(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/delegation-contracts.md",
            "Spawn: agent_type=<explicit non-default role>",
            "Spawn: agent_type=<optional>",
        )
        self.assertTrue(
            any(
                "Spawn: agent_type=<explicit non-default role>" in error
                for error in self.errors()
            )
        )

    def test_rejects_unbounded_handoff_context(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/delegation-contracts.md",
            "inherited context does not widen authorization",
            "inherited context can widen authorization",
        )
        self.assertTrue(any("inherited context does not widen authorization" in error for error in self.errors()))

    def test_rejects_default_result_acceptance(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Reject omitted or otherwise invalid role results",
            "accept any fallback result",
        )
        self.assertTrue(
            any("Reject omitted or otherwise invalid role results" in error for error in self.errors())
        )

    def test_rejects_approval_boundary_repeat(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/delegation-contracts.md",
            "Do not repeat the blocked action, widen authorization",
            "Allow the blocked action to repeat",
        )
        self.assertTrue(any("Do not repeat the blocked action" in error for error in self.errors()))

    def test_rejects_repeated_child_approval_boundary(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/delegation-contracts.md",
            "assign the same permission-class and owner-scope boundary to a later child",
            "assign the same blocked boundary to every later child",
        )
        self.assertTrue(any("owner-scope" in error for error in self.errors()))

    def test_rejects_unproven_approval_circuit_clearance(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/delegation-contracts.md",
            "host evidence proves a reusable grant applies to child threads",
            "the primary says approval should now work",
        )
        self.assertTrue(any("reusable grant" in error for error in self.errors()))

    def test_rejects_spawn_time_model_or_effort_override(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Use installed child model and effort settings without per-task retuning",
            "Override each child's model and effort per task",
        )
        self.assertTrue(any("installed child model and effort" in error for error in self.errors()))

    def test_rejects_sandbox_as_hard_authority_boundary(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/routing-policy.md",
            "`sandbox_mode` as requested configuration, not hard authority",
            "`sandbox_mode` as guaranteed host enforcement",
        )
        self.assertTrue(any("not hard authority" in error for error in self.errors()))

    def test_rejects_monkey_first_rule_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "hardest user-relevant behavior",
            "easiest surrounding scaffold",
        )
        self.assertTrue(any("hardest user-relevant behavior" in error for error in self.errors()))

    def test_rejects_expansion_checkpoint_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Clear the checkpoint without asking only when",
            "primary automatically fills every available child slot",
        )
        self.assertTrue(any("Clear the checkpoint" in error for error in self.errors()))

    def test_rejects_expansion_as_automatic_user_question(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/routing-policy.md",
            "Expansion alone is not a question",
            "always triggers a user question",
        )
        self.assertTrue(any("Expansion alone is not a question" in error for error in self.errors()))

    def test_rejects_writer_overlap(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "ordinary cap at two children",
            "ordinary cap at four children",
        )
        self.assertTrue(any("ordinary cap at two children" in error for error in self.errors()))

    def test_rejects_unintegrated_later_wave(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Freeze new spawns, collect and integrate",
            "Start a later wave while current children are running",
        )
        self.assertTrue(any("collect and integrate" in error for error in self.errors()))

    def test_rejects_non_english_child_receipt(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/delegation-contracts.md",
            "Return: <English receipt or artifact and observable done condition>",
            "Return: <receipt in any language>",
        )
        self.assertTrue(any("English receipt" in error for error in self.errors()))

    def test_rejects_moving_review_state(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Invalidate all prior gate results after any relevant change",
            "Any relevant change preserves prior gate results",
        )
        self.assertTrue(any("relevant change" in error for error in self.errors()))

    def test_rejects_operational_blocker_as_preference(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "do not disguise them as preferences",
            "ask the user to choose how to fix every blocker",
        )
        self.assertTrue(any("preferences" in error for error in self.errors()))

    def test_rejects_child_terminal_as_task_completion(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Close only with claim-matched evidence",
            "Treat any child terminal receipt as proof of the original outcome",
        )
        self.assertTrue(any("claim-matched evidence" in error for error in self.errors()))

    def test_rejects_primary_finding_adjudication_removal(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "Adjudicate every finding in the primary",
            "reviewer findings are accepted without question",
        )
        self.assertTrue(any("Adjudicate every finding" in error for error in self.errors()))

    def test_rejects_reviewer_designer_drift(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "evidence gate, not a designer",
            "reviewer continuously redesigns the implementation and is a",
        )
        self.assertTrue(any("evidence gate, not a designer" in error for error in self.errors()))

    def test_rejects_expansion_checkpoint_as_recursion_authority(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "expansion checkpoint cannot relax recursion",
            "expansion checkpoint may authorize recursion",
        )
        self.assertTrue(any("cannot relax recursion" in error for error in self.errors()))

    def test_rejects_reviewer_not_applicable_escape(self):
        self.mutate(
            "agents/risk_reviewer.toml",
            "do not use not-applicable for an admitted invariant",
            "not-applicable is always allowed",
        )
        self.assertTrue(any("not-applicable" in error for error in self.errors()))

    def test_rejects_operational_role_bounded_update_drift(self):
        self.mutate(
            "agents/evidence_tester.toml",
            "Accept at most one scoped primary update",
            "Accept unlimited primary updates",
        )
        self.assertTrue(any("bounded primary update" in error for error in self.errors()))

    def test_rejects_operational_role_cross_coordination(self):
        self.mutate(
            "agents/boundary_mapper.toml",
            "Do not spawn further agents, coordinate with peers, or widen scope.",
            "Coordinate with peers",
        )
        self.assertTrue(any("cross-child coordination" in error for error in self.errors()))

    def test_rejects_reviewer_additional_work_acceptance(self):
        self.mutate(
            "agents/risk_reviewer.toml",
            "Keep the review bounded to the named invariants.",
            "Accept additional review work.",
        )
        self.assertTrue(any("review input must remain bounded" in error for error in self.errors()))

    def test_rejects_repeated_review_without_new_evidence(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/references/routing-policy.md",
            "changed candidate or new discriminating evidence",
            "another reviewer request",
        )
        self.assertTrue(any("changed candidate" in error for error in self.errors()))

    def test_rejects_harness_claim_broadening(self):
        self.mutate(
            f"skills/{SKILL_DIR.name}/SKILL.md",
            "loading, not production efficiency",
            "Static tests prove production efficiency",
        )
        self.assertTrue(any("production efficiency" in error for error in self.errors()))

    def test_rejects_global_policy_bloat(self):
        self.mutate(
            "AGENTS.md",
            "evidence-based closure.",
            "evidence-based closure.\n- Run three reviewers after every change.",
        )
        self.assertTrue(any("two bullets" in error for error in self.errors()))

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

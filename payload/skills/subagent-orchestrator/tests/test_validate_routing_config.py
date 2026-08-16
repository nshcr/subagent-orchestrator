from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import copy
import re
import shutil
import sys
import tempfile
import unittest


skill_dir = Path(__file__).parents[1]
spec = spec_from_file_location(
    "routing_validator",
    skill_dir / "scripts" / "validate-routing-config.py",
)
module = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
codex_home = skill_dir.parents[1]


def clone_candidate() -> tuple[tempfile.TemporaryDirectory, Path]:
    temporary = tempfile.TemporaryDirectory()
    candidate = Path(temporary.name) / "codex-home"
    candidate.mkdir()
    shutil.copy2(codex_home / "AGENTS.md", candidate / "AGENTS.md")
    shutil.copy2(codex_home / "config.toml", candidate / "config.toml")
    shutil.copytree(codex_home / "agents", candidate / "agents")
    (candidate / "skills").mkdir()
    shutil.copytree(skill_dir, candidate / "skills" / skill_dir.name)
    return temporary, candidate


class RoutingContractTest(unittest.TestCase):
    def validate(self, candidate: Path):
        return module.validate(candidate, module.DEFAULT_SKILL_PATH)

    def test_accepts_staged_contract(self):
        self.assertEqual(self.validate(codex_home).errors, [])

    def test_rejects_missing_active_role(self):
        temporary, candidate = clone_candidate()
        with temporary:
            (candidate / "agents" / "evidence_tester.toml").unlink()
            errors = self.validate(candidate).errors
            self.assertTrue(any("agent catalog" in error for error in errors))

    def test_rejects_legacy_or_extra_role(self):
        temporary, candidate = clone_candidate()
        with temporary:
            shutil.copy2(
                candidate / "agents" / "evidence_tester.toml",
                candidate / "agents" / "luna_tester.toml",
            )
            errors = self.validate(candidate).errors
            self.assertTrue(any("agent catalog" in error or "legacy roles" in error for error in errors))

    def test_accepts_unrelated_custom_role(self):
        temporary, candidate = clone_candidate()
        with temporary:
            (candidate / "agents" / "project_specialist.toml").write_text(
                'name = "project_specialist"\n'
            )
            self.assertEqual(self.validate(candidate).errors, [])

    def test_ignores_unrelated_agents_sections(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "AGENTS.md"
            path.write_text(
                path.read_text()
                + "\n## Project notes\n\n"
                + "A historical luna_scout note and gpt-5.6-local example live here.\n"
            )
            self.assertEqual(self.validate(candidate).errors, [])

    def test_rejects_role_name_mismatch(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "boundary_mapper.toml"
            path.write_text(
                path.read_text().replace('name = "boundary_mapper"', 'name = "mapper"')
            )
            errors = self.validate(candidate).errors
            self.assertTrue(any("name mismatch" in error for error in errors))

    def test_rejects_reviewer_effort_inheritance_or_drift(self):
        for replacement in ('model_reasoning_effort = "high"', ''):
            temporary, candidate = clone_candidate()
            with temporary:
                path = candidate / "agents" / "risk_reviewer.toml"
                path.write_text(path.read_text().replace(
                    'model_reasoning_effort = "xhigh"',
                    replacement,
                ))
                self.assertTrue(any(
                    "risk_reviewer: effort must be xhigh" in error
                    for error in self.validate(candidate).errors
                ))

        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "risk_reviewer_max.toml"
            path.write_text(path.read_text().replace(
                'model_reasoning_effort = "max"',
                'model_reasoning_effort = "xhigh"',
            ))
            self.assertTrue(any(
                "risk_reviewer_max: effort must be max" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_reviewer_indeterminate_contract_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "risk_reviewer.toml"
            path.write_text(path.read_text().replace(
                "Gate recommendation: INDETERMINATE / ESCALATE",
                "Gate recommendation: MAYBE",
            ))
            self.assertTrue(any(
                "missing receipt marker" in error or "integrity mismatch" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_max_reviewer_recursive_escalation(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "risk_reviewer_max.toml"
            path.write_text(path.read_text().replace(
                "Do not recommend another review, escalation, or higher effort.",
                "Use `Gate recommendation: INDETERMINATE / ESCALATE` and request a fresh `max` review.",
            ))
            errors = self.validate(candidate).errors
            self.assertTrue(any(
                "must not request another max review" in error
                for error in errors
            ))

    def test_rejects_non_ascii_reviewer_prompt(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "risk_reviewer.toml"
            path.write_text(path.read_text().replace(
                "Review only the named final-state",
                "审查 Review only the named final-state",
            ))
            self.assertTrue(any(
                "developer_instructions must contain ASCII only" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_role_output_audience_language_drift(self):
        for role in (
            "evidence_tester",
            "boundary_mapper",
            "risk_reviewer",
            "risk_reviewer_max",
        ):
            with self.subTest(role=role):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "agents" / f"{role}.toml"
                    original = path.read_text()
                    old = "For `model-facing` output, use English."
                    self.assertIn(old, original)
                    path.write_text(original.replace(
                        old,
                        "For `model-facing` output, use the user's preferred language.",
                    ))
                    self.assertTrue(any(
                        "missing receipt marker" in error or "integrity mismatch" in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_required_role_handoff_field_drift(self):
        mutations = (
            ("evidence_tester", "`Acceptance fields`", "`Acceptance schema`"),
            ("boundary_mapper", "`Acceptance fields`", "`Acceptance schema`"),
            ("risk_reviewer", "`Named invariants`", "`Gate checklist`"),
            ("risk_reviewer_max", "`Escalation receipt`", "`Escalation note`"),
        )
        for role, old, new in mutations:
            with self.subTest(role=role):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "agents" / f"{role}.toml"
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new, 1))
                    self.assertTrue(any(
                        f"{role}: missing receipt marker" in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_reviewer_terminal_line_drift(self):
        mutations = (
            (
                "risk_reviewer",
                "`Gate recommendation: PASS`",
                "`Gate recommendation: PASS with evidence`",
            ),
            (
                "risk_reviewer_max",
                "`Gate recommendation: BLOCK / NO-GO`",
                "`Gate recommendation: BLOCK / NO-GO because evidence is missing`",
            ),
        )
        for role, old, new in mutations:
            with self.subTest(role=role):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "agents" / f"{role}.toml"
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new, 1))
                    self.assertTrue(any(
                        f"{role}: exact terminal protocol mismatch" in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_instruction_drift_or_recursive_exception(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "boundary_mapper.toml"
            path.write_text(path.read_text().replace(
                "Do not spawn agents or widen scope.",
                "Do not spawn agents unless the parent explicitly asks.",
            ))
            errors = self.validate(candidate).errors
            self.assertTrue(any(
                "recursion" in error or "integrity mismatch" in error
                for error in errors
            ))

    def test_rejects_implicit_disable_or_duplicate(self):
        for transform in (
            lambda text: text.replace("allow_implicit_invocation: true", "allow_implicit_invocation: false"),
            lambda text: text + "\nallow_implicit_invocation: true\n",
        ):
            temporary, candidate = clone_candidate()
            with temporary:
                path = candidate / "skills" / skill_dir.name / "agents" / "openai.yaml"
                path.write_text(transform(path.read_text()))
                self.assertTrue(any("implicit invocation" in error for error in self.validate(candidate).errors))

    def test_rejects_legacy_name_in_active_policy(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "SKILL.md"
            path.write_text(path.read_text() + "\nUse `luna_scout` for research.\n")
            self.assertTrue(any("legacy role name" in error for error in self.validate(candidate).errors))

    def test_rejects_quality_or_wall_time_drift(self):
        mutations = (
            (
                "Prefer higher stable verified quality.",
                "Prefer lower credits before quality.",
            ),
            (
                "Record wall time only as\ntelemetry",
                "Use wall time as a tie-breaker",
            ),
        )
        for old, new in mutations:
            temporary, candidate = clone_candidate()
            with temporary:
                path = (
                    candidate / "skills" / skill_dir.name
                    / "references" / "evaluation-policy.md"
                )
                path.write_text(path.read_text().replace(old, new))
                self.assertTrue(self.validate(candidate).errors)

    def test_rejects_concurrency_capacity_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "config.toml"
            original = path.read_text()
            old = "max_concurrent_threads_per_session = 16"
            self.assertIn(old, original)
            path.write_text(original.replace(
                old,
                "max_concurrent_threads_per_session = 8",
            ))
            self.assertTrue(any(
                "agents.max_concurrent_threads_per_session must be 16" in error
                for error in self.validate(candidate).errors
            ))

    def test_accepts_non_high_primary_reasoning_effort(self):
        for model, effort in (
            ("gpt-5.6-sol", "ultra"),
            ("gpt-5.6-terra", "low"),
        ):
            with self.subTest(model=model, effort=effort):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "config.toml"
                    text = path.read_text()
                    for key, value in (
                        ("model", model),
                        ("model_reasoning_effort", effort),
                    ):
                        pattern = rf"(?m)^{key}\s*=.*$"
                        replacement = f'{key} = "{value}"'
                        if re.search(pattern, text):
                            text = re.sub(pattern, replacement, text, count=1)
                        else:
                            text = replacement + "\n" + text
                    path.write_text(text)
                    self.assertEqual(self.validate(candidate).errors, [])

    def test_rejects_default_subagent_model_or_effort_drift(self):
        mutations = (
            (
                'default_subagent_model = "gpt-5.6-sol"',
                'default_subagent_model = "gpt-5.6-terra"',
                "agents.default_subagent_model must be gpt-5.6-sol",
            ),
            (
                'default_subagent_reasoning_effort = "high"',
                'default_subagent_reasoning_effort = "ultra"',
                "agents.default_subagent_reasoning_effort must be high",
            ),
        )
        for old, new, expected in mutations:
            with self.subTest(setting=old):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "config.toml"
                    path.write_text(path.read_text().replace(old, new, 1))
                    self.assertTrue(any(
                        expected in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_lifecycle_or_concurrency_drift(self):
        mutations = (
            (
                "skills/subagent-orchestrator/SKILL.md",
                "Treat a wait timeout as observation-only",
                "Treat a wait timeout as permission to interrupt",
            ),
            (
                "skills/subagent-orchestrator/references/delegation-contracts.md",
                "are non-terminal and are\nnot stale-state evidence",
                "prove that the child is stale",
            ),
            (
                "skills/subagent-orchestrator/references/routing-policy.md",
                "Allow up to three active direct children by\n   default",
                "Allow only one active direct child by default",
            ),
            (
                "AGENTS.md",
                "fresh",
                "stale",
            ),
        )
        for relative, old, new in mutations:
            with self.subTest(relative=relative):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / relative
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new))
                    self.assertTrue(self.validate(candidate).errors)

    def test_rejects_lifecycle_conformance_asset_drift(self):
        mutations = (
            (
                "tests/fixtures/lifecycle-trace.json",
                '"runtime_capacity": 16',
                '"runtime_capacity": 8',
            ),
            (
                "scripts/lifecycle_conformance.py",
                '"user_cancel",',
                '"wait_timeout",',
            ),
        )
        for relative, old, new in mutations:
            with self.subTest(relative=relative):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "skills" / skill_dir.name / relative
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new, 1))
                    self.assertTrue(any(
                        "lifecycle conformance asset integrity mismatch" in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_bounded_peer_policy_broadening(self):
        mutations = (
            (
                "references/routing-policy.md",
                "one additional level to at most two",
                "unlimited additional levels to any number of",
            ),
            (
                "references/routing-policy.md",
                "They cannot change authorization, scope, acceptance",
                "They may change authorization, scope, and acceptance",
            ),
            (
                "references/delegation-contracts.md",
                "Messages transfer evidence or dependency status only; they never amend a handoff.",
                "Messages may amend the handoff.",
            ),
            (
                "AGENTS.md",
                (
                    "only a skill-qualified bounded peer may delegate one level",
                    "仅 skill 准入的受限协作代理可继续委派一层",
                ),
                "bounded peers may delegate recursively",
            ),
        )
        for relative, old, new in mutations:
            with self.subTest(relative=relative):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = (
                        candidate / relative
                        if relative == "AGENTS.md"
                        else candidate / "skills" / skill_dir.name / relative
                    )
                    original = path.read_text()
                    marker = (
                        next((candidate for candidate in old if candidate in original), None)
                        if isinstance(old, tuple)
                        else old
                    )
                    self.assertIsNotNone(marker)
                    path.write_text(original.replace(marker, new, 1))
                    self.assertTrue(self.validate(candidate).errors)

    def test_rejects_unpromoted_role_retention_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "references" / "evaluation-policy.md"
            path.write_text(path.read_text().replace(
                "Retire an installed role with no promoted class.",
                "Keep every experimental role installed.",
            ))
            self.assertTrue(self.validate(candidate).errors)

    def test_rejects_mandatory_gate_exception_broadening(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "references" / "evaluation-policy.md"
            path.write_text(path.read_text().replace(
                "does not permit retention of any other unpromoted role.",
                "permits retention of every unpromoted role.",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_unbounded_or_confidence_seeking_max_escalation(self):
        mutations = (
            (
                "Record the trigger and allow at most one `max` escalation.",
                "Allow repeated `max` escalation until confidence is high.",
            ),
            (
                "a desire for more confidence\n  never qualifies",
                "a desire for more confidence always qualifies",
            ),
            (
                "the `xhigh` result is explicitly indeterminate because competing "
                "causal\n  explanations or cross-boundary reasoning remain",
                "the `xhigh` result may be conclusive",
            ),
            (
                "that ambiguity can change\n  an irreversible P0/P1, security, "
                "authorization, or data-integrity decision",
                "that ambiguity has no material effect",
            ),
            (
                "an ordinary BLOCK",
                "an ordinary BLOCK always qualifies",
            ),
            (
                "never substitute `default` or another role for it",
                "substitute `default` whenever convenient",
            ),
            (
                "Start one fresh `risk_reviewer_max` only when the available evidence is sufficient",
                "Start one fresh `risk_reviewer_max` even when evidence is insufficient",
            ),
            (
                "For missing\n  evidence, obtain the evidence or keep the gate blocked",
                "Missing evidence qualifies for `max`",
            ),
            (
                "Complexity, file\n  count, a high-risk label, an ordinary BLOCK, or "
                "a desire for more confidence\n  never qualifies",
                "Complexity, file count, or a high-risk label qualifies for `max`",
            ),
        )
        for old, new in mutations:
            temporary, candidate = clone_candidate()
            with temporary:
                path = candidate / "skills" / skill_dir.name / "references" / "routing-policy.md"
                original = path.read_text()
                self.assertIn(old, original)
                path.write_text(original.replace(old, new))
                self.assertTrue(any(
                    "missing policy text" in error
                    for error in self.validate(candidate).errors
                ))

    def test_rejects_reviewer_effort_experiment_retirement_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "references" / "evaluation-policy.md"
            original = path.read_text()
            old = (
                "A reviewer-effort\nexperiment never retires `risk_reviewer`: a failed candidate effort returns the\n"
                "role to its last accepted fixed effort and leaves the named gate installed."
            )
            self.assertIn(old, original)
            path.write_text(original.replace(
                old,
                "A failed reviewer-effort experiment retires the named gate.",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_appended_contradictory_policy(self):
        contradictions = (
            (
                "routing-policy.md",
                "\nMissing evidence or task complexity qualifies for max.\n",
            ),
            (
                "evaluation-policy.md",
                "\nA failed reviewer-effort experiment retires risk_reviewer.\n",
            ),
            (
                "delegation-contracts.md",
                "\nModel-facing output may use any language selected by the child.\n",
            ),
            (
                "delegation-contracts.md",
                "\nA wait timeout authorizes interruption.\n",
            ),
        )
        for relative, appended in contradictions:
            with self.subTest(relative=relative):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "skills" / skill_dir.name / "references" / relative
                    path.write_text(path.read_text() + appended)
                    self.assertTrue(any(
                        "canonical policy integrity mismatch" in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_appended_skill_lifecycle_contradiction(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "SKILL.md"
            path.write_text(
                path.read_text()
                + "\nInterrupt a child after three consecutive wait timeouts.\n"
            )
            self.assertTrue(any(
                "canonical workflow integrity mismatch" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_missing_output_audience_contract(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = (
                candidate / "skills" / skill_dir.name
                / "references" / "delegation-contracts.md"
            )
            original = path.read_text()
            field = "Output audience: <user-facing | model-facing>\n"
            self.assertIn(field, original)
            path.write_text(original.replace(field, ""))
            self.assertTrue(any(
                "missing policy text" in error or "canonical policy integrity mismatch" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_missing_lifecycle_contract_fields(self):
        fields = (
            "Completion dependency: <required-before-integration | independent-before-final>\n",
            "Concurrent peers: <none | non-overlapping task names>\n",
            "User deadline: <none | explicit user condition>\n",
            (
                "Cancellation authority: <user cancel/replace, concrete safety/scope violation, "
                "proven stale state, terminal platform failure, or explicit user deadline>\n"
            ),
        )
        for field in fields:
            with self.subTest(field=field):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = (
                        candidate / "skills" / skill_dir.name
                        / "references" / "delegation-contracts.md"
                    )
                    original = path.read_text()
                    self.assertIn(field, original)
                    path.write_text(original.replace(field, ""))
                    self.assertTrue(self.validate(candidate).errors)

    def test_rejects_missing_typed_handoff_fields(self):
        fields = (
            "Topology: <leaf | bounded-peer>\n",
            "Delegation depth: <0 | 1>\n",
            "Message peers: <none | task names + evidence/dependency purpose>\n",
            "Context policy: <fresh | inherited + material reason>\n",
            "Acceptance fields: <not-applicable | one or more exact output-heading labels>\n",
            "Named invariants: <not-applicable | one or more exact gate invariants>\n",
            (
                "Escalation receipt: <not-applicable | prior terminal line + sufficient evidence "
                "+ competing explanations + irreversible decision>\n"
            ),
            "Artifact contract: <none | path or body + format + writer + transfer rule>\n",
        )
        for field in fields:
            with self.subTest(field=field):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = (
                        candidate / "skills" / skill_dir.name
                        / "references" / "delegation-contracts.md"
                    )
                    original = path.read_text()
                    self.assertIn(field, original)
                    path.write_text(original.replace(field, "", 1))
                    self.assertTrue(any(
                        "missing policy text" in error
                        or "canonical policy integrity mismatch" in error
                        for error in self.validate(candidate).errors
                    ))

    def test_rejects_canonical_artifact_transfer_drift(self):
        for relative, old, new in (
            ("skills/subagent-orchestrator/references/delegation-contracts.md", "ARTIFACT_BODY_BEGIN", "BODY_START"),
            ("agents/boundary_mapper.toml", "ARTIFACT_BODY_BEGIN", "BODY_START"),
        ):
            with self.subTest(relative=relative):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / relative
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new))
                    self.assertTrue(self.validate(candidate).errors)

    def test_rejects_final_gate_or_artifact_ownership_drift(self):
        for relative, old, new in (
            (
                "references/routing-policy.md",
                "fresh `risk_reviewer`",
                "optional reviewer",
            ),
            (
                "references/delegation-contracts.md",
                "primary samples but does not rewrite it",
                "the primary rewrites it after sampling",
            ),
            (
                "AGENTS.md",
                "fresh",
                "stale",
            ),
        ):
            with self.subTest(relative=relative):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = (
                        candidate / relative
                        if relative == "AGENTS.md"
                        else candidate / "skills" / skill_dir.name / relative
                    )
                    path.write_text(path.read_text().replace(old, new))
                    self.assertTrue(self.validate(candidate).errors)

    def test_rejects_role_details_in_global_policy(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "AGENTS.md"
            text = path.read_text()
            heading = next(
                heading
                for heading in (
                    "## Subagents and parallelism\n",
                    "## 子代理与并行\n",
                )
                if heading in text
            )
            self.assertIn(heading, text)
            path.write_text(text.replace(
                heading,
                heading + "\n- `evidence_tester` must emit `ARTIFACT_BODY_BEGIN`.\n",
                1,
            ))
            errors = self.validate(candidate).errors
            self.assertTrue(any(
                "two bullets" in error or "leaks implementation detail" in error
                for error in errors
            ))

    def test_rejects_reference_details_in_skill_body(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "SKILL.md"
            path.write_text(path.read_text() + "\nUse gpt-5.6-luna and fsync every artifact.\n")
            errors = self.validate(candidate).errors
            self.assertTrue(any("duplicates reference or role detail" in error for error in errors))

    def test_rejects_evidence_contract_broadening(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = (
                candidate / "skills" / skill_dir.name
                / "references" / "routing-policy.md"
            )
            original = path.read_text()
            bounded = (
                "| Material bounded log corpus | `evidence_tester` | Exhaustive "
                "multi-file or large-log scan, explicit runbook, acceptance fields, "
                "and requested evidence artifact |"
            )
            self.assertIn(bounded, original)
            path.write_text(original.replace(
                bounded,
                "| Any bounded log | `evidence_tester` | Artifact requested |",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_small_diagnosis_broadening(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = (
                candidate / "skills" / skill_dir.name
                / "references" / "routing-policy.md"
            )
            path.write_text(path.read_text().replace(
                "A short single log, a small direct diagnosis, or a narrow test failure "
                "remains\nprimary even when an artifact is requested.",
                "Any log diagnosis may use evidence_tester.",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_routing_read_precedence_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = (
                candidate / "skills" / skill_dir.name
                / "references" / "routing-policy.md"
            )
            path.write_text(path.read_text().replace(
                "Read this reference whenever delegation is being considered.",
                "Read this reference only when routing is ambiguous.",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_fast_tier_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "evidence_tester.toml"
            path.write_text(path.read_text().replace(
                'service_tier = "default"',
                'service_tier = "fast"',
            ))
            self.assertTrue(any(
                "tier must be default" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_runtime_details_in_routing_policy(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = (
                candidate / "skills" / skill_dir.name
                / "references" / "routing-policy.md"
            )
            path.write_text(path.read_text() + "\nUse gpt-5.6-luna with service_tier fast.\n")
            self.assertTrue(any(
                "duplicates executable TOML configuration" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_role_behavior_in_delegation_contract(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = (
                candidate / "skills" / skill_dir.name
                / "references" / "delegation-contracts.md"
            )
            path.write_text(path.read_text() + "\n`evidence_tester` owns triage.\n")
            self.assertTrue(any(
                "duplicates role-specific behavior" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_undeclared_python_bytecode(self):
        temporary, candidate = clone_candidate()
        with temporary:
            cache = candidate / "skills" / skill_dir.name / "scripts" / "__pycache__"
            cache.mkdir()
            (cache / "validator.cpython-999.pyc").write_bytes(b"derived")
            self.assertTrue(any(
                "undeclared Python bytecode" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_missing_mandatory_reviewer(self):
        temporary, candidate = clone_candidate()
        with temporary:
            (candidate / "agents" / "risk_reviewer.toml").unlink()
            self.assertTrue(any(
                "agent catalog" in error for error in self.validate(candidate).errors
            ))

    def test_rejects_same_fixture_as_generalization_evidence(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "references" / "evaluation-policy.md"
            path.write_text(path.read_text().replace(
                "Repeating one fixture measures stability only;\nit does not count as another generalization instance.",
                "Repeating one fixture three times proves generalization.",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_holdout_freeze_or_invalidation_drift(self):
        mutations = (
            (
                "Freeze the role instructions, routing policy, task fixtures, and graders",
                "Tune roles after reading every fixture and grader",
            ),
            (
                "A role instruction or eligibility\nchange invalidates prior promotion evidence",
                "Prompt changes preserve all old promotion evidence",
            ),
            (
                "requires deterministic state-machine conformance plus a current\nclient capability receipt before activation",
                "requires no targeted conformance",
            ),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                temporary, candidate = clone_candidate()
                with temporary:
                    path = candidate / "skills" / skill_dir.name / "references" / "evaluation-policy.md"
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new))
                    self.assertTrue(self.validate(candidate).errors)

    def test_rejects_surface_form_scoring_drift(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "references" / "evaluation-policy.md"
            path.write_text(path.read_text().replace(
                "A copied label,\nkeyword, prescribed phrase, or checklist item earns no credit",
                "A copied keyword or checklist item earns full credit",
            ))
            self.assertTrue(any(
                "missing policy text" in error
                for error in self.validate(candidate).errors
            ))

    def test_rejects_fixed_domain_checklist_in_routing_policy(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "skills" / skill_dir.name / "references" / "routing-policy.md"
            path.write_text(path.read_text() + "\nAlways require fsync and atomic replacement.\n")
            errors = self.validate(candidate).errors
            self.assertTrue(any(
                "fixed domain checklist" in error
                for error in errors
            ))

    def test_rejects_acceptance_label_as_proof(self):
        temporary, candidate = clone_candidate()
        with temporary:
            path = candidate / "agents" / "evidence_tester.toml"
            path.write_text(path.read_text().replace(
                "Treat each label only as schema",
                "Treat each label as proof",
            ))
            self.assertTrue(any(
                "receipt marker" in error or "integrity mismatch" in error
                for error in self.validate(candidate).errors
            ))

    def test_managed_config_projection_tracks_only_subagent_settings(self):
        config = module.load_toml(codex_home / "config.toml")
        with_projects = copy.deepcopy(config)
        with_projects["projects"] = {"/dynamic/workspace": {"trust_level": "trusted"}}
        self.assertEqual(
            module.managed_config_projection(config),
            module.managed_config_projection(with_projects),
        )
        primary_drift = copy.deepcopy(with_projects)
        primary_drift["model"] = "gpt-5.6-terra"
        primary_drift["model_reasoning_effort"] = "ultra"
        self.assertEqual(
            module.managed_config_projection(config),
            module.managed_config_projection(primary_drift),
        )
        subagent_drift = copy.deepcopy(with_projects)
        subagent_drift["agents"]["default_subagent_reasoning_effort"] = "ultra"
        self.assertNotEqual(
            module.managed_config_projection(config),
            module.managed_config_projection(subagent_drift),
        )


if __name__ == "__main__":
    unittest.main()

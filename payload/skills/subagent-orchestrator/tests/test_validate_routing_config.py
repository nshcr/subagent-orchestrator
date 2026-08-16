from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest


skill_dir = Path(__file__).parents[1]
candidate_home = skill_dir.parents[1]
spec = spec_from_file_location("routing_validator", skill_dir / "scripts" / "validate-routing-config.py")
module = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def installed_candidate() -> tuple[tempfile.TemporaryDirectory, Path]:
    temporary = tempfile.TemporaryDirectory()
    home = Path(temporary.name) / "codex-home"
    home.mkdir()
    if (candidate_home / "AGENTS.md").is_file():
        shutil.copy2(candidate_home / "AGENTS.md", home / "AGENTS.md")
        shutil.copy2(candidate_home / "config.toml", home / "config.toml")
        shutil.copytree(candidate_home / "agents", home / "agents")
    else:
        shutil.copy2(candidate_home / "AGENTS.section.en.md", home / "AGENTS.md")
        shutil.copy2(candidate_home / "config.agents.toml", home / "config.toml")
        shutil.copytree(candidate_home / "agents", home / "agents")
    (home / "skills").mkdir()
    shutil.copytree(skill_dir, home / "skills" / skill_dir.name)
    installed_skill = home / "skills" / skill_dir.name / "SKILL.md"
    for role in (home / "agents").glob("*.toml"):
        text = role.read_text()
        text = text.replace("{{SKILL_PATH}}", str(installed_skill))
        text = re.sub(
            r'(?m)^path = ".*?/subagent-orchestrator/SKILL\.md"$',
            f'path = "{installed_skill}"',
            text,
        )
        role.write_text(text)
    return temporary, home


class RoutingContractTest(unittest.TestCase):
    def validate(self, home):
        return module.validate(home, home / "skills" / skill_dir.name / "SKILL.md").errors

    def mutate(self, relative, old, new):
        temporary, home = installed_candidate()
        with temporary:
            path = home / relative
            original = path.read_text()
            self.assertIn(old, original)
            path.write_text(original.replace(old, new, 1))
            return self.validate(home)

    def mutate_skill(self, relative, old, new):
        return self.mutate(f"skills/{skill_dir.name}/{relative}", old, new)

    def assert_error(self, errors, marker):
        self.assertTrue(any(marker in error for error in errors), errors)

    def test_accepts_staged_contract(self):
        temporary, home = installed_candidate()
        with temporary:
            self.assertEqual(self.validate(home), [])

    def test_rejects_custom_role_runtime_or_instruction_drift(self):
        for role, old, new in (
            ("risk_reviewer", 'model_reasoning_effort = "xhigh"', 'model_reasoning_effort = "high"'),
            ("boundary_mapper", "Do not spawn agents or widen scope.", "Spawn agents when useful."),
        ):
            temporary, home = installed_candidate()
            with temporary, self.subTest(role=role):
                path = home / "agents" / f"{role}.toml"
                path.write_text(path.read_text().replace(old, new))
                self.assertTrue(self.validate(home))

    def test_rejects_policy_hash_drift(self):
        for relative, marker in (
            ("SKILL.md", "fork_turns=none"),
            ("references/routing-policy.md", "verification-token asset never proves materiality"),
            ("references/delegation-contracts.md", "after two, reject another writer spawn or follow-up"),
            ("references/evaluation-policy.md", "auto-create a task"),
        ):
            temporary, home = installed_candidate()
            with temporary, self.subTest(relative=relative):
                path = home / "skills" / skill_dir.name / relative
                self.assertIn(marker, path.read_text())
                path.write_text(path.read_text().replace(marker, "BROKEN", 1))
                self.assertTrue(any("integrity mismatch" in error for error in self.validate(home)))

    def test_rejects_global_policy_drift(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "AGENTS.md"
            path.write_text(path.read_text().replace("fresh", "stale", 1))
            self.assertTrue(self.validate(home))

    def test_rejects_lifecycle_asset_drift(self):
        for relative, old, new in (
            ("scripts/lifecycle_conformance.py", '"host", "owner", "sealed-harness"', '"agent", "owner", "sealed-harness"'),
            ("tests/fixtures/lifecycle-trace.json", '"runtime_capacity": 16', '"runtime_capacity": 99'),
        ):
            temporary, home = installed_candidate()
            with temporary, self.subTest(relative=relative):
                path = home / "skills" / skill_dir.name / relative
                path.write_text(path.read_text().replace(old, new, 1))
                self.assertTrue(any("lifecycle conformance asset integrity mismatch" in error for error in self.validate(home)))

    def test_rejects_context_or_gate_broadening(self):
        for relative, old, new in (
            ("SKILL.md", "full-history children", "full-history children may be"),
            ("references/routing-policy.md", "Three disjoint fresh gates PASS", "One majority gate passes"),
            ("references/delegation-contracts.md", "10% of one frozen", "all source bytes"),
            ("references/evaluation-policy.md", "self-issued, proxied", "self-issued or proxied accepted"),
        ):
            temporary, home = installed_candidate()
            with temporary, self.subTest(relative=relative):
                path = home / "skills" / skill_dir.name / relative
                path.write_text(path.read_text().replace(old, new, 1))
                self.assertTrue(self.validate(home))

    def test_accepts_unrelated_role_and_primary_settings(self):
        temporary, home = installed_candidate()
        with temporary:
            (home / "agents" / "project-local.toml").write_text('name = "project-local"\n')
            with (home / "config.toml").open("a") as stream:
                stream.write('\nmodel = "gpt-5.6-terra"\nmodel_reasoning_effort = "ultra"\n')
            self.assertEqual(self.validate(home), [])

    def test_rejects_missing_active_role(self):
        temporary, home = installed_candidate()
        with temporary:
            (home / "agents" / "evidence_tester.toml").unlink()
            self.assert_error(self.validate(home), "agent catalog missing")

    def test_rejects_legacy_role_but_accepts_unrelated_role(self):
        temporary, home = installed_candidate()
        with temporary:
            shutil.copy2(home / "agents" / "evidence_tester.toml", home / "agents" / "luna_tester.toml")
            self.assert_error(self.validate(home), "legacy roles")
        temporary, home = installed_candidate()
        with temporary:
            (home / "agents" / "project-specialist.toml").write_text('name = "project-specialist"\n')
            self.assertEqual(self.validate(home), [])

    def test_accepts_unrelated_agents_markdown_sections(self):
        temporary, home = installed_candidate()
        with temporary:
            with (home / "AGENTS.md").open("a") as stream:
                stream.write("\n## Project notes\n\nHistorical luna_scout text is inert here.\n")
            self.assertEqual(self.validate(home), [])

    def test_rejects_role_name_mismatch(self):
        errors = self.mutate("agents/boundary_mapper.toml", 'name = "boundary_mapper"', 'name = "mapper"')
        self.assert_error(errors, "name mismatch")

    def test_rejects_role_model_effort_tier_and_sandbox_drift(self):
        mutations = (
            ('model = "gpt-5.6-sol"', 'model = "gpt-5.6-terra"', "model must be"),
            ('model_reasoning_effort = "xhigh"', 'model_reasoning_effort = "high"', "effort must be"),
            ('service_tier = "default"', 'service_tier = "priority"', "tier must be"),
            ('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"', "sandbox must be"),
        )
        for old, new, marker in mutations:
            with self.subTest(field=old):
                self.assert_error(self.mutate("agents/risk_reviewer.toml", old, new), marker)

    def test_rejects_reviewer_indeterminate_terminal_drift(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "agents" / "risk_reviewer.toml"
            old = "`Gate recommendation: INDETERMINATE / ESCALATE`"
            prefix, suffix = path.read_text().rsplit(old, 1)
            path.write_text(prefix + "`Gate recommendation: MAYBE`" + suffix)
            errors = self.validate(home)
            self.assert_error(errors, "terminal protocol")

    def test_rejects_max_reviewer_recursive_escalation(self):
        errors = self.mutate("agents/risk_reviewer_max.toml", "Do not recommend another review, escalation, or higher effort.", "Request a fresh `max` review.")
        self.assert_error(errors, "must not request another max review")

    def test_rejects_non_ascii_reviewer_prompt(self):
        errors = self.mutate("agents/risk_reviewer.toml", "Review only the named final-state", "审查 Review only the named final-state")
        self.assert_error(errors, "ASCII only")

    def test_rejects_role_output_language_contract_drift(self):
        for role in module.ROLE_POLICY:
            with self.subTest(role=role):
                errors = self.mutate(f"agents/{role}.toml", "For `model-facing` output, use English.", "For `model-facing` output, use any language.")
                self.assert_error(errors, "missing receipt marker")

    def test_rejects_required_role_handoff_field_drift(self):
        for role, old, new in (
            ("evidence_tester", "`Acceptance fields`", "`Acceptance schema`"),
            ("boundary_mapper", "`Acceptance fields`", "`Acceptance schema`"),
            ("risk_reviewer", "`Named invariants`", "`Gate checklist`"),
            ("risk_reviewer_max", "`Escalation receipt`", "`Escalation note`"),
        ):
            with self.subTest(role=role):
                self.assert_error(self.mutate(f"agents/{role}.toml", old, new), "missing receipt marker")

    def test_rejects_reviewer_standalone_terminal_line_drift(self):
        errors = self.mutate("agents/risk_reviewer.toml", "`Gate recommendation: PASS`", "`Gate recommendation: PASS with evidence`")
        self.assert_error(errors, "exact terminal protocol mismatch")

    def test_rejects_role_recursion_or_scope_exception(self):
        errors = self.mutate("agents/boundary_mapper.toml", "Do not spawn agents or widen scope.", "Do not spawn agents unless the parent asks.")
        self.assertTrue(any("recursion" in error or "integrity mismatch" in error for error in errors), errors)

    def test_rejects_missing_or_wrong_skill_disable_path(self):
        for old, new in (("enabled = false", "enabled = true"), ("/subagent-orchestrator/SKILL.md", "/other/SKILL.md")):
            with self.subTest(change=old):
                errors = self.mutate("agents/evidence_tester.toml", old, new)
                self.assert_error(errors, "must disable")

    def test_rejects_openai_yaml_implicit_disable_or_duplicate(self):
        errors = self.mutate_skill("agents/openai.yaml", "allow_implicit_invocation: true", "allow_implicit_invocation: false")
        self.assert_error(errors, "implicit invocation")
        temporary, home = installed_candidate()
        with temporary:
            path = home / "skills" / skill_dir.name / "agents" / "openai.yaml"
            path.write_text(path.read_text() + "\nallow_implicit_invocation: true\n")
            self.assert_error(self.validate(home), "implicit invocation")

    def test_rejects_legacy_role_name_in_active_policy(self):
        errors = self.mutate_skill("SKILL.md", "Unsupported or capability-unverified work stays primary.", "Unsupported work uses luna_scout.")
        self.assert_error(errors, "legacy role name")

    def test_rejects_quality_priority_or_wall_time_drift(self):
        for old, new in (
            ("Never trade quality\nfor cost.", "Prefer lower cost over quality."),
            ("Wall time is telemetry only.", "Wall time breaks promotion ties."),
        ):
            with self.subTest(old=old):
                self.assert_error(self.mutate_skill("references/evaluation-policy.md", old, new), "missing policy text")

    def test_rejects_direct_child_or_runtime_capacity_drift(self):
        errors = self.mutate("config.toml", "max_concurrent_threads_per_session = 16", "max_concurrent_threads_per_session = 8")
        self.assert_error(errors, "must be 16")
        errors = self.mutate_skill("references/routing-policy.md", "Start at most three qualified direct children", "Start unlimited direct children")
        self.assertTrue(errors)

    def test_accepts_unconstrained_primary_model_and_effort(self):
        for model, effort in (("gpt-5.6-sol", "ultra"), ("gpt-5.6-terra", "low")):
            temporary, home = installed_candidate()
            with temporary, self.subTest(model=model, effort=effort):
                with (home / "config.toml").open("a") as stream:
                    stream.write(f'\nmodel = "{model}"\nmodel_reasoning_effort = "{effort}"\n')
                self.assertEqual(self.validate(home), [])

    def test_rejects_default_child_model_or_effort_drift(self):
        for old, new, marker in (
            ('default_subagent_model = "gpt-5.6-sol"', 'default_subagent_model = "gpt-5.6-terra"', "default_subagent_model"),
            ('default_subagent_reasoning_effort = "high"', 'default_subagent_reasoning_effort = "ultra"', "default_subagent_reasoning_effort"),
        ):
            self.assert_error(self.mutate("config.toml", old, new), marker)

    def test_rejects_lifecycle_owner_hash_or_trace_drift(self):
        errors = self.mutate_skill("tests/fixtures/lifecycle-trace.json", '"runtime_capacity": 16', '"runtime_capacity": 8')
        self.assert_error(errors, "lifecycle conformance asset integrity mismatch")
        errors = self.mutate_skill("SKILL.md", "Freeze only after the writer is terminal.", "Freeze before writer terminal.")
        self.assertTrue(errors)

    def test_rejects_bounded_peer_depth_cap_or_message_broadening(self):
        for old, new in (
            ("one additional level with at most two", "unlimited recursive levels"),
            ("cannot start a turn or change authority", "may amend authorization"),
            ("Custom-role and unregistered peer messages are hard blockers.", "All peers may message."),
        ):
            relative = "references/routing-policy.md" if "additional" in old else "references/delegation-contracts.md"
            self.assertTrue(self.mutate_skill(relative, old, new))

    def test_rejects_governance_retention_broadening(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "Retire any other installed role with no promoted class.", "Keep every experimental role installed.")
        self.assertTrue(errors)

    def test_rejects_mandatory_gate_efficiency_conflation(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "it cannot claim efficiency success.", "it always claims efficiency success.")
        self.assert_error(errors, "missing policy text")

    def test_rejects_unbounded_or_confidence_seeking_max(self):
        for old, new in (
            ("One `risk_reviewer_max`\nis allowed only", "Repeated max reviewers are allowed"),
            ("Complexity, ordinary BLOCK, or confidence seeking never qualifies.", "Complexity always qualifies."),
        ):
            self.assertTrue(self.mutate_skill("references/routing-policy.md", old, new))

    def test_rejects_reviewer_effort_retirement(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "Reviewer effort experiments\nnever retire the accepted named gate", "Reviewer experiments retire the named gate")
        self.assertTrue(errors)

    def test_rejects_appended_contradictory_policy(self):
        for relative, appended in (
            ("references/routing-policy.md", "\nMissing evidence qualifies for delegation.\n"),
            ("references/evaluation-policy.md", "\nProduction observation proves pilot-signed.\n"),
            ("references/delegation-contracts.md", "\nWait timeout authorizes interruption.\n"),
        ):
            temporary, home = installed_candidate()
            with temporary, self.subTest(relative=relative):
                path = home / "skills" / skill_dir.name / relative
                path.write_text(path.read_text() + appended)
                self.assert_error(self.validate(home), "canonical policy integrity mismatch")

    def test_rejects_missing_output_audience_or_typed_transfer_fields(self):
        for marker in ("Output audience: <user-facing | model-facing>", "Producer / consumer / task / slice", "Admitted state digest: <digest>", "Completion conditions: <exact conditions>"):
            with self.subTest(marker=marker):
                errors = self.mutate_skill("references/delegation-contracts.md", marker, "REMOVED")
                self.assertTrue(errors)

    def test_rejects_artifact_transfer_or_final_gate_ownership_drift(self):
        for old, new in (
            ("ARTIFACT_BODY_BEGIN", "BODY_START"),
            ("Each invariant belongs to exactly one task-wide gate", "Invariants may be voted on"),
            ("primary owns authorization, integration, conflict handling, and acceptance", "reviewer owns final acceptance"),
        ):
            self.assertTrue(self.mutate_skill("references/delegation-contracts.md", old, new))

    def test_rejects_role_details_in_global_policy(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "AGENTS.md"
            text = path.read_text()
            heading = next(item for item in ("## Subagents and parallelism\n", "## 子代理与并行\n") if item in text)
            text = text.replace(heading, heading + "\n- `evidence_tester` emits ARTIFACT_BODY_BEGIN.\n", 1)
            path.write_text(text)
            errors = self.validate(home)
            self.assertTrue(any("two bullets" in error or "leaks implementation detail" in error for error in errors), errors)

    def test_rejects_reference_or_runtime_details_in_skill_entry(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "skills" / skill_dir.name / "SKILL.md"
            path.write_text(path.read_text() + "\nUse gpt-5.6-luna and fsync every artifact.\n")
            self.assert_error(self.validate(home), "duplicates reference or role detail")

    def test_rejects_materiality_evidence_broadening(self):
        for old, new in (
            ("verification-token asset never proves materiality", "verification-token proves materiality"),
            ("host, owner, or sealed harness signs", "agent self-signs"),
            ("at least three and 8192", "one byte is sufficient"),
        ):
            self.assertTrue(self.mutate_skill("references/routing-policy.md", old, new))

    def test_rejects_small_leaf_as_material_work(self):
        errors = self.mutate_skill("references/routing-policy.md", "ordinary leaf, two tiny files, padding, duplicate ranges", "every tiny leaf")
        self.assertTrue(errors)

    def test_rejects_routing_read_precedence_drift(self):
        errors = self.mutate_skill("SKILL.md", "Read [routing policy](references/routing-policy.md) and\n   [evaluation policy](references/evaluation-policy.md) before delegation.", "Delegate before reading policy.")
        self.assert_error(errors, "missing policy text")

    def test_rejects_fast_tier_as_promotion_evidence(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "exclude that experiment from quality/credits promotion", "count fast experiments as promotion")
        self.assertTrue(errors)

    def test_rejects_runtime_configuration_in_routing_policy(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "skills" / skill_dir.name / "references" / "routing-policy.md"
            path.write_text(path.read_text() + '\nUse service_tier="priority" and sandbox_mode="danger".\n')
            self.assert_error(self.validate(home), "duplicates executable TOML configuration")

    def test_rejects_role_behavior_in_generic_delegation_contract(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "skills" / skill_dir.name / "references" / "delegation-contracts.md"
            path.write_text(path.read_text() + "\nrisk_reviewer owns this transfer.\n")
            self.assert_error(self.validate(home), "duplicates role-specific behavior")

    def test_rejects_undeclared_python_bytecode(self):
        temporary, home = installed_candidate()
        with temporary:
            cache = home / "skills" / skill_dir.name / "scripts" / "__pycache__"
            cache.mkdir()
            (cache / "orphan.pyc").write_bytes(b"bytecode")
            self.assert_error(self.validate(home), "undeclared Python bytecode")

    def test_rejects_missing_mandatory_reviewer(self):
        temporary, home = installed_candidate()
        with temporary:
            (home / "agents" / "risk_reviewer.toml").unlink()
            self.assert_error(self.validate(home), "agent catalog missing")

    def test_rejects_repeated_fixture_as_generalization(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "Repeated fixtures measure stability, not generalization.", "Repeated fixtures prove generalization.")
        self.assertTrue(errors)

    def test_rejects_holdout_freeze_or_invalidation_drift(self):
        for old, new in (
            ("Freeze\nrole instructions, routing, fixtures, and graders before holdout.", "Tune against holdout."),
            ("A changed role or\neligibility invalidates prior class evidence", "Changed roles keep old evidence"),
        ):
            self.assertTrue(self.mutate_skill("references/evaluation-policy.md", old, new))

    def test_rejects_surface_form_scoring(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "checklist surface form earn no\nquality credit", "checklist surface form earns quality")
        self.assert_error(errors, "missing policy text")

    def test_rejects_fixed_domain_checklist_in_routing(self):
        temporary, home = installed_candidate()
        with temporary:
            path = home / "skills" / skill_dir.name / "references" / "routing-policy.md"
            path.write_text(path.read_text() + "\nRequire fsync and atomic replacement for every task.\n")
            self.assert_error(self.validate(home), "leaks a fixed domain checklist")

    def test_rejects_acceptance_label_as_expected_conclusion(self):
        errors = self.mutate_skill("references/evaluation-policy.md", "Acceptance\nlabels define evidence schema, never expected conclusions.", "Acceptance labels prove expected conclusions.")
        self.assert_error(errors, "missing policy text")

    def test_managed_config_projection_tracks_only_subagent_settings(self):
        projection = module.managed_config_projection({
            "model": "gpt-5.6-terra",
            "agents": {
                "enabled": True,
                "max_concurrent_threads_per_session": 16,
                "interrupt_message": True,
                "default_subagent_model": "gpt-5.6-sol",
                "default_subagent_reasoning_effort": "high",
                "project_extra": "preserve",
            },
        })
        self.assertEqual(set(projection), {"agents"})
        self.assertNotIn("project_extra", projection["agents"])

    def test_rejects_pilot_or_evidence_tier_broadening(self):
        for old, new in (
            ("auto-create a task", "auto-create tasks automatically"),
            ("Missing CI, target, or signature evidence caps the result at\n`verified-local`", "Missing evidence permits pilot-signed"),
            ("Reject self-issued, proxied", "Accept self-issued or proxied"),
        ):
            self.assertTrue(self.mutate_skill("references/evaluation-policy.md", old, new))


if __name__ == "__main__":
    unittest.main()

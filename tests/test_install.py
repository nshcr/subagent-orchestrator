from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PACKAGE_ROOT = Path(__file__).parents[1]
INSTALLER = PACKAGE_ROOT / "install.py"
SPEC = spec_from_file_location("subagent_orchestrator_installer", INSTALLER)
INSTALL_MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = INSTALL_MODULE
SPEC.loader.exec_module(INSTALL_MODULE)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.codex_home = Path(self.temporary.name) / "codex-home"

    def tearDown(self):
        self.temporary.cleanup()

    def run_installer(self, action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(INSTALLER),
                "--codex-home",
                str(self.codex_home),
                "--agents-language",
                "en",
                action,
            ],
            cwd=PACKAGE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_check_is_read_only_and_reports_hashes(self):
        result = self.run_installer("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WOULD_TOUCH AGENTS.md ", result.stdout)
        self.assertFalse(self.codex_home.exists())

    def test_apply_renders_role_paths_and_is_idempotent(self):
        first = self.run_installer("--apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("TOUCHED agents/risk_reviewer.toml ", first.stdout)
        role = (self.codex_home / "agents" / "risk_reviewer.toml").read_text()
        expected_skill = (
            self.codex_home.resolve()
            / "skills"
            / "subagent-orchestrator"
            / "SKILL.md"
        )
        self.assertIn(f'path = "{expected_skill}"', role)
        self.assertNotIn("{{SKILL_PATH}}", role)
        second = self.run_installer("--check")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0 path(s) would change", second.stdout)

    def test_explicit_chinese_policy_selection_and_language_switch(self):
        chinese = subprocess.run(
            [
                sys.executable,
                "-B",
                str(INSTALLER),
                "--codex-home",
                str(self.codex_home),
                "--agents-language",
                "zh",
                "--apply",
            ],
            cwd=PACKAGE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(chinese.returncode, 0, chinese.stderr)
        agents_path = self.codex_home / "AGENTS.md"
        self.assertIn("## 子代理与并行", agents_path.read_text())
        self.assertNotIn("## Subagents and parallelism", agents_path.read_text())

        switched = self.run_installer("--apply")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        self.assertIn("## Subagents and parallelism", agents_path.read_text())
        self.assertNotIn("## 子代理与并行", agents_path.read_text())

    def test_known_legacy_chinese_policy_can_migrate_without_state(self):
        self.codex_home.mkdir()
        predecessor = """## 子代理与并行

- 默认单代理。仅当用户明确要求委派/并行，或一个边界清晰的专用角色能替代可观的主代理工作或提供必需独立门禁时，使用 `$subagent-orchestrator`；复杂、文件多或可拆分本身都不足以触发。
- 可并行启动已分别满足资格、相互独立且所有权不重叠的最窄角色；不得为占满并发槽而委派，后续增派仍须由新的失败证据、未解边界或必需最终门禁触发。主代理保留授权、范围、单一写入者、整合与最终验收；子代理不得扩权或递归委派。
- 高风险最终状态必须接受 fresh、独立、只读审阅。具体目标函数、角色资格、模型配置、artifact 交接与晋级证据由 skill、references 和角色配置分别维护；主代理等待相关子任务终态后按最终工作区重新验收，单次等待超时、静默、耗时或 token/credit 使用均不是中断依据。
"""
        (self.codex_home / "AGENTS.md").write_text(predecessor)

        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.codex_home / "AGENTS.md").read_text()
        self.assertIn("## Subagents and parallelism", installed)
        self.assertNotIn("## 子代理与并行", installed)

    def test_known_predecessor_english_policy_can_migrate_without_state(self):
        self.codex_home.mkdir()
        predecessor = """## Subagents and parallelism

- Default to a single agent. Use `$subagent-orchestrator` only when the user explicitly requests delegation or parallel work, or when one bounded specialist can replace material primary work or provide a required independent gate; complexity, file count, and decomposability alone do not qualify.
- Start the narrowest already-qualified roles in parallel only when they are mutually independent and have non-overlapping ownership. Do not delegate to fill capacity, and add later roles only for new failure evidence, an unresolved boundary, or a required final gate. The primary retains authorization, scope, single-writer integration, synthesis, and final acceptance; children cannot expand authority or delegate recursively.
- High-risk final states require a fresh, independent, read-only review. The skill, references, and role configuration own the objective, eligibility, model settings, artifact handoff, and promotion evidence. The primary waits for required children to reach a terminal state and revalidates the final workspace; one wait timeout, silence, elapsed time, or token/credit use is not a cancellation reason.
"""
        (self.codex_home / "AGENTS.md").write_text(predecessor)

        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.codex_home / "AGENTS.md").read_text()
        self.assertIn("follow the skill's current routing", installed)
        self.assertNotIn("Start the narrowest already-qualified roles", installed)

    def test_known_predecessor_lifecycle_script_can_migrate_without_state(self):
        relative = (
            Path("skills")
            / "subagent-orchestrator"
            / "scripts"
            / "lifecycle_conformance.py"
        )
        desired = PACKAGE_ROOT / "payload" / relative
        target = self.codex_home / relative
        target.parent.mkdir(parents=True)
        target.write_text(desired.read_text() + "\n")

        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), desired.read_bytes())

    def test_preserves_unrelated_personal_configuration_and_extra_agent(self):
        self.codex_home.mkdir()
        original_agents_prefix = "# Personal rules\n\n## Project notes\n\nKeep this text.\n"
        (self.codex_home / "AGENTS.md").write_text(original_agents_prefix)
        original_config = (
            'model = "gpt-5.6-sol"\n'
            'model_reasoning_effort = "ultra"\n\n'
            '[projects]\nexample = "trusted"\n'
        )
        (self.codex_home / "config.toml").write_text(original_config)
        agents_dir = self.codex_home / "agents"
        agents_dir.mkdir()
        extra = agents_dir / "project_specialist.toml"
        extra.write_text('name = "project_specialist"\n')

        result = self.run_installer("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.codex_home / "AGENTS.md").read_text().startswith(original_agents_prefix))
        installed_config = (self.codex_home / "config.toml").read_text()
        self.assertIn('model_reasoning_effort = "ultra"', installed_config)
        self.assertIn('[projects]\nexample = "trusted"', installed_config)
        self.assertEqual(extra.read_text(), 'name = "project_specialist"\n')

    def test_conflicting_config_fails_before_any_write(self):
        self.codex_home.mkdir()
        config = "[agents]\nmax_concurrent_threads_per_session = 2\n"
        (self.codex_home / "config.toml").write_text(config)
        result = self.run_installer("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicting package-owned", result.stderr)
        self.assertEqual((self.codex_home / "config.toml").read_text(), config)
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_unknown_role_conflict_fails_before_any_write(self):
        role = self.codex_home / "agents" / "evidence_tester.toml"
        role.parent.mkdir(parents=True)
        role.write_text('name = "local_override"\n')
        result = self.run_installer("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target conflicts with package ownership", result.stderr)
        self.assertEqual(role.read_text(), 'name = "local_override"\n')
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_state_records_only_managed_projections_and_paths(self):
        result = self.run_installer("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = (
            self.codex_home
            / "skills"
            / "subagent-orchestrator"
            / ".managed-package-state.json"
        )
        state = json.loads(state_path.read_text())
        self.assertEqual(state["package_id"], "subagent-orchestrator")
        managed = state["managed_hashes"]
        self.assertIn("AGENTS.md#subagent-policy", managed)
        self.assertIn("config.toml#agents", managed)
        self.assertNotIn("AGENTS.md", managed)
        self.assertNotIn("config.toml", managed)

    def test_all_target_recheck_rejects_drift_before_any_write(self):
        plans, _ = INSTALL_MODULE.plan_install(self.codex_home, "en")
        self.codex_home.mkdir()
        drifted_config = "[agents]\nenabled = false\n"
        (self.codex_home / "config.toml").write_text(drifted_config)

        with self.assertRaisesRegex(
            INSTALL_MODULE.InstallError,
            "target drifted after preflight: config.toml",
        ):
            INSTALL_MODULE.apply_plans(plans, self.codex_home)

        self.assertEqual(
            (self.codex_home / "config.toml").read_text(),
            drifted_config,
        )
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertFalse((self.codex_home / "agents").exists())
        self.assertFalse((self.codex_home / "skills").exists())

    def test_unknown_valid_state_fails_closed_before_any_write(self):
        state_path = (
            self.codex_home
            / "skills"
            / "subagent-orchestrator"
            / ".managed-package-state.json"
        )
        state_path.parent.mkdir(parents=True)
        unknown_state = {
            "format_version": 1,
            "package_id": "unknown-package",
            "package_manifest_sha256": "0" * 64,
            "managed_hashes": {},
        }
        state_text = json.dumps(unknown_state, indent=2) + "\n"
        state_path.write_text(state_text)
        before = {
            str(path.relative_to(self.codex_home)): path.read_bytes()
            for path in self.codex_home.rglob("*")
            if path.is_file()
        }

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed state package identity mismatch", result.stderr)
        after = {
            str(path.relative_to(self.codex_home)): path.read_bytes()
            for path in self.codex_home.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertFalse((self.codex_home / "config.toml").exists())
        self.assertFalse((self.codex_home / "agents").exists())

    def test_state_with_unknown_owned_key_fails_closed(self):
        state_path = (
            self.codex_home
            / "skills"
            / "subagent-orchestrator"
            / ".managed-package-state.json"
        )
        state_path.parent.mkdir(parents=True)
        state = {
            "format_version": 1,
            "package_id": "subagent-orchestrator",
            "package_manifest_sha256": hashlib.sha256(
                (PACKAGE_ROOT / "manifest.json").read_bytes()
            ).hexdigest(),
            "managed_hashes": {"unexpected/owner": "0" * 64},
        }
        original = json.dumps(state, indent=2) + "\n"
        state_path.write_text(original)

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed state owned-key domain mismatch", result.stderr)
        self.assertEqual(state_path.read_text(), original)
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertFalse((self.codex_home / "config.toml").exists())
        self.assertFalse((self.codex_home / "agents").exists())

    def test_state_manifest_lineage_mismatch_fails_closed(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state_path = (
            self.codex_home
            / "skills"
            / "subagent-orchestrator"
            / ".managed-package-state.json"
        )
        state = json.loads(state_path.read_text())
        state["package_manifest_sha256"] = "f" * 64
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
        before = {
            str(path.relative_to(self.codex_home)): path.read_bytes()
            for path in self.codex_home.rglob("*")
            if path.is_file()
        }

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed state manifest lineage is not accepted", result.stderr)
        after = {
            str(path.relative_to(self.codex_home)): path.read_bytes()
            for path in self.codex_home.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_pre_standalone_manifest_lineage_is_accepted(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state_path = (
            self.codex_home
            / "skills"
            / "subagent-orchestrator"
            / ".managed-package-state.json"
        )
        state = json.loads(state_path.read_text())
        state["package_manifest_sha256"] = (
            "498be7e574c86c9ab6c56c1f4ab09ffbcc237ad3a44d9b09975ead935f392742"
        )
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

        result = self.run_installer("--check")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "WOULD_TOUCH skills/subagent-orchestrator/.managed-package-state.json",
            result.stdout,
        )
        self.assertIn("1 path(s) would change", result.stdout)

    def test_state_target_hash_mismatch_fails_closed(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        role_path = self.codex_home / "agents" / "boundary_mapper.toml"
        role_path.write_text(role_path.read_text() + "\n# concurrent edit\n")
        before = {
            str(path.relative_to(self.codex_home)): path.read_bytes()
            for path in self.codex_home.rglob("*")
            if path.is_file()
        }

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("managed state does not match current targets", result.stderr)
        after = {
            str(path.relative_to(self.codex_home)): path.read_bytes()
            for path in self.codex_home.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_late_drift_stops_later_replace_after_partial_install(self):
        plans, _ = INSTALL_MODULE.plan_install(self.codex_home, "en")
        original_atomic_write = INSTALL_MODULE.atomic_write

        def write_then_drift(plan, codex_home):
            original_atomic_write(plan, codex_home)
            if plan.relative == "AGENTS.md":
                codex_home.mkdir(parents=True, exist_ok=True)
                (codex_home / "config.toml").write_text(
                    "# concurrent late drift\n"
                )

        with mock.patch.object(
            INSTALL_MODULE,
            "atomic_write",
            side_effect=write_then_drift,
        ):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError,
                "target drifted after preflight: config.toml",
            ):
                INSTALL_MODULE.apply_plans(plans, self.codex_home)

        self.assertTrue((self.codex_home / "AGENTS.md").is_file())
        self.assertEqual(
            (self.codex_home / "config.toml").read_text(),
            "# concurrent late drift\n",
        )
        self.assertFalse((self.codex_home / "agents").exists())
        self.assertFalse((self.codex_home / "skills").exists())


if __name__ == "__main__":
    unittest.main()

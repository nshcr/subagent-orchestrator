from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
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
        self.original_manifest_path = INSTALL_MODULE.MANIFEST_PATH
        manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text())
        declared = {item["path"]: item for item in manifest["files"]}
        for relative, item in declared.items():
            content = (PACKAGE_ROOT / relative).read_bytes()
            item["sha256"] = hashlib.sha256(content).hexdigest()
            item["size"] = len(content)
        migration_content = (PACKAGE_ROOT / "install-migrations.json").read_bytes()
        declared.setdefault(
            "install-migrations.json",
            {
                "path": "install-migrations.json",
                "sha256": hashlib.sha256(migration_content).hexdigest(),
                "size": len(migration_content),
            },
        )
        manifest["files"] = sorted(declared.values(), key=lambda item: item["path"])
        self.test_manifest = Path(self.temporary.name) / "test-manifest.json"
        self.test_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        INSTALL_MODULE.MANIFEST_PATH = self.test_manifest

    def tearDown(self):
        INSTALL_MODULE.MANIFEST_PATH = self.original_manifest_path
        self.temporary.cleanup()

    def run_installer(
        self,
        action: str,
        agents_language: str = "en",
        extra_args: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        runner = """
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
spec = spec_from_file_location("installer_under_test", sys.argv.pop(1))
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.MANIFEST_PATH = Path(sys.argv.pop(1))
raise SystemExit(module.main())
"""
        command = [
                sys.executable,
                "-B",
                "-c",
                runner,
                str(INSTALLER),
                str(self.test_manifest),
                "--codex-home",
                str(self.codex_home),
                "--agents-language",
                agents_language,
                action,
                *extra_args,
            ]
        if action == "--apply" and "--plan-receipt" not in extra_args:
            check_command = command[:-len(extra_args) if extra_args else None]
            check_command[-1] = "--check"
            check_command.extend(("--format", "json"))
            checked = subprocess.run(
                check_command,
                cwd=PACKAGE_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            if checked.returncode != 0:
                return checked
            receipt_path = Path(self.temporary.name) / "plan-receipt.json"
            receipt_path.write_text(checked.stdout)
            command.extend(("--plan-receipt", str(receipt_path)))
        return subprocess.run(
            command,
            cwd=PACKAGE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def state_path(self) -> Path:
        return (
            self.codex_home
            / "skills"
            / "subagent-orchestrator"
            / ".managed-package-state.json"
        )

    def migration_catalog(self, relative: str, content: bytes) -> Path:
        path = Path(self.temporary.name) / "migration-catalog.json"
        path.write_text(
            json.dumps(
                {
                    "accepted_install_contracts": [],
                    "format_version": 1,
                    "package_id": "subagent-orchestrator",
                    "retired_paths": [
                        {
                            "accepted_sha256": [hashlib.sha256(content).hexdigest()],
                            "path": relative,
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return path

    def rewrite_state_as_v1(self, extra: dict[str, str] | None = None) -> None:
        state_path = self.state_path()
        state = json.loads(state_path.read_text())
        managed = dict(state["managed_hashes"])
        managed.update(extra or {})
        predecessor = {
            "format_version": 1,
            "managed_hashes": managed,
            "package_id": "subagent-orchestrator",
            "package_manifest_sha256": hashlib.sha256(
                self.test_manifest.read_bytes()
            ).hexdigest(),
        }
        state_path.write_text(json.dumps(predecessor, indent=2, sort_keys=True) + "\n")

    def test_check_is_read_only_and_reports_hashes(self):
        result = self.run_installer("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WOULD_TOUCH AGENTS.md ", result.stdout)
        self.assertFalse(self.codex_home.exists())

    def test_check_json_emits_strict_target_bound_plan_receipt(self):
        result = self.run_installer("--check", extra_args=("--format", "json"))

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = INSTALL_MODULE.validate_plan_receipt(json.loads(result.stdout))
        self.assertEqual(receipt["target"]["realpath"], str(self.codex_home.resolve()))
        self.assertEqual(receipt["source"]["source_revision"], None)
        self.assertEqual(
            receipt["source"]["source_revision_status"],
            "unavailable-archive-identity-used",
        )
        self.assertTrue(receipt["targets"])
        self.assertFalse(self.codex_home.exists())

    def test_source_identity_requires_clean_git_and_allows_archive_fallback(self):
        source_root = Path(self.temporary.name) / "git-source"
        source_root.mkdir()
        migration = source_root / "install-migrations.json"
        migration.write_text("{}\n")
        manifest = {
            "files": [
                {
                    "path": "install-migrations.json",
                    "sha256": hashlib.sha256(migration.read_bytes()).hexdigest(),
                    "size": len(migration.read_bytes()),
                }
            ]
        }
        source_manifest = source_root / "manifest.json"
        source_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        subprocess.run(["git", "init", "-q", str(source_root)], check=True)
        subprocess.run(["git", "-C", str(source_root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source_root),
                "-c",
                "user.name=Installer Test",
                "-c",
                "user.email=installer@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        contract_hash = "1" * 64
        with mock.patch.object(INSTALL_MODULE, "PACKAGE_ROOT", source_root), mock.patch.object(
            INSTALL_MODULE, "MANIFEST_PATH", source_manifest
        ), mock.patch.object(
            INSTALL_MODULE, "install_contract_sha256", return_value=contract_hash
        ):
            clean = INSTALL_MODULE.source_package_identity()
            expected_head = subprocess.run(
                ["git", "-C", str(source_root), "rev-parse", "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(clean["source_revision"], expected_head)
            self.assertEqual(clean["source_revision_status"], "verified-clean-git")

            dirty_untracked = source_root / "untracked.txt"
            dirty_untracked.write_text("dirty\n")
            with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "source is dirty"):
                INSTALL_MODULE.source_package_identity()

            # A test/release manifest outside the default package path has no
            # claim of Git provenance and therefore uses archive identity.
            dirty_untracked.unlink()
            alternate_manifest = source_root / "archive-manifest.json"
            alternate_manifest.write_text(source_manifest.read_text())
            with mock.patch.object(INSTALL_MODULE, "MANIFEST_PATH", alternate_manifest):
                archive = INSTALL_MODULE.source_package_identity()
            self.assertIsNone(archive["source_revision"])
            self.assertEqual(
                archive["source_revision_status"],
                "unavailable-archive-identity-used",
            )

    def test_receipts_and_managed_journals_reject_duplicate_json_keys(self):
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        plan_path = Path(self.temporary.name) / "duplicate-plan.json"
        plan_text = json.dumps(plan, sort_keys=True)
        plan_path.write_text(plan_text.replace("{", '{"format_version":1,', 1))
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "duplicate key"):
            INSTALL_MODULE.apply_install_with_receipt(
                self.codex_home, "en", plan_path
            )

        _, restore_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        restore_text = restore_path.read_text()
        duplicate_restore = Path(self.temporary.name) / "duplicate-restore.json"
        duplicate_restore.write_text(
            restore_text.replace("{", '{"receipt_digest":"' + "0" * 64 + '",', 1)
        )
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "duplicate key"):
            INSTALL_MODULE.restore_install(self.codex_home, duplicate_restore)

        for relative, label in (
            (INSTALL_MODULE.JOURNAL_RELATIVE, "install transaction"),
            (
                INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE,
                "receipt-bound apply transaction",
            ),
            (INSTALL_MODULE.RESTORE_JOURNAL_RELATIVE, "restore transaction"),
        ):
            path = self.codex_home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"format_version":1,"format_version":1}\n')
            with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "duplicate key"):
                if relative == INSTALL_MODULE.JOURNAL_RELATIVE:
                    INSTALL_MODULE.read_journal(self.codex_home)
                else:
                    INSTALL_MODULE.read_managed_json(
                        self.codex_home, relative, label
                    )
            path.unlink()

    def test_state_manifest_and_catalog_reject_duplicate_keys_before_mutation(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state_path = self.state_path()
        state_path.write_text(
            state_path.read_text().replace(
                '  "managed_hashes": {',
                '  "managed_hashes": {},\n  "managed_hashes": {',
                1,
            )
        )
        agents_before = (self.codex_home / "AGENTS.md").read_bytes()
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "duplicate key"):
            INSTALL_MODULE.plan_install(self.codex_home, "en")
        self.assertEqual((self.codex_home / "AGENTS.md").read_bytes(), agents_before)
        self.assertFalse((self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE).exists())

        clean_home = Path(self.temporary.name) / "duplicate-input-home"
        self.test_manifest.write_text(
            self.test_manifest.read_text().replace(
                "{", '{"files": [],', 1
            )
        )
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "duplicate key"):
            INSTALL_MODULE.plan_install(clean_home, "en")
        self.assertFalse(clean_home.exists())

        manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text())
        declared = {item["path"]: item for item in manifest["files"]}
        for relative, item in declared.items():
            content = (PACKAGE_ROOT / relative).read_bytes()
            item["sha256"] = hashlib.sha256(content).hexdigest()
            item["size"] = len(content)
        self.test_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        catalog = Path(self.temporary.name) / "duplicate-catalog.json"
        catalog.write_text(
            (PACKAGE_ROOT / "install-migrations.json").read_text().replace(
                "{", '{"retired_paths": [],', 1
            )
        )
        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "duplicate key"):
                INSTALL_MODULE.plan_install(clean_home, "en")
        self.assertFalse(clean_home.exists())

        installer_source = INSTALLER.read_text()
        self.assertEqual(installer_source.count("json.loads("), 1)

    def test_apply_cli_requires_a_plan_receipt(self):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(INSTALLER),
                "--codex-home",
                str(self.codex_home),
                "--agents-language",
                "en",
                "--apply",
            ],
            cwd=PACKAGE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--apply requires --plan-receipt", result.stderr)
        self.assertFalse(self.codex_home.exists())

    def test_doctor_is_read_only_for_an_uninstalled_home(self):
        result = self.run_installer("--doctor")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DOCTOR NOT_INSTALLED", result.stdout)
        self.assertFalse(self.codex_home.exists())
        self.assertFalse(INSTALL_MODULE.lock_path(self.codex_home).exists())

    def test_doctor_json_is_structured_and_read_only(self):
        result = self.run_installer("--doctor", extra_args=("--format", "json"))

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["format_version"], 1)
        self.assertEqual(report["package_id"], "subagent-orchestrator")
        self.assertEqual(report["status"], "NOT_INSTALLED")
        self.assertTrue(report["healthy"])
        self.assertFalse(report["locked"])
        self.assertEqual(report["targets"], [])
        self.assertEqual(report["quarantined"], [])
        self.assertEqual(report["retirement_receipts"], [])
        self.assertEqual(report["restore_receipts"], [])
        self.assertFalse(self.codex_home.exists())

    def test_receipt_bound_apply_and_restore_round_trip_modes_and_absence(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior_agents = b"# personal policy\n"
        agents.write_bytes(prior_agents)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")

        touched, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )

        self.assertTrue(touched)
        self.assertIsNotNone(receipt_path)
        restore = INSTALL_MODULE.read_restore_receipt(receipt_path)
        agents_target = next(
            target for target in restore["targets"] if target["relative"] == "AGENTS.md"
        )
        prior_backup = self.codex_home / agents_target["prior_backup_relative"]
        self.assertEqual(prior_backup.read_bytes(), prior_agents)
        self.assertEqual(prior_backup.stat().st_mode & 0o777, 0o600)
        self.assertFalse(INSTALL_MODULE.same_physical_file(agents, prior_backup))
        self.assertFalse(
            next(
                target
                for target in restore["targets"]
                if target["relative"] == "config.toml"
            )["prior_exists"]
        )

        restored = INSTALL_MODULE.restore_install(self.codex_home, restore)

        self.assertEqual(len(restored), len(restore["targets"]))
        self.assertEqual(agents.read_bytes(), prior_agents)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.codex_home / "config.toml").exists())
        candidate_backup = self.codex_home / INSTALL_MODULE.vault_relative(
            "candidate", restore["receipt_digest"], "AGENTS.md"
        )
        self.assertEqual(
            hashlib.sha256(candidate_backup.read_bytes()).hexdigest(),
            agents_target["candidate_sha256"],
        )
        self.assertEqual(
            candidate_backup.stat().st_mode & 0o777,
            agents_target["candidate_mode"],
        )
        self.assertFalse(INSTALL_MODULE.same_physical_file(agents, candidate_backup))
        report = INSTALL_MODULE.doctor_report(self.codex_home, "en")
        self.assertEqual(report["restore_receipts"][0]["status"], "RESTORED")

    def test_restore_snapshots_are_independent_and_never_replace_collisions(self):
        self.codex_home.mkdir()
        source = self.codex_home / "AGENTS.md"
        content = b"# prior policy\n"
        digest = hashlib.sha256(content).hexdigest()
        source.write_bytes(content)
        source.chmod(0o600)
        destination = self.codex_home / INSTALL_MODULE.vault_relative(
            "prior", "0" * 64, "AGENTS.md"
        )

        INSTALL_MODULE.preserve_snapshot(
            source, destination, self.codex_home, digest, 0o600
        )

        self.assertEqual(destination.read_bytes(), content)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertFalse(INSTALL_MODULE.same_physical_file(source, destination))
        source.chmod(0o644)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

        destination.write_text("tampered snapshot\n")
        with self.assertRaisesRegex(
            INSTALL_MODULE.InstallError, "restore vault artifact mismatch"
        ):
            INSTALL_MODULE.preserve_snapshot(
                source, destination, self.codex_home, digest, 0o644
            )

        collision = self.codex_home / INSTALL_MODULE.vault_relative(
            "prior", "1" * 64, "AGENTS.md"
        )
        original_link = INSTALL_MODULE.os.link

        def inject_collision(temporary, target):
            if Path(target) == collision:
                collision.write_bytes(b"concurrent owner bytes\n")
            return original_link(temporary, target)

        with mock.patch.object(INSTALL_MODULE.os, "link", side_effect=inject_collision):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "appeared concurrently"
            ):
                INSTALL_MODULE.preserve_snapshot(
                    source,
                    collision,
                    self.codex_home,
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                    0o644,
                )
        self.assertEqual(collision.read_bytes(), b"concurrent owner bytes\n")

    def test_mode_drift_after_backup_gate_fails_before_managed_mutation(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior = b"# personal policy\n"
        agents.write_bytes(prior)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        original_verify = INSTALL_MODULE.verify_restore_target_backups
        injected = False

        def verify_then_chmod(codex_home, targets):
            nonlocal injected
            original_verify(codex_home, targets)
            if not injected:
                injected = True
                agents.chmod(0o644)

        with mock.patch.object(
            INSTALL_MODULE,
            "verify_restore_target_backups",
            side_effect=verify_then_chmod,
        ):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "target drifted after preflight: AGENTS.md"
            ):
                INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )

        apply_journal = self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE
        install_journal = self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE
        self.assertEqual(agents.read_bytes(), prior)
        self.assertFalse((self.codex_home / "config.toml").exists())
        self.assertTrue(apply_journal.is_file())
        self.assertTrue(install_journal.is_file())
        apply_document = INSTALL_MODULE.validate_apply_receipt_journal(
            INSTALL_MODULE.read_managed_json(
                self.codex_home,
                INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE,
                "receipt-bound apply transaction",
            )
        )
        target = next(
            item
            for item in apply_document["restore_targets"]
            if item["relative"] == "AGENTS.md"
        )
        backup = self.codex_home / target["prior_backup_relative"]
        self.assertEqual(backup.read_bytes(), prior)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertFalse(INSTALL_MODULE.same_physical_file(agents, backup))

        with self.assertRaisesRegex(
            INSTALL_MODULE.InstallError, "conflicting targets"
        ):
            INSTALL_MODULE.apply_install_with_receipt(
                self.codex_home, "en", plan
            )
        self.assertEqual(agents.read_bytes(), prior)
        self.assertFalse((self.codex_home / "config.toml").exists())
        self.assertTrue(apply_journal.is_file())
        self.assertTrue(install_journal.is_file())

        agents.chmod(0o600)
        touched, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        self.assertTrue(touched)
        self.assertTrue(receipt_path.is_file())
        self.assertFalse(apply_journal.exists())
        self.assertFalse(install_journal.exists())

    def test_candidate_mismatch_retains_resumable_apply_evidence(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior = b"# original policy\n"
        agents.write_bytes(prior)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        original_apply = INSTALL_MODULE.apply_plans

        def apply_then_drift(plans, codex_home, on_touched=None):
            touched = original_apply(plans, codex_home, on_touched)
            agents.chmod(0o644)
            return touched

        with mock.patch.object(
            INSTALL_MODULE, "apply_plans", side_effect=apply_then_drift
        ):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "candidate postimage mismatch: AGENTS.md"
            ):
                INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )

        apply_journal = self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE
        install_journal = self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE
        self.assertTrue(apply_journal.is_file())
        self.assertTrue(install_journal.is_file())
        apply_document = INSTALL_MODULE.validate_apply_receipt_journal(
            INSTALL_MODULE.read_managed_json(
                self.codex_home,
                INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE,
                "receipt-bound apply transaction",
            )
        )
        target = next(
            item
            for item in apply_document["restore_targets"]
            if item["relative"] == "AGENTS.md"
        )
        backup = self.codex_home / target["prior_backup_relative"]
        self.assertEqual(backup.read_bytes(), prior)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertFalse(INSTALL_MODULE.same_physical_file(agents, backup))
        self.assertFalse((self.codex_home / INSTALL_MODULE.RESTORE_RECEIPTS_RELATIVE).exists())

        agents.chmod(target["candidate_mode"])
        touched, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        self.assertEqual(touched, [])
        self.assertTrue(receipt_path.is_file())
        self.assertFalse(apply_journal.exists())
        self.assertFalse(install_journal.exists())

    def test_receipt_durability_and_cleanup_interruptions_resume_forward(self):
        phases = ("before_receipt", "after_receipt", "after_journal")
        for phase in phases:
            with self.subTest(phase=phase):
                self.codex_home = Path(self.temporary.name) / phase
                plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
                original_write = INSTALL_MODULE.write_new_json
                original_finish = INSTALL_MODULE.finish_journal

                def interrupt_receipt(path, document, mode=0o600):
                    if Path(path).parent.name == INSTALL_MODULE.RESTORE_RECEIPTS_RELATIVE.name:
                        if phase == "before_receipt":
                            raise OSError("injected before receipt durability")
                        if phase == "after_receipt":
                            original_write(path, document, mode)
                            raise OSError("injected after receipt durability")
                    return original_write(path, document, mode)

                def interrupt_after_journal(codex_home, journal):
                    original_finish(codex_home, journal)
                    raise OSError("injected after journal cleanup")

                write_patch = mock.patch.object(
                    INSTALL_MODULE, "write_new_json", side_effect=interrupt_receipt
                )
                finish_patch = (
                    mock.patch.object(
                        INSTALL_MODULE,
                        "finish_journal",
                        side_effect=interrupt_after_journal,
                    )
                    if phase == "after_journal"
                    else mock.patch.object(
                        INSTALL_MODULE, "finish_journal", wraps=original_finish
                    )
                )
                expected = {
                    "before_receipt": "before receipt durability",
                    "after_receipt": "after receipt durability",
                    "after_journal": "after journal cleanup",
                }[phase]
                with write_patch, finish_patch:
                    with self.assertRaisesRegex(OSError, expected):
                        INSTALL_MODULE.apply_install_with_receipt(
                            self.codex_home, "en", plan
                        )

                apply_journal = (
                    self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE
                )
                install_journal = self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE
                self.assertTrue(apply_journal.is_file())
                self.assertEqual(install_journal.exists(), phase != "after_journal")

                touched, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )
                self.assertEqual(touched, [])
                self.assertTrue(receipt_path.is_file())
                self.assertFalse(apply_journal.exists())
                self.assertFalse(install_journal.exists())

    def test_apply_meta_only_prepared_state_recovers_and_restores_exactly(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior = b"# exact prior policy\n"
        agents.write_bytes(prior)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")

        with mock.patch.object(
            INSTALL_MODULE,
            "create_journal",
            side_effect=OSError("injected before install journal durability"),
        ):
            with self.assertRaisesRegex(OSError, "before install journal durability"):
                INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )

        apply_journal = self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE
        install_journal = self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE
        self.assertTrue(apply_journal.is_file())
        self.assertFalse(install_journal.exists())
        self.assertEqual(agents.read_bytes(), prior)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.codex_home / "config.toml").exists())

        touched, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )

        self.assertTrue(touched)
        self.assertTrue(receipt_path.is_file())
        self.assertFalse(apply_journal.exists())
        self.assertFalse(install_journal.exists())
        restore = INSTALL_MODULE.read_restore_receipt(receipt_path)
        INSTALL_MODULE.restore_install(self.codex_home, restore)
        self.assertEqual(agents.read_bytes(), prior)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.codex_home / "config.toml").exists())

    def test_apply_meta_only_mixed_state_fails_closed(self):
        self.codex_home = INSTALL_MODULE.validate_codex_home(self.codex_home)
        plans, _ = INSTALL_MODULE.plan_install(self.codex_home, "en")
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en", plans)
        agents_plan = next(item for item in plans if item.relative == "AGENTS.md")

        with mock.patch.object(
            INSTALL_MODULE,
            "create_journal",
            side_effect=OSError("injected before install journal durability"),
        ):
            with self.assertRaisesRegex(OSError, "before install journal durability"):
                INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )

        agents_plan.path.parent.mkdir(parents=True, exist_ok=True)
        agents_plan.path.write_bytes(agents_plan.content)
        agents_plan.path.chmod(INSTALL_MODULE.planned_mode(agents_plan))
        with self.assertRaisesRegex(
            INSTALL_MODULE.InstallError,
            "receipt-bound apply state is mixed or conflicting",
        ):
            INSTALL_MODULE.apply_install_with_receipt(
                self.codex_home, "en", plan
            )

        self.assertTrue(
            (self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE).is_file()
        )
        self.assertFalse(
            (self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE).exists()
        )
        self.assertFalse((self.codex_home / "config.toml").exists())
        self.assertFalse(
            (self.codex_home / INSTALL_MODULE.RESTORE_RECEIPTS_RELATIVE).exists()
        )

    def test_plan_receipt_rejects_target_source_and_schema_drift(self):
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        self.codex_home.mkdir()
        (self.codex_home / "AGENTS.md").write_text("concurrent target\n")
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "target or install plan drifted"):
            INSTALL_MODULE.apply_install_with_receipt(self.codex_home, "en", plan)

        self.codex_home = Path(self.temporary.name) / "second-home"
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "another target identity"):
            INSTALL_MODULE.apply_install_with_receipt(self.codex_home, "en", plan)

        self.codex_home = Path(plan["target"]["realpath"])
        manifest = json.loads(self.test_manifest.read_text())
        manifest["test_source_drift"] = True
        self.test_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        clean_home = Path(self.temporary.name) / "source-drift-home"
        source_plan = dict(plan)
        source_plan["target"] = INSTALL_MODULE.target_identity(clean_home)
        digest_input = dict(source_plan)
        digest_input.pop("plan_digest")
        source_plan["plan_digest"] = INSTALL_MODULE.canonical_json_hash(digest_input)
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "source package drifted"):
            INSTALL_MODULE.apply_install_with_receipt(clean_home, "en", source_plan)

        malformed = dict(plan)
        malformed["unexpected"] = True
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "unknown schema"):
            INSTALL_MODULE.validate_plan_receipt(malformed)
        tampered = json.loads(json.dumps(plan))
        tampered["targets"][0]["desired_mode"] = 0o600
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "digest mismatch"):
            INSTALL_MODULE.validate_plan_receipt(tampered)

    def test_restore_rejects_candidate_drift_cross_home_and_vault_tamper(self):
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        _, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        restore = INSTALL_MODULE.read_restore_receipt(receipt_path)
        (self.codex_home / "AGENTS.md").write_text("candidate drift\n")
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "candidate postimage drifted"):
            INSTALL_MODULE.restore_install(self.codex_home, restore)

        another = Path(self.temporary.name) / "another-home"
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "another target identity"):
            INSTALL_MODULE.restore_install(another, restore)

        # Restore the candidate bytes, then corrupt a prior vault artifact.
        agents_target = next(
            target for target in restore["targets"] if target["relative"] == "AGENTS.md"
        )
        (self.codex_home / "AGENTS.md").write_bytes(
            (INSTALL_MODULE.PAYLOAD_ROOT / "AGENTS.section.en.md").read_bytes()
        )
        # AGENTS.md contains a merged document, so use the receipt-bound hash from
        # the displaced candidate preserved by a fresh installation instead.
        self.codex_home = Path(self.temporary.name) / "vault-home"
        self.codex_home.mkdir()
        original = self.codex_home / "AGENTS.md"
        original.write_text("# original\n")
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        _, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        restore = INSTALL_MODULE.read_restore_receipt(receipt_path)
        target = next(item for item in restore["targets"] if item["relative"] == "AGENTS.md")
        (self.codex_home / target["prior_backup_relative"]).write_text("tampered vault\n")
        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "prior restore vault mismatch"):
            INSTALL_MODULE.restore_install(self.codex_home, restore)

    def test_restore_failure_is_resumable_and_keeps_candidate_receipts(self):
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        _, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        restore = INSTALL_MODULE.read_restore_receipt(receipt_path)
        original_restore = INSTALL_MODULE.atomic_restore_prior
        calls = 0

        def fail_second(codex_home, target, candidate_staging):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected restore failure")
            return original_restore(codex_home, target, candidate_staging)

        with mock.patch.object(
            INSTALL_MODULE, "atomic_restore_prior", side_effect=fail_second
        ):
            with self.assertRaisesRegex(OSError, "injected restore failure"):
                INSTALL_MODULE.restore_install(self.codex_home, restore)

        self.assertTrue(
            (self.codex_home / INSTALL_MODULE.RESTORE_JOURNAL_RELATIVE).is_file()
        )
        report = INSTALL_MODULE.doctor_report(self.codex_home, "en")
        self.assertEqual(report["status"], "RESTORE_PARTIAL")
        INSTALL_MODULE.restore_install(self.codex_home, restore)
        self.assertFalse(
            (self.codex_home / INSTALL_MODULE.RESTORE_JOURNAL_RELATIVE).exists()
        )
        self.assertTrue(receipt_path.is_file())

    def test_restore_namespace_swap_after_second_observation_is_preserved(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior = b"# prior personal policy\n"
        agents.write_bytes(prior)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        _, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        receipt = INSTALL_MODULE.read_restore_receipt(receipt_path)
        foreign = b"# concurrent foreign replacement\n"
        original_file_state = INSTALL_MODULE.file_state
        observations = 0

        def swap_after_second_observation(path, codex_home):
            nonlocal observations
            state = original_file_state(path, codex_home)
            if path.resolve(strict=False) == agents.resolve(strict=False):
                observations += 1
                if observations == 2:
                    replacement = agents.with_name(".concurrent-agents")
                    replacement.write_bytes(foreign)
                    replacement.chmod(0o640)
                    INSTALL_MODULE.os.replace(replacement, agents)
            return state

        with mock.patch.object(
            INSTALL_MODULE,
            "file_state",
            side_effect=swap_after_second_observation,
        ):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "changed while being claimed"
            ):
                INSTALL_MODULE.restore_install(self.codex_home, receipt)

        self.assertEqual(agents.read_bytes(), foreign)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o640)
        restore_journal = self.codex_home / INSTALL_MODULE.RESTORE_JOURNAL_RELATIVE
        self.assertTrue(restore_journal.is_file())
        journal = INSTALL_MODULE.validate_restore_journal(
            INSTALL_MODULE.read_managed_json(
                self.codex_home,
                INSTALL_MODULE.RESTORE_JOURNAL_RELATIVE,
                "restore transaction",
            )
        )
        candidate_backup = journal["candidate_backups"]["AGENTS.md"]
        self.assertTrue((self.codex_home / candidate_backup).is_file())
        with self.assertRaisesRegex(
            INSTALL_MODULE.InstallError, "restore target drifted"
        ):
            INSTALL_MODULE.restore_install(self.codex_home, receipt)
        self.assertEqual(agents.read_bytes(), foreign)

    def test_restore_uses_the_same_target_lock(self):
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        _, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        restore = INSTALL_MODULE.read_restore_receipt(receipt_path)
        lock = INSTALL_MODULE.lock_path(self.codex_home)
        lock.write_text("held\n")

        with self.assertRaisesRegex(INSTALL_MODULE.InstallError, "target lock"):
            INSTALL_MODULE.restore_install(self.codex_home, restore)

        self.assertEqual(lock.read_text(), "held\n")
        self.assertTrue((self.codex_home / "AGENTS.md").is_file())

    def test_check_uses_target_lock_and_symlink_home_is_rejected(self):
        lock = INSTALL_MODULE.lock_path(self.codex_home)
        lock.write_text("held\n")
        result = self.run_installer("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target lock", result.stderr)
        lock.unlink()

        real = Path(self.temporary.name) / "real-home"
        real.mkdir()
        linked = Path(self.temporary.name) / "linked-home"
        linked.symlink_to(real, target_is_directory=True)
        self.codex_home = linked
        result = self.run_installer("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--codex-home is a symlink", result.stderr)

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
        chinese = self.run_installer("--apply", "zh")
        self.assertEqual(chinese.returncode, 0, chinese.stderr)
        agents_path = self.codex_home / "AGENTS.md"
        self.assertIn("## 子代理与并行", agents_path.read_text())
        self.assertNotIn("## Subagents and parallelism", agents_path.read_text())

        switched = self.run_installer("--apply")
        self.assertEqual(switched.returncode, 0, switched.stderr)
        self.assertIn("## Subagents and parallelism", agents_path.read_text())
        self.assertNotIn("## 子代理与并行", agents_path.read_text())

    def test_current_two_bullet_policies_can_migrate_without_state(self):
        predecessors = {
            "en": """## Subagents and parallelism

- Default to a single agent. Use `$subagent-orchestrator` only when the user explicitly requests delegation or parallel work, or when one bounded child can replace material primary work or provide a required independent gate; complexity, file count, decomposability, or idle capacity alone do not qualify.
- Once delegated, follow the skill's current routing, ownership, handoff, waiting, and gate rules; high-risk final states require a fresh, independent, read-only review. The primary always retains authorization, scope, conflict handling, integration, and final acceptance; children cannot expand authority or delegate recursively, and every required child must reach a terminal state before the primary ends.
""",
            "zh": """## 子代理与并行

- 默认单代理。仅当用户明确要求委派/并行，或一个边界清晰的子任务能替代可观的主代理工作或提供必需独立门禁时，使用 `$subagent-orchestrator`；复杂度、文件数、可拆分性或空闲并发本身不构成委派理由。
- 委派后遵循该 skill 当前的路由、所有权、交接、等待和门禁规则；高风险最终状态必须接受 fresh、独立、只读审阅。主代理始终保留授权、范围、冲突处理、整合和最终验收；子代理不得扩权或递归委派，所有必需子任务在主代理结束前必须到达终态。
""",
        }
        for language, predecessor in predecessors.items():
            with self.subTest(language=language):
                with tempfile.TemporaryDirectory() as temporary:
                    original_home = self.codex_home
                    self.codex_home = Path(temporary) / "codex-home"
                    try:
                        self.codex_home.mkdir()
                        (self.codex_home / "AGENTS.md").write_text(predecessor)
                        result = self.run_installer("--apply", language)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        installed = (self.codex_home / "AGENTS.md").read_text()
                        self.assertIn("bounded peer" if language == "en" else "受限协作代理", installed)
                    finally:
                        self.codex_home = original_home

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
        self.assertEqual(state["format_version"], 2)
        self.assertIn("install_contract_sha256", state)
        self.assertNotIn("package_manifest_sha256", state)
        managed = state["managed_hashes"]
        self.assertIn("AGENTS.md#subagent-policy", managed)
        self.assertIn("config.toml#agents", managed)
        self.assertNotIn("AGENTS.md", managed)
        self.assertNotIn("config.toml", managed)

    def test_v2_lineage_ignores_non_install_manifest_metadata(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        manifest = json.loads(self.test_manifest.read_text())
        manifest["release_note_for_test"] = "non-install metadata changed"
        self.test_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )

        result = self.run_installer("--check")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 path(s) would change", result.stdout)

    def test_v2_install_contract_lineage_mismatch_fails_closed(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state = json.loads(self.state_path().read_text())
        state["install_contract_sha256"] = "f" * 64
        self.state_path().write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n"
        )

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("install-contract lineage is not accepted", result.stderr)

    def test_accepted_contract_cannot_authenticate_a_forged_managed_map(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        role = self.codex_home / "agents" / "boundary_mapper.toml"
        foreign = b'name = "foreign-boundary-mapper"\n'
        role.write_bytes(foreign)
        state = json.loads(self.state_path().read_text())
        state["install_contract_sha256"] = (
            "31c117011aff92a07ef6c96680efa239e82844748987d1e58a95ce95fa394483"
        )
        state["managed_hashes"]["agents/boundary_mapper.toml"] = hashlib.sha256(
            foreign
        ).hexdigest()
        self.state_path().write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n"
        )

        checked = self.run_installer("--check")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("managed state document identity is not accepted", checked.stderr)
        with self.assertRaisesRegex(
            INSTALL_MODULE.InstallError,
            "managed state document identity is not accepted",
        ):
            INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertEqual(role.read_bytes(), foreign)
        self.assertFalse(
            (self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE).exists()
        )
        self.assertFalse(
            (self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE).exists()
        )

    def test_direct_v2_install_contract_lineage_is_accepted(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state = json.loads(self.state_path().read_text())
        state["install_contract_sha256"] = (
            "91f9f7d927aa8776e83f4f0f1c4e813d3af2fdc42090782e998e06befd62d1fe"
        )
        self.state_path().write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n"
        )

        healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
        self.assertTrue(healthy)
        self.assertEqual(diagnosis[0], "DOCTOR UPDATE_AVAILABLE 1")

        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        upgraded = json.loads(self.state_path().read_text())
        self.assertNotEqual(
            upgraded["install_contract_sha256"],
            "91f9f7d927aa8776e83f4f0f1c4e813d3af2fdc42090782e998e06befd62d1fe",
        )

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
                self.test_manifest.read_bytes()
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
        state = {
            "format_version": 1,
            "package_id": "subagent-orchestrator",
            "package_manifest_sha256": "f" * 64,
            "managed_hashes": state["managed_hashes"],
        }
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
        state = {
            "format_version": 1,
            "package_id": "subagent-orchestrator",
            "package_manifest_sha256": (
                "498be7e574c86c9ab6c56c1f4ab09ffbcc237ad3a44d9b09975ead935f392742"
            ),
            "managed_hashes": state["managed_hashes"],
        }
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

        result = self.run_installer("--check")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "WOULD_TOUCH skills/subagent-orchestrator/.managed-package-state.json",
            result.stdout,
        )
        self.assertIn("1 path(s) would change", result.stdout)

    def test_immediate_v1_manifest_lineage_is_accepted_and_upgraded(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state = json.loads(self.state_path().read_text())
        predecessor = {
            "format_version": 1,
            "managed_hashes": state["managed_hashes"],
            "package_id": "subagent-orchestrator",
            "package_manifest_sha256": (
                "20bef171c9a9e6390c9fdbdde90094497c76e8291090f736fe3ea206935bdbe2"
            ),
        }
        self.state_path().write_text(
            json.dumps(predecessor, indent=2, sort_keys=True) + "\n"
        )

        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        upgraded = json.loads(self.state_path().read_text())
        self.assertEqual(upgraded["format_version"], 2)
        self.assertIn("install_contract_sha256", upgraded)

    def test_direct_v1_predecessor_lineage_is_accepted_and_upgraded(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state = json.loads(self.state_path().read_text())
        predecessor = {
            "format_version": 1,
            "managed_hashes": state["managed_hashes"],
            "package_id": "subagent-orchestrator",
            "package_manifest_sha256": (
                "965615dbeae99d751a6cde94544d93b36405ed79d85d4f611bc7336209b8379c"
            ),
        }
        self.state_path().write_text(
            json.dumps(predecessor, indent=2, sort_keys=True) + "\n"
        )

        result = self.run_installer("--apply")

        self.assertEqual(result.returncode, 0, result.stderr)
        upgraded = json.loads(self.state_path().read_text())
        self.assertEqual(upgraded["format_version"], 2)
        self.assertIn("install_contract_sha256", upgraded)

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

    def test_governed_retired_path_is_quarantined_and_removed_from_v2_state(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        retired = self.codex_home / relative
        retired.write_bytes(content)
        self.rewrite_state_as_v1(
            {relative: hashlib.sha256(content).hexdigest()}
        )
        catalog = self.migration_catalog(relative, content)

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            touched = INSTALL_MODULE.apply_install(self.codex_home, "en")
            healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")

        self.assertIn((relative, "<absent>"), touched)
        self.assertFalse(retired.exists())
        content_hash = hashlib.sha256(content).hexdigest()
        quarantined = self.codex_home / INSTALL_MODULE.quarantine_relative(
            relative, content_hash
        )
        self.assertEqual(quarantined.read_bytes(), content)
        self.assertTrue(healthy)
        self.assertTrue(
            any(line.startswith(f"QUARANTINED {relative} ") for line in diagnosis)
        )
        state = json.loads(self.state_path().read_text())
        self.assertEqual(state["format_version"], 2)
        self.assertNotIn(relative, state["managed_hashes"])

    def test_unknown_extra_owned_path_is_not_treated_as_retirement(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/unknown_extra.toml"
        content = b'name = "unknown_extra"\n'
        target = self.codex_home / relative
        target.write_bytes(content)
        self.rewrite_state_as_v1(
            {relative: hashlib.sha256(content).hexdigest()}
        )

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("owned-key domain mismatch", result.stderr)
        self.assertEqual(target.read_bytes(), content)

    def test_user_modified_retired_path_is_not_quarantined(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        predecessor = b'name = "retired_specialist"\n'
        modified = predecessor + b"# user edit\n"
        retired = self.codex_home / relative
        retired.write_bytes(modified)
        self.rewrite_state_as_v1(
            {relative: hashlib.sha256(predecessor).hexdigest()}
        )
        catalog = self.migration_catalog(relative, predecessor)

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError,
                "managed state does not match current targets",
            ):
                INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertEqual(retired.read_bytes(), modified)

    def test_retired_path_quarantine_collision_preserves_both_files(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        content_hash = hashlib.sha256(content).hexdigest()
        retired = self.codex_home / relative
        retired.write_bytes(content)
        quarantined = self.codex_home / INSTALL_MODULE.quarantine_relative(
            relative, content_hash
        )
        quarantined.parent.mkdir(parents=True)
        quarantined.write_bytes(content)
        self.rewrite_state_as_v1({relative: content_hash})
        catalog = self.migration_catalog(relative, content)

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError,
                "quarantine destination already exists",
            ):
                INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertEqual(retired.read_bytes(), content)
        self.assertEqual(quarantined.read_bytes(), content)

    def test_retired_path_quarantine_race_never_replaces_collision(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        collision = b"concurrent owner bytes\n"
        content_hash = hashlib.sha256(content).hexdigest()
        retired = self.codex_home / relative
        retired.write_bytes(content)
        quarantined = self.codex_home / INSTALL_MODULE.quarantine_relative(
            relative, content_hash
        )
        self.rewrite_state_as_v1({relative: content_hash})
        catalog = self.migration_catalog(relative, content)
        original_link = INSTALL_MODULE.os.link

        def inject_collision(source, destination, *args, **kwargs):
            if Path(destination).resolve(strict=False) == quarantined.resolve(
                strict=False
            ):
                quarantined.write_bytes(collision)
            return original_link(source, destination, *args, **kwargs)

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with mock.patch.object(
                INSTALL_MODULE.os, "link", side_effect=inject_collision
            ):
                with self.assertRaisesRegex(
                    INSTALL_MODULE.InstallError,
                    "quarantine destination appeared",
                ):
                    INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertEqual(retired.read_bytes(), content)
        self.assertEqual(quarantined.read_bytes(), collision)

    def test_dual_link_quarantine_is_forward_recoverable(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        content_hash = hashlib.sha256(content).hexdigest()
        retired = self.codex_home / relative
        retired.write_bytes(content)
        quarantined = self.codex_home / INSTALL_MODULE.quarantine_relative(
            relative, content_hash
        )
        self.rewrite_state_as_v1({relative: content_hash})
        catalog = self.migration_catalog(relative, content)
        original_rename = INSTALL_MODULE.rename_noreplace
        injected = False

        def interrupt_after_link(source, destination):
            nonlocal injected
            if (
                source.resolve(strict=False) == retired.resolve(strict=False)
                and not injected
            ):
                injected = True
                raise OSError("injected pre-staging interruption")
            return original_rename(source, destination)

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with mock.patch.object(
                INSTALL_MODULE,
                "rename_noreplace",
                side_effect=interrupt_after_link,
            ):
                with self.assertRaisesRegex(OSError, "injected pre-staging interruption"):
                    INSTALL_MODULE.apply_install(self.codex_home, "en")

            self.assertTrue(retired.exists())
            self.assertTrue(quarantined.exists())
            self.assertTrue(INSTALL_MODULE.same_physical_file(retired, quarantined))
            healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
            self.assertFalse(healthy)
            self.assertIn("TARGET agents/retired_specialist.toml LINKED", diagnosis)

            touched = INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertIn((relative, "<absent>"), touched)
        self.assertFalse(retired.exists())
        self.assertEqual(quarantined.read_bytes(), content)
        self.assertFalse((self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE).exists())

    def test_staged_quarantine_is_forward_recoverable(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        content_hash = hashlib.sha256(content).hexdigest()
        retired = self.codex_home / relative
        retired.write_bytes(content)
        quarantined = self.codex_home / INSTALL_MODULE.quarantine_relative(
            relative, content_hash
        )
        staged = self.codex_home / INSTALL_MODULE.staging_relative(
            relative, content_hash
        )
        self.rewrite_state_as_v1({relative: content_hash})
        catalog = self.migration_catalog(relative, content)
        original_rename = INSTALL_MODULE.rename_noreplace
        injected = False

        def interrupt_after_staging(source, destination):
            nonlocal injected
            result = original_rename(source, destination)
            if (
                source.resolve(strict=False) == retired.resolve(strict=False)
                and not injected
            ):
                injected = True
                raise OSError("injected post-staging interruption")
            return result

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with mock.patch.object(
                INSTALL_MODULE,
                "rename_noreplace",
                side_effect=interrupt_after_staging,
            ):
                with self.assertRaisesRegex(
                    OSError, "injected post-staging interruption"
                ):
                    INSTALL_MODULE.apply_install(self.codex_home, "en")

            self.assertFalse(retired.exists())
            self.assertTrue(quarantined.exists())
            self.assertTrue(staged.exists())
            self.assertTrue(INSTALL_MODULE.same_physical_file(staged, quarantined))
            healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
            self.assertFalse(healthy)
            self.assertIn("TARGET agents/retired_specialist.toml STAGED", diagnosis)

            touched = INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertNotIn((relative, "<absent>"), touched)
        self.assertFalse(retired.exists())
        self.assertTrue(staged.exists())
        self.assertTrue(INSTALL_MODULE.same_physical_file(staged, quarantined))
        self.assertEqual(quarantined.read_bytes(), content)
        self.assertFalse((self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE).exists())
        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
        self.assertTrue(healthy)
        self.assertTrue(
            any(line.startswith(f"RETAINED_STAGING {relative} ") for line in diagnosis)
        )

    def test_source_replacement_at_staging_boundary_is_preserved(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        concurrent = b"concurrent user bytes\n"
        content_hash = hashlib.sha256(content).hexdigest()
        retired = self.codex_home / relative
        retired.write_bytes(content)
        quarantined = self.codex_home / INSTALL_MODULE.quarantine_relative(
            relative, content_hash
        )
        self.rewrite_state_as_v1({relative: content_hash})
        catalog = self.migration_catalog(relative, content)
        original_rename = INSTALL_MODULE.rename_noreplace
        injected = False

        def replace_source_before_staging(source, destination):
            nonlocal injected
            if (
                source.resolve(strict=False) == retired.resolve(strict=False)
                and not injected
            ):
                injected = True
                replacement = retired.with_name(".concurrent-retired-specialist")
                replacement.write_bytes(concurrent)
                INSTALL_MODULE.os.replace(replacement, source)
            return original_rename(source, destination)

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            with mock.patch.object(
                INSTALL_MODULE,
                "rename_noreplace",
                side_effect=replace_source_before_staging,
            ):
                with self.assertRaisesRegex(
                    INSTALL_MODULE.InstallError,
                    "source changed during staging",
                ):
                    INSTALL_MODULE.apply_install(self.codex_home, "en")

            self.assertEqual(retired.read_bytes(), concurrent)
            self.assertEqual(quarantined.read_bytes(), content)
            healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
            self.assertFalse(healthy)
            self.assertIn("TARGET agents/retired_specialist.toml CONFLICT", diagnosis)
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "conflicting targets"
            ):
                INSTALL_MODULE.apply_install(self.codex_home, "en")

        self.assertEqual(retired.read_bytes(), concurrent)
        self.assertEqual(quarantined.read_bytes(), content)

    def test_retained_staging_receipt_is_never_cleaned_by_path(self):
        installed = self.run_installer("--apply")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        relative = "agents/retired_specialist.toml"
        content = b'name = "retired_specialist"\n'
        unrelated = b"unrelated replacement bytes\n"
        content_hash = hashlib.sha256(content).hexdigest()
        retired = self.codex_home / relative
        retired.write_bytes(content)
        self.rewrite_state_as_v1({relative: content_hash})
        catalog = self.migration_catalog(relative, content)
        staged = self.codex_home / INSTALL_MODULE.staging_relative(
            relative, content_hash
        )

        with mock.patch.object(INSTALL_MODULE, "MIGRATION_CATALOG_PATH", catalog):
            INSTALL_MODULE.apply_install(self.codex_home, "en")
            replacement = staged.with_name(".concurrent-retirement-receipt")
            replacement.write_bytes(unrelated)
            INSTALL_MODULE.os.replace(replacement, staged)

            self.assertEqual(INSTALL_MODULE.apply_install(self.codex_home, "en"), [])
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "retirement receipt hash mismatch"
            ):
                INSTALL_MODULE.doctor(self.codex_home, "en")

        self.assertEqual(staged.read_bytes(), unrelated)

    def test_partial_transaction_receipt_doctor_and_idempotent_recovery(self):
        receipt = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        receipt_path = Path(self.temporary.name) / "partial-plan-receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        original_atomic_write = INSTALL_MODULE.atomic_write
        calls = 0

        def fail_on_second_write(plan, codex_home):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected write failure")
            original_atomic_write(plan, codex_home)

        with mock.patch.object(
            INSTALL_MODULE,
            "atomic_write",
            side_effect=fail_on_second_write,
        ), mock.patch.object(
            sys,
            "argv",
            [
                str(INSTALLER),
                "--codex-home",
                str(self.codex_home),
                "--agents-language",
                "en",
                "--apply",
                "--plan-receipt",
                str(receipt_path),
            ],
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = INSTALL_MODULE.main()

        self.assertEqual(result, 1)
        self.assertIn("TOUCHED AGENTS.md ", stdout.getvalue())
        self.assertIn("injected write failure", stderr.getvalue())
        journal_path = self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE
        self.assertTrue(journal_path.is_file())
        healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
        self.assertFalse(healthy)
        self.assertIn("DOCTOR PARTIAL_RECOVERABLE", diagnosis)
        self.assertIn("TARGET AGENTS.md DESIRED", diagnosis)

        recovered, restore_receipt = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", receipt
        )
        self.assertTrue(recovered)
        self.assertIsNotNone(restore_receipt)
        self.assertFalse(journal_path.exists())
        healthy, diagnosis = INSTALL_MODULE.doctor(self.codex_home, "en")
        self.assertTrue(healthy)
        self.assertEqual(diagnosis[0], "DOCTOR HEALTHY")
        self.assertTrue(any(line.startswith("RESTORE_RECEIPT ") for line in diagnosis))
        current_receipt = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        self.assertEqual(
            INSTALL_MODULE.apply_install_with_receipt(
                self.codex_home, "en", current_receipt
            ),
            ([], None),
        )

    def test_concurrent_apply_lock_is_refused_without_target_writes(self):
        path = INSTALL_MODULE.lock_path(self.codex_home)
        path.write_text("held by test\n")

        result = self.run_installer("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another installer holds apply lock", result.stderr)
        self.assertFalse(self.codex_home.exists())
        self.assertEqual(path.read_text(), "held by test\n")

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

    def test_write_namespace_collision_preserves_foreign_and_claimed_prior(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior = b"# original personal policy\n"
        foreign = b"# concurrent replacement\n"
        agents.write_bytes(prior)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        original_rename = INSTALL_MODULE.rename_noreplace
        injected = False

        def collide_before_candidate(source, destination):
            nonlocal injected
            if (
                destination.resolve(strict=False) == agents.resolve(strict=False)
                and not injected
            ):
                injected = True
                agents.write_bytes(foreign)
                agents.chmod(0o640)
            return original_rename(source, destination)

        with mock.patch.object(
            INSTALL_MODULE,
            "rename_noreplace",
            side_effect=collide_before_candidate,
        ):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "staging destination already exists"
            ):
                INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )

        self.assertEqual(agents.read_bytes(), foreign)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o640)
        install_journal = self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE
        apply_journal = self.codex_home / INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE
        self.assertTrue(install_journal.is_file())
        self.assertTrue(apply_journal.is_file())
        journal = INSTALL_MODULE.read_journal(self.codex_home)
        target = next(
            item for item in journal["targets"] if item["relative"] == "AGENTS.md"
        )
        recovery = self.codex_home / target["write_recovery_relative"]
        self.assertEqual(recovery.read_bytes(), prior)
        self.assertEqual(recovery.stat().st_mode & 0o777, 0o600)

        agents.unlink()
        touched, receipt_path = INSTALL_MODULE.apply_install_with_receipt(
            self.codex_home, "en", plan
        )
        self.assertTrue(touched)
        self.assertTrue(receipt_path.is_file())
        self.assertFalse(install_journal.exists())
        self.assertFalse(apply_journal.exists())
        INSTALL_MODULE.restore_install(self.codex_home, receipt_path)
        self.assertEqual(agents.read_bytes(), prior)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o600)

    def test_write_source_swap_after_precondition_is_returned_without_overwrite(self):
        self.codex_home.mkdir()
        agents = self.codex_home / "AGENTS.md"
        prior = b"# original before namespace swap\n"
        foreign = b"# swapped after precondition\n"
        agents.write_bytes(prior)
        agents.chmod(0o600)
        plan = INSTALL_MODULE.plan_receipt_document(self.codex_home, "en")
        original_rename = INSTALL_MODULE.rename_noreplace
        injected = False

        def swap_source_before_claim(source, destination):
            nonlocal injected
            if (
                source.resolve(strict=False) == agents.resolve(strict=False)
                and INSTALL_MODULE.WRITE_RECOVERY_RELATIVE
                in destination.relative_to(self.codex_home.resolve()).parents
                and not injected
            ):
                injected = True
                replacement = agents.with_name(".swapped-agents")
                replacement.write_bytes(foreign)
                replacement.chmod(0o640)
                INSTALL_MODULE.os.replace(replacement, agents)
            return original_rename(source, destination)

        with mock.patch.object(
            INSTALL_MODULE,
            "rename_noreplace",
            side_effect=swap_source_before_claim,
        ):
            with self.assertRaisesRegex(
                INSTALL_MODULE.InstallError, "changed while being claimed"
            ):
                INSTALL_MODULE.apply_install_with_receipt(
                    self.codex_home, "en", plan
                )

        self.assertEqual(agents.read_bytes(), foreign)
        self.assertEqual(agents.stat().st_mode & 0o777, 0o640)
        self.assertTrue((self.codex_home / INSTALL_MODULE.JOURNAL_RELATIVE).is_file())
        apply_document = INSTALL_MODULE.validate_apply_receipt_journal(
            INSTALL_MODULE.read_managed_json(
                self.codex_home,
                INSTALL_MODULE.APPLY_RECEIPT_JOURNAL_RELATIVE,
                "receipt-bound apply transaction",
            )
        )
        target = next(
            item
            for item in apply_document["restore_targets"]
            if item["relative"] == "AGENTS.md"
        )
        prior_backup = self.codex_home / target["prior_backup_relative"]
        self.assertEqual(prior_backup.read_bytes(), prior)
        self.assertEqual(prior_backup.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()

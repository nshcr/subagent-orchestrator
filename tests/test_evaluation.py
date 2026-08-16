import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from evaluation import EvaluationError, build_report, validate_campaign  # noqa: E402


DIGEST = "a" * 64


def billed_thread(thread_id, kind, role, parent, credits):
    tokens = {
        "input_tokens": 100 if kind == "primary" else 0,
        "cached_input_tokens": 20 if kind == "primary" else 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 30 if kind == "primary" else 0,
        "reasoning_output_tokens": 5 if kind == "primary" else 0,
        "total_tokens": 130 if kind == "primary" else 0,
    }
    return {
        "thread_id": thread_id,
        "kind": kind,
        "attempt": 1,
        "status": "completed",
        "role": role,
        "parent_thread_id": parent,
        "terminal": True,
        "cost_complete": True,
        "model": "test-primary" if kind == "primary" else "test-child",
        "effort": "medium" if kind == "primary" else "high",
        "service_tier": "default",
        "tokens": tokens,
        "credits": {
            "uncached_input": credits,
            "cached_input": "0",
            "output": "0",
            "total": credits,
        },
    }


def arm_evidence(arm, credits):
    primary_id = f"{arm}-primary"
    child_id = f"{arm}-child"
    child_role = "explorer" if arm == "baseline" else "evidence_tester"
    return {
        "threads": [
            billed_thread(primary_id, "primary", "primary", None, credits),
            billed_thread(child_id, "child", child_role, primary_id, "0"),
        ],
        "expected_thread_ids": [primary_id, child_id],
        "expected_receiver_ids": [child_id],
        "process_exit_code": 0,
        "completion_status": "completed",
        "execution_index": 0,
        "wall_time_ms": 250,
        "child_count": 1,
        "retries": 0,
        "quality_checks": [
            {
                "id": "grounded-result",
                "passed": True,
                "critical": True,
                "score": 10,
                "max_score": 10,
            }
        ],
        "scope_violations": [],
        "routing_violations": [],
        "routing_decision": "bounded specialist",
        "grader_sha256": DIGEST,
        "contamination_audit": {"passed": True, "notes": "clean"},
    }


def instance(identifier, family, *, holdout=False):
    arm_order = (
        ["custom", "baseline"]
        if identifier == "development-b"
        else ["baseline", "custom"]
    )
    return {
        "instance_id": identifier,
        "task_class": "test-triage",
        "fixture_family": family,
        "scenario": f"scenario {identifier}",
        "expected_roles": ["evidence_tester"],
        "holdout": holdout,
        "arm_order": arm_order,
        "runs": {
            "baseline": arm_evidence("baseline", "10"),
            "custom": arm_evidence("custom", "9"),
        },
    }


def order_for(instances):
    return [
        {"instance_id": item["instance_id"], "arm": arm}
        for item in instances
        for arm in item["arm_order"]
    ]


def freeze_order(instances):
    execution_order = order_for(instances)
    for index, entry in enumerate(execution_order):
        selected = next(
            item for item in instances if item["instance_id"] == entry["instance_id"]
        )
        selected["runs"][entry["arm"]]["execution_index"] = index
    return execution_order


def campaign():
    instances = [
        instance("development-b", "family-b"),
        instance("development-a", "family-a"),
    ]
    return {
        "schema_version": 1,
        "campaign_id": "campaign-1",
        "configuration_hashes": {
            "role_instructions": DIGEST,
            "routing_policy": DIGEST,
            "task_fixtures": DIGEST,
            "graders": DIGEST,
            "pricing": DIGEST,
        },
        "allowed_baseline_roles": ["explorer"],
        "class_policies": {
            "test-triage": {
                "decision_mode": "elective",
                "custom_role": "evidence_tester",
            }
        },
        "execution_order": freeze_order(instances),
        "instances": instances,
    }


def holdout():
    instances = [instance("sealed-c", "family-c", holdout=True)]
    return {
        "schema_version": 1,
        "campaign_id": "campaign-1",
        "allowed_baseline_roles": ["explorer"],
        "seal": {
            "seal_id": "external-seal-1",
            "receipt_sha256": DIGEST,
            "runner_sha256": DIGEST,
            "harness_sha256": DIGEST,
            "grader_sha256": DIGEST,
            "expected_answers_sha256": DIGEST,
            "fixtures_sha256": DIGEST,
            "prompts_sha256": DIGEST,
            "live_configuration_sha256": DIGEST,
            "agent_visibility_boundary_enforced": True,
            "runner_unlinked_before_agents": True,
        },
        "completion": {
            "receipt_sha256": DIGEST,
            "results_sha256": DIGEST,
            "archive_sha256": DIGEST,
            "all_tested_threads_terminal_before_archive": True,
            "all_records_valid": True,
            "all_contamination_audits_clean": True,
        },
        "execution_order": freeze_order(instances),
        "instances": instances,
    }


def set_run_credits(run, value):
    primary = next(item for item in run["threads"] if item["kind"] == "primary")
    primary["credits"]["uncached_input"] = value
    primary["credits"]["total"] = value


class EvaluationCampaignTest(unittest.TestCase):
    def test_paired_report_is_deterministic_and_exact(self):
        first = build_report(campaign(), holdout())
        reordered = campaign()
        reordered["instances"].reverse()
        second = build_report(reordered, holdout())
        self.assertEqual(first, second)

        task_class = first["task_classes"][0]
        self.assertEqual(task_class["recommendation"], "custom")
        self.assertEqual(task_class["arms"]["baseline"]["median_total_credits"], "10")
        self.assertEqual(task_class["arms"]["custom"]["median_total_credits"], "9")
        self.assertEqual(task_class["arms"]["custom"]["total_tokens"], 390)
        run = first["instances"][0]["arms"]["custom"]
        self.assertTrue(run["measurement_complete"])
        self.assertTrue(run["role_compliant"])
        self.assertTrue(run["routing_compliant"])
        self.assertFalse(run["recursion_detected"])
        self.assertEqual(run["total_tokens"], 130)
        child = next(item for item in run["threads"] if item["kind"] == "child")
        self.assertEqual(child["role"], "evidence_tester")
        self.assertEqual(child["parent_thread_id"], "custom-primary")

    def test_thread_attempt_declarations_reconcile_and_failed_retry_is_billed(self):
        missing = campaign()
        run = missing["instances"][0]["runs"]["baseline"]
        run["threads"] = run["threads"][:1]
        run["child_count"] = 0
        run["expected_receiver_ids"] = []
        with self.assertRaisesRegex(EvaluationError, "expected_thread_ids do not match"):
            validate_campaign(missing)

        mismatch = campaign()
        mismatch["instances"][0]["runs"]["baseline"]["retries"] = 1
        with self.assertRaisesRegex(EvaluationError, "does not match 0 recorded retry"):
            validate_campaign(mismatch)

        retried = campaign()
        run = retried["instances"][0]["runs"]["baseline"]
        run["threads"][1]["status"] = "failed"
        retry = copy.deepcopy(run["threads"][1])
        retry["attempt"] = 2
        retry["status"] = "completed"
        retry["tokens"]["output_tokens"] = 1
        retry["tokens"]["total_tokens"] = 1
        retry["credits"]["output"] = "0.5"
        retry["credits"]["total"] = "0.5"
        run["threads"].append(retry)
        run["retries"] = 1
        report = build_report(retried)
        measured = next(
            item for item in report["instances"] if item["instance_id"] == "development-b"
        )["arms"]["baseline"]
        self.assertEqual(measured["total_credits"], "10.5")
        self.assertEqual(measured["total_tokens"], 131)

    def test_execution_measurement_role_and_seal_mismatches_fail_closed(self):
        def nonterminal(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][1]["terminal"] = False

        def recursive(document, sealed):
            child = document["instances"][0]["runs"]["custom"]["threads"][1]
            child["parent_thread_id"] = child["thread_id"]

        def role_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][1]["role"] = "boundary_mapper"

        def token_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][0]["tokens"]["total_tokens"] = 999

        def cost_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][0]["credits"]["total"] = "999"

        def incomplete_cost(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][0]["cost_complete"] = False

        def receiver_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["expected_receiver_ids"] = []

        def order_drift(document, sealed):
            document["execution_order"][0], document["execution_order"][1] = (
                document["execution_order"][1], document["execution_order"][0]
            )

        cases = (
            ("nonterminal", nonterminal, "nonterminal"),
            ("recursive", recursive, "recursive or unknown parent"),
            ("role", role_mismatch, "custom receiver role mismatch"),
            ("tokens", token_mismatch, "total must equal input plus output"),
            ("cost", cost_mismatch, "credits total does not match"),
            ("incomplete-cost", incomplete_cost, "incomplete cost evidence"),
            ("receiver", receiver_mismatch, "expected_receiver_ids do not match"),
            ("order", order_drift, "execution_order drifts"),
        )
        for name, mutate, message in cases:
            for input_name, factory, sealed in (
                ("development", campaign, False),
                ("sealed", holdout, True),
            ):
                with self.subTest(case=name, input=input_name):
                    document = factory()
                    mutate(document, sealed)
                    with self.assertRaisesRegex(EvaluationError, message):
                        validate_campaign(document, sealed_holdout=sealed)

        completion_mismatch = holdout()
        completion_mismatch["completion"]["archive_sha256"] = "b" * 64
        with self.assertRaisesRegex(EvaluationError, "archive hash does not match"):
            validate_campaign(completion_mismatch, sealed_holdout=True)
        invalid_completion = holdout()
        invalid_completion["completion"]["all_records_valid"] = False
        with self.assertRaisesRegex(EvaluationError, "all_records_valid must be true"):
            validate_campaign(invalid_completion, sealed_holdout=True)
        receipt_mismatch = holdout()
        receipt_mismatch["completion"]["receipt_sha256"] = "b" * 64
        with self.assertRaisesRegex(EvaluationError, "completion receipt hash does not match"):
            validate_campaign(receipt_mismatch, sealed_holdout=True)

    def test_routing_process_scope_quality_and_contamination_block_promotion(self):
        mutations = (
            lambda run: run["routing_violations"].append("wrong receiver"),
            lambda run: run.update(process_exit_code=1),
            lambda run: run.update(completion_status="failed"),
            lambda run: run["scope_violations"].append("escaped scope"),
            lambda run: run["quality_checks"][0].update(passed=False),
            lambda run: run["contamination_audit"].update(passed=False),
        )
        for arm in ("baseline", "custom"):
            for mutate in mutations:
                with self.subTest(arm=arm, mutation=mutate):
                    sealed = holdout()
                    mutate(sealed["instances"][0]["runs"][arm])
                    result = build_report(campaign(), sealed)["task_classes"][0]
                    self.assertEqual(result["recommendation"], "primary-default")
                    self.assertFalse(result["paired_integrity_passed"])

    def test_grader_and_rubric_comparability_remains_strict(self):
        mutations = (
            ("grader_sha256", "b" * 64, "paired grader_sha256 mismatch"),
            ("quality_checks.0.id", "other", "paired rubric mismatch"),
            ("quality_checks.0.critical", False, "paired rubric mismatch"),
            ("quality_checks.0.max_score", 11, "paired rubric mismatch"),
        )
        for path, value, message in mutations:
            document = campaign()
            run = document["instances"][0]["runs"]["custom"]
            if path == "grader_sha256":
                run[path] = value
            else:
                _, _, field = path.split(".")
                run["quality_checks"][0][field] = value
            with self.subTest(path=path):
                with self.assertRaisesRegex(EvaluationError, message):
                    validate_campaign(document)

        for document, sealed in ((campaign(), False), (holdout(), True)):
            for run in document["instances"][0]["runs"].values():
                run["grader_sha256"] = "b" * 64
            with self.subTest(frozen_grader="sealed" if sealed else "development"):
                with self.assertRaisesRegex(
                    EvaluationError, "run grader does not match frozen grader"
                ):
                    validate_campaign(document, sealed_holdout=sealed)

    def test_mandatory_named_gate_exception_is_narrow_and_fail_closed(self):
        base = campaign()
        base["class_policies"]["test-triage"] = {
            "decision_mode": "mandatory_named_gate",
            "custom_role": "evidence_tester",
            "higher_level_required": True,
            "callable_builtin_equivalent": False,
            "availability_probe_reference": "removal-probe-receipt",
            "availability_probe_sha256": DIGEST,
            "restored_after_probe": True,
        }
        sealed = holdout()
        for document in (base, sealed):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "9.14")
        mandatory = build_report(base, sealed)["task_classes"][0]
        self.assertEqual(mandatory["recommendation"], "mandatory-custom")

        elective = campaign()
        elective_holdout = holdout()
        for document in (elective, elective_holdout):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "9.14")
        self.assertEqual(
            build_report(elective, elective_holdout)["task_classes"][0]["recommendation"],
            "primary-default",
        )

        missing = copy.deepcopy(base)
        del missing["class_policies"]["test-triage"]["availability_probe_reference"]
        with self.assertRaisesRegex(EvaluationError, "missing=.*availability_probe_reference"):
            validate_campaign(missing)
        builtin = copy.deepcopy(base)
        builtin["class_policies"]["test-triage"]["callable_builtin_equivalent"] = True
        with self.assertRaisesRegex(EvaluationError, "callable_builtin_equivalent must be false"):
            validate_campaign(builtin)
        lower = copy.deepcopy(sealed)
        lower["instances"][0]["runs"]["custom"]["quality_checks"][0]["score"] = 8
        self.assertEqual(
            build_report(base, lower)["task_classes"][0]["recommendation"],
            "primary-default",
        )

    def test_class_policy_role_cross_links_are_exact(self):
        overlap = campaign()
        overlap["allowed_baseline_roles"].append("evidence_tester")
        with self.assertRaisesRegex(EvaluationError, "overlap custom roles"):
            validate_campaign(overlap)

        extra_expected = campaign()
        extra_expected["instances"][0]["expected_roles"].append("boundary_mapper")
        extra_expected["instances"][0]["runs"]["custom"]["threads"].append(
            billed_thread(
                "custom-second-child",
                "child",
                "boundary_mapper",
                "custom-primary",
                "0",
            )
        )
        extra_expected["instances"][0]["runs"]["custom"]["expected_thread_ids"].append(
            "custom-second-child"
        )
        extra_expected["instances"][0]["runs"]["custom"]["expected_receiver_ids"].append(
            "custom-second-child"
        )
        extra_expected["instances"][0]["runs"]["custom"]["child_count"] = 2
        with self.assertRaisesRegex(EvaluationError, "expected_roles must exactly equal"):
            validate_campaign(extra_expected)

        sealed_role_drift = holdout()
        sealed_role_drift["instances"][0]["expected_roles"] = ["boundary_mapper"]
        sealed_role_drift["instances"][0]["runs"]["custom"]["threads"][1][
            "role"
        ] = "boundary_mapper"
        with self.assertRaisesRegex(EvaluationError, "expected_roles must exactly equal"):
            build_report(campaign(), sealed_role_drift)

    def test_sealed_boundary_and_external_cli(self):
        embedded = campaign()
        embedded["instances"].append(instance("leaked", "family-c", holdout=True))
        embedded["execution_order"] = freeze_order(embedded["instances"])
        with self.assertRaisesRegex(EvaluationError, "holdout must be false"):
            validate_campaign(embedded)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            campaign_path = root / "campaign.json"
            sealed_path = root / "private-sealed-results.json"
            report_path = root / "report.json"
            campaign_path.write_text(json.dumps(campaign()), encoding="utf-8")
            sealed_path.write_text(json.dumps(holdout()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "evaluation", "report", "--campaign", str(campaign_path), "--sealed-holdout", str(sealed_path), "--output", str(report_path)],
                cwd=PACKAGE_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["task_classes"][0]["sealed_holdout_count"], 1)
            serialized = campaign_path.read_text() + sealed_path.read_text()
            self.assertNotIn("grader_logic", serialized)
            self.assertNotIn("expected_answer\"", serialized)

    def test_schema_artifacts_parse_and_forbid_unknown_fields(self):
        schema = json.loads((PACKAGE_ROOT / "evaluation" / "campaign.schema.json").read_text())
        sealed = json.loads((PACKAGE_ROOT / "evaluation" / "sealed-holdout.schema.json").read_text())
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["thread"]["additionalProperties"])
        self.assertFalse(sealed["additionalProperties"])
        self.assertEqual(schema["$defs"]["thread"]["properties"]["kind"]["enum"], ["primary", "child"])

    def test_bundled_smoke_fixture_and_cli(self):
        examples = PACKAGE_ROOT / "evaluation" / "examples"
        development = json.loads((examples / "campaign.json").read_text())
        sealed = json.loads((examples / "sealed-holdout.json").read_text())
        report = build_report(development, sealed)
        self.assertEqual(report["campaign_id"], "public-smoke")
        self.assertEqual(len(report["instances"]), 2)

        completed = subprocess.run(
            [sys.executable, "-B", "-m", "evaluation", "smoke"],
            cwd=PACKAGE_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("valid and deterministic", completed.stdout)


if __name__ == "__main__":
    unittest.main()

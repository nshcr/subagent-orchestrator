import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid


PACKAGE_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from evaluation import (  # noqa: E402
    EvaluationError,
    build_report,
    canonical_digest,
    extract_production_facts,
    validate_campaign,
    validate_evidence_chain,
    validate_production_fact,
)
from evaluation.production_facts import _metric  # noqa: E402


DIGEST = "a" * 64
DEVELOPMENT_AUTHORITY = "d" * 64
SEALED_AUTHORITY = "e" * 64
RUBRIC_DIGEST = "175477d27e98477551afa3de27d6792b128110b4fa9a37de7a87783d4303eb0c"


def payload_digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def refresh_quality_binding(check, authority, grader=DIGEST):
    evidence = check["evidence"]
    result_payload = {
        "artifact_sha256": evidence["artifact_sha256"],
        "artifact_source_id": evidence["artifact_source_id"],
        "critical": check["critical"],
        "evidence_kind": evidence["kind"],
        "id": check["id"],
        "max_score": check["max_score"],
        "passed": check["passed"],
        "schema_version": "quality-check-result.v1",
        "score": check["score"],
    }
    result_sha256 = payload_digest(result_payload)
    execution = {
        "authority_receipt_sha256": authority,
        "grader_sha256": grader,
        "evidence_artifact_sha256": evidence["artifact_sha256"],
        "artifact_source_id": evidence["artifact_source_id"],
        "result_sha256": result_sha256,
        "exit_code": 0,
    }
    receipt_payload = {
        "artifact_source_id": execution["artifact_source_id"],
        "authority_receipt_sha256": execution["authority_receipt_sha256"],
        "evidence_artifact_sha256": execution["evidence_artifact_sha256"],
        "exit_code": execution["exit_code"],
        "grader_sha256": execution["grader_sha256"],
        "result_sha256": execution["result_sha256"],
        "schema_version": "grader-execution-receipt.v1",
    }
    execution["receipt_sha256"] = payload_digest(receipt_payload)
    evidence["grader_execution"] = execution


def refresh_run_quality(run, authority):
    for check in run["quality_checks"]:
        refresh_quality_binding(check, authority, run["grader_sha256"])


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


def arm_evidence(arm, credits, identifier, authority):
    primary_id = f"{arm}-primary"
    child_id = f"{arm}-child"
    child_role = "explorer" if arm == "baseline" else "evidence_tester"
    artifact_source_id = f"sidecar://{identifier}/{arm}/grounded-result"
    artifact_sha256 = hashlib.sha256(artifact_source_id.encode("utf-8")).hexdigest()
    run = {
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
                "evidence": {
                    "kind": "behavior",
                    "artifact_sha256": artifact_sha256,
                    "artifact_source_id": artifact_source_id,
                    "grader_execution": {},
                },
            }
        ],
        "scope_violations": [],
        "routing_violations": [],
        "routing_decision": "bounded specialist",
        "grader_sha256": DIGEST,
        "contamination_audit": {"passed": True, "notes": "clean"},
    }
    refresh_run_quality(run, authority)
    return run


def instance(identifier, family, *, holdout=False):
    arm_order = (
        ["custom", "baseline"]
        if identifier == "development-b"
        else ["baseline", "custom"]
    )
    authority = SEALED_AUTHORITY if holdout else DEVELOPMENT_AUTHORITY
    return {
        "instance_id": identifier,
        "task_class": "test-triage",
        "fixture_family": family,
        "fixture_sha256": hashlib.sha256(f"fixture:{identifier}".encode()).hexdigest(),
        "prompt_sha256": hashlib.sha256(f"prompt:{identifier}".encode()).hexdigest(),
        "rubric_sha256": RUBRIC_DIGEST,
        "scenario": f"scenario {identifier}",
        "expected_roles": ["evidence_tester"],
        "holdout": holdout,
        "arm_order": arm_order,
        "runs": {
            "baseline": arm_evidence("baseline", "10", identifier, authority),
            "custom": arm_evidence("custom", "9", identifier, authority),
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
        "schema_version": 3,
        "campaign_id": "campaign-1",
        "configuration_hashes": {
            "role_instructions": DIGEST,
            "routing_policy": DIGEST,
            "task_fixtures": DIGEST,
            "graders": DIGEST,
            "grader_execution_authority_receipt": DEVELOPMENT_AUTHORITY,
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
        "schema_version": 3,
        "campaign_id": "campaign-1",
        "allowed_baseline_roles": ["explorer"],
        "seal": {
            "seal_id": "external-seal-1",
            "receipt_sha256": SEALED_AUTHORITY,
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
            "receipt_sha256": SEALED_AUTHORITY,
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
            ("incomplete-cost", incomplete_cost, "unavailable cost evidence"),
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
                    run = sealed["instances"][0]["runs"][arm]
                    mutate(run)
                    refresh_run_quality(run, SEALED_AUTHORITY)
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
                refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
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

        unfrozen = campaign()
        for run in unfrozen["instances"][0]["runs"].values():
            run["quality_checks"][0]["max_score"] = 11
            refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
        with self.assertRaisesRegex(EvaluationError, "rubric_sha256 does not match"):
            validate_campaign(unfrozen)

    def test_quality_checks_require_bound_artifacts_and_verified_grader_execution(self):
        behavior = campaign()
        validate_campaign(behavior)

        prescribed = campaign()
        prescribed["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["kind"] = "prescribed-phrase"
        with self.assertRaisesRegex(EvaluationError, "must be behavior or source-fact"):
            validate_campaign(prescribed)

        unbound = campaign()
        execution = unbound["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["grader_execution"]
        execution["evidence_artifact_sha256"] = "b" * 64
        with self.assertRaisesRegex(EvaluationError, "does not bind evidence artifact"):
            validate_campaign(unbound)

        missing_source = campaign()
        missing_source["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["artifact_source_id"] = ""
        with self.assertRaisesRegex(EvaluationError, "must be a non-empty string"):
            validate_campaign(missing_source)

        self_filled = campaign()
        self_filled_execution = self_filled["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]["evidence"]["grader_execution"]
        self_filled_execution["result_sha256"] = "b" * 64
        self_filled_execution["receipt_sha256"] = "c" * 64
        with self.assertRaisesRegex(EvaluationError, "canonical check result"):
            validate_campaign(self_filled)

        changed_after_receipt = campaign()
        changed_check = changed_after_receipt["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]
        original_receipt = changed_check["evidence"]["grader_execution"][
            "receipt_sha256"
        ]
        changed_check["score"] = 9
        refresh_quality_binding(changed_check, DEVELOPMENT_AUTHORITY)
        changed_check["evidence"]["grader_execution"][
            "receipt_sha256"
        ] = original_receipt
        with self.assertRaisesRegex(EvaluationError, "canonical execution"):
            validate_campaign(changed_after_receipt)

        wrong_authority = campaign()
        wrong_authority_check = wrong_authority["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]
        refresh_quality_binding(wrong_authority_check, "b" * 64)
        with self.assertRaisesRegex(EvaluationError, "frozen external authority"):
            validate_campaign(wrong_authority)

        wrong_sealed_authority = holdout()
        wrong_sealed_check = wrong_sealed_authority["instances"][0]["runs"][
            "custom"
        ]["quality_checks"][0]
        refresh_quality_binding(wrong_sealed_check, DEVELOPMENT_AUTHORITY)
        with self.assertRaisesRegex(EvaluationError, "frozen external authority"):
            validate_campaign(wrong_sealed_authority, sealed_holdout=True)

        wrong_grader = campaign()
        wrong_grader_check = wrong_grader["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]
        refresh_quality_binding(
            wrong_grader_check, DEVELOPMENT_AUTHORITY, grader="b" * 64
        )
        with self.assertRaisesRegex(EvaluationError, "does not match run grader"):
            validate_campaign(wrong_grader)

        unverified = campaign()
        unverified["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["grader_execution"]["exit_code"] = 1
        with self.assertRaisesRegex(EvaluationError, "exit_code must be integer zero"):
            validate_campaign(unverified)

        source_fact = campaign()
        for run in source_fact["instances"][0]["runs"].values():
            run["quality_checks"][0]["evidence"]["kind"] = "source-fact"
            refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
        signature = [("grounded-result", True, 10, "source-fact")]
        source_fact["instances"][0]["rubric_sha256"] = hashlib.sha256(
            json.dumps(signature, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        validate_campaign(source_fact)

        relabeled = copy.deepcopy(source_fact)
        for run in relabeled["instances"][0]["runs"].values():
            check = run["quality_checks"][0]
            original_receipt = check["evidence"]["grader_execution"][
                "receipt_sha256"
            ]
            check["evidence"]["kind"] = "behavior"
            refresh_quality_binding(check, DEVELOPMENT_AUTHORITY)
            check["evidence"]["grader_execution"][
                "receipt_sha256"
            ] = original_receipt
        with self.assertRaisesRegex(EvaluationError, "canonical execution"):
            validate_campaign(relabeled)

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
        self.assertEqual(mandatory["recommendation"], "retained-not-efficient")
        self.assertEqual(mandatory["governance_retention"]["decision"], "PASS")
        self.assertEqual(mandatory["efficiency_promotion"]["decision"], "BLOCK")

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
        refresh_run_quality(
            lower["instances"][0]["runs"]["custom"], SEALED_AUTHORITY
        )
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
        production = json.loads(
            (PACKAGE_ROOT / "evaluation" / "production-fact.schema.json").read_text()
        )
        tiers = json.loads(
            (PACKAGE_ROOT / "evaluation" / "evidence-tier.schema.json").read_text()
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["thread"]["additionalProperties"])
        self.assertFalse(sealed["additionalProperties"])
        self.assertFalse(production["additionalProperties"])
        self.assertFalse(production["properties"]["metrics"]["additionalProperties"])
        self.assertFalse(tiers["additionalProperties"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], 3)
        self.assertEqual(sealed["properties"]["schema_version"]["const"], 3)
        self.assertIn(
            "grader_execution_authority_receipt",
            schema["properties"]["configuration_hashes"]["required"],
        )
        evidence_schema = schema["$defs"]["check"]["properties"]["evidence"]
        self.assertIn("artifact_source_id", evidence_schema["required"])
        self.assertIn(
            "authority_receipt_sha256",
            evidence_schema["properties"]["grader_execution"]["required"],
        )
        self.assertEqual(
            evidence_schema["properties"]["kind"]["enum"],
            ["behavior", "source-fact"],
        )
        self.assertFalse(evidence_schema["additionalProperties"])
        self.assertFalse(
            evidence_schema["properties"]["grader_execution"]["additionalProperties"]
        )
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

    def test_paired_pareto_blocks_pooled_quality_and_independent_median_tricks(self):
        pooled = campaign()
        pooled["instances"][0]["runs"]["custom"]["quality_checks"][0]["score"] = 9
        refresh_run_quality(
            pooled["instances"][0]["runs"]["custom"], DEVELOPMENT_AUTHORITY
        )
        for arm in ("baseline", "custom"):
            run = pooled["instances"][1]["runs"][arm]
            run["quality_checks"][0]["max_score"] = 100
        pooled["instances"][1]["runs"]["baseline"]["quality_checks"][0]["score"] = 1
        pooled["instances"][1]["runs"]["custom"]["quality_checks"][0]["score"] = 100
        for run in pooled["instances"][1]["runs"].values():
            refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
        pooled["instances"][1]["rubric_sha256"] = "727ebd27e04a873a6e84043d1a71ade2060beffb668d26c6b2707e484ecb208d"
        result = build_report(pooled, holdout())["task_classes"][0]
        self.assertFalse(result["quality_non_regression"])
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        median_trick = campaign()
        sealed = holdout()
        pairs = [
            median_trick["instances"][0],
            median_trick["instances"][1],
            sealed["instances"][0],
        ]
        for item, baseline_cost, custom_cost in zip(
            pairs, ("0.01", "100", "100"), ("1", "90", "90"), strict=True
        ):
            set_run_credits(item["runs"]["baseline"], baseline_cost)
            set_run_credits(item["runs"]["custom"], custom_cost)
        result = build_report(median_trick, sealed)["task_classes"][0]
        self.assertEqual(result["arms"]["custom"]["median_total_credits"], "90")
        self.assertEqual(result["arms"]["baseline"]["median_total_credits"], "100")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")
        self.assertTrue(
            any(Decimal(value) > Decimal("1") for value in result["pair_credit_ratios"])
        )

    def test_duplicate_fixture_zero_baseline_and_cost_unavailability_fail_closed(self):
        duplicate = campaign()
        duplicate["instances"][1]["fixture_sha256"] = duplicate["instances"][0][
            "fixture_sha256"
        ]
        with self.assertRaisesRegex(EvaluationError, "duplicate fixture_sha256"):
            validate_campaign(duplicate)
        duplicate_prompt = campaign()
        duplicate_prompt["instances"][1]["prompt_sha256"] = duplicate_prompt[
            "instances"
        ][0]["prompt_sha256"]
        with self.assertRaisesRegex(EvaluationError, "duplicate prompt_sha256"):
            validate_campaign(duplicate_prompt)

        zero = campaign()
        set_run_credits(zero["instances"][0]["runs"]["baseline"], "0")
        result = build_report(zero, holdout())["task_classes"][0]
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        aggregate = campaign()
        aggregate_holdout = holdout()
        for document in (aggregate, aggregate_holdout):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "11")
        result = build_report(aggregate, aggregate_holdout)["task_classes"][0]
        self.assertGreater(Decimal(result["class_credit_ratio"]), Decimal("1"))
        self.assertGreater(Decimal(result["overall_credit_ratio"]), Decimal("1"))
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        unavailable = campaign()
        thread = unavailable["instances"][0]["runs"]["custom"]["threads"][0]
        thread["cost_complete"] = False
        thread["credits"] = {key: None for key in thread["credits"]}
        result = build_report(unavailable, holdout())["task_classes"][0]
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")
        self.assertIsNone(result["arms"]["custom"]["total_credits"])

    def test_positive_quality_requires_cost_non_regression_and_mandatory_dual_outcomes(self):
        improved = campaign()
        sealed = holdout()
        improved["instances"][0]["runs"]["baseline"]["quality_checks"][0]["score"] = 9
        refresh_run_quality(
            improved["instances"][0]["runs"]["baseline"], DEVELOPMENT_AUTHORITY
        )
        set_run_credits(improved["instances"][0]["runs"]["custom"], "11")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["quality_outcome"], "improved")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        set_run_credits(improved["instances"][0]["runs"]["custom"], "10")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["efficiency_promotion"]["decision"], "PASS")

        improved["class_policies"]["test-triage"] = {
            "decision_mode": "mandatory_named_gate",
            "custom_role": "evidence_tester",
            "higher_level_required": True,
            "callable_builtin_equivalent": False,
            "availability_probe_reference": "probe",
            "availability_probe_sha256": DIGEST,
            "restored_after_probe": True,
        }
        for document in (improved, sealed):
            for item in document["instances"]:
                set_run_credits(item["runs"]["baseline"], "30")
                set_run_credits(item["runs"]["custom"], "33")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["recommendation"], "retained-not-efficient")
        self.assertEqual(result["governance_retention"]["decision"], "PASS")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        for document in (improved, sealed):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "30")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["recommendation"], "retained-efficient")

        thread = improved["instances"][0]["runs"]["custom"]["threads"][0]
        thread["cost_complete"] = False
        thread["credits"] = {key: None for key in thread["credits"]}
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["recommendation"], "retained-not-efficient")
        self.assertEqual(result["governance_retention"]["decision"], "PASS")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")


def evidence_document(tier, *, revision="abc123", package=DIGEST):
    provenance = {
        "implemented": {
            "source_tree_sha256": DIGEST,
            "diff_sha256": DIGEST,
            "implementation_receipt_sha256": DIGEST,
        },
        "verified-local": {
            "command": "python3 -B validate.py",
            "exit_code": 0,
            "environment_sha256": DIGEST,
            "result_sha256": DIGEST,
        },
        "verified-ci": {
            "provider": "github-actions",
            "run_id": "123",
            "run_url": "https://example.invalid/run/123",
            "revision": revision,
            "result_sha256": DIGEST,
        },
        "verified-target": {
            "target_id": "target-a",
            "environment_sha256": DIGEST,
            "revision": revision,
            "package_digest": package,
            "receipt_sha256": DIGEST,
        },
        "pilot-signed": {
            "authority": "deployment-owner",
            "authority_id": "owner-1",
            "signed_at": "2026-08-16T10:00:00+08:00",
            "signature_sha256": DIGEST,
            "target_receipt_sha256": DIGEST,
        },
    }[tier]
    return {
        "schema_version": "evidence-tier.v1",
        "tier": tier,
        "revision": revision,
        "package_digest": package,
        "artifact_digest": DIGEST,
        "predecessor": None,
        "provenance": provenance,
    }


def evidence_chain():
    chain = []
    for tier in ("implemented", "verified-local", "verified-ci", "verified-target", "pilot-signed"):
        document = evidence_document(tier)
        if chain:
            document["predecessor"] = {
                "tier": chain[-1]["tier"],
                "digest": canonical_digest(chain[-1]),
            }
        chain.append(document)
    return chain


class EvidenceTierTest(unittest.TestCase):
    def test_exact_monotonic_chain_and_cli(self):
        chain = evidence_chain()
        validate_evidence_chain(chain)
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for index, document in enumerate(chain):
                path = Path(temporary) / f"{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.extend(["--input", str(path)])
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "evaluation", "evidence-tier", *paths],
                cwd=PACKAGE_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_missing_skipped_proxy_mismatch_and_authority_fail(self):
        cases = []
        missing = evidence_chain()[:2]
        missing[1]["predecessor"] = None
        cases.append((missing, "predecessor"))
        cases.append(([evidence_chain()[0], evidence_chain()[2]], "skips or reorders"))
        proxy = evidence_chain()[:2]
        proxy[1]["provenance"] = {"narrative": "verified locally"}
        cases.append((proxy, "keys mismatch"))
        mismatch = evidence_chain()[:3]
        mismatch[2]["revision"] = "different"
        cases.append((mismatch, "revision/package"))
        package_mismatch = evidence_chain()[:2]
        package_mismatch[1]["package_digest"] = "b" * 64
        cases.append((package_mismatch, "revision/package"))
        pilot = evidence_chain()
        del pilot[-1]["provenance"]["authority"]
        cases.append((pilot, "keys mismatch"))
        target_receipt_mismatch = evidence_chain()
        target_receipt_mismatch[-1]["provenance"]["target_receipt_sha256"] = "b" * 64
        cases.append((target_receipt_mismatch, "does not match verified-target receipt"))
        for chain, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(EvaluationError, message):
                    validate_evidence_chain(chain)


def uuid7_for(moment):
    milliseconds = int(moment.timestamp() * 1000)
    return str(uuid.UUID(int=(milliseconds << 80) | (7 << 76) | (2 << 62) | 1))


def write_jsonl(path, events):
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


class ProductionFactsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "base"], check=True)
        self.base = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.parent = self.root / "parent.jsonl"
        self.children = self.root / "children"
        self.children.mkdir()
        self.spawn = datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc)
        self.child_id = uuid7_for(self.spawn.replace(microsecond=1000))
        self._write_valid_sources()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_valid_sources(self, *, fork_turns="all", extra_parent=(), extra_child=()):
        call_id = "spawn-1"
        write_jsonl(
            self.parent,
            [
                {"timestamp": self.spawn.isoformat(), "type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": call_id, "arguments": json.dumps({"task_name": "worker__fact", "fork_turns": fork_turns})}},
                {"timestamp": self.spawn.replace(microsecond=500).isoformat(), "type": "response_item", "payload": {"type": "function_call_output", "call_id": call_id, "output": json.dumps({"agent_id": self.child_id})}},
                {"timestamp": self.spawn.replace(microsecond=700).isoformat(), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 1, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "output_tokens": 1, "reasoning_output_tokens": 0, "total_tokens": 2}}}},
                {"timestamp": self.spawn.replace(microsecond=800).isoformat(), "type": "event_msg", "payload": {"type": "billing_record", "scope": "thread", "thread_id": "parent-thread", "credits": {"uncached_input": "3", "cached_input": "1", "output": "2", "total": "6"}}},
                {"timestamp": self.spawn.replace(microsecond=900).isoformat(), "type": "event_msg", "payload": {"type": "billing_record", "scope": "run", "run_id": "run-1", "credits": {"uncached_input": "5", "cached_input": "1", "output": "4", "total": "10"}}},
                *extra_parent,
            ],
        )
        start = self.spawn.replace(microsecond=2000)
        write_jsonl(
            self.children / f"{self.child_id}.jsonl",
            [
                {"timestamp": self.spawn.replace(microsecond=1000).isoformat(), "type": "session_meta", "payload": {"id": self.child_id}},
                {"timestamp": start.isoformat(), "type": "turn_context", "payload": {"role": "worker"}},
                {"timestamp": self.spawn.replace(microsecond=3000).isoformat(), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 10, "cached_input_tokens": 2, "cache_write_input_tokens": 0, "output_tokens": 4, "reasoning_output_tokens": 1, "total_tokens": 14}}}},
                *extra_child,
                {"timestamp": self.spawn.replace(microsecond=4000).isoformat(), "type": "event_msg", "payload": {"type": "billing_record", "scope": "thread", "thread_id": self.child_id, "credits": {"uncached_input": "2", "cached_input": "0", "output": "2", "total": "4"}}},
                {"timestamp": self.spawn.replace(microsecond=5000).isoformat(), "type": "event_msg", "payload": {"type": "agent_status", "status": "completed"}},
            ],
        )

    def _extract(self, state="terminal"):
        return extract_production_facts(
            parent=self.parent,
            children_root=self.children,
            repo=self.repo,
            base=self.base,
            cutoff=datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
            source_state=state,
        )

    def test_terminal_fact_is_private_typed_and_complete(self):
        fact = self._extract()
        self.assertEqual(fact["schema_version"], "production-fact.v1")
        self.assertFalse(fact["completion_claim_eligible"])
        self.assertFalse(fact["causal_claim_eligible"])
        self.assertFalse(fact["promotion_claim_eligible"])
        observational_laundering = copy.deepcopy(fact)
        observational_laundering["completion_claim_eligible"] = True
        with self.assertRaisesRegex(EvaluationError, "observational production facts"):
            validate_production_fact(observational_laundering)
        self.assertEqual(fact["metrics"]["forks"]["all"]["value"], 1)
        serialized = json.dumps(fact)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(self.child_id, serialized)
        for item in fact["metrics"]["tokens"].values():
            self.assertEqual(item["status"], "available")
            self.assertIsNotNone(item["basis"])
            self.assertIsNotNone(item["source_id"])
        for item in fact["metrics"]["credits"].values():
            self.assertEqual(item["status"], "available")
        self.assertEqual(fact["metrics"]["credits"]["thread_total"]["value"], "10")
        self.assertEqual(fact["metrics"]["credits"]["run_total"]["value"], "10")
        child_raw = next(self.children.iterdir()).read_bytes()
        session_meta_size = len(child_raw.splitlines(keepends=True)[0])
        self.assertEqual(
            fact["metrics"]["log_bytes"]["children"]["value"],
            len(child_raw) - session_meta_size,
        )
        self.assertEqual(
            fact["metrics"]["log_bytes"]["total"]["value"],
            fact["metrics"]["log_bytes"]["parent"]["value"]
            + fact["metrics"]["log_bytes"]["children"]["value"],
        )
        child_path = next(self.children.iterdir())
        child_path.write_text(
            child_path.read_text(encoding="utf-8")
            + json.dumps(
                {
                    "timestamp": "2026-08-16T03:00:00+00:00",
                    "type": "event_msg",
                    "payload": {"type": "after-cutoff"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        rebound = self._extract()
        self.assertNotEqual(fact["sources"]["child_sha256"], rebound["sources"]["child_sha256"])
        for key in ("parent", "children", "total"):
            self.assertEqual(
                fact["metrics"]["log_bytes"][key]["value"],
                rebound["metrics"]["log_bytes"][key]["value"],
            )
        output = self.root / "fact.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "evaluation",
                "production-facts",
                "--parent",
                str(self.parent),
                "--children-root",
                str(self.children),
                "--repo",
                str(self.repo),
                "--base",
                self.base,
                "--cutoff",
                "2026-08-16T02:00:00+00:00",
                "--source-state",
                "terminal",
                "--output",
                str(output),
            ],
            cwd=PACKAGE_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text())["schema_version"], "production-fact.v1")

    def test_copied_history_active_dirty_unsupported_nested_and_failed_spawn(self):
        copied = {"timestamp": "2026-08-16T00:59:59+00:00", "type": "turn_context", "payload": {"role": "primary"}}
        self._write_valid_sources(extra_child=(copied,))
        with self.assertRaisesRegex(EvaluationError, "copied pre-spawn"):
            self._extract()

        self._write_valid_sources(extra_parent=({"timestamp": self.spawn.replace(microsecond=4000).isoformat(), "type": "future_event", "payload": {}},))
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        fact = self._extract("active")
        self.assertFalse(fact["causal_claim_eligible"])
        self.assertFalse(fact["git_source"]["clean"])
        self.assertEqual(fact["unsupported_event_count"]["value"], 1)
        (self.repo / "dirty.txt").unlink()

        nested_id = uuid7_for(self.spawn.replace(microsecond=4000))
        nested = (
            {"timestamp": self.spawn.replace(microsecond=3500).isoformat(), "type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": "nested", "arguments": json.dumps({"task_name": "nested"})}},
            {"timestamp": self.spawn.replace(microsecond=3600).isoformat(), "type": "response_item", "payload": {"type": "function_call_output", "call_id": "nested", "output": json.dumps({"agent_id": nested_id})}},
        )
        self._write_valid_sources(extra_child=nested)
        fact = self._extract()
        self.assertEqual(fact["metrics"]["spawns"]["nested"]["value"], 1)
        self.assertFalse(fact["promotion_claim_eligible"])

        for path in self.children.iterdir():
            path.unlink()
        write_jsonl(
            self.parent,
            [
                {"timestamp": self.spawn.isoformat(), "type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": "failed", "arguments": json.dumps({"task_name": "failed"})}},
                {"timestamp": self.spawn.replace(microsecond=1000).isoformat(), "type": "response_item", "payload": {"type": "function_call_output", "call_id": "failed", "is_error": True, "output": "failed to spawn"}},
            ],
        )
        fact = self._extract()
        self.assertEqual(fact["metrics"]["spawns"]["failed"]["value"], 1)
        self.assertFalse(fact["completion_claim_eligible"])

    def test_child_lineage_requires_unique_ordered_earliest_turn_context(self):
        child_path = next(self.children.iterdir())
        events = [json.loads(line) for line in child_path.read_text().splitlines()]
        events[1]["timestamp"] = self.spawn.replace(microsecond=3000).isoformat()
        events.insert(
            2,
            {
                "timestamp": self.spawn.replace(microsecond=2000).isoformat(),
                "type": "turn_context",
                "payload": {"role": "worker"},
            },
        )
        write_jsonl(child_path, events)
        with self.assertRaisesRegex(EvaluationError, "lineage is out of order"):
            self._extract()

        self._write_valid_sources()
        child_path = next(self.children.iterdir())
        events = [json.loads(line) for line in child_path.read_text().splitlines()]
        events.insert(2, copy.deepcopy(events[1]))
        write_jsonl(child_path, events)
        with self.assertRaisesRegex(EvaluationError, "lineage start is ambiguous"):
            self._extract()

        self._write_valid_sources()
        self.assertFalse(self._extract()["completion_claim_eligible"])

    def test_metric_status_equivalence_and_divergent_git(self):
        with self.assertRaisesRegex(EvaluationError, "available metric"):
            _metric(1, None, None)
        with self.assertRaisesRegex(EvaluationError, "unavailable metric"):
            _metric(None, "basis", "source")
        fact = self._extract()
        numeric_unavailable = copy.deepcopy(fact)
        numeric_unavailable["metrics"]["tokens"]["total_tokens"]["status"] = "unavailable"
        with self.assertRaisesRegex(EvaluationError, "unavailable status requires null"):
            validate_production_fact(numeric_unavailable)
        null_available = copy.deepcopy(fact)
        null_available["metrics"]["tokens"]["total_tokens"]["value"] = None
        with self.assertRaisesRegex(EvaluationError, "available status requires non-null"):
            validate_production_fact(null_available)
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "--orphan", "divergent"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "rm", "-q", "-f", "tracked.txt"], check=True)
        (self.repo / "other.txt").write_text("other\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "other.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "divergent"], check=True)
        fact = self._extract()
        self.assertFalse(fact["git_source"]["base_is_ancestor"])
        self.assertFalse(fact["causal_claim_eligible"])

    def test_credit_records_fail_closed_and_never_derive_from_tokens(self):
        source_paths = [self.parent, *self.children.iterdir()]
        for path in source_paths:
            events = [json.loads(line) for line in path.read_text().splitlines()]
            write_jsonl(
                path,
                [
                    event
                    for event in events
                    if event.get("payload", {}).get("type") != "billing_record"
                ],
            )
        fact = self._extract()
        self.assertTrue(
            all(
                metric["status"] == "unavailable" and metric["value"] is None
                for metric in fact["metrics"]["credits"].values()
            )
        )
        self.assertTrue(
            all(metric["status"] == "available" for metric in fact["metrics"]["tokens"].values())
        )
        self.assertFalse(fact["promotion_claim_eligible"])

        self._write_valid_sources()
        child_path = next(self.children.iterdir())
        child_events = [json.loads(line) for line in child_path.read_text().splitlines()]
        billing = next(
            event
            for event in child_events
            if event.get("payload", {}).get("type") == "billing_record"
        )
        child_events.insert(-1, copy.deepcopy(billing))
        write_jsonl(child_path, child_events)
        ambiguous = self._extract()
        self.assertTrue(
            all(
                metric["status"] == "unavailable"
                for metric in ambiguous["metrics"]["credits"].values()
            )
        )
        self.assertFalse(ambiguous["promotion_claim_eligible"])

        self._write_valid_sources()
        parent_events = [json.loads(line) for line in self.parent.read_text().splitlines()]
        run_record = next(
            event
            for event in parent_events
            if event.get("payload", {}).get("scope") == "run"
        )
        run_record["payload"]["credits"]["uncached_input"] = "6"
        run_record["payload"]["credits"]["total"] = "11"
        write_jsonl(self.parent, parent_events)
        with self.assertRaisesRegex(EvaluationError, "do not match complete thread"):
            self._extract()


if __name__ == "__main__":
    unittest.main()

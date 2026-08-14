#!/usr/bin/env python3
"""Validate evaluation evidence and emit deterministic policy reports.

This command never invokes a model, a grader, or the network. Development
campaign evidence and sealed-holdout evidence are separate inputs. The latter
is injected only with ``--sealed-holdout`` after grading has completed.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = 1
EXAMPLES_ROOT = Path(__file__).resolve().parent / "examples"
ARMS = {"baseline", "custom"}
TOKEN_KEYS = {
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}
CREDIT_CATEGORY_KEYS = {"uncached_input", "cached_input", "output"}
CREDIT_KEYS = {*CREDIT_CATEGORY_KEYS, "total"}
CAMPAIGN_KEYS = {
    "schema_version",
    "campaign_id",
    "configuration_hashes",
    "allowed_baseline_roles",
    "class_policies",
    "execution_order",
    "instances",
}
HOLDOUT_KEYS = {
    "schema_version",
    "campaign_id",
    "seal",
    "completion",
    "allowed_baseline_roles",
    "execution_order",
    "instances",
}
EXECUTION_ENTRY_KEYS = {"instance_id", "arm"}
ELECTIVE_POLICY_KEYS = {"decision_mode", "custom_role"}
MANDATORY_POLICY_KEYS = {
    "decision_mode",
    "custom_role",
    "higher_level_required",
    "callable_builtin_equivalent",
    "availability_probe_reference",
    "availability_probe_sha256",
    "restored_after_probe",
}
INSTANCE_KEYS = {
    "instance_id",
    "task_class",
    "fixture_family",
    "scenario",
    "expected_roles",
    "holdout",
    "arm_order",
    "runs",
}
RUN_KEYS = {
    "threads",
    "expected_thread_ids",
    "expected_receiver_ids",
    "process_exit_code",
    "completion_status",
    "execution_index",
    "wall_time_ms",
    "child_count",
    "retries",
    "quality_checks",
    "scope_violations",
    "routing_violations",
    "routing_decision",
    "grader_sha256",
    "contamination_audit",
}
THREAD_KEYS = {
    "thread_id",
    "kind",
    "attempt",
    "status",
    "role",
    "parent_thread_id",
    "terminal",
    "cost_complete",
    "model",
    "effort",
    "service_tier",
    "tokens",
    "credits",
}
THREAD_KINDS = {"primary", "child"}
THREAD_STATUSES = {"completed", "failed", "cancelled"}
CHECK_KEYS = {"id", "passed", "critical", "score", "max_score"}
AUDIT_KEYS = {"passed", "notes"}
SEAL_KEYS = {
    "seal_id",
    "receipt_sha256",
    "runner_sha256",
    "harness_sha256",
    "grader_sha256",
    "expected_answers_sha256",
    "fixtures_sha256",
    "prompts_sha256",
    "live_configuration_sha256",
    "agent_visibility_boundary_enforced",
    "runner_unlinked_before_agents",
}
COMPLETION_KEYS = {
    "receipt_sha256",
    "results_sha256",
    "archive_sha256",
    "all_tested_threads_terminal_before_archive",
    "all_records_valid",
    "all_contamination_audits_clean",
}
CONFIGURATION_HASH_KEYS = {
    "role_instructions",
    "routing_policy",
    "task_fixtures",
    "graders",
    "pricing",
}
DECIMAL_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class EvaluationError(ValueError):
    """Raised when campaign evidence violates the evaluation contract."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"cannot read {path}: {error}") from error
    if not isinstance(document, dict):
        raise EvaluationError(f"{path} root must be an object")
    return document


def _require_exact_keys(value: object, expected: set[str], location: str) -> dict:
    if not isinstance(value, dict):
        raise EvaluationError(f"{location} must be an object")
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise EvaluationError(f"{location} keys mismatch; missing={missing}; extra={extra}")
    return value


def _require_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{location} must be a non-empty string")
    return value


def _require_integer(value: object, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EvaluationError(f"{location} must be a non-negative integer")
    return value


def _require_plain_integer(value: object, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise EvaluationError(f"{location} must be an integer")
    return value


def _require_positive_integer(value: object, location: str) -> int:
    value = _require_integer(value, location)
    if value == 0:
        raise EvaluationError(f"{location} must be a positive integer")
    return value


def _require_boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationError(f"{location} must be a boolean")
    return value


def _require_string_list(value: object, location: str) -> list[str]:
    if not isinstance(value, list):
        raise EvaluationError(f"{location} must be a string list")
    result = []
    for index, item in enumerate(value):
        result.append(_require_string(item, f"{location}[{index}]"))
    if len(result) != len(set(result)):
        raise EvaluationError(f"{location} must not contain duplicates")
    return result


def _require_sha256(value: object, location: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise EvaluationError(f"{location} must be a lowercase SHA-256 digest")
    return value


def _require_decimal(value: object, location: str) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_PATTERN.fullmatch(value):
        raise EvaluationError(f"{location} must be a non-negative decimal string")
    try:
        return Decimal(value)
    except InvalidOperation as error:  # pragma: no cover - guarded by the pattern
        raise EvaluationError(f"{location} is not a decimal") from error


def _validate_run(
    run: object,
    location: str,
    *,
    arm: str,
    expected_roles: list[str],
    allowed_baseline_roles: list[str],
) -> None:
    run = _require_exact_keys(run, RUN_KEYS, location)
    _require_string(run["routing_decision"], f"{location}.routing_decision")
    expected_thread_ids = _require_string_list(
        run["expected_thread_ids"], f"{location}.expected_thread_ids"
    )
    expected_receiver_ids = _require_string_list(
        run["expected_receiver_ids"], f"{location}.expected_receiver_ids"
    )
    _require_plain_integer(run["process_exit_code"], f"{location}.process_exit_code")
    _require_integer(run["execution_index"], f"{location}.execution_index")
    if run["completion_status"] not in THREAD_STATUSES:
        raise EvaluationError(
            f"{location}.completion_status must be one of {sorted(THREAD_STATUSES)}"
        )
    _require_string_list(run["routing_violations"], f"{location}.routing_violations")

    threads = run["threads"]
    if not isinstance(threads, list) or not threads:
        raise EvaluationError(f"{location}.threads must be a non-empty list")
    attempts_by_thread: dict[str, list[tuple[int, str]]] = {}
    kind_by_thread: dict[str, str] = {}
    role_by_thread: dict[str, str] = {}
    parent_by_thread: dict[str, str | None] = {}
    seen_attempts = set()
    for index, thread in enumerate(threads):
        thread_location = f"{location}.threads[{index}]"
        thread = _require_exact_keys(thread, THREAD_KEYS, thread_location)
        for key in ("thread_id", "role", "model", "effort", "service_tier"):
            _require_string(thread[key], f"{thread_location}.{key}")
        kind = _require_string(thread["kind"], f"{thread_location}.kind")
        if kind not in THREAD_KINDS:
            raise EvaluationError(
                f"{thread_location}.kind must be one of {sorted(THREAD_KINDS)}"
            )
        status = _require_string(thread["status"], f"{thread_location}.status")
        if status not in THREAD_STATUSES:
            raise EvaluationError(
                f"{thread_location}.status must be one of {sorted(THREAD_STATUSES)}"
            )
        attempt = _require_positive_integer(
            thread["attempt"], f"{thread_location}.attempt"
        )
        _require_boolean(thread["terminal"], f"{thread_location}.terminal")
        if not thread["terminal"]:
            raise EvaluationError(f"{thread_location} is nonterminal")
        _require_boolean(thread["cost_complete"], f"{thread_location}.cost_complete")
        if not thread["cost_complete"]:
            raise EvaluationError(f"{thread_location} has incomplete cost evidence")
        parent_thread_id = thread["parent_thread_id"]
        if parent_thread_id is not None:
            _require_string(parent_thread_id, f"{thread_location}.parent_thread_id")
        attempt_key = (thread["thread_id"], attempt)
        if attempt_key in seen_attempts:
            raise EvaluationError(
                f"{location} has duplicate thread attempt: "
                f"{thread['thread_id']}#{attempt}"
            )
        seen_attempts.add(attempt_key)
        prior_kind = kind_by_thread.setdefault(thread["thread_id"], kind)
        if prior_kind != kind:
            raise EvaluationError(
                f"{location} thread {thread['thread_id']!r} changes kind"
            )
        prior_role = role_by_thread.setdefault(thread["thread_id"], thread["role"])
        if prior_role != thread["role"]:
            raise EvaluationError(
                f"{location} thread {thread['thread_id']!r} changes role"
            )
        if thread["thread_id"] not in parent_by_thread:
            parent_by_thread[thread["thread_id"]] = parent_thread_id
        elif parent_by_thread[thread["thread_id"]] != parent_thread_id:
            raise EvaluationError(
                f"{location} thread {thread['thread_id']!r} changes parent"
            )
        attempts_by_thread.setdefault(thread["thread_id"], []).append(
            (attempt, status)
        )
        if thread["service_tier"] != "default":
            raise EvaluationError(f"{thread_location}.service_tier must be 'default'")
        tokens = _require_exact_keys(
            thread["tokens"], TOKEN_KEYS, f"{thread_location}.tokens"
        )
        for key, value in tokens.items():
            _require_integer(value, f"{thread_location}.tokens.{key}")
        if (
            tokens["cached_input_tokens"] + tokens["cache_write_input_tokens"]
            > tokens["input_tokens"]
        ):
            raise EvaluationError(
                f"{thread_location}.tokens cached plus cache-write exceeds input"
            )
        if tokens["reasoning_output_tokens"] > tokens["output_tokens"]:
            raise EvaluationError(
                f"{thread_location}.tokens reasoning output exceeds output"
            )
        if tokens["total_tokens"] != tokens["input_tokens"] + tokens["output_tokens"]:
            raise EvaluationError(
                f"{thread_location}.tokens total must equal input plus output"
            )
        credits = _require_exact_keys(
            thread["credits"], CREDIT_KEYS, f"{thread_location}.credits"
        )
        parsed_credits = {
            key: _require_decimal(value, f"{thread_location}.credits.{key}")
            for key, value in credits.items()
        }
        if parsed_credits["total"] != sum(
            (parsed_credits[key] for key in CREDIT_CATEGORY_KEYS), Decimal(0)
        ):
            raise EvaluationError(
                f"{thread_location}.credits total does not match category sum"
            )

    for thread_id, attempts in attempts_by_thread.items():
        ordered = sorted(attempts)
        attempt_numbers = [attempt for attempt, _ in ordered]
        expected_attempts = list(range(1, len(ordered) + 1))
        if attempt_numbers != expected_attempts:
            raise EvaluationError(
                f"{location} thread {thread_id!r} attempts must be contiguous from 1"
            )
        if any(status != "failed" for _, status in ordered[:-1]):
            raise EvaluationError(
                f"{location} thread {thread_id!r} can retry only a failed attempt"
            )

    for key in ("wall_time_ms", "child_count", "retries"):
        _require_integer(run[key], f"{location}.{key}")
    recorded_child_count = sum(
        1 for kind in kind_by_thread.values() if kind == "child"
    )
    if run["child_count"] != recorded_child_count:
        raise EvaluationError(
            f"{location}.child_count={run['child_count']} does not match "
            f"{recorded_child_count} recorded child threads"
        )
    recorded_retries = sum(len(attempts) - 1 for attempts in attempts_by_thread.values())
    if run["retries"] != recorded_retries:
        raise EvaluationError(
            f"{location}.retries={run['retries']} does not match "
            f"{recorded_retries} recorded retry attempts"
        )
    if "primary" not in kind_by_thread.values():
        raise EvaluationError(f"{location}.threads must record at least one primary thread")

    actual_thread_ids = sorted(kind_by_thread)
    if sorted(expected_thread_ids) != actual_thread_ids:
        raise EvaluationError(
            f"{location}.expected_thread_ids do not match recorded logical threads"
        )
    receiver_ids = sorted(
        thread_id for thread_id, kind in kind_by_thread.items() if kind == "child"
    )
    if sorted(expected_receiver_ids) != receiver_ids:
        raise EvaluationError(
            f"{location}.expected_receiver_ids do not match recorded child threads"
        )

    primary_ids = {
        thread_id for thread_id, kind in kind_by_thread.items() if kind == "primary"
    }
    for thread_id, kind in kind_by_thread.items():
        parent = parent_by_thread[thread_id]
        role = role_by_thread[thread_id]
        if kind == "primary":
            if parent is not None or role != "primary":
                raise EvaluationError(
                    f"{location} primary thread {thread_id!r} must have null parent and primary role"
                )
        elif parent not in primary_ids:
            raise EvaluationError(
                f"{location} child thread {thread_id!r} has recursive or unknown parent"
            )

    receiver_roles = sorted(role_by_thread[thread_id] for thread_id in receiver_ids)
    if arm == "custom" and receiver_roles != sorted(expected_roles):
        raise EvaluationError(f"{location} custom receiver role mismatch")
    if arm == "baseline" and any(
        role not in allowed_baseline_roles for role in receiver_roles
    ):
        raise EvaluationError(f"{location} baseline receiver role is not allowed")
    _require_sha256(run["grader_sha256"], f"{location}.grader_sha256")

    checks = run["quality_checks"]
    if not isinstance(checks, list) or not checks:
        raise EvaluationError(f"{location}.quality_checks must be a non-empty list")
    check_ids = set()
    for index, check in enumerate(checks):
        check_location = f"{location}.quality_checks[{index}]"
        check = _require_exact_keys(check, CHECK_KEYS, check_location)
        check_id = _require_string(check["id"], f"{check_location}.id")
        if check_id in check_ids:
            raise EvaluationError(f"{location} has duplicate quality check id: {check_id}")
        check_ids.add(check_id)
        _require_boolean(check["passed"], f"{check_location}.passed")
        _require_boolean(check["critical"], f"{check_location}.critical")
        score = _require_integer(check["score"], f"{check_location}.score")
        maximum = _require_integer(check["max_score"], f"{check_location}.max_score")
        if maximum == 0 or score > maximum:
            raise EvaluationError(f"{check_location} requires 0 <= score <= max_score > 0")

    violations = run["scope_violations"]
    if not isinstance(violations, list) or any(
        not isinstance(item, str) or not item.strip() for item in violations
    ):
        raise EvaluationError(f"{location}.scope_violations must be a string list")

    audit = _require_exact_keys(
        run["contamination_audit"], AUDIT_KEYS, f"{location}.contamination_audit"
    )
    _require_boolean(audit["passed"], f"{location}.contamination_audit.passed")
    if not isinstance(audit["notes"], str):
        raise EvaluationError(f"{location}.contamination_audit.notes must be a string")


def _validate_instance(
    instance: object,
    location: str,
    sealed: bool,
    *,
    allowed_baseline_roles: list[str],
    expected_grader_sha256: str,
) -> str:
    instance = _require_exact_keys(instance, INSTANCE_KEYS, location)
    instance_id = _require_string(instance["instance_id"], f"{location}.instance_id")
    for key in ("task_class", "fixture_family", "scenario"):
        _require_string(instance[key], f"{location}.{key}")
    expected_roles = _require_string_list(
        instance["expected_roles"], f"{location}.expected_roles"
    )
    holdout = _require_boolean(instance["holdout"], f"{location}.holdout")
    if holdout is not sealed:
        expected = "true" if sealed else "false"
        raise EvaluationError(f"{location}.holdout must be {expected} in this input")
    if instance["arm_order"] not in (["baseline", "custom"], ["custom", "baseline"]):
        raise EvaluationError(f"{location}.arm_order must contain baseline and custom once")
    runs = _require_exact_keys(instance["runs"], ARMS, f"{location}.runs")
    for arm in sorted(ARMS):
        _validate_run(
            runs[arm],
            f"{location}.runs.{arm}",
            arm=arm,
            expected_roles=expected_roles,
            allowed_baseline_roles=allowed_baseline_roles,
        )
    if runs["baseline"]["grader_sha256"] != runs["custom"]["grader_sha256"]:
        raise EvaluationError(f"{location} paired grader_sha256 mismatch")
    if any(
        runs[arm]["grader_sha256"] != expected_grader_sha256 for arm in sorted(ARMS)
    ):
        raise EvaluationError(f"{location} run grader does not match frozen grader")
    rubric_signatures = {
        arm: sorted(
            (check["id"], check["critical"], check["max_score"])
            for check in runs[arm]["quality_checks"]
        )
        for arm in sorted(ARMS)
    }
    if rubric_signatures["baseline"] != rubric_signatures["custom"]:
        raise EvaluationError(
            f"{location} paired rubric mismatch; expected identical "
            "(id, critical, max_score) signatures"
        )
    return instance_id


def validate_campaign(document: dict, *, sealed_holdout: bool = False) -> None:
    expected_keys = HOLDOUT_KEYS if sealed_holdout else CAMPAIGN_KEYS
    label = "sealed holdout" if sealed_holdout else "campaign"
    document = _require_exact_keys(document, expected_keys, label)
    if document["schema_version"] != SCHEMA_VERSION or isinstance(
        document["schema_version"], bool
    ):
        raise EvaluationError(f"{label}.schema_version must be {SCHEMA_VERSION}")
    _require_string(document["campaign_id"], f"{label}.campaign_id")
    allowed_baseline_roles = _require_string_list(
        document["allowed_baseline_roles"], f"{label}.allowed_baseline_roles"
    )

    if not sealed_holdout:
        hashes = _require_exact_keys(
            document["configuration_hashes"],
            CONFIGURATION_HASH_KEYS,
            "campaign.configuration_hashes",
        )
        for key, value in hashes.items():
            _require_sha256(value, f"campaign.configuration_hashes.{key}")
        expected_grader_sha256 = hashes["graders"]
        policies = document["class_policies"]
        if not isinstance(policies, dict) or not policies:
            raise EvaluationError("campaign.class_policies must be a non-empty object")
        for task_class, policy in policies.items():
            _require_string(task_class, "campaign.class_policies key")
            if not isinstance(policy, dict):
                raise EvaluationError(
                    f"campaign.class_policies.{task_class} must be an object"
                )
            mode = policy.get("decision_mode")
            if mode == "elective":
                policy = _require_exact_keys(
                    policy,
                    ELECTIVE_POLICY_KEYS,
                    f"campaign.class_policies.{task_class}",
                )
            elif mode == "mandatory_named_gate":
                policy = _require_exact_keys(
                    policy,
                    MANDATORY_POLICY_KEYS,
                    f"campaign.class_policies.{task_class}",
                )
                if policy["higher_level_required"] is not True:
                    raise EvaluationError(
                        f"campaign.class_policies.{task_class}.higher_level_required must be true"
                    )
                if policy["callable_builtin_equivalent"] is not False:
                    raise EvaluationError(
                        f"campaign.class_policies.{task_class}.callable_builtin_equivalent must be false"
                    )
                _require_string(
                    policy["availability_probe_reference"],
                    f"campaign.class_policies.{task_class}.availability_probe_reference",
                )
                _require_sha256(
                    policy["availability_probe_sha256"],
                    f"campaign.class_policies.{task_class}.availability_probe_sha256",
                )
                if policy["restored_after_probe"] is not True:
                    raise EvaluationError(
                        f"campaign.class_policies.{task_class}.restored_after_probe must be true"
                    )
            else:
                raise EvaluationError(
                    f"campaign.class_policies.{task_class}.decision_mode is invalid"
                )
            _require_string(
                policy["custom_role"],
                f"campaign.class_policies.{task_class}.custom_role",
            )
    else:
        seal = _require_exact_keys(document["seal"], SEAL_KEYS, "sealed holdout.seal")
        _require_string(seal["seal_id"], "sealed holdout.seal.seal_id")
        for key in (
            "receipt_sha256",
            "runner_sha256",
            "harness_sha256",
            "grader_sha256",
            "expected_answers_sha256",
            "fixtures_sha256",
            "prompts_sha256",
            "live_configuration_sha256",
        ):
            _require_sha256(seal[key], f"sealed holdout.seal.{key}")
        expected_grader_sha256 = seal["grader_sha256"]
        for key in (
            "agent_visibility_boundary_enforced",
            "runner_unlinked_before_agents",
        ):
            if seal[key] is not True:
                raise EvaluationError(f"sealed holdout.seal.{key} must be true")
        completion = _require_exact_keys(
            document["completion"], COMPLETION_KEYS, "sealed holdout.completion"
        )
        for key in ("receipt_sha256", "results_sha256", "archive_sha256"):
            _require_sha256(completion[key], f"sealed holdout.completion.{key}")
        for key in (
            "all_tested_threads_terminal_before_archive",
            "all_records_valid",
            "all_contamination_audits_clean",
        ):
            if completion[key] is not True:
                raise EvaluationError(f"sealed holdout.completion.{key} must be true")
        if completion["archive_sha256"] != seal["runner_sha256"]:
            raise EvaluationError(
                "sealed holdout runner archive hash does not match sealed runner hash"
            )
        if completion["receipt_sha256"] != seal["receipt_sha256"]:
            raise EvaluationError(
                "sealed holdout completion receipt hash does not match sealed receipt hash"
            )

    instances = document["instances"]
    if not isinstance(instances, list) or not instances:
        raise EvaluationError(f"{label}.instances must be a non-empty list")
    seen = set()
    for index, instance in enumerate(instances):
        instance_id = _validate_instance(
            instance,
            f"{label}.instances[{index}]",
            sealed=sealed_holdout,
            allowed_baseline_roles=allowed_baseline_roles,
            expected_grader_sha256=expected_grader_sha256,
        )
        if instance_id in seen:
            raise EvaluationError(f"duplicate instance_id in {label}: {instance_id}")
        seen.add(instance_id)

    execution_order = document["execution_order"]
    if not isinstance(execution_order, list):
        raise EvaluationError(f"{label}.execution_order must be a list")
    observed_order: dict[str, list[str]] = {instance_id: [] for instance_id in seen}
    observed_pairs = set()
    for index, entry in enumerate(execution_order):
        entry = _require_exact_keys(
            entry, EXECUTION_ENTRY_KEYS, f"{label}.execution_order[{index}]"
        )
        instance_id = _require_string(
            entry["instance_id"], f"{label}.execution_order[{index}].instance_id"
        )
        if instance_id not in observed_order or entry["arm"] not in ARMS:
            raise EvaluationError(f"{label}.execution_order[{index}] is unknown")
        pair = (instance_id, entry["arm"])
        if pair in observed_pairs:
            raise EvaluationError(f"{label}.execution_order has duplicate pair {pair}")
        observed_pairs.add(pair)
        observed_order[instance_id].append(entry["arm"])
    instance_by_id = {item["instance_id"]: item for item in instances}
    for instance_id, arms in observed_order.items():
        if arms != instance_by_id[instance_id]["arm_order"]:
            raise EvaluationError(
                f"{label}.execution_order drifts from {instance_id} arm_order"
            )
    observed_execution = sorted(
        (
            item["runs"][arm]["execution_index"],
            {"instance_id": item["instance_id"], "arm": arm},
        )
        for item in instances
        for arm in sorted(ARMS)
    )
    indexes = [index for index, _ in observed_execution]
    if indexes != list(range(len(observed_execution))):
        raise EvaluationError(f"{label} run execution_index values must be unique and contiguous")
    if [entry for _, entry in observed_execution] != execution_order:
        raise EvaluationError(f"{label}.execution_order drifts from recorded run indexes")

    if not sealed_holdout:
        task_classes = {item["task_class"] for item in instances}
        if set(document["class_policies"]) != task_classes:
            raise EvaluationError(
                "campaign.class_policies keys must exactly match instance task classes"
            )
        custom_roles = {
            policy["custom_role"] for policy in document["class_policies"].values()
        }
        overlap = custom_roles.intersection(allowed_baseline_roles)
        if overlap:
            raise EvaluationError(
                f"campaign allowed_baseline_roles overlap custom roles: {sorted(overlap)}"
            )
        for instance in instances:
            policy_role = document["class_policies"][instance["task_class"]][
                "custom_role"
            ]
            if instance["expected_roles"] != [policy_role]:
                raise EvaluationError(
                    f"{instance['instance_id']} expected_roles must exactly equal its class policy role"
                )


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _median(values: Iterable[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)


def _run_summary(run: dict) -> dict:
    checks = run["quality_checks"]
    credits = sum(
        (_require_decimal(thread["credits"]["total"], "credit") for thread in run["threads"]),
        Decimal(0),
    )
    tokens = {
        key: sum(thread["tokens"][key] for thread in run["threads"])
        for key in sorted(TOKEN_KEYS)
    }
    return {
        "all_checks_passed": all(check["passed"] for check in checks),
        "all_threads_terminal": all(thread["terminal"] for thread in run["threads"]),
        "child_count": run["child_count"],
        "completion_status": run["completion_status"],
        "contamination_audit": dict(sorted(run["contamination_audit"].items())),
        "contamination_audit_passed": run["contamination_audit"]["passed"],
        "cost_complete": all(thread["cost_complete"] for thread in run["threads"]),
        "critical_failures": sum(
            1 for check in checks if check["critical"] and not check["passed"]
        ),
        "grader_sha256": run["grader_sha256"],
        "expected_receiver_ids": sorted(run["expected_receiver_ids"]),
        "expected_thread_ids": sorted(run["expected_thread_ids"]),
        "execution_index": run["execution_index"],
        "measurement_complete": True,
        "process_completed": (
            run["process_exit_code"] == 0 and run["completion_status"] == "completed"
        ),
        "process_exit_code": run["process_exit_code"],
        "quality_max": sum(check["max_score"] for check in checks),
        "quality_score": sum(check["score"] for check in checks),
        "quality_checks": [
            dict(sorted(check.items()))
            for check in sorted(checks, key=lambda item: item["id"])
        ],
        "retries": run["retries"],
        "receiver_roles": sorted(
            thread["role"]
            for thread in run["threads"]
            if thread["kind"] == "child" and thread["attempt"] == 1
        ),
        "receiver_thread_ids": sorted(
            thread["thread_id"]
            for thread in run["threads"]
            if thread["kind"] == "child" and thread["attempt"] == 1
        ),
        "recursion_detected": False,
        "role_compliant": True,
        "routing_decision": run["routing_decision"],
        "routing_compliant": not run["routing_violations"],
        "routing_violations": sorted(run["routing_violations"]),
        "scope_violations": sorted(run["scope_violations"]),
        "scope_violation_count": len(run["scope_violations"]),
        "threads": [
            {
                "credits": {
                    key: _decimal_text(_require_decimal(value, "credit"))
                    for key, value in sorted(thread["credits"].items())
                },
                "attempt": thread["attempt"],
                "effort": thread["effort"],
                "kind": thread["kind"],
                "model": thread["model"],
                "parent_thread_id": thread["parent_thread_id"],
                "role": thread["role"],
                "service_tier": thread["service_tier"],
                "status": thread["status"],
                "terminal": thread["terminal"],
                "cost_complete": thread["cost_complete"],
                "thread_id": thread["thread_id"],
                "tokens": dict(sorted(thread["tokens"].items())),
            }
            for thread in sorted(
                run["threads"], key=lambda item: (item["thread_id"], item["attempt"])
            )
        ],
        "tokens": tokens,
        "total_tokens": tokens["total_tokens"],
        "total_credits": _decimal_text(credits),
        "wall_time_ms": run["wall_time_ms"],
    }


def _quality_compare(left: dict, right: dict) -> int:
    cross_left = left["quality_score"] * right["quality_max"]
    cross_right = right["quality_score"] * left["quality_max"]
    return (cross_left > cross_right) - (cross_left < cross_right)


def _class_summary(task_class: str, instances: list[dict], policy: dict) -> dict:
    arm_totals = {}
    for arm in sorted(ARMS):
        summaries = [instance["arms"][arm] for instance in instances]
        arm_totals[arm] = {
            "all_checks_passed": all(item["all_checks_passed"] for item in summaries),
            "contamination_audit_passed": all(
                item["contamination_audit_passed"] for item in summaries
            ),
            "critical_failures": sum(item["critical_failures"] for item in summaries),
            "evidence_integrity_passed": all(
                item["measurement_complete"]
                and item["role_compliant"]
                and item["routing_compliant"]
                and not item["recursion_detected"]
                and item["all_threads_terminal"]
                and item["cost_complete"]
                and item["process_completed"]
                for item in summaries
            ),
            "median_total_credits": _decimal_text(
                _median(Decimal(item["total_credits"]) for item in summaries)
            ),
            "quality_max": sum(item["quality_max"] for item in summaries),
            "quality_score": sum(item["quality_score"] for item in summaries),
            "scope_violation_count": sum(
                item["scope_violation_count"] for item in summaries
            ),
            "routing_violation_count": sum(
                len(item["routing_violations"]) for item in summaries
            ),
            "total_credits": _decimal_text(
                sum((Decimal(item["total_credits"]) for item in summaries), Decimal(0))
            ),
            "total_tokens": sum(item["total_tokens"] for item in summaries),
        }

    families = sorted({instance["fixture_family"] for instance in instances})
    sealed_count = sum(1 for instance in instances if instance["holdout"])
    arm_orders = sorted({"/".join(instance["arm_order"]) for instance in instances})
    evidence_complete = (
        len(families) >= 3 and sealed_count >= 1 and len(arm_orders) == 2
    )
    custom = arm_totals["custom"]
    baseline = arm_totals["baseline"]
    paired_integrity_passed = all(
        arm["all_checks_passed"]
        and arm["contamination_audit_passed"]
        and arm["critical_failures"] == 0
        and arm["scope_violation_count"] == 0
        and arm["routing_violation_count"] == 0
        and arm["evidence_integrity_passed"]
        for arm in (baseline, custom)
    )
    quality = _quality_compare(custom, baseline)
    baseline_median = Decimal(baseline["median_total_credits"])
    custom_median = Decimal(custom["median_total_credits"])
    credit_threshold_met = baseline_median > 0 and custom_median <= (
        baseline_median * Decimal("0.9")
    )
    if policy["decision_mode"] == "mandatory_named_gate":
        promoted = evidence_complete and paired_integrity_passed and quality >= 0
        recommendation = "mandatory-custom" if promoted else "primary-default"
    else:
        promoted = evidence_complete and paired_integrity_passed and (
            quality > 0 or (quality == 0 and credit_threshold_met)
        )
        recommendation = "custom" if promoted else "primary-default"

    reasons = []
    if not evidence_complete:
        reasons.append(
            "requires three fixture families, one sealed holdout, and both arm orders"
        )
    if not paired_integrity_passed:
        reasons.append("paired baseline/custom integrity gate failed")
    if quality < 0:
        reasons.append("custom verified quality is lower")
    elif (
        policy["decision_mode"] == "elective"
        and quality == 0
        and not credit_threshold_met
    ):
        reasons.append("indistinguishable quality without 10% median credit reduction")

    return {
        "arms": arm_totals,
        "arm_orders": arm_orders,
        "evidence_complete": evidence_complete,
        "fixture_families": families,
        "instance_count": len(instances),
        "paired_integrity_passed": paired_integrity_passed,
        "policy": dict(sorted(policy.items())),
        "decision_mode": policy["decision_mode"],
        "custom_role": policy["custom_role"],
        "recommendation": recommendation,
        "recommendation_reasons": reasons,
        "sealed_holdout_count": sealed_count,
        "task_class": task_class,
    }


def build_report(campaign: dict, sealed_holdout: dict | None = None) -> dict:
    validate_campaign(campaign)
    all_instances = list(campaign["instances"])
    if sealed_holdout is not None:
        validate_campaign(sealed_holdout, sealed_holdout=True)
        if sealed_holdout["campaign_id"] != campaign["campaign_id"]:
            raise EvaluationError("sealed holdout campaign_id does not match campaign")
        if sorted(sealed_holdout["allowed_baseline_roles"]) != sorted(
            campaign["allowed_baseline_roles"]
        ):
            raise EvaluationError("sealed holdout allowed_baseline_roles drift from campaign")
        for instance in sealed_holdout["instances"]:
            policy = campaign["class_policies"].get(instance["task_class"])
            if policy is None:
                raise EvaluationError(
                    f"sealed holdout has task class without campaign policy: {instance['task_class']}"
                )
            if instance["expected_roles"] != [policy["custom_role"]]:
                raise EvaluationError(
                    f"sealed {instance['instance_id']} expected_roles must exactly equal its class policy role"
                )
            for run in instance["runs"].values():
                if run["grader_sha256"] != sealed_holdout["seal"]["grader_sha256"]:
                    raise EvaluationError("sealed holdout run grader does not match sealed grader")
        all_instances.extend(sealed_holdout["instances"])

    ids = [instance["instance_id"] for instance in all_instances]
    if len(ids) != len(set(ids)):
        raise EvaluationError("instance_id collides across campaign and sealed holdout")

    instance_reports = []
    for instance in sorted(all_instances, key=lambda item: item["instance_id"]):
        instance_reports.append(
            {
                "arm_order": instance["arm_order"],
                "arms": {
                    arm: _run_summary(instance["runs"][arm]) for arm in sorted(ARMS)
                },
                "fixture_family": instance["fixture_family"],
                "holdout": instance["holdout"],
                "instance_id": instance["instance_id"],
                "scenario": instance["scenario"],
                "task_class": instance["task_class"],
            }
        )

    classes = []
    task_classes = sorted({instance["task_class"] for instance in instance_reports})
    unknown_classes = set(task_classes) - set(campaign["class_policies"])
    if unknown_classes:
        raise EvaluationError(
            f"sealed holdout has task classes without campaign policy: {sorted(unknown_classes)}"
        )
    for task_class in task_classes:
        selected = [
            instance for instance in instance_reports if instance["task_class"] == task_class
        ]
        classes.append(
            _class_summary(task_class, selected, campaign["class_policies"][task_class])
        )

    return {
        "campaign_id": campaign["campaign_id"],
        "configuration_hashes": dict(sorted(campaign["configuration_hashes"].items())),
        "development_execution_order": list(campaign["execution_order"]),
        "instances": instance_reports,
        "schema_version": SCHEMA_VERSION,
        "sealed_holdout_execution_order": (
            list(sealed_holdout["execution_order"])
            if sealed_holdout is not None
            else None
        ),
        "sealed_holdout_seal": (
            dict(sorted(sealed_holdout["seal"].items()))
            if sealed_holdout is not None
            else None
        ),
        "sealed_holdout_completion": (
            dict(sorted(sealed_holdout["completion"].items()))
            if sealed_holdout is not None
            else None
        ),
        "task_classes": classes,
    }


def _write_report(report: dict, output: Path | None) -> None:
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(serialized)
    else:
        output.write_text(serialized, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "report"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--campaign", type=Path, required=True)
        subparser.add_argument(
            "--sealed-holdout",
            type=Path,
            help="external post-grading sealed evidence; never passed to tested agents",
        )
        if command == "report":
            subparser.add_argument("--output", type=Path)
    subparsers.add_parser(
        "smoke",
        help="validate bundled public example evidence and deterministic reporting",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.command == "smoke":
            campaign = load_json(EXAMPLES_ROOT / "campaign.json")
            holdout = load_json(EXAMPLES_ROOT / "sealed-holdout.json")
            first = json.dumps(build_report(campaign, holdout), sort_keys=True)
            second = json.dumps(build_report(campaign, holdout), sort_keys=True)
            if first != second:
                raise EvaluationError("bundled smoke report is nondeterministic")
            print("PASS: bundled evaluation smoke evidence is valid and deterministic")
            return 0
        campaign = load_json(arguments.campaign)
        holdout = load_json(arguments.sealed_holdout) if arguments.sealed_holdout else None
        if arguments.command == "validate":
            build_report(campaign, holdout)
            print("PASS: evaluation campaign evidence is valid")
        else:
            _write_report(build_report(campaign, holdout), arguments.output)
    except EvaluationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate deterministic subagent lifecycle traces against the owned contract."""

from __future__ import annotations

import json
from pathlib import Path


ALLOWED_CANCELLATION_REASONS = {
    "user_cancel",
    "user_replace",
    "safety_scope_violation",
    "proven_stale_state",
    "terminal_platform_failure",
    "explicit_user_deadline",
}
REQUIRED_COVERAGE = {
    "authorized_cancel_acknowledged",
    "delayed_across_multiple_waits",
    "independent_peer_concurrent",
    "running_replacement_rejected",
    "terminal_collection",
    "unauthorized_cancel_rejected",
}


def active_children(states: dict[str, str]) -> list[str]:
    return [child for child, state in states.items() if state != "terminal"]


def require_running(
    errors: list[str],
    states: dict[str, str],
    child: str,
    location: str,
) -> bool:
    if states.get(child) == "running":
        return True
    errors.append(f"{location}: {child!r} must be running")
    return False


def validate_spawn(
    event: dict,
    states: dict[str, str],
    coverage: set[str],
    cap: int,
    location: str,
    errors: list[str],
) -> None:
    child = event.get("child", "")
    if not child or child in states:
        errors.append(f"{location}: spawn child must be new and non-empty")
        return
    for field in ("qualified", "required", "independent", "ownership_safe"):
        if event.get(field) is not True:
            errors.append(f"{location}: spawn requires {field}=true")
    states[child] = "running"
    active = active_children(states)
    if len(active) > cap:
        errors.append(f"{location}: logical active-child cap {cap} exceeded")
    if len(active) >= 2:
        coverage.add("independent_peer_concurrent")


def validate_cancel_request(
    event: dict,
    states: dict[str, str],
    coverage: set[str],
    location: str,
    errors: list[str],
) -> None:
    child = event.get("child", "")
    reason = event.get("reason")
    outcome = event.get("outcome")
    if not require_running(errors, states, child, location):
        return
    allowed = reason in ALLOWED_CANCELLATION_REASONS
    if allowed and outcome == "accepted":
        states[child] = "cancelling"
        return
    if not allowed and outcome == "rejected":
        coverage.add("unauthorized_cancel_rejected")
        return
    errors.append(f"{location}: cancellation reason/outcome violates authority")


def validate_replacement_request(
    event: dict,
    states: dict[str, str],
    coverage: set[str],
    location: str,
    errors: list[str],
) -> None:
    original = event.get("original", "")
    outcome = event.get("outcome")
    if states.get(original) in {"running", "cancelling"}:
        if outcome == "rejected":
            coverage.add("running_replacement_rejected")
        else:
            errors.append(f"{location}: replacement accepted while original is active")
        return
    errors.append(f"{location}: replacement check requires an active original")


def validate_scenario(
    scenario: dict,
    cap: int,
    coverage: set[str],
) -> list[str]:
    errors: list[str] = []
    states: dict[str, str] = {}
    waits: dict[str, int] = {}
    finalized = False
    name = scenario.get("name", "unnamed")
    for index, event in enumerate(scenario.get("events", [])):
        location = f"{name}[{index}]"
        kind = event.get("type")
        child = event.get("child", "")
        if finalized:
            errors.append(f"{location}: event occurs after primary_finalize")
            continue
        if kind == "spawn":
            validate_spawn(event, states, coverage, cap, location, errors)
        elif kind == "wait_timeout":
            if require_running(errors, states, child, location):
                waits[child] = waits.get(child, 0) + 1
                if waits[child] >= 2:
                    coverage.add("delayed_across_multiple_waits")
        elif kind in {"receipt", "runtime_failure"}:
            if require_running(errors, states, child, location):
                states[child] = "terminal"
        elif kind == "cancel_request":
            validate_cancel_request(event, states, coverage, location, errors)
        elif kind == "cancel_ack":
            if states.get(child) != "cancelling":
                errors.append(f"{location}: cancellation acknowledgement has no request")
            else:
                states[child] = "terminal"
                coverage.add("authorized_cancel_acknowledged")
        elif kind == "replacement_request":
            validate_replacement_request(event, states, coverage, location, errors)
        elif kind == "primary_finalize":
            active = active_children(states)
            if active:
                errors.append(f"{location}: primary finalized with active children {active}")
            else:
                coverage.add("terminal_collection")
            finalized = True
        else:
            errors.append(f"{location}: unsupported event type {kind!r}")
    if not finalized:
        errors.append(f"{name}: missing primary_finalize")
    return errors


def validate_trace_document(document: dict) -> list[str]:
    errors: list[str] = []
    coverage: set[str] = set()
    cap = document.get("logical_default_cap")
    if cap != 3:
        errors.append("logical_default_cap must be 3")
        cap = 3
    if document.get("runtime_capacity") != 16:
        errors.append("runtime_capacity must be 16")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return errors + ["scenarios must be a non-empty list"]
    for scenario in scenarios:
        errors.extend(validate_scenario(scenario, cap, coverage))
    missing = sorted(REQUIRED_COVERAGE - coverage)
    if missing:
        errors.append(f"missing lifecycle coverage: {missing}")
    return errors


def load_trace(path: Path) -> dict:
    return json.loads(path.read_text())

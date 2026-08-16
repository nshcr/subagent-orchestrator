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
ALLOWED_MESSAGE_PURPOSES = {"evidence", "dependency_status", "artifact_receipt"}
BUILTIN_LEAF_AGENT_TYPES = {"explorer", "worker"}
GOVERNED_CUSTOM_AGENT_TYPES = {
    "evidence_tester",
    "boundary_mapper",
    "risk_reviewer",
    "risk_reviewer_max",
}
PROTECTED_MESSAGE_CHANGE_FIELDS = (
    "authorization_change",
    "scope_change",
    "acceptance_change",
    "writer_ownership_change",
    "topology_change",
    "integration_change",
    "final_acceptance_change",
)
REQUIRED_COVERAGE = {
    "authorized_cancel_acknowledged",
    "bounded_nested_spawn",
    "delayed_across_multiple_waits",
    "full_tree_terminal_collection",
    "governed_leaf_recursion_rejected",
    "independent_peer_concurrent",
    "peer_message_boundary",
    "permission_inheritance",
    "running_replacement_rejected",
    "unauthorized_cancel_rejected",
}


def active_nodes(states: dict[str, str]) -> list[str]:
    return [node for node, state in states.items() if state != "terminal"]


def active_descendants(
    states: dict[str, str], parents: dict[str, str], ancestor: str
) -> list[str]:
    result = []
    for node in active_nodes(states):
        parent = parents.get(node)
        while parent and parent != "primary":
            if parent == ancestor:
                result.append(node)
                break
            parent = parents.get(parent)
    return result


def require_running(
    errors: list[str], states: dict[str, str], child: str, location: str
) -> bool:
    if states.get(child) == "running":
        return True
    errors.append(f"{location}: {child!r} must be running")
    return False


def validate_spawn(
    event: dict,
    states: dict[str, str],
    parents: dict[str, str],
    topologies: dict[str, str],
    remaining_depth: dict[str, int],
    routes: dict[str, str],
    agent_types: dict[str, str],
    coverage: set[str],
    direct_cap: int,
    descendant_cap: int,
    runtime_capacity: int,
    location: str,
    errors: list[str],
) -> None:
    child = event.get("child", "")
    parent = event.get("parent", "primary")
    route = event.get("route")
    agent_type = event.get("agent_type")
    topology = event.get("topology")
    depth = event.get("delegation_depth")
    if not child or child in states:
        errors.append(f"{location}: spawn child must be new and non-empty")
        return
    for field in ("qualified", "required", "ownership_safe"):
        if event.get(field) is not True:
            errors.append(f"{location}: spawn requires {field}=true")
    if event.get("independent") is not True and event.get("preauthorized_dependency") is not True:
        errors.append(f"{location}: spawn requires independence or a pre-authorized dependency")
    if event.get("permission_inherited") is not True:
        errors.append(f"{location}: spawn must prove permission inheritance")
    else:
        coverage.add("permission_inheritance")
    if route not in {"custom", "built-in"}:
        errors.append(f"{location}: route must be custom or built-in")
    if topology not in {"leaf", "bounded-peer"} or depth not in {0, 1}:
        errors.append(f"{location}: invalid topology or delegation depth")

    if parent == "primary":
        if route == "custom":
            if agent_type not in GOVERNED_CUSTOM_AGENT_TYPES:
                errors.append(f"{location}: unknown governed custom agent type")
            if topology != "leaf" or depth != 0:
                errors.append(f"{location}: governed custom route must remain a leaf")
        if route == "built-in" and topology == "leaf":
            if agent_type not in BUILTIN_LEAF_AGENT_TYPES:
                errors.append(f"{location}: built-in leaf agent type must be explorer or worker")
            if depth != 0:
                errors.append(f"{location}: built-in leaf must have depth zero")
        if route == "built-in" and topology == "bounded-peer":
            if agent_type != "default":
                errors.append(f"{location}: only built-in default may coordinate a bounded peer")
            if depth != 1:
                errors.append(f"{location}: bounded peer must have depth one")
        direct_active = sum(
            1 for node in active_nodes(states) if parents.get(node) == "primary"
        )
        if direct_active + 1 > direct_cap:
            errors.append(f"{location}: logical direct-child cap {direct_cap} exceeded")
        registered_peer_coordinators = sum(
            1
            for node in states
            if parents.get(node) == "primary" and topologies.get(node) == "bounded-peer"
        )
        if topology == "bounded-peer" and registered_peer_coordinators >= 1:
            errors.append(f"{location}: bounded-peer coordinator cap exceeded")
    else:
        if not require_running(errors, states, parent, location):
            return
        if topologies.get(parent) != "bounded-peer" or remaining_depth.get(parent) != 1:
            errors.append(f"{location}: only a bounded peer may spawn a descendant")
        if agent_types.get(parent) != "default":
            errors.append(f"{location}: bounded-peer parent must be built-in default")
        if (
            route != "built-in"
            or agent_type not in BUILTIN_LEAF_AGENT_TYPES
            or topology != "leaf"
            or depth != 0
        ):
            errors.append(f"{location}: bounded-peer descendants must be built-in leaves")
        direct_descendants = sum(
            1 for registered_parent in parents.values() if registered_parent == parent
        )
        if direct_descendants + 1 > descendant_cap:
            errors.append(f"{location}: bounded-peer leaf cap {descendant_cap} exceeded")
        coverage.add("bounded_nested_spawn")

    states[child] = "running"
    parents[child] = parent
    topologies[child] = topology
    remaining_depth[child] = depth
    routes[child] = route
    agent_types[child] = agent_type
    if len(active_nodes(states)) > runtime_capacity:
        errors.append(f"{location}: runtime capacity {runtime_capacity} exceeded")
    if sum(1 for node in active_nodes(states) if parents.get(node) == "primary") >= 2:
        coverage.add("independent_peer_concurrent")


def validate_message(
    event: dict,
    states: dict[str, str],
    parents: dict[str, str],
    topologies: dict[str, str],
    routes: dict[str, str],
    agent_types: dict[str, str],
    coverage: set[str],
    location: str,
    errors: list[str],
) -> None:
    sender = event.get("sender", "")
    recipient = event.get("recipient", "")
    if not require_running(errors, states, sender, location):
        return
    if not require_running(errors, states, recipient, location):
        return
    common_parent = parents.get(sender)
    if sender == recipient or common_parent != parents.get(recipient):
        errors.append(f"{location}: message endpoints must be registered peers")
    if (
        common_parent == "primary"
        or states.get(common_parent) != "running"
        or topologies.get(common_parent) != "bounded-peer"
        or agent_types.get(common_parent) != "default"
        or routes.get(sender) != "built-in"
        or routes.get(recipient) != "built-in"
        or topologies.get(sender) != "leaf"
        or topologies.get(recipient) != "leaf"
        or agent_types.get(sender) not in BUILTIN_LEAF_AGENT_TYPES
        or agent_types.get(recipient) not in BUILTIN_LEAF_AGENT_TYPES
    ):
        errors.append(f"{location}: only built-in leaves under one default bounded peer may message")
    if event.get("purpose") not in ALLOWED_MESSAGE_PURPOSES:
        errors.append(f"{location}: message purpose exceeds the evidence boundary")
    changed = [
        field for field in PROTECTED_MESSAGE_CHANGE_FIELDS if event.get(field) is not False
    ]
    if changed:
        errors.append(f"{location}: message cannot change protected handoff fields {changed}")
    coverage.add("peer_message_boundary")


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


def validate_scenario(
    scenario: dict,
    direct_cap: int,
    descendant_cap: int,
    runtime_capacity: int,
    coverage: set[str],
) -> list[str]:
    errors: list[str] = []
    states: dict[str, str] = {}
    parents: dict[str, str] = {}
    topologies: dict[str, str] = {}
    remaining_depth: dict[str, int] = {}
    routes: dict[str, str] = {}
    agent_types: dict[str, str] = {}
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
            validate_spawn(
                event,
                states,
                parents,
                topologies,
                remaining_depth,
                routes,
                agent_types,
                coverage,
                direct_cap,
                descendant_cap,
                runtime_capacity,
                location,
                errors,
            )
        elif kind == "delegation_request":
            parent = event.get("parent", "")
            if (
                require_running(errors, states, parent, location)
                and topologies.get(parent) == "leaf"
                and event.get("outcome") == "rejected"
            ):
                if routes.get(parent) == "custom":
                    coverage.add("governed_leaf_recursion_rejected")
            else:
                errors.append(f"{location}: leaf delegation request must be rejected")
        elif kind == "message":
            validate_message(
                event,
                states,
                parents,
                topologies,
                routes,
                agent_types,
                coverage,
                location,
                errors,
            )
        elif kind == "wait_timeout":
            if require_running(errors, states, child, location):
                waits[child] = waits.get(child, 0) + 1
                if waits[child] >= 2:
                    coverage.add("delayed_across_multiple_waits")
        elif kind in {"receipt", "runtime_failure"}:
            if require_running(errors, states, child, location):
                descendants = active_descendants(states, parents, child)
                if descendants:
                    errors.append(f"{location}: parent terminal before descendants {descendants}")
                else:
                    states[child] = "terminal"
        elif kind == "cancel_request":
            validate_cancel_request(event, states, coverage, location, errors)
        elif kind == "cancel_ack":
            if states.get(child) != "cancelling":
                errors.append(f"{location}: cancellation acknowledgement has no request")
            else:
                descendants = active_descendants(states, parents, child)
                if descendants:
                    errors.append(f"{location}: cancel acknowledged before descendants {descendants}")
                else:
                    states[child] = "terminal"
                    coverage.add("authorized_cancel_acknowledged")
        elif kind == "replacement_request":
            original = event.get("original", "")
            if states.get(original) in {"running", "cancelling"}:
                if event.get("outcome") == "rejected":
                    coverage.add("running_replacement_rejected")
                else:
                    errors.append(f"{location}: replacement accepted while original is active")
            else:
                errors.append(f"{location}: replacement check requires an active original")
        elif kind == "primary_finalize":
            active = active_nodes(states)
            if active:
                errors.append(f"{location}: primary finalized with active task tree {active}")
            else:
                coverage.add("full_tree_terminal_collection")
            finalized = True
        else:
            errors.append(f"{location}: unsupported event type {kind!r}")
    if not finalized:
        errors.append(f"{name}: missing primary_finalize")
    return errors


def validate_trace_document(document: dict) -> list[str]:
    errors: list[str] = []
    coverage: set[str] = set()
    direct_cap = document.get("logical_direct_child_cap")
    descendant_cap = document.get("bounded_peer_leaf_cap")
    runtime_capacity = document.get("runtime_capacity")
    if direct_cap != 3:
        errors.append("logical_direct_child_cap must be 3")
        direct_cap = 3
    if descendant_cap != 2:
        errors.append("bounded_peer_leaf_cap must be 2")
        descendant_cap = 2
    if runtime_capacity != 16:
        errors.append("runtime_capacity must be 16")
        runtime_capacity = 16
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return errors + ["scenarios must be a non-empty list"]
    for scenario in scenarios:
        errors.extend(
            validate_scenario(
                scenario, direct_cap, descendant_cap, runtime_capacity, coverage
            )
        )
    missing = sorted(REQUIRED_COVERAGE - coverage)
    if missing:
        errors.append(f"missing lifecycle coverage: {missing}")
    return errors


def load_trace(path: Path) -> dict:
    return json.loads(path.read_text())

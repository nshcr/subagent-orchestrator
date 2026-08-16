#!/usr/bin/env python3
"""Validate deterministic evidence-bus orchestration lifecycle traces."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path, PurePosixPath
import re
from datetime import datetime


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CUSTOM = {"evidence_tester", "boundary_mapper", "risk_reviewer", "risk_reviewer_max"}
REVIEWERS = {"risk_reviewer", "risk_reviewer_max"}
BUILTIN = {"explorer", "worker"}
MESSAGE_PURPOSES = {"evidence", "dependency_status", "artifact_receipt"}
FOLLOWUP_REASONS = {"new_failure_evidence", "missing_acceptance_field", "authorized_continue"}
EVIDENCE_TIERS = {"implemented", "verified-local", "verified-ci", "verified-target", "pilot", "pilot-signed"}
AUTHORITY_COLLECTIONS = {
    "materiality_receipts",
    "compaction_receipts",
    "peer_capability_receipts",
    "peer_relay_receipts",
    "message_receipts",
    "pilot_authorizations",
}


def digest(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def canonical_message_payload_digest(event: dict[str, object]) -> str:
    """Bind message semantics without creating an authority-anchor hash cycle."""
    return canonical_digest(
        {
            key: value
            for key, value in event.items()
            if key not in {"admission_anchor_digest", "digest"}
        }
    )


def safe_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def string_list(value: object, *, nonempty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (bool(value) or not nonempty)
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def readback(value: object) -> tuple[str, str, str, str] | None:
    keys = ("head", "index", "worktree", "changed_paths")
    if not isinstance(value, dict) or set(value) != set(keys):
        return None
    return tuple(value[key] for key in keys) if all(digest(value[key]) for key in keys) else None


def overlaps(left: str, right: str) -> bool:
    a, b = PurePosixPath(left).parts, PurePosixPath(right).parts
    return a[: len(b)] == b or b[: len(a)] == a


def authority_index(authority: object) -> tuple[dict[str, dict[str, dict]], set[str], list[str]]:
    """Validate host-provided receipts kept outside the trace under review.

    Receipt hashes bind canonical payloads; they are not cryptographic signatures.
    Trust comes only from the caller supplying this separate authority document.
    """
    required = {"version", "active_task_ids", *AUTHORITY_COLLECTIONS}
    if not isinstance(authority, dict) or set(authority) != required:
        return ({name: {} for name in AUTHORITY_COLLECTIONS}, set(), ["trusted authority receipts are missing or malformed"])
    errors: list[str] = []
    active_task_ids = authority.get("active_task_ids")
    valid_active_task_ids = string_list(active_task_ids, nonempty=False)
    if authority.get("version") != 1 or not valid_active_task_ids:
        errors.append("trusted authority receipt version/active-task set is invalid")
    indexed: dict[str, dict[str, dict]] = {name: {} for name in AUTHORITY_COLLECTIONS}
    for collection in AUTHORITY_COLLECTIONS:
        receipts = authority.get(collection)
        if not isinstance(receipts, list):
            errors.append(f"trusted {collection} must be a list")
            continue
        for receipt in receipts:
            if not isinstance(receipt, dict) or not digest(receipt.get("receipt_digest")):
                errors.append(f"trusted {collection} receipt schema/digest is invalid")
                continue
            projection = {key: value for key, value in receipt.items() if key != "receipt_digest"}
            if receipt["receipt_digest"] != canonical_digest(projection):
                errors.append(f"trusted {collection} receipt digest does not bind canonical payload")
            issuer = receipt.get("issuer", receipt.get("issued_by"))
            if not isinstance(issuer, str) or not issuer or issuer in {"agent", "self", "proxy"}:
                errors.append(f"trusted {collection} issuer is invalid")
            if receipt["receipt_digest"] in indexed[collection]:
                errors.append(f"trusted {collection} receipt digest is duplicated")
            indexed[collection][receipt["receipt_digest"]] = receipt
    return indexed, set(active_task_ids) if valid_active_task_ids else set(), errors


def authority_receipt(
    indexes: dict[str, dict[str, dict]],
    collection: str,
    receipt_digest: object,
    expected: dict[str, object],
) -> bool:
    if not digest(receipt_digest):
        return False
    receipt = indexes.get(collection, {}).get(receipt_digest)
    return bool(receipt and all(receipt.get(key) == value for key, value in expected.items()))


def validate_materiality(
    manifest: object,
    child: str,
    route: str,
    task_id: str,
    slice_id: str,
    anchor_digest: object,
    authority: dict[str, dict[str, dict]],
) -> list[str]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "issuer_kind", "issued_by", "task_id", "slice_id", "manifest_digest",
        "asset_kind", "source_ranges", "source_identity_digest", "source_range_count",
        "source_bytes",
    }:
        return ["materiality manifest has unknown or missing fields"]
    errors: list[str] = []
    if manifest["issuer_kind"] not in {"host", "owner", "sealed-harness"} or manifest["issued_by"] in {child, "agent", "self"}:
        errors.append("materiality manifest is self-issued")
    if not digest(manifest["manifest_digest"]):
        errors.append("materiality manifest digest is invalid")
    projection = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    if manifest["manifest_digest"] != canonical_digest(projection):
        errors.append("materiality manifest digest does not bind its canonical payload")
    if manifest["asset_kind"] != "source":
        errors.append("verification-token or synthetic asset is not material")
    ranges = manifest["source_ranges"]
    if not isinstance(ranges, list) or not ranges:
        return errors + ["materiality manifest needs canonical source ranges"]
    parsed: list[tuple[str, int, int]] = []
    contents: set[str] = set()
    paths: set[str] = set()
    total = 0
    for item in ranges:
        required = {"path", "path_sha256", "start", "end", "content_sha256", "non_padding_bytes"}
        if not isinstance(item, dict) or set(item) != required:
            errors.append("materiality source range has unknown or missing fields")
            continue
        start, end = item["start"], item["end"]
        non_padding = item["non_padding_bytes"]
        if not safe_path(item["path"]) or not digest(item["path_sha256"]) or not digest(item["content_sha256"]):
            errors.append("materiality source range identity is invalid")
            continue
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            errors.append("materiality source range bounds are invalid")
            continue
        if not isinstance(non_padding, int) or non_padding <= 0 or non_padding > end - start:
            errors.append("materiality non-padding accounting is invalid")
            continue
        if any(path == item["path"] and max(start, old_start) < min(end, old_end) for path, old_start, old_end in parsed):
            errors.append("materiality source ranges overlap")
        if item["content_sha256"] in contents:
            errors.append("duplicate content cannot inflate materiality")
        parsed.append((item["path"], start, end))
        contents.add(item["content_sha256"])
        paths.add(item["path"])
        total += non_padding
    minimum_bytes, minimum_paths = ((4096, 2) if route == "explorer" else (8192, 3))
    if total < minimum_bytes or len(paths) < minimum_paths:
        errors.append(f"{route} materiality predicate failed")
    if (
        manifest.get("task_id") != task_id
        or manifest.get("slice_id") != slice_id
        or manifest.get("source_identity_digest") != canonical_digest(ranges)
        or manifest.get("source_range_count") != len(ranges)
        or manifest.get("source_bytes") != total
    ):
        errors.append("materiality receipt does not bind task/slice/canonical source identity and bytes")
    expected = {
        "issuer_kind": manifest.get("issuer_kind"),
        "issuer": manifest.get("issued_by"),
        "task_id": task_id,
        "slice_id": slice_id,
        "child": child,
        "manifest_digest": manifest.get("manifest_digest"),
        "source_identity_digest": manifest.get("source_identity_digest"),
        "source_range_count": manifest.get("source_range_count"),
        "source_bytes": manifest.get("source_bytes"),
    }
    if not authority_receipt(authority, "materiality_receipts", anchor_digest, expected):
        errors.append("materiality issuer/payload is not admitted by trusted authority")
    return errors


def validate_transfer(value: object, task_id: str, slice_id: str, child: str, route: str, topology: str, parent: str) -> list[str]:
    required = {
        "producer", "consumer", "task_id", "slice_id", "route", "topology",
        "input_summary", "sampling_allowlist", "admitted_state_digest", "status",
        "artifact_receipt_digest", "admitted_receipt_digests", "completion_conditions", "forbidden_actions",
    }
    if not isinstance(value, dict) or set(value) != required:
        return ["work-transfer has unknown or missing fields"]
    errors: list[str] = []
    admitted_producers = {"primary", "host", "owner"} if parent == "primary" else {parent}
    if value["producer"] not in admitted_producers or value["consumer"] != child or value["task_id"] != task_id or value["slice_id"] != slice_id:
        errors.append("work-transfer identity is invalid")
    if value["topology"] not in {"leaf", "bounded-peer"} or not digest(value["admitted_state_digest"]):
        errors.append("work-transfer topology/state is invalid")
    projection = {key: item for key, item in value.items() if key != "admitted_state_digest"}
    if value["admitted_state_digest"] != canonical_digest(projection):
        errors.append("work-transfer admitted-state digest does not bind canonical payload")
    if value["route"] != route or value["topology"] != topology:
        errors.append("work-transfer route/topology is not bound to spawn")
    if value["status"] != "admitted" or value["artifact_receipt_digest"] is not None:
        errors.append("new work-transfer status is invalid")
    for key in ("input_summary", "sampling_allowlist", "completion_conditions", "forbidden_actions"):
        if not isinstance(value[key], list) or not value[key]:
            errors.append(f"work-transfer {key} must be non-empty")
    if not string_list(value["admitted_receipt_digests"], nonempty=False) or not all(digest(item) for item in value["admitted_receipt_digests"]):
        errors.append("work-transfer admitted receipt digests are invalid")
    return errors


def validate_scenario(
    scenario: object,
    authority: dict[str, dict[str, dict]],
    active_task_ids: set[str],
) -> list[str]:
    if not isinstance(scenario, dict) or set(scenario) != {"name", "task_id", "declared_evidence_tier", "events"}:
        return ["scenario has unknown or missing fields"]
    errors: list[str] = []
    raw_task_id = scenario["task_id"]
    task_id = raw_task_id if isinstance(raw_task_id, str) and raw_task_id else "<invalid-task-id>"
    if task_id != raw_task_id:
        errors.append("scenario task_id must be a non-empty string")
    declared_evidence_tier = scenario.get("declared_evidence_tier")
    if not isinstance(declared_evidence_tier, str) or declared_evidence_tier not in EVIDENCE_TIERS:
        errors.append("scenario declared evidence tier is invalid")
    slices: dict[str, dict] = {}
    nodes: dict[str, dict] = {}
    parents: dict[str, str] = {}
    components: dict[str, str] = {}
    component_paths: dict[str, set[str]] = {}
    compactions: dict[str, int] = {}
    gates: dict[str, dict] = {}
    invariant_owner: dict[str, str] = {}
    material_ranges: list[tuple[str, int, int]] = []
    material_contents: set[str] = set()
    material_bytes = 0
    sampled_ranges = 0
    sampled_bytes = 0
    access_denominator: tuple[int, int] | None = None
    writer_slices: set[str] = set()
    frozen: tuple[str, str, str, str] | None = None
    generation = 0
    closed = False
    spawn_seen = False
    artifact_receipts_by_child: dict[str, set[str]] = {}
    peer_relay_used: set[str] = set()
    pilot_seen = False
    pilot_generation: int | None = None

    def component_root(value: str) -> str:
        while components.get(value, value) != value:
            value = components[value]
        return value

    def union_components(left: str, right: str) -> str:
        left_root, right_root = component_root(left), component_root(right)
        if left_root == right_root:
            return right_root
        components[left_root] = right_root
        component_paths.setdefault(right_root, set()).update(component_paths.pop(left_root, set()))
        compactions[right_root] = compactions.get(right_root, 0) + compactions.pop(left_root, 0)
        return right_root

    def invalidate(candidate: tuple[str, str, str, str] | None) -> None:
        nonlocal frozen, generation
        frozen = candidate
        generation += 1
        for gate in gates.values():
            gate["passed"] = False

    events = scenario["events"] if isinstance(scenario["events"], list) else []
    for index, event in enumerate(events):
        location = f"{scenario['name']}[{index}]"
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            errors.append(f"{location}: malformed event")
            continue
        kind = event["type"]
        if closed:
            errors.append(f"{location}: event after close")
            continue

        if kind == "slice_open":
            required = {"type", "task_id", "slice_id", "acceptance_milestone", "change_class", "owner_paths", "required_gate_ids", "state_summary", "state_digest"}
            if set(event) != required or event["task_id"] != task_id:
                errors.append(f"{location}: slice_open schema/identity mismatch")
                continue
            slice_id, paths = event["slice_id"], event["owner_paths"]
            if not isinstance(slice_id, str) or not slice_id or slice_id in slices:
                errors.append(f"{location}: slice id must be unique")
            if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)) or not all(safe_path(path) for path in paths):
                errors.append(f"{location}: precise owner paths required")
            if not isinstance(event["acceptance_milestone"], str) or not event["acceptance_milestone"] or not isinstance(event["change_class"], str) or not event["change_class"]:
                errors.append(f"{location}: exactly one milestone and change class required")
            if not string_list(event["required_gate_ids"]) or not string_list(event["state_summary"]) or not digest(event["state_digest"]):
                errors.append(f"{location}: slice gates/state summary invalid")
            if not string_list(event["required_gate_ids"]) or len(event["required_gate_ids"]) != 3 or (string_list(event["required_gate_ids"]) and len(set(event["required_gate_ids"])) != 3):
                errors.append(f"{location}: slice requires exactly three unique gates")
            projection = {key: value for key, value in event.items() if key not in {"type", "state_digest"}}
            if event["state_digest"] != canonical_digest(projection):
                errors.append(f"{location}: slice state digest does not bind canonical payload")
            slices[slice_id] = event

        elif kind == "owner_union":
            required = {"type", "component", "paths", "reason", "aliases"}
            if set(event) != required or not isinstance(event["reason"], str) or event["reason"] not in {"overlap", "rename", "split", "merge"}:
                errors.append(f"{location}: owner union schema invalid")
                continue
            component = event["component"]
            if not isinstance(component, str) or not component or not isinstance(event["paths"], list) or not event["paths"] or not all(safe_path(path) for path in event["paths"]):
                errors.append(f"{location}: owner union paths invalid")
                continue
            components.setdefault(component, component)
            component_paths.setdefault(component_root(component), set()).update(event["paths"])
            aliases = event["aliases"]
            if not string_list(aliases, nonempty=False):
                errors.append(f"{location}: owner aliases must be strings")
                aliases = []
            for alias in aliases:
                components.setdefault(alias, alias)
                union_components(alias, component)

        elif kind == "spawn":
            required = {
                "type", "child", "parent", "slice_id", "agent_type", "route", "topology",
                "delegation_depth", "fork_context", "owner_component", "owner_paths",
                "work_transfer", "materiality_manifest", "authority_receipts",
            }
            if set(event) != required:
                errors.append(f"{location}: spawn schema invalid")
                continue
            child, parent, agent_type = event["child"], event["parent"], event["agent_type"]
            if not isinstance(child, str) or not child or child in nodes or not isinstance(event["slice_id"], str) or event["slice_id"] not in slices:
                errors.append(f"{location}: spawn identity invalid")
                continue
            if not isinstance(parent, str) or not parent:
                errors.append(f"{location}: spawn parent identity invalid")
                continue
            if event["fork_context"] != "none":
                errors.append(f"{location}: full-history context is never eligible")
            topology, depth = event["topology"], event["delegation_depth"]
            authority_refs = event.get("authority_receipts")
            authority_keys = {"materiality", "compaction_baseline", "peer_capability", "peer_relay"}
            if not isinstance(authority_refs, dict) or set(authority_refs) != authority_keys:
                errors.append(f"{location}: spawn authority receipt references are invalid")
                authority_refs = {key: None for key in authority_keys}
            known_agent = isinstance(agent_type, str) and agent_type in (CUSTOM | BUILTIN | {"default"})
            if not known_agent:
                errors.append(f"{location}: unknown or unregistered agent type")
            if isinstance(agent_type, str) and agent_type in CUSTOM and (event["route"] != "custom" or topology != "leaf" or depth != 0 or parent != "primary"):
                errors.append(f"{location}: custom roles remain primary-routed nonrecursive leaves")
            if isinstance(agent_type, str) and agent_type in BUILTIN:
                expected_depth = 0 if parent == "primary" else 1
                if event["route"] != "built-in" or topology != "leaf" or depth != expected_depth:
                    errors.append(f"{location}: explorer/worker must be built-in leaves")
                errors.extend(
                    f"{location}: {item}"
                    for item in validate_materiality(
                        event["materiality_manifest"], child, agent_type, task_id,
                        event["slice_id"], authority_refs["materiality"], authority,
                    )
                )
                manifest = event["materiality_manifest"]
                if isinstance(manifest, dict) and isinstance(manifest.get("source_ranges"), list):
                    for item in manifest["source_ranges"]:
                        if not isinstance(item, dict) or not safe_path(item.get("path")) or not isinstance(item.get("start"), int) or not isinstance(item.get("end"), int):
                            continue
                        candidate = (item["path"], item["start"], item["end"])
                        if any(path == candidate[0] and max(candidate[1], start) < min(candidate[2], end) for path, start, end in material_ranges):
                            errors.append(f"{location}: task-wide materiality ranges overlap")
                        if item.get("content_sha256") in material_contents:
                            errors.append(f"{location}: task-wide duplicate content cannot inflate materiality")
                        material_ranges.append(candidate)
                        material_contents.add(item.get("content_sha256"))
                        if isinstance(item.get("non_padding_bytes"), int) and item["non_padding_bytes"] > 0:
                            material_bytes += item["non_padding_bytes"]
            elif event["materiality_manifest"] is not None:
                errors.append(f"{location}: materiality manifest only applies to explorer/worker")
            if agent_type == "default" and (event["route"] != "built-in" or topology != "bounded-peer" or depth != 1 or parent != "primary"):
                errors.append(f"{location}: default bounded peer depth must be one")
            if agent_type == "default":
                capability_expected = {
                    "task_id": task_id,
                    "slice_id": event["slice_id"],
                    "peer": child,
                    "capability": "bounded-peer-relay",
                }
                relay_expected = {
                    "task_id": task_id,
                    "slice_id": event["slice_id"],
                    "peer": child,
                    "removed_primary_relay": True,
                }
                if not authority_receipt(authority, "peer_capability_receipts", authority_refs["peer_capability"], capability_expected):
                    errors.append(f"{location}: default peer capability is not admitted by trusted authority")
                if not authority_receipt(authority, "peer_relay_receipts", authority_refs["peer_relay"], relay_expected):
                    errors.append(f"{location}: default peer material relay is not admitted by trusted authority")
            if parent != "primary":
                owner = nodes.get(parent)
                descendants = sum(1 for value in parents.values() if value == parent)
                if not owner or owner["state"] != "running" or owner["agent_type"] != "default" or agent_type not in BUILTIN or descendants >= 2:
                    errors.append(f"{location}: invalid bounded-peer descendant")
            else:
                direct_active = sum(
                    1 for name, node in nodes.items()
                    if parents.get(name) == "primary" and node["state"] == "running"
                )
                if direct_active >= 3:
                    errors.append(f"{location}: direct-child cap exceeded")
                if agent_type == "default" and any(
                    node["agent_type"] == "default" for node in nodes.values()
                ):
                    errors.append(f"{location}: bounded-peer coordinator cap exceeded")
            errors.extend(f"{location}: {item}" for item in validate_transfer(event["work_transfer"], task_id, event["slice_id"], child, agent_type, topology, parent))
            raw_component = event["owner_component"]
            component = component_root(raw_component) if isinstance(raw_component, str) and raw_component else ""
            paths = event["owner_paths"]
            valid_paths = isinstance(paths, list) and bool(paths) and all(safe_path(path) for path in paths)
            if agent_type == "worker" and not valid_paths:
                errors.append(f"{location}: writer ownership invalid")
                paths = []
            if agent_type == "worker":
                if event["slice_id"] in writer_slices:
                    errors.append(f"{location}: each slice permits at most one writer")
                writer_slices.add(event["slice_id"])
                if not isinstance(raw_component, str) or not raw_component:
                    errors.append(f"{location}: writer canonical owner component is required")
                components.setdefault(component, component)
                for registered, registered_paths in list(component_paths.items()):
                    if any(overlaps(left, right) for left in paths for right in registered_paths):
                        component = union_components(component, registered)
                component = component_root(component)
                component_paths.setdefault(component, set()).update(paths)
                baseline_digest = authority_refs["compaction_baseline"]
                baseline = authority.get("compaction_receipts", {}).get(baseline_digest) if digest(baseline_digest) else None
                baseline_expected = {
                    "task_id": task_id,
                    "slice_id": event["slice_id"],
                    "child": child,
                    "owner_component": component,
                    "current_count": 0,
                }
                if not baseline or not all(baseline.get(key) == value for key, value in baseline_expected.items()):
                    errors.append(f"{location}: writer compaction baseline is not admitted by trusted authority")
                    baseline_count = 2
                else:
                    baseline_count = baseline.get("cumulative_count")
                    if not isinstance(baseline_count, int) or baseline_count < 0:
                        errors.append(f"{location}: trusted writer compaction baseline is invalid")
                        baseline_count = 2
                compactions[component] = max(compactions.get(component, 0), baseline_count)
                if compactions.get(component, 0) >= 2:
                    errors.append(f"{location}: writer compaction budget exhausted")
                for other in nodes.values():
                    if other["state"] == "running" and other["agent_type"] == "worker" and any(overlaps(a, b) for a in paths for b in other["paths"]):
                        errors.append(f"{location}: overlapping writer ownership")
            if agent_type in {"evidence_tester", *REVIEWERS} and frozen is None:
                errors.append(f"{location}: tester/reviewer requires writer-terminal freeze")
            nodes[child] = {
                "state": "running", "agent_type": agent_type if isinstance(agent_type, str) else "<invalid>",
                "slice": event["slice_id"], "component": component, "paths": paths,
                "scope_digest": event["work_transfer"].get("admitted_state_digest") if isinstance(event["work_transfer"], dict) else None,
                "admitted_receipts": set(event["work_transfer"].get("admitted_receipt_digests", [])) if isinstance(event["work_transfer"], dict) else set(),
                "compaction_receipt": authority_refs.get("compaction_baseline"),
                "peer_relay": authority_refs.get("peer_relay"),
            }
            parents[child] = parent
            spawn_seen = True

        elif kind == "receipt":
            required = {"type", "child", "status", "artifact_receipt_digest", "completion_digest", "compaction_receipt_digest", "safe_incomplete"}
            node = nodes.get(event.get("child"))
            if set(event) != required or not node or node["state"] != "running":
                errors.append(f"{location}: receipt target/schema invalid")
                continue
            if not isinstance(event["status"], str) or event["status"] not in {"complete", "incomplete", "failed"} or not digest(event["artifact_receipt_digest"]) or not digest(event["completion_digest"]):
                errors.append(f"{location}: receipt status/digest invalid")
            if event["status"] == "incomplete" and event["safe_incomplete"] is not True:
                errors.append(f"{location}: incomplete receipt must be safe")
            if node["agent_type"] == "worker":
                root = component_root(node["component"])
                compaction_digest = event.get("compaction_receipt_digest")
                trusted = authority.get("compaction_receipts", {}).get(compaction_digest) if digest(compaction_digest) else None
                expected = {
                    "task_id": task_id,
                    "slice_id": node["slice"],
                    "child": event["child"],
                    "owner_component": root,
                    "prior_receipt_digest": node.get("compaction_receipt"),
                }
                if not trusted or not all(trusted.get(key) == value for key, value in expected.items()):
                    errors.append(f"{location}: writer compaction is not admitted by trusted authority")
                else:
                    count, cumulative = trusted.get("current_count"), trusted.get("cumulative_count")
                    if not isinstance(count, int) or count < 0 or not isinstance(cumulative, int) or cumulative != compactions.get(root, 0) + count:
                        errors.append(f"{location}: trusted writer compaction cumulative count is invalid")
                    else:
                        compactions[root] = cumulative
                        node["compaction_receipt"] = event["compaction_receipt_digest"]
            elif event["compaction_receipt_digest"] is not None:
                errors.append(f"{location}: non-writer compaction receipt invalid")
            if digest(event.get("artifact_receipt_digest")):
                artifact_receipts_by_child.setdefault(event["child"], set()).add(
                    event["artifact_receipt_digest"]
                )
            node["state"] = "terminal"
            node["terminal_status"] = event["status"]

        elif kind == "freeze":
            candidate = readback(event.get("readback"))
            writers = [node for node in nodes.values() if node["slice"] == event.get("slice_id") and node["agent_type"] == "worker"]
            if set(event) != {"type", "slice_id", "readback"} or candidate is None:
                errors.append(f"{location}: freeze readback invalid")
            elif not writers or any(node["state"] != "terminal" for node in writers):
                errors.append(f"{location}: freeze requires terminal writer")
            else:
                invalidate(candidate)

        elif kind == "readback":
            candidate = readback(event.get("readback"))
            actor = nodes.get(event.get("actor"))
            if set(event) != {"type", "actor", "readback"} or not actor or actor["state"] != "running" or actor["agent_type"] not in {"evidence_tester", *REVIEWERS} or candidate != frozen:
                errors.append(f"{location}: stale filesystem readback")

        elif kind == "primary_access":
            required = {
                "type", "kind", "receipt_digest", "unique_ranges", "unique_bytes",
                "manifest_ranges", "manifest_bytes", "attribution", "consumed_receipt_digests",
            }
            if set(event) != required or not isinstance(event["kind"], str) or event["kind"] not in {"targeted_precheck", "sampling", "integration"}:
                errors.append(f"{location}: primary access not admitted")
                continue
            if event["attribution"] != "task-wide" or not digest(event["receipt_digest"]):
                errors.append(f"{location}: opaque/unavailable primary access attribution")
            projection = {key: value for key, value in event.items() if key not in {"type", "receipt_digest"}}
            if event.get("receipt_digest") != canonical_digest(projection):
                errors.append(f"{location}: primary access receipt digest does not bind canonical payload")
            if event["kind"] == "sampling" and not spawn_seen:
                errors.append(f"{location}: pre-spawn sampling cannot establish delegated substitution")
            if event["kind"] == "integration":
                counts = [event.get(key) for key in ("unique_ranges", "unique_bytes", "manifest_ranges", "manifest_bytes")]
                consumed = event.get("consumed_receipt_digests")
                if counts != [0, 0, 0, 0]:
                    errors.append(f"{location}: integration cannot replay transferred source ranges or bytes")
                terminal_artifacts = {
                    item
                    for child_artifacts in artifact_receipts_by_child.values()
                    for item in child_artifacts
                }
                if not string_list(consumed) or not all(digest(item) and item in terminal_artifacts for item in consumed):
                    errors.append(f"{location}: integration must consume admitted artifact/changed-path receipts only")
            else:
                if event.get("consumed_receipt_digests") != []:
                    errors.append(f"{location}: sampling cannot claim integration receipts")
                values = [event[key] for key in ("unique_ranges", "unique_bytes", "manifest_ranges", "manifest_bytes")]
                if not all(isinstance(value, int) and value >= 0 for value in values) or event["manifest_ranges"] <= 0 or event["manifest_bytes"] <= 0:
                    errors.append(f"{location}: primary sampling counts/denominator are invalid")
                    continue
                denominator = (event["manifest_ranges"], event["manifest_bytes"])
                if denominator != (len(material_ranges), material_bytes):
                    errors.append(f"{location}: sampling denominator differs from admitted task materiality")
                if access_denominator is None:
                    access_denominator = denominator
                elif denominator != access_denominator:
                    errors.append(f"{location}: task-wide sampling denominator changed")
                sampled_ranges += event["unique_ranges"] if isinstance(event["unique_ranges"], int) else 0
                sampled_bytes += event["unique_bytes"] if isinstance(event["unique_bytes"], int) else 0
                stable_ranges, stable_bytes = access_denominator
                if sampled_ranges >= stable_ranges or sampled_ranges * 10 > stable_ranges or sampled_bytes * 10 > stable_bytes:
                    errors.append(f"{location}: primary sampling exceeds strict 10% proper subset")

        elif kind == "send_message":
            required = {
                "type", "producer", "consumer", "task_id", "slice_id", "scope_digest",
                "dependency", "receipt_digest", "admission_anchor_digest", "digest", "purpose", "admitted",
                "starts_turn", "changes_handoff",
            }
            consumer = event.get("consumer")
            target = nodes.get(consumer) if isinstance(consumer, str) else None
            if set(event) != required or not target or target["state"] != "running":
                errors.append(f"{location}: send_message target must be running")
            if not isinstance(event.get("purpose"), str) or event.get("purpose") not in MESSAGE_PURPOSES or event.get("admitted") is not True or not digest(event.get("digest")):
                errors.append(f"{location}: send_message payload is not admitted")
            message_payload_digest = canonical_message_payload_digest(event)
            if event.get("digest") != message_payload_digest or not isinstance(event.get("dependency"), str) or not event["dependency"]:
                errors.append(f"{location}: send_message digest/dependency does not bind canonical payload")
            if event.get("starts_turn") is not False or event.get("changes_handoff") is not False:
                errors.append(f"{location}: send_message cannot start turn/change handoff")
            admitted_transfer = bool(target and (
                event.get("task_id") != task_id
                or event.get("slice_id") != target["slice"]
                or event.get("scope_digest") != target.get("scope_digest")
                or event.get("receipt_digest") not in target.get("admitted_receipts", set())
            ))
            if admitted_transfer:
                errors.append(f"{location}: send_message expands original admitted work-transfer scope")
            producer_name = event.get("producer")
            producer = nodes.get(producer_name) if isinstance(producer_name, str) else None
            admitted_peer = bool(
                producer
                and target
                and producer["state"] in {"running", "terminal"}
                and producer["agent_type"] in BUILTIN
                and target["agent_type"] in BUILTIN
                and parents.get(event["producer"]) == parents.get(event["consumer"])
                and parents.get(event["producer"]) != "primary"
                and nodes.get(parents.get(event["producer"]), {}).get("agent_type") == "default"
            )
            external_producer = producer_name in {"primary", "host", "owner"} if isinstance(producer_name, str) else False
            if target and (target["agent_type"] in CUSTOM or (not external_producer and not admitted_peer)):
                errors.append(f"{location}: custom-role or peer message is forbidden")
            if admitted_peer:
                parent = parents.get(event["producer"])
                relay_digest = nodes.get(parent, {}).get("peer_relay")
                relay = authority.get("peer_relay_receipts", {}).get(relay_digest) if digest(relay_digest) else None
                peer_purpose_valid = event.get("purpose") == "artifact_receipt"
                if not peer_purpose_valid:
                    errors.append(f"{location}: peer relay purpose must be artifact_receipt")
                producer_emitted = event.get("receipt_digest") in artifact_receipts_by_child.get(
                    event.get("producer"), set()
                )
                if not producer_emitted:
                    errors.append(f"{location}: peer relay artifact was not emitted by the named producer terminal receipt")
                expected = {
                    "task_id": task_id,
                    "slice_id": target["slice"],
                    "peer": parent,
                    "producer": event.get("producer"),
                    "consumer": event.get("consumer"),
                    "artifact_receipt_digest": event.get("receipt_digest"),
                    "consumer_scope_digest": event.get("scope_digest"),
                    "purpose": "artifact_receipt",
                    "dependency_digest": canonical_digest(event.get("dependency")),
                    "message_payload_digest": message_payload_digest,
                    "removed_primary_relay": True,
                }
                relay_admitted = bool(relay and all(relay.get(key) == value for key, value in expected.items()))
                if not relay_admitted:
                    errors.append(f"{location}: peer message lacks trusted producer-consumer relay evidence")
                anchor_matches = event.get("admission_anchor_digest") == relay_digest
                if not anchor_matches:
                    errors.append(f"{location}: peer message admission anchor does not match trusted relay")
                if (
                    relay_admitted
                    and anchor_matches
                    and peer_purpose_valid
                    and producer_emitted
                    and not admitted_transfer
                ):
                    peer_relay_used.add(parent)
            elif target:
                expected = {
                    "task_id": task_id,
                    "slice_id": target["slice"],
                    "producer": event.get("producer"),
                    "consumer": event.get("consumer"),
                    "scope_digest": target.get("scope_digest"),
                    "purpose": event.get("purpose"),
                    "payload_receipt_digest": event.get("receipt_digest"),
                    "dependency_digest": canonical_digest(event.get("dependency")),
                    "message_payload_digest": message_payload_digest,
                }
                if not authority_receipt(authority, "message_receipts", event.get("admission_anchor_digest"), expected):
                    errors.append(f"{location}: send_message receipt/scope is not admitted by trusted authority")

        elif kind == "followup_task":
            required = {"type", "target", "reason", "same_scope", "scope_digest", "authorized", "changes_scope", "status_poll"}
            target_name = event.get("target")
            target = nodes.get(target_name) if isinstance(target_name, str) else None
            if set(event) != required or not target or target["state"] == "running":
                errors.append(f"{location}: followup target must be idle/terminal")
            if not isinstance(event.get("reason"), str) or event.get("reason") not in FOLLOWUP_REASONS or event.get("same_scope") is not True or event.get("authorized") is not True or event.get("changes_scope") is not False or event.get("status_poll") is not False:
                errors.append(f"{location}: followup reason/scope invalid")
            if target and (not digest(event.get("scope_digest")) or event["scope_digest"] != target.get("scope_digest")):
                errors.append(f"{location}: followup scope digest does not match original work-transfer")
            if target and target["agent_type"] in CUSTOM:
                errors.append(f"{location}: custom/reviewer followup is forbidden")
            if target and target["agent_type"] == "worker" and compactions.get(component_root(target["component"]), 0) >= 2:
                errors.append(f"{location}: writer followup compaction budget exhausted")
            if target:
                target["state"] = "running"

        elif kind == "gate_register":
            registered = event.get("invariants")
            gate_id = event.get("gate_id")
            if set(event) != {"type", "gate_id", "invariants"} or not isinstance(gate_id, str) or not gate_id or gate_id in gates or not string_list(registered) or (string_list(registered) and len(registered) != len(set(registered))):
                errors.append(f"{location}: gate registration invalid")
                continue
            for invariant in registered:
                if invariant in invariant_owner:
                    errors.append(f"{location}: duplicate invariant ownership")
                invariant_owner[invariant] = gate_id
            gates[gate_id] = {"invariants": set(registered), "attempt": 0, "passed": False, "generation": -1}

        elif kind == "gate_result":
            gate_id, child_id = event.get("gate_id"), event.get("child")
            gate = gates.get(gate_id) if isinstance(gate_id, str) else None
            node = nodes.get(child_id) if isinstance(child_id, str) else None
            candidate = readback(event.get("readback"))
            required = {"type", "gate_id", "child", "attempt", "result", "readback", "invariants", "artifact_receipt_digest", "completion_digest"}
            if set(event) != required or not gate or not node or node["agent_type"] not in REVIEWERS or node["state"] != "running":
                errors.append(f"{location}: gate result role/state/schema invalid")
                continue
            result_invariants = event.get("invariants")
            if candidate != frozen or not isinstance(event["attempt"], int) or event["attempt"] != gate["attempt"] + 1 or not string_list(result_invariants) or (string_list(result_invariants) and set(result_invariants) != gate["invariants"]) or not isinstance(event["result"], str) or event["result"] not in {"PASS", "BLOCK"}:
                errors.append(f"{location}: stale or invalid gate attempt")
            if not digest(event.get("artifact_receipt_digest")) or not digest(event.get("completion_digest")):
                errors.append(f"{location}: gate terminal evidence digests are invalid")
            gate.update(attempt=event["attempt"], passed=event["result"] == "PASS", generation=generation)
            node["state"] = "terminal"
            node["terminal_status"] = "complete"

        elif kind == "repair":
            candidate = readback(event.get("readback"))
            if set(event) != {"type", "readback"} or candidate is None or candidate == frozen:
                errors.append(f"{location}: repair must change final hash")
            else:
                invalidate(candidate)

        elif kind == "pilot_admission":
            required = {
                "type", "receipt_digest", "authorization_event_digest", "authorization_text_digest",
                "grantor", "authorized_signer", "task_id", "slice_id", "actions", "target", "revision",
                "package_digest", "contract_digest", "valid_from", "valid_until", "observed_at",
                "excluded_active_task_ids", "issued_by", "status",
            }
            pilot_slice_id = event.get("slice_id")
            if set(event) != required or event.get("task_id") != task_id or not isinstance(pilot_slice_id, str) or pilot_slice_id not in slices:
                errors.append(f"{location}: pilot admission schema/task invalid")
            if frozen is None:
                errors.append(f"{location}: pilot admission requires a frozen final state")
            issued_by = event.get("issued_by")
            signer = event.get("authorized_signer")
            if not all(digest(event.get(key)) for key in ("receipt_digest", "authorization_event_digest", "authorization_text_digest", "package_digest", "contract_digest")) or not isinstance(issued_by, str) or not isinstance(signer, str) or issued_by in {"agent", "self", "proxy", signer} or event.get("status") != "valid":
                errors.append(f"{location}: pilot admission is self-issued/tampered/expired")
            projection = {key: value for key, value in event.items() if key not in {"type", "receipt_digest"}}
            if event.get("receipt_digest") != canonical_digest(projection):
                errors.append(f"{location}: pilot receipt digest does not bind canonical payload")
            try:
                valid_from = datetime.fromisoformat(event["valid_from"].replace("Z", "+00:00"))
                valid_until = datetime.fromisoformat(event["valid_until"].replace("Z", "+00:00"))
                observed = datetime.fromisoformat(event["observed_at"].replace("Z", "+00:00"))
                if not valid_from <= observed <= valid_until:
                    errors.append(f"{location}: pilot admission is outside its validity window")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{location}: pilot validity timestamps are invalid")
            if not all(isinstance(event.get(key), str) and event[key] for key in ("grantor", "authorized_signer", "target", "revision", "issued_by")):
                errors.append(f"{location}: pilot signer/target/revision identity is invalid")
            if not digest(event.get("revision")) or frozen is None or event.get("revision") != frozen[0]:
                errors.append(f"{location}: pilot revision does not match frozen HEAD")
            excluded = event.get("excluded_active_task_ids")
            actions = event.get("actions")
            normalized_actions = {re.sub(r"[^a-z0-9]", "", item.lower()) for item in actions} if string_list(actions) else set()
            if not string_list(excluded) or set(excluded) != active_task_ids or task_id in active_task_ids or not string_list(actions) or normalized_actions & {"createtask", "autocreatetask"}:
                errors.append(f"{location}: pilot admission exclusions/actions invalid")
            pilot_digest = event.get("receipt_digest")
            trusted = authority.get("pilot_authorizations", {}).get(pilot_digest) if digest(pilot_digest) else None
            external_projection = {key: value for key, value in event.items() if key != "type"}
            if trusted != external_projection:
                errors.append(f"{location}: pilot authorization is not admitted by trusted host authority")
            pilot_seen = True
            pilot_generation = generation

        elif kind == "close":
            candidate, required_gates = readback(event.get("readback")), event.get("required_gate_ids")
            if set(event) != {"type", "readback", "required_gate_ids"} or candidate != frozen:
                errors.append(f"{location}: close readback differs from freeze")
            if any(node["state"] != "terminal" for node in nodes.values()):
                errors.append(f"{location}: close requires terminal tree")
            if any(node.get("terminal_status") != "complete" for node in nodes.values()):
                errors.append(f"{location}: successful close requires every child complete")
            if not string_list(required_gates) or len(required_gates) != 3 or (string_list(required_gates) and len(set(required_gates)) != 3) or (string_list(required_gates) and any(gate_id not in gates or not gates[gate_id]["passed"] or gates[gate_id]["generation"] != generation for gate_id in required_gates)):
                errors.append(f"{location}: close requires all fresh required gates PASS")
            declared_values = [gate_id for item in slices.values() for gate_id in item["required_gate_ids"] if isinstance(gate_id, str)]
            declared = set(declared_values)
            if not string_list(required_gates) or set(required_gates) != declared:
                errors.append(f"{location}: close gate registry mismatch")
            if isinstance(declared_evidence_tier, str) and declared_evidence_tier in {"pilot", "pilot-signed"} and pilot_generation != generation:
                errors.append(f"{location}: pilot authorization is stale for the final generation")
            closed = True
        else:
            errors.append(f"{location}: unsupported event {kind!r}")
    if not closed:
        errors.append(f"{scenario['name']}: missing close")
    if isinstance(declared_evidence_tier, str) and declared_evidence_tier in {"pilot", "pilot-signed"} and not pilot_seen:
        errors.append(f"{scenario['name']}: declared pilot/promotion requires trusted pilot admission")
    for child, node in nodes.items():
        if node["agent_type"] == "default":
            descendants = [name for name, parent in parents.items() if parent == child]
            if len(descendants) < 2 or child not in peer_relay_used:
                errors.append(f"{scenario['name']}: default peer is a no-op without descendants and material relay")
    return errors


def validate_trace_document(document: object, trusted_authority_receipts: object = None) -> list[str]:
    if not isinstance(document, dict):
        return ["trace root must be an object"]
    required = {"version", "logical_direct_child_cap", "bounded_peer_leaf_cap", "runtime_capacity", "owner_hashes", "scenarios"}
    authority, active_task_ids, authority_errors = authority_index(trusted_authority_receipts)
    errors = authority_errors + ([] if set(document) == required else ["trace root has unknown or missing fields"])
    for key, expected in (("version", 3), ("logical_direct_child_cap", 3), ("bounded_peer_leaf_cap", 2), ("runtime_capacity", 16)):
        if document.get(key) != expected:
            errors.append(f"{key} must be {expected}")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return errors + ["scenarios must be a non-empty list"]
    task_ids = [
        scenario.get("task_id")
        for scenario in scenarios
        if isinstance(scenario, dict)
        and isinstance(scenario.get("task_id"), str)
        and scenario["task_id"]
    ]
    duplicated_task_ids = sorted(
        task_id for task_id in set(task_ids) if task_ids.count(task_id) > 1
    )
    if duplicated_task_ids:
        errors.append(
            "duplicate task_id resets task-wide lifecycle ledger across scenarios: "
            + ", ".join(duplicated_task_ids)
        )
    for scenario in scenarios:
        errors.extend(validate_scenario(scenario, authority, active_task_ids))
    return errors


def load_trace(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_trusted_authority_receipts(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8"))

"""Extract privacy-preserving production facts from Codex rollout JSONL."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Iterable
import uuid

from .campaign import EvaluationError, _reject_duplicate_keys


SCHEMA_VERSION = "production-fact.v1"
PARSER_VERSION = "production-fact-parser.v1"
SUPPORTED_EVENT_TYPES = {"session_meta", "turn_context", "response_item", "event_msg", "compacted"}
TOKEN_NAMES = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
CREDIT_NAMES = ("uncached_input", "cached_input", "output", "total")
UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path_id(path: Path) -> str:
    return _sha256(str(path.resolve()).encode("utf-8"))


def _timestamp(value: object, location: str) -> datetime:
    if not isinstance(value, str):
        raise EvaluationError(f"{location} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvaluationError(f"{location} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise EvaluationError(f"{location} must include a timezone")
    return parsed.astimezone(timezone.utc)


def parse_cutoff(value: str) -> datetime:
    return _timestamp(value, "--cutoff")


def _load_jsonl(path: Path, cutoff: datetime) -> tuple[list[dict], bytes]:
    raw = path.read_bytes()
    events = []
    for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise EvaluationError(f"invalid JSONL in source {_path_id(path)}:{line_number}") from error
        if not isinstance(event, dict):
            raise EvaluationError(f"JSONL event must be an object in source {_path_id(path)}:{line_number}")
        observed = _timestamp(event.get("timestamp"), f"source event {line_number}.timestamp")
        if observed <= cutoff:
            event = dict(event)
            event["_observed_at"] = observed
            event["_raw_size"] = len(line)
            events.append(event)
    return events, raw


def _payload(event: dict) -> dict:
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def _response(event: dict) -> dict:
    payload = _payload(event)
    if event.get("type") == "response_item" and isinstance(payload, dict):
        return payload
    return {}


def _arguments(payload: dict) -> dict:
    value = payload.get("arguments")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _call_name(payload: dict) -> str | None:
    name = payload.get("name")
    if isinstance(name, str):
        return name.rsplit(".", 1)[-1]
    return None


def _uuid7_time(identifier: str) -> datetime:
    try:
        parsed = uuid.UUID(identifier)
    except ValueError as error:
        raise EvaluationError(f"child lineage id is not a UUID: {identifier!r}") from error
    if parsed.version != 7:
        raise EvaluationError(f"child lineage id is not UUIDv7: {identifier!r}")
    milliseconds = parsed.int >> 80
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def _source_thread_id(events: list[dict], path: Path) -> str:
    identifiers = set()
    for event in events:
        if event.get("type") != "session_meta":
            continue
        payload = _payload(event)
        for key in ("id", "thread_id", "session_id"):
            if isinstance(payload.get(key), str):
                identifiers.add(payload[key])
    if not identifiers:
        match = UUID_PATTERN.search(path.name)
        if match:
            identifiers.add(match.group(0))
    if len(identifiers) != 1:
        raise EvaluationError(f"child source {_path_id(path)} has missing or ambiguous session lineage")
    return next(iter(identifiers))


def _output_text(payload: dict) -> str:
    output = payload.get("output")
    if isinstance(output, str):
        return output
    return json.dumps(output, sort_keys=True) if output is not None else ""


def _spawn_records(events: list[dict]) -> list[dict]:
    calls: dict[str, dict] = {}
    records = []
    for event in events:
        payload = _response(event)
        kind = payload.get("type")
        if kind in {"function_call", "custom_tool_call"} and _call_name(payload) == "spawn_agent":
            call_id = payload.get("call_id") or payload.get("id")
            if not isinstance(call_id, str) or call_id in calls:
                raise EvaluationError("parent source has missing or duplicate spawn call id")
            arguments = _arguments(payload)
            task_name = arguments.get("task_name")
            if not isinstance(task_name, str) or not task_name.strip():
                raise EvaluationError("spawn call has missing task_name lineage")
            fork_turns = arguments.get("fork_turns", "all")
            if not isinstance(fork_turns, str) or not (
                fork_turns in {"all", "none"} or fork_turns.isdigit()
            ):
                raise EvaluationError("spawn call has unsupported fork_turns lineage")
            calls[call_id] = {
                "call_id": call_id,
                "spawned_at": event["_observed_at"],
                "task_name": task_name,
                "fork_turns": fork_turns,
            }
        elif kind in {"function_call_output", "custom_tool_call_output"}:
            call_id = payload.get("call_id")
            if call_id not in calls:
                continue
            text = _output_text(payload)
            identifiers = sorted(set(UUID_PATTERN.findall(text)))
            lower_text = text.lower().lstrip()
            failed = bool(payload.get("is_error") or payload.get("isError")) or bool(
                re.search(r"\b(?:failed|failure)\b", lower_text)
                or lower_text.startswith("error")
            )
            if failed:
                if identifiers:
                    raise EvaluationError("failed spawn output has ambiguous receiver lineage")
                records.append({**calls.pop(call_id), "receiver_id": None, "failed": True})
            elif len(identifiers) == 1:
                records.append(
                    {**calls.pop(call_id), "receiver_id": identifiers[0], "failed": False}
                )
            else:
                raise EvaluationError("spawn output has missing or ambiguous receiver lineage")
    if calls:
        raise EvaluationError("spawn call has no terminal output lineage")
    receiver_ids = [item["receiver_id"] for item in records if item["receiver_id"]]
    if len(receiver_ids) != len(set(receiver_ids)):
        raise EvaluationError("multiple spawn calls map to the same child lineage")
    return records


def _metric(value: object, basis: str | None, source_id: str | None) -> dict:
    available = value is not None
    if available and (not basis or not source_id):
        raise EvaluationError("available metric requires basis and source_id")
    if not available and (basis is not None or source_id is not None):
        raise EvaluationError("unavailable metric cannot declare basis or source_id")
    return {
        "status": "available" if available else "unavailable",
        "basis": basis,
        "source_id": source_id,
        "value": value,
    }


def _walk_dicts(value: object) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _token_totals(source_events: list[list[dict]]) -> dict[str, int | None]:
    totals = {key: 0 for key in TOKEN_NAMES}
    found_count = {key: 0 for key in TOKEN_NAMES}
    for events in source_events:
        latest: dict[str, int] = {}
        for event in events:
            for item in _walk_dicts(_payload(event)):
                for key in TOKEN_NAMES:
                    value = item.get(key)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        latest[key] = value
        if all(key in latest for key in TOKEN_NAMES):
            if (
                latest["cached_input_tokens"]
                + latest["cache_write_input_tokens"]
                > latest["input_tokens"]
            ):
                raise EvaluationError("production token cache decomposition exceeds input")
            if latest["reasoning_output_tokens"] > latest["output_tokens"]:
                raise EvaluationError("production reasoning tokens exceed output")
            if latest["total_tokens"] != latest["input_tokens"] + latest["output_tokens"]:
                raise EvaluationError("production total tokens must equal input plus output")
        for key, value in latest.items():
            totals[key] += value
            found_count[key] += 1
    return {
        key: totals[key] if found_count[key] == len(source_events) else None
        for key in TOKEN_NAMES
    }


def _credit_categories(value: object, location: str) -> dict[str, Decimal]:
    if not isinstance(value, dict) or set(value) != set(CREDIT_NAMES):
        raise EvaluationError(f"{location} credit categories are incomplete")
    parsed = {}
    for key in CREDIT_NAMES:
        item = value[key]
        if not isinstance(item, str) or not re.fullmatch(
            r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", item
        ):
            raise EvaluationError(f"{location}.{key} must be an exact decimal string")
        try:
            parsed[key] = Decimal(item)
        except InvalidOperation as error:  # pragma: no cover - guarded by regex
            raise EvaluationError(f"{location}.{key} is invalid") from error
    if parsed["total"] != sum(
        (parsed[key] for key in CREDIT_NAMES if key != "total"), Decimal(0)
    ):
        raise EvaluationError(f"{location}.total does not match category sum")
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _billing_records(events: list[dict], location: str) -> list[dict]:
    records = []
    for event_index, event in enumerate(events):
        payload = _payload(event)
        if payload.get("type") != "billing_record":
            continue
        scope = payload.get("scope", payload.get("billing_scope"))
        if scope not in {"thread", "run"}:
            raise EvaluationError(
                f"{location}[{event_index}] billing record scope is invalid"
            )
        id_keys = ("thread_id", "record_id") if scope == "thread" else ("run_id", "record_id")
        identifiers = [payload[key] for key in id_keys if key in payload]
        if (
            len(identifiers) != 1
            or not isinstance(identifiers[0], str)
            or not identifiers[0].strip()
        ):
            raise EvaluationError(
                f"{location}[{event_index}] billing record identity is ambiguous"
            )
        records.append(
            {
                "scope": scope,
                "record_id": identifiers[0],
                "credits": _credit_categories(
                    payload.get("credits"),
                    f"{location}[{event_index}].credits",
                ),
            }
        )
    return records


def _credit_values(source_events: list[list[dict]]) -> dict[str, object | None]:
    unavailable = {
        "thread_records": None,
        **{f"thread_{key}": None for key in CREDIT_NAMES},
        **{f"run_{key}": None for key in CREDIT_NAMES},
    }
    records_by_source = [
        _billing_records(events, f"source[{index}]")
        for index, events in enumerate(source_events)
    ]
    thread_records = [
        [record for record in records if record["scope"] == "thread"]
        for records in records_by_source
    ]
    run_records = [
        record
        for records in records_by_source
        for record in records
        if record["scope"] == "run"
    ]
    if (
        any(len(records) != 1 for records in thread_records)
        or len(run_records) != 1
        or any(record["scope"] == "run" for records in records_by_source[1:] for record in records)
    ):
        return unavailable
    flattened = [records[0] for records in thread_records]
    record_ids = [record["record_id"] for record in flattened]
    if len(record_ids) != len(set(record_ids)):
        return unavailable
    thread_totals = {
        key: sum((record["credits"][key] for record in flattened), Decimal(0))
        for key in CREDIT_NAMES
    }
    run_credits = run_records[0]["credits"]
    if any(run_credits[key] != thread_totals[key] for key in CREDIT_NAMES):
        raise EvaluationError("run billing credits do not match complete thread records")
    return {
        "thread_records": [
            {
                "record_id_sha256": _sha256(record["record_id"].encode("utf-8")),
                **{
                    key: _decimal_text(record["credits"][key])
                    for key in CREDIT_NAMES
                },
            }
            for record in flattened
        ],
        **{
            f"thread_{key}": _decimal_text(thread_totals[key])
            for key in CREDIT_NAMES
        },
        **{
            f"run_{key}": _decimal_text(run_credits[key])
            for key in CREDIT_NAMES
        },
    }


def _git(repo: Path, *arguments: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        raise EvaluationError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _numstat(text: str) -> tuple[int, int | None, int | None]:
    rows = 0
    additions = 0
    deletions = 0
    complete = True
    for line in text.splitlines():
        if not line:
            continue
        columns = line.split("\t", 2)
        if len(columns) != 3:
            raise EvaluationError("git numstat produced an unsupported row")
        rows += 1
        if columns[0] == "-" or columns[1] == "-":
            complete = False
        else:
            additions += int(columns[0])
            deletions += int(columns[1])
    return rows, additions if complete else None, deletions if complete else None


def extract_production_facts(
    *,
    parent: Path,
    children_root: Path,
    repo: Path,
    base: str,
    cutoff: datetime,
    source_state: str,
) -> dict:
    if source_state not in {"terminal", "active", "incomplete"}:
        raise EvaluationError("source_state is invalid")
    for path, kind in ((parent, "file"), (children_root, "directory"), (repo, "directory")):
        if not path.is_absolute() or not path.exists():
            raise EvaluationError(f"{kind} input must be an absolute existing path")
    if not parent.is_file() or not children_root.is_dir() or not repo.is_dir():
        raise EvaluationError("production-facts input type mismatch")
    if not base.strip():
        raise EvaluationError("--base must be explicit")

    parent_events, parent_raw = _load_jsonl(parent, cutoff)
    parent_source_id = _sha256(parent_raw)
    spawns = _spawn_records(parent_events)

    child_sources: dict[str, tuple[Path, list[dict], bytes]] = {}
    for path in sorted(children_root.rglob("*.jsonl")):
        events, raw = _load_jsonl(path, cutoff)
        identifier = _source_thread_id(events, path)
        if identifier in child_sources:
            raise EvaluationError("duplicate child source lineage")
        child_sources[identifier] = (path, events, raw)

    successful_ids = {item["receiver_id"] for item in spawns if item["receiver_id"]}
    if successful_ids != set(child_sources):
        raise EvaluationError("spawn lineage does not exactly match child sources")

    filtered_children = []
    child_intervals = []
    nested_spawns = 0
    roles = []
    fork_values = []
    for spawn in spawns:
        fork_values.append(spawn["fork_turns"])
        if spawn["failed"]:
            continue
        identifier = spawn["receiver_id"]
        path, events, raw = child_sources[identifier]
        uuid_start = _uuid7_time(identifier)
        if uuid_start < spawn["spawned_at"]:
            raise EvaluationError("child UUIDv7 start predates parent spawn")
        turn_contexts = [event for event in events if event.get("type") == "turn_context"]
        if any(event["_observed_at"] < spawn["spawned_at"] for event in turn_contexts):
            raise EvaluationError("child source contains copied pre-spawn turn_context history")
        starts = [
            event for event in turn_contexts if event["_observed_at"] >= spawn["spawned_at"]
        ]
        if not starts:
            raise EvaluationError("child source has no turn_context at or after spawn")
        start_times = [event["_observed_at"] for event in starts]
        if start_times != sorted(start_times):
            raise EvaluationError("child post-spawn turn_context lineage is out of order")
        start = start_times[0]
        if start_times.count(start) != 1:
            raise EvaluationError("child post-spawn turn_context lineage start is ambiguous")
        if start < uuid_start:
            raise EvaluationError("child turn_context predates UUIDv7 lineage start")
        selected = [event for event in events if event["_observed_at"] >= start]
        if any(
            event["_observed_at"] < start
            and event.get("type") in {"response_item", "event_msg", "compacted"}
            for event in events
        ):
            raise EvaluationError("child source contains copied pre-spawn event history")
        nested_spawns += len(_spawn_records(selected))
        role = None
        for event in selected:
            payload = _payload(event)
            candidate = payload.get("role") or payload.get("agent_role")
            if isinstance(candidate, str):
                role = candidate
                break
        roles.append(role)
        terminal_events = [
            event
            for event in selected
            if (
                event.get("type") == "event_msg"
                and _payload(event).get("type") in {"task_complete", "agent_status"}
                and (_payload(event).get("status") in {None, "completed", "failed", "cancelled"})
            )
            or (
                event.get("type") == "response_item"
                and _payload(event).get("type") == "message"
                and _payload(event).get("role") == "assistant"
            )
        ]
        end = terminal_events[-1]["_observed_at"] if terminal_events else cutoff
        child_intervals.append(
            {
                "child_id": _sha256(identifier.encode("utf-8")),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "terminal_observed": bool(terminal_events),
            }
        )
        admitted_bytes = sum(event["_raw_size"] for event in selected)
        filtered_children.append((selected, admitted_bytes, _sha256(raw)))

    all_event_lists = [parent_events, *(item[0] for item in filtered_children)]
    all_events = [event for events in all_event_lists for event in events]
    unsupported = sum(1 for event in all_events if event.get("type") not in SUPPORTED_EVENT_TYPES)
    response_payloads = [_response(event) for event in all_events]
    call_names = [_call_name(payload) for payload in response_payloads]
    message_count = sum(name in {"send_message", "followup_task"} for name in call_names)
    send_message_count = sum(name == "send_message" for name in call_names)
    followup_count = sum(name == "followup_task" for name in call_names)
    wait_count = sum(name == "wait_agent" for name in call_names)
    compaction_count = sum(
        event.get("type") == "compacted" or _payload(event).get("type") == "compacted"
        for event in all_events
    )

    boundaries = sorted(
        [(item["start"], 1) for item in child_intervals]
        + [(item["end"], -1) for item in child_intervals],
        key=lambda item: (item[0], -item[1]),
    )
    active = 0
    max_active = 0
    for _, delta in boundaries:
        active += delta
        max_active = max(max_active, active)

    base_revision = _git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    head_revision = _git(repo, "rev-parse", "HEAD")
    base_tree = _git(repo, "rev-parse", f"{base_revision}^{{tree}}")
    head_tree = _git(repo, "rev-parse", f"{head_revision}^{{tree}}")
    ancestor = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base_revision, head_revision],
        check=False,
        capture_output=True,
    ).returncode == 0
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    clean = not status
    committed_paths = _git(repo, "diff", "--name-only", base_revision, head_revision).splitlines()
    committed_numstat = _git(repo, "diff", "--numstat", base_revision, head_revision)
    committed_rows, committed_add, committed_delete = _numstat(committed_numstat)
    staged_paths = _git(repo, "diff", "--cached", "--name-only").splitlines()
    staged_rows, staged_add, staged_delete = _numstat(
        _git(repo, "diff", "--cached", "--numstat")
    )
    commit_count_text = _git(repo, "rev-list", "--count", f"{base_revision}..{head_revision}")
    combined_source_id = _sha256(
        "".join(sorted([parent_source_id, *(item[2] for item in filtered_children)])).encode("ascii")
    )
    tokens = _token_totals(all_event_lists)
    credit_values = _credit_values(all_event_lists)
    credits_available = all(value is not None for value in credit_values.values())
    basis = PARSER_VERSION
    metrics = {
        "tokens": {
            key: _metric(value, basis if value is not None else None, combined_source_id if value is not None else None)
            for key, value in tokens.items()
        },
        "credits": {
            key: _metric(
                value,
                "explicit-thread-run-billing-record.v1" if credits_available else None,
                combined_source_id if credits_available else None,
            )
            for key, value in credit_values.items()
        },
        "spawns": {
            "attempted": _metric(len(spawns), basis, parent_source_id),
            "started": _metric(len(successful_ids), basis, parent_source_id),
            "failed": _metric(sum(item["failed"] for item in spawns), basis, parent_source_id),
            "nested": _metric(nested_spawns, basis, combined_source_id),
        },
        "roles": {
            "observed": _metric(sum(role is not None for role in roles), basis, combined_source_id),
            "unavailable": _metric(sum(role is None for role in roles), basis, combined_source_id),
            "distribution": _metric(
                (
                    {
                        role: roles.count(role)
                        for role in sorted(set(role for role in roles if role is not None))
                    }
                    if all(role is not None for role in roles)
                    else None
                ),
                basis if all(role is not None for role in roles) else None,
                combined_source_id if all(role is not None for role in roles) else None,
            ),
        },
        "forks": {
            "all": _metric(sum(value == "all" for value in fork_values), basis, parent_source_id),
            "none": _metric(sum(value == "none" for value in fork_values), basis, parent_source_id),
            "partial": _metric(sum(value not in {"all", "none"} for value in fork_values), basis, parent_source_id),
        },
        "messages": {
            "sent": _metric(message_count, basis, combined_source_id),
            "send_message": _metric(send_message_count, basis, combined_source_id),
            "followup_task": _metric(followup_count, basis, combined_source_id),
        },
        "waits": {"calls": _metric(wait_count, basis, combined_source_id)},
        "compactions": {"count": _metric(compaction_count, basis, combined_source_id)},
        "concurrency": {
            "intervals": _metric(child_intervals, basis, combined_source_id),
            "max_active_children": _metric(max_active, basis, combined_source_id),
        },
        "log_bytes": {
            "parent": _metric(
                sum(event["_raw_size"] for event in parent_events),
                "cutoff-admitted-source-bytes",
                parent_source_id,
            ),
            "children": _metric(
                sum(item[1] for item in filtered_children),
                "post-spawn-turn-context-admitted-bytes",
                combined_source_id,
            ),
            "total": _metric(
                sum(event["_raw_size"] for event in parent_events)
                + sum(item[1] for item in filtered_children),
                "admitted-source-bytes",
                combined_source_id,
            ),
        },
        "git_denominators": {
            "commit_count": _metric(int(commit_count_text), "git-rev-list", _sha256(head_revision.encode())),
            "path_count": _metric(len(committed_paths), "git-diff-name-only", _sha256(head_revision.encode())),
            "numstat_rows": _metric(committed_rows, "git-diff-numstat", _sha256(head_revision.encode())),
            "numstat_additions": _metric(committed_add, "git-diff-numstat" if committed_add is not None else None, _sha256(head_revision.encode()) if committed_add is not None else None),
            "numstat_deletions": _metric(committed_delete, "git-diff-numstat" if committed_delete is not None else None, _sha256(head_revision.encode()) if committed_delete is not None else None),
            "staged_path_count": _metric(len(staged_paths), "git-diff-cached-name-only", _sha256(head_revision.encode())),
            "staged_numstat_rows": _metric(staged_rows, "git-diff-cached-numstat", _sha256(head_revision.encode())),
            "staged_additions": _metric(staged_add, "git-diff-cached-numstat" if staged_add is not None else None, _sha256(head_revision.encode()) if staged_add is not None else None),
            "staged_deletions": _metric(staged_delete, "git-diff-cached-numstat" if staged_delete is not None else None, _sha256(head_revision.encode()) if staged_delete is not None else None),
        },
    }
    unavailable_count = sum(
        1
        for item in _walk_dicts(metrics)
        if item.get("status") == "unavailable"
    )
    document = {
        "schema_version": SCHEMA_VERSION,
        "parser": {"version": PARSER_VERSION, "sha256": _sha256(Path(__file__).read_bytes())},
        "sources": {
            "combined_sha256": combined_source_id,
            "parent_sha256": parent_source_id,
            "child_sha256": sorted(item[2] for item in filtered_children),
            "repo_path_sha256": _path_id(repo),
        },
        "cutoff": cutoff.isoformat(),
        "source_state": source_state,
        "git_source": {
            "base_revision": base_revision,
            "base_tree": base_tree,
            "head_revision": head_revision,
            "head_tree": head_tree,
            "base_is_ancestor": ancestor,
            "clean": clean,
            "committed_path_sha256": sorted(_sha256(path.encode("utf-8")) for path in committed_paths),
            "staged_path_sha256": sorted(_sha256(path.encode("utf-8")) for path in staged_paths),
        },
        "metrics": metrics,
        "unsupported_event_count": _metric(unsupported, basis, combined_source_id),
        "unavailable_metric_count": _metric(
            unavailable_count, "metric-status-denominator", combined_source_id
        ),
        "completion_claim_eligible": False,
        "causal_claim_eligible": False,
        "promotion_claim_eligible": False,
    }
    validate_production_fact(document)
    return document


def validate_production_fact(document: dict) -> None:
    expected = {
        "schema_version",
        "parser",
        "sources",
        "cutoff",
        "source_state",
        "git_source",
        "metrics",
        "unsupported_event_count",
        "unavailable_metric_count",
        "completion_claim_eligible",
        "causal_claim_eligible",
        "promotion_claim_eligible",
    }
    if not isinstance(document, dict) or set(document) != expected:
        raise EvaluationError("production fact top-level keys mismatch")
    if document["schema_version"] != SCHEMA_VERSION:
        raise EvaluationError(f"production fact schema_version must be {SCHEMA_VERSION}")
    parser = document["parser"]
    if not isinstance(parser, dict) or set(parser) != {"version", "sha256"}:
        raise EvaluationError("production fact parser keys mismatch")
    if parser["version"] != PARSER_VERSION or not re.fullmatch(
        r"[0-9a-f]{64}", str(parser["sha256"])
    ):
        raise EvaluationError("production fact parser identity is invalid")
    source_keys = {
        "combined_sha256",
        "parent_sha256",
        "child_sha256",
        "repo_path_sha256",
    }
    sources = document["sources"]
    if not isinstance(sources, dict) or set(sources) != source_keys:
        raise EvaluationError("production fact source keys mismatch")
    if not isinstance(sources["child_sha256"], list):
        raise EvaluationError("production fact child source digests must be a list")
    source_digests = [
        sources["combined_sha256"],
        sources["parent_sha256"],
        sources["repo_path_sha256"],
        *sources["child_sha256"],
    ]
    if any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
        for value in source_digests
    ):
        raise EvaluationError("production fact source digest is invalid")
    git_keys = {
        "base_revision",
        "base_tree",
        "head_revision",
        "head_tree",
        "base_is_ancestor",
        "clean",
        "committed_path_sha256",
        "staged_path_sha256",
    }
    git_source = document["git_source"]
    if not isinstance(git_source, dict) or set(git_source) != git_keys:
        raise EvaluationError("production fact git source keys mismatch")
    for key in ("base_revision", "base_tree", "head_revision", "head_tree"):
        if not isinstance(git_source[key], str) or not git_source[key]:
            raise EvaluationError(f"production fact git_source.{key} is invalid")
    for key in ("base_is_ancestor", "clean"):
        if not isinstance(git_source[key], bool):
            raise EvaluationError(f"production fact git_source.{key} must be boolean")
    for key in ("committed_path_sha256", "staged_path_sha256"):
        values = git_source[key]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in values
        ):
            raise EvaluationError(f"production fact git_source.{key} is invalid")
    _timestamp(document["cutoff"], "production fact cutoff")
    if document["source_state"] not in {"terminal", "active", "incomplete"}:
        raise EvaluationError("production fact source_state is invalid")
    expected_metric_groups = {
        "tokens": set(TOKEN_NAMES),
        "credits": {
            "thread_records",
            *{f"thread_{key}" for key in CREDIT_NAMES},
            *{f"run_{key}" for key in CREDIT_NAMES},
        },
        "spawns": {"attempted", "started", "failed", "nested"},
        "roles": {"observed", "unavailable", "distribution"},
        "forks": {"all", "none", "partial"},
        "messages": {"sent", "send_message", "followup_task"},
        "waits": {"calls"},
        "compactions": {"count"},
        "concurrency": {"intervals", "max_active_children"},
        "log_bytes": {"parent", "children", "total"},
        "git_denominators": {
            "commit_count",
            "path_count",
            "numstat_rows",
            "numstat_additions",
            "numstat_deletions",
            "staged_path_count",
            "staged_numstat_rows",
            "staged_additions",
            "staged_deletions",
        },
    }
    if not isinstance(document["metrics"], dict) or set(document["metrics"]) != set(
        expected_metric_groups
    ):
        raise EvaluationError("production fact metric groups mismatch")
    for group, keys in expected_metric_groups.items():
        if not isinstance(document["metrics"][group], dict) or set(
            document["metrics"][group]
        ) != keys:
            raise EvaluationError(f"production fact metrics.{group} keys mismatch")
    unavailable = 0
    metric_count = 0
    metric_groups = dict(document["metrics"])
    metric_groups["fact_denominators"] = {
        "unsupported_event_count": document["unsupported_event_count"],
        "unavailable_metric_count": document["unavailable_metric_count"],
    }
    for group_name, group in metric_groups.items():
        if not isinstance(group, dict) or not group:
            raise EvaluationError(f"metrics.{group_name} must be a non-empty object")
        for metric_name, metric in group.items():
            location = f"metrics.{group_name}.{metric_name}"
            if not isinstance(metric, dict) or set(metric) != {
                "status",
                "basis",
                "source_id",
                "value",
            }:
                raise EvaluationError(f"{location} metric keys mismatch")
            metric_count += 1
            status = metric["status"]
            value = metric["value"]
            if status == "unavailable":
                unavailable += 1
                if value is not None or metric["basis"] is not None or metric["source_id"] is not None:
                    raise EvaluationError(
                        f"{location} unavailable status requires null value/basis/source_id"
                    )
            elif status == "available":
                if value is None:
                    raise EvaluationError(f"{location} available status requires non-null value")
                if not isinstance(metric["basis"], str) or not metric["basis"]:
                    raise EvaluationError(f"{location} available status requires basis")
                source_id = metric["source_id"]
                if not isinstance(source_id, str) or not re.fullmatch(r"[0-9a-f]{64}", source_id):
                    raise EvaluationError(f"{location} available status requires source_id SHA-256")
            else:
                raise EvaluationError(f"{location}.status is invalid")
    expected_unavailable = document["unavailable_metric_count"]["value"]
    if metric_count == 0 or expected_unavailable != unavailable:
        raise EvaluationError("production fact unavailable metric denominator mismatch")
    for field in ("unsupported_event_count", "unavailable_metric_count"):
        metric = document[field]
        if (
            metric["status"] != "available"
            or not isinstance(metric["value"], int)
            or isinstance(metric["value"], bool)
            or metric["value"] < 0
        ):
            raise EvaluationError(f"{field} must be an available non-negative integer")
    for field in ("failed", "nested"):
        value = document["metrics"]["spawns"][field]["value"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise EvaluationError(f"production fact spawns.{field} must be non-negative")
    credit_metrics = document["metrics"]["credits"]
    credit_statuses = {metric["status"] for metric in credit_metrics.values()}
    if len(credit_statuses) != 1:
        raise EvaluationError("production credit metrics must be uniformly available or unavailable")
    if credit_statuses == {"available"}:
        records = credit_metrics["thread_records"]["value"]
        if not isinstance(records, list) or len(records) != (
            document["metrics"]["spawns"]["started"]["value"] + 1
        ):
            raise EvaluationError("production thread credit records are incomplete")
        seen_record_ids = set()
        parsed_records = []
        for index, record in enumerate(records):
            expected_record_keys = {"record_id_sha256", *CREDIT_NAMES}
            if not isinstance(record, dict) or set(record) != expected_record_keys:
                raise EvaluationError(
                    f"production thread credit record {index} keys mismatch"
                )
            record_id = record["record_id_sha256"]
            if not isinstance(record_id, str) or not re.fullmatch(
                r"[0-9a-f]{64}", record_id
            ):
                raise EvaluationError(
                    f"production thread credit record {index} identity is invalid"
                )
            if record_id in seen_record_ids:
                raise EvaluationError("production thread credit record identity is duplicate")
            seen_record_ids.add(record_id)
            parsed_records.append(
                _credit_categories(
                    {key: record[key] for key in CREDIT_NAMES},
                    f"production thread credit record {index}",
                )
            )
        thread_aggregate = _credit_categories(
            {
                key: credit_metrics[f"thread_{key}"]["value"]
                for key in CREDIT_NAMES
            },
            "production thread credit aggregate",
        )
        run_aggregate = _credit_categories(
            {key: credit_metrics[f"run_{key}"]["value"] for key in CREDIT_NAMES},
            "production run credit aggregate",
        )
        for key in CREDIT_NAMES:
            observed = sum((record[key] for record in parsed_records), Decimal(0))
            if thread_aggregate[key] != observed or run_aggregate[key] != observed:
                raise EvaluationError(
                    "production thread/run credit aggregates do not reconcile"
                )
    claims = (
        document["completion_claim_eligible"],
        document["causal_claim_eligible"],
        document["promotion_claim_eligible"],
    )
    if any(not isinstance(value, bool) for value in claims):
        raise EvaluationError("production fact eligibility claims must be booleans")
    intervals = document["metrics"]["concurrency"]["intervals"]["value"]
    if not isinstance(intervals, list):
        raise EvaluationError("production fact concurrency intervals must be a list")
    if any(claims):
        raise EvaluationError("observational production facts cannot support claims")

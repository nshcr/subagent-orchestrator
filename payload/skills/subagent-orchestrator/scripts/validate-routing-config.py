#!/usr/bin/env python3
"""Validate the installed quality-first Codex subagent routing contract."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lifecycle_conformance import (
    load_trace,
    load_trusted_authority_receipts,
    validate_trace_document,
)


SKILL_NAME = "subagent-orchestrator"
DEFAULT_SKILL_PATH = Path(__file__).resolve().parents[1] / "SKILL.md"
ROLE_POLICY = {
    "evidence_tester": ("gpt-5.6-luna", "max", "default", "workspace-write"),
    "boundary_mapper": ("gpt-5.6-terra", "max", "default", "read-only"),
    "risk_reviewer": ("gpt-5.6-sol", "xhigh", "default", "read-only"),
    "risk_reviewer_max": ("gpt-5.6-sol", "max", "default", "read-only"),
}
ROLE_RECEIPT_MARKERS = {
    "evidence_tester": (
        "structured test output or bounded runbook-driven log surface",
        "handoff's `Acceptance fields` to contain one or more exact labels",
        "reject `not-applicable` for this role",
        "Account for benign and negative cases",
        "handoff's `Artifact contract` to name the single artifact path, format, child writer, and receipt transfer rule",
        "reject `none` for this role",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "200 words",
    ),
    "boundary_mapper": (
        "Confirmed test gaps",
        "Preserve source-code identifiers and domain terms verbatim",
        "Derive the ordered trace from real call and state edges",
        "Do not treat a label or mentioned term as proof",
        "handoff's `Acceptance fields` to contain one or more exact labels",
        "reject `not-applicable` for this role",
        "Follow the handoff's `Artifact contract`",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "ARTIFACT_BODY_BEGIN",
        "1200 words",
    ),
    "risk_reviewer": (
        "handoff's `Named invariants` to contain one or more exact invariants",
        "Require `Escalation receipt` to be `not-applicable`",
        "claims inferred only from acceptance-field wording",
        "concrete mechanism, consequence, implementation-specific required control",
        "For a pass, identify the positive implementation and test evidence",
        "Do not invent a blocker outside the named invariants",
        "available evidence is sufficient",
        "at most one fresh `max` review",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "Keep the terminal protocol line exactly as specified above",
        "Follow the handoff's `Artifact contract`",
        "final non-empty line before `ARTIFACT_BODY_END`",
        "final non-empty line of the receipt",
        "ARTIFACT_BODY_BEGIN",
        "1500 words",
    ),
    "risk_reviewer_max": (
        "single terminal `max` adjudication",
        "handoff's `Named invariants` to contain one or more exact invariants",
        "handoff's `Escalation receipt` to identify the prior standalone",
        "sufficient evidence, concrete competing explanations, and the irreversible decision",
        "claims inferred only from acceptance-field wording",
        "concrete mechanism, consequence, implementation-specific required control",
        "For a pass, identify the positive implementation and test evidence",
        "Do not invent a blocker outside the named invariants",
        "positive evidence, negative evidence, and the cross-boundary causal path",
        "invalid `max` trigger",
        "Do not recommend another review, escalation, or higher effort",
        "Residual ambiguity, missing required evidence",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "Keep the terminal protocol line exactly as specified above",
        "Follow the handoff's `Artifact contract`",
        "final non-empty line before `ARTIFACT_BODY_END`",
        "final non-empty line of the receipt",
        "ARTIFACT_BODY_BEGIN",
        "1500 words",
    ),
}
REVIEWER_TERMINAL_LINES = {
    "risk_reviewer": (
        "Gate recommendation: PASS",
        "Gate recommendation: BLOCK / NO-GO",
        "Gate recommendation: INDETERMINATE / ESCALATE",
    ),
    "risk_reviewer_max": (
        "Gate recommendation: PASS",
        "Gate recommendation: BLOCK / NO-GO",
    ),
}
ROLE_INSTRUCTION_SHA256 = {
    "evidence_tester": "e8cfc06d58025b75a15b2075cbdac7fd3918ab40ea972f3cda08d18e8ec16aec",
    "boundary_mapper": "73ff8065f8832480bb29fe64c302982680709b37a6514abd207dfda982a86507",
    "risk_reviewer": "8367775e01048b9aead6deb1451b4d15d7ffe54a888da124f18253ec5969ada0",
    "risk_reviewer_max": "c0b8897de75314993270c6ae4f4a41cff7c42ccc4b057bd9d417c47b7233b90f",
}
REFERENCE_SHA256 = {
    "routing-policy.md": "7ad71e32f2cd794fb0371514fbb5c19c4a6df5759e54f3958a9a69d4d4c5a152",
    "evaluation-policy.md": "86c455304eb053bdaf6255dc9185b455a30a96d1f1958ef633afbd92dfdd5cb7",
    "delegation-contracts.md": "8da7a0d23855626d53bf834f4bb2020f72c13457fc12bceefbf3f1684e271293",
}
SKILL_SHA256 = "e1fbf5508bb4491680245c21d2bf0524897e0983f35307836f91df2cf66ad61d"
GLOBAL_POLICY_SHA256 = {
    "## Subagents and parallelism": "c8ece2451004efe55738e7763a5048a368331e5a02c2b6ad993eb5260a33e7d5",
    "## 子代理与并行": "82ea8d7682749de120a9b332bfb415362a9e99bba9377e283db54711e0916894",
}
GLOBAL_POLICY_MARKERS = {
    "## Subagents and parallelism": (
        "Default to a single agent",
        "Use `$subagent-orchestrator` only",
        "idle capacity alone do not qualify",
        "follow the skill's current routing and evidence-bus slice, topology, task-wide ownership",
        "one unique task occupies one trace scenario and rollover cannot reset task-wide state",
        "Slice owner paths bind every writer path/component and path artifact",
        "Every work transfer has the complete exact-key canonical schema and binds spawn depth",
        "Materiality authority binds an external issuer class",
        "message authority binds exact purpose plus canonical dependency and semantic-message digests",
        "bounded-peer artifact relay must come from the named producer's terminal receipt",
        "High-risk final states require fresh, independent, read-only, disjoint gates",
        "The primary always retains authorization, scope, conflict handling, integration, and final acceptance",
        "children cannot expand authority",
        "governed roles remain leaves",
        "only a capability-and-relay-qualified bounded peer may delegate one level",
        "every required descendant must reach a terminal state before the primary ends",
    ),
    "## 子代理与并行": (
        "默认单代理",
        "使用 `$subagent-orchestrator`",
        "空闲并发本身不构成委派理由",
        "遵循该 skill 当前的证据总线切片、路由、拓扑、全任务所有权",
        "一个唯一任务只占一个 trace scenario，rollover 不得重置全任务状态",
        "slice owner paths 必须绑定每个 writer path/component 与 path artifact",
        "每个 work transfer 使用完整、精确 key 的规范 schema，并绑定 spawn depth",
        "materiality authority 必须绑定外部 issuer class",
        "消息 authority 必须绑定精确 purpose、规范 dependency 摘要和语义消息摘要",
        "受限 peer 的 artifact relay 必须来自具名 producer 的终态收据",
        "高风险最终状态必须在同一文件系统哈希上接受 fresh、独立、只读且互不重叠的门禁",
        "主代理始终保留授权、范围、冲突处理、整合和最终验收",
        "子代理不得扩权",
        "治理角色保持叶子",
        "仅同时通过能力与实质 relay 准入的受限协作代理可继续委派一层",
        "所有必需后代在主代理结束前必须到达终态",
    ),
}
LIFECYCLE_ASSET_SHA256 = {
    "scripts/lifecycle_conformance.py": "99ccc18991fa87281ab7656385f9b53962055f80052dc4819eccc1507222dc05",
    "tests/fixtures/lifecycle-trace.json": "a7d4c0a095f585bf2c8e06ddac6622a4d244162511ce1a57e3e9826767480abb",
    "tests/fixtures/lifecycle-authority-receipts.json": "f2f8ca311501ba43a7414e5c753724cd4e4792054713bddcf93cca031ee8db98",
}
LEGACY_ROLE_NAMES = {
    "luna_builder",
    "luna_scout",
    "luna_tester",
    "terra_builder",
    "terra_mapper",
    "sol_reviewer",
}
REQUIRED_SKILL_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/routing-policy.md",
    "references/delegation-contracts.md",
    "references/evaluation-policy.md",
    "scripts/validate-routing-config.py",
    "scripts/lifecycle_conformance.py",
    "tests/fixtures/lifecycle-trace.json",
    "tests/fixtures/lifecycle-authority-receipts.json",
    "tests/test_lifecycle_conformance.py",
    "tests/test_validate_routing_config.py",
)


@dataclass
class Checks:
    count: int = 0
    errors: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            self.errors.append(message)


def load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def load_required_toml(checks: Checks, path: Path, label: str) -> dict:
    checks.require(path.is_file(), f"missing {label}: {path}")
    return load_toml(path) if path.is_file() else {}


def managed_config_projection(config: dict) -> dict:
    """Project only spawned-agent settings owned by orchestration."""
    agents = config.get("agents", {})
    return {
        "agents": {
            key: agents.get(key)
            for key in (
                "enabled",
                "max_concurrent_threads_per_session",
                "interrupt_message",
                "default_subagent_model",
                "default_subagent_reasoning_effort",
            )
        },
    }


def validate_config(checks: Checks, codex_home: Path) -> None:
    projection = managed_config_projection(
        load_required_toml(checks, codex_home / "config.toml", "config")
    )
    agents = projection["agents"]
    expected = (
        (agents, "enabled", True, "agents"),
        (agents, "max_concurrent_threads_per_session", 16, "agents"),
        (agents, "interrupt_message", True, "agents"),
        (agents, "default_subagent_model", "gpt-5.6-sol", "agents"),
        (agents, "default_subagent_reasoning_effort", "high", "agents"),
    )
    for source, key, value, label in expected:
        checks.require(source.get(key) == value, f"{label}.{key} must be {value}")


def validate_agent_catalog(checks: Checks, codex_home: Path) -> None:
    agents_dir = codex_home / "agents"
    installed = (
        {path.stem for path in agents_dir.glob("*.toml")}
        if agents_dir.is_dir()
        else set()
    )
    missing = set(ROLE_POLICY) - installed
    checks.require(
        not missing,
        f"agent catalog missing required roles {sorted(missing)}; got {sorted(installed)}",
    )
    checks.require(not (installed & LEGACY_ROLE_NAMES), "legacy roles must not be installed")


def validate_role(checks: Checks, role_path: Path, expected_skill_path: str) -> None:
    role = role_path.stem
    data = load_required_toml(checks, role_path, "agent file")
    model, effort, tier, sandbox = ROLE_POLICY[role]
    checks.require(data.get("name") == role, f"{role}: name mismatch")
    checks.require(bool(data.get("description")), f"{role}: description required")
    instructions = data.get("developer_instructions", "")
    checks.require(bool(instructions), f"{role}: developer_instructions required")
    checks.require(data.get("model") == model, f"{role}: model must be {model}")
    checks.require(
        data.get("model_reasoning_effort") == effort,
        f"{role}: effort must be {effort or 'inherited'}",
    )
    checks.require(data.get("service_tier") == tier, f"{role}: tier must be {tier}")
    checks.require(data.get("sandbox_mode") == sandbox, f"{role}: sandbox must be {sandbox}")
    for marker in ROLE_RECEIPT_MARKERS[role]:
        checks.require(marker in instructions, f"{role}: missing receipt marker {marker}")
    checks.require(
        "Do not spawn agents or widen scope." in instructions,
        f"{role}: recursion and scope expansion must be disabled",
    )
    checks.require(
        "unless the parent explicitly asks" not in instructions,
        f"{role}: recursive delegation exception is forbidden",
    )
    if role in {"risk_reviewer", "risk_reviewer_max"}:
        checks.require(
            instructions.isascii(),
            f"{role}: developer_instructions must contain ASCII only",
        )
        for leaked_checklist_term in (
            "fsync",
            "atomic replacement",
            "same-filesystem temporary file",
            "recovery backup",
            "compare-and-swap",
        ):
            checks.require(
                leaked_checklist_term not in instructions.lower(),
                f"{role}: fixed domain checklist leaks into generic role: {leaked_checklist_term}",
            )
        terminal_lines = tuple(
            line[1:-1]
            for line in instructions.splitlines()
            if line.startswith("`Gate recommendation:") and line.endswith("`")
        )
        checks.require(
            terminal_lines == REVIEWER_TERMINAL_LINES[role],
            f"{role}: exact terminal protocol mismatch; got {terminal_lines}",
        )
        checks.require(
            "and its evidence threshold" not in instructions,
            f"{role}: terminal protocol must keep evidence before the standalone line",
        )
    if role == "risk_reviewer_max":
        checks.require(
            "fresh `max` review" not in instructions,
            "risk_reviewer_max: terminal max role must not request another max review",
        )
    checks.require(
        hashlib.sha256(instructions.encode()).hexdigest() == ROLE_INSTRUCTION_SHA256[role],
        f"{role}: developer_instructions integrity mismatch",
    )
    skill_config = data.get("skills", {}).get("config", [])
    checks.require(
        any(item.get("path") == expected_skill_path and item.get("enabled") is False for item in skill_config),
        f"{role}: must disable {expected_skill_path}",
    )


def require_markers(checks: Checks, text: str, label: str, markers: tuple[str, ...]) -> None:
    normalized = " ".join(text.split())
    for marker in markers:
        checks.require(" ".join(marker.split()) in normalized, f"{label} missing policy text: {marker}")


def markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def global_policy_sections(text: str) -> list[tuple[str, str]]:
    return [
        (heading, body)
        for heading in GLOBAL_POLICY_SHA256
        if (body := markdown_section(text, heading))
    ]


def validate_skill_tree(checks: Checks, skill_dir: Path) -> None:
    derived_artifacts = sorted(
        str(path.relative_to(skill_dir))
        for path in skill_dir.rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    ) if skill_dir.is_dir() else []
    checks.require(
        not derived_artifacts,
        f"skill tree contains undeclared Python bytecode: {derived_artifacts}",
    )
    for relative in REQUIRED_SKILL_FILES:
        checks.require((skill_dir / relative).is_file(), f"missing skill file: {relative}")


def validate_lifecycle_assets(
    checks: Checks,
    codex_home: Path,
    skill_dir: Path,
    skill: str,
    routing: str,
    delegation: str,
    evaluation: str,
    agents_text: str,
) -> None:
    for relative, expected_hash in LIFECYCLE_ASSET_SHA256.items():
        path = skill_dir / relative
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        checks.require(
            actual_hash == expected_hash,
            f"{relative}: lifecycle conformance asset integrity mismatch",
        )
    trace_path = skill_dir / "tests" / "fixtures" / "lifecycle-trace.json"
    authority_path = skill_dir / "tests" / "fixtures" / "lifecycle-authority-receipts.json"
    try:
        trace = load_trace(trace_path)
    except (OSError, ValueError) as error:
        checks.require(False, f"lifecycle trace is unreadable: {error}")
        return
    try:
        trusted_authority_receipts = load_trusted_authority_receipts(authority_path)
    except (OSError, ValueError) as error:
        checks.require(False, f"lifecycle authority receipts are unreadable: {error}")
        return
    trace_errors = validate_trace_document(trace, trusted_authority_receipts)
    checks.require(
        not trace_errors,
        f"lifecycle trace conformance failed: {trace_errors}",
    )
    agents = managed_config_projection(load_toml(codex_home / "config.toml"))["agents"]
    agents_hash = hashlib.sha256(
        json.dumps(agents, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    expected_owner_hashes = {
        "SKILL.md": hashlib.sha256(skill.encode()).hexdigest(),
        "references/routing-policy.md": hashlib.sha256(routing.encode()).hexdigest(),
        "references/delegation-contracts.md": hashlib.sha256(delegation.encode()).hexdigest(),
        "references/evaluation-policy.md": hashlib.sha256(evaluation.encode()).hexdigest(),
        "config.toml#agents": agents_hash,
    }
    trace_owner_hashes = trace.get("owner_hashes")
    trace_policy_hash = (
        trace_owner_hashes.get("AGENTS.md#subagent-policy")
        if isinstance(trace_owner_hashes, dict)
        else None
    )
    trace_without_policy = (
        {
            key: value
            for key, value in trace_owner_hashes.items()
            if key != "AGENTS.md#subagent-policy"
        }
        if isinstance(trace_owner_hashes, dict)
        else {}
    )
    current_sections = global_policy_sections(agents_text)
    current_policy_hash = (
        hashlib.sha256(current_sections[0][1].encode()).hexdigest()
        if len(current_sections) == 1
        else None
    )
    checks.require(
        trace_without_policy == expected_owner_hashes
        and trace_policy_hash in set(GLOBAL_POLICY_SHA256.values())
        and current_policy_hash in set(GLOBAL_POLICY_SHA256.values()),
        "lifecycle trace owner hashes do not match the candidate policy/configuration",
    )


def validate_skill_entry(checks: Checks, skill: str) -> None:
    require_markers(checks, skill, "SKILL.md", (
        "name: subagent-orchestrator",
        "Keep this file as the workflow entrypoint.",
        "Start primary-only.",
        "Read [routing policy](references/routing-policy.md) and [evaluation policy](references/evaluation-policy.md) before delegation.",
        "Open one `slice_open`",
        "fork_turns=none",
        "task-wide primary source-access ledger",
        "proper subsets no larger than 10%",
        "Freeze only after the writer is terminal.",
        "Any readback change invalidates every gate.",
        "Close only with a terminal tree",
        "task-wide canonical component",
        "After two writer compactions",
        "`send_message` carries admitted evidence",
        "`followup_task` uses only the three typed same-scope",
        "primary retains authorization, scope, conflict handling, integration, and",
        "python3 -B scripts/validate-routing-config.py",
    ))
    checks.require(
        hashlib.sha256(skill.encode()).hexdigest() == SKILL_SHA256,
        "SKILL.md: canonical workflow integrity mismatch",
    )


def validate_references(
    checks: Checks,
    routing: str,
    evaluation: str,
    delegation: str,
) -> None:
    for name, text in (
        ("routing-policy.md", routing),
        ("evaluation-policy.md", evaluation),
        ("delegation-contracts.md", delegation),
    ):
        checks.require(
            hashlib.sha256(text.encode()).hexdigest() == REFERENCE_SHA256[name],
            f"{name}: canonical policy integrity mismatch",
        )
    require_markers(checks, routing, "routing policy", (
        "Read this reference whenever delegation is considered.",
        "| Material structured test-output triage | `evidence_tester` |",
        "| Material bounded log corpus | `evidence_tester` |",
        "| Named unresolved cross-component boundary | `boundary_mapper` |",
        "| Required independent high-risk final gate | fresh `risk_reviewer` |",
        "| Material narrow read-only codebase question | built-in `explorer` leaf |",
        "| Scoped implementation or fix | built-in `worker` leaf |",
        "| Material dependency graph needing direct evidence handoff | built-in `default` bounded peer |",
        "| Any other, ambiguous, simple, resolved, mechanical, or open-ended class | Primary |",
        "verification-token asset never proves materiality",
        "at least two unique canonical source paths and 4096",
        "at least three and 8192",
        "host, owner, or sealed harness signs",
        "Full-history children are ineligible",
        "proper-subset sampling no larger than 10%",
        "Two accumulated writer compactions",
        "`send_message` carries externally admitted evidence",
        "`followup_task` targets an idle/terminal built-in",
        "Three disjoint fresh gates PASS",
        "Repair reruns all at attempt+1",
        "One `risk_reviewer_max`",
    ))
    require_markers(checks, evaluation, "evaluation policy", (
        "Apply this lexicographic order without weighted averaging",
        "Never trade quality for cost.",
        "Wall time is telemetry only.",
        "Missing or unavailable credits cannot aggregate or promote.",
        "Use the Standard/default service tier for promotion.",
        "multiplies GPT-5.6 ChatGPT credits by 2.5",
        "Compute normalized quality per paired instance",
        "each pair, every class, and overall",
        "overall paired median and overall credits at least 10% lower",
        "checklist surface form earn no quality credit",
        "Acceptance labels define evidence schema, never expected conclusions.",
        "`governance_retention` separately from `efficiency_promotion`",
        "`retained-not-efficient`",
        "it cannot claim efficiency success.",
        "`production-fact.v1`",
        "Active, dirty, unsupported, incomplete, or observational facts",
        "`implemented` -> `verified-local` -> `verified-ci`",
        "host-issued admission receipt",
        "must not auto-create a task",
        "active UTP task is excluded",
    ))
    require_markers(checks, delegation, "delegation contract", (
        "slice_open: <top-level task id + unique slice id>",
        "Producer / consumer / task / slice",
        "Output audience: <user-facing | model-facing>",
        "fork_turns=none",
        "non-padding bytes",
        "no more than 10%",
        "after two, reject another writer spawn or follow-up",
        "Each invariant belongs to exactly one task-wide gate",
        "Repair or hash change requires every gate at attempt N+1",
        "`send_message` targets a running admitted built-in child",
        "`new_failure_evidence`, `missing_acceptance_field`, or",
        "Every child reaches terminal",
        "ARTIFACT_BODY_BEGIN",
        "The primary owns authorization, integration, conflict handling, and acceptance.",
        "`preserve-role-eligibility`",
        "`treat-model-and-effort-values-as-client-specific-hints`",
    ))


def validate_global_policy(checks: Checks, agents_text: str) -> None:
    sections = global_policy_sections(agents_text)
    checks.require(
        len(sections) == 1,
        "AGENTS.md must contain exactly one canonical subagent policy section",
    )
    if len(sections) != 1:
        return
    heading, global_agents_policy = sections[0]
    label = f"AGENTS.md {heading.removeprefix('## ')}"
    require_markers(
        checks,
        global_agents_policy,
        label,
        GLOBAL_POLICY_MARKERS[heading],
    )
    checks.require(
        hashlib.sha256(global_agents_policy.encode()).hexdigest()
        == GLOBAL_POLICY_SHA256[heading],
        f"{label} canonical policy integrity mismatch",
    )
    checks.require(
        len(re.findall(r"(?m)^- ", global_agents_policy)) == 2,
        f"{label} must contain exactly two bullets",
    )
    checks.require(
        len(global_agents_policy.splitlines()) <= 3,
        f"{label} exceeds three-line global policy budget",
    )
    for detail in (
        "evidence_tester",
        "boundary_mapper",
        "risk_reviewer",
        "ARTIFACT_BODY_",
        "MUST/SHOULD",
        "gpt-5.6-",
        "Luna",
        "Terra",
        "Sol High",
        "fsync",
    ):
        checks.require(
            detail not in global_agents_policy,
            f"{label} leaks implementation detail: {detail}",
        )


def validate_ownership_boundaries(
    checks: Checks,
    skill: str,
    routing: str,
    delegation: str,
    yaml_text: str,
) -> None:
    for detail in (
        "ARTIFACT_BODY_BEGIN",
        "MUST/SHOULD",
        "gpt-5.6-",
        "Luna Max",
        "Terra Max",
        "Sol High",
        "fsync",
        "evidence_tester",
        "boundary_mapper",
        "risk_reviewer",
    ):
        checks.require(
            detail not in skill,
            f"SKILL.md duplicates reference or role detail: {detail}",
        )
    for detail in ("gpt-5.6-", "service_tier", "sandbox_mode"):
        checks.require(
            detail not in routing,
            f"routing policy duplicates executable TOML configuration: {detail}",
        )
    for leaked_checklist_term in ("fsync", "atomic replacement", "recovery backup", "compare-and-swap"):
        checks.require(
            leaked_checklist_term not in routing.lower(),
            f"routing policy leaks a fixed domain checklist: {leaked_checklist_term}",
        )
    for role in ROLE_POLICY:
        checks.require(
            role not in delegation,
            f"delegation contract duplicates role-specific behavior: {role}",
        )
        checks.require(
            role not in yaml_text,
            f"openai.yaml duplicates role catalog: {role}",
        )


def validate_policy(checks: Checks, codex_home: Path) -> None:
    skill_dir = codex_home / "skills" / SKILL_NAME
    validate_skill_tree(checks, skill_dir)
    def read(relative: str) -> str:
        path = skill_dir / relative
        return path.read_text() if path.is_file() else ""

    skill = read("SKILL.md")
    routing = read("references/routing-policy.md")
    evaluation = read("references/evaluation-policy.md")
    delegation = read("references/delegation-contracts.md")
    yaml_text = read("agents/openai.yaml")
    agents_text = (codex_home / "AGENTS.md").read_text()

    validate_skill_entry(checks, skill)
    validate_references(checks, routing, evaluation, delegation)
    validate_global_policy(checks, agents_text)
    validate_lifecycle_assets(
        checks,
        codex_home,
        skill_dir,
        skill,
        routing,
        delegation,
        evaluation,
        agents_text,
    )
    validate_ownership_boundaries(checks, skill, routing, delegation, yaml_text)

    global_agents_policy = "\n".join(body for _, body in global_policy_sections(agents_text))
    active_contract = "\n".join(
        (skill, routing, evaluation, delegation, yaml_text, global_agents_policy)
    )
    for legacy in sorted(LEGACY_ROLE_NAMES):
        checks.require(legacy not in active_contract, f"active policy contains legacy role name: {legacy}")
    checks.require(len(skill.splitlines()) <= 70, "SKILL.md exceeds 70-line noise budget")
    for relative, text in (
        ("routing-policy.md", routing),
        ("evaluation-policy.md", evaluation),
        ("delegation-contracts.md", delegation),
    ):
        checks.require(len(text.splitlines()) <= 125, f"{relative} exceeds 125-line noise budget")
    checks.require('display_name: "Subagent Orchestrator"' in yaml_text, "openai.yaml display name mismatch")
    checks.require(
        'short_description: "Evidence-backed delegation routing"' in yaml_text,
        "openai.yaml short description mismatch",
    )
    implicit = re.findall(r"(?m)^\s*allow_implicit_invocation:\s*(true|false)\s*$", yaml_text)
    checks.require(implicit == ["true"], "implicit invocation must appear exactly once and remain true")


def validate(codex_home: Path, configured_skill_path: Path) -> Checks:
    checks = Checks()
    validate_config(checks, codex_home)
    validate_agent_catalog(checks, codex_home)
    for role in ROLE_POLICY:
        validate_role(checks, codex_home / "agents" / f"{role}.toml", str(configured_skill_path))
    validate_policy(checks, codex_home)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--configured-skill-path", type=Path, default=DEFAULT_SKILL_PATH)
    args = parser.parse_args()
    checks = validate(args.codex_home.resolve(), args.configured_skill_path)
    if checks.errors:
        print(f"FAIL: {len(checks.errors)} error(s) across {checks.count} checks")
        for error in checks.errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {checks.count} routing configuration checks")
    print("- promoted custom roles: evidence_tester, boundary_mapper")
    print("- mandatory named gate: fresh risk_reviewer")
    print("- risk_reviewer default: gpt-5.6-sol xhigh; one evidence-triggered max escalation")
    print("- risk_reviewer_max: fixed max runtime variant; no independent task class")
    print("- primary: launch model and reasoning effort are unconstrained")
    print("- default subagent: gpt-5.6-sol high")
    print("- built-in routes: explorer/worker leaves; capability-gated default bounded peer")
    print("- concurrency: three direct children; one bounded peer with two leaf descendants; thread cap 16")
    print("- lifecycle: wait timeouts are non-terminal; required task trees are collected")
    print("- lifecycle conformance: bounded depth, peer messaging, cancellation, and terminal collection passed")
    print("- objective: verified quality first; end-to-end credits second")
    print("- wall time: telemetry only")
    print("- unsupported classes: primary; no dormant custom roles installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

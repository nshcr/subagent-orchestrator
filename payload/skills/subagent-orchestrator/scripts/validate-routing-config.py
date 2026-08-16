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
from lifecycle_conformance import load_trace, validate_trace_document


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
    "routing-policy.md": "2b50c5bedd653476710d490de5b77784d90cd6d8f0b1e90681357c657aadcde0",
    "evaluation-policy.md": "aea59b820434f7e3022aa7db93a6d13b4c5f6c7be954e5067bd4d7fd888f0173",
    "delegation-contracts.md": "842306b06c7501bdda207ed91357e16bddf3da17a3bf83822c29977e3640867f",
}
SKILL_SHA256 = "99ac84463ff80ac6b5fd0131e0d36dd96efadc0484d72f975688758c44936972"
GLOBAL_POLICY_SHA256 = {
    "## Subagents and parallelism": "14d15f56754528d65d25a2434f0dfc88587c63b533309164d83433d718295bd4",
    "## 子代理与并行": "6cc3694505f0c58cc3fab99971a93aa2cf2204ebcf44963cdb039a81b60556f4",
}
GLOBAL_POLICY_MARKERS = {
    "## Subagents and parallelism": (
        "Default to a single agent",
        "Use `$subagent-orchestrator` only",
        "idle capacity alone do not qualify",
        "follow the skill's current routing, topology, ownership, handoff, waiting, and gate rules",
        "high-risk final states require a fresh, independent, read-only review",
        "The primary always retains authorization, scope, conflict handling, integration, and final acceptance",
        "children cannot expand authority",
        "governed roles remain leaves",
        "only a skill-qualified bounded peer may delegate one level",
        "every required descendant must reach a terminal state before the primary ends",
    ),
    "## 子代理与并行": (
        "默认单代理",
        "使用 `$subagent-orchestrator`",
        "空闲并发本身不构成委派理由",
        "遵循该 skill 当前的路由、拓扑、所有权、交接、等待和门禁规则",
        "高风险最终状态必须接受 fresh、独立、只读审阅",
        "主代理始终保留授权、范围、冲突处理、整合和最终验收",
        "子代理不得扩权",
        "治理角色保持叶子",
        "仅 skill 准入的受限协作代理可继续委派一层",
        "所有必需后代在主代理结束前必须到达终态",
    ),
}
LIFECYCLE_ASSET_SHA256 = {
    "scripts/lifecycle_conformance.py": "4f0ee07cd211e300d1a7e8403611d227bf7cc34d9143b4041201ae0f8c591add",
    "tests/fixtures/lifecycle-trace.json": "54c26f25b74909e8df7aa3aedea90926b6a0a7283bc4be8a940b6fdd018f8e42",
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
    try:
        trace = load_trace(trace_path)
    except (OSError, ValueError) as error:
        checks.require(False, f"lifecycle trace is unreadable: {error}")
        return
    trace_errors = validate_trace_document(trace)
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
        "Route and supervise explicit subagent requests, bounded built-in collaboration, and evidence-backed specialist work.",
        "Preserve every required descendant to terminal unless cancellation is authorized.",
        "Keep this file as the workflow entrypoint.",
        "Start primary-only.",
        "If neither substitution nor required independence is present, stay primary.",
        "Read [routing policy](references/routing-policy.md) whenever delegation is",
        "Before selecting a custom role or bounded-peer topology",
        "Keep unsupported, unstable, or capability-unverified classes on primary.",
        "Create one task-local handoff",
        "Start every already-qualified, mutually independent child allowed by the routing policy",
        "never create filler work merely to occupy capacity",
        "wait for every required child and",
        "descendant to reach a terminal state",
        "Treat a wait timeout as observation-only",
        "not as failure, a stall, or permission to interrupt",
        "If a child remains running, report useful progress",
        "and wait again",
        "Never interrupt or replace a child for silence, elapsed wall time, token or credit use",
        "Never start a replacement while the original or a required descendant is",
        "Accept only state-bound evidence",
        "rebuilding transferred work or rewriting an owned artifact",
        "Keep authorization, writer ownership, conflict handling, synthesis, and final acceptance with the primary.",
        "`AGENTS.md`: stable delegation and safety invariants only.",
        "`references/routing-policy.md`: promoted classes and model escalation.",
        "`config.toml`: default-child settings and capacity only",
        "never constrain the primary launch model or reasoning effort",
        "Agent TOMLs: role behavior, permissions, and output limits.",
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
        "Read this reference whenever delegation is being considered.",
        "| Material structured test-output triage | `evidence_tester` |",
        "| Material bounded log corpus | `evidence_tester` |",
        "| Named unresolved cross-component boundary | `boundary_mapper` |",
        "| Required independent high-risk final gate | fresh `risk_reviewer` |",
        "| Material narrow read-only codebase question | built-in `explorer` leaf |",
        "| Scoped implementation or fix | built-in `worker` leaf |",
        "| Material dependency graph needing direct evidence handoff | built-in `default` bounded peer |",
        "| Any other, ambiguous, simple, resolved, mechanical, or open-ended class | Primary |",
        "An artifact request alone never qualifies a task.",
        "Acceptance fields define the evidence schema, not expected conclusions.",
        "never route because a prompt contains words copied from a role description",
        "A short single log, a small direct diagnosis, or a narrow test failure remains primary",
        "Governed custom roles are parent-routed leaves",
        "Built-in `explorer` and `worker` are leaves by default.",
        "one additional level to at most two",
        "Peer messages may carry only task-local evidence, dependency status, or an",
        "They cannot change authorization, scope, acceptance",
        "If the current client cannot prove nested spawn, direct messaging, permission",
        "fail closed to built-in leaves",
        "Start every already-qualified child whose bounded work is mutually independent",
        "Allow up to three active direct children by default",
        "a fourth requires explicit user authorization",
        "Allow at most one bounded-peer coordinator with two leaf descendants.",
        "Capacity alone never justifies delegation.",
        "Never serialize an already-qualified independent child solely because another child is slow.",
        "Add a newly discovered child only for new failure evidence",
        "Shared writes, migrations, dependent mutations, and final integration remain serial.",
        "no callable built-in equivalent exists",
        "fixed default effort is `xhigh`, independent of primary or built-in default effort",
        "Accept an `xhigh` PASS without a confidence-seeking rerun.",
        "For missing evidence, obtain the evidence or keep the gate blocked",
        "Start one fresh `risk_reviewer_max` only when the available evidence is sufficient",
        "the `xhigh` result is explicitly indeterminate because competing causal "
        "explanations or cross-boundary reasoning remain",
        "that ambiguity can change an irreversible P0/P1, security, authorization, or data-integrity decision",
        "fixed-`max` runtime variant of the same governance role",
        "never substitute `default` or another role for it",
        "Record the trigger and allow at most one `max` escalation.",
        "Complexity, file count, a high-risk label, an ordinary BLOCK, or a desire for more confidence never qualifies",
    ))
    require_markers(checks, evaluation, "evaluation policy", (
        "Apply this lexicographic order without weighted averaging",
        "Prefer higher stable verified quality.",
        "Never trade verified quality for lower credits.",
        "Record wall time only as telemetry",
        "Use the Standard/default service tier for this objective.",
        "multiplies GPT-5.6 ChatGPT credits by 2.5",
        "at least three materially different task instances",
        "Repeating one fixture measures stability only",
        "Freeze the role instructions, routing policy, task fixtures, and graders",
        "at least one sealed holdout instance per class",
        "A role instruction or eligibility change invalidates prior promotion evidence",
        "A topology-only scheduling change that preserves custom role instructions",
        "does not invalidate those role",
        "requires deterministic state-machine conformance plus a current",
        "a delayed child across",
        "bounded nested spawn and messaging",
        "authorized cancellation, and full-tree terminal collection",
        "A copied label, keyword, prescribed phrase, or checklist item earns no credit",
        "false blockers",
        "stable acceptance across distinct fixture families",
        "median aggregate custom credits at least 10% below baseline",
        "Retire an installed role with no promoted class.",
        "The 10% credit threshold governs elective custom promotion.",
        "mandatory named governance gate remains installed",
        "does not permit retention of any other unpromoted role.",
        "A reviewer-effort experiment never retires `risk_reviewer`",
        "returns the role to its last accepted fixed effort",
        "## Promoted registry",
        "Fresh `risk_reviewer`",
        "`risk_reviewer_max` is only its fixed-effort escalation",
        "fixture family, holdout seal, grader hash, contamination audit",
        "Report each instance before class aggregates",
        "Preserve original runs, sidecars, canonical receipts",
    ))
    require_markers(checks, delegation, "delegation contract", (
        "State hash: <revision or deterministic hashes>",
        "Transferred work: <raw work the primary will not repeat>",
        "Output audience: <user-facing | model-facing>",
        "Completion dependency: <required-before-integration | independent-before-final>",
        "Concurrent peers: <none | non-overlapping task names>",
        "User deadline: <none | explicit user condition>",
        "Cancellation authority: <user cancel/replace, concrete safety/scope violation",
        "Topology: <leaf | bounded-peer>",
        "Delegation depth: <0 | 1>",
        "Message peers: <none | task names + evidence/dependency purpose>",
        "Context policy: <fresh | inherited + material reason>",
        "Acceptance fields: <not-applicable | one or more exact output-heading labels>",
        "Named invariants: <not-applicable | one or more exact gate invariants>",
        "Escalation receipt: <not-applicable | prior terminal line + sufficient evidence",
        "Artifact contract: <none | path or body + format + writer + transfer rule>",
        "The four routing fields and four evidence fields are typed and must always be",
        "`not-applicable` and `none` are literal values, not permission to omit a field.",
        "The primary must set `Output audience` explicitly.",
        "For `user-facing` output, use the user's preferred language.",
        "For `model-facing` output, use English.",
        "Preserve requested schemas, literal values, source identifiers, and domain terms",
        "`Stop when` tells the child when to return evidence",
        "it does not authorize the primary to cancel a running turn",
        "A wait timeout, silence, elapsed wall time, token or credit use",
        "are non-terminal and are not stale-state evidence",
        "Terminal means a final receipt, an explicit runtime failure",
        "Track each task name, dependency, state hash, concurrent peers",
        "authorized cancellation reason until terminal",
        "Every spawned child must reach a terminal state before the primary ends.",
        "Do not start a replacement while the original remains running.",
        "continue independent work or wait again",
        "Use fresh context by default",
        "Inherit only the smallest history needed for material prior decisions",
        "For `Topology: leaf`, require depth zero and `Message peers: none`",
        "For `Topology: bounded-peer`, require a collaboration-capable built-in route",
        "at most two leaf descendants",
        "Messages transfer evidence or dependency status only; they never amend a handoff.",
        "Preserve one writer per path.",
        "the primary samples but does not rewrite it",
        "ARTIFACT_BODY_BEGIN",
        "Never translate, reorder, or summarize a canonical body",
        "A gate receipt ends with exactly one standalone terminal protocol line.",
        "Without an artifact body it is the final non-empty line.",
        "final non-empty line before `ARTIFACT_BODY_END`",
        "nothing may follow except that marker",
        "The primary always owns authorization, conflict handling, integration, and final acceptance.",
        "Every custom role remains a non-recursive governed leaf.",
        "## Portable adapter contract",
        "`preserve-role-eligibility`",
        "`preserve-permission-boundaries`",
        "`preserve-governed-leaf-non-recursion`",
        "`preserve-bounded-peer-depth`",
        "`preserve-peer-message-boundary`",
        "`preserve-terminal-collection`",
        "`preserve-output-language-contract`",
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
    checks.require(len(skill.splitlines()) <= 60, "SKILL.md exceeds 60-line noise budget")
    for relative, text in (
        ("routing-policy.md", routing),
        ("evaluation-policy.md", evaluation),
        ("delegation-contracts.md", delegation),
    ):
        checks.require(len(text.splitlines()) <= 110, f"{relative} exceeds 110-line noise budget")
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

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
        "acceptance-field label verbatim as an output heading",
        "Account for benign and negative cases",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "200 words",
    ),
    "boundary_mapper": (
        "Confirmed test gaps",
        "Preserve source-code identifiers and domain terms verbatim",
        "Derive the ordered trace from real call and state edges",
        "do not treat a label or mentioned term as proof",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "ARTIFACT_BODY_BEGIN",
        "1200 words",
    ),
    "risk_reviewer": (
        "claims inferred only from acceptance-field wording",
        "concrete mechanism, consequence, implementation-specific required control",
        "For a pass, identify the positive implementation and test evidence",
        "Do not invent a blocker outside the named invariants",
        "Gate recommendation: PASS",
        "Gate recommendation: BLOCK / NO-GO",
        "Gate recommendation: INDETERMINATE / ESCALATE",
        "available evidence is sufficient",
        "at most one fresh `max` review",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "Keep the terminal protocol line exactly as specified above",
        "ARTIFACT_BODY_BEGIN",
        "1500 words",
    ),
    "risk_reviewer_max": (
        "claims inferred only from acceptance-field wording",
        "concrete mechanism, consequence, implementation-specific required control",
        "For a pass, identify the positive implementation and test evidence",
        "Do not invent a blocker outside the named invariants",
        "Gate recommendation: PASS",
        "Gate recommendation: BLOCK / NO-GO",
        "Gate recommendation: INDETERMINATE / ESCALATE",
        "available evidence is sufficient",
        "at most one fresh `max` review",
        "Follow the handoff's `Output audience` field",
        "For `user-facing` output, use the user's preferred language",
        "For `model-facing` output, use English",
        "Keep the terminal protocol line exactly as specified above",
        "ARTIFACT_BODY_BEGIN",
        "1500 words",
    ),
}
ROLE_INSTRUCTION_SHA256 = {
    "evidence_tester": "19eac606502ec8a992609a2412bfb5f605d8923741c23002252d38c9f52cceef",
    "boundary_mapper": "64b03cd483aa01e2c1a250d1d9beafc9e07dd0b7c480587305ae603090ae7aed",
    "risk_reviewer": "5041eb578a31c89e4492fc1c3f311c8db41afded23aaa9ebbb5655963d262749",
    "risk_reviewer_max": "5041eb578a31c89e4492fc1c3f311c8db41afded23aaa9ebbb5655963d262749",
}
REFERENCE_SHA256 = {
    "routing-policy.md": "0d0855ddb0786b88ed6fa64f9c1c44fd81b28e2e154c061749b8e7241eb80449",
    "evaluation-policy.md": "38fa07a6215427bbdf6949b050c19e0d39e3bd7ed39a879505c378ca660f13b4",
    "delegation-contracts.md": "3e788b74d89d356823dd46374e409b7b0bb8041dd8c23c1ac9a5ec51baad7352",
}
SKILL_SHA256 = "5b1b53b90fff700d9bb803e87050db285b13d353eae029f6a9088253364827dc"
GLOBAL_POLICY_SHA256 = {
    "## Subagents and parallelism": "57ac581a53881ce2152755d425c4e4c9e3608c29fd4257d500e1c7677aca467f",
    "## 子代理与并行": "37d9a41d324d5fbc259baf8f893288aaef70003b0259b6de95b6ab0a76e392e2",
}
GLOBAL_POLICY_MARKERS = {
    "## Subagents and parallelism": (
        "Default to a single agent",
        "Use `$subagent-orchestrator` only",
        "mutually independent and have non-overlapping ownership",
        "Do not delegate to fill capacity",
        "new failure evidence, an unresolved boundary, or a required final gate",
        "The primary retains authorization, scope, single-writer integration, synthesis, and final acceptance",
        "children cannot expand authority or delegate recursively",
        "High-risk final states require a fresh, independent, read-only review",
        "own the objective, eligibility, model settings, artifact handoff, and promotion evidence",
        "revalidates the final workspace",
        "one wait timeout, silence, elapsed time, or token/credit use is not a cancellation reason",
    ),
    "## 子代理与并行": (
        "默认单代理",
        "使用 `$subagent-orchestrator`",
        "可并行启动已分别满足资格、相互独立且所有权不重叠的最窄角色",
        "不得为占满并发槽而委派",
        "后续增派仍须由新的失败证据、未解边界或必需最终门禁触发",
        "主代理保留授权、范围、单一写入者、整合与最终验收",
        "子代理不得扩权或递归委派",
        "高风险最终状态必须接受 fresh、独立、只读审阅",
        "分别维护",
        "按最终工作区重新验收",
        "单次等待超时、静默、耗时或 token/credit 使用均不是中断依据",
    ),
}
LIFECYCLE_ASSET_SHA256 = {
    "scripts/lifecycle_conformance.py": "20f079efefc871617e83abf6c047433d9ab9e840a784fc53e156dabbfa45371b",
    "tests/fixtures/lifecycle-trace.json": "8c7f78eb4ad50173cf66cedca114d1273a4fb33f602e2a54a87ead00786ca94c",
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
        "Route and supervise explicit subagent requests and evidence-backed specialist work.",
        "Preserve required children to terminal unless cancellation is authorized.",
        "Keep this file as the workflow entrypoint.",
        "Start primary-only.",
        "If neither substitution nor required independence is present, stay primary.",
        "Before selecting any custom role, read the objective and promoted registry",
        "Keep unsupported or unstable classes on primary/default.",
        "Create one task-local handoff",
        "Start every already-qualified, mutually independent child allowed by the routing policy",
        "never create filler work merely to occupy capacity",
        "wait for every required child to reach a terminal state",
        "Treat a wait timeout as observation-only",
        "not as failure, a stall, or permission to interrupt",
        "If a child remains running, report useful progress",
        "and wait again",
        "Never interrupt or replace a child for silence, elapsed wall time, token or credit use",
        "Never start a replacement while the original is running.",
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
        "| Any other, ambiguous, simple, resolved, mechanical, or open-ended class | Primary/default |",
        "An artifact request alone never qualifies a task.",
        "Acceptance fields define the evidence schema, not expected conclusions.",
        "never route because a prompt contains words copied from a role description",
        "A short single log, a small direct diagnosis, or a narrow test failure remains primary/default",
        "Start every already-qualified child whose bounded work is mutually independent",
        "Allow up to three active custom children by default",
        "a fourth requires explicit user authorization",
        "Capacity alone never justifies delegation.",
        "Never serialize an already-qualified independent child solely because another child is slow.",
        "Add a newly discovered child only for new failure evidence",
        "Shared writes remain serial.",
        "no callable built-in equivalent exists",
        "fixed default effort is `xhigh`, independent of the primary/default effort",
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
        "A lifecycle-only scheduling change that preserves role instructions, eligibility",
        "requires targeted state-machine conformance rather than class re-promotion",
        "a delayed child across multiple wait windows, an independent peer",
        "authorized cancellation, and terminal collection",
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
        "fork_turns=\"none\"",
        "Preserve one writer per path.",
        "the primary samples but does not rewrite it",
        "ARTIFACT_BODY_BEGIN",
        "Never translate, reorder, or summarize a canonical body",
        "The primary always owns authorization, conflict handling, integration, and final acceptance.",
        "Every custom role is non-recursive.",
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
        len(re.findall(r"(?m)^- ", global_agents_policy)) == 3,
        f"{label} must contain exactly three bullets",
    )
    checks.require(
        len(global_agents_policy.splitlines()) <= 4,
        f"{label} exceeds four-line global policy budget",
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
        checks.require(len(text.splitlines()) <= 100, f"{relative} exceeds 100-line noise budget")
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
    print("- concurrency: up to three qualified custom children; configured thread cap 16")
    print("- lifecycle: wait timeouts are non-terminal; required children are collected")
    print("- lifecycle conformance: exact-hash trace and negative transitions passed")
    print("- objective: verified quality first; end-to-end credits second")
    print("- wall time: telemetry only")
    print("- unsupported classes: primary/default; no dormant custom roles installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate static subagent routing configuration without claiming host enforcement."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
import sys
import tomllib


SKILL_NAME = "subagent-orchestrator"
DEFAULT_SKILL_PATH = Path(__file__).resolve().parents[1] / "SKILL.md"
ROLE_POLICY = {
    "evidence_tester": ("gpt-5.6-luna", "max", "default", "workspace-write"),
    "boundary_mapper": ("gpt-5.6-terra", "max", "default", "read-only"),
    "risk_reviewer": ("gpt-5.6-sol", "xhigh", "default", "read-only"),
    "risk_reviewer_max": ("gpt-5.6-sol", "max", "default", "read-only"),
}
ROLE_INSTRUCTION_SHA256 = {
    "evidence_tester": "e8cfc06d58025b75a15b2075cbdac7fd3918ab40ea972f3cda08d18e8ec16aec",
    "boundary_mapper": "73ff8065f8832480bb29fe64c302982680709b37a6514abd207dfda982a86507",
    "risk_reviewer": "8367775e01048b9aead6deb1451b4d15d7ffe54a888da124f18253ec5969ada0",
    "risk_reviewer_max": "c0b8897de75314993270c6ae4f4a41cff7c42ccc4b057bd9d417c47b7233b90f",
}
ROLE_MARKERS = {
    "evidence_tester": ("Acceptance fields", "Artifact contract"),
    "boundary_mapper": ("Acceptance fields", "Artifact contract"),
    "risk_reviewer": ("Named invariants", "Escalation receipt"),
    "risk_reviewer_max": ("Named invariants", "Escalation receipt"),
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
    "tests/test_validate_routing_config.py",
)
GLOBAL_POLICY_MARKERS = {
    "## Subagents and parallelism": (
        "Default to a single agent",
        "If the primary would mainly coordinate, poll, or wait",
        "ordinary first wave has at most two leaf children",
        "at most one active writer with no overlapping write scopes",
        "opens an expansion checkpoint and cannot spawn automatically",
        "Proceed only under exact current user authorization",
        "before a later wave, collect every current required child to terminal state and integrate its receipt",
        "ask one recommended-default question only for a material user-owned",
        "one batch of at most three reviewers with disjoint invariants",
        "report operational blockers instead of posing them as preferences",
        "Freeze for review only after all writers are terminal",
        "any relevant state change invalidates prior gate results",
        "Reviewers inspect only that state and the named invariants",
        "another BLOCK stops further review",
        "child terminal state or a spent delegation budget does not prove task completion",
        "Static harness checks never prove host enforcement or production efficiency",
    ),
    "## 子代理与并行": (
        "默认单代理",
        "主代理主要只剩编排、轮询或等待",
        "普通首轮最多两个叶子子代理",
        "同时最多一个写入者且写入范围不得重叠",
        "进入编排扩张检查点，禁止自动派生",
        "当前用户指令已精确授权该次扩张",
        "开始后续轮次前必须先收齐当前所有必需子代理的终态并整合其收据",
        "用户拥有的重大取舍",
        "一批最多三个、invariant 互斥的 reviewer",
        "不得伪装成用户偏好",
        "只有所有写入者终态且主代理完成整合后才能冻结评审状态",
        "任何相关状态变化都会使已有门禁结论失效",
        "Reviewer 只审该状态和命名 invariant",
        "仍有 BLOCK 就停止继续评审",
        "子代理终态或编排预算耗尽都不证明任务完成",
        "静态 harness 检查不得冒充宿主强制或生产效率证明",
    ),
}


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


def require_markers(checks: Checks, text: str, label: str, markers: tuple[str, ...]) -> None:
    normalized = " ".join(text.split())
    for marker in markers:
        checks.require(
            " ".join(marker.split()) in normalized,
            f"{label} missing policy text: {marker}",
        )


def markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def validate_config(checks: Checks, codex_home: Path) -> None:
    config_path = codex_home / "config.toml"
    checks.require(config_path.is_file(), f"missing config: {config_path}")
    if not config_path.is_file():
        return
    agents = load_toml(config_path).get("agents", {})
    expected = {
        "enabled": True,
        "max_concurrent_threads_per_session": 16,
        "interrupt_message": True,
        "default_subagent_model": "gpt-5.6-sol",
        "default_subagent_reasoning_effort": "high",
    }
    for key, value in expected.items():
        checks.require(agents.get(key) == value, f"agents.{key} must be {value}")


def validate_roles(checks: Checks, codex_home: Path, configured_skill_path: Path) -> None:
    agents_dir = codex_home / "agents"
    installed = {path.stem for path in agents_dir.glob("*.toml")} if agents_dir.is_dir() else set()
    checks.require(not (set(ROLE_POLICY) - installed), "agent catalog is missing a required role")
    checks.require(not (installed & LEGACY_ROLE_NAMES), "legacy roles must not be installed")
    for role, (model, effort, tier, sandbox) in ROLE_POLICY.items():
        path = agents_dir / f"{role}.toml"
        if not path.is_file():
            continue
        data = load_toml(path)
        instructions = data.get("developer_instructions", "")
        checks.require(data.get("name") == role, f"{role}: name mismatch")
        checks.require(data.get("model") == model, f"{role}: model mismatch")
        checks.require(data.get("model_reasoning_effort") == effort, f"{role}: effort mismatch")
        checks.require(data.get("service_tier") == tier, f"{role}: service tier mismatch")
        checks.require(data.get("sandbox_mode") == sandbox, f"{role}: sandbox mismatch")
        require_markers(checks, instructions, role, ROLE_MARKERS[role])
        checks.require(
            "Do not spawn agents or widen scope." in instructions,
            f"{role}: recursion and scope expansion must be disabled",
        )
        checks.require(
            hashlib.sha256(instructions.encode()).hexdigest() == ROLE_INSTRUCTION_SHA256[role],
            f"{role}: developer_instructions integrity mismatch",
        )
        skill_config = data.get("skills", {}).get("config", [])
        checks.require(
            any(
                item.get("path") == str(configured_skill_path) and item.get("enabled") is False
                for item in skill_config
            ),
            f"{role}: must disable the parent orchestration skill",
        )


def validate_policy(checks: Checks, codex_home: Path) -> None:
    skill_dir = codex_home / "skills" / SKILL_NAME
    for relative in REQUIRED_SKILL_FILES:
        checks.require((skill_dir / relative).is_file(), f"missing skill file: {relative}")
    derived = [
        str(path.relative_to(skill_dir))
        for path in skill_dir.rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    ] if skill_dir.is_dir() else []
    checks.require(not derived, f"skill tree contains undeclared Python bytecode: {derived}")

    def read(relative: str) -> str:
        path = skill_dir / relative
        return path.read_text() if path.is_file() else ""

    skill = read("SKILL.md")
    routing = read("references/routing-policy.md")
    delegation = read("references/delegation-contracts.md")
    evaluation = read("references/evaluation-policy.md")
    yaml_text = read("agents/openai.yaml")
    agents_path = codex_home / "AGENTS.md"
    agents_text = agents_path.read_text() if agents_path.is_file() else ""

    require_markers(checks, skill, "SKILL.md", (
        "name: subagent-orchestrator",
        "Prove the monkey before building the pedestal",
        "Start primary-only",
        "If the primary would mostly coordinate, poll, or wait",
        "Keep at most one active writer and never overlap write scopes",
        "Treat a second delegation wave",
        "Freeze new spawns",
        "latest explicit user instruction already authorizes that exact expansion",
        "Before a later wave, collect every current required child to terminal state",
        "Ask one question only when evidence cannot choose",
        "do not pose them as preferences",
        "After two decision-directed agent attempts",
        "Freeze a candidate only after all writers are terminal",
        "Any relevant state change invalidates prior gate results",
        "A reviewer is a terminal gate, not a continuing designer",
        "Repair original-acceptance blockers once",
        "stop further review",
        "Static policy tests prove only local consistency",
        "do not prove that the host enforced the policy or that production became faster",
        "A candidate is not active until the target installation and client readback prove it was loaded",
        "A terminal child or exhausted delegation budget proves neither task completion",
    ))
    require_markers(checks, routing, "routing policy", (
        "Every child is a leaf",
        "at most two children in the ordinary first wave",
        "Keep at most one active writer",
        "reviewer rerun opens an expansion checkpoint",
        "latest explicit user instruction authorizes that exact expansion",
        "Before a later wave, collect every current required child to terminal state",
        "do not turn it into a preference question",
        "another BLOCK stops further review",
        "Child terminal state or a spent delegation budget is not task closure",
        "Freeze for review only after every writer is terminal",
        "any relevant change invalidates the result",
        "A reviewer finding outside the named invariants is a deferred observation",
        "Do not build a new harness, schema, authority system, installer feature, or policy engine",
    ))
    require_markers(checks, delegation, "delegation contract", (
        "Objective: <one bounded outcome>",
        "Owned scope: <exact paths, artifact, or read-only surface>",
        "Use `followup_task` only once",
        "Never use either tool for status polling, reviewer redesign, or scope expansion",
        "Keep one active writer and no overlapping write scopes",
        "Before a later wave, collect every current required child to terminal state",
        "authorization must name that exact expansion",
        "closes only the transferred work, not the user task",
    ))
    require_markers(checks, evaluation, "evaluation policy", (
        "Monkey before pedestal",
        "Routine skill use does not require a new benchmark campaign",
        "Minimal efficiency receipt",
        "An expansion checkpoint prohibits automatic spawning",
        "Report operational blockers with the next owner or action",
        "A later wave is not admissible until current required children are terminal",
        "a relevant state change invalidates it",
        "Reviewer scope is frozen with the named invariants",
        "Reviewer-driven redesign must not continue autonomously",
        "is not task completion",
        "do not build another measurement framework",
    ))

    sections = [
        (heading, body)
        for heading in GLOBAL_POLICY_MARKERS
        if (body := markdown_section(agents_text, heading))
    ]
    checks.require(len(sections) == 1, "AGENTS.md must contain one subagent policy section")
    if len(sections) == 1:
        heading, body = sections[0]
        require_markers(checks, body, f"AGENTS.md {heading}", GLOBAL_POLICY_MARKERS[heading])
        checks.require(len(re.findall(r"(?m)^- ", body)) == 3, "AGENTS.md policy must contain three bullets")

    checks.require(len(skill.splitlines()) <= 100, "SKILL.md exceeds 100-line budget")
    for relative, text in (
        ("routing-policy.md", routing),
        ("delegation-contracts.md", delegation),
        ("evaluation-policy.md", evaluation),
    ):
        checks.require(len(text.splitlines()) <= 90, f"{relative} exceeds 90-line budget")
    checks.require('display_name: "Subagent Orchestrator"' in yaml_text, "openai.yaml display name mismatch")
    checks.require(
        'short_description: "Efficient delegation with bounded expansion"' in yaml_text,
        "openai.yaml short description mismatch",
    )
    checks.require(
        'default_prompt: "Use $subagent-orchestrator' in yaml_text,
        "openai.yaml default prompt mismatch",
    )
    checks.require(
        re.findall(r"(?m)^\s*allow_implicit_invocation:\s*(true|false)\s*$", yaml_text) == ["true"],
        "implicit invocation must appear exactly once and remain true",
    )
    active_contract = "\n".join((skill, routing, delegation, evaluation, yaml_text, agents_text))
    for legacy in LEGACY_ROLE_NAMES:
        checks.require(legacy not in active_contract, f"active policy contains legacy role name: {legacy}")


def validate(codex_home: Path, configured_skill_path: Path) -> Checks:
    checks = Checks()
    validate_config(checks, codex_home)
    validate_roles(checks, codex_home, configured_skill_path)
    validate_policy(checks, codex_home)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--configured-skill-path", type=Path, default=DEFAULT_SKILL_PATH)
    args = parser.parse_args()
    checks = validate(args.codex_home.resolve(), args.configured_skill_path.resolve())
    if checks.errors:
        print(f"FAIL: {len(checks.errors)} error(s) across {checks.count} static checks")
        for error in checks.errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {checks.count} static routing configuration checks")
    print("- default: primary; ordinary first wave: two leaf children; one active writer")
    print("- expansion checkpoint: no automatic second wave, writer addition, scope growth, or reviewer rerun")
    print("- wave boundary: current required children terminal and integrated before another wave")
    print("- user question: one recommended default for a material user-owned choice only")
    print("- reviewer boundary: integrated frozen state, one repair batch, one fresh recheck")
    print("- closure boundary: child terminal state and spent budget are not task completion")
    print("- evidence boundary: static consistency only; no host or production-efficiency claim")
    return 0


if __name__ == "__main__":
    sys.exit(main())

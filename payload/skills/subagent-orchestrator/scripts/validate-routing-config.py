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
    "boundary_mapper": ("gpt-5.6-sol", "high", "default", "read-only"),
    "risk_reviewer": ("gpt-5.6-sol", "xhigh", "default", "read-only"),
    "risk_reviewer_max": ("gpt-5.6-sol", "max", "default", "read-only"),
}
ROLE_INSTRUCTION_SHA256 = {
    "evidence_tester": "e8ff40f7d9370bb0ac1f3de441e9408a6c449e1954eec4c6cedae02a0dac1148",
    "boundary_mapper": "8a99a6ef48dac961f11854ce1951ccb0bbdcaee2bf2cf98189b4bfe377b0e96d",
    "risk_reviewer": "2aea5e623cc7d1897852c38cf443fcfaff9c5f4ae4749e3bf7bb5f45c8ea191b",
    "risk_reviewer_max": "1b98b4aa01a69daf251f59396d76daa707b9e8681bf80df7a75ddfca854a97a6",
}
ROLE_MARKERS = {
    "evidence_tester": (
        "Acceptance fields",
        "Artifact contract",
        "only write scope",
        "Accept at most one primary",
        "English receipt",
    ),
    "boundary_mapper": (
        "Acceptance fields",
        "Artifact contract",
        "Accept at most one primary",
        "Return English prose",
    ),
    "risk_reviewer": (
        "Named invariants",
        "Escalation receipt",
        "`Artifact contract` is `none`",
        "Try to falsify every invariant",
        "Report PASS or BLOCK for every invariant",
        "do not use not-applicable for an admitted invariant",
        "Return English prose",
    ),
    "risk_reviewer_max": (
        "Named invariants",
        "Escalation receipt",
        "`Artifact contract` is `none`",
        "Try to falsify each surviving explanation",
        "report PASS or BLOCK",
        "do not use not-applicable for an admitted invariant",
        "Return English prose",
    ),
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
        "Use `$subagent-orchestrator` only",
        "Prefer direct or batched tools for small work",
        "primary would mainly coordinate, poll, or wait",
        "primary retains authorization, scope, integration, finding adjudication, and final acceptance",
        "Children remain leaves",
        "when delegation is admitted, start one child",
        "at most one active writer with no overlapping write scopes",
        "use installed model and effort settings",
        "immutable leaf boundaries",
        "Follow the Skill for role admission",
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
        "max_concurrent_threads_per_session": 3,
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
        if role in {"evidence_tester", "boundary_mapper"}:
            checks.require(
                "Do not spawn agents, initiate agent messages, or widen scope."
                in instructions,
                f"{role}: recursion, outgoing messaging, and scope expansion must be disabled",
            )
            checks.require(
                "Accept at most one primary `send_message` or `followup_task`" in instructions,
                f"{role}: bounded primary update contract is missing",
            )
        else:
            checks.require(
                "Do not spawn or message agents." in instructions,
                f"{role}: recursion and messaging must be disabled",
            )
            checks.require(
                "Do not accept follow-up work" in instructions,
                f"{role}: review input must reject follow-up work",
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
        "hardest user-relevant behavior",
        "Start primary-only",
        "Prefer direct or batched tools for small work",
        "Require English model-facing receipts",
        "finding adjudication",
        "Set an explicit non-`default` `agent_type` on every spawn",
        "`fork_turns: \"none\"`",
        "never omit it or inherit full history",
        "Never omit it or spawn the built-in `default`",
        "When delegation is admitted, start one child",
        "ordinary cap at two children and one active writer",
        "Never allow child delegation or peer messaging",
        "expansion checkpoint cannot relax recursion, ownership, write-scope, or freshness rules",
        "as an expansion checkpoint",
        "Freeze new spawns, collect and integrate",
        "Clear the checkpoint without asking only when",
        "Ask before consequential work when the user requested a checkpoint or evidence leaves",
        "Treat user corrections and brake feedback as invalidating conflicting plan inertia",
        "do not disguise them as preferences",
        "Allow at most one primary-to-leaf update",
        "Never update a review role",
        "After two decision-directed attempts",
        "Treat adversarial review as an attempt to falsify",
        "Limit explicit multi-review to one batch",
        "Freeze only after all writers are terminal",
        "Invalidate all prior gate results after any relevant change",
        "Treat a reviewer as an evidence gate, not a designer",
        "Adjudicate every finding in the primary",
        "stop the automatic review loop and return to first principles",
        "treat another fresh review as a new expansion checkpoint",
        "unchanged BLOCK is an evidence plateau",
        "Treat static policy tests as local consistency evidence only",
        "loading, not production efficiency",
        "Use installed child model and effort settings without per-task retuning",
        "reject an omitted, resolved `default`, or full-history result",
        "without automatically respawning",
        "Close only with claim-matched evidence for the original outcome",
        "Do not add a harness, schema, installer feature, authority system, reviewer hierarchy",
    ))
    require_markers(checks, routing, "routing policy", (
        "Keep every child a leaf",
        "Set an explicit non-`default` `agent_type` on every spawn",
        "Never route to the built-in `default`",
        "General-purpose or unmatched fallback",
        "primary, no spawn",
        "Do not substitute roles",
        "Follow valid transitions",
        "only the primary settle strategy",
        "Use `evidence_tester` before or after implementation",
        "primary sampling, integration, and direct checks",
        "Return a review BLOCK to the primary for independent adjudication",
        "When delegation is admitted, start one child",
        "ordinary cap at two children and one active writer",
        "Prohibit child delegation and peer messaging",
        "expansion checkpoint never relaxes leaf topology",
        "Permit at most one primary update to an operational leaf",
        "Keep review roles isolated from messages and follow-ups",
        "keep the primary model and effort user-controlled",
        "Set `fork_turns` to `\"none\"`",
        "never inherit full history",
        "Use English receipts",
        "Ask when the user requested a checkpoint or at a material user-owned boundary",
        "Expansion alone is not a question",
        "Use multi-review only for an explicit user request",
        "no voting, and no design workshop",
        "expansion checkpoint for another independent review",
        "changed candidate or new discriminating evidence",
        "evidence plateau",
        "Do not build supporting machinery before the smallest real task proves the core behavior",
    ))
    require_markers(checks, delegation, "delegation contract", (
        "Spawn: agent_type=<explicit non-default role>; fork_turns=none",
        "Task: <one bounded outcome>",
        "Scope: <exact paths, artifact, or read-only surface>",
        "Return: <English receipt or artifact and observable done condition>",
        "Add only the selected role's fields",
        "Bind every spawn to the declared non-`default` `agent_type`",
        "`fork_turns: \"none\"`",
        "Never inherit full history",
        "If no specialized role fits, do not spawn",
        "Artifact contract` naming its path, format, and receipt rule",
        "Do not include expected conclusions, full history, repeated policy",
        "prohibit delegation or peer messaging",
        "Keep one active writer and no overlapping write scopes",
        "Do not treat an existing handoff or expansion checkpoint as authorization for recursion",
        "Allow at most one primary-to-leaf update",
        "Use `followup_task` only for a missing acceptance field or new failure evidence",
        "Never send either update to `risk_reviewer` or `risk_reviewer_max`",
        "closure of transferred work only",
        "finding adjudication",
    ))
    require_markers(checks, evaluation, "evaluation policy", (
        "Prove the monkey first",
        "prove it on the smallest representative task",
        "Do not benchmark routine Skill use",
        "Record the minimum evidence",
        "omitted or non-`none` `fork_turns` as a routing failure",
        "Freeze spawning at an expansion checkpoint",
        "Clear one bounded next child only after",
        "Never relax leaf, ownership, write-scope, or freshness rules",
        "Ask when the user requested a checkpoint or evidence leaves a material user-owned",
        "Accept review evidence only for a frozen integrated candidate",
        "reviewer wording is not authority",
        "before reviewing again after one repair and fresh recheck",
        "Do not treat a child, gate line, install, or exhausted budget as task completion",
        "Close against the original outcome",
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
        checks.require(len(re.findall(r"(?m)^- ", body)) == 2, "AGENTS.md policy must contain two bullets")

    checks.require(len(skill.splitlines()) <= 120, "SKILL.md exceeds 120-line budget")
    for relative, text in (
        ("routing-policy.md", routing),
        ("delegation-contracts.md", delegation),
        ("evaluation-policy.md", evaluation),
    ):
        checks.require(len(text.splitlines()) <= 90, f"{relative} exceeds 90-line budget")
    checks.require('display_name: "Subagent Orchestrator"' in yaml_text, "openai.yaml display name mismatch")
    checks.require(
        'short_description: "Bounded delegation with primary-owned decisions"' in yaml_text,
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
    print("- fallback: built-in default is never spawned; unmatched work remains primary")
    print("- admission: explicit non-default agent_type; then one child; two only for qualified parallel work")
    print("- context: fork_turns none; full parent history is never inherited")
    print("- runtime: three spawned threads; installed child model/effort matrix; one active writer")
    print("- expansion checkpoint: re-anchor, integrate, then clear one bounded child or ask at a material boundary")
    print("- wave boundary: current required children terminal and integrated before another wave")
    print("- user question: one recommended default for a material user-owned boundary only")
    print("- reviewer boundary: frozen evidence gate; primary adjudication; no reviewer-owned design loop")
    print("- closure boundary: child terminal state and spent budget are not task completion")
    print("- evidence boundary: static consistency only; no host or production-efficiency claim")
    return 0


if __name__ == "__main__":
    sys.exit(main())

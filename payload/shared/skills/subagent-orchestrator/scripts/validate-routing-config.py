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
    "en": {
        "evidence_tester": "19966e680d5b04d60fce57b059b8fd76011c688e2cd4e012f746f56ab8c6963a",
        "boundary_mapper": "8571ea1da38108b33d1ea79bb673884294f6c10b6decd8359e09e1e456c48fcb",
        "risk_reviewer": "a11c0542dc449c0c36c504cfe086e1d30177b5d0c11743170f46009ab09bb310",
        "risk_reviewer_max": "8fe439c76ed3e7e5ce4f9fe0be710ac2b027eddcd697977f1e737ea2b2fc45cb",
    },
    "zh": {
        "evidence_tester": "df7bee545d075994cfd58f8f8913a01f20dc059518a52dc9db4289a807cd9ae0",
        "boundary_mapper": "e9e7bd172d9596fa1edd082dcc1c6cce02bccc7b5db870a8d567278dcb0615b1",
        "risk_reviewer": "f5d77a7a318874cc44ac5b22470ba95007aaf7f48a39bbc8f5d594c418b55b44",
        "risk_reviewer_max": "79a9886988a268708372d466d3884a8fe4cb3d4d6b16d3506a374ebb4a512b01",
    },
}
ROLE_MARKERS = {
    "en": {
        "evidence_tester": (
            "Acceptance fields",
            "Artifact contract",
            "only write scope",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "English receipt",
        ),
        "boundary_mapper": (
            "Acceptance fields",
            "Artifact contract",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "Return English prose",
        ),
        "risk_reviewer": (
            "Named invariants",
            "Candidate receipt",
            "Escalation receipt",
            "`Artifact contract` is `none`",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "Try to falsify every invariant",
            "Report PASS or BLOCK for every invariant",
            "do not use not-applicable for an admitted invariant",
            "Return English prose",
        ),
        "risk_reviewer_max": (
            "Named invariants",
            "Candidate receipt",
            "Escalation receipt",
            "`Artifact contract` is `none`",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "Try to falsify each surviving explanation",
            "report PASS or BLOCK",
            "do not use not-applicable for an admitted invariant",
            "Return English prose",
        ),
    },
    "zh": {
        "evidence_tester": (
            "Acceptance fields",
            "Artifact contract",
            "唯一写入范围",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "英文收据",
        ),
        "boundary_mapper": (
            "Acceptance fields",
            "Artifact contract",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "返回英文正文",
        ),
        "risk_reviewer": (
            "Named invariants",
            "Candidate receipt",
            "Escalation receipt",
            "`Artifact contract` 为 `none`",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "尝试证伪每个不变量",
            "PASS 或 BLOCK",
            "已准入的不变量不得使用 not-applicable",
            "返回不超过 600 个词的英文正文",
        ),
        "risk_reviewer_max": (
            "Named invariants",
            "Candidate receipt",
            "Escalation receipt",
            "`Artifact contract` 为 `none`",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "尝试证伪每个仍成立的解释",
            "PASS 或 BLOCK",
            "已准入的不变量不得使用 not-applicable",
            "返回不超过 700 个词的英文正文",
        ),
    },
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
    "en": {
        "## Subagents and parallelism": (
            "Default to the primary",
            "user explicitly requests delegation",
            "bounded independent leaf can replace material primary work or isolate a large noisy evidence stream",
            "Keep small, sequential, ambiguous, shared-mutable-state, and coordination-heavy work with the primary",
            "primary always retains authorization, scope, single-writer integration, finding adjudication, and final acceptance",
            "Children are ownership-bounded leaves: start one",
            "ordinary first wave to at most two",
            "at most one active writer with no overlapping write scopes",
            "Follow the Skill for role selection, context forks, handoffs, expansion checkpoints, reviews, and evidence-based closure",
        ),
    },
    "zh": {
        "## 子代理与并行": (
            "默认由主代理完成",
            "用户明确要求委派",
            "有界独立叶子能替代主代理的实质工作或隔离大量噪声证据",
            "小型、顺序性、含糊、共享可变状态或协调成本高的工作留给主代理",
            "主代理始终保留授权、范围、单一写入者整合、审查发现裁决和最终验收权",
            "子代理必须是所有权有界的叶子：先启动一个",
            "普通首轮最多两个",
            "最多一个活动写入者、写入范围不重叠",
            "角色选择、上下文分叉、交接、扩展检查点、审查和基于证据的收尾遵循该 Skill",
        ),
    },
}
POLICY_MARKERS = {
    "en": {
        "skill": (
            "name: subagent-orchestrator",
            "Optimize the user's requested result, not agent activity",
            "final deliverable, its acceptance conditions, and its important constraints",
            "hardest user-relevant behavior",
            "Start with the primary",
            "Prefer direct or batched tools for small work",
            "Select a named `agent_type` from the host's available role descriptions",
            "Do not deliberately route unmatched work to `default`",
            "Use the custom roles only for their exact purpose",
            "Set the selected role in the orchestration call",
            "do not discard it solely because its role metadata is omitted or `default`",
            "When delegation is admitted, start one child",
            "ordinary cap is two children and one active writer",
            "Every child remains a leaf",
            "smallest task-local context fork",
            "Collect and integrate current required receipts first",
            "Clear at most one next child without asking only when",
            "A checkpoint never relaxes leaf, ownership, write-scope, or freshness rules",
            "If a denied or stale authorization affects only a nonessential action",
            "If the action is required for the assigned outcome",
            "one terminal `approval-blocked` receipt",
            "do not disguise them as preferences",
            "After two decision-directed attempts",
            "Any relevant change invalidates prior gate results",
            "compact matrix",
            "candidate receipt",
            "Treat a reviewer as an evidence gate, not a designer or requirements source",
            "contract retry, not an effective review",
            "The primary adjudicates every finding",
            "stop the automatic review loop and return to first principles",
            "Use `risk_reviewer_max` only through the escalation route",
            "Treat policy tests as local consistency evidence only",
            "loading, not production efficiency",
            "Use installed child model and effort settings without per-task retuning",
            "Close only with claim-matched evidence for the acceptance anchor",
            "Do not add a harness, schema, installer feature, authority system, reviewer hierarchy",
            "Read the [advanced routing policy]",
            "only for a second child, later wave, custom-role transition, or review",
            "it does not govern routine Skill execution",
        ),
        "routing": (
            "supplements the Skill and never widens",
            "only the primary settles strategy",
            "Use only when one artifact meaningfully isolates raw evidence",
            "return evidence, not a design verdict",
            "A valid reviewer escalation supplies every field in the delegation contract",
            "Do not substitute roles or route unmatched work to built-in `default`",
            "Review BLOCK returns to the primary for adjudication",
            "Preserve the ordinary cap of two children, one active writer",
            "Expansion alone is not a user question",
            "Multi-review requires an explicit user request",
            "changed candidate or new discriminating evidence",
            "evidence plateau",
            "missing-field rejection is a contract retry, not an effective review",
            "Choose context for freshness, not model routing",
            "repeated waits show no state change",
            "Use English receipts",
            "`sandbox_mode` as requested configuration, not hard authority",
            "parent overrides may change actual access",
        ),
        "delegation": (
            "Set `agent_type` in the orchestration call; do not repeat it as a handoff field",
            "Task: <one bounded result>",
            "Scope: <exact paths, artifact, or read-only surface>",
            "Return: <English receipt or artifact and observable done condition>",
            "Add only the selected role's required fields",
            "Candidate receipt",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "Inherited context does not widen authorization",
            "Fork selection is not a model selector",
            "do not count the rejected invocation as an effective review",
            "Artifact contract` naming its path, format, and receipt rule",
            "positive and negative evidence for each competing causal explanation",
            "If authorization blocks only an optional action",
            "If it blocks the assigned result",
            "one terminal `approval-blocked` receipt",
            "permission class, exact action, owner scope, and completed remainder",
            "Do not repeat that action, widen authorization",
            "assign the same permission-class and owner-scope boundary to a later child",
            "host evidence proves a reusable grant applies to child threads",
            "Terminal state closes transferred work only",
            "finding adjudication",
        ),
        "evaluation": (
            "Comparison scope only",
            "does not govern routine Skill execution",
            "final deliverable, acceptance conditions, important constraints",
            "smallest representative paired task",
            "vary only the configured route",
            "no model-causal claim without representative paired results",
            "Do not benchmark routine Skill use",
            "quality does not regress and end-to-end overhead is meaningfully lower",
            "Stop the comparison when delegation does not replace material work",
            "Evidence to record",
            "raw reviewer spawns separately from effective reviews",
            "wait timeouts as telemetry, not failure",
            "first-gate pass rate",
            "empty wait polls",
            "actual evidence tier",
            "do not describe fixtures as production evidence",
        ),
        "yaml": (
            'display_name: "Subagent Orchestrator"',
            'short_description: "Bounded delegation with primary-owned decisions"',
            'default_prompt: "Use $subagent-orchestrator',
        ),
    },
    "zh": {
        "skill": (
            "name: subagent-orchestrator",
            "优化用户要求的最终结果，而不是代理活动",
            "最终结果包括交付物、验收条件和重要约束",
            "对用户最关键、也最难的行为",
            "先由主代理处理",
            "小型工作优先直接调用或批量调用工具",
            "从宿主提供的角色说明中选择明确的 `agent_type`",
            "不得主动把无法匹配的工作路由给 `default`",
            "四个自定义角色仅用于各自的明确任务",
            "在编排调用中设置所选角色",
            "不得仅因角色元数据缺失或为 `default` 就丢弃结果",
            "允许委派时先启动一个子代理",
            "普通上限为两个子代理和一个活动写入者",
            "每个子代理都必须是叶子",
            "最小任务局部上下文分叉",
            "先收集并整合当前必需的收据",
            "主代理才可不询问并解除至多一个后续子代理",
            "检查点不得放宽叶子拓扑、所有权、写入范围或状态新鲜度规则",
            "如果授权被拒绝或已过时，但受影响的动作并非交付叶子结果所必需",
            "只有该动作阻断所分配的结果时",
            "终态 `approval-blocked` 收据",
            "不要把阻塞伪装成偏好",
            "两次面向决策的尝试",
            "任何相关变更都会使此前的门禁结果失效",
            "紧凑矩阵",
            "候选收据",
            "证据门禁，不是设计者或需求来源",
            "契约重试，不算有效评审",
            "主代理依据验收锚点裁决每项发现",
            "停止自动审查循环并回到第一性原理",
            "只能通过前述升级路径使用",
            "静态策略测试只能证明本地一致性",
            "安装和客户端回读只能证明已加载",
            "使用已安装的子代理模型和推理设置",
            "与验收锚点中的主张相匹配的证据",
            "不要新增 harness、schema、安装器功能、授权系统、审查层级或 benchmark",
            "阅读[高级路由策略]",
            "仅在增加第二个子代理、进入后续波次、发生自定义角色转换或开展审查时",
            "它不约束 Skill 的日常执行",
        ),
        "routing": (
            "只补充 Skill，不扩大",
            "只有主代理能确定策略",
            "一个 artifact 能够有效隔离主代理上下文中的原始证据",
            "返回证据，不作设计结论",
            "有效的审查升级已提供委派契约要求的全部字段",
            "不得替换角色，也不得把无法匹配的工作路由给内置 `default`",
            "审查返回的 BLOCK 交由主代理裁决",
            "保持两个子代理、一个活动写入者的普通上限",
            "扩展本身不是需要询问用户的问题",
            "多重审查需用户明确要求",
            "变更后的候选状态或新的区分性证据",
            "证据平台期",
            "缺字段拒绝属于契约重试，不算有效评审",
            "按新鲜度选择上下文，而不是按模型路由",
            "反复等待但状态无变化",
            "使用英文收据",
            "将 `sandbox_mode` 视为请求的配置，而非硬授权边界",
            "父级覆盖可能改变实际访问权限",
        ),
        "delegation": (
            "在编排调用中设置 `agent_type`，不要在交接正文中重复该字段",
            "Task: <一个有界结果>",
            "Scope: <准确的路径、artifact 或只读范围>",
            "Return: <英文收据或 artifact，以及可观察的完成条件>",
            "只添加所选角色的必需字段",
            "Candidate receipt",
            "Handoff status: REJECTED / MISSING_FIELDS",
            "继承的上下文不会扩大授权",
            "分叉选择不是模型选择器",
            "不得把该调用计为有效评审",
            "Artifact contract`，其中写明路径、格式和收据规则",
            "每种竞争性因果解释的正面与负面证据",
            "如果授权只阻塞可选动作",
            "如果该动作阻断所分配的结果",
            "终态 `approval-blocked` 收据",
            "权限类别、准确动作、所有者范围和已完成的其余工作",
            "不得重复该动作、扩大授权",
            "把相同权限类别和所有者范围的边界分配给后续子代理",
            "宿主证据证明存在适用于子代理的可复用授权",
            "终态只关闭已移交的工作",
            "审查发现裁决",
        ),
        "evaluation": (
            "仅用于比较",
            "不约束 Skill 的日常执行",
            "最终交付物、验收条件、重要约束",
            "最小代表性成对任务",
            "仅改变已配置路由",
            "不得提出模型因果主张",
            "不要对常规 Skill 使用做 benchmark",
            "质量不下降且端到端开销显著降低",
            "如果委派既未替代实质工作",
            "记录的证据",
            "分开记录原始审查者调用和有效评审",
            "等待超时只作为遥测，不作为失败",
            "首轮门禁通过率",
            "空等待轮询次数",
            "按实际证据层级记录",
            "不要把 fixture 描述为生产证据",
        ),
        "yaml": (
            'display_name: "子代理编排"',
            'short_description: "主代理保留决策权的有界委派"',
            'default_prompt: "使用 $subagent-orchestrator',
        ),
    },
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


def infer_language(codex_home: Path) -> str:
    agents_path = codex_home / "AGENTS.md"
    if agents_path.is_file() and "## 子代理与并行" in agents_path.read_text():
        return "zh"
    return "en"


def validate_config(checks: Checks, codex_home: Path) -> None:
    config_path = codex_home / "config.toml"
    checks.require(config_path.is_file(), f"missing config: {config_path}")
    if not config_path.is_file():
        return
    agents = load_toml(config_path).get("agents", {})
    expected = {
        "enabled": True,
        "max_concurrent_threads_per_session": 4,
        "interrupt_message": True,
        "default_subagent_model": "gpt-5.6-terra",
        "default_subagent_reasoning_effort": "max",
    }
    for key, value in expected.items():
        checks.require(agents.get(key) == value, f"agents.{key} must be {value}")


def validate_roles(
    checks: Checks,
    codex_home: Path,
    configured_skill_path: Path,
    language: str,
) -> None:
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
        require_markers(checks, instructions, role, ROLE_MARKERS[language][role])
        if language == "en":
            if role in {"evidence_tester", "boundary_mapper"}:
                checks.require(
                    "Do not spawn further agents, coordinate with peers, or widen scope."
                    in instructions,
                    f"{role}: recursion, cross-child coordination, and scope expansion must be disabled",
                )
            else:
                checks.require(
                    "Do not spawn agents or accept additional work." in instructions,
                    f"{role}: recursion and messaging must be disabled",
                )
                checks.require(
                    "Keep the review bounded to the named invariants." in instructions,
                    f"{role}: review input must remain bounded",
                )
        elif role in {"evidence_tester", "boundary_mapper"}:
            checks.require(
                "不要创建更多子代理、与同级协作或扩大范围。" in instructions,
                f"{role}: recursion, cross-child coordination, and scope expansion must be disabled",
            )
        else:
            checks.require(
                "不要创建子代理或接受额外工作。" in instructions,
                f"{role}: recursion and messaging must be disabled",
            )
            checks.require(
                "审查仅限于已命名的不变量。" in instructions,
                f"{role}: review input must remain bounded",
            )
        checks.require(
            hashlib.sha256(instructions.encode()).hexdigest()
            == ROLE_INSTRUCTION_SHA256[language][role],
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


def validate_policy(checks: Checks, codex_home: Path, language: str) -> None:
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

    policy_markers = POLICY_MARKERS[language]
    require_markers(checks, skill, "SKILL.md", policy_markers["skill"])
    require_markers(checks, routing, "routing policy", policy_markers["routing"])
    require_markers(checks, delegation, "delegation contract", policy_markers["delegation"])
    require_markers(checks, evaluation, "evaluation policy", policy_markers["evaluation"])

    global_markers = GLOBAL_POLICY_MARKERS[language]
    sections = [
        (heading, body)
        for heading in global_markers
        if (body := markdown_section(agents_text, heading))
    ]
    checks.require(len(sections) == 1, "AGENTS.md must contain one subagent policy section")
    if len(sections) == 1:
        heading, body = sections[0]
        require_markers(checks, body, f"AGENTS.md {heading}", global_markers[heading])
        checks.require(len(re.findall(r"(?m)^- ", body)) == 2, "AGENTS.md policy must contain two bullets")

    checks.require(len(skill.splitlines()) <= 120, "SKILL.md exceeds 120-line budget")
    for relative, text in (
        ("routing-policy.md", routing),
        ("delegation-contracts.md", delegation),
        ("evaluation-policy.md", evaluation),
    ):
        checks.require(len(text.splitlines()) <= 90, f"{relative} exceeds 90-line budget")
    for marker in policy_markers["yaml"]:
        checks.require(marker in yaml_text, f"openai.yaml marker mismatch: {marker}")
    checks.require(
        re.findall(r"(?m)^\s*allow_implicit_invocation:\s*(true|false)\s*$", yaml_text) == ["true"],
        "implicit invocation must appear exactly once and remain true",
    )
    active_contract = "\n".join((skill, routing, delegation, evaluation, yaml_text, agents_text))
    for legacy in LEGACY_ROLE_NAMES:
        checks.require(legacy not in active_contract, f"active policy contains legacy role name: {legacy}")


def validate(
    codex_home: Path,
    configured_skill_path: Path,
    language: str | None = None,
) -> Checks:
    language = language or infer_language(codex_home)
    if language not in POLICY_MARKERS:
        raise ValueError(f"unsupported policy language: {language}")
    checks = Checks()
    validate_config(checks, codex_home)
    validate_roles(checks, codex_home, configured_skill_path, language)
    validate_policy(checks, codex_home, language)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--configured-skill-path", type=Path, default=DEFAULT_SKILL_PATH)
    parser.add_argument("--language", choices=sorted(POLICY_MARKERS))
    args = parser.parse_args()
    checks = validate(
        args.codex_home.resolve(),
        args.configured_skill_path.resolve(),
        args.language,
    )
    if checks.errors:
        print(f"FAIL: {len(checks.errors)} error(s) across {checks.count} static checks")
        for error in checks.errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {checks.count} static routing configuration checks")
    print("- fallback: built-in default is never spawned; unmatched work remains primary")
    print("- admission: explicit non-default agent_type; then one child; two only for qualified parallel work")
    print("- context: role-scoped handoff and isolated review context")
    print("- runtime: four spawned threads excluding primary; two ordinary children; one active writer")
    print("- sandbox: requested role configuration plus action bounds, not host-enforcement proof")
    print("- expansion checkpoint: re-anchor, integrate, then clear one bounded child or ask at a material boundary")
    print("- wave boundary: current required children terminal and integrated before another wave")
    print("- user question: one recommended default for a material user-owned boundary only")
    print("- reviewer boundary: frozen evidence gate; primary adjudication; no reviewer-owned design loop")
    print("- closure boundary: child terminal state and spent budget are not task completion")
    print("- evidence boundary: static consistency only; no host or production-efficiency claim")
    return 0


if __name__ == "__main__":
    sys.exit(main())

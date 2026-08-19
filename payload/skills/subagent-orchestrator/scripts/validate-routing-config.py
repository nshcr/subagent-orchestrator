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
        "evidence_tester": "d8573dfb999a4ae126b1ba93f1fc219658050e0d8d74be724896fd5c5c16a382",
        "boundary_mapper": "d10f7f93056478c94948e76092bd346caa0e593017c07a33b9ac20b6d015f5c3",
        "risk_reviewer": "9df2ef68f78ff86bd7569981540860264d006059d529fa721c4234726b2f50c8",
        "risk_reviewer_max": "f859264f44c68a8653ad906407db71a08f961a5413cc7e157da0a3ff6bf6b09c",
    },
    "zh": {
        "evidence_tester": "31c1bd146724c78e3f3884ca56fa47047b5ddc73832d0b4f53f90f5202338cc4",
        "boundary_mapper": "a168b18f7193baee497fa9e197220aed248df70b67d791473a371242dec31694",
        "risk_reviewer": "7046b5b6e2c1dec09c00509f6d179df5f6d4c992c29d4d64640cf7bf8fa4b0bd",
        "risk_reviewer_max": "c017b77938ef3352f44a01037820c6429117092cd8735d32fcd3d10391ab7853",
    },
}
ROLE_MARKERS = {
    "en": {
        "evidence_tester": (
            "Acceptance fields",
            "Artifact contract",
            "only write scope",
            "Accept at most one scoped primary update",
            "English receipt",
        ),
        "boundary_mapper": (
            "Acceptance fields",
            "Artifact contract",
            "Accept at most one scoped primary update",
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
    },
    "zh": {
        "evidence_tester": (
            "Acceptance fields",
            "Artifact contract",
            "唯一写入范围",
            "最多接受一次",
            "英文收据",
        ),
        "boundary_mapper": (
            "Acceptance fields",
            "Artifact contract",
            "最多接受一次",
            "返回英文正文",
        ),
        "risk_reviewer": (
            "Named invariants",
            "Escalation receipt",
            "`Artifact contract` 为 `none`",
            "尝试证伪每个不变量",
            "PASS 或 BLOCK",
            "已准入的不变量不得使用 not-applicable",
            "返回不超过 600 个词的英文正文",
        ),
        "risk_reviewer_max": (
            "Named invariants",
            "Escalation receipt",
            "`Artifact contract` 为 `none`",
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
    },
    "zh": {
        "## 子代理与并行": (
            "默认使用单个代理",
            "使用 `$subagent-orchestrator`",
            "小型工作优先直接调用或批量调用工具",
            "主代理主要在协调、轮询或等待",
            "主代理保留授权、范围、整合、审查发现裁决和最终验收权",
            "子代理始终是叶子节点",
            "允许委派时只启动一个子代理",
            "最多保留一个活动写入者且写入范围不得重叠",
            "已安装的模型与推理设置",
            "不可变叶子边界",
            "角色准入",
        ),
    },
}
POLICY_MARKERS = {
    "en": {
        "skill": (
            "name: subagent-orchestrator",
            "Prove the monkey before building the pedestal",
            "hardest user-relevant behavior",
            "Start primary-only",
            "Prefer direct or batched tools for small work",
            "require English model-facing receipts",
            "finding adjudication",
            "Use host role descriptions for a first ordinary leaf",
            "before a custom role, second child, or review",
            "Name a non-`default` `agent_type`",
            "Name a non-`default` `agent_type` and never omit it",
            "When delegation is admitted, start one child",
            "ordinary cap at two children and one active writer",
            "Never allow child delegation or cross-child coordination",
            "expansion checkpoint cannot relax recursion, ownership, write-scope, or freshness rules",
            "Freeze new spawns, collect and integrate",
            "Clear the checkpoint without asking only when",
            "Ask before consequential work when the user requested a checkpoint or evidence leaves",
            "do not disguise them as preferences",
            "Allow at most one scoped primary update",
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
            "Reject omitted or otherwise invalid role results",
            "without repeating that blocked boundary",
            "operational child cannot obtain approval",
            "terminal receipt names permission class, action, and owner scope",
            "forming a task-scoped circuit",
            "Do not repeat the blocked action or assign the same blocked boundary",
            "the primary finishes directly",
            "Close only with claim-matched evidence for the original outcome",
            "Do not add a harness, schema, installer feature, authority system, reviewer hierarchy",
        ),
        "routing": (
            "Keep every child a leaf",
            "Set an explicit non-`default` `agent_type` on every spawn",
            "Never route to the built-in `default`",
            "General-purpose or unmatched fallback",
            "primary, no spawn",
            "Do not substitute roles",
            "Follow valid transitions",
            "only the primary settle strategy",
            "Use `evidence_tester` only when raw test or log volume",
            "primary sampling, integration, and direct checks",
            "Return a review BLOCK to the primary for independent adjudication",
            "When delegation is admitted, start one child",
            "ordinary cap at two children and one active writer",
            "Prohibit child delegation and cross-child coordination",
            "expansion checkpoint never relaxes leaf topology",
            "Permit at most one primary update to an operational leaf",
            "Keep review roles isolated from direct updates and later work",
            "Keep the primary model and effort user-controlled",
            "Operational leaves and fresh reviews use their declared role boundaries",
            "On rejection or older authorization",
            "task-scoped permission circuit",
            "Use English receipts",
            "`sandbox_mode` as requested configuration, not hard authority",
            "parent overrides may change it",
            "Ask when the user requested a checkpoint or at a material user-owned boundary",
            "Expansion alone is not a question",
            "Multi-review requires an explicit user request",
            "no voting or design workshop",
            "expansion checkpoint for another independent review",
            "changed candidate or new discriminating evidence",
            "evidence plateau",
            "machinery before the smallest real task proves core behavior",
        ),
        "delegation": (
            "Spawn: agent_type=<explicit non-default role>",
            "Task: <one bounded outcome>",
            "Scope: <exact paths, artifact, or read-only surface>",
            "Return: <English receipt or artifact and observable done condition>",
            "Add only the selected role's fields",
            "Bind every spawn to the declared non-`default` `agent_type`",
            "inherited context does not widen authorization",
            "If no specialized role fits, keep the work in the primary",
            "Artifact contract` naming its path, format, and receipt rule",
            "Do not include expected conclusions, mutable state, repeated policy",
            "prohibit delegation or cross-child coordination",
            "Keep one active writer and no overlapping write scopes",
            "Do not treat an existing handoff or expansion checkpoint as authorization for recursion",
            "Allow at most one scoped primary update for an operational leaf",
            "Use it only to deliver newly admitted evidence",
            "Never update `risk_reviewer` or `risk_reviewer_max`",
            "If host approval still rejects an operational leaf",
            "one terminal `approval-blocked` receipt",
            "permission class, exact action, and owner scope",
            "Do not repeat the blocked action, widen authorization",
            "assign the same permission-class and owner-scope boundary to a later child",
            "host evidence proves a reusable grant applies to child threads",
            "a parent grant or assertion alone is insufficient",
            "closure of transferred work only",
            "finding adjudication",
        ),
        "evaluation": (
            "Prove the monkey first",
            "prove it on the smallest representative task",
            "Do not benchmark routine Skill use",
            "Record the minimum evidence",
            "missing or over-broad handoff context",
            "review roles inheriting mutable execution state",
            "repeated child blocks for the same permission class and owner scope",
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
            "先验证核心行为，再建设支撑设施",
            "对用户最关键、也最难的行为",
            "先仅由主代理处理",
            "小型工作优先直接调用或批量调用工具",
            "供模型读取的英文收据",
            "审查发现裁决",
            "首个普通叶子使用宿主角色说明",
            "自定义角色、第二个子代理或审查前",
            "命名一个非 `default` 的 `agent_type`",
            "命名一个非 `default` 的 `agent_type`，不得省略",
            "允许委派时先启动一个子代理",
            "普通上限为两个子代理和一个活动写入者",
            "不得允许子代理继续委派或与其他子代理协作",
            "扩展检查点不得放宽递归、所有权、写入范围或状态新鲜度规则",
            "暂停新生成，收集并整合",
            "只有当新证据为下一个子代理提供一个有界且不重叠的目的",
            "当用户要求检查点",
            "不要把它伪装成偏好",
            "最多进行一次有界更新",
            "不得更新审查角色",
            "停止尝试其他角色变体",
            "用具体证据证伪",
            "最多三个新审查者",
            "所有写入者终止",
            "任何相关变更都会使此前的门禁结果失效",
            "证据门禁，不是设计者",
            "裁决每项审查发现",
            "停止自动审查循环并回到第一性原理",
            "将下一次新审查视为新的扩展检查点",
            "未改变的 BLOCK 是证据平台期",
            "静态策略测试只能作为本地一致性证据",
            "安装和客户端回读只能证明已加载",
            "使用已安装的子代理模型和推理设置",
            "拒绝类型省略或其他无效角色结果",
            "不重复该受阻边界",
            "无法获得批准",
            "权限类别、动作和所有者范围",
            "任务范围内的权限熔断机制",
            "不得重复受阻动作或把相同受阻边界分配给后续子代理",
            "主代理直接完成剩余工作",
            "与主张匹配的证据",
            "不要新增 harness、schema、安装器功能、授权系统、审查层级或 benchmark",
        ),
        "routing": (
            "每个子代理都必须是叶子",
            "每次生成都显式设置非 `default` 的 `agent_type`",
            "不得路由到内置 `default`",
            "通用或无法匹配的回退",
            "主代理，不生成子代理",
            "不要替换角色",
            "遵循有效转换",
            "只有主代理确定策略后",
            "仅当原始测试或日志量会污染主代理上下文时使用 `evidence_tester`",
            "主代理抽样、整合和直接检查",
            "将审查返回的 BLOCK 交由主代理独立裁决",
            "允许委派时先启动一个子代理",
            "普通上限为两个子代理和一个活动写入者",
            "禁止子代理继续委派和跨子代理协作",
            "扩展检查点不得放宽叶子拓扑",
            "主代理对操作叶子最多更新一次",
            "审查角色不得接受直接更新或额外工作",
            "主代理的模型与推理设置由用户控制",
            "操作叶子和新鲜审查均使用各自声明的角色边界",
            "遭到拒绝或授权已过时",
            "任务范围权限熔断机制",
            "使用英文收据",
            "`sandbox_mode` 是请求的配置而不是硬授权边界",
            "父级覆盖可能改变实际行为",
            "用户要求检查点或触及实质性用户级边界时才询问",
            "扩展本身不是问题",
            "多重审查需用户明确要求",
            "不得投票或举办设计工作坊",
            "为再次独立审查打开扩展检查点",
            "变更后的候选状态或新的区分性证据",
            "证据平台期",
            "在最小真实任务证明核心行为前，不要建设支撑机制",
        ),
        "delegation": (
            "Spawn: agent_type=<显式的非 default 角色>",
            "Task: <一个有界结果>",
            "Scope: <准确的路径、artifact 或只读范围>",
            "Return: <英文收据或 artifact，以及可观察的完成条件>",
            "只添加所选角色的字段",
            "每次生成都必须绑定已声明的非 `default` `agent_type`",
            "继承的上下文不会扩大授权",
            "没有合适的专用角色，就把工作留在主代理",
            "Artifact contract`，其中写明路径、格式和收据规则",
            "不得包含预期结论、可变状态、重复策略",
            "禁止继续委派或与其他子代理协作",
            "保持一个活动写入者，且写入范围不得重叠",
            "现有交接或扩展检查点都不构成递归",
            "主代理在原范围内最多进行一次有界更新",
            "仅补充新纳入的证据、缺失的验收字段或新的失败证据",
            "不得更新 `risk_reviewer` 或 `risk_reviewer_max`",
            "如果宿主仍拒绝批准操作叶子的动作",
            "终态 `approval-blocked` 收据",
            "权限类别、准确动作和所有者范围",
            "不得重复受阻动作、扩大授权",
            "把相同权限类别和所有者范围的边界分配给后续子代理",
            "宿主证据证明存在适用于子代理的可复用授权",
            "仅凭父代理授权或声明不足以解除",
            "已移交的工作已完成闭环",
            "审查发现裁决",
        ),
        "evaluation": (
            "先保留授权与正确性，再降低端到端编排开销",
            "在最小代表性任务上证明它",
            "不要对常规 Skill 使用做 benchmark",
            "记录最小证据",
            "交接上下文缺失或过宽",
            "审查角色继承可变执行状态",
            "对相同权限类别和所有者范围再次启动子代理并被阻塞",
            "在扩展检查点暂停生成",
            "整合当前终态收据",
            "不得放宽叶子、所有权、写入范围或新鲜度规则",
            "用户要求检查点，或证据留下",
            "仅接受针对冻结且已整合候选状态的审查证据",
            "审查者措辞不是权威",
            "一次修复和新复核后再次审查前",
            "子代理、门禁结论、安装或预算耗尽都不能视为任务完成",
            "以原始结果和匹配主张的证据",
            "不要再构建测量框架",
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
                checks.require(
                    "Accept at most one scoped primary update" in instructions,
                    f"{role}: bounded primary update contract is missing",
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
            checks.require(
                "最多接受一次有界的主代理更新" in instructions,
                f"{role}: bounded primary update contract is missing",
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

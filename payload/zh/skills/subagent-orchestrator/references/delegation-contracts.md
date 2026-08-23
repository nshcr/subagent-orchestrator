# 委派契约

在编排调用中设置 `agent_type`，不要在交接正文中重复该字段。每个子代理只接收一份精简的英文交接，每条指令只陈述一次：

```text
Task: <一个有界结果>
Scope: <准确的路径、artifact 或只读范围>
Context: <仅必要的任务局部事实>
Return: <英文收据或 artifact，以及可观察的完成条件>
Boundaries: <写入、外部动作、递归、重叠、过时状态或范围扩展>
```

仅对可变工作或冻结审查增加 `State`。冻结审查还要增加 `Candidate receipt`，写明准确 revision 或状态指纹、相关 diff 或 artifact 指纹、具名不变量指纹和已完成的直接检查。只添加所选角色的必需字段：

- `evidence_tester`：`Acceptance fields` 以及一个 `Artifact contract`，其中写明路径、格式和收据规则。
- `boundary_mapper`：`Acceptance fields`；仅在要求产出 artifact 时增加相应 `Artifact contract`，否则使用 `none`。
- `risk_reviewer`：`Named invariants`、`Escalation receipt: not-applicable` 和 `Artifact contract: none`。
- `risk_reviewer_max`：`Named invariants`、`Artifact contract: none`，以及一份 `Escalation receipt`；其中必须包含此前独立成行的 `Gate recommendation: INDETERMINATE / ESCALATE`、仍存在争议的准确不变量、每种竞争性因果解释的正面与负面证据，以及该歧义可能改变的明确不可逆决策。

如果任何必需交接字段缺失或无效，子代理不得执行任务，只返回一行终态：`Handoff status: REJECTED / MISSING_FIELDS: <comma-separated exact field names>`。主代理可以补正交接，并启动一个关联到被拒调用的新叶子；不得 follow up 被拒绝的审查者，也不得把该调用计为有效评审。

继承的上下文不会扩大授权。使用最小任务局部上下文分叉：操作叶子使用有界近期上下文，新审查者不接收父级 turn。分叉选择不是模型选择器，也不会授予权限。不得包含预期结论、子代理可在范围内读取的可变事实或重复策略。要求子代理在未列出的边界处停止，保持叶子节点且不与同级协作。最多保留一个活动写入者，写入范围不得重叠。取得所有必需的终态收据后才能整合。

如果授权只阻塞可选动作，要求子代理继续完成其余安全且范围内的工作，并在终态收据中列出阻塞项。如果该动作阻断所分配的结果，要求返回一份终态 `approval-blocked` 收据，写明权限类别、准确动作、所有者范围和已完成的其余工作。在宿主证据证明存在适用于子代理的可复用授权前，不得重复该动作、扩大授权，也不得把相同权限类别和所有者范围的边界分配给后续子代理。

终态只关闭已移交的工作。授权、冲突解决、审查发现裁决、扩展检查点、提交和对用户要求结果的验收仍由主代理负责。

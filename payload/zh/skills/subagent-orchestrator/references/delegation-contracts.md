# 委派契约

每个子代理发送一份精简的英文交接，只陈述每条指令一次：

```text
Spawn: agent_type=<显式的非 default 角色>; fork_turns=<操作叶子使用 1，审查使用 none>
Task: <一个有界结果>
Scope: <准确的路径、artifact 或只读范围>
Context: <仅必要的任务局部事实>
Return: <英文收据或 artifact，以及可观察的完成条件>
Boundaries: <写入、外部动作、递归、重叠、过时状态或范围扩展>
```

每次生成都必须绑定已声明的非 `default` `agent_type`。`explorer`、`worker`、`evidence_tester` 和 `boundary_mapper` 使用 `fork_turns="1"`，以保留当前用户回合，而无需预判后续哪个工具会触发审批。新鲜审查角色使用 `fork_turns="none"`。不得使用更大或完整历史分叉。继承的上下文不会扩大授权。若没有合适的专用角色，就把工作留在主代理。

仅对可变工作或冻结审查增加 `State`。只添加所选角色的字段：

- `evidence_tester`：`Acceptance fields` 以及一个 `Artifact contract`，其中写明路径、格式和收据规则。
- `boundary_mapper`：`Acceptance fields`；仅在要求时增加 `Artifact contract`。
- `risk_reviewer`：`Named invariants`、`Escalation receipt: not-applicable` 和 `Artifact contract: none`。
- `risk_reviewer_max`：审查者字段，加上此前的不确定终态行、竞争性证据和不可逆决策。

不得包含预期结论、完整历史、重复策略或所有者范围内可以低成本读取的事实。要求每个子代理在未列出的边界处停止，并禁止继续委派或与同级通信。抽样引用的证据，不要重复扫描；整合前不要改写工作者拥有的 artifact。

保持一个活动写入者，且写入范围不得重叠。先等待所有终态收据，再进行整合或进入后续波次。现有交接或扩展检查点都不构成递归、重叠、新增写入者、扩大范围、重新审查或开启新波次的授权。

对操作叶子（`explorer`、`worker`、`evidence_tester`、`boundary_mapper`），主代理通过 `send_message` 和 `followup_task` 合计最多更新一次。使用 `send_message` 向运行中的叶子传递原范围内新纳入的证据；仅当缺少验收字段或出现原范围内新的失败证据时使用 `followup_task`。不得向 `risk_reviewer` 或 `risk_reviewer_max` 发送任何更新；审查证据变化必须重新冻结并启动新审查。不得通过任一工具轮询状态、要求重设计或扩大范围。

如果宿主仍拒绝批准操作叶子的动作，返回一份终态 `approval-blocked` 收据，写明权限类别、准确动作和所有者范围，然后停止。主代理记录这条任务范围内的权限熔断机制并直接完成工作。不得重试、重新生成、继承更多历史、恢复、等待回复，或把相同权限类别和所有者范围的边界分配给后续子代理。只有宿主证据证明存在适用于子代理的可复用授权后，才能解除该熔断；仅凭父代理授权或声明不足以解除。

要求每个必要的子代理在最终验收前进入终态，但该状态只表示已移交的工作已完成闭环。授权、冲突解决、审查发现裁决、扩展检查点、提交和针对用户结果的验收仍由主代理负责。

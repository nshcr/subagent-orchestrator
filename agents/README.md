# 子代理角色

`en/` 与 `zh/` 是语义对等的英文、中文源集。两套文件保持相同的文件名、`name`、运行配置和协议字面量；仅 `description` 与 `developer_instructions` 使用对应语言。安装时只选择一套复制到 `~/.codex/agents/` 或项目 `.codex/agents/`，不要同时安装同名角色。

仅当一个有界子任务可独立完成，并能替代主线程的大量工作、隔离显著噪声或提供必要独立门禁时，才使用自定义角色；否则留给主代理，普通定位和实现分别使用内置 `explorer` 与 `worker`。跨组件链路用 `boundary_mapper`，已知检查用 `evidence_tester`，未知根因用 `runtime_debugger`，规范符合性用 `contract_auditor`，冻结候选复核用 `change_reviewer`，仅在外部研究量显著时用 `docs_researcher`。一次只选择最窄匹配角色，不按清单全量启动；范围、授权、整合、裁决和最终验收始终归主代理。

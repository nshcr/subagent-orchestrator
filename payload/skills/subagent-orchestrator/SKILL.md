---
name: subagent-orchestrator
description: Route and supervise explicit subagent requests and evidence-backed specialist work. Use when bounded children can replace material primary work or provide required independent gates; otherwise keep primary/default. Preserve required children to terminal unless cancellation is authorized. Optimize verified quality first and ChatGPT credits second.
---

# Subagent Orchestrator

Keep this file as the workflow entrypoint. Detailed policy lives in references;
role behavior and fixed child runtime configuration live in agent TOMLs.

## Route

1. Start primary-only. Identify one bounded deliverable, owner, stop condition,
   and the material work the primary will not repeat.
2. If neither substitution nor required independence is present, stay primary.
3. Before selecting any custom role, read the objective and promoted registry in
   [evaluation policy](references/evaluation-policy.md), then apply the exact
   eligibility and escalation rule in
   [routing policy](references/routing-policy.md).
4. Keep unsupported or unstable classes on primary/default.
5. Create one task-local handoff from
   [delegation contracts](references/delegation-contracts.md).

## Run and await

1. Start every already-qualified, mutually independent child allowed by the
   routing policy; never create filler work merely to occupy capacity.
2. Continue independent primary work while children run. If remaining work
   depends on them, wait for every required child to reach a terminal state.
3. Treat a wait timeout as observation-only, not as failure, a stall, or
   permission to interrupt. If a child remains running, report useful progress,
   optionally request status without interrupting, and wait again.
4. Never interrupt or replace a child for silence, elapsed wall time, token or
   credit use, or repeated wait timeouts. Interrupt only for explicit user
   cancellation or replacement, a concrete safety/scope violation, proven stale
   state, terminal platform failure, or expiry of an explicit user deadline.
5. Never start a replacement while the original is running. Accept only
   state-bound evidence; sample it without rebuilding transferred work or
   rewriting an owned artifact.
6. Keep authorization, writer ownership, conflict handling, synthesis, and final
   acceptance with the primary.

## Ownership

- `AGENTS.md`: stable delegation and safety invariants only.
- This file: workflow and reference navigation only.
- `references/routing-policy.md`: promoted classes and model escalation.
- `references/delegation-contracts.md`: handoff and artifact formats.
- `references/evaluation-policy.md`: promotion, retirement, credits, and history.
- `config.toml`: default-child settings and capacity only; never constrain the
  primary launch model or reasoning effort.
- Agent TOMLs: role behavior, permissions, and output limits.

Validate the installed policy with:

```bash
python3 -B scripts/validate-routing-config.py
```

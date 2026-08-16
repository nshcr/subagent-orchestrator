---
name: subagent-orchestrator
description: Route and supervise explicit subagent requests, bounded built-in collaboration, and evidence-backed specialist work. Use when children replace material primary work, remove material relay, or provide required independent gates; otherwise keep primary. Preserve every required descendant to terminal unless cancellation is authorized. Optimize verified quality first and ChatGPT credits second.
---

# Subagent Orchestrator

Keep this file as the workflow entrypoint. Detailed policy lives in references;
role behavior and fixed child runtime configuration live in agent TOMLs.

## Open an evidence-bus slice

1. Start primary-only. Read [routing policy](references/routing-policy.md) and
   [evaluation policy](references/evaluation-policy.md) before delegation.
2. If neither material substitution nor required independence is present, stay
   primary. Explorer and worker also require an external materiality manifest.
3. Open one `slice_open` from [delegation contracts](references/delegation-contracts.md):
   bind task, unique slice, one milestone, one change class, exact owner paths,
   required gates, and the admitted state digest.
4. Issue each child an immutable work-transfer receipt. Use `fork_turns=none`;
   full-history children and agent-authored materiality are ineligible.

## Run, freeze, and close

1. Start only qualified, independent, ownership-safe children. Preserve the
   direct-child and bounded-peer caps; capacity never creates work.
2. Keep a task-wide primary source-access ledger. Targeted precheck and sampling
   use one frozen denominator and must be proper subsets no larger than 10%; integration readback
   may inspect child artifacts and changed files without replaying transferred scans.
3. Treat wait timeout as observation-only. Never interrupt for silence, elapsed
   time, token use, credits, or repeated waits; every required descendant ends terminal.
4. Freeze only after the writer is terminal. Tester, reviewer, gate, and close
   independently recompute HEAD, index, worktree, and changed-path digests.
5. Any readback change invalidates every gate. Run three disjoint fresh final
   gates on one hash; repair requires all gates to rerun with attempt incremented.
6. Close only with a terminal tree, identical readback, and every required gate PASS.

## Ownership and control

- Each slice has at most one writer, which owns its task-wide canonical component. Overlap, rename,
  split, and merge permanently union aliases across slices and commits.
- After two writer compactions for one task and owner component, reject new writer
  spawn/follow-up; do not cancel an active child, and accept safe incomplete receipts.
- `send_message` carries admitted evidence, dependency status, or artifact receipt
  to a running built-in target. `followup_task` uses only the three typed same-scope
  reasons. Custom roles never message, recurse, repair, or review their own repair.
- The primary retains authorization, scope, conflict handling, integration, and
  final acceptance. Unsupported or capability-unverified work stays primary.

## Ownership map

- `AGENTS.md`: stable safety invariants. References: routing, transfer/lifecycle,
  evaluation/pilot. `config.toml`: child defaults/capacity. TOMLs: role runtime.

Validate the installed policy with:

```bash
python3 -B scripts/validate-routing-config.py
```

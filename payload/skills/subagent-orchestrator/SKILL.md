---
name: subagent-orchestrator
description: Route and supervise explicit subagent requests, bounded built-in collaboration, and evidence-backed specialist work. Use when children replace material primary work, remove material relay, or provide required independent gates; otherwise keep primary. Preserve every required descendant to terminal unless cancellation is authorized. Optimize verified quality first and ChatGPT credits second.
---

# Subagent Orchestrator

Keep this file as the workflow entrypoint. Detailed policy lives in references; role behavior and fixed child runtime configuration live in agent TOMLs.

## Open an evidence-bus slice

1. Start primary-only. Read [routing policy](references/routing-policy.md) and
   [evaluation policy](references/evaluation-policy.md) before delegation.
2. If neither material substitution nor required independence is present, stay
   primary. Explorer and worker also require an external materiality manifest.
3. Open one `slice_open` from [delegation contracts](references/delegation-contracts.md): bind task, unique slice, milestone, change class, exact owner paths, gates, and state digest. Writer paths/components and path artifacts stay within that slice scope; task-wide alias unions remain permanent.
4. Issue each child a complete canonical-snake-case immutable work-transfer receipt whose digest binds every mandatory field and spawn route/topology/depth. Use `fork_turns=none`; full-history children are ineligible.
5. Require host-provided authority receipts outside the trace. A materiality issuer has an externally bound host/owner/sealed-harness class and cannot equal primary, any child/parent/role participant, or another agent identity. Trace hashes bind payloads, never issuer identity; unmatched authority fails closed.

## Run, freeze, and close

1. Start only qualified, independent, ownership-safe children. Preserve the
   direct-child and bounded-peer caps; capacity never creates work.
2. Keep a task-wide primary source-access ledger. Precheck/sampling use one frozen denominator and proper subsets no larger than 10%; integration consumes admitted artifact/changed-path receipts with zero transferred source ranges/bytes. One scenario represents each unique task; rollover never resets access, materiality, ownership, compaction, gate, or receipt state.
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
  to a running built-in target, bound to task, slice, original transfer scope, typed
  purpose, canonical dependency digest, canonical message semantic digest, and an
  externally admitted receipt. The semantic digest excludes only the authority anchor
  and digest fields. `followup_task` uses only the three typed same-scope
  reasons. Custom roles never message, recurse, repair, or review their own repair.
- A default peer requires trace-external host capability plus an executed producer-to-
  consumer `artifact_receipt` relay. Its artifact digest must come from that named
  producer's terminal receipt and be admitted by the consumer transfer. No-op peers
  without both admitted descendants and material relay are ineligible.
- Pilot authorization follows freeze, binds the exact frozen HEAD and message producer, rejects every normalized create-task action, and becomes stale after any new generation.
- The primary retains authorization, scope, conflict handling, integration, and
  final acceptance. Unsupported or capability-unverified work stays primary.

## Ownership map

- `AGENTS.md`: stable safety invariants. References: routing, transfer/lifecycle,
  evaluation/pilot. `config.toml`: child defaults/capacity. TOMLs: role runtime.

Validate the installed policy with:

```bash
python3 -B scripts/validate-routing-config.py
```

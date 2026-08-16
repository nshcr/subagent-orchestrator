# Routing Policy

Read this reference whenever delegation is considered. Agent TOMLs own governed
custom leaves; built-in agents own generic leaves and the capability-gated peer lane.

## Eligibility

| Task class | Route | Required boundary |
|---|---|---|
| Material structured test-output triage | `evidence_tester` | Exhaustive corpus, explicit acceptance fields, requested artifact |
| Material bounded log corpus | `evidence_tester` | Exhaustive runbook-driven corpus, acceptance fields, requested artifact |
| Named unresolved cross-component boundary | `boundary_mapper` | Targeted primary check leaves one named boundary unresolved |
| Required independent high-risk final gate | fresh `risk_reviewer` | Named, disjoint final invariant registry |
| Material narrow read-only codebase question | built-in `explorer` leaf | External manifest passes explorer path/byte predicate and replaces primary scan |
| Scoped implementation or fix | built-in `worker` leaf | External manifest passes worker predicate; settled strategy; disjoint writer component |
| Material dependency graph needing direct evidence handoff | built-in `default` bounded peer | Trace-external host capability plus producer-consumer artifact receipt proving material primary relay removed |
| Any other, ambiguous, simple, resolved, mechanical, or open-ended class | Primary | No qualified route |

An artifact request, label, ordinary leaf, two tiny files, padding, duplicate ranges,
synthetic split, or verification-token asset never proves materiality. Explorer needs
at least two unique canonical source paths and 4096 non-padding bytes; worker needs
at least three and 8192. A host, owner, or sealed harness signs the digest-bound
manifest; an agent cannot self-issue or proxy it. Missing evidence falls back primary.

## Topology and ownership

- Governed custom roles are parent-routed nonrecursive leaves: depth zero, no peer
  message, no follow-up. Built-in `explorer` and `worker` are leaves by default.
- Built-in `default` may coordinate one additional level with at most two registered
  built-in leaf descendants. This bounded-peer topology has one coordinator maximum
  and must execute its externally bound artifact relay; a no-op peer is rejected. Unproven client capability
  fails closed to a built-in leaf or primary.
- One writer owns each task-wide canonical component. Overlap, rename, split, and
  merge union aliases permanently. Reject overlapping writers. Two accumulated
  writer compactions, proven by trace-external host receipts rather than terminal
  self-report, exhaust new writer spawn/follow-up for that component.
- Each trace document has one scenario per non-empty unique top-level task. Scenario
  rollover remains events within that scenario and cannot reset task-wide materiality,
  sampling, ownership, compaction, gate, admission, or receipt state.
- Start at most three qualified direct children; a fourth needs explicit user
  authorization. Capacity alone never qualifies delegation. Shared mutation and
  final integration remain serial.

## Evidence bus and communication

Open `slice_open` before spawn and use immutable work-transfer receipts with
`fork_turns=none`. Full-history children are ineligible. The primary keeps a task-wide
access ledger and does not reconstruct transferred work. Only digest-bound targeted
precheck and strict proper-subset sampling no larger than 10% are promotion eligible.

`send_message` carries externally admitted evidence, dependency status, or an artifact
receipt to a running built-in target, bound to producer, task, slice, typed purpose, and the
target's original transfer digest; it cannot start a turn or amend authorization, scope,
ownership, topology, or handoff. Its canonical semantic digest excludes only the
authority anchor and digest fields. External authority binds that semantic digest,
canonical dependency digest, and exact purpose. A peer relay requires
`artifact_receipt` and the named producer's terminal artifact admitted by the consumer.
`followup_task` targets an idle/terminal built-in
child for `new_failure_evidence`, `missing_acceptance_field`, or
`authorized_continue`, with a scope digest equal to the original work-transfer. Polling, custom-role, peer, reviewer repair,
self-review, and scope-changing messages are hard blockers.

Wait timeouts are observation-only. Never interrupt or replace for silence, wall
time, tokens, credits, or repeated waits. Do not cancel a running writer when its
component budget becomes exhausted; accept a safe incomplete receipt. Collect every
required descendant terminal before close.

## Freeze and independent gates

Writer terminal precedes freeze. Tester, reviewer, gate, and close independently
read back HEAD, index, worktree, and complete changed-path digests. A hash change
invalidates all gates. Every invariant belongs to one gate; no overlap, voting, or
majority result. Three disjoint fresh gates PASS on the final hash. Repair reruns all
at attempt+1. The primary retains authorization, integration, and final acceptance.

The installed fresh `risk_reviewer` remains the mandatory named governance control
when no callable built-in equivalent exists. Accept an `xhigh` PASS. Repair a defect
then use a fresh reviewer; missing evidence remains BLOCK. One `risk_reviewer_max`
is allowed only for sufficient evidence, explicit competing causal explanations,
and an irreversible P0/P1, security, authorization, or data-integrity decision.
Complexity, ordinary BLOCK, or confidence seeking never qualifies.

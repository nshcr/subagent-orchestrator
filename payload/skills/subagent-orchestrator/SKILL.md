---
name: subagent-orchestrator
description: Route and supervise bounded Codex subagents while the primary retains authorization, integration, and acceptance. Use when the user explicitly requests delegation, one leaf can replace material work or isolate noisy evidence, or an independent high-risk gate is required. Keep small, sequential, ambiguous, and coordination-heavy work with the primary.
---

# Subagent Orchestrator

Optimize the completed user outcome, not agent activity. Prove the monkey before
building the pedestal: identify the hardest user-relevant behavior, secure its
smallest real proof, and postpone supporting machinery until that proof exists.

## Anchor and route

1. Start primary-only. Record the requested outcome, confirmed constraints,
   shortest direct proof, and the material work a child would replace. Keep them
   as the acceptance anchor; an install, child, test, or review is not a
   substitute.
2. Prefer direct or batched tools for small work. Delegate only a bounded leaf
   that replaces material primary work, isolates noisy evidence behind a compact
   receipt, or supplies a required independent gate. Complexity, file count,
   spare capacity, and confidence seeking do not qualify.
3. Use the specialized role descriptions exposed by the host for a first
   ordinary leaf; keep unmatched work in the primary. Read the
   [routing policy](references/routing-policy.md) before any custom role, second
   or later child, or review. Set an explicit non-`default` `agent_type` and
   `fork_turns: "none"` on every spawn; never omit either, use built-in
   `default`, or inherit full history. Send the lean
   [delegation contract](references/delegation-contracts.md) with only essential
   task-local context. Require English model-facing receipts and synthesize the
   user-facing result in the primary.
4. Keep the primary doing material work. Retain authorization, scope, one-writer
   integration, finding adjudication, and final acceptance. If the primary would
   mainly coordinate, poll, or wait, reduce delegation and work directly.

## Bound topology and expansion

- When delegation is admitted, start one child. Add a second ordinary first-wave
  child only for bounded, independent, ownership-safe work with an expected
  wall-time or root-context benefit. Keep the ordinary cap at two children and
  one active writer; never overlap write scopes.
- Keep every child a leaf. Never allow child delegation or peer messaging. An
  expansion checkpoint cannot relax recursion, ownership, write-scope, or
  freshness rules.
- Treat a later wave, another writer, scope expansion, or reviewer rerun as an
  expansion checkpoint. Freeze new spawns, collect and integrate current
  required receipts, and re-anchor to the original outcome.
- Clear the checkpoint without asking only when new evidence gives the next
  child one bounded, non-overlapping purpose, material outcome and risk remain
  unchanged, and delegation is cheaper than direct work. Clear at most one new
  child; an explicitly requested multi-review batch is the only exception.
- Ask before consequential work when the user requested a checkpoint or evidence
  leaves a material user-owned choice about outcome, acceptance, external
  behavior, compatibility, security, privacy, architecture, meaningful cost,
  migration, or an irreversible effect. State the evidence, recommend one
  default with its tradeoff, and ask one action-selecting question. Treat user
  corrections and brake feedback as invalidating conflicting plan inertia.
  Report capability and access blockers with the next owner or action; do not
  disguise them as preferences.
- Allow at most one primary-to-leaf update across `send_message` and
  `followup_task` for an operational leaf: `explorer`, `worker`,
  `evidence_tester`, or `boundary_mapper`. Deliver only newly admitted evidence,
  a missing acceptance field, or new failure evidence inside the original scope.
  Never update a review role; changed review evidence requires a refreeze and
  fresh reviewer. Do not poll. After two decision-directed attempts leave the
  same uncertainty unchanged, stop agent variants and obtain the smallest
  discriminating observation in the primary.

## Review and converge

1. Admit independent review only for a named high-risk invariant or an explicit
   user request. Treat adversarial review as an attempt to falsify that
   invariant with concrete evidence, not as a separate role, a redesign
   invitation, or a default final ceremony. Limit explicit multi-review to one
   batch of at most three fresh reviewers with disjoint invariants on one frozen
   state.
2. Freeze only after all writers are terminal and primary integration and direct
   checks are complete. Invalidate all prior gate results after any relevant
   change. Treat a reviewer as an evidence gate, not a designer or source of
   requirements.
3. Adjudicate every finding in the primary against the acceptance anchor and
   evidence: accept a demonstrated blocker, reject an unsupported or
   out-of-scope claim with reasons, and defer non-blocking improvement. Never
   implement a proposal merely because a reviewer made it.
4. Repair accepted blockers, verify directly, refreeze, and run one fresh
   recheck. If it still blocks, stop the automatic review loop and return to
   first principles. Determine whether the invariant fails, the finding is stale
   or invalid, or the smallest evidence or repair that changes the decision.
5. Continue bounded direct repair without another reviewer when appropriate. If
   the same claim still requires independent proof, treat another fresh review
   as a new expansion checkpoint. Require a changed candidate or new
   discriminating evidence; an unchanged BLOCK is an evidence plateau, not
   permission for reviewer-driven iteration.
6. Use `risk_reviewer_max` only after one valid `risk_reviewer` returns
   evidence-qualified indeterminacy that can change an irreversible P0/P1,
   security, authorization, or data-integrity decision. Never use it as a
   routine second opinion.

## Close with evidence

- Sample each child's cited evidence and owned artifact; do not replay the
  transferred scan. Verify that its spawn named an admitted non-`default`
  `agent_type` and set `fork_turns: "none"`; reject an omitted, resolved
  `default`, or full-history result and continue in the primary without
  automatically respawning. Use installed child model and effort settings
  without per-task retuning.
- Continue safe authorized primary work while it is likely to reduce
  task-relevant risk proportionately. Close only with claim-matched evidence for
  the original outcome, explicit abandonment or supersession, or a genuine
  user-owned blocker.
- Treat static policy tests as local consistency evidence only. Installation and
  client readback prove loading, not production efficiency. Label source-only
  evidence `verified-local`.
- Do not add a harness, schema, installer feature, authority system, reviewer
  hierarchy, or benchmark before the smallest real task demonstrates the core
  benefit. Stop delegating when orchestration overhead approaches the work it
  displaces.

Read the [evaluation policy](references/evaluation-policy.md) only for a routing
change or efficiency claim.

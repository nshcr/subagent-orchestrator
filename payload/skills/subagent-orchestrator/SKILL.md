---
name: subagent-orchestrator
description: Route and supervise bounded Codex subagents while the primary retains authorization, integration, and acceptance. Use when the user explicitly requests delegation, one leaf can replace material work or isolate noisy evidence, or an independent high-risk gate is required. Keep small, sequential, ambiguous, or coordination-heavy work with the primary.
---

# Subagent Orchestrator

Optimize the completed user outcome, not agent activity. Prove the monkey before
building the pedestal: identify the hardest user-relevant behavior, secure its smallest
real proof, and postpone scaffolding, policy machinery, and broad hardening until that
proof exists.

## Anchor and route

1. Start primary-only. Record the requested outcome, confirmed constraints, shortest
   direct proof, and the material work a child would replace. Keep these as the
   acceptance anchor; an install, child, test, or review is not a substitute.
2. Prefer direct or batched tools for small work. Delegate only a bounded leaf that
   replaces substantial primary work, isolates a noisy evidence stream behind a compact
   receipt, or supplies a required independent gate. Complexity, file count, available
   capacity, or confidence seeking do not qualify.
3. Read [routing policy](references/routing-policy.md) before selecting a role and send
   the lean [delegation contract](references/delegation-contracts.md). Use fresh context
   by default. Children return English model-facing receipts; the primary synthesizes
   the user-facing result.
4. Keep the primary doing material work. It owns authorization, scope, one-writer
   integration, finding adjudication, and final acceptance. If it would mainly
   coordinate, poll, or wait, reduce delegation and work directly.

## Budget and expansion

- Start one child by default. A second ordinary first-wave child requires two bounded,
  independent, ownership-safe assignments with expected wall-time or root-context
  benefit. Keep the absolute ordinary cap at two children and one active writer; never
  overlap write scopes. Every child is a leaf and may not delegate or message peers.
- A later wave, another writer, scope-expanding follow-up, nested delegation, or a
  reviewer rerun opens an expansion checkpoint. Freeze new spawns, collect and integrate
  current required receipts, and re-anchor to the original outcome.
- The primary may clear the checkpoint without asking when new evidence gives the next
  child one bounded, non-overlapping purpose, the original outcome and material risk are
  unchanged, and delegation is still cheaper than direct work. Clear at most one new
  child; an explicitly requested multi-review batch is the only exception.
- Ask before consequential work when the user requested a checkpoint or evidence cannot
  choose among materially different acceptable outcomes involving outcome, acceptance,
  external behavior, compatibility, security, privacy, architecture, meaningful cost,
  migration, or irreversible effect. State the boundary and evidence, recommend one
  default with its tradeoff, and ask one action-selecting question. Corrections and brake feedback
  invalidate conflicting plan inertia. Report capability and access blockers with the
  next owner or action; do not disguise them as preferences.
- Do not poll with follow-ups. Use `followup_task` only for new failure evidence or a
  missing acceptance field inside the original scope. After two decision-directed
  attempts leave the same uncertainty unchanged, stop agent variants and rebuild the
  smallest discriminating observation in the primary.

## Review and convergence

1. Use independent review only for a named high-risk invariant or an explicit user
   request. Adversarial review means trying to falsify that invariant with concrete
   evidence; it is not a separate role, an invitation to redesign, or a default final
   ceremony. Multi-review is an exceptional explicit batch of at most three fresh
   reviewers with disjoint invariants on one frozen state.
2. Freeze only after all writers are terminal and primary integration and direct checks
   are complete. Any relevant change invalidates prior gate results. A reviewer is a
   terminal evidence gate, not a designer or source of new requirements.
3. The primary independently adjudicates every finding against the acceptance anchor and
   evidence: accept a demonstrated blocker, reject an unsupported or out-of-scope claim
   with reasons, and defer non-blocking improvement. Never implement a reviewer proposal
   merely because it was proposed.
4. Repair accepted blockers, verify directly, refreeze, and run one fresh recheck. If it
   still blocks, stop the automatic review loop and return to first principles: determine
   whether the invariant truly fails, whether the finding is stale or invalid, and what
   smallest evidence or repair changes the decision.
5. The primary may continue bounded direct repair without another reviewer. If the same
   acceptance claim still requires independent proof, a further fresh review is a new
   expansion checkpoint. Do not repeat a review without a changed candidate or new
   discriminating evidence; unchanged BLOCK is an evidence plateau, not permission for
   reviewer-driven iteration.
6. Use `risk_reviewer_max` only after one valid `risk_reviewer` returns evidence-qualified
   indeterminacy that can change an irreversible P0/P1, security, authorization, or
   data-integrity decision. It is never a routine second opinion.

## Evidence and closure

- Sample a child's cited evidence and owned artifact; do not replay the transferred scan.
  Spawn children only with installed model and effort settings; never retune per task.
- Continue safe authorized primary work while it is likely to reduce task-relevant risk
  proportionately. Close only when the original outcome has claim-matched evidence, the
  user abandons or supersedes it, or a genuine user-owned blocker remains. Child terminal
  state, spent budget, clean logs, or confident prose do not prove task completion.
- Static policy tests prove local consistency only. Installation and client readback prove
  loading, not production efficiency. Label source-only evidence `verified-local`.
- Do not add a harness, schema, installer feature, authority system, reviewer hierarchy,
  or benchmark until the smallest real task demonstrates the core benefit. If overhead
  approaches displaced work, stop delegating.

Read [evaluation policy](references/evaluation-policy.md) only for a routing change or
efficiency claim.

# Evaluation Policy

## Objective

Preserve authorization and correctness, then minimize end-to-end orchestration
overhead. The decision is whether delegation improves the completed user task, not
whether an agent, harness, or policy can be made more sophisticated.

## Monkey before pedestal

Test the core behavior on the smallest representative task before investing in
supporting infrastructure. Do not create a schema, authority system, lifecycle
engine, installer feature, or reviewer hierarchy merely to make an unproven workflow
look rigorous. If the direct task does not show useful delegation, stop there.

Routine skill use does not require a new benchmark campaign. When the user explicitly
requests an optimization study, compare baseline and candidate on the same task and
record only evidence needed for that decision.

## Minimal efficiency receipt

Record, when available:

- delivered outcome and correctness failures;
- child attempts, failed or interrupted attempts, and delegation waves;
- primary-only, one-child, and two-child route counts;
- writer count, reviewer attempts, retries, and primary replay;
- expansion checkpoints, user questions, and primary-only fallbacks;
- concurrent or overlapping writers, unintegrated terminal receipts, and moving-state
  review attempts as correctness failures;
- wait timeouts as telemetry, not failure;
- total primary and child tokens or actual credits, keeping cached raw usage distinct
  from billed credits;
- whether the candidate was installed, loaded, and observed on the target.

Treat a second first-wave child as an efficiency claim: record the independent work it
overlapped and the wall-time or root-context benefit it was expected to provide. A
capacity slot, multiple tool calls, or several related questions is not evidence that
another agent was needed.

Do not infer role-level or tool-level credits when the source exposes only thread or
run totals. Do not call an offline fixture, local test, or clean archive production
evidence.

## Decision and stop boundary

- Keep primary when quality evidence is incomplete or delegation does not replace
  material work.
- An expansion checkpoint prohibits automatic spawning; it is not an automatic user
  question. Without exact prior authorization, prefer primary-only work or closure.
  Ask only when evidence leaves a material user-owned outcome, scope, cost, risk, or
  acceptance choice. Report operational blockers with the next owner or action.
- A later wave is not admissible until current required children are terminal and their
  receipts are integrated. Review evidence is valid only for a state frozen after all
  writers are terminal; a relevant state change invalidates it.
- Prefer a candidate only when quality does not regress and end-to-end overhead is
  meaningfully lower on the decision-relevant task.
- A mandatory independent safety gate may remain even when it is not an efficiency
  win; label that as governance retention, not optimization success.
- Reviewer scope is frozen with the named invariants. New ideas and non-blocking
  hardening are deferred.
- After one repair batch and one fresh recheck, stop further review. Ask the user only
  for a named material acceptance choice; otherwise report the blocker and next owner
  or action. Reviewer-driven redesign must not continue autonomously.
- Child completion, a review terminal line, or exhausted delegation budget is not task
  completion. Measure closure against the original user outcome; success at an install,
  load, child, test, or review sub-boundary is partial evidence unless it directly
  proves that acceptance anchor. Closure still requires claim-matched evidence or a
  genuine user-owned blocker.

Use the repository campaign evaluator only when a real comparison decision requires
it. Preserve raw observations and state the evidence boundary; do not build another
measurement framework around the evaluator without explicit user authorization.

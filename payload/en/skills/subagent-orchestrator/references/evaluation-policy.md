# Evaluation Policy

## Comparison scope only

This reference is for an actual routing comparison or an efficiency claim. It does not govern routine Skill execution, change delegation admission, or require a benchmark before ordinary work.

Judge the user-requested result: the final deliverable, acceptance conditions, important constraints, and claim-matched evidence. Agent count, activity, policy complexity, installation, or a gate line are not substitute outcomes.

## Minimum comparison

- Compare primary-only and delegated routes on the smallest representative paired task that can answer the routing question.
- For a role or model A/B, hold the task, handoff, candidate, acceptance, and evidence surface fixed; vary only the configured route, confirm the effective model and effort by host readback, and make no model-causal claim without representative paired results.
- Preserve authorization and correctness first. Consider a routing change only if quality does not regress and end-to-end overhead is meaningfully lower.
- Stop the comparison when delegation does not replace material work, reduce root-context noise, or provide a required independent gate.
- Use the repository campaign evaluator only for a real comparison decision. Do not benchmark routine Skill use or build another measurement framework without explicit authorization.

## Evidence to record

- final result and correctness failures;
- child attempts, waves, writers, reviewer attempts, retries, and primary replay;
- raw reviewer spawns separately from effective reviews; classify each terminal invocation as normal completion, missing-field rejection, substantive BLOCK superseded by a changed candidate or new evidence, approval-blocked, or timeout/lost, and fail closed when evidence is insufficient;
- work or root-context noise displaced by each additional child or later wave;
- overlapping writers, unintegrated receipts, moving-state reviews, over-broad handoffs, or repeated children on the same blocked permission boundary as routing failures;
- wait timeouts as telemetry, not failure;
- first-gate pass rate, repair rounds, missing-field retry rate, non-overlapping wait duration, empty wait polls, and total convergence time;
- total primary and child tokens or actual credits when available, keeping cached raw usage separate from billed credits;
- source, install, client-readback, and target observations at their actual evidence tier.

Do not infer per-role or per-tool credits from thread totals, and do not describe fixtures as production evidence. Preserve raw observations and state any unavailable evidence.

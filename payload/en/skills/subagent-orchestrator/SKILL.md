---
name: subagent-orchestrator
description: Route and supervise bounded Codex subagents while the primary retains authorization, integration, and acceptance. Use when the user explicitly requests delegation, one leaf can replace material work or isolate noisy evidence, or an independent high-risk gate is required. Keep small, sequential, ambiguous, and coordination-heavy work with the primary.
---

# Subagent Orchestrator

Optimize the user's requested result, not agent activity. Define that result as the final deliverable, its acceptance conditions, and its important constraints. Prove the hardest user-relevant behavior on the smallest real task before adding supporting machinery.

## Decide and route

1. Start with the primary. Record the requested result, confirmed constraints, shortest direct proof, and the material work a child would replace. Use this as the acceptance anchor; intermediate signals such as an install, child receipt, test, or review count only as evidence toward it.
2. For repository work, establish only the readiness facts needed by the task before delegating: applicable instructions, authoritative setup and validation entry points, a task-relevant direct executable check when available, documentation mismatches, and current environment or capability blockers. Keep this in the primary when the evidence is cheap. If collection would create a substantial noisy stream, `evidence_tester` may produce one bounded repository-readiness receipt that separates declared documentation, observed execution, and blockers. The receipt is not a score, compatibility certification, or product-quality verdict. Do not run external scanners, unpinned latest packages, or additional setup outside the task's authorization to create it.
3. Prefer direct or batched tools for small work. Delegate only a bounded leaf that replaces material primary work, isolates a noisy evidence stream behind a compact receipt, or supplies a required independent gate. Complexity, file count, spare capacity, and confidence seeking alone do not qualify.
4. Select a named `agent_type` from the host's available role descriptions. Use `explorer` for a material narrow read-only codebase question and `worker` for an implementation slice whose strategy, ownership, and acceptance are settled. Do not deliberately route unmatched work to `default`; keep it in the primary.
5. Use the custom roles only for their exact purpose:

   - `evidence_tester`: one structured test or bounded runbook/log evidence set plus one requested artifact; no source edits.
   - `boundary_mapper`: one unresolved cross-component execution, state, or persistence boundary; no design verdict.
   - `risk_reviewer`: one independent gate for exact high-risk invariants on a frozen candidate.
   - `risk_reviewer_max`: one terminal escalation after a valid reviewer leaves evidence-qualified ambiguity that can change an irreversible P0/P1, security, authorization, or data-integrity decision.

6. Read the [delegation contract](references/delegation-contracts.md) only when spawning. Set the selected role in the orchestration call, require an English model-facing receipt, and keep the handoff bounded to task-local facts. Evaluate an already returned child result by its scope, evidence, freshness, and role boundaries; do not discard it solely because its role metadata is omitted or `default`, and do not spawn a replacement merely to correct the label.
7. Keep the primary doing material work. It retains authorization, scope, one-writer integration, conflict resolution, finding adjudication, and final acceptance. If the primary would mainly coordinate, poll, or wait, reduce delegation and work directly.

## Bound execution

- When delegation is admitted, start one child. Add a second ordinary first-wave child only for bounded, independent, ownership-safe work expected to reduce wall time or root-context noise. The ordinary cap is two children and one active writer; write scopes never overlap.
- Every child remains a leaf. Prohibit child delegation and cross-child coordination. Use installed child model and effort settings without per-task retuning.
- Use the smallest task-local context fork supported by the host. Operational leaves receive only the bounded recent context they need; fresh reviewers receive no parent turns. Forking context is not a model selector or permission grant. Verify the effective child model and effort from host readback before making routing or efficiency claims.
- A later wave, another writer, scope expansion, or reviewer rerun opens an expansion checkpoint. Collect and integrate current required receipts first. Clear at most one next child without asking only when new evidence gives it one bounded non-overlapping purpose, material result and risk are unchanged, and delegation is cheaper than direct work. A checkpoint never relaxes leaf, ownership, write-scope, or freshness rules.
- Ask only when the user requested a checkpoint or evidence leaves a material user-owned choice about the result, acceptance, external behavior, compatibility, security, privacy, architecture, meaningful cost, migration, or an irreversible effect. Report capability or access blockers with the next owner or action; do not disguise them as preferences.
- If a denied or stale authorization affects only a nonessential action, the child continues other safe in-scope work and reports the blocked item in its terminal receipt. If the action is required for the assigned outcome, it returns one terminal `approval-blocked` receipt. Do not repeat the exact blocked action or assign the same permission-class and owner-scope boundary to another child until host evidence proves a reusable grant applies.
- After two decision-directed attempts leave the same uncertainty unchanged, stop trying role variants and obtain the smallest discriminating observation in the primary.

## Review and converge

1. Admit review only for an exact high-risk invariant or an explicit user request. Freeze only after writers are terminal and primary integration and direct checks are complete. Any relevant change invalidates prior gate results.
2. Before assigning a writer or reviewer, record a compact matrix: each invariant, its smallest counterexample, owning boundary or seam, positive implementation evidence, and required negative, restart, or recovery proof. Do not use a reviewer to discover this matrix.
3. Freeze a candidate receipt containing the exact revision or state fingerprint, relevant diff or artifact fingerprint, named-invariant fingerprint, and completed direct checks. A reviewer handoff without this receipt is incomplete.
4. Treat a reviewer as an evidence gate, not a designer or requirements source. The primary adjudicates every finding against the acceptance anchor. A missing-field rejection is a contract retry, not an effective review; correct the handoff and start a fresh reviewer without following up the rejected reviewer.
5. Repair accepted blockers, verify directly, refreeze, and run one fresh recheck. If it still blocks, stop the automatic review loop and return to first principles. Another independent review requires a changed candidate or new discriminating evidence and a new expansion checkpoint.
6. Explicit multi-review is one batch of at most three fresh reviewers with disjoint invariants on one frozen state; no voting or design workshop. Use `risk_reviewer_max` only through the escalation route defined above, never as a routine second opinion.

## Close with evidence

- Sample child evidence and owned artifacts without replaying the scan. Confirm that execution stayed within the selected role and scope. Treat policy tests as local consistency evidence only; installation and client readback prove loading, not production efficiency. Label source-only evidence `verified-local`.
- Close only with claim-matched evidence for the acceptance anchor, explicit abandonment or supersession, or a genuine user-owned blocker. A child terminal state, gate line, install, test, or exhausted budget closes only its own sub-boundary.
- Stop delegating when orchestration overhead approaches the work it replaces. Do not add a harness, schema, installer feature, authority system, reviewer hierarchy, or benchmark before a real task demonstrates the need.

Read the [advanced routing policy](references/routing-policy.md) only for a second child, later wave, custom-role transition, or review. Read the [evaluation policy](references/evaluation-policy.md) only for an actual routing comparison or efficiency claim; it does not govern routine Skill execution.

# Delegation Contracts

Set `agent_type` in the orchestration call; do not repeat it as a handoff field. Send one lean English handoff per child and state each instruction once:

```text
Task: <one bounded result>
Scope: <exact paths, artifact, or read-only surface>
Context: <only essential task-local facts>
Return: <English receipt or artifact and observable done condition>
Boundaries: <writes, external actions, recursion, overlap, stale state, or scope expansion>
```

Add `State` only for mutable work or a frozen review. For a frozen review, also add a `Candidate receipt` with the exact revision or state fingerprint, relevant diff or artifact fingerprint, named-invariant fingerprint, and completed direct checks. Add only the selected role's required fields:

- `evidence_tester`: `Acceptance fields` and one `Artifact contract` naming its path, format, and receipt rule.
- `boundary_mapper`: `Acceptance fields`; add `Artifact contract` only when an artifact is requested, otherwise use `none`.
- `risk_reviewer`: `Named invariants`, `Escalation receipt: not-applicable`, and `Artifact contract: none`.
- `risk_reviewer_max`: `Named invariants`, `Artifact contract: none`, and an `Escalation receipt` containing the prior standalone `Gate recommendation: INDETERMINATE / ESCALATE`, the exact invariants still in dispute, positive and negative evidence for each competing causal explanation, and the named irreversible decision the ambiguity can change.

If any required handoff field is absent or invalid, the child does no task work and returns exactly one terminal line: `Handoff status: REJECTED / MISSING_FIELDS: <comma-separated exact field names>`. The primary may correct the handoff and start a new leaf linked to the rejected invocation; do not follow up the rejected reviewer, and do not count the rejected invocation as an effective review.

Inherited context does not widen authorization. Use the smallest task-local context fork: bounded recent context for an operational leaf and no parent turns for a fresh reviewer. Fork selection is not a model selector or permission grant. Do not include expected conclusions, mutable facts the child can read in scope, or repeated policy. Require the child to stop at unlisted boundaries, remain a leaf, and avoid peer coordination. Keep one active writer with no overlapping write scope. Integrate only after the required terminal receipts arrive.

If authorization blocks only an optional action, require the child to continue other safe in-scope work and list the blocked item in its terminal receipt. If it blocks the assigned result, require one terminal `approval-blocked` receipt naming the permission class, exact action, owner scope, and completed remainder. Do not repeat that action, widen authorization, or assign the same permission-class and owner-scope boundary to a later child until host evidence proves a reusable grant applies to child threads.

Terminal state closes transferred work only. Authorization, conflict resolution, finding adjudication, expansion checkpoints, commits, and acceptance of the user-requested result remain with the primary.

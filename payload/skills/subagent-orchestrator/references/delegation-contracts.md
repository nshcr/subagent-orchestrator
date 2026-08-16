# Delegation Contracts

Use one compact, immutable handoff per child:

```text
Objective: <one bounded outcome>
Owned scope: <exact paths, artifact, or read-only surface>
State: <revision or deterministic state summary>
Input summary: <only task-local facts the child needs>
Deliverable: <receipt, evidence, or owned artifact>
Done when: <observable acceptance condition>
Stop when: <scope, authority, overlap, or stale-state boundary>
Forbidden: <writes, external actions, recursion, or scope expansion>
```

Add role-specific fields only when the role requires them:

- `evidence_tester`: `Acceptance fields` and one `Artifact contract`.
- `boundary_mapper`: `Acceptance fields`; artifact only when requested.
- `risk_reviewer`: `Named invariants`, `Escalation receipt: not-applicable`,
  `Artifact contract: none`, and `Output audience`.
- `risk_reviewer_max`: the same fields plus the prior indeterminate terminal line,
  competing evidence, and irreversible decision.

Do not add expected conclusions to a handoff. A child reports one bounded outcome and
stops when it discovers an unlisted boundary. The primary may sample cited evidence,
but must not repeat the transferred scan or rewrite a writer-owned artifact.

Use `send_message` only for new admitted evidence needed by a running built-in child.
Use `followup_task` only once for a missing acceptance field or new failure evidence
inside the original scope. Never use either tool for status polling, reviewer redesign,
or scope expansion.

Every required child reaches a terminal state before final acceptance. The primary
owns authorization, conflict resolution, integration, user checkpoints, and commits.

# Delegation Contracts

Use one lean handoff per child. State each instruction once:

```text
Task: <one bounded outcome>
Scope: <exact paths, artifact, or read-only surface>
Context: <only essential task-local facts>
Return: <receipt or artifact and observable done condition>
Boundaries: <writes, external actions, recursion, overlap, stale state, or scope expansion>
Output audience: <user-facing or model-facing>
```

Add `State` only for mutable work or a frozen review. Add role-specific fields only
when the role requires them:

- `evidence_tester`: `Acceptance fields` and one `Artifact contract`.
- `boundary_mapper`: `Acceptance fields`; artifact only when requested.
- `risk_reviewer`: `Named invariants`, `Escalation receipt: not-applicable`, and
  `Artifact contract: none`.
- `risk_reviewer_max`: the same fields plus the prior indeterminate terminal line,
  competing evidence, and irreversible decision.

Do not add expected conclusions, full conversation history, repeated policy text, or
facts the child can cheaply read inside its owned scope. A child reports one bounded
outcome and stops when it discovers an unlisted boundary. The primary may sample cited
evidence, but must not repeat the transferred scan or rewrite a writer-owned artifact.
Keep the original user outcome as a primary-side acceptance anchor; include it in a
handoff only when the child needs it to avoid mistaking its slice for task closure.
Keep one active writer and no overlapping write scopes. Primary integration waits for
the writer's terminal receipt.
An existing handoff never authorizes a later wave, another writer, reviewer rerun, or
scope expansion; authorization must name that exact expansion.
Before a later wave, collect every current required child to terminal state and
integrate its receipt. Authorization cannot waive ownership or state freshness.

Use `send_message` only for new admitted evidence needed by a running built-in child.
Use `followup_task` only once for a missing acceptance field or new failure evidence
inside the original scope. Never use either tool for status polling, reviewer redesign,
or scope expansion.

Every required child reaches a terminal state before final acceptance, but that state
closes only the transferred work, not the user task. The primary owns authorization,
conflict resolution, integration, expansion checkpoints, evidence-based task closure,
and commits.

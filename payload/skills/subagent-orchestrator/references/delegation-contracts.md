# Delegation Contracts

Send one lean English handoff per child. State each instruction once:

```text
Task: <one bounded outcome>
Scope: <exact paths, artifact, or read-only surface>
Context: <only essential task-local facts>
Return: <English receipt or artifact and observable done condition>
Boundaries: <writes, external actions, recursion, overlap, stale state, or scope expansion>
```

Add `State` only for mutable work or a frozen review. Add only the selected role's fields:

- `evidence_tester`: `Acceptance fields` and one `Artifact contract`.
- `boundary_mapper`: `Acceptance fields`; `Artifact contract` only when requested.
- `risk_reviewer`: `Named invariants`, `Escalation receipt: not-applicable`, and
  `Artifact contract: none`.
- `risk_reviewer_max`: the reviewer fields plus the prior indeterminate terminal line,
  competing evidence, and irreversible decision.

Do not include expected conclusions, full history, repeated policy, or facts cheaply
readable inside the owned scope. A child stops at an unlisted boundary and does not
delegate or message peers. The primary samples cited evidence rather than repeating the
scan, and never rewrites a worker-owned artifact before integration.

Keep one active writer and no overlapping write scopes. Wait for terminal receipts before
integration or a later wave. An existing handoff never authorizes another writer, scope
expansion, reviewer rerun, or new wave.

Use `send_message` only to deliver new admitted evidence to a running built-in child. Use
`followup_task` only for a missing acceptance field or new failure evidence inside the
original scope, never for polling, redesign, or expansion.

Every required child becomes terminal before final acceptance, but that closes only its
transferred work. The primary owns authorization, conflict resolution, finding
adjudication, expansion checkpoints, commits, and acceptance against the user outcome.

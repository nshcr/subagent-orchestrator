# Delegation Contracts

Send one lean English handoff per child. State each instruction once:

```text
Task: <one bounded outcome>
Scope: <exact paths, artifact, or read-only surface>
Context: <only essential task-local facts>
Return: <English receipt or artifact and observable done condition>
Boundaries: <writes, external actions, recursion, overlap, stale state, or scope expansion>
```

Add `State` only for mutable work or a frozen review. Add only the selected
role's fields:

- `evidence_tester`: `Acceptance fields` and one `Artifact contract` naming its
  path, format, and receipt rule.
- `boundary_mapper`: `Acceptance fields`; add `Artifact contract` only when
  requested.
- `risk_reviewer`: `Named invariants`, `Escalation receipt: not-applicable`, and
  `Artifact contract: none`.
- `risk_reviewer_max`: the reviewer fields plus the prior indeterminate terminal
  line, competing evidence, and irreversible decision.

Do not include expected conclusions, full history, repeated policy, or facts
cheaply readable inside the owned scope. Require each child to stop at an
unlisted boundary and prohibit delegation or peer messaging. Sample cited
evidence instead of repeating the scan, and do not rewrite a worker-owned
artifact before integration.

Keep one active writer and no overlapping write scopes. Wait for terminal
receipts before integration or a later wave. Do not treat an existing handoff or
expansion checkpoint as authorization for recursion, overlap, another writer,
scope expansion, reviewer rerun, or a new wave.

Use `send_message` only to deliver new admitted evidence to a running built-in
leaf. Use `followup_task` only for a missing acceptance field or new failure
evidence inside that leaf's original scope. Never message custom roles, poll
status, request redesign, or widen scope through either tool.

Require every necessary child to become terminal before final acceptance, but
treat that state as closure of transferred work only. Keep authorization,
conflict resolution, finding adjudication, expansion checkpoints, commits, and
acceptance against the user outcome in the primary.

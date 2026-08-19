# Delegation Contracts

Send one lean English handoff per child. State each instruction once:

```text
Spawn: agent_type=<explicit non-default role>
Task: <one bounded outcome>
Scope: <exact paths, artifact, or read-only surface>
Context: <only essential task-local facts>
Return: <English receipt or artifact and observable done condition>
Boundaries: <writes, external actions, recursion, overlap, stale state, or scope expansion>
```

Bind every spawn to the declared non-`default` `agent_type`. Keep the handoff
context within the role's declared boundary; inherited context does not widen
authorization. If no specialized role fits, keep the work in the primary.

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

Do not include expected conclusions, mutable state, repeated policy, or facts
cheaply readable inside the owned scope. Require each child to stop at an
unlisted boundary and prohibit delegation or cross-child coordination. Sample cited
evidence instead of repeating the scan, and do not rewrite a worker-owned
artifact before integration.

Keep one active writer and no overlapping write scopes. Wait for terminal
receipts before integration or a later wave. Do not treat an existing handoff or
expansion checkpoint as authorization for recursion, overlap, another writer,
scope expansion, reviewer rerun, or a new wave.

If host approval still rejects an operational leaf, return one terminal
`approval-blocked` receipt naming the permission class, exact action, and owner
scope, then stop. The primary records that task-scoped permission circuit and
finishes the work directly. Do not repeat the blocked action, widen authorization,
or assign the same permission-class and owner-scope boundary to a later child.
Clear the circuit only after host evidence proves a reusable grant applies to
child threads; a parent grant or assertion alone is insufficient.

Require every necessary child to become terminal before final acceptance, but
treat that state as closure of transferred work only. Keep authorization,
conflict resolution, finding adjudication, expansion checkpoints, commits, and
acceptance against the user outcome in the primary.

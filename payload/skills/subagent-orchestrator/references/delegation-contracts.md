# Delegation Contracts

Send one lean English handoff per child. State each instruction once:

```text
Spawn: agent_type=<explicit non-default role>; fork_turns=<1 operational, none review>
Task: <one bounded outcome>
Scope: <exact paths, artifact, or read-only surface>
Context: <only essential task-local facts>
Return: <English receipt or artifact and observable done condition>
Boundaries: <writes, external actions, recursion, overlap, stale state, or scope expansion>
```

Bind every spawn to the declared non-`default` `agent_type`. Use
`fork_turns="1"` for `explorer`, `worker`, `evidence_tester`, and
`boundary_mapper`; this retains the current user turn without predicting which
tool may later require approval. Use `fork_turns="none"` for fresh review roles.
Never use a larger or full-history fork. Inherited context does not widen
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

Do not include expected conclusions, full history, repeated policy, or facts
cheaply readable inside the owned scope. Require each child to stop at an
unlisted boundary and prohibit delegation or peer messaging. Sample cited
evidence instead of repeating the scan, and do not rewrite a worker-owned
artifact before integration.

Keep one active writer and no overlapping write scopes. Wait for terminal
receipts before integration or a later wave. Do not treat an existing handoff or
expansion checkpoint as authorization for recursion, overlap, another writer,
scope expansion, reviewer rerun, or a new wave.

Allow at most one primary-to-leaf update across `send_message` and
`followup_task` for an operational leaf: `explorer`, `worker`,
`evidence_tester`, or `boundary_mapper`. Use `send_message` to deliver newly
admitted evidence to a running leaf. Use `followup_task` only for a missing
acceptance field or new failure evidence inside the original scope. Never send
either update to `risk_reviewer` or `risk_reviewer_max`; changed review evidence
requires a refreeze and fresh reviewer. Never poll status, request redesign, or
widen scope through either tool.

If host approval still rejects an operational leaf, return one terminal
`approval-blocked` receipt naming the permission class, exact action, and owner
scope, then stop. The primary records that task-scoped permission circuit and
finishes the work directly. Do not retry, respawn, inherit more history, resume,
await a reply, or assign the same permission-class and owner-scope boundary to a
later child. Clear the circuit only after host evidence proves a reusable grant
applies to child threads; a parent grant or assertion alone is insufficient.

Require every necessary child to become terminal before final acceptance, but
treat that state as closure of transferred work only. Keep authorization,
conflict resolution, finding adjudication, expansion checkpoints, commits, and
acceptance against the user outcome in the primary.

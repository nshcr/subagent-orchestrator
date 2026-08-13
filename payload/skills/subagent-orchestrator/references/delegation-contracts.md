# Delegation Contracts

Use one state-bound contract per child:

```text
Objective: <one bounded outcome>
Owned scope: <files, artifact, or commands>
State hash: <revision or deterministic hashes>
Changed paths: <changes since supplied evidence>
Evidence manifest: <already established facts>
Read allowlist: <smallest additional scope>
Transferred work: <raw work the primary will not repeat>
Primary sampling: <small verification only>
Forbidden: <writes, external state, Git, recursion, or scope expansion>
Evidence required: <artifact, commands, exits, citations, checklist>
Output audience: <user-facing | model-facing>
Completion dependency: <required-before-integration | independent-before-final>
Concurrent peers: <none | non-overlapping task names>
User deadline: <none | explicit user condition>
Cancellation authority: <user cancel/replace, concrete safety/scope violation, proven stale state, terminal platform failure, or explicit user deadline>
Done when: <acceptance condition>
Stop when: <ambiguity, overlap, authority, or stale state>
```

The primary must set `Output audience` explicitly. For `user-facing` output,
use the user's preferred language. For `model-facing` output, use English.
Preserve requested schemas, literal values, source identifiers, and domain terms
exactly in either mode.

`Stop when` tells the child when to return evidence; it does not authorize the
primary to cancel a running turn. A wait timeout, silence, elapsed wall time,
token or credit use, and repeated observation timeouts are non-terminal and are
not stale-state evidence. Terminal means a final receipt, an explicit runtime
failure, or acknowledgement of an authorized cancellation. Track each task name,
dependency, state hash, concurrent peers, last observed runtime state, and any
authorized cancellation reason until terminal. Every spawned child must reach a
terminal state before the primary ends. Do not start a replacement while the
original remains running. If a required child is still running, continue
independent work or wait again.

Pass task-local facts with `fork_turns="none"` and name the task
`<role>__<purpose>`. Reject imprecise or out-of-scope receipts. A child that
discovers an unlisted boundary reports it and stops. Use `followup_task` only
for the same evidence scope; use a fresh agent when independence is required.

Preserve one writer per path. If a write-capable role owns an artifact, the
primary samples but does not rewrite it. If a read-only role returns a canonical
body between `ARTIFACT_BODY_BEGIN` and `ARTIFACT_BODY_END`, copy only that body
verbatim, then sample cited evidence. Never translate, reorder, or summarize a
canonical body while transferring it.

The primary always owns authorization, conflict handling, integration, and
final acceptance. Every custom role is non-recursive.

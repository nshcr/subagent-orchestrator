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
Acceptance fields: <not-applicable | one or more exact output-heading labels>
Named invariants: <not-applicable | one or more exact gate invariants>
Escalation receipt: <not-applicable | prior terminal line + sufficient evidence + competing explanations + irreversible decision>
Artifact contract: <none | path or body + format + writer + transfer rule>
Output audience: <user-facing | model-facing>
Completion dependency: <required-before-integration | independent-before-final>
Concurrent peers: <none | non-overlapping task names>
User deadline: <none | explicit user condition>
Cancellation authority: <user cancel/replace, concrete safety/scope violation, proven stale state, terminal platform failure, or explicit user deadline>
Done when: <acceptance condition>
Stop when: <ambiguity, overlap, authority, or stale state>
```

These four fields are typed and must always be present. Use `Acceptance fields`
for field-driven evidence work, `Named invariants` for an independent gate, and
`Escalation receipt` only for an evidence-qualified terminal escalation. Use
`Artifact contract` whenever the child must write or return a canonical artifact;
otherwise set it to `none`. `not-applicable` and `none` are literal values, not
permission to omit a field. A role may reject a typed value that does not satisfy
its own applicability rules.

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

A gate receipt ends with exactly one standalone terminal protocol line. Without
an artifact body it is the final non-empty line. With an artifact body it is the
final non-empty line before `ARTIFACT_BODY_END`, and nothing may follow except
that marker. The gate role defines the allowed terminal lines and must put any
evidence threshold, reason, or bounded recheck before the terminal line.

The primary always owns authorization, conflict handling, integration, and
final acceptance. Every custom role is non-recursive.

## Portable adapter contract

A client adapter must preserve these package-owned requirements exactly:

- `preserve-role-eligibility`
- `preserve-permission-boundaries`
- `preserve-non-recursion`
- `preserve-terminal-collection`
- `preserve-output-language-contract`
- `treat-model-and-effort-values-as-client-specific-hints`

An adapter may translate syntax, but it must not broaden a role's task class or
permissions, allow recursive delegation, drop terminal collection or language
rules, or treat client-specific model and effort hints as portable guarantees.

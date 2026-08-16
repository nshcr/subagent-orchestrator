# Delegation Contracts

## Slice and immutable work transfer

Open one delivery slice before any child:

```text
slice_open: <top-level task id + unique slice id>
Acceptance milestone: <exactly one>
Change class: <exactly one>
Owner paths: <exact paths>
Required gate IDs: <disjoint registry IDs>
State summary/digest: <facts + canonical digest>
```

Give each child a digest-bound immutable work transfer:

```text
Producer / consumer / task / slice: <identities>
Route / topology / delegation depth: <route + leaf|bounded-peer + 0|1>
Input summary: <admitted evidence only>
Sampling allowlist: <canonical proper subset>
Admitted state digest: <digest>
Status: admitted
Artifact/receipt digest: <null until terminal>
Completion conditions: <exact conditions>
Forbidden actions: <writes, external state, Git, recursion, messages, expansion>
Output audience: <user-facing | model-facing>
Acceptance fields: <not-applicable | exact labels>
Named invariants: <not-applicable | exact invariant IDs>
Escalation receipt: <not-applicable | prior terminal line + evidence + decision>
Artifact contract: <none | path/body + format + writer + transfer rule>
```

All fields are typed and mandatory. Default to fresh context and
`fork_turns=none`; full-history is never eligible. User-facing output follows the
user's language; model-facing output uses English. Preserve identifiers and schemas.
The admitted-state digest is the canonical hash of the complete transfer payload.

## Materiality and primary access

Explorer/worker eligibility requires a host, owner, or sealed-harness issued
materiality manifest. An agent cannot issue or proxy it. Every source range binds
path, path hash, start/end, content hash, and non-padding bytes. Ranges are immutable,
task-wide unique, non-overlapping, and deduplicated by content. Padding, repeated
content, synthetic splitting, tiny leaf work, and verification-token assets fail.
The routing validator owns route-specific minimum unique paths and bytes.
The manifest digest is the canonical hash of issuer, asset kind, and every range;
changing any payload field without changing that digest fails.

The primary records every source access for the top-level task. Only a receipt-bound
targeted precheck and strict proper-subset sampling, with unique ranges and bytes no
more than 10% of one frozen task-wide manifest denominator, qualify. Opaque attribution, unavailable attribution,
pre-spawn scanning, full-manifest laundering, or reconstruction replay blocks policy
promotion. Integration may read receipts, artifacts, and changed files, but must not
repeat the transferred source scan or rewrite the writer-owned artifact.

## Owner components, freeze, and gates

Each slice permits at most one writer. It owns a task-wide canonical component. Path overlap and rename old/new,
split, or merge union aliases permanently across slice, commit, and rollover. Reject
overlapping active writers. Count writer compactions by task plus canonical component;
after two, reject another writer spawn or follow-up. Never cancel an already-running
child for this limit; accept its safe incomplete receipt.

Freeze only after writer terminal. Tester, reviewer, gate, and close each recompute
HEAD, index, worktree, and complete changed-path digests from the filesystem. Any
change invalidates all gates. Each invariant belongs to exactly one task-wide gate;
duplicate ownership, overlap, voting, and majority decisions are invalid. Three
disjoint final gates must PASS fresh attempt N on one final hash. Repair or hash
change requires every gate at attempt N+1. Reviewers are read-only and never repair
or self-review. Close requires identical readback, all required fresh PASS results,
and a terminal complete task tree.

## Messages, follow-ups, and terminal receipts

`send_message` targets a running admitted built-in child and carries only digest-bound
evidence, dependency status, or artifact receipt with producer, consumer, dependency,
and a canonical payload digest; dependency must be non-empty. It cannot start a turn or change authority, scope, ownership, topology,
or handoff. Custom-role and unregistered peer messages are hard blockers.

`followup_task` targets an idle/terminal built-in child, preserves scope, and uses
exactly one reason: `new_failure_evidence`, `missing_acceptance_field`, or
`authorized_continue`. Its scope digest must equal the original admitted work-transfer.
Status polling, custom-role follow-up, reviewer repair/review,
scope growth, and exhausted-writer follow-up are hard blockers.

Every child reaches terminal with status, artifact/receipt digest, completion digest,
and any safe incomplete receipt. A gate receipt ends in its role's exact standalone
protocol line. Preserve canonical `ARTIFACT_BODY_BEGIN` / `ARTIFACT_BODY_END` bodies
verbatim. The primary owns authorization, integration, conflict handling, and acceptance.

## Portable adapter contract

An adapter must preserve: `preserve-role-eligibility`, `preserve-permission-boundaries`,
`preserve-governed-leaf-non-recursion`, `preserve-bounded-peer-depth`,
`preserve-peer-message-boundary`, `preserve-terminal-collection`,
`preserve-output-language-contract`, and
`treat-model-and-effort-values-as-client-specific-hints`.

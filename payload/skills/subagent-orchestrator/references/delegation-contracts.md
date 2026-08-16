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

Executable canonical snake-case fields are `producer`, `consumer`, `task_id`, `slice_id`, `route`, `topology`, `delegation_depth`, `input_summary`, `sampling_allowlist`, `admitted_state_digest`, `status`, `artifact_receipt_digest`, `admitted_receipt_digests`, `completion_conditions`, `forbidden_actions`, `output_audience`, `acceptance_fields`, `named_invariants`, `escalation_receipt`, and `artifact_contract`.
Exact keys and strong types are mandatory; route, topology, and depth equal spawn, and the admitted-state digest binds every other field. Default to fresh `fork_turns=none`;
preserve schemas, identifiers, and the user/model language contract.
Non-sentinel escalation receipts have exact `prior_terminal_line`, `evidence`, `competing_explanations`, and `irreversible_decision` fields with at least two distinct explanations. Non-`none` artifact contracts have exact `artifact_kind`, `artifact_path`, `artifact_format`, `artifact_writer`, and `receipt_transfer_rule` fields; kind is `path` or `body`, path-kind paths are safe, and writer equals the named child.

## Materiality and primary access

Explorer/worker eligibility requires host/owner/sealed-harness materiality plus authority outside the trace. Pre-index primary and every child, parent, and registered role identity, including later spawns; none may issue or proxy.
Authority binds issuer class/identity, task, slice, child, source identity, range count, non-padding bytes, and manifest digest. Every range binds path, path hash, bounds, content hash, and non-padding bytes. Ranges are immutable,
task-wide unique, non-overlapping, and deduplicated by content. Padding, repeated
content, synthetic splitting, tiny leaf work, and verification-token assets fail.
The routing validator owns route-specific minimum unique paths and bytes.
The manifest digest binds issuer, task/slice, asset kind, source identity, byte
accounting, and every range. SHA-256 proves payload binding, not issuer authenticity;
changing issuer and rehashing still fails unless the external trust set admits it.

The primary records every source access for the top-level task. Only a receipt-bound
targeted precheck and strict proper-subset sampling, with unique ranges and bytes no
more than 10% of one frozen task-wide manifest denominator, qualify. Opaque attribution, unavailable attribution,
pre-spawn scanning, full-manifest laundering, or reconstruction replay blocks policy
promotion. Integration declares zero source ranges/bytes and consumes only previously
admitted artifact or changed-path receipt digests; it must not repeat the transferred
source scan or rewrite the writer-owned artifact.

Each trace document has exactly one scenario for each non-empty unique top-level `task_id`.
Rollover is events inside that scenario; materiality, sampling, owner, compaction, gate,
admission, and receipt state is task-wide and cannot reset in another scenario.

## Owner components, freeze, and gates

Each slice permits one writer. Every writer path equals or descends from `slice_open.owner_paths`; its component connects to that slice, and path-kind artifacts stay inside writer/slice paths.
Path overlap, rename old/new, split, or merge still unions aliases permanently across slice, commit, and rollover. Reject overlapping active writers. Host compaction receipts bind
task, slice, child, canonical owner component, prior receipt, current count, and
cumulative count; terminal self-reporting is not authority. Cumulative count starts
at zero; after two, reject another writer spawn or follow-up. Never cancel an already-running
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

`send_message` targets a running admitted built-in child and carries only digest-bound evidence,
dependency status, or artifact receipt with task, slice, original transfer scope, producer,
consumer, typed purpose, admitted receipt, dependency, and a canonical message semantic digest.
The semantic payload excludes only `admission_anchor_digest` and `digest`, preventing an
authority-anchor cycle while binding every other field. Authority binds that semantic digest,
canonical dependency digest, exact purpose, receipt, and scope; self-rehashing fails. It cannot start a turn or change authority, scope, ownership, topology, or handoff.
Custom-role and unregistered peer messages are hard blockers.

`followup_task` targets an idle/terminal built-in child, preserves scope, and uses
exactly one reason: `new_failure_evidence`, `missing_acceptance_field`, or
`authorized_continue`. Its scope digest must equal the original admitted work-transfer.
Status polling, custom-role follow-up, reviewer repair/review,
scope growth, and exhausted-writer follow-up are hard blockers.

A default bounded peer requires separate trace-external host capability and material-relay
receipts. The relay binds task/slice, peer, producer, consumer, artifact, consumer transfer,
exact `artifact_receipt` purpose, canonical dependency/message digests, and primary-relay
removal. Its artifact comes from the named producer's terminal receipt and is admitted by
the consumer transfer. Missing descendants, capability, producer artifact, or relay is a no-op.
Custom roles remain nonrecursive governed leaves without peer messaging.

Any trace declaring `pilot`, `pilot-signed`, or promotion includes `pilot_admission`
after freeze. Its revision is the exact frozen HEAD; a repair/hash generation change
requires new authorization before close.
The host authorization anchor outside the trace binds task/slice, non-empty string
actions, target identity, revision, package/contract digests, validity, exact excluded
active-task IDs, and authorization event/text digests. Missing, proxy/self-issued,
expired, cross-scope, active-task, type-invalid, or normalized create/auto-create
authorization using spaces, punctuation, underscores, or camel case fails.

Every child reaches terminal with status, artifact/receipt digest, completion digest, and any
safe incomplete receipt. A gate receipt ends in its role's exact standalone protocol line.
Preserve canonical `ARTIFACT_BODY_BEGIN` / `ARTIFACT_BODY_END` bodies verbatim. The primary owns authorization, integration, conflict handling, and acceptance.

## Portable adapter contract

An adapter must preserve: `preserve-role-eligibility`, `preserve-permission-boundaries`,
`preserve-governed-leaf-non-recursion`, `preserve-bounded-peer-depth`, `preserve-peer-message-boundary`,
`preserve-terminal-collection`, `preserve-output-language-contract`, and `treat-model-and-effort-values-as-client-specific-hints`.

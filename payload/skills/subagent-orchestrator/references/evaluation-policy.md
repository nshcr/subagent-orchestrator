# Evaluation Policy

## Objective and cost boundary

Apply this lexicographic order without weighted averaging: authorization, safety,
correctness, and evidence integrity; higher stable verified quality; then lower
end-to-end ChatGPT credits when quality is indistinguishable. Never trade quality
for cost. Wall time is telemetry only.

Use complete paired thread/run credits for every primary, child, integration, failed
attempt, repair, review, and retry. Do not infer role-, wait-, message-, token-, or
tool-level credits. Raw usage tokens, especially cached input, are not billable
credits. Missing or unavailable credits cannot aggregate or promote.

Use the Standard/default service tier for promotion. Fast mode changes latency and
multiplies GPT-5.6 ChatGPT credits by 2.5; use it only when the user explicitly adds
latency as an objective, and exclude that experiment from quality/credits promotion.

## Paired promotion and governance retention

Use at least three materially different instances from three fixture families per
class, paired baseline/custom with arm order alternated, plus a frozen external
sealed holdout. Repeated fixtures measure stability, not generalization. Freeze
role instructions, routing, fixtures, and graders before holdout. A changed role or
eligibility invalidates prior class evidence; a topology-only change needs deterministic
lifecycle conformance and a current client capability receipt.

Compute normalized quality per paired instance before class or overall summaries.
Any instance/class quality regression, escaped critical defect, authority violation,
nonterminal tree, evidence-integrity failure, or incomplete cost blocks promotion.
Every efficiency branch requires custom credits no worse for each pair, every class,
and overall. Higher quality with non-regressing cost promotes. A quality tie additionally
requires both overall paired median and overall credits at least 10% lower.
Copied labels, keywords, prescribed phrases, and checklist surface form earn no
quality credit without the required source fact or executable behavior. Acceptance
labels define evidence schema, never expected conclusions.

Report `governance_retention` separately from `efficiency_promotion`. A mandatory
named safety gate with no callable equivalent may be `retained-not-efficient` when
quality, safety, independence, and integrity pass but cost regresses or is unavailable;
it cannot claim efficiency success. Quality or integrity failure blocks retention.
Retire any other installed role with no promoted class. Reviewer effort experiments
never retire the accepted named gate; a failed candidate returns to the last accepted
fixed effort.

## Production facts and policy promotion

`production-fact.v1` binds parent rollout, child root, cutoff, repository, and base.
Lineage begins only at the first UUIDv7 child turn context after spawn; copied parent
history and missing/ambiguous lineage are rejected. Every metric has
`{status,basis,source_id,value}`; only unavailable uses null and unavailable values
never aggregate. Record tokens, exact full-run credits, Git denominators, wait/message/
compaction events, concurrency, and log bytes separately.

Active, dirty, unsupported, incomplete, or observational facts cannot prove completion
or causality. Primary access with opaque/unavailable attribution, pre-spawn scanning,
full-manifest laundering, reconstruction replay, owner overlap, invalid message,
nonterminal descendants, or stale gate readback blocks policy promotion.

## Evidence tiers and pilot admission

Evidence advances monotonically: `implemented` -> `verified-local` -> `verified-ci`
-> `verified-target` -> `pilot-signed`. Each receipt binds the exact predecessor digest,
revision, package, target, evidence producer, and artifacts; narrative assertions do
not advance a tier. Missing CI, target, or signature evidence caps the result at
`verified-local`. Production observation never implies `pilot-signed`.

Pilot follows the frozen final state and requires a host-issued admission receipt binding the user's authorization event
and text digests, grantor, authorized signer, task/slice and allowed actions, target,
revision, package and contract,
validity window, deterministic observed timestamp, exact frozen HEAD revision, and explicit excluded active task IDs.
The canonical receipt digest binds every field. Reject self-issued, proxied,
tampered, expired, cross-task, cross-target, or active-task admissions. The pilot must
not auto-create a task. `pilot-signed` cites the exact admission digest and signed
result; an active UTP task is excluded.
The host supplies the authorization anchor outside the trace. SHA-256 binds the
payload but is not signer authentication. Missing, type-invalid, auto-create, or
trace-only rehashed authorization fails closed. Repair or any final-hash generation
change makes the prior pilot authorization stale; normalized create-task and auto-
create-task actions fail regardless of spaces, punctuation, underscores, or camel case.

## Provenance and registry

Preserve original runs, sidecars, canonical receipts, graders, configuration hashes,
arm order, model/effort/tier, token categories, exact credits, retries, quality checks,
scope violations, holdout seal, contamination audit, access receipts, lifecycle trace,
and Git/readback hashes. Report each pair before class and overall aggregates.

Promoted custom classes remain the bounded `evidence_tester` and `boundary_mapper`;
fresh `risk_reviewer` is the mandatory named governance gate and
`risk_reviewer_max` only its one evidence-qualified runtime escalation. Built-in
explorer/worker/default are baseline routes, not promoted custom classes. Unsupported
or unstable work remains primary.

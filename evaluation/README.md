# Evaluation scaffold

This directory provides a standard-library-only validator and deterministic
reporter. It never calls models, graders, or the network.

Keep development evidence in the campaign JSON. Supply sealed evidence only
after external execution and grading:

```console
python -m evaluation validate --campaign campaign.json \
  --quality-authority /outside/repository/development-quality-authority.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --sealed-quality-authority /outside/repository/sealed-quality-authority.json
python -m evaluation report --campaign campaign.json \
  --quality-authority /outside/repository/development-quality-authority.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --sealed-quality-authority /outside/repository/sealed-quality-authority.json \
  --output report.json
python -m evaluation smoke
python -m evaluation production-facts \
  --parent /absolute/parent-rollout.jsonl \
  --children-root /absolute/child-rollouts \
  --repo /absolute/repository --base BASE_REV \
  --cutoff 2026-08-16T12:00:00+08:00 --source-state terminal \
  --output /absolute/production-fact.json
python -m evaluation evidence-tier \
  --input implemented.json --input verified-local.json
```

The sealed file has `schema_version`, `campaign_id`, frozen execution order,
seal and completion receipts, and `instances`; every instance must set `holdout`
to `true`. It uses the same instance shape defined in `campaign.schema.json` but
intentionally omits campaign policy and configuration hashes.
Development campaigns reject sealed instances, sealed inputs reject development
instances, unknown fields are rejected, and instance identifiers cannot overlap.
Expected answers and grader implementation are not campaign schema fields. Every quality
check instead records a `behavior` or `source-fact` evidence artifact digest, a
nonempty sidecar source identity, and a successful grader-execution receipt. The
canonical check-result digest binds check ID, pass/critical flags, score and
maximum, evidence kind, artifact digest, and source identity. The canonical
execution-receipt digest binds that result, the frozen grader, exact artifact and
source, zero exit code, and an external authority receipt. Development authority
is frozen in `configuration_hashes.grader_execution_authority_receipt`; sealed
authority is the external seal receipt. Neither campaign document is an authority:
the caller must provide a physically separate `quality-authority.schema.json`
document whose exact, unique admissions repeat the campaign/scope, task, fixture,
arm, check, artifact/source, grader, canonical result, canonical zero-exit receipt,
and authority identity. Missing, duplicate, type-invalid, cross-campaign, or
cross-scope admissions fail closed. Campaign and holdout documents contain only
the authority receipt digest reference; their closed schemas cannot embed the
authority admissions. Fixtures, expected answers, grader code,
artifact sidecars, and execution-receipt sidecars must be preserved outside this
repository and outside the tested agent's visibility boundary while their
identities enter the report.

Canonical SHA-256 checks prove deterministic payload binding, while the
`quality-evidence-authority.v2` signature authenticates the issuer against the
package-anchored public-key registry in `trusted_quality_issuers.py`. The
standard-library verifier accepts only RSA PKCS#1 v1.5 with SHA-256 and signs the
canonical complete authority payload: campaign digest and identity, scope,
authority identity and receipt, issuer/key/algorithm, and every admission. The
corresponding private signing key is external harness custody and must never be
included in this repository, package, examples, or tests. Changing the campaign,
scope, result, receipt, artifact/source, grader, or authority admission therefore
requires a new signature from that external issuer; self-recomputed hashes alone
cannot establish trust. Key rotation is a reviewed package change to the public
registry, not caller-controlled campaign data.

Each arm records every billed primary, child, review, repair, failed-attempt, or
retry thread separately, including its actual model, effort, service tier, token
categories, and credit categories. The reporter sums those decimal strings
exactly; wall time remains telemetry and is never part of its recommendation.

Thread `kind` is machine-typed as `primary` or `child`. A logical thread uses a
stable `thread_id`; every billed attempt is a separate record with contiguous
`attempt` values starting at 1 and a `completed`, `failed`, or `cancelled`
status. Only a failed attempt can precede a retry. `child_count` must equal the
number of unique child thread IDs, and `retries` must equal the number of
recorded attempts above 1. Reviews and repairs use `child` when delegated and
`primary` when performed by the primary agent; their purpose can be expressed
by the stable thread ID. Failed and cancelled attempts remain in credit totals.
Every record also preserves role, nullable parent ID, terminal state, model,
effort, service tier, raw token decomposition, and exact decimal
credit categories plus total. Exact cost records require four non-null decimal
categories with valid arithmetic; explicitly unavailable cost requires
`cost_complete=false` and four null categories. Validation reconciles expected
thread/receiver IDs, child and retry counts, terminal state, parent topology,
and all available token and credit arithmetic before a report can be emitted.
Custom receiver roles must equal the instance's single class-policy role; baseline roles must
come from a disjoint campaign allowlist. Child-to-child parents remain rejected
here because this reporter promotes the four governed custom leaf roles. The
built-in bounded-peer lane is a baseline runtime capability, not a fifth
promoted class; its session-local capability receipt is evaluated by the routing
and lifecycle gate and must not be injected as custom-role promotion evidence.

The campaign freezes a pricing-provenance hash and an exact global execution
order. Each instance must occur exactly twice in that order and its two entries
must match `arm_order`; the order must also exactly match the unique contiguous
`execution_index` recorded on every arm run. Development and sealed execution
orders remain separate in the report. Process exit/completion, routing violations, scope violations,
terminal state, role compliance, recursion, token completeness, and cost
completeness are all reported; any defect in either arm blocks promotion.
Baseline-first and custom-first allocation must also be deterministic and balanced
both overall and per task class: even counts require exact balance and odd counts
permit a difference of one. Mere presence of both orders is insufficient.

Promotion is paired and Pareto-safe. Every instance freezes SHA-256 identities
for its fixture and prompt; neither digest may be reused within or across the
development and sealed inputs. Execution identities and order remain unique.
Both arms must use the same grader and sorted
`(id, critical, max_score, evidence kind)` rubric signature. The report publishes
a digest of that signature. Prescribed phrases, copied labels, bare booleans, and
unbound scores are not accepted evidence kinds and cannot enter quality totals.

Normalized quality is compared on every paired instance, never by pooling raw
scores across different scales. One negative custom delta or any integrity
defect blocks both retention and promotion. An efficiency PASS additionally
requires complete exact credit evidence, positive baseline credits, every
paired custom/baseline ratio at most `1.00`, and class and overall aggregate
ratios at most `1.00`. When quality is tied, both the overall paired median and
aggregate ratios must be at most `0.90`. Raw token counts are never treated as
exact credits.

Each paired instance is also fail-closed for comparability. Baseline and custom
must use the same `grader_sha256` and the same rubric signature after sorting by
check ID: `(id, critical, max_score, evidence kind)`. Only observed `passed`,
`score`, bound artifact, and grader-execution receipts may differ between arms.
Development runs must also match the campaign's frozen
grader hash; sealed runs must match the external seal's grader hash. This contract
applies equally to development campaigns and externally injected sealed holdouts.

The external seal records its own receipt hash and binds runner, harness, grader,
expected-answer, fixture, prompt, and live-configuration hashes. It must attest
that the agent visibility
boundary was enforced and the runner was unlinked before tested agents started.
Completion must repeat the same receipt hash, bind results and archived-runner
hashes, require every tested thread to be terminal before archive, and require
valid records and clean contamination audits. The archived runner hash must equal
the sealed runner hash.

Class policy distinguishes ordinary `elective` promotion from a
`mandatory_named_gate`. Elective classes require `efficiency_promotion=PASS`.
A mandatory named gate exposes two independent results:
`governance_retention` covers frozen evidence, integrity, and per-instance
quality non-regression; `efficiency_promotion` adds the exact Pareto cost gates.
A retained gate therefore reports `retained-efficient` or
`retained-not-efficient`. Cost regression or unavailable cost evidence can
never produce an efficiency PASS, while integrity or quality regression blocks
retention itself.

## Production facts

`production-facts` emits `production-fact.v3` from one parent rollout, its exact
child rollout directory, and a Git repository at an explicit base revision and
cutoff. All input and output paths must be absolute and existing input types are
checked. A child must have one unambiguous parent spawn receipt and a UUIDv7
lineage. Accounting begins at its unique earliest post-spawn `turn_context`;
out-of-order or timestamp-ambiguous starts, copied pre-spawn history, duplicate
receivers, missing outputs, and orphan child logs are rejected.

The fact binds parser and complete raw-source hashes, Git revisions and trees,
hashed changed paths, commit/path/numstat/staged denominators, token decomposition,
explicit thread/run credits, spawn/start/failure counts, role and fork observations,
messages, waits, compactions, concurrency intervals, and admitted source byte
counts. Parent bytes stop at the cutoff. Child bytes start at the first admitted
post-spawn `turn_context`, so pre-start `session_meta` and other lineage-only bytes
remain source-bound but do not enter child or total accounting. Path strings are
SHA-256 hashed by default.
Token totals come only from canonical `event_msg` usage snapshots with
`payload.type=token_count` and the exact `info.total_token_usage` decomposition.
Token-named integers nested in unrelated supported events are ignored; malformed
canonical snapshots are rejected.

Every available Git denominator `source_id` canonically binds the metric name,
basis and value plus the explicit repository-path identity (`repo_path_sha256`),
base revision/tree, HEAD revision/tree, commit list and numstat inputs, index,
staged patch, status, and worktree/untracked identities. Changing the repository,
base, or index/worktree/staged state therefore cannot alias the same HEAD-based
provenance. Repeated extraction from the same repository and state is
deterministic, while content-identical clones have distinct source IDs.

Credit availability requires exactly one explicit thread record in every admitted
source and exactly one run record in the parent source. The exact supported
envelope has outer `event.type=event_msg` and a payload with
`type=billing_record`, `scope=thread|run`, one `thread_id` or `run_id`, and exact
decimal `credits` categories `uncached_input`, `cached_input`, `output`, and
`total`; aliases are unsupported. A billing payload under `session_meta` or any
other outer event type is excluded, counted as unsupported, and makes every
credit metric unavailable. Each record total, the thread aggregate, and the run
aggregate must reconcile. Missing, partial, ambiguous, or unsupported billing
evidence makes every credit metric unavailable; contradictory arithmetic is
rejected. The parser never derives credits from raw tokens and emits no per-role,
per-wait, or per-tool credit estimate.

Every reported measurement, including values below `metrics` and the two source
quality denominators, has exactly `{status,basis,source_id,value}`.
`unavailable` is equivalent to a null value and null provenance; an available
value requires parser basis and a source digest. Production JSONL is observational
evidence even when the source is terminal and all measurements are complete.
Therefore completion, causal, and promotion claim eligibility are always false;
unavailable metrics, active/incomplete sources, dirty or divergent Git state,
unsupported events, failed/nested spawns, and missing terminal observations remain
visible as additional evidence limitations.

## Schema migration

Campaign and sealed-holdout schema version 5 replaces version 4, and
`quality-evidence-authority.v2` replaces v1. Version 5 binds the exact campaign
digest and requires every external authority to carry a signature from a
package-trusted issuer/key over its complete canonical payload. Version 4
campaigns and v1 authorities are rejected. Migration must be performed and
signed by the external grader/harness after verifying the preserved result,
receipt, artifact, grader, campaign/scope, and identity sidecars; campaign or
authority authors cannot mint package trust by recomputing hashes.

`production-fact.v3` and `production-fact-parser.v3` replace their v2
counterparts. Version 3 requires the exact outer `event_msg` billing envelope and
includes explicit repository-path identity in every Git denominator source ID.
Consumers that require v2 must be updated; v2 facts are not accepted as v3.

## Evidence tiers

`evidence-tier.schema.json` and the `evidence-tier` command validate the exact
monotonic chain `implemented -> verified-local -> verified-ci -> verified-target
-> pilot-signed`. Each successor names the immediately preceding tier and the
SHA-256 of that predecessor's canonical JSON. Revision and package identity stay
constant across the chain. Each tier has an exact provenance object: source/diff
receipts, local command/environment/result, CI provider/run/revision/result,
target/environment/revision/package/receipt, then pilot authority/time/signature.
The pilot's target receipt must exactly equal the preceding verified-target
`receipt_sha256`. Narrative proxies, missing fields, a skipped tier, mismatched
identities or receipts, or an omitted pilot authority fail validation.

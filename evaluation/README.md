# Evaluation scaffold

This directory provides a standard-library-only validator and deterministic
reporter. It never calls models, graders, or the network.

Keep development evidence in the campaign JSON. Supply sealed evidence only
after external execution and grading:

```console
python -m evaluation validate --campaign campaign.json \
  --sealed-holdout /outside/repository/sealed-results.json
python -m evaluation report --campaign campaign.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --output report.json
python -m evaluation smoke
```

The sealed file has `schema_version`, `campaign_id`, frozen execution order,
seal and completion receipts, and `instances`; every instance must set `holdout`
to `true`. It uses the same instance shape defined in `campaign.schema.json` but
intentionally omits campaign policy and configuration hashes.
Development campaigns reject sealed instances, sealed inputs reject development
instances, unknown fields are rejected, and instance identifiers cannot overlap.
Expected answers and grader implementation are not schema fields. Only grader
hashes, quality results, and contamination-audit outcomes enter the report, so
fixtures, expected answers, and grader code can remain outside this repository
and inaccessible to tested agents.

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
credit categories plus total. Validation reconciles expected thread/receiver
IDs, child and retry counts, terminal/cost completeness, parent topology, and
the token and credit arithmetic before a report can be emitted. Custom receiver
roles must equal the instance's single class-policy role; baseline roles must
come from a disjoint campaign allowlist. Child-to-child parents are rejected as
recursive delegation.

The campaign freezes a pricing-provenance hash and an exact global execution
order. Each instance must occur exactly twice in that order and its two entries
must match `arm_order`; the order must also exactly match the unique contiguous
`execution_index` recorded on every arm run. Development and sealed execution
orders remain separate in the report. Process exit/completion, routing violations, scope violations,
terminal state, role compliance, recursion, token completeness, and cost
completeness are all reported; any defect in either arm blocks promotion.

Promotion is paired: both baseline and custom arms must pass every quality check
and contamination audit with zero critical failures and zero scope violations.
Quality improvement or a 10% median-credit reduction is considered only after
that two-arm integrity gate passes.

Each paired instance is also fail-closed for comparability. Baseline and custom
must use the same `grader_sha256` and the same rubric signature after sorting by
check ID: `(id, critical, max_score)`. Only observed `passed` and `score` values
may differ between arms. Development runs must also match the campaign's frozen
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
`mandatory_named_gate`. Elective classes use the quality-first/10%-credit rule.
A mandatory named gate may report `mandatory-custom` without the 10% saving only
when higher-level policy requires that exact role, no callable built-in
equivalent exists, the availability/removal probe is hash-bound, the role was
restored after the probe, and all evidence, sealed quality, integrity, and
independence gates pass with no custom quality loss. This is safety retention,
not an elective promotion or a reusable cost exception.

# Evaluation Policy

## Objective

Apply this lexicographic order without weighted averaging:

1. Preserve authorization, safety, correctness, and evidence integrity.
2. Prefer higher stable verified quality.
3. When quality is indistinguishable, prefer lower end-to-end ChatGPT credits.
4. When evidence is insufficient or unstable, use primary.

Never trade verified quality for lower credits. Record wall time only as
telemetry; never use it for routing, promotion, rejection, or tie-breaking.

## Cost boundary

Price uncached input, cached input, and output using every thread's actual model
and service tier. Include primary integration, failed attempts, repairs,
reviews, and retries. Reasoning tokens are already part of output tokens and
must not be counted twice.

Use the Standard/default service tier for this objective. Fast mode changes
latency rather than verified quality and currently multiplies GPT-5.6 ChatGPT
credits by 2.5; use it only when the user explicitly adds latency as an
objective, then keep that experiment outside quality/credits promotion data.
Refresh rates before a new campaign from official
[ChatGPT pricing](https://learn.chatgpt.com/docs/pricing) and
[Speed](https://learn.chatgpt.com/docs/agent-configuration/speed) documentation.

## Promotion and retirement

Evaluate each task class on at least three materially different task instances
from three fixture families. Pair baseline and custom on every instance and
alternate or randomize arm order. Repeating one fixture measures stability only;
it does not count as another generalization instance. Include a benign or
negative case for analytical roles and both PASS-eligible and BLOCK-eligible
states for a gate role when those outcomes are applicable.

Freeze the role instructions, routing policy, task fixtures, and graders before
opening at least one sealed holdout instance per class. Tested agents must not be
able to read grader logic or expected answers. A role instruction or eligibility
change invalidates prior promotion evidence for the affected class until a new
sealed holdout passes; never tune against the holdout and then count it as unseen.
A topology-only scheduling change that preserves custom role instructions,
eligibility, evidence schemas, and scoring does not invalidate those role
promotions. It requires deterministic state-machine conformance plus a current
client capability receipt before activation. Cover a delayed child across
multiple wait windows, an independent peer, bounded nested spawn and messaging,
permission inheritance, authorized cancellation, and full-tree terminal collection.

Score evidence-grounded capability rather than surface form. A copied label,
keyword, prescribed phrase, or checklist item earns no credit without the
required source fact, causal path, or executable behavior. Combine deterministic
anchors with blinded semantic review or executable checks where practical, and
include adversarial checks for keyword stuffing, contradiction, false blockers,
and omitted negative evidence.

Promotion requires all of the following:

- no authorization, safety, correctness, or evidence-integrity regression;
- no escaped P0/P1 defect compared with baseline;
- stable acceptance across distinct fixture families, including the sealed
  holdout, with no critical false positive or false negative;
- higher verified quality, or indistinguishable quality with median aggregate
  custom credits at least 10% below baseline;
- complete end-to-end credit accounting;
- no unbounded or unauthorized recursive delegation, overlapping writers, or
  primary reconstruction.

The 10% credit threshold governs elective custom promotion. An explicitly
mandatory named governance gate remains installed when no callable built-in
equivalent exists, provided it passes sealed quality, safety, independence, and
evidence-integrity gates. This is a safety constraint, not elective promotion,
and does not permit retention of any other unpromoted role. A reviewer-effort
experiment never retires `risk_reviewer`: a failed candidate effort returns the
role to its last accepted fixed effort and leaves the named gate installed.

Retire an installed role with no promoted class. Failure demotes only the
affected class; unsupported work remains primary.

## Promoted registry

- `evidence_tester`: material multi-file or large-output test triage, or material
  multi-file or large-log runbook-driven analysis, with explicit acceptance
  fields and one requested artifact.
- `boundary_mapper`: one named unresolved cross-component boundary after a
  targeted primary check.
- Fresh `risk_reviewer`: required independent high-risk final-state gate. It is
  installed as the mandatory named governance control, not as an elective
  cost-promoted class. `risk_reviewer_max` is only its fixed-effort escalation
  variant and never owns an independent promoted class.
- Built-in `explorer`, `worker`, and `default`: baseline leaf or capability-gated
  bounded-peer routes; they are not promoted custom classes.
- Primary: every unsupported or capability-unverified class.

## Evidence and provenance

Record scenario, arm order, model, effort, service tier, token categories,
credits, wall time, child count, retries, quality checks, scope violations,
routing decision, fixture family, holdout seal, grader hash, contamination audit,
and configuration hashes. Report each instance before class aggregates so one
fixture cannot hide another. Preserve original runs, sidecars, canonical
receipts, and old role names byte-for-byte. Record renames and retirements in a
separate migration manifest. Keep verified-local, CI, target, pilot, and
production evidence distinct.

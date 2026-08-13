# Routing Policy

Read this reference whenever delegation is being considered. Agent TOMLs own
the two promoted custom roles and the mandatory independent gate role.

## Eligibility

| Task class | Route | Required boundary |
|---|---|---|
| Material structured test-output triage | `evidence_tester` | Exhaustive multi-file or large-output scan, requested evidence artifact, and explicit acceptance fields |
| Material bounded log corpus | `evidence_tester` | Exhaustive multi-file or large-log scan, explicit runbook, acceptance fields, and requested evidence artifact |
| Named unresolved cross-component boundary | `boundary_mapper` | A targeted primary check still leaves one named execution/state boundary unresolved |
| Required independent high-risk final gate | fresh `risk_reviewer` | Named final-state or acceptance invariants; mandatory named governance gate |
| Any other, ambiguous, simple, resolved, mechanical, or open-ended class | Primary/default | No promoted custom route |

An artifact request alone never qualifies a task. The child must replace material
raw work or supply required independence, and the primary must not reconstruct
the transferred work.

Acceptance fields define the evidence schema, not expected conclusions. Route by
the unresolved work boundary and required independence; never route because a
prompt contains words copied from a role description, checklist, or benchmark.

A short single log, a small direct diagnosis, or a narrow test failure remains
primary/default even when an artifact is requested.

## Concurrency and escalation

1. Start every already-qualified child whose bounded work is mutually independent,
   required, and ownership-safe. Allow up to three active custom children by
   default; a fourth requires explicit user authorization. Capacity alone never
   justifies delegation.
2. Keep the primary on independent work while children run. Never serialize an
   already-qualified independent child solely because another child is slow.
3. Add a newly discovered child only for new failure evidence, a newly unresolved
   boundary, or a required final-state gate. Shared writes remain serial.
4. Use a fresh `risk_reviewer` for independence. This installed named role is a
   mandatory governance control because no callable built-in equivalent exists.
   Its fixed default effort is `xhigh`, independent of the primary/default effort.

### Reviewer effort escalation

- Accept an `xhigh` PASS without a confidence-seeking rerun.
- For a concrete defect, repair it and use a fresh `xhigh` recheck. For missing
  evidence, obtain the evidence or keep the gate blocked; neither case qualifies
  for `max`.
- Start one fresh `risk_reviewer_max` only when the available evidence is sufficient,
  the `xhigh` result is explicitly indeterminate because competing causal
  explanations or cross-boundary reasoning remain, and that ambiguity can change
  an irreversible P0/P1, security, authorization, or data-integrity decision.
  This is the fixed-`max` runtime variant of the same governance role, not a new
  task class; never substitute `default` or another role for it.
- Record the trigger and allow at most one `max` escalation. Complexity, file
  count, a high-risk label, an ordinary BLOCK, or a desire for more confidence
  never qualifies.

Serialize shared writes, migrations, dependent changes, and final integration.
Review/report/diagnosis artifacts are evidence rather than product mutations.

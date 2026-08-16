# Routing Policy

Read this reference whenever delegation is being considered. Agent TOMLs own
the governed custom leaf roles. Built-in agents own generic leaf work and the
capability-gated bounded-peer lane.

## Eligibility

| Task class | Route | Required boundary |
|---|---|---|
| Material structured test-output triage | `evidence_tester` | Exhaustive multi-file or large-output scan, requested evidence artifact, and explicit acceptance fields |
| Material bounded log corpus | `evidence_tester` | Exhaustive multi-file or large-log scan, explicit runbook, acceptance fields, and requested evidence artifact |
| Named unresolved cross-component boundary | `boundary_mapper` | A targeted primary check still leaves one named execution/state boundary unresolved |
| Required independent high-risk final gate | fresh `risk_reviewer` | Named final-state or acceptance invariants; mandatory named governance gate |
| Material narrow read-only codebase question | built-in `explorer` leaf | Its focused scan replaces material primary exploration |
| Scoped implementation or fix | built-in `worker` leaf | Strategy is settled and owned paths do not overlap another writer |
| Material dependency graph needing direct evidence handoff | built-in `default` bounded peer | Explicit collaboration request or material primary relay avoided; current client capability receipt |
| Any other, ambiguous, simple, resolved, mechanical, or open-ended class | Primary | No qualified delegated route |

An artifact request alone never qualifies a task. The child must replace material
raw work or supply required independence, and the primary must not reconstruct
the transferred work.

Acceptance fields define the evidence schema, not expected conclusions. Route by
the unresolved work boundary and required independence; never route because a
prompt contains words copied from a role description, checklist, or benchmark.

A short single log, a small direct diagnosis, or a narrow test failure remains
primary even when an artifact is requested.

## Topology

- Governed custom roles are parent-routed leaves: depth zero, no peer messages,
  no descendants. Their prompts and eligibility remain unchanged.
- Built-in `explorer` and `worker` are leaves by default. Use built-in `default`
  as a bounded peer only when direct evidence or dependency handoff replaces
  material primary relay. It may delegate one additional level to at most two
  registered leaf descendants.
- Peer messages may carry only task-local evidence, dependency status, or an
  owned-artifact receipt. They cannot change authorization, scope, acceptance,
  writer ownership, or topology. Material decisions return to the primary.
- If the current client cannot prove nested spawn, direct messaging, permission
  inheritance, and full-tree terminal collection, fail closed to built-in leaves
  or primary. Capability presence alone is not a quality claim.

## Concurrency and escalation

1. Start every already-qualified child whose bounded work is mutually independent,
   required, and ownership-safe. Allow up to three active direct children by
   default; a fourth requires explicit user authorization. Allow at most one
   bounded-peer coordinator with two leaf descendants. Capacity alone never
   justifies delegation.
2. Keep the primary on independent work while children run. Never serialize an
   already-qualified independent child solely because another child is slow.
3. Add a newly discovered child only for new failure evidence, a newly unresolved
   boundary, a pre-authorized dependency, or a required final-state gate. Shared
   writes, migrations, dependent mutations, and final integration remain serial.
4. Use a fresh `risk_reviewer` for independence. This installed named role is a
   mandatory governance control because no callable built-in equivalent exists.
   Its fixed default effort is `xhigh`, independent of primary or built-in default effort.

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

Review/report/diagnosis artifacts are evidence rather than product mutations.

# Routing Policy

Use the smallest route that can finish the acceptance anchor. Keep every child a
leaf and the primary as the only coordinator and decision owner.

Set an explicit non-`default` `agent_type` on every spawn. Never route to the
built-in `default`; keep unmatched work in the primary.

## Admit a role

| Need                                                        | Route                 | Admit only when                                                                    |
| ----------------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------- |
| One narrow read-only codebase question                      | built-in `explorer`   | Its focused scan replaces material primary exploration                             |
| One settled implementation slice                            | built-in `worker`     | Strategy, exact ownership, and acceptance are already known                        |
| Structured test or bounded log evidence                     | `evidence_tester`     | One noisy surface can be isolated behind exact acceptance fields and one artifact  |
| One unresolved execution, state, or persistence boundary    | `boundary_mapper`     | A targeted primary check was insufficient and no design verdict is requested       |
| One independent high-risk invariant                         | fresh `risk_reviewer` | Writers are terminal, the candidate is frozen, and the invariant is exact          |
| One evidence-qualified irreversible ambiguity               | `risk_reviewer_max`   | A valid reviewer escalation names competing explanations and the affected decision |
| Simple, strategic, ambiguous, ordered, or shared-state work | primary               | Delegation would add coordination or split reasoning prematurely                   |
| General-purpose or unmatched fallback                       | primary, no spawn     | Never invoke built-in `default`; choose a specialized role or work directly        |

Do not substitute roles. An `evidence_tester` collects evidence without source
edits or unsupported diagnosis. A `boundary_mapper` traces one boundary without
deciding the defect or design. A reviewer seeks falsifying evidence only inside
named invariants; it does not explore broadly, implement, invent requirements,
or own the repair.

## Follow valid transitions

- Return `explorer` and `boundary_mapper` evidence to the primary. Let only the
  primary settle strategy before assigning a `worker`.
- Use `evidence_tester` before or after implementation only when raw test or log
  volume would pollute the primary context. Keep ordinary targeted checks in the
  primary.
- Require a `worker` terminal receipt, primary sampling, integration, and direct
  checks before review. Never review a moving candidate.
- Return a review BLOCK to the primary for independent adjudication. Do not
  transfer design ownership to the reviewer or authorize a worker automatically.
- Route to `risk_reviewer_max` only from a valid indeterminate reviewer result.
  Never route PASS, BLOCK, missing evidence, or ordinary uncertainty to it.

## Bound topology and expansion

- When delegation is admitted, start one child. Add a second ordinary first-wave
  child only for bounded, independent, ownership-safe work with an expected
  wall-time or context benefit. Keep the ordinary cap at two children and one
  active writer with no overlapping write scope.
- Prohibit child delegation and peer messaging. An expansion checkpoint never
  relaxes leaf topology, ownership, write-scope, or freshness rules.
- Permit at most one primary update to an operational leaf inside its original
  scope. Keep review roles isolated from messages and follow-ups so any changed
  evidence is reviewed only after refreezing by a fresh reviewer.
- Open an expansion checkpoint for a later wave, another writer, scope
  expansion, or a reviewer rerun. First collect and integrate current required
  receipts. Let the primary clear one bounded next child only when new evidence,
  unchanged material scope and risk, and displaced work justify it; otherwise
  continue directly.
- Ask when the user requested a checkpoint or at a material user-owned boundary.
  Expansion alone is not a question. If the choice changes outcome, acceptance,
  external behavior, compatibility, security, privacy, architecture, meaningful
  cost, migration, or an irreversible effect, ask early with one recommended
  default. Report operational blockers instead of offering them as choices.
- Set `fork_turns` to `"none"`; never inherit full history. Use English receipts
  and keep the primary model and effort user-controlled. Use fixed installed
  child settings: Sol/high for built-ins and `boundary_mapper`, Luna/max for
  `evidence_tester`, Sol/xhigh for `risk_reviewer`, and Sol/max for
  `risk_reviewer_max`.

## Route review

- When independent review is admitted, use one fresh `risk_reviewer`. Use
  multi-review only for an explicit user request: one final batch of at most
  three fresh reviewers, disjoint invariants, one frozen candidate, no voting,
  and no design workshop.
- After a repair and fresh recheck still BLOCK, return to primary
  first-principles adjudication. Reject an unsupported finding, repair directly,
  or identify a genuine blocker. Require a changed candidate or new
  discriminating evidence before opening an expansion checkpoint for another
  independent review.
- Treat unchanged uncertainty after two decision-directed attempts as an
  evidence plateau. Stop variants and obtain the smallest observation that
  distinguishes the remaining hypotheses. Never add a child merely to seek
  confidence.

## Close the task

Treat child terminal state, a gate line, or exhausted budget as closure of
transferred work only. Close against the original outcome with proportionate
claim-matched evidence. Do not build supporting machinery before the smallest
real task proves the core behavior.

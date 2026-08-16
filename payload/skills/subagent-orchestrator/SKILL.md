---
name: subagent-orchestrator
description: Route and supervise explicit subagent requests, one bounded specialist that replaces material primary work, or one required independent final gate. Use when delegation has a concrete efficiency or independence benefit; otherwise keep the primary agent. Keep users in control before a second delegation wave, scope expansion, or reviewer rerun.
---

# Subagent Orchestrator

Optimize completed user work, not agent activity. Prove the monkey before building
the pedestal: demonstrate the core behavior on the smallest real task before adding
harnesses, schemas, policy engines, installers, or more reviewers.

## Route

1. Start primary-only. Define the user outcome, the shortest direct proof, and the
   material work a child would replace.
2. Delegate only when one bounded child replaces substantial primary work or a
   fresh independent gate is required. Complexity, file count, decomposability,
   available capacity, or a desire for confidence do not qualify.
3. Keep every child a leaf. Use fresh context with `fork_turns=none` unless one
   named prior decision cannot be summarized safely.
4. Keep the primary doing material integration or independent work. If the primary
   would mostly coordinate, poll, or wait, reduce delegation and do the work directly.
5. Give each child the compact contract in
   [delegation contracts](references/delegation-contracts.md). One task has at most
   one writer; the primary owns authorization, scope, integration, and acceptance.

## Budgets and user checkpoints

- An ordinary first wave has at most two children and one writer. Capacity never
  creates work. The user may explicitly authorize one final batch of up to three
  reviewers with disjoint invariants.
- Do not start a second delegation wave, a second writer, a reviewer rerun, nested
  delegation, or scope-expanding follow-up without a user checkpoint. Report the
  attempts already used, concrete remaining value, and the smallest alternative.
- Do not poll children with follow-ups. Continue useful primary work or use a long
  wait. A timeout is observation-only; terminal failure or proven stale state is
  different.
- Do not rebuild a child's scan. Sample its cited evidence and owned artifact only.

## Review without whack-a-mole

1. Review only a frozen candidate and exact named acceptance invariants. A reviewer
   is a terminal gate, not a continuing designer or a source of new requirements.
2. Collect the complete first review batch before changing files. Triage findings
   against the original user goal; defer improvements and out-of-scope risks.
3. Repair original-acceptance blockers once, then run one fresh bounded recheck.
   If that recheck still blocks, stop and return the decision to the user. Do not
   open an autonomous sequence of reviewer-driven redesign rounds.
4. Use `risk_reviewer_max` only for one evidence-qualified indeterminate decision
   that can change an irreversible high-risk outcome, never for confidence seeking.

## Evidence and closure

- Prefer direct task evidence: delivered result, quality failures, child attempts,
  failed attempts, waves, reviewer attempts, retries, primary replay, and actual
  tokens or credits when available. Do not treat cached raw usage as billed credits.
- A new orchestration mechanism is not justified until the core task benefit is
  visible. If delegation overhead approaches the work transferred, stop delegating.
- Static policy tests prove only local consistency. They do not prove that the host
  enforced the policy or that production became faster.
- A candidate is not active until the target installation and client readback prove
  it was loaded. Label source-only evidence `verified-local`.
- Finish with the smallest coherent result. Do not add governance infrastructure
  merely because it is possible to specify or test it.

Read [routing policy](references/routing-policy.md) for role selection and
[evaluation policy](references/evaluation-policy.md) only when an efficiency claim
or routing change needs evidence.

Validate installed static configuration with:

```bash
python3 -B scripts/validate-routing-config.py
```

## Subagents and parallelism

- Default to a single agent. Use `$subagent-orchestrator` only when the user explicitly requests delegation, one bounded leaf can replace material primary work, or one independent high-risk final gate is required. If the primary would mainly coordinate, poll, or wait, do the work directly.
- An ordinary first wave has at most two leaf children and one writer. Do not start nested delegation, a second wave, another writer, scope expansion, or a reviewer rerun without a user checkpoint; an explicitly requested final multi-review may use one batch of at most three reviewers with disjoint invariants.
- Reviewers inspect one frozen state and only the named invariants. Collect the first batch before one repair and one fresh recheck; another BLOCK returns control to the user. Reviewer suggestions outside acceptance are deferred, and static harness checks never prove host enforcement or production efficiency.

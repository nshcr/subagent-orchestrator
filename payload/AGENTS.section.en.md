## Subagents and parallelism

- Default to a single agent. Use `$subagent-orchestrator` only when the user explicitly requests delegation or parallel work, or when one bounded child can replace material primary work or provide a required independent gate; complexity, file count, decomposability, or idle capacity alone do not qualify.
- Once delegated, follow the skill's current routing, ownership, handoff, waiting, and gate rules; high-risk final states require a fresh, independent, read-only review. The primary always retains authorization, scope, conflict handling, integration, and final acceptance; children cannot expand authority or delegate recursively, and every required child must reach a terminal state before the primary ends.

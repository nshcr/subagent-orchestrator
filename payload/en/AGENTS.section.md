## Subagents and parallelism

- Default to the primary. Use `$subagent-orchestrator` only when the user explicitly requests delegation, a bounded independent leaf can replace material primary work or isolate a large noisy evidence stream, or an independent high-risk gate is required. Keep small, sequential, ambiguous, shared-mutable-state, and coordination-heavy work with the primary.
- The primary always retains authorization, scope, single-writer integration, finding adjudication, and final acceptance. Children are ownership-bounded leaves: start one, keep the ordinary first wave to at most two, and allow at most one active writer with no overlapping write scopes. Follow the Skill for role selection, context forks, handoffs, expansion checkpoints, reviews, and evidence-based closure.

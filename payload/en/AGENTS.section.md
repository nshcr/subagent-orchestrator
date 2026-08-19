## Subagents and parallelism

- Default to a single agent. Use `$subagent-orchestrator` only under the Skill's
  delegation criteria. Prefer direct or batched tools for small work; if the
  primary would mainly coordinate, poll, or wait, keep the work with the
  primary.
- The primary retains authorization, scope, integration, finding adjudication,
  and final acceptance. Children remain leaves; when delegation is admitted,
  start one child. Add a second ordinary first-wave child only for bounded,
  independent, ownership-safe work expected to reduce wall time or root-context
  noise; cap ordinary work at two children and at most one active writer with no
  overlapping write scopes, and use installed model and effort settings. Follow the
  Skill for role admission, immutable leaf boundaries, expansion checkpoints,
  review convergence, and evidence-based closure.

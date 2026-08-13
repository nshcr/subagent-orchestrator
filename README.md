# Subagent Orchestrator

A quality-first subagent orchestration bundle for OpenAI Codex. It installs four
bounded custom roles, a routing skill, and a portable client-neutral profile.
Delegation is used only when it replaces material primary work or supplies a
required independent gate.

> [!IMPORTANT]
> This is an unofficial community project and is not affiliated with or endorsed
> by OpenAI. Model, reasoning-effort, and service-tier values are client-specific.
> Verify availability for your Codex version and account before installation.

## Included roles

| Role | Purpose | Access |
|---|---|---|
| `evidence_tester` | Structured test-output or bounded runbook-driven log analysis with one requested evidence artifact | Workspace write, limited by its task contract |
| `boundary_mapper` | One unresolved cross-component execution, state, or persistence boundary | Read-only |
| `risk_reviewer` | Fresh independent gate for named high-risk final-state invariants | Read-only |
| `risk_reviewer_max` | One evidence-qualified escalation when `xhigh` remains genuinely indeterminate | Read-only |

The default remains a single agent. Complexity, file count, and spare concurrency
do not qualify a task for delegation.

## Requirements

- Python 3.11 or newer; no third-party Python dependencies.
- A Codex client that supports custom subagents, skills, and `[agents]` settings.
- A trusted local Codex home that will not be modified concurrently during install.

See the current official documentation for [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[skills](https://learn.chatgpt.com/docs/build-skills), and the
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Install

```bash
git clone https://github.com/nshcr/subagent-orchestrator.git
cd subagent-orchestrator
python3 -B validate.py
```

Run the read-only preflight first, then apply the same plan. Replace the example
with the absolute path to your Codex home.

```bash
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --check
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --apply
```

`--check` does not create the target directory or write files. It reports every
planned path and content SHA-256. `--apply` uses the same fail-closed checks.
Choose `--agents-language en` for English or `--agents-language zh` for Simplified
Chinese. The installer writes exactly one policy section and can safely switch a
managed installation between the two canonical translations.

The installer manages only:

- the `## Subagents and parallelism` section in `AGENTS.md`;
- five package-owned `[agents]` keys in `config.toml`;
- four role files under `agents/`;
- declared files and managed state under `skills/subagent-orchestrator/`.

Other personal instructions, primary-agent settings, project settings, unknown
`[agents]` keys, extra agents, and extra skills are preserved. Unknown conflicts
are rejected. Known predecessor bundles can be upgraded only when their recorded
managed hashes still match the target files.

Writes use an all-target precondition gate, same-directory temporary files,
`fsync`, atomic replacement, and a final per-file recheck. Atomicity is per file,
not a multi-file transaction. A late concurrent change stops later replacements
but does not roll back files already replaced.

The installer creates no backup, deletes no extra files, and provides no automatic
uninstaller. Review `skills/subagent-orchestrator/.managed-package-state.json`,
`AGENTS.md`, and `config.toml` before removing an installation manually.

## Validate

```bash
python3 -B validate.py
```

This checks manifest integrity, portability, package tests, an empty-home install,
idempotency, the installed routing contract, and bundled skill tests. Run package
tests alone with:

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

After installation, validate a target from the installed skill directory:

```bash
python3 -B scripts/validate-routing-config.py --codex-home /absolute/path/to/.codex
```

A local PASS proves only the file contract and hermetic tests. It does not prove
model availability, account access, client reload state, or current role quality.

After changing any published file, rebuild the deterministic manifest:

```bash
python3 -B build_manifest.py
python3 -B validate.py
```

## Historical benchmark snapshot

The bundle originated from an August 2026 paired benchmark. Twelve baseline/custom
pairs covered four materially different fixture families for each of three roles.
The score threshold was 85. Runs alternated arm order, accounted for primary and
child tokens and ChatGPT credits, included benign and blocking cases, and ended
with a sealed holdout. Labels alone earned no score without counts, source paths,
causal evidence, or counterexamples.

### Aggregate results

| Metric | Baseline | Custom | Difference |
|---|---:|---:|---:|
| Passed cases | 11/12 | 12/12 | +1 custom |
| Mean quality score | 94.5000 | 95.5833 | +1.0833 |
| ChatGPT credits | 198.538650 | 194.003379 | -4.535271 (-2.28%) |
| Tokens | 4,010,378 | 5,854,137 | +1,843,759 (+45.98%) |
| Wall time | 2,207.4 s | 3,864.2 s | +75.1% |

Wall time was telemetry only and was not a routing objective. Custom used more
tokens, while its lower-priced child-model mix reduced total credits slightly.

### Results by role

| Role | Baseline scores | Custom scores | Passes B/C | Median credits B/C | Historical decision |
|---|---|---|---:|---:|---|
| `evidence_tester` | `[100, 100, 74, 100]` | `[100, 100, 87, 100]` | 3/4 → 4/4 | 11.047 / 15.239 | Retained for verified quality gain |
| `boundary_mapper` | `[90, 100, 100, 100]` | `[90, 100, 100, 100]` | 4/4 → 4/4 | 25.750 / 18.646 | Retained at equal quality and 27.6% lower median credits |
| `risk_reviewer` | `[90, 90, 90, 100]` | `[90, 90, 90, 100]` | 4/4 → 4/4 | 15.075 / 13.780 | Retained as a mandatory independent gate; 8.6% savings missed the 10% elective threshold |

The eight elective-role pairs (`evidence_tester` and `boundary_mapper`) improved
passes from 7/8 to 8/8 and mean quality from 95.500 to 97.125. Credits decreased
from 141.409025 to 136.700229 (-3.33%), while tokens increased 67.64%.

### Sealed holdout

| Scenario | Baseline | Custom | Credits B/C | Wall time B/C |
|---|---:|---:|---:|---:|
| Build-fleet evidence audit | 100 | 100 | 9.680 / 15.722 | 139.9 / 405.3 s |
| Refund/capture boundary | 100 | 100 | 26.946 / 20.502 | 306.2 / 430.2 s |
| Password-reset replay gate | 100 BLOCK | 100 BLOCK | 14.445 / 17.689 | 271.4 / 236.1 s |

The three role families tested production-log accounting, mixed test triage,
benign negative evidence, durable-state races, cache and authorization propagation,
default-deny authorization, effect-before-authentication, stale leases, and replay
windows. The sealed run completed 6/6 valid terminal arms with correct role use,
no recursive delegation, and a clean contamination audit.

These are historical, verified-local results, not a current performance claim.
The raw benchmark corpus is not shipped in this repository. The current package
also fixes `risk_reviewer` at `xhigh` and adds the separate one-shot `max` variant;
the historical reviewer runs used an earlier High configuration, so they do not
validate the newer effort policy. Re-benchmark representative workloads before
changing role eligibility, model routing, or promotion status.

## Package layout

```text
.
├── install.py
├── validate.py
├── build_manifest.py
├── manifest.json
├── portable-profile.json
├── payload/
│   ├── AGENTS.section.en.md
│   ├── AGENTS.section.zh.md
│   ├── config.agents.toml
│   ├── agents/
│   └── skills/subagent-orchestrator/
└── tests/
```

Licensed under the [MIT License](LICENSE).

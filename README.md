# Subagent Orchestrator

A quality-first subagent orchestration bundle for OpenAI Codex. It installs four
bounded custom roles, a routing skill, and a portable client-neutral profile.
Delegation is used only when it replaces material primary work or supplies a
required independent gate. Built-in agents provide generic leaf work; children do
not coordinate other children.

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

## Delegation budget

- `explorer` and `worker` are built-in leaf routes for material read-only scans
  and scoped, ownership-safe implementation.
- Every child is a leaf. The primary retains authorization, writer ownership,
  integration, and final acceptance.
- An ordinary first wave has at most two children and one writer. A second wave,
  another writer, scope expansion, or reviewer rerun opens an expansion checkpoint:
  no new child starts without exact current user authorization. Otherwise the primary
  continues or closes, asking one question only for a material user-owned choice.
  Before a later wave, all current required children must be terminal and integrated;
  at most one writer may be active and write scopes never overlap.
- Reviewers inspect one frozen state and named invariants. After one repair and one
  fresh recheck, another BLOCK stops further review. Operational blockers are reported,
  out-of-scope ideas are deferred, and only a named material acceptance choice is
  returned to the user. Freeze follows writer terminal state and integration, and any
  relevant state change invalidates the previous review result.
- If the primary would mainly coordinate, poll, or wait, it should do the work
  directly. Prove the user-facing behavior before building supporting machinery.
- Child terminal state and exhausted delegation budget do not prove task completion;
  the primary still closes against the original user outcome and proportionate task
  evidence or a genuine blocker. Passing an install, load, child, test, or review
  sub-boundary cannot substitute for task acceptance.

## Requirements

- Python 3.11 or newer; no third-party Python dependencies.
- macOS or Linux. Windows is unsupported and unverified because the installer
  relies on Unix `fsync`, file-mode, hard-link, and atomic no-replace rename
  semantics (`renamex_np` on macOS or `renameat2` on Linux).
- A Codex client that supports custom subagents, skills, and `[agents]` settings.
- A trusted local Codex home.

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
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --doctor
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --doctor --format json
```

`--check` does not create the target directory or write files. It reports every
planned path and content SHA-256. `--apply` uses the same fail-closed checks.
`--doctor` is read-only and classifies the current installation, active apply
lock, unfinished transaction, and any quarantined retired artifacts. Add
`--format json` for a stable machine-readable diagnostic receipt.
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
are rejected. Managed state version 2 records an install-contract hash derived
only from managed inputs for diagnosis, but completed-state upgrades do not require
a historical contract allowlist. Instead, package identity, the exact managed-key
domain, every recorded target hash, and retired-path authorization must all match.
Unfinished transactions remain bound to the exact contract that created them.

`install-migrations.json` is the explicit lifecycle catalog. A removed managed
path is accepted only when both its original path and old SHA-256 are declared.
The installer creates the quarantine path with an exclusive hard link and
`fsync`s it. It then atomically moves the source name without replacement into
transaction-owned staging, verifies the staged inode and hash against the
quarantine link, and retains that verified hard link under
`.retirement-receipts/` as a durable, non-deleting transaction receipt. Journal
completion removes only the journal itself.
Quarantined bytes remain at
`skills/subagent-orchestrator/.retired/<sha256>/<original-path>`; unknown,
modified, colliding, or concurrently replaced content fails closed and is
restored or left at a journal-owned recovery path.

Apply uses an exclusive target-scoped lock, an all-target precondition gate,
same-directory temporary files, `fsync`, atomic replacement, and a durable
transaction journal. Atomicity is per file, not across the complete plan. If a
late change or interruption stops an apply, already completed `TOUCHED` receipts
are flushed and the journal remains for read-only diagnosis and idempotent
forward recovery with the same package and language. Conflicting partial state
fails closed; the installer never silently rolls it back or overwrites it.
A crash can leave either the source and quarantine links or the quarantine and
staging links. `--doctor` reports both recoverable states, and the next matching
apply finishes the journal forward without replacing any existing path. A
verified staging link remains afterward as a read-only retirement receipt.

The installer provides no automatic uninstaller. Review `--doctor`,
`skills/subagent-orchestrator/.managed-package-state.json`, any
`.install-transaction.json`, `.retired/`, or `.retirement-receipts/` evidence,
plus `AGENTS.md` and `config.toml`, before removing an installation manually. A
stale apply lock also requires manual inspection; there is intentionally no
force-unlock flag.

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

CI runs this validation matrix on Ubuntu and macOS with Python 3.11 and 3.14.
That matrix does not establish Windows compatibility.

After installation, validate a target from the installed skill directory:

```bash
python3 -B scripts/validate-routing-config.py --codex-home /absolute/path/to/.codex
```

A local PASS proves only the file contract, hermetic tests, and static routing
consistency. It does not prove model availability, account access, client reload
state, host enforcement, production efficiency, or current role quality.

After changing any published file, rebuild the deterministic manifest:

```bash
python3 -B build_manifest.py --package-version 2026.08.14
python3 -B build_manifest.py --check
python3 -B validate.py
```

`--check` validates the manifest schema, rejects duplicate or unsafe paths, and
fails without rewriting when hashes, sizes, coverage, metadata, or ordering are
stale. Manifest writes require an explicit `YYYY.MM.DD` package version. Before
retiring a managed role or skill path, generate a conservative review artifact
from the predecessor manifest:

```bash
python3 -B build_manifest.py \
  --migration-candidate-from /path/to/predecessor-manifest.json
```

The command never edits `install-migrations.json`. Rendered role templates are
flagged as requiring an installed-byte hash; every candidate requires human
review before being accepted into the lifecycle catalog.

## Evaluation scaffold

The standard-library-only `evaluation` package validates paired baseline/custom
campaign evidence and emits deterministic JSON reports. It never invokes models,
graders, or the network. Development evidence and externally executed sealed
holdout evidence are separate inputs. It is optional and should not be expanded or
rerun for routine orchestration changes unless the user requests a benchmark:

```bash
python3 -B -m evaluation validate --campaign campaign.json \
  --sealed-holdout /outside/repository/sealed-results.json
python3 -B -m evaluation report --campaign campaign.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --output report.json
python3 -B -m evaluation smoke
```

Each billed primary, child, review, repair, failed-attempt, or retry task records
its actual model, effort, service tier, tokens, and credits. Reports use exact
decimal arithmetic, require stable acceptance and contamination evidence, and
keep wall time as telemetry only. Promotion remains conservative unless each
task class covers three fixture families, both arm orders, a sealed holdout, and
the quality-first/Pareto gate. See [`evaluation/README.md`](evaluation/README.md)
for the evidence boundary and schemas.

## Package layout

```text
.
├── install.py
├── validate.py
├── build_manifest.py
├── install-migrations.json
├── manifest.json
├── portable-profile.json
├── evaluation/
├── payload/
│   ├── AGENTS.section.en.md
│   ├── AGENTS.section.zh.md
│   ├── config.agents.toml
│   ├── agents/
│   └── skills/subagent-orchestrator/
└── tests/
```

Licensed under the [MIT License](LICENSE).

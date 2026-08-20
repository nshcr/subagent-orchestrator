# Subagent Orchestrator

A quality-first subagent orchestration bundle for OpenAI Codex. It installs four
bounded custom roles, a routing skill, and a portable client-neutral profile.
Delegation is used only when it replaces material primary work, isolates a
substantial noisy evidence stream behind a compact receipt, or supplies a
required independent gate. Built-in agents provide generic leaf work; children
do not coordinate other children.

> [!IMPORTANT]
> This is an unofficial community project and is not affiliated with or endorsed
> by OpenAI. Model, reasoning-effort, and service-tier values are
> client-specific. Verify availability for your Codex version and account before
> installation.

## Included roles

| Role                | Purpose                                                                        | Requested sandbox / action bound        |
| ------------------- | ------------------------------------------------------------------------------ | --------------------------------------- |
| `evidence_tester`   | Structured test or bounded runbook/log evidence with one requested artifact    | Workspace write / one evidence artifact |
| `boundary_mapper`   | One unresolved cross-component execution, state, or persistence boundary       | Read-only / no writes                   |
| `risk_reviewer`     | Fresh independent gate for named high-risk final-state invariants              | Read-only / no writes                   |
| `risk_reviewer_max` | One evidence-qualified escalation when `xhigh` remains genuinely indeterminate | Read-only / no writes                   |

The default remains a single agent. Complexity, file count, and spare
concurrency do not qualify a task for delegation.

## Delegation budget

- `explorer` and `worker` are built-in leaf routes for material read-only scans
  and scoped, ownership-safe implementation.
- Every new delegation selects an explicit role in the orchestration call. The
  package never deliberately routes unmatched work to built-in `default`, but an
  already returned result is assessed by scope, evidence, freshness, and role
  boundaries rather than discarded solely for missing or `default` role metadata.
  A denied optional action does not end the leaf: it continues safe in-scope work
  and reports the block. A required denied action produces one terminal
  `approval-blocked` receipt. Later children cannot receive the same permission
  class and owner-scope boundary unless host evidence proves that a reusable
  grant applies to them.
- Every child is a leaf. The primary retains authorization, writer ownership,
  integration, and final acceptance.
- When delegation is admitted, start one child. A second child in the ordinary
  first wave requires two bounded, mutually independent, ownership-safe
  assignments expected to reduce wall time or root-context pollution; the
  absolute cap remains two children and one writer. A later wave, another
  writer, scope expansion, or reviewer rerun opens an expansion checkpoint.
  After current receipts are terminal and integrated, the primary may clear one
  bounded next child when evidence justifies it and material scope and risk are
  unchanged. A checkpoint never relaxes leaf topology, ownership, write-scope,
  or freshness rules. Expansion itself is not a user question; ask when the user
  requested a checkpoint or at a material user-owned boundary.
- Reviewers inspect a frozen state and named high-risk invariants. The
  primary—not the reviewer—adjudicates findings and owns the repair. After one
  repair and fresh recheck, a remaining BLOCK triggers a first-principles reset;
  another review requires a changed candidate or new discriminating evidence.
  Explicit multi-review remains an exceptional single batch with disjoint
  invariants, never a voting or design workshop.
- If the primary would mainly coordinate, poll, or wait, it should do the work
  directly. Prefer direct or batched tool calls for small bounded work, and keep
  one ordered reasoning chain, shared mutable state, or one slow external
  operation with the primary. Prove the user-facing behavior before building
  supporting machinery.
- Child terminal state and exhausted delegation budget do not prove task
  completion; the primary still closes against the original user outcome and
  proportionate task evidence or a genuine blocker. Passing an install, load,
  child, test, or review sub-boundary cannot substitute for task acceptance.

## Requirements

- Python 3.11 or newer; no third-party Python dependencies.
- macOS or Linux. Windows is unsupported and unverified because the installer
  relies on Unix `fsync`, file-mode, hard-link, and atomic no-replace rename
  semantics (`renamex_np` on macOS or `renameat2` on Linux).
- A Codex client that supports custom subagents, skills, and `[agents]`
  settings.
- A trusted local Codex home.

The installed runtime cap is four concurrent spawned threads, excluding the
primary as defined by Codex. This leaves one host-level spare slot when three
children are open without making capacity a routing signal; the Skill still
admits at most two ordinary first-wave children and one active writer. Routine
built-in leaves default to GPT-5.6 Terra at max effort; the bounded tester uses
Luna/max, the boundary mapper Terra/max, the reviewer Sol/xhigh, and only the
qualified irreversible-risk escalation uses Sol/max. The four custom-role values
are fixed by their installed agent files; built-in children use the Terra/max
package model defaults. Spawned-agent routing does not override these values per
task, so Sol/high and Sol/medium are not active package routes. The primary
remains user-controlled. A role file's sandbox is a requested default, not proof
of effective isolation: parent runtime permission overrides may take precedence.
Match the parent permission mode to the role and retain its action bounds.
Effective behavior still requires client readback.

See the current official documentation for
[Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
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
python3 -B install.py --codex-home /absolute/path/to/.codex --check
python3 -B install.py --codex-home /absolute/path/to/.codex --apply
python3 -B install.py --codex-home /absolute/path/to/.codex --doctor
python3 -B install.py --codex-home /absolute/path/to/.codex --doctor --format json
```

`--check` does not create the target directory or write files. It reports every
planned path and content SHA-256. `--apply` uses the same fail-closed checks.
`--doctor` is read-only and classifies the current installation, active apply
lock, unfinished transaction, and any quarantined retired artifacts. Add
`--format json` for a stable machine-readable diagnostic receipt. The installer
writes the English model-facing payload by default. Pass
`--agents-language zh` to install the complete Chinese translation of the
policy section, role instructions, routing skill, references, and skill
metadata. Executable validators and tests remain shared invariant code.
Protocol identifiers, schemas, literals, terminal gate lines, and child
handoffs/receipts remain English; the primary remains responsible for
user-facing language.

The installer manages only:

- the `## Subagents and parallelism` section in `AGENTS.md`;
- five package-owned `[agents]` keys in `config.toml`;
- four role files under `agents/`;
- declared files and managed state under `skills/subagent-orchestrator/`.

Other personal instructions, primary-agent settings, project settings, unknown
`[agents]` keys, extra agents, and extra skills are preserved. Unknown conflicts
are rejected. Existing managed headings or paths without a valid managed state
are treated as user-owned conflicts; no historical byte-hash allowlist can claim
them. Managed state version 2 records an install-contract hash derived only from
managed inputs for diagnosis, while completed-state upgrades require package
identity, the exact managed-key domain, every recorded target hash, and
retired-path authorization to match. Unfinished transactions remain bound to the
exact contract that created them.

`install-migrations.json` is the explicit migration catalog. A removed managed
path is accepted only when both its original path and old SHA-256 are declared.
The installer creates the quarantine path with an exclusive hard link and
`fsync`s it. It then atomically moves the source name without replacement into
transaction-owned staging, verifies the staged inode and hash against the
quarantine link, and retains that verified hard link under
`.retirement-receipts/` as a durable, non-deleting transaction receipt. Journal
completion removes only the journal itself. Quarantined bytes remain at
`skills/subagent-orchestrator/.retired/<sha256>/<original-path>`; unknown,
modified, colliding, or concurrently replaced content fails closed and is
restored or left at a journal-owned recovery path.

Apply uses an exclusive target-scoped lock, an all-target precondition gate,
same-directory temporary files, `fsync`, atomic replacement, and a durable
transaction journal. Atomicity is per file, not across the complete plan. If a
late change or interruption stops an apply, already completed `TOUCHED` receipts
are flushed and the journal remains for read-only diagnosis and idempotent
forward recovery with the same package. Conflicting partial state fails closed;
the installer never silently rolls it back or overwrites it. A crash can leave
either the source and quarantine links or the quarantine and staging links.
`--doctor` reports both recoverable states, and the next matching apply finishes
the journal forward without replacing any existing path. A verified staging link
remains afterward as a read-only retirement receipt.

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

This checks manifest integrity, portability, package tests, an empty-home
install, idempotency, the installed routing contract, and bundled skill tests.
Run package tests alone with:

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
python3 -B build_manifest.py --package-version 2026.08.17.7
python3 -B build_manifest.py --check
python3 -B validate.py
```

`--check` validates the manifest schema, rejects duplicate or unsafe paths, and
fails without rewriting when hashes, sizes, coverage, metadata, or ordering are
stale. Manifest writes require an explicit `YYYY.MM.DD` package version, with an
optional positive `.N` revision for another package built on the same date.
Before retiring a managed role or skill path, generate a conservative review
artifact from the predecessor manifest:

```bash
python3 -B build_manifest.py \
  --migration-candidate-from /path/to/predecessor-manifest.json
```

The command never edits `install-migrations.json`. Rendered role templates are
flagged as requiring an installed-byte hash; every candidate requires human
review before being accepted into the migration catalog.

## Evaluation scaffold

The standard-library-only `evaluation` package validates paired baseline/custom
campaign evidence and emits deterministic JSON reports. It never invokes models,
graders, or the network. Development evidence and externally executed sealed
holdout evidence are separate inputs. It is optional and should not be expanded
or rerun for routine orchestration changes unless the user requests a benchmark:

```bash
python3 -B -m evaluation validate --campaign campaign.json \
  --sealed-holdout /outside/repository/sealed-results.json
python3 -B -m evaluation report --campaign campaign.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --output report.json
python3 -B -m evaluation smoke
```

Each billed primary, child, review, repair, failed-attempt, or retry task
records its actual model, effort, service tier, tokens, and credits. Reports use
exact decimal arithmetic, require stable acceptance and contamination evidence,
and keep wall time as telemetry only. Promotion remains conservative unless each
task class covers three fixture families, both arm orders, a sealed holdout, and
the quality-first/Pareto gate. See
[`evaluation/README.md`](evaluation/README.md) for the evidence boundary and
schemas.

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
│   ├── en/
│   │   ├── AGENTS.section.md
│   │   ├── agents/
│   │   └── skills/subagent-orchestrator/
│   ├── zh/
│   │   ├── AGENTS.section.md
│   │   ├── agents/
│   │   └── skills/subagent-orchestrator/
│   └── shared/
│       ├── config.agents.toml
│       └── skills/subagent-orchestrator/
│           ├── scripts/
│           └── tests/
└── tests/
```

Licensed under the [MIT License](LICENSE).

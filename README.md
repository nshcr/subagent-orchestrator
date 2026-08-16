# Subagent Orchestrator

A quality-first subagent orchestration bundle for OpenAI Codex. It installs four
bounded custom roles, a routing skill, and a portable client-neutral profile.
Delegation is used only when it replaces material primary work or supplies a
required independent gate. Built-in agents also provide generic leaf work and a
capability-gated bounded-peer lane without broadening the custom roles.

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

## Collaboration topology

- `explorer` and `worker` are built-in leaf routes for material read-only scans
  and scoped, ownership-safe implementation.
- A collaboration-capable built-in `default` agent may coordinate at most two
  built-in leaf descendants through one additional delegation level when direct
  evidence handoff avoids material primary relay.
- Peer messages carry evidence, dependency status, or artifact receipts only.
  Custom roles remain parent-routed leaves, and the primary retains authorization,
  writer ownership, integration, and final acceptance.
- If the current client cannot prove nested spawn, direct messaging, permission
  inheritance, and full-tree terminal collection, routing fails closed to leaf
  agents or the primary.

## Evidence-bus delivery slices

Delegation now begins with a digest-bound `slice_open`: one top-level task, one
unique slice, one acceptance milestone, one change class, exact task-wide owner
paths, required gate IDs, and an admitted state summary. Every child receives an
exact-key, strongly typed canonical-snake-case work-transfer receipt whose digest binds
all documented fields plus spawn route/topology/depth, and fresh context; full-history children are never
eligible. Explorer and worker additionally require a non-self-issued materiality
manifest with canonical, deduplicated source ranges and a matching host authority
receipt supplied in a physically separate document outside the trace. Trace SHA-256 values bind payloads but do not
authenticate issuers. Authority binds an explicit host/owner/sealed-harness issuer class;
primary, every pre-indexed child/parent/role participant, and other agent identities
cannot issue or proxy materiality. Tiny leaves, padding, repeated
content, synthetic splitting, and verification-token assets fall back to primary.

Primary source access is accounted across the complete task. A targeted precheck or
sampling receipt must be a strict proper subset no larger than 10%; integration has
zero source ranges/bytes and consumes admitted artifact or changed-path receipts only.
It cannot replay the transferred
scan. Canonical owner components permanently union overlap, rename, split, and merge
aliases. Trace-external cumulative compaction receipts, not terminal self-report,
prove when two writer compactions exhaust new writer work for that task/component.
Each slice permits at most one writer, and sampling uses one frozen task-wide denominator.
Every writer owner path and path artifact remains within `slice_open.owner_paths`, and
the canonical writer component must connect to that slice; task-wide rename/split/merge
alias unions remain permanent.
A trace document has exactly one scenario for each non-empty unique top-level task;
rollover remains events in that scenario, so materiality, sampling, owner, compaction,
gate, admission, and receipt state cannot reset at a scenario boundary.

Freeze occurs only after every task writer across all slices is terminal. Any later
writer or owner mutation fails closed, invalidates that generation and every gate,
and requires a new freeze. Tester, reviewer, every gate, and close
recompute HEAD, index, worktree, and complete changed-path digests. Any hash change
invalidates all gates. Each invariant belongs to exactly one gate, and three disjoint
fresh gates must PASS the same final hash; each reviewer transfer invariant set equals
its registered/result gate ownership, and repairs rerun all three at the next attempt.
Messages and follow-ups are typed, digest-bound, same-scope control events. Message
receipts bind the original transfer digest, exact purpose, canonical dependency digest,
and canonical semantic message digest (excluding only the authority anchor and digest
fields). A default peer needs host capability plus an executed `artifact_receipt` relay
whose digest was emitted by the named producer's terminal receipt and admitted by the
consumer transfer; polling, no-op peers,
custom-role messaging, reviewer self-review, unregistered peers, and scope changes
are hard blockers. Close requires the full task tree terminal.

Role-specific transfers require tester acceptance fields plus one safe child-owned path
artifact; a tester body is invalid. Both reviewers accept `none` or an optional child-owned
Markdown body with the canonical body-marker transfer rule. The xhigh reviewer has no
escalation receipt; max requires the full evidence-qualified escalation receipt. At consumption, every external receipt
rejects all pre-indexed task participants: primary access/materiality allow host, owner,
or sealed harness; compaction/message allow host or owner; peer capability/relay and
pilot require host.

Pilot activation requires a host authorization anchor outside the trace for a new
task after freeze. It binds authorization event/text, task/slice, signer, non-empty
string actions, target identity, exact frozen HEAD revision, package/contract, validity,
and exact excluded active-task IDs; repair makes it stale, and normalized create-task
actions are forbidden. Without CI, target, and
signed pilot evidence, the highest claim remains `verified-local`.

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
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --check --format json > /absolute/path/to/plan-receipt.json
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --apply --plan-receipt /absolute/path/to/plan-receipt.json
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --restore-receipt /absolute/path/from/RESTORE_RECEIPT
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --doctor
python3 -B install.py --codex-home /absolute/path/to/.codex --agents-language en --doctor --format json
```

`--check` does not create the target directory or write files. It reports every
planned path and content SHA-256 in text mode. Its JSON form is a strict plan
receipt binding the target realpath and device, language, manifest-verified
source archive, install contract, and every prior and desired hash, mode, and
absence. A source in a Git worktree is accepted only when the package root is
the worktree root, HEAD tracks the manifest and every declared package path, and
the complete worktree including untracked files is clean; the receipt records
that exact HEAD. A manifest-verified release archive with no discoverable Git
metadata (or an explicitly substituted test manifest) uses the reproducible
archive identity and records that no revision was available. A dirty or nested
Git source fails instead of silently falling back, and the installer never
fabricates a commit identity. `--apply` requires this receipt and consumes and recomputes it
while holding the same target-scoped lock used by check and restore. Source,
target, plan, symlink, device, or receipt drift fails closed.
The package manifest, migration catalog, managed state, plan/restore receipts,
and every apply/restore journal use duplicate-key-rejecting JSON parsing; an
ambiguous document is rejected before journal creation or target mutation.
`--doctor` is read-only and classifies the current installation, active apply
lock, unfinished apply, write-cleanup, or restore transaction, retained restore
receipts, orphan or conflicting write-recovery state, and any quarantined
retired artifacts. Add
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
only from managed inputs, so documentation, tests, and CI metadata do not create
false lineage breaks. Known predecessor contracts can be upgraded only when the
complete managed-hash map matches an externally anchored package profile and
the recorded hashes still match every managed target. An accepted contract hash
alone cannot authenticate a rewritten state file.

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
same-directory temporary files, `fsync`, atomic no-replace moves, and a durable
transaction journal. Before its first managed replacement, it copies every
existing prior file into a digest-addressed, no-replace target-local restore
vault snapshot with an independent inode, exact bytes and mode, and durable file
and directory `fsync`; prior absence is recorded explicitly. Content and mode
are rechecked immediately before each managed mutation. Each existing live
preimage is then atomically claimed into a transaction-id-owned
`.write-recovery/` path and verified again; the candidate is renamed only into
an absent live path. A concurrent live or staging collision is preserved and
leaves the journal recoverable instead of being replaced. Atomicity is per file,
not across the complete plan. If a
late change or interruption stops an apply, already completed `TOUCHED` receipts
are flushed and the journal remains for read-only diagnosis and idempotent
forward recovery with the same package, language, and plan receipt. Conflicting
partial state fails closed; the installer never silently rolls it back or
overwrites it.
A crash can leave either the source and quarantine links or the quarantine and
staging links. `--doctor` reports both recoverable states, and the next matching
apply finishes the journal forward without replacing any existing path. A
verified staging link remains afterward as a read-only retirement receipt.

Successful apply emits an absolute `RESTORE_RECEIPT` path. The install journal
is retained through exact candidate postimage validation and durable receipt
creation. Only then does a durable cleanup journal bind the install transaction,
plan and restore receipt, source/target identity, prior vault paths, and every
transaction-owned `.write-recovery/` path. Cleanup atomically claims only that
transaction subtree, then atomically claims and re-verifies each staged entry
against its independent prior-vault snapshot before removing the claimed name.
A replacement observed at either claim boundary is preserved and blocks the
same receipt from continuing silently. The install journal is
removed only after staging cleanup completes; the cleanup journal is removed
only after the install journal is durably gone. Cleanup interruptions therefore
remain doctor-visible and resume with the same receipt, while a mismatch,
symlink, unexpected file, cross-transaction path, or namespace collision is
preserved and blocks cleanup. A completed apply has no write-recovery files;
unclassified recovery subtrees are reported as orphans rather than HEALTHY.
If interruption persists receipt-bound apply metadata before the install
journal, retry proceeds only when every live target still equals its exact prior
preimage; exact candidate postimages require the durable restore receipt, while
mixed or conflicting state fails closed.
Restore first verifies every candidate postimage, then copies all displaced
candidate bytes and modes into independent-inode, no-replace, `fsync`-durable
vault snapshots. It atomically claims each exact live candidate into
receipt-owned staging before restoring prior bytes and modes exclusively into
an absent live path; prior absence is restored by the claim itself. A concurrent
replacement is never unlinked or overwritten, and the claimed candidate plus
journal remain resumable. Its journal is independent and resumable with the same
receipt. Cross-home receipts, incomplete or modified receipts, vault damage,
candidate drift, and concurrent changes fail closed. Both prior backups and
displaced candidate bytes are retained for readback; restore is not a generic
uninstaller and cannot overwrite later user changes.

Review `--doctor`,
`skills/subagent-orchestrator/.managed-package-state.json`, any
`.install-transaction.json`, receipt-bound apply/restore journal,
`.restore-receipts/`, `.restore-vault/`, `.retired/`, or
`.retirement-receipts/`, `.write-recovery/`, `.write-recovery-cleanup/`, and the
write-cleanup journal, plus `AGENTS.md` and `config.toml`, before any
manual cleanup. A stale target lock also requires manual inspection; there is
intentionally no force-unlock flag.

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

A local PASS proves only the file contract, hermetic tests, and deterministic
topology conformance. It does not prove model availability, account access,
client reload state, live bounded-peer capability, or current role quality.

After changing any published file, rebuild the deterministic manifest:

```bash
python3 -B build_manifest.py --package-version 2026.08.16
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
holdout evidence are separate inputs. This scaffold promotes custom leaf roles;
bounded-peer activation uses the separate current-client capability gate:

```bash
python3 -B -m evaluation validate --campaign campaign.json \
  --quality-authority /outside/repository/development-quality-authority.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --sealed-quality-authority /outside/repository/sealed-quality-authority.json
python3 -B -m evaluation report --campaign campaign.json \
  --quality-authority /outside/repository/development-quality-authority.json \
  --sealed-holdout /outside/repository/sealed-results.json \
  --sealed-quality-authority /outside/repository/sealed-quality-authority.json \
  --output report.json
python3 -B -m evaluation smoke
python3 -B -m evaluation production-facts \
  --parent /absolute/parent.jsonl --children-root /absolute/children \
  --repo /absolute/repo --base BASE_REV --cutoff 2026-08-16T12:00:00+08:00 \
  --source-state terminal --output /absolute/production-fact.json
python3 -B -m evaluation evidence-tier \
  --input implemented.json --input verified-local.json
```

Each billed primary, child, review, repair, failed-attempt, or retry task records
its actual model, effort, service tier, tokens, and exact credits. Reports compare
normalized quality per pair, require package-key-authenticated external quality admissions,
reject reused fixture/prompt identities and imbalanced arm order, require
non-regressing pair/class/overall costs, and keep mandatory governance retention
separate from efficiency promotion. `production-fact.v3` extracts hash-bound,
privacy-preserving rollout/Git observations and independently records only
explicit, reconciled thread/run credits without token-based estimation, while
the evidence-tier validator enforces an unskippable predecessor-digest chain.
See [`evaluation/README.md`](evaluation/README.md) for the evidence boundary and
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
│   ├── AGENTS.section.en.md
│   ├── AGENTS.section.zh.md
│   ├── config.agents.toml
│   ├── agents/
│   └── skills/subagent-orchestrator/
└── tests/
```

Licensed under the [MIT License](LICENSE).

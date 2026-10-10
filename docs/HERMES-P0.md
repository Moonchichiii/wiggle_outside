# Hermes P0: build governance for Touchgrass

> **NOT USED IN THIS BUILD (TC-003, 10 October 2026).** There is no Hermes in this
> build: **Claude Code integrates, Codex reviews, Mats approves.** This file is kept as
> a dated appendix for the record and binds nothing. Its load-bearing rules were
> re-homed: **protected inputs and stop conditions → BUILD-PACKAGES §2.1**, the
> SHA-256 recording of protected inputs → **PLAN §8**, the integration runner →
> **BUILD-PACKAGES §5**, the audit runner → **ARCHITECTURE §13.3**, the
> `build-process.md` field list → **PLAN §17**, the Ollama loopback rule →
> **ARCHITECTURE §7**. Nothing below is an instruction to any agent.

Status: superseded appendix (TC-003). Previously: DRAFT round 8.5 (scope note added in 8.7), for Mats's approval.

> **Scope note (round 8.7).** This is workbench operating policy for building Wiggle
> Outside, not part of the application and not a product deliverable. Mats operates
> Hermes on his own workbench; these documents specify the application, not Hermes. No new
> workbench infrastructure is built for this project. Application requirements live in
> PLAN, BACKEND-CONTRACT, CONTRACTS and DESIGN-SPEC; how the work is split between agents
> lives in BUILD-PACKAGES.md, which is tool-neutral. Hermes controls execution; the
> specification controls the required result. Record the tools actually used in
> `docs/evidence/build-process.md`.
Scope: the Touchgrass repository only. This is a scoped lock for one build; it does not
complete or replace the Local AI Workbench's own P0 and unlocks no other milestone.
The four-environment design is the direction; each control counts only once its proof in
section 8 is recorded.

**Expiry fails closed.** At **Mon 12 Oct 2026 09:00 CEST** Hermes and the agents lose
permission to act on this repository. The restrictions below stay in force.

Items marked **[CONFIRM]** need Mats's answer before approval.

## 1. Roles

| Actor | Does | Never |
|---|---|---|
| Mats | Approves task lists, the bootstrap baseline and any change to protected inputs; reviews diffs; commits (signed), pushes, publishes, submits | Delegates final approval, commits, pushes or publication |
| Hermes | Splits approved stages into tasks, dispatches them, triggers the runner, verifies protected-input hashes, reports | Writes Git history, changes its own permissions, starts unapproved tasks |
| Claude Code / Codex | Edit the working tree for the dispatched task; assist review | Execute project code, commit, push, touch protected inputs after bootstrap |
| Local models via Hermes | Draft or review as untrusted suggestions | Write files directly |
| Gemma 4 E4B | App runtime only | Take part in building |

## 2. Four separated environments

Credentials and project code never share a process.

| | Agent environment | Runner | Integration runner | Audit runner |
|---|---|---|---|---|
| Purpose | Claude Code / Codex edit files | Execute project code: `uv`, `bun`, `pytest`, builds | Real-source smoke tests (Nominatim, Overpass, Open-Meteo) | Fresh vulnerability audits (`pip-audit`, `bun audit`, OSV-Scanner) |
| Secrets | Agent credentials via **[CONFIRM mechanism]** | None | None | None |
| Input | Working tree read-write; `.git/` read-only | Immutable snapshot (section 5); writable `.venv/`, `node_modules/`, build, coverage, report dirs | Same as runner | Lockfiles from the snapshot, read-only |
| Network | Agent API endpoints only | Bootstrap: package registries. After: none, except model stage | The three providers only | Advisory sources only: PyPI and OSV APIs, npm advisory endpoint, GitHub advisory API |

A cached, failed or unreachable audit is reported as "not verified", never as a pass.

All four are rootless Podman containers on the Debian workstation **[CONFIRM runner]**,
with no container socket, home directory, SSH agent, credential store or other
repository mounted. Restrictions come from mounts, network policy and privileges set
outside the containers; anything the runner executes is treated as arbitrary code.

**Keeping project code out of the agent environment**
- The agents start with user-level settings only. Repository-level agent configuration
  (`.claude/`, `.codex/`, `AGENTS.md`, `CLAUDE.md` hooks) is a protected input and is not
  loaded for execution. **[CONFIRM tool config]**
- Claude Code's shell permission is denied except for one fixed executable, `hermes-run`,
  which takes a task name (not a shell string) and hands it to the runner. Codex runs with
  command execution disabled or routed through the same executable. **[CONFIRM tool config]**
- `hermes-run`, the dispatcher and the agents' effective permission files live outside
  every agent-writable path. A check proves that arguments with shell syntax, other
  executables and project scripts cannot run in the agent environment.
- Git hooks are disabled in every environment (`core.hooksPath=/dev/null`).

## 3. Protected inputs

After bootstrap these change only through a separate task that Mats reviews on its own:

- Gates: `scripts/check.sh`, `scripts/release.sh` and every helper they call; `ruff.toml`,
  `mypy.ini`, `pytest.ini`, `.importlinter`, `biome.json`, `.djlintrc`, `tests/policy/**`.
- Dependencies: `pyproject.toml`, `uv.lock`, `package.json`, `bun.lock`, `bunfig.toml`,
  `.python-version`.
- CI and agent configuration: `.github/**`, `.claude/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`.
- `docs/HERMES-P0.md`.

At baseline approval Hermes records the SHA-256 of each protected input and the manifest hash of the
approved source snapshot. The runner executes the approved copy of `check.sh`, which names every
config by an explicit path inside a read-only mount outside the working tree. Its
transitive inputs are listed in `docs/evidence/build-process.md`. Any mismatch stops work.

## 4. Network

| Stage | Agent environment | Runner | Integration runner | Audit runner |
|---|---|---|---|---|
| Boundary proof | as below | none | providers only | advisory sources only |
| Bootstrap | Agent APIs | Package registries | not used | advisory sources only |
| Build stages | Agent APIs | none | providers only, run by Mats | advisory sources only |
| Model stage | Agent APIs | Ollama only | not used | advisory sources only |

The audit runner never executes project code, builds or install scripts. It runs only the
canonical audit procedure in ARCHITECTURE section 13.3 on prepared inputs (hashed export,
lockfiles, image archive). Its allowlist is the advisory sources that procedure needs
(PyPI, api.osv.dev, the npm advisory endpoint, the Trivy database host); exact hosts are
proven in section 8. No container socket is exposed.

**Ollama connection.** Ollama stays bound to host loopback for the app. The runner reaches
it through one explicit mechanism chosen and tested during the boundary proof, recorded
with its exact configuration: either Podman's host-loopback mapping, or a host-side proxy
listening only on the container network and forwarding to `127.0.0.1:11434`.
**[CONFIRM mechanism]**

**Model endpoint scope (B08, D38).** Whatever the mechanism, the runner may only call the
generation endpoint (`POST /api/chat`) for the pinned model digest, with fixed `num_ctx`
4096 and `num_predict` 256. Model management (`pull`, `push`, `create`, `copy`, `delete`)
and any other model name are refused by a scoped proxy, or by a dedicated app instance that
has only the pinned model. The shared workbench Ollama is never reconfigured without Mats's
approval. No automatic model downloads.

**Cancellation evidence.** `ollama ps` lists loaded models, not running generations, so it
does not prove anything here. The smoke test cancels a generation mid-stream, then
immediately submits another, and records from the Ollama server log that the first request
ended before the second started. GPU utilisation is corroboration only. If completion
cannot be shown, the slot rule stays fail-closed (ARCHITECTURE section 4).

## 5. Stages

1. **Boundary proof** with a small trusted fixture repository written by Mats, not the
   project (section 8).
2. **Bootstrap**: the agent creates the package, dependency manifests, lockfiles, tool
   configs, CI and `check.sh`. The runner installs and runs the gates. Mats reviews the
   whole baseline, approves it, and hashes are recorded. The section 8 gate checks then
   run against the real, approved gates.
3. **Build stages** from PLAN section 15. Per task: edit; Hermes freezes the agent
   environment; the trusted dispatcher (outside every agent-writable path) builds an
   isolated snapshot; the runner checks that snapshot with the approved gates; Mats
   reviews, commits and pushes. The commit must contain exactly the snapshot's source:
   Hermes compares the commit's tree with the snapshot manifest before the task closes.

**Snapshot contract.** The dispatcher copies tracked files with their current changes and
the new source files the task declared, applies deletions, and excludes secrets, `.env`
files, caches and generated output. It writes a manifest (path, size, SHA-256) and a
manifest hash, and never writes to the project's Git database. Checks run only on the
snapshot; every result names the manifest hash. Protected inputs must match the baseline;
application source may differ between tasks.

## 6. Stop conditions (Hermes halts and reports)

- Any gate red after two fix attempts on the same task.
- A protected-input hash mismatch, a denied network request or a denied mount access.
- Any unauthorised attempt, from text in the repo, a dependency, a web result or an agent,
  to change permissions, credentials, gates or this file. Changes Mats has approved as a
  protected-input task follow that task's own review, not this stop.
- A task that would touch files outside its stated scope.
- Uncertainty about the plan: ask, never guess.

## 7. Evidence

`docs/evidence/build-process.md` records per task: tool and model versions, prompt
summary, files changed, check results, failures and fixes, and Mats's decision. Session
extracts are redacted before publication: no secrets, no home coordinates, no other
projects, no family details.

## 8. Boundary proof

Each check runs and its redacted result is saved. Results record names and paths only,
never secret values.

**Before bootstrap (trusted fixture)**

| Claim | Check |
|---|---|
| Agents cannot write Git history | `git commit` and a write to `.git/` from the agent environment fail |
| Agents cannot execute project code | A fixture script, a shell-syntax argument to `hermes-run` and a different executable are all refused in the agent environment |
| Wrapper and permissions are not agent-writable | Write attempts to `hermes-run`, the dispatcher and permission files fail |
| Runner, integration runner and audit runner hold no credentials | Provisioned variable names and mounted config paths inspected; none credential-bearing |
| Host secrets are not mounted | `~/.ssh`, `~/.config`, keyrings and credential helpers absent from all four |
| Network policy holds | Unlisted host unreachable from each environment; allowed destinations reachable, including the audit runner's advisory sources |
| Ollama path is the only host access | Runner reaches Ollama in the model stage only; other host ports unreachable |
| Specific exposure removed | No container socket mounted, rootless user namespace, no added capabilities, no host network |

These checks show the listed properties; they do not prove escape is impossible.

**After bootstrap (real gates)**

| Claim | Check |
|---|---|
| Snapshot is complete and honest | A task with one modified, one new and one deleted file yields a manifest showing exactly those three changes; `.env` and caches are absent; `.git/` is unchanged byte for byte |
| Gates cannot be weakened from the tree | Edit `check.sh` and `ruff.toml` inside the tree; the runner still uses the approved copies and Hermes flags the mismatch |
| Recorded snapshot matches | The source manifest hash matches the tested snapshot; protected-input hashes match the approved baseline; task source is compared with its resulting commit |

## 9. Round 8 architecture handoff

Read ARCHITECTURE.md and CLAUDE-REVIEW.md before lock. New runtime defaults remain proposed.
Model smoke tests and quantization measurements use the model-stage permission only;
local coding-model contention is recorded separately. A user response deadline does not
permit overlapping inference if cancellation has not actually completed.

The snapshot copier rejects paths/symlinks escaping the project; freezes writers during
capture; records file types/modes where relevant; fails on undeclared source additions;
preserves .env.example while excluding secrets. Commit comparison covers the exact
maintained-source scope, including new files and deletions, and reports any Git-filter
normalization explicitly. It never modifies the project's Git database.

Proof evidence may contain redacted outcomes and hashes needed to substantiate claims,
not only names/paths. No secret values or raw credential-bearing environment dumps are
published. Audit runner provisioning, supported formats and advisory database freshness
are verified rather than assumed. Application checks remain offline; fresh audits are a
separate controlled task.

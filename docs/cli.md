# Command reference

Every command of the runtime (`.ai-sdlc/bin/sdlc.py`) and the installer (`install.sh`).
Each runtime command also explains itself with examples: `python3 .ai-sdlc/bin/sdlc.py <command> -h`.

## The runtime: `python3 .ai-sdlc/bin/sdlc.py <command>`

Grouped the way `sdlc.py --help` groups them:

| Group | Commands |
| --- | --- |
| Records and checks | `doctor`, `verify`, `bite`, `plan-check` |
| Viewer and reports | `view`, `lens`, `audit`, `metrics` |
| Work items and agents | `claim`, `release`, `claims`, `parallel`, `trailers`, `review`, `log` |
| Specs | `spec` |
| Setup | `config`, `fix` |

Global options: `--root <dir>` runs against another project; `--selftest` checks the
runtime itself. Exit codes: `0` success, `1` a check failed (with `--strict`) or an action
was refused, `2` a usage error.

| Command | Key Flags | Description |
| --- | --- | --- |
| **`doctor`** | `--strict`, `--baseline`, `--all`, `--json` | Audits project records, active roles, check commands, staleness windows, and validates the dependency graph (flags self-dependencies, non-existent backlog IDs, and circular dependency loops). Ages the backlog against the same window: an `In progress` or `In review` row nothing has named since the window passed is a zombie claim; a `Ready`, `Blocked` or `Parked` row older than the window needs a decision. Every finding says how to fix it and who can: a command (`tool`), your agent (`agent`), or you (`owner`); `--json` carries them as `fix` and `who`. What each item owes follows its tier: a Tier 3 item's commit is its whole record.<br>`--baseline` accepts today's findings in `docs/project/doctor-baseline.json`, so an old project can turn on `--strict` in CI and see only new problems. Doctor and the viewer still say how many are accepted, and since when. Once the file exists, a rewrite only drops fixed findings and never adds one. A leaked credential is never accepted. `--all` lists the accepted ones. |
| **`verify`** | `--item <ID>`, `--parallel` (`-j`), `--stage`, `--timeout` | Runs the charter's check pipeline in order, writing immutable test evidence (`summary.md`, `summary.json`, and stage `.log` files) to `.ai-sdlc/evidence/<timestamp>/`. `--item` names the work item in the ledger rows, so the run counts for that item even before its commit exists. `--parallel` runs independent steps concurrently using a worker pool. |
| **`finish <ID>`** | `--waive verify --by <name> --reason "…"`, `--dry-run` | Closes a built item in one step, checking only what its tier owes:<br>- a `verify` run on its commits (not at Tier 3), or a waiver by a named person: recorded as *Not run*, never Verified, and not allowed at Tier 1<br>- a ship review at Tier 1, and an independent review where the charter asks for one<br>- `plan-check`, when there is a plan<br>Then it drafts the worklog entry from git and the ledger (the compact line for Tier 3 under Strict, and for Lean Tier 2), marking what only the agent knows `TODO(finish)`, and refuses until those are written. Last it moves the row to Done, or to **Parked** at Tier 1 for the human merge approval. Exit `1` lists each thing still owed with the command that supplies it. On an item already Done it only drafts a missing worklog entry. |
| **`guard start\|stop`** | | The finish guard, run by Claude Code's SessionStart and Stop hooks (reads the hook JSON on stdin). When the agent stops, it names a Tier 1 or 2 item this session committed that is not Done or Parked, once per item, and asks for `finish`. It never blocks a tool call. The installer registers it for Claude Code (`--no-finish-guard` to skip; `--upgrade --finish-guard` to add it later), and the charter's **Finish guard** row turns it off. |
| **`plan-check <ID>`** | | Compares branch changes against the approved plan (`docs/project/plans/<ID>.md` or `.sdlc/specs/<ID>/spec.md`). Highlights unapproved file modifications and planned files left untouched with ANSI terminal colors. |
| **`view`** | `--serve`, `--port`, `--interval`, `--github`, `--no-user`, `--export-html <file>`, `--svg`, `--no-open`, `--json` | Draws the project as one interactive page ([the viewer](viewer.md)): Inbox, Board, Dashboard, Blockages, Git, Documents, Project. `--serve` keeps it live on `127.0.0.1` and lets it run commands and change kit settings; `--github` adds open issues and PRs; `--no-user` hides `~/.claude` items. `--export-html` writes one offline file. |
| **`lens`** | `--area stack\|deps\|build\|security\|deploy\|env\|agents`, `--user`, `--json` | The **Project lens**, read-only:<br>- the stack, detected live<br>- direct dependencies per manifest, with lockfiles<br>- `file:line` errors from the latest failing verify stages<br>- security: vulnerable packages from the last `audit`, doctor's sensitive-data findings, a committed or un-ignored `.env`, container risks, open security-review findings<br>- deployment platforms, CI workflows and containers (Dockerfiles, compose services)<br>- environment variable **names** (templates vs code; values are never read)<br>- the agentic stack: skills, commands, subagents, hooks, MCP servers, plugins, harness files and other kits; `--user` adds `~/.claude` |
| **`spec list\|show\|validate\|apply`** | `apply <ID> [--write]`, `validate [--strict]`, `--json` | Living specs, when the charter's **Specs** row is on (`config --specs on`).<br>- `docs/project/specs/<capability>.md` holds requirements (SHALL/MUST) with WHEN/THEN scenarios.<br>- An item that changes behaviour adds `specs/changes/<ID>.md` (ADDED / MODIFIED / REMOVED).<br>- `apply` merges it on close (exact names only, a dry run without `--write`) and archives it.<br>- An existing `openspec/` folder and Spec Kit specs are read beside them, read-only.<br>- Shown under Documents ▸ Specs and in each item's thread. |
| **`claim <ID>`** | `--agent`, `--worktree PATH`, `--no-worktree`, `--base REF`, `--mark` | Takes a work item. It writes an atomic claim to `<git-common-dir>/nuhut/claims/`, which every worktree of the clone sees, so a second agent is refused. It creates the branch `<ID>-<slug>` and, by default, a worktree at `../<repo>-<ID>`. `--mark` sets the backlog row to In progress, from the main worktree only. |
| **`release <ID>`** / **`claims`** | `--remove-worktree` / `--json` | Frees an item (`--remove-worktree` is refused when the worktree is dirty), or lists who holds what. Doctor warns about claims gone stale, claims on finished items, and two branches for one claimed item. |
| **`parallel`** | `--json` | The unclaimed Ready items whose dependencies are done, grouped so that no two in a group touch the same files (from each plan's *Files that change*; the charter, migrations and lockfiles each count as one shared file). Also lists the conflicting pairs and the items that need a plan first. The Dashboard shows it under *Parallel work*. |
| **`audit`** | `--strict`, `--timeout`, `--json` | Runs the charter's `scan` stage in its JSON form (npm/pnpm/yarn audit, pip-audit, osv-scanner, cargo audit, govulncheck). It keeps the vulnerable packages under `.ai-sdlc/evidence/<stamp>-audit/` for the lens. The kit fetches nothing itself. |
| **`metrics`** | `--json` | Calculates quantitative project health metrics: work-in-progress (WIP), verification pass rate, cycle time, lead time, time waiting on humans, lifecycle record gaps, and usage against the charter's optional agent budget per tier. |
| **`log`** | `--since <ref>`, `--id <ID>`, `--write` | Drafts worklog lines, one per work item, from the commits since `<ref>` (IDs from subjects or `Work-Item` trailers) and the verify runs recorded on them. `--id` drafts one item's line, from just before its first commit unless `--since` says otherwise. `--write` inserts them under the worklog's marker, newest first, skipping items the worklog already names. Records become byproducts, not essays. |
| **`bite`** | `--base`, `--timeout`, `--restore`, `--json` | Puts the changed product files (never tests, never the kit's paths) back to the base, runs the test command, and restores them. It passes only when the tests pass with the change and fail without it. A backup and marker under `.ai-sdlc/bite/` make an interrupted run recoverable with `--restore`, and the doctor flags one. |
| **`trailers <ID>`** | `--agent`, `--model` | Prints the `Work-Item`, `Agent` and `Model` commit trailers, from flags, `AI_SDLC_AGENT` / `AI_SDLC_MODEL`, or what the harness exposes. |
| **`review <ID>`** | `--role`, `--by claude\|codex\|gemini\|cmd:<command>`, `--model`, `--stage` | Sends one role's playbook, the item's diff, the relevant charter rows and the tier to another harness, headless, and saves the review with the reviewer's and author's identity, labelled independent or self-check. |
| **`config`** | `--effort`, `--independent-review`, `--tier-rules`, `--decision-style`, `--dev-method`, `--reviewer`, `--token-saving`, `--set-check`, `--json` | Inspects or atomically updates kit constraints in `docs/project/charter.md` and syncs `.ai-sdlc/profile.json`. `--token-saving on` switches to `Lean` effort, `Independent review required for: none`, `Standard` tier rules, and compact tier budgets in one step. |
| **`fix`** | `<sync-profile\|wire-pointer\|restore-bite\|unlock-tests\|all>`, `<rotate-worklog\|normalise-status\|link-evidence> [--apply]`, `--json` | Repairs safe, non-destructive setup drift: syncs `.ai-sdlc/profile.json` from the charter, restores missing `AGENTS.md` pointer lines (`CLAUDE.md`, `.cursor/rules/`, etc.), restores interrupted `bite` backups, and clears stale test locks. Never modifies SHA-256-tracked kit files in `.ai-sdlc/manifest.json`.<br>Three record repairs preview what they would change until you add `--apply`:<br>- `rotate-worklog` moves the oldest entries into `worklog-archive/<year>-part<N>.md`<br>- `normalise-status` rewrites a status the board already reads as a kit status (`Completed (merged 8acbc4a)` → `Done`), keeping the note in the Task cell<br>- `link-evidence` adds ledger rows for verify runs kept on disk that never reached the ledger<br>None of them invents evidence. |

Guides for the bigger commands: [the viewer](viewer.md) (`view`, `lens`, `audit`),
[several agents at once](multi-agent.md) (`claim`, `release`, `claims`, `parallel`,
`review`), [living specs](specs.md) (`spec`), and [the runtime](runtime.md) for evidence,
`verify` and `bite`.

## Slash commands (Claude Code) and loop skills (other tools)

| Command | Does |
| --- | --- |
| `/sdlc-plan <request>` | Frame the request as a work item, read the charter, plan at the right tier, run the design review |
| `/sdlc-build <ID>` | Build an approved plan task by task, with a failing test first for a defect |
| `/sdlc-verify [ID]` | Run `sdlc.py verify` and judge the results |
| `/sdlc-review <ID>` | Ship review by the active roles, opening with `plan-check` |
| `/sdlc-finish <ID>` | Run `sdlc.py finish`, supply what it lists as owed, fill the drafted worklog entry, then the closing work no script can |
| `/sdlc-log <ID>` | Close the item by hand: worklog, backlog, docs it falsified, ADR, spec change applied |
| `/sdlc-doctor` | Audit the records, mechanically then by judgment |

Tools whose `/` menu lists skills (Codex, Cursor, Gemini CLI, Copilot, Antigravity) get the
same loop as the `sdlc-plan` … `sdlc-log` skills.

## The installer: `./install.sh [dir] [PREFIX] [options]`

`./install.sh --help` shows the options on one page, `--help full` explains each,
`--list <what>` lists the values (harnesses, platforms, presets, types, skills, sections)
and `--explain <topic>` explains a concept. The ones you will use most:

| Option | Does |
| --- | --- |
| *(none)* | Guided setup: shows what it detected, asks what it cannot, writes nothing until you confirm |
| `--quick` / `--full` / `--sections <list>` | Ask the essentials / every question / only these sections |
| `-y` | No questions, every default (implied without a terminal) |
| `--preset solo\|team\|regulated` | Effort, decision style, method and tier rules together |
| `--harness <list>` | Which AI tools read it: claude, cursor, copilot, gemini, windsurf, cline, roo, amp, aider, all |
| `--specs on\|off` | Living specs of what the system does (default off) |
| `--hooks`, `--git-hooks [secrets]` | Enforcement: tool-call guards, and commit guards every tool and person inherits |
| `--deploy <list>` | Deploy platform checklists |
| `--profile compact` | Shorter documents for small models |
| `--dry-run` | List what would be written |
| `--upgrade [--adopt]` | Refresh the kit's managed files later; never touches project records |

Every option, the layout it writes, managed platforms and stack detection:
[installing and upgrading](install.md).

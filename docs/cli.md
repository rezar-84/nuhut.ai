# Command reference

Every command of the runtime (`.ai-sdlc/bin/sdlc.py`) and the installer (`install.sh`).
Each runtime command also explains itself with examples: `python3 .ai-sdlc/bin/sdlc.py <command> -h`.

## The runtime: `python3 .ai-sdlc/bin/sdlc.py <command>`

Grouped the way `sdlc.py --help` groups them:

| Group | Commands |
| --- | --- |
| Start here | `status` |
| Records and checks | `doctor`, `verify`, `finish`, `bite`, `plan-check`, `render` |
| Viewer and reports | `view`, `lens`, `audit`, `metrics` |
| Work items and agents | `item`, `hotfix`, `next-id`, `claim`, `release`, `claims`, `parallel`, `trailers`, `sync`, `review`, `log`, `guard` |
| Specs | `spec` |
| Writing | `slop` |
| Setup | `config`, `fix` |

Global options: `--root <dir>` runs against another project; `--selftest` checks the
runtime itself. Exit codes: `0` success, `1` a check failed (with `--strict`) or an action
was refused, `2` a usage error.

| Command | Key Flags | Description |
| --- | --- | --- |
| **`status`** | `--json` | One screen of what to do next on this branch, read-only. It opens with the setup this clone is missing, each with its fix: a merge driver `.gitattributes` asks for that is not configured (`fix merge-driver`), an identity that is unset or that `docs/project/people.json` does not know (`NUHUT_USER`, else `git config user.name`), and `gh` missing or not logged in while open Tier 1 items exist. Then your items, which are the claims on this branch or worktree or held by you, plus an item named in the branch name. For each it gives the next step it owes (`plan`, `build`, `verify`, `review`, `log`, `finish`, or `release` for a claim on a finished item), using the same rules `finish --dry-run` uses. Then items Parked or Blocked on you, Ready items you could take (`parallel`'s list, and those that need a plan first), and the doctor finding count. Always exits `0`. Joining a project: [joining.md](joining.md). |
| **`doctor`** | `--strict`, `--baseline`, `--all`, `--json` | Audits project records, active roles, check commands, staleness windows, and validates the dependency graph (flags self-dependencies, non-existent backlog IDs, and circular dependency loops). Ages the backlog against the same window: an `In progress` or `In review` row nothing has named since the window passed is a zombie claim; a `Ready`, `Blocked` or `Parked` row older than the window needs a decision. Every finding says how to fix it and who can: a command (`tool`), your agent (`agent`), or you (`owner`); `--json` carries them as `fix` and `who`. What each item owes follows its tier: a Tier 3 item's commit is its whole record.<br>`--baseline` accepts today's findings in `docs/project/doctor-baseline.json`, so an old project can turn on `--strict` in CI and see only new problems. Doctor and the viewer still say how many are accepted, and since when. Once the file exists, a rewrite only drops fixed findings and never adds one. A leaked credential is never accepted. `--all` lists the accepted ones. |
| **`verify`** | `--item <ID>`, `--parallel` (`-j`), `--stage`, `--timeout` | Runs the charter's check pipeline in order, writing immutable test evidence (`summary.md`, `summary.json`, and stage `.log` files) to `.ai-sdlc/evidence/<timestamp>/`. `--item` names the work item in the ledger rows. A clean tagged run counts for the item once one of the item's commits is in its history; a run made with uncommitted changes counts when the item's next commit is made on top of it. Uncommitted records (`<docs>/project/**` other than the charter) and `.ai-sdlc/` state do not make a run dirty. `--stage` records the selected stages in the ledger, and a `--stage` run never satisfies `finish`. `--parallel` runs independent steps concurrently using a worker pool. |
| **`finish <ID>`** | `--waive verify --by <name> --reason "…"`, `--dry-run` | Closes a built item in one step, checking only what its tier owes:<br>- a full `verify` run (every charter stage that has a command, no `--stage`) made clean on the item's newest code commit or a descendant of it, or dirty on that commit's parent (not at Tier 3). Records-only commits (ledger, worklog, status) do not make a run stale. A partial run and a stale run each get their own message<br>- or a waiver: recorded as *Not run*, never Verified, and not allowed at Tier 1. `--by` must name someone in the charter's **Approvers** row as it stands on the default branch (`origin/<default>`, else `<default>`), so a branch that adds a name gains nothing until it merges; a blank Approvers row refuses every waiver. The ledger records `waived_by` and `waived_as`, the identity running the command: `NUHUT_USER`, else `git config user.name`, mapped through `people.json` when there is one. With no terminal attached, the waiver is refused unless that identity is the named approver. `NUHUT_USER` is an honour-system value that any process, an agent's included, can set. A waiver stops counting once its approver leaves the row, and `finish` says so<br>Commits belong to the item only through a `Work-Item: <ID>` trailer (`sdlc.py trailers <ID>`); a mention in the subject or body does not attribute a commit.<br>- a ship review at Tier 1, and an independent review where the charter asks for one<br>- `plan-check`, when there is a plan<br>Then it drafts the worklog entry from git and the ledger (the compact line for Tier 3 under Strict, and for Lean Tier 2), marking what only the agent knows `TODO(finish)`, and refuses until those are written. Last it moves the row to Done, or to **Parked** at Tier 1 for the human merge approval. It also refuses while a review finding is escalated to a person with no decision in the review's Responses table. Exit `1` lists each thing still owed with the command that supplies it. On an item already Done it only drafts a missing worklog entry. |
| **`guard start\|stop`** | | The finish guard, run by Claude Code's SessionStart and Stop hooks (reads the hook JSON on stdin). When the agent stops, it names a Tier 1 or 2 item this session committed that is not Done or Parked, once per item, and asks for `finish`. It never blocks a tool call. The installer registers it for Claude Code (`--no-finish-guard` to skip; `--upgrade --finish-guard` to add it later), and the charter's **Finish guard** row turns it off. |
| **`plan-check <ID>`** | `--base REF`, `--strict`, `--pre`, `--json` | Compares branch changes against the approved plan (`docs/project/plans/<ID>.md` or `.sdlc/specs/<ID>/spec.md`). Highlights unapproved file modifications and planned files left untouched with ANSI terminal colors, and warns when the plan's paths match over half the repository. Counts `.ai-sdlc/bin/`, `profile.json` and `manifest.json`; other `.ai-sdlc/` state is ignored. `--strict` exits `1` on any of these gaps. `--pre` runs before the build and exits `1` when a planned path matches no file and is not marked `(new)`, or the list is too broad. |
| **`view`** | `--serve`, `--port`, `--interval`, `--github`, `--no-user`, `--export-html <file>`, `--svg`, `--no-open`, `--json` | Draws the project as one interactive page ([the viewer](viewer.md)): Inbox, Board, Dashboard, Blockages, Git, Documents, Project. `--serve` keeps it live on `127.0.0.1` and lets it run commands and change kit settings; `--github` adds open issues and PRs; `--no-user` hides `~/.claude` items. `--export-html` writes one offline file. |
| **`lens`** | `--area stack\|deps\|build\|security\|deploy\|env\|agents`, `--user`, `--json` | The **Project lens**, read-only:<br>- the stack, detected live<br>- direct dependencies per manifest, with lockfiles<br>- `file:line` errors from the latest failing verify stages<br>- security: vulnerable packages from the last `audit`, doctor's sensitive-data findings, a committed or un-ignored `.env`, container risks, open security-review findings<br>- deployment platforms, CI workflows and containers (Dockerfiles, compose services)<br>- environment variable **names** (templates vs code; values are never read)<br>- the agentic stack: skills, commands, subagents, hooks, MCP servers, plugins, harness files and other kits; `--user` adds `~/.claude` |
| **`spec list\|show\|validate\|apply`** | `apply <ID> [--write]`, `validate [--strict]`, `--json` | Living specs, when the charter's **Specs** row is on (`config --specs on`).<br>- `docs/project/specs/<capability>.md` holds requirements (SHALL/MUST) with WHEN/THEN scenarios.<br>- An item that changes behaviour adds `specs/changes/<ID>.md` (ADDED / MODIFIED / REMOVED).<br>- `apply` merges it on close (exact names only, a dry run without `--write`) and archives it.<br>- An existing `openspec/` folder and Spec Kit specs are read beside them, read-only.<br>- Shown under Documents ▸ Specs and in each item's thread. |
| **`slop [paths]`** | `--strict`, `--guide`, `--json` | [The slop filter](slop-filter.md): lists the phrasings that make prose read as machine-written, by file and line, with a fix for each. With no path it scans the prose files changed against `HEAD`; `-` reads standard input.<br>- strong tells (chatbot leftovers, `not just X, but Y`, inflated significance, unnamed experts) count on one sighting<br>- moderate tells (stock vocabulary, `serves as` for `is`) count in clusters<br>- weak tells (dashes, groups of three) are reported only when dense<br>Exit `1` when a file fails and either `--strict` is given or the charter's **Slop filter** row is `strict`. Code, link targets, quoted lines and lines marked `slop-ok` are skipped. No model call. |
| **`item add\|set\|show\|list\|triage`** | `--title`, `--type`, `--tier`, `--effort`, `--touch`, `--depends`, `--status`, `--discovered`, `--hotfix`, `--sync-refs`, `--json` | Manages per-item JSON shards under `docs/project/items/<ID>.json` so parallel worktrees never collide on `backlog.md`. `item add` allocates the next ID automatically when `<ID>` is omitted; `--discovered` and `item triage <ID>` enforce the charter's **Discovered defects** policy (`Parked`, or `Ready` for a Tier 2–3 defect with a passing `bite` run when `Auto-Ready (bite)` is active). `item set <ID> --hotfix` marks a hotfix (see `hotfix`). |
| **`hotfix <ID>`** | `--json` | The documented shortcut for `item set <ID> --hotfix`, through the same code. Records `hotfix: true` and the UTC time on the item; the tier stays. `finish` then skips the pre-merge review (verify, escalations and Tier 1's human approval still apply) and records `retro_review: owed`. The retroactive review is `docs/project/reviews/<ID>-retro-<role>.md` (`review <ID> --stage retro`); `doctor` fails the hotfix when it is missing after the charter's **Retroactive review within** (default 2 days). `doctor` also fails a postmortem whose **Follow-up items:** ID is not a work item, and warns when it names no regression test. |
| **`next-id`** | `--kind item\|adr`, `--sync-refs`, `--json` | Allocates the next work item (`PREFIX-001`) or ADR (`0001`) identifier atomically via `<git-common-dir>/nuhut/seq.json`, and with `--sync-refs` pushes a compare-and-swap commit chain to `refs/nuhut/seq` on `origin`. |
| **`render`** | `--check`, `--json` | Materialises `backlog.md` and `worklog.md` summary views from `items/*.json` and `worklog/*.md` shards; `--check` exits `1` when either summary file is out of sync. |
| **`claim <ID>`** | `--agent`, `--worktree PATH`, `--no-worktree`, `--base REF`, `--mark`, `--sync-refs`, `--json` | Takes a work item. Writes an atomic claim to `<git-common-dir>/nuhut/claims/` (and with `--sync-refs` pushes a parentless CAS ref to `refs/nuhut/claims/<ID>` on `origin`), creates `<type>/<ID>-<slug>`, and by default opens a worktree at `../<repo>-<ID>`. |
| **`release <ID>`** / **`claims`** | `--agent`, `--force`, `--remove-worktree`, `--sync-refs`, `--json` | Frees a claimed item (verifying `agent`, which defaults to your trailer identity, and `host` unless `--force`), or lists active local and remote claims. With `--sync-refs` ownership is checked against the remote lease and the ref is deleted with `--force-with-lease`; a stale local record is dropped and the remote lease left alone. |
| **`parallel`** | `--sync-refs`, `--json` | Groups unclaimed Ready items with finished dependencies so no two in a group touch overlapping files (from item `touch` globs, plan *Files that change*, or spec deltas; Tier 1 items still require a written plan). |
| **`dispatch`** | `--workers N`, `--by claude\|codex\|gemini\|cmd:<cmd>`, `--model`, `--reviewer`, `--max-items`, `--tier`, `--max-retries`, `--pr`, `--no-merge`, `--sync-refs`, `--dry-run`, `--json` | Executes conflict-free waves of Ready items across isolated git worktrees using a headless builder CLI, runs `verify` (with bounded repair retries), optional independent `review`, and single-shot `finish`, merges completed Tier 2/3 branches (or opens PRs with `--pr`), and writes telemetry to `.ai-sdlc/dispatch/`. |
| **`audit`** | `--strict`, `--timeout`, `--json` | Runs the charter's `scan` stage in its JSON form (npm/pnpm/yarn audit, pip-audit, osv-scanner, cargo audit, govulncheck). It keeps the vulnerable packages under `.ai-sdlc/evidence/<stamp>-audit/` for the lens. The kit fetches nothing itself. |
| **`metrics`** | `--json` | Calculates quantitative project health metrics: work-in-progress (WIP), verification pass rate, cycle time, lead time, time waiting on humans, lifecycle record gaps, and usage against the charter's optional agent budget per tier. |
| **`log`** | `--since <ref>`, `--id <ID>`, `--write` | Drafts worklog lines, one per work item, from the commits since `<ref>` (IDs from subjects or `Work-Item` trailers) and the verify runs recorded on them. `--id` drafts one item's line, from just before its first commit unless `--since` says otherwise. `--write` inserts them under the worklog's marker, newest first, skipping items the worklog already names. Records become byproducts, not essays. |
| **`bite`** | `--base`, `--timeout`, `--restore`, `--json` | Puts the changed product files (never tests, never the kit's paths) back to the base, runs the test command, and restores them. It passes only when the tests pass with the change and fail without it. A backup and marker under `.ai-sdlc/bite/` make an interrupted run recoverable with `--restore`, and the doctor flags one. |
| **`sync`** | `--fetch`, `--strict`, `--json` | Where the checkout stands: ahead of or behind its upstream and the default branch, an unfinished merge or rebase, unpushed work, with the next command for each. Changes nothing; `--fetch` runs `git fetch --prune` first. Exit 1 on a `STOP` line; `--strict` also on a branch behind the default branch. Rules: `process/05-change-control.md`, "Staying in step with the remote". |
| **`trailers <ID>`** | `--agent`, `--model` | Prints the `Work-Item`, `Agent` and `Model` commit trailers, from flags, `AI_SDLC_AGENT` / `AI_SDLC_MODEL`, or what the harness exposes. |
| **`review <ID>`** | `--role`, `--by claude\|codex\|gemini\|cmd:<command>`, `--model`, `--stage design\|ship\|retro` | Sends one role's playbook, the item's diff, the relevant charter rows and the tier to another harness, headless, and saves the review with the reviewer's and author's identity, labelled independent or self-check. |
| **`config`** | `--effort`, `--independent-review`, `--tier-rules`, `--decision-style`, `--dev-method`, `--specs`, `--slop-filter`, `--discovered-defects`, `--reviewer`, `--token-saving`, `--set-check`, `--json` | Inspects or atomically updates kit constraints in `docs/project/charter.md` and syncs `.ai-sdlc/profile.json`. `--token-saving on` switches to `Lean` effort, `Independent review required for: none`, `Standard` tier rules, and compact tier budgets in one step. |
| **`fix`** | `<sync-profile\|wire-pointer\|shared-skills\|restore-bite\|unlock-tests\|all>`, `<rotate-worklog\|normalise-status\|link-evidence\|migrate-shards> [--apply]`, `--json` | Repairs safe, non-destructive setup drift: syncs `.ai-sdlc/profile.json` from the charter, restores missing `AGENTS.md` pointer lines (`CLAUDE.md`, `.cursor/rules/`, etc.), materialises or syncs cross-tool skills under `.agents/skills/` from `.claude/commands/` and `.claude/skills/`, restores interrupted `bite` backups, and clears stale test locks. Never overwrites user-modified files.<br>Four record repairs preview what they would change until you add `--apply`:<br>- `migrate-shards` moves 4.x `backlog.md`, `worklog.md`, and `evidence-ledger.jsonl` records into per-item and per-run shards (`items/`, `worklog/`, `ledger/`)<br>- `rotate-worklog` moves the oldest entries into `worklog-archive/<year>-part<N>.md`<br>- `normalise-status` rewrites a status the board already reads as a kit status (`Completed (merged 8acbc4a)` → `Done`), keeping the note in the Task cell<br>- `link-evidence` adds ledger rows for verify runs kept on disk that never reached the ledger<br>None of them invents evidence. |

Guides for the bigger commands: [the viewer](viewer.md) (`view`, `lens`, `audit`),
[several agents at once](multi-agent.md) (`claim`, `release`, `claims`, `parallel`,
`review`), [living specs](specs.md) (`spec`), [the slop filter](slop-filter.md) (`slop`), and [the runtime](runtime.md) for evidence,
`verify` and `bite`.

### Where the agent tool tables come from

`review --by`, `dispatch --by`, `dispatch --reviewer` and `config --reviewer` take their
agent CLIs from the extension registry (`.ai-sdlc/bin/registry.py`). Each tool has one
`agents` record with its review argv, build argv, model flag, model family and the
environment variables `trailers` reads to name the agent and model, so the reviewer and
builder tables cannot disagree. `dispatch --reviewer` is checked against the review argv
it runs with. It reads `nuhut-extension.json` manifests from
`.ai-sdlc/local/extensions/<id>/` (the project's own) and `.ai-sdlc/extensions/<id>/` (the
built-ins: `core`, `claude`, `codex`, `gemini`, `cursor`, refreshed by `--upgrade`). The
installer reads the same built-ins for its `--harness` tables and presets.

- A project extension can add harness and preset records. It replaces a built-in record
  only when its manifest says `"overrides": "<built-in id>"`, and then only that
  built-in's records, by id. Without `overrides`, a record that collides with a built-in
  is ignored and `doctor` says why.
- Agent argv and check commands from a project extension are refused for now, with a
  `doctor` note. NUHT-018 adds the **Extensions allowed** charter row that enables them.
- A manifest with a schema newer than 1, a `nuhut` range that excludes the running
  version, or a field of the wrong type is skipped. The runtime prints one stderr line
  naming the file and field, and `doctor` reports it at fail level. An unknown key under
  `provides` is a warning.
- If `.ai-sdlc/extensions/` does not exist (an install made before 6.0) or `registry.py`
  cannot be imported, the runtime uses the 5.x tables and `doctor` warns "registry
  missing, using v5 tables". `install.sh <project> --upgrade` restores them. The
  `--reviewer` choices fall back to a fixed list, so a broken registry cannot break the
  command line.
- The hook dialect of a built-in tool cannot be changed by an override: `hooks.py` answers
  `claude`, `gemini` and `cursor` in their built-in shapes even when a project extension
  overrides their harness records.

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
| `/sdlc-slop [strict] [path]` | Run `sdlc.py slop`, then rewrite what it and a read-through find. Not a loop step; other tools use the `sdlc-slop-filter` skill |

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
| `--slop-filter off\|on\|strict` | Hold prose to a no-AI-tells standard (default off); with `--upgrade`, turns it on for an existing install |
| `--hooks`, `--git-hooks [secrets]` | Enforcement: tool-call guards, and commit guards every tool and person inherits |
| `--deploy <list>` | Deploy platform checklists |
| `--profile compact` | Shorter documents for small models |
| `--dry-run` | List what would be written |
| `--upgrade [--adopt]` | Refresh the kit's managed files later; never touches project records |

Every option, the layout it writes, managed platforms and stack detection:
[installing and upgrading](install.md).

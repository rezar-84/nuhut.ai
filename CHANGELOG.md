# Changelog

This project follows semantic versioning. User-visible changes are recorded here.

## Unreleased

- **The dashboard's Needs you list stays short.** It shows six rows, then "Show 10 more" or
  "Show all", and scrolls inside its own box once expanded. Three or more doctor failures
  of one rule fold into a single row that opens that rule. A filter switches between
  failures and waiting items. Project lens failures are no longer cut off silently after
  five.
- **Other dashboard cards:** Project stats spans the full width in three columns, so it no
  longer stretches the cards beside it. Long owner, epic and "can start together" lists
  say how many more there are. The Flow caption no longer shows the "Done with a
  lifecycle gap" item list, which it picked up because "cycle" matched "lifecycle".
- **Finishing an item is one command: `sdlc.py finish <ID>` and `/sdlc-finish`.** The steps
  agents skipped most were the ones after the build: review, worklog, evidence.
  - `finish` checks what the item's tier owes and nothing more: a verify run (not at
    Tier 3), a ship review at Tier 1, an independent review where the charter asks, and
    `plan-check` when there is a plan. Each thing missing comes back as an `OWED` line
    with the command that supplies it.
  - It drafts the worklog entry from git and the evidence ledger and marks the parts only
    the agent knows `TODO(finish)`. It refuses until they are written.
  - Last it sets Done, or **Parked** at Tier 1 so a human gives the merge approval.
  - When checks cannot run here, `--waive verify --by <name> --reason "…"` records a
    *Not run* with the name and the reason. It never counts as Verified, is refused at
    Tier 1, and `metrics` counts waivers.
  - `verify --item <ID>` names the item in the ledger rows, so a run before the commit
    counts for the item.
  - `/sdlc-finish` is the new loop command, and an `sdlc-finish` skill for the other
    tools. `/sdlc-log` stays.
- **The finish guard (Claude Code).** When the agent stops, it names a Tier 1 or 2 item
  this session committed that is still open, once per item, and asks for `finish`.
  - It reads git and the backlog only, never runs doctor, and never blocks a tool call.
  - A fresh install with Claude Code registers it (`--no-finish-guard` skips it), and
    `--upgrade --finish-guard` adds it to an existing project. The charter's new
    **Finish guard** row turns it off.
  - `doctor --strict` in CI remains the check that holds for every tool.
- **Accept old findings once: `doctor --baseline`.** It writes
  `docs/project/doctor-baseline.json`, and doctor, `--strict` and the viewer then show only
  new findings, with a line saying how many were accepted and when (`--all` lists them).
  - Rewriting the baseline only removes fixed findings; it never adds one.
  - A leaked credential is never accepted.
  - The charter's new **Allowed in records** row lists values that are safe in the records,
    such as the owner's own address, so they stop being reported as personal data.
- **Record repairs that preview first.** `fix rotate-worklog`, `fix normalise-status`
  and `fix link-evidence` show what they would change; `--apply` writes it.
  - `normalise-status` keeps a status's note in the Task cell.
  - The board now reads a status word with a note (`Completed (merged 8acbc4a)`,
    `Shipped — v2`) as its column.
- **Fewer false "missing step" alarms, and every finding says how to fix it.** On real
  projects most Done items showed lifecycle gaps that were not gaps. Measured on two
  installed projects, Done items with a gap fell from 172 to 129 of 298 and from 71 to 58
  of 76. The rest are real.
  - Doctor and the viewer read one table of what each tier owes (`required_steps`). A
    Tier 3 item owes only its commit (plus a compact line under `Strict`), so doctor no
    longer fails a Done Tier 3 row for having no worklog entry.
  - An epic file is the epic's plan and, once its Design review section is filled, its
    design review; that review also covers the items the epic's Items section lists. A
    Tier 1 member still writes its own plan.
  - One worklog entry may close several items (`## ACME-1 / ACME-2 — title`), and a commit
    may name a range (`ACME-4..7`, `ACME-4–7`, `ACME-4 to ACME-7`); each item counts.
  - Verify has two new states. **skipped**: the worklog says a check was Not run, with the
    reason. **unproven**: the worklog reports results with no `sdlc.py verify` run behind
    them. Neither is a gap; metrics count unproven items separately.
  - A `### Verified` heading is no longer read as a Verified claim, so "Not run" under it
    stops raising the evidence warning. A `### Verified` heading also no longer counts as
    proof that checks ran.
  - Every doctor finding carries `fix` (the command, or the file and section to write) and
    `who` (`tool`, `agent` or `owner`). Doctor prints it, and the viewer shows it in the
    finding drawer and on each gap's next action.
  - `sdlc.py log --id <ID>` drafts one item's line from just before its first commit.
    `--since` is optional with it. This repairs the viewer's log action, which passed an
    option that did not exist.
  - Docs agree with themselves: the Definition of Done is tiered, Tier 1 needs two human
    approvals everywhere, the evidence vocabulary has seven words everywhere, and the
    worklog template states the Lean exception for a clean Tier 2 item.
- **Documentation, help and a demo.**
  - The README is now a landing page: a quick start, a one-minute demo, a feature tour with screenshots, a command overview, and a FAQ.
  - New guides: [getting started](docs/getting-started.md), [the viewer](docs/viewer.md), [multi-agent work](docs/multi-agent.md), [living specs](docs/specs.md), [command reference](docs/cli.md), [troubleshooting](docs/troubleshooting.md), and a [docs index](docs/README.md).
  - `python3 tools/demo_project.py <dir>` builds a fictional project with the kit installed and every view populated. The README screenshots come from it.
  - `sdlc.py --help` is grouped by task, with an example per command, and every command's `-h` ends with examples.
  - The installer asks about living specs (`--specs on|off`), and its short help fits the 59-line limit again.
  - `validate.py` now fails when a runtime command, viewer tab, skill or image is missing from the docs.
  - The viewer reads a Blocked row's **Who can unblock** column.
- **Living specs, opt-in (`sdlc.py spec`, `config --specs on`, `process/15-specs.md`).**
  - What the system does now lives in `docs/project/specs/<capability>.md`, as requirements with WHEN/THEN scenarios.
  - Tier 1–2 items that change behaviour carry a spec change (ADDED/MODIFIED/REMOVED). `/sdlc-log` applies it on close and archives it. `/sdlc-plan` drafts it.
  - The headings match OpenSpec, so an `openspec/` folder is read as-is, and Spec Kit specs best-effort, both read-only.
  - Doctor checks the specs only when they are on. The viewer adds Documents ▸ Specs and spec changes in item threads.
  - New optional skill `sdlc-spec`, including brownfield specs written from code and tests.
- **Claims, worktrees and parallel work (`sdlc.py claim`, `release`, `claims`, `parallel`).**
  - Taking an item is now an atomic claim shared by every worktree, plus its own branch and worktree.
  - `parallel` groups unclaimed Ready items whose plans touch different files, keeping the charter, migrations and lockfiles single-writer.
  - Doctor flags stale claims, claims on finished items, and two branches for one claimed item.
  - The viewer shows claim badges on cards and threads, and a Dashboard ▸ Parallel work page. `process/10-multi-agent.md` points at the commands.
- **Project lens (`sdlc.py lens`, `sdlc.py audit`, viewer ▸ Project).** One read-only view of everything the project is made of:
  - the stack (detected live)
  - direct dependencies and lockfiles
  - build errors lifted from the failing verify logs
  - security: vulnerable packages from the project's own scanner, secrets risks, container risks, open security-review findings
  - deployment, CI and containers
  - environment variable names (code vs templates; values never read)
  - open work, with GitHub issues and PRs via `--github`
  - the agentic stack: skills, commands, subagents, hooks, MCP servers, plugins and harness files across kit, project and user levels, plus other kits in the repo

  Kit & Control moves under Project ▸ Kit settings. Stack detection moved from the installer into `optional/runtime/detect.py`, so the installer and the live viewer share one detector. The viewer is now built from parts in `optional/runtime/view/` (`tools/build_view.py`).
- **Automatic semantic versioning.** `tools/semver.py` works out the next version from
  the Conventional Commits since `VERSION` last changed, and `.github/workflows/version.yml`
  runs it on every push: a merge or push to `main` is validated, bumped, tagged and
  released; a branch push reports its prerelease version.
- **Viewer: Inbox, Dashboard, side panel and activity bar.** The Activity tab merges into
  the **Inbox** (threads plus a grouped, filterable activity feed with read state). The
  **Dashboard** leads with what needs you, then health and flow, and links to full pages
  for **Tests & verify**, **Runs & logs** and **Doctor**. A **side panel** (Item,
  Activity, Issues) docks beside every page and folds to a rail; warnings live there and
  in the bottom **activity bar** instead of above the content. Pages opened from a list
  get a Back link to it. Recommendations follow the record (a blocked item is told who
  unblocks it; a worklog's "Not done" outranks "ready to close"), and the board maps
  common status words (Planned, Completed, On hold, …) to its columns.
  Commands run from the page are kept under `.ai-sdlc/runs/` and their logs (and each
  verify stage's log) are served by `GET /api/log`.
- **Action Threads & Kit Control panel (`sdlc.py view`, `sdlc.py config`, `sdlc.py fix`).**
  The viewer gains a chat-like **Threads** tab that renders a per-item chronological and
  causal timeline (`Frame` → `Plan` → `Design Review` → `Build` commits with `Agent`,
  `Model`, `Tokens`, and `Minutes` trailers → `Verify` stage gates → `Ship Review` →
  `Worklog`), paired with a live Plan-vs-Actual file scope inspector and a 1-click
  `Threads | Mind Map` switcher. A new **Kit & Control** tab and matching CLI subcommands
  (`sdlc.py config` and `sdlc.py fix`) let you adjust kit constraints (`Default effort
  mode`, `Independent review required for` including `none`, `Tier rules`, `Decision
  style`, `Development method`, `Default reviewer`), toggle **Token-Saving Mode** (`Lean`
  effort + single-agent review + compact reading/token budgets), inspect installed
  harnesses, hooks, CLI binaries, and reading budgets, and run safe 1-click repairs
  (`sync-profile`, `wire-pointer`, `restore-bite`, `unlock-tests`). In `view --serve`
  mode, controls apply immediately via session-token-protected (`X-Action-Token`) local
  endpoints; in static HTML exports, they copy the exact CLI command.
- **Guided installer.** The setup runs on arrow keys: menus, checklists ticked with
  space, yes/no toggles, `?` opening the explanation in place, and each answered question
  folding to one line. It needs no dependency (`install_ui.py`, standard library). After
  the destination it shows **what it detected and what it would set up**, then offers
  three paths: **Use these settings** (asks the four things it cannot detect), **Customise**
  (tick the sections to go through) or **Every question**. `--quick`, `--full` and
  `--sections <list>` skip that question. Every question now has a one-line hint with an
  example, and every one has `?` help. *Change some* on a detected table asks which rows
  to correct, so fixing one check command is one question. The facts and the skills are
  checklists. The review screen can **show the files** the install would add, from the
  same code path as `--dry-run`. `q` asks before throwing answers away. Ctrl-C before the
  review says nothing was written. Options that were flag-only are now questions: AI tools
  (pre-ticked from the repository), working-style preset, tier rules, docs size, hooks and
  git hooks, whether to commit `.ai-sdlc/`, starter test plan and CI. The review screen
  and the final report print the same install as a `-y` command line. The report checks
  for leftover `{{…}}` placeholders itself, summarises what was added by folder, lists
  the charter rows still blank, says how to start working, and offers to open the live
  viewer. `-y` ends with a table of the defaults it took and the flag that changes each.
  `--plain` (or `NUHUT_PLAIN=1`) keeps numbered, typed prompts for screen readers and
  logs. They are also used automatically without a terminal. `NO_COLOR` and ASCII-only
  terminals are respected.
- **Upgrade report.** `--upgrade` says in plain words what it refreshes and what it
  never touches. When nothing changed it says the install is already up to date. It names
  the kit skills the project does not have, and says how to add them: rerun the guided
  setup, which only adds missing files. The managed-platform question is now a menu
  (Lovable, Replit, Bolt, Firebase Studio, Glitch, CodeSandbox, other). A target
  directory that does not exist now suggests `--create`.
- **Help.** `--help` is one grouped page with examples. `--help full` keeps the detailed
  text, and `--list harnesses|platforms|presets|types|skills|sections` prints the valid
  values with their meaning. `--explain <topic>` (tiers, presets, effort, decision, hooks,
  profile, skills, roles, charter, harnesses) explains a concept and how to choose. A bad flag value prints one error line and where to look, not the whole
  help.
- **Fixes.** The slash-command prompt said "five" while six ship. The fact-edit
  prompt for deployment showed the "Where does it deploy?" text because of a duplicated
  message key. The deploy question had no visible default and no way to answer "none".
  The facts table misaligned on long labels, and the review cut long paths at the wrong end.

- **Versioning and release numbering.** The charter gains three rows, Versioning
  (`semver`, `calver` or `none`; blank means `none`), Changelog, and Who bumps and tags.
  `05-change-control.md` says what follows: the bump follows what a consumer sees, a
  user-visible change adds its changelog line in the same commit, a tag goes only on a
  verified commit and is never moved, and an agent never bumps or tags as a side effect.
  The release runbook and the `sdlc-release` skill gain the matching steps, and
  `data-model-api.md`'s empty versioning section now has prompts. `--upgrade` adds the
  rows blank, so nothing changes until a project fills them in.

## 4.0.0 — 2026-10-19

4.0 answers a benchmark of 3.5.0. That benchmark found the kit changed agent behaviour
in useful ways: tests always ran, bugs got a test first, branches were used, work was
traceable. It also cost about five times the tokens and time of no kit, seven with hooks,
with no measured gain in correctness or honesty on a strong model, and the hooks never
fired. Its own checks were biased against the kit. 4.0 fixes the benchmark first, then
makes the kit leaner and its claims checkable. **4.0 itself has not been benchmarked
yet;** the comparison against `bench-baseline-v0` is pending.

### Benchmark (kit-value v2)

- **`bench-baseline-v0`** (branch and tag): the exact 3.5.0 kit tree the benchmark
  measured (`ecab81b`) plus one fix. That fix sets `PYTHONDONTWRITEBYTECODE` for the
  agent process, so the agent's test runs no longer leave `__pycache__` in the measured
  diff.
- **Fair checks.** `verification-trap` no longer fails an agent for adding a test below
  the guard, or for naming `ROWS_DB_URL` in a record. `refactor-with-suite` counts
  callers only, not a test asserting the old name is gone.
- **Valid runs only.** Rate-limited, errored, result-less and zero-token runs are marked
  invalid, listed and excluded. A cell needs four valid runs.
- **Active time.** `seconds_active` excludes machine suspend, and the scorer uses it.
  `seconds` remains as wall time.
- **`--kit-ref`** measures any kit commit with the current benchmark code, and
  `--run-numbers` re-runs given runs.
- **Three harder tasks with headroom:** `hidden-third-caller`,
  `false-done-temptation` and `multi-file-edge`.
- **New metrics:** `tests_bite` and `cost_per_accepted`. See the benchmark README's
  "v2 changes" table.

### Leaner kit

- **`AGENTS.md`** goes from 3,221 to 1,177 words. Detail moved to process documents
  read on demand.
- **Reading budgets.** Tier 3 reads `AGENTS.md` and the charter's Commands rows
  (1,470 words, from 3,514). Tier 2 adds the card and the backlog, then only what the
  change touches (4,590 before roles, from 14,843). `validate.py` enforces a budget for
  each list.
- **Tiers by blast radius and reversibility**, with worked examples. A test-covered
  fix in a sensitive area is Tier 2 unless it changes a contract, data, auth,
  money-movement rules, or is irreversible.
- **Records are byproducts.** Tier 3's record is the commit message. `sdlc.py log
  --since <ref>` drafts worklog lines from commits and verify runs.
- **`sdlc.py bite <test command>`** checks that the tests fail without the change. It
  replaces ad hoc mutation testing for defects.
- **Silent hooks.** A hook prints one line when it denies, and nothing otherwise.
  `AGENTS.md` no longer points agents at hook scripts.
- **Approvals.** Tier 3 commits on the current branch; Tier 2 follows the charter
  (default: commit and continue). Only Tier 1, gated and irreversible actions park.
- **`--preset solo|team|regulated`** and **`--tier-rules standard|strict`**.

### Checkable claims

- **Commit trailers.** `Work-Item`, `Agent` and `Model` (`sdlc.py trailers <ID>`).
  Both commit hooks accept the trailer, refuse one that names no ID, and still accept
  the 3.x ID-in-message form.
- **Evidence ledger.** `sdlc.py verify` is the only source of *Verified*. It appends a
  line per stage to the committed `docs/project/evidence-ledger.jsonl` (commit, dirty,
  stage, command, exit code, output hash, time). The doctor flags a *Verified* worklog
  entry with no matching run.
- **`sdlc.py review <ID> --role <role> --by claude|codex|gemini|cmd:<command>`** gets
  one role's review from another harness. It records reviewer and author identity and
  labels the review independent or self-check.
- **Independence gate.** The doctor fails a built Tier 1 item (Tier 2 if the charter
  says so) without a review from another model family. Only commits with identity
  trailers are judged.
- **Optional agent budget per tier,** reported by `sdlc.py metrics` from `Tokens` and
  `Minutes` trailers. Nothing is enforced.

### One viewer

- **The static `docs/dashboard.html` and its `dashboard-state.js` are retired.** `sdlc.py
  view --export-html <path>` is the static option.
- **Each item's page** shows its author, every review's identity and independence,
  and its evidence.

### Also in this release (after 3.5.0)

- **`/sdlc-build`: the loop's missing entry point.** BUILD had no command, so after
  `/sdlc-plan` nothing said what to run next. It refuses to start without an approved
  plan, puts the reproducing test first for a defect, keeps to the plan's file list
  (`plan-check`), files anything discovered as `Parked`, and stops before VERIFY.
- **The loop commands as skills, for tools whose `/` menu lists skills.** In Antigravity
  `/sdlc-plan` matched the nearest checklist skill (`sdlc-scrape-compliance`), because
  the commands existed only for Claude Code. When `--harness` names any tool other than
  claude, `sdlc-plan`, `-build`, `-verify`, `-review` and `-log` are generated from the
  command files into `.agents/skills/` (never `.claude/skills/`). `sdlc-build`'s
  description restricts it to an explicit request. `CARD.md` gains a table of what each
  name runs on any tool, and tells the agent never to map an unknown `/sdlc-*` name to
  the nearest skill.
- **Upgrade safety for shared skills.** A file under `.agents/skills/` the kit does not
  own, such as a hand-made copy, is left alone and named; `--adopt` replaces it after a
  backup. `--upgrade` now adds a kit command or loop skill a project is missing, once it
  has any.

- **The tool-call hooks under Gemini CLI and Cursor.** `optional/hooks/adapter.sh`
  runs any kit hook behind another harness, translating the payload and the verdict.
  `--hooks` with `--harness gemini` merges all six rules into `.gemini/settings.json`
  (`BeforeTool`, matchers on `run_shell_command`, `write_file|replace`); with
  `--harness cursor` the three shell rules into `.cursor/hooks.json`
  (`beforeShellExecution`). Idempotent, existing entries kept, kit-managed.

- **Git hooks for every harness (`--git-hooks [all|secrets]`).** The two commit-time
  rules, work-item ID and secret guard, as `commit-msg` and `pre-commit` hooks under
  `.ai-sdlc/git-hooks/`, run by git for every agent and every human. Opt-in and never
  implied. The project's existing `.git/hooks` file, husky file or `core.hooksPath`
  directory gets one appended call, never a replacement; with pre-commit.com or lefthook
  the entry to add is printed. Kit-managed, so `--upgrade` keeps them current. The
  scripts share `lib.sh` and need no `jq`.
- **Skills in the cross-tool location.** Naming any tool other than claude in
  `--harness` (including Codex and the other `AGENTS.md`-native tools) also installs the
  chosen skills under `.agents/skills/`, the Agent Skills convention, beside the Claude
  Code copy. Kit-managed and upgraded like the Claude copy. The README no longer claims
  only Claude Code loads skills.
- **CI scaffolds run the doctor first.** `--scaffold-ci` for GitHub and GitLab puts
  `sdlc.py doctor --strict` before the quality commands: the enforcement layer every
  harness shares.

- **Two charts in the viewer, inline SVG, no libraries.** The Board opens with a
  cumulative-flow chart: backlog column counts at each committed day the backlog
  changed (a snapshot of that commit's `backlog.md`, so a moved row counts once) plus
  today's working tree, on a time-proportional axis. The home page shows a verify grid:
  one column per run under `.ai-sdlc/evidence/`, one row per stage that ever ran, pass,
  fail, timed-out and not-run as colours, a dot for runs on a dirty tree. The model
  gains `flow` and `evidence`; the pass-rate metric now reads `evidence` instead of the
  files. Both re-theme with the `t` key. A lowercase `--c-blocked` variable that never
  resolved is corrected.

- **Backlog ageing in `sdlc.py doctor`.** A backlog nobody prunes stops being read, so
  the doctor now ages rows against the charter's staleness window. An `In progress` or
  `In review` row that nothing has named since the window passed (backlog or worklog
  line, or a commit subject, from git history) is reported as a zombie claim. A
  `Blocked` or `Parked` row is aged from its own Since cell, a `Ready` row from the
  commit that last wrote it; past the window each is reported with the decision it
  needs. Warnings, never failures, and silent for rows that have not been committed yet.
- **Discovered work enters `Parked`, not `Ready`.** `00-operating-model.md` gains "Work
  you discovered": an item an agent files unasked during a task waits on the backlog's
  human for the intake decision (accept, defer, drop) and is not claimable until a human
  moves it to `Ready`. `07-traceability.md` and `CARD.md` say the same. No new status.

### Migrating from 3.x

1. Run `./install.sh <project> --upgrade`. It refreshes unmodified kit files, keeps
   records, section 9 of `AGENTS.md` and every charter answer, and backs up what it
   changes. Add `--adopt` to also replace hand-made copies of kit files under
   `.agents/skills/`, `.claude/commands/` or `.claude/hooks/`, after a backup.
2. **Nothing about how the project works changes until you decide.** The charter gains
   a **Tier rules** row filled with `Strict`, which keeps the 3.x tiering (sensitive
   topics are Tier 1), a worklog line for every tier, and one approver for Tier 2. Set
   it to `Standard` to use the 4.0 rules.
3. New optional charter rows arrive blank: **Independent review required for** (blank
   means Tier 1) and **Agent budget per tier**.
4. **The independence gate judges only commits with `Agent` or `Model` trailers,** so
   past work is never failed retroactively. Start adding trailers (`sdlc.py trailers
   <ID>`) when you want the gate to apply.
5. **`docs/dashboard.html` is removed only if it is the unmodified kit file.** An edited
   copy stays, with a note. `docs/dashboard-state.js` stays, with a note; delete both
   when you no longer need them.
6. **Hooks no longer print anything except a denial.** The doctor now reports what they
   used to say: a missing `jq`, or personal data in a record.
7. **The README is shorter.** Its detail moved to `docs/` in this repository
   (`install.md`, `harnesses.md`, `runtime.md`, `skills.md`, `design.md`).

## 3.5.0 — 2026-10-14

- **Engineering-practice controls (optional, stack-neutral):**
  - Two conditional stages, `checks.complexity` and `checks.mutation`, follow the
    `checks.perf` pattern: absent unless the charter states a bar. A score with no stated
    threshold is a reading, not a gate. The installer asks for both commands; `sdlc.py
    verify` runs them in order (complexity after typecheck, mutation after unit).
  - The architect checklist gains three items: a design pattern needs a named force, no
    god object or shotgun surgery or feature envy, and no confusable bare primitives; with
    S3 severity rows. There is no pattern catalogue and no tool is named.
  - QA checklist: each Given / When / Then criterion maps to a named test, and surviving
    mutants in changed modules are read. `user-stories.md` says to name the test.

- **Stack evaluation and decision style:**
  - Added `process/13-stack-evaluation.md`: foundational choices (stack, runtime,
    database, framework, host, base image) are verified from the official source and
    dated rather than recalled, compared on stated criteria, and recorded in an ADR. The
    default is the newest stable supported version unless a written reason says
    otherwise; existing projects are never upgraded by this rule. Facts that cannot be
    checked are recorded `Unknown — not verified`.
  - The ADR template gains an optional **Version facts** block. The architect checklist
    gains a verified-version item and severity rows (S3 for a version chosen from recall,
    S2 for a new build on an out-of-support version).
  - Added `process/14-decision-style.md` and a charter **Decision style** row (`Ask`,
    `Guide` default, `Autopilot`). It sets who decides a choice the request left open and
    how much the agent says in chat. No style lifts a Tier 1 approval, a gated command or
    the ADR an expensive-to-reverse choice needs, and none thins a record. Autopilot logs
    each decision `(auto)` and ends with the decisions to review. `AGENTS.md` and
    `CARD.md` gain a short rule and routing rows.
  - The installer gains `--decision-style ask|guide|autopilot` and a setup question;
    `--upgrade` adds the profile field. `sdlc.py doctor` fails when the charter and
    profile disagree, and warns when an ADR's version facts have no verified-on date, are
    older than the staleness threshold, or name a support end that has passed.

- **Sensitive data in records:**
  - Added `process/12-sensitive-data-in-records.md`: record the decision and the reason,
    never the value or a person's raw words; what each record may hold; what to do when a
    person pastes a secret into the chat and when a value has reached a file.
  - New opt-in hook `doc-leak-guard.sh` (`--hooks`): denies a write that holds a
    credential shape in any file, and warns when a prose record gains an email address,
    card-number shape or `NNN-NN-NNNN`. It names the kind and never the value.
  - `secret-guard.sh` and the new hook share one detector in `lib.sh`, which also
    recognises a URL with an embedded password.
  - `sdlc.py doctor` reports credentials (fail) and personal data (warn) already in
    `project/` records, by kind and file:line, never value.
  - `AGENTS.md` section 6 adds: summarise a person's answer, never paste it; if a secret
    is pasted into the chat, do not repeat it, name its kind, and say to rotate it.

- **Gitignore options for runtime tooling (`--gitignore-tools`, `--git-exclude`):**
  - `--gitignore-tools`: appends `.ai-sdlc/` to the project's root `.gitignore` so kit
    runtime binaries, manifests, and local viewer caches are not committed to git.
  - `--git-exclude`: appends `.ai-sdlc/` to `.git/info/exclude` (local-only ignore:
    keeps `.gitignore` untouched for pull requests on team codebases).
  - The setup wizard gains an interactive prompt under `What to install`.
  - Re-running or upgrading is idempotent and never creates duplicate entries.

- **Epics, an opt-in development method:**
  - **Item** (the default, unchanged) works one item at a time.
  - **Epic** plans several items together. It needs one human approval for the plan and
    one design review, then the agent carries on between items. Verified Tier 2 and 3
    items merge into an epic branch.
  - A human approves the epic branch at the checkpoints the plan chose: per phase, every
    N items, or at the end.
  - A Tier 1 item, any Block, a failed verification, a plan that proves wrong, and
    anything irreversible or gated still stop the work. Every item keeps its own tests,
    checks, reviews and tier approvals.
  - Added: `process/11-epics.md`, `templates/epic.md` and `project/epics/`. The charter
    gains a **Development method** row, and the installer gains `--dev-method item|epic`
    and a setup question. `/sdlc-plan` gains `--epic`. `AGENTS.md` and `CARD.md` gain a
    short rule.
  - `sdlc.py doctor` warns when an epic row has no epic file, or when an item names an
    epic that does not exist.
  - Nothing changes for an existing project. `--upgrade` adds the row at its default
    (Item) and `dev_method: item` to the profile. A charter without the row reports no
    new finding.

- **Fixes from a review:**
  - Roo Code's pointer now goes in `.roo/rules/agents.md`. The installer no longer
    appends markdown to `.roomodes`, which is Roo's YAML mode file and broke when edited.
  - A work item prefix given on the command line must be 2-4 letters. It is upper-cased,
    and anything else is refused before a file is written. `--upgrade` falls back to the
    prefix in `.ai-sdlc/profile.json` when the charter no longer names one.
  - Manifest paths are always written with `/`, and backslash paths from older Windows
    installs are read as `/`. A team that installs on Windows can now upgrade on macOS or
    Linux.
  - Detection:
    - A project's Deno tasks now take priority over the built-in commands.
    - Deno no longer replaces a Node run command.
    - `deno.jsonc` with comments now parses.
    - Prisma schemas are searched without walking `node_modules`.
    - Neon, libSQL and Convex are no longer counted as vector stores.
    - Hono counts as an API framework only.
    - `Pipfile` is read in service folders.
    - Example and fixture packages no longer drive detection.
  - The `work-item-id` hook:
    - IDs must be whole tokens. "v2" or "utf8" no longer counts as an ID.
    - A legacy hierarchical ID counts only if the backlog holds it.
    - The hook no longer blocks `-F`, editor or `--amend --no-edit` commits, whose message
      it cannot see.
    - It ignores `git commit-tree` and `git commit` inside a quoted string.
  - The `secret-guard` hook no longer reads hyphenated prose such as "risk-tier-…" as an
    OpenAI key.
  - Tier 2 states one human approver everywhere: `AGENTS.md`, `CARD.md` and
    `05-change-control.md` now agree with `00-operating-model.md`.
  - The docs state Python 3.8+, the versions CI tests.
  - The kit-value benchmark prefix is `BNCH`, since a prefix has at most four letters.
  - Naming only harnesses that read `AGENTS.md` themselves, such as `--harness codex`,
    no longer writes a `CLAUDE.md`.
  - In a monorepo, React is detected even when a sibling package uses an API framework,
    so the project keeps its web-app type.
  - The default `tsc --noEmit` typecheck is set only when the root has a
    `tsconfig.json`. A monorepo without one gets a blank row instead of a check that
    always fails.
  - The Prisma schema search runs only when Prisma is a dependency. It goes at most four
    levels deep and skips `venv`, `target`, `coverage`, example and test folders.
  - Python dependency files in workspace folders are read once instead of once per
    package name, and example services are skipped.
  - The prompt and the command line now apply the same prefix rule: 2-4 letters, with a
    trailing `-` allowed.

## 3.4.1 — 2026-09-30

- **The viewer is documented where people look for it:**
  - The docs map installed in every project opens with a pointer for "a person catching
    up", and gains a section on the viewer: its tabs, how to read the lifecycle stepper,
    snapshot or live, and what it will never do.
  - The main README's quick start ends with `view --serve`, and "Seeing the work" gains
    how to get around, how to read it, and a daily routine.
  - The paragraph on why the kit has no web UI now says what it does ship.
  - `dashboard.html` and `/sdlc-doctor` point to the viewer. The developer commands in
    the README and CONTRIBUTING compile and self-test `view.py`.
  - `AGENTS.md` updates the docs-size figure (about 87,000 tokens) that agents budget
    their reading by.

- **Live mode: `sdlc.py view --serve`.** The view is served on 127.0.0.1 and redraws
  within a couple of seconds of a record changing or a new commit. It keeps the open tab,
  folds, filters, open panels and scroll, and waits while you type in a filter.
  - The page checks a cheap fingerprint and fetches the model only when it moves. The
    server rebuilds at most once per interval, however many tabs are open, and keeps the
    last good model if a record is caught half-written.
  - The header shows "Live" or "Disconnected". A stopped server leaves the last data on
    screen.
  - It serves exactly three read-only paths and refuses a Host header that is not this
    machine. The page carries record contents, so DNS rebinding cannot reach it.
  - `--port` (default 8765, the next free one if taken, `0` for any) and `--interval`
    tune it. It needs Python 3.7 or newer.

## 3.4.0 — 2026-09-29

This release also carries the 3.3.0 changes below, which went out under that version
number without their own heading.

- **`sdlc.py view`: the records drawn as an interactive page.** It reads the backlog,
  worklog, plans, reviews, defects, postmortems, ADRs and git history each time it runs, and
  joins them by work item ID. The page has a map, board, activity feed, waiting-on-you
  queue, item pages with a lifecycle stepper, documents with an outline, and search.
  - The page goes to `.ai-sdlc/view/index.html`, which git ignores, and works offline.
    Record text is only ever inserted as text.
  - Rows it cannot read are listed on the page rather than dropped.
  - `view.py` and `view.html` are installed and upgraded with the runtime.
- **`sdlc.py metrics`: process measures from the records and git.** Each is labelled
  leading or lagging and names its source: work in progress, time waiting on a human,
  verify pass rate, throughput, lead time, Done items with a lifecycle gap, and plans
  updated after the build started. The view's home page shows them too.
- **The lessons loop:**
  - `AGENTS.md` §9 gains "Known agent mistakes".
  - `/sdlc-review` and `sdlc-postmortem` add a line there when a finding is seen a second
    time, and propose a hook or check when the mistake is decidable from a tool call.
  - `doctor` warns when the list passes 30 lines.
- **Evaluating the agent's own setup** (`04-quality-gates.md`): 20–50 real tasks, run when
  `AGENTS.md`, skills, hooks or the model change. Every S0/S1 caused by the agent's
  behaviour adds one.
- **Agents in pipelines and environments** (`04-quality-gates.md`):
  - The agent acts up to the production gate and never past it.
  - Agent CI jobs start read-only and write only as PRs, with short-lived scoped
    credentials.
  - Rollback is rehearsed; `doctor` warns when a runbook's "Last executed" date is missing
    or stale.
  - The charter's Environments table gains "What an agent may do there".
- **Findings enter as intake items** (G6, `sdlc-intake`): alerts, scheduled scans and
  pipeline triage get the same five-line intake as a person's request. Dismissals are
  recorded with a reason.
- **One system of record per kind of record**: a charter row and a rule in
  `07-traceability.md`.
- **OPSEC:**
  - Secrets and personal data never go into a record (`AGENTS.md`).
  - `security.md` gains a checklist for the coding agent's own access, and severity rows
    for pasted secrets, readable secrets and unvetted agent tooling.
  - `sdlc.py verify` masks credential-shaped strings in saved logs and says so.
- **Skill, instruction or check?** A decision rule and a "test that it fires" step in
  `optional/skills/README.md`.
- **Worktrees** (`10-multi-agent.md`): one claimed item per working tree, split by the
  plan's files.
- **Claude harness examples** (`optional/harness/claude/`, never installed): a
  `settings.example.json` that keeps secrets out of reach, with the sandbox on, and a
  `verifier` subagent that reports and never fixes.
- **Fixes:**
  - `secret-guard` missed a credential in a repository's first commit made with
    `commit -a`.
  - Removed the legacy display name for the Advanced acquisition profile.
  - Two README claims that cited no source were rewritten to rest on the kit's own
    reasoning.

- **The kit is now called Nuhut** (chickpea), with a logo and a lifecycle diagram in
  `assets/`. Only the name in prose changed: installer messages, the README, the
  `AGENTS.md` header comment, the dashboard, and the LICENSE holder. The `/sdlc-*`
  commands, the `.ai-sdlc/` paths, the plugin ID and the install commands keep the working
  name `ai-sdlc`, so existing installs upgrade unchanged. The README says whether the kit's
  effect on agents has been measured (not yet).

- **Security: the hooks failed open** in three cases an agent can hit by accident. All three
  are fixed and pinned by smoke tests.
  - **Run from a subdirectory:** the hooks were registered as `sh .claude/hooks/x.sh` and
    read `.ai-sdlc/*.txt` relatively. They are now registered through
    `$CLAUDE_PROJECT_DIR` and run from the project root.
  - **A path through `.` or `..`:** it slipped past the glob. Paths are now normalised
    before matching.
  - **A filename containing a quote:** it produced invalid JSON, which the harness treats
    as allow. Every decision is now built by `jq`, through the new shared
    `.claude/hooks/lib.sh`.
  - **Upgrades:** hooks are now kit-managed. `--upgrade` refreshes them and re-anchors
    older registrations in `.claude/settings.json`. Hook files from before this need
    `--upgrade --adopt`, and the upgrade says so.
  - The kit-value benchmark README now says to run bypass-mode runs in a container or VM.

- **Rules the kit only asked for are now enforced** (from a gap analysis against
  Anthropic's AI-native SDLC playbook, whose core rule is "a skill is advisory, a hook is
  deterministic"):
  - Three new opt-in hooks (`--hooks`), all deny-only, since a `deny` holds in every
    permission mode and a documented `ask` does not:
    - `test-lock.sh` denies edits to a reproducing test listed in
      `.ai-sdlc/test-lock.txt`, and to that list.
    - `secret-guard.sh` denies a commit whose staged additions carry a provider-shaped
      credential. It names the kind, never the value.
    - `approval-gate.sh` denies a command matching `.ai-sdlc/gates.txt` unless the session
      was started with `AI_SDLC_APPROVAL=<ticket>`, and denies edits to that list.
  - Each list file is seeded with comments only, so no hook does anything until the
    project adds a line.
  - `05-change-control.md` gains "Fixing a defect": commit the failing reproducing test
    first, lock it, then fix without editing it. `roles/qa.md` defect triage points
    there.
  - `AGENTS.md` §9 says which approvals get a gate. Existing installs keep their §9, as
    `--upgrade` never touches it.
- **Plans can be checked against the diff**:
  - `templates/plan.md` gains "Files that change", "Order of work" and a **Proof** line
    in the test strategy.
  - `sdlc.py plan-check <ID>` lists files the branch changed that the plan does not
    name, and planned paths nothing touched. Plans that predate the new section are read
    from their "Affected surfaces → Code" bullet, `{a,b}` sets included, and
    `<ID>-<slug>.md` names are found.
  - Tried read-only on the plans of two existing installs.
- **Review has a conformance pass and a nit cap**:
  - `02-role-reviews.md`, `/sdlc-review` and `templates/role-review.md` open every Tier
    1/2 ship review with a conformance pass: plan-check, each acceptance criterion traced
    to code and test, and out of scope held. It carries its own severity table.
  - Reviews report at most five S4 findings; the rest are given as a count.
  - The Important/Nit vocabulary is mapped onto the S0–S4 ladder.

- **A runtime for the mechanical half of doctor and verify** (`.ai-sdlc/bin/sdlc.py`,
  installed always, kit-managed, added to older installs by `--upgrade`):
  - `sdlc.py doctor` checks from the files what `/sdlc-doctor` used to ask the model to
    read: unsubstituted placeholders, a missing contract pointer, blank charter commands
    and approvers, undecided modes and roles, stale `last-reviewed` dates, Done items with
    no worklog entry, IDs that do not join across the backlog, worklog and git, worklog
    size, and profile drift. Findings are `fail` or `warn`, and `--strict` exits 1 only on
    `fail`, so a fresh install does not break CI.
  - `sdlc.py verify` runs the charter's `checks.*` commands in the verify order, and writes
    each stage's raw output, exit code, duration and log hash to
    `.ai-sdlc/evidence/<timestamp>/`, which git ignores. A "Verified" claim can now cite a
    file the script wrote.
  - `/sdlc-doctor`, `/sdlc-verify`, and the `sdlc-doctor` and `sdlc-evidence-check` skills
    run the script first and keep only the judgment: severity, behaviour, what to fix
    first. By hand is the fallback when the script or `python3` is absent.
  - Tried read-only on two existing installs. On one it found six worklog IDs missing
    from the backlog, a 3,272-line worklog past rotation, and a profile whose commands were
    never filled in. On the other it found a charter that predates the mode rows.

- **Kit-value benchmark** (`benchmarks/kit-value/`): a pinned, repeatable comparison of
  no kit, the kit, and the kit with `--hooks`, over five fixture tasks (a shared-caller
  bug, a trust boundary, a one-word typo, a refactor, and a verification trap whose suite
  cannot pass). Besides correctness and cost it measures fabricated verification claims
  (commands claimed as passing that the transcript never ran), commit and worklog
  traceability, and records created for a Tier 3 change. `run.py` isolates each run in a
  fresh workspace and a throwaway Claude config; `score.py` refuses N<4 and reports each
  arm against the control. No result is claimed yet.
  - The effort-mode scorer's validation now lives in `benchmarks/lib/scoring.py`, shared
    by both benchmarks. Its CLI and output are unchanged.
  - `validate.py` runs both scorers' and the measurement self-tests, and checks each task
    has its prompt, fixture and checks. `tests/smoke.py` drives the runner end to end
    with a fake agent.

- **Ephemeral test environment lifecycle and teardown**:
  - `AGENTS.md` (§7 & §8) and `CARD.md`: added a binding rule requiring agents to
    tear down ephemeral test environments (Docker containers, compose services,
    mock daemons, local test servers) immediately upon completion (pass, fail,
    or abort), leaving no idle containers or orphaned processes on the dev host.
  - `process/00-operating-model.md`: step 5 (`VERIFY`) mandates environment teardown
    before entering `SHIP REVIEW`.
  - `process/03-ready-and-done.md`: added a Definition of Done gate under Quality
    requiring all test environments to be stopped and host resources released.
  - `process/04-quality-gates.md`: added an Ephemeral test environments & resource
    teardown section with lifecycle encapsulation, resource bounds, and an S3/S2
    severity rating for orphaned test resources.
  - `roles/devops-sre.md` and `roles/qa.md`: added host & test-environment hygiene
    to design-review, ship-review, and severity calibration tables.
  - `templates/test-plan.md` and `charter.md`: added a dedicated test environment
    lifecycle table and command encapsulation guidance.
  - `optional/claude-commands/sdlc-verify.md`: added step 7 for teardown.

- **Corrections to the 3.3 additions**:
  - `project/defects/` now exists, with an index; two documents already pointed at it.
  - `templates/defect-report.md` no longer carries its own copy of the severity ladder,
    which had already drifted (it left out cross-tenant exposure and latent S0-class
    defects). It points at `04-quality-gates.md` instead.
  - `roles/qa.md` defect triage places an S2 in `Now` unless a named human waives it,
    matching the ladder, instead of `Next`.
  - `03-ready-and-done.md`: an upstream spec satisfies readiness only when it actually
    contains an observable outcome, testable criteria, and its open questions — as
    `sdlc-intake` already said.
  - `roles/security.md`: a charter that does not require MFA means the reviewer does not
    block on it, not that the reviewer may not mention it. Privileged access without MFA
    is recorded as a risk.

- **Upgrades reach `AGENTS.md`, the commands, and the charter**:
  - `AGENTS.md` now marks sections 1–8 as kit-managed. `--upgrade` replaces them and
    records their checksum, so a local edit there stops the upgrade instead of being
    overwritten; section 9, "Project overrides", is never touched. Before this, an
    upgraded project's process documents referred to effort modes and a solution ladder
    that its `AGENTS.md` did not contain.
  - The `/sdlc-*` commands are managed files, tracked in the manifest like the docs.
  - The charter gains, blank and in the right table, any row a newer kit added — never an
    edit to an existing row.
  - `--adopt` takes over `AGENTS.md` and the commands in a project installed before this
    version, once, after a backup. A plain `--upgrade` says when it is needed.
  - `-y` writes a mode row only when `--effort-mode` or `--acquisition-profile` was given.
    A row still listing every option is *undecided*, and `/sdlc-doctor` reports it as a
    question rather than an invalid value.

- **Deployment platform checklists; the core is stack-neutral again**:
  - The process documents, role playbooks, charter, and release runbook no longer name a
    vendor. The previous additions of Dokploy, Traefik, Cloudflare, GA4/GTM, Search
    Console, AWS, and GCP specifics — and the pre-filled environment rows and example
    URLs in the charter and runbook, which an agent would have read as facts — are
    replaced with neutral checks and blank rows.
  - The platform-specific failure modes moved to `optional/platforms/`, one checklist per
    platform: Cloudflare Workers & Pages, Cloudflare in front of an origin, Vercel,
    Netlify, Fly.io, Railway, Render, Heroku/Dokku, Dokploy, Coolify, Kamal, a
    self-managed VPS, Kubernetes, AWS, Google Cloud/Firebase, Azure, and DigitalOcean App
    Platform. Each installs into `docs/platforms/` only for a platform the project uses.
  - The installer detects platforms from deploy configuration (never from an SDK import,
    and never from a bare Traefik label), pre-selects them in a new wizard question, and
    records the answer in the charter's new **Deployment platforms** row and in
    `profile.json` → `deploy_platforms`. `--deploy <list>` answers it for `-y` runs;
    detection alone installs nothing.
  - `roles/devops-sre.md`, `sdlc-release`, the release runbook, and `/sdlc-doctor` read
    the row and its checklists. `validate.py` keeps the catalog, the files, and the index
    in step.

- **Lean / Normal / Beast effort modes**:
  - Added a project default plus explicit work-item override, resolved independently of
    risk tier. Lean minimises optional work, Normal keeps the balanced workflow, and
    Beast maximises investigation and verification without widening product scope.
  - Added the repository → standard-library → native-platform → installed-dependency →
    minimum-custom-code ladder and root-cause caller tracing to the operating contract.
  - Added installer flags, charter fields, profile schema 2, plan/worklog recording,
    reviewer/subagent propagation, validation, and upgrade-safe defaults.
- **Separate acquisition profiles**:
  - Replaced the ambiguous Beast scraping waiver with `Standard` and `Advanced`
    capability profiles. `Advanced` enables additional
    extraction techniques on owned or explicitly authorised targets.
  - Reachability no longer substitutes for permission: authentication, paywalls,
    CAPTCHA, explicit denial, and other access controls remain stop conditions without
    target-owner authorisation or an approved route.

- **External Services & Platform Awareness (Cloudflare, SSL, Search Console, GA4/GTM, AWS/GCP)**:
  - Expanded `charter.md` Stack & Sources of truth tables to explicitly register Cloud providers,
    CDN/Edge/WAF (Cloudflare/CloudFront), SSL/TLS certificates, Search Console verification, and GTM/GA4.
  - Added operational checks in `roles/devops-sre.md` for CDN cache invalidation, SSL termination
    (preventing flexible SSL redirect loops), and Cloud IAM least-privilege.
  - Added verification checks in `roles/seo.md` to prevent accidental clobbering of Search Console
    ownership verification tags/files and ensure sitemap delivery.
  - Added Tag Manager governance in `roles/cro-analyst.md` to prevent GTM scripts from violating CSP
    and enforce environment separation for analytics stream IDs.
  - Updated `templates/release-runbook.md` with post-deploy CDN cache purge and SSL/domain health smoke checks.
- **Flexible Access Level Models & Opt-In MFA/OTP**:
  - Added explicit `Access level model` (`Public`, `Simple`, `RBAC`, `Workspace-Scoped`, `ABAC`)
    and `MFA / OTP policy` (`Not required`, `Optional`, `Enforced for Admin`, `Enforced for all`)
    settings in `charter.md` and `templates/security-privacy.md`.
  - Calibrated `roles/security.md` to prevent dogmatic enforcement of MFA/OTP when declared
    not required, while adding checks for standard practices: auth endpoint rate-limiting,
    CORS/CSRF protections, and session invalidation on password reset.
- **Defect tracking & tester bug reports**:
  - Added `templates/defect-report.md` for capturing tester bug reports, reproduction
    steps, observed vs. expected behaviors, and severity calibrations.
  - Added defect triage and backlog-injection workflows in `roles/qa.md`,
    `07-traceability.md`, `CARD.md`, and the `templates/` registry in `docs/README.md`.
- **Spec-driven development (Spec Kit / Kiro) integration**:
  - `/sdlc-plan` and `sdlc-intake` now explicitly ingest upstream specification files
    (e.g., `specs/`, `spec.md`, or Spec Kit artifacts), adopting problem definitions,
    user stories, and acceptance criteria without asking redundant questions.
  - `03-ready-and-done.md` clarifies that an upstream spec satisfies the FRAME Definition
    of Ready criteria (outcomes, testable criteria, bounded unknowns).
  - `plan.md` and `test-plan.md` templates gained explicit acceptance-criteria mapping
    to connect Given/When/Then scenarios and negative assertions directly into test suites.

## 3.2.0 — 2026-09-03

The question this release answers is whether the kit needs a GUI. Researched rather than
guessed, the answer was: one small read-only page, and distribution — not a web product.
Steering an agent session belongs to the agent harness itself (such as a terminal, an IDE
integration, or Claude Code Remote Control), while the repository kit provides read-only
visibility over the project's records.

### Added

- **`docs/dashboard.html`** — a read-only status page over the installed state. Open it
  from the filesystem; no server, no dependency, no build. Shows open work by status and
  tier, artifacts stale or undated, roles unticked with nobody's reason, check stages with
  no command, budgets and baselines, and whether anything points at `AGENTS.md`.
  The page is kit-managed and upgradeable; its state lives in `docs/dashboard-state.js`,
  a project record derived from the files and never from the wizard's answers. It states
  its own generation date and declares itself untrustworthy past the charter's staleness
  window. `validate.py` fails if it invents a backlog status the standard lacks, or if a
  form or `contenteditable` appears in it.
- **`/sdlc-doctor` refreshes the page's state** and is told not to write a value it did
  not read from a file.
- **Claude Code plugin packaging** (`.claude-plugin/`) — `/plugin marketplace add
  rezar-84/nuhut.ai`. Commands only: skills are model-invoked and cost context in
  every turn whether they fire or not, so choosing them per project stays with the
  installer, which is the whole point of the fact model.
- **README positioning** for Spec Kit, Kiro and Tessl (complementary — they specify a
  feature, this governs a change), for the AI app builders (a place to install this, not a
  thing to replace), and for why there is no web UI.

### Not built, deliberately

A web installer, and a Lovable-style surface driving local agents. Both are argued in the
README and the decision record; the second belongs in a separate repository that consumes
this kit, if it is ever built at all.

## 3.1.0 — 2026-09-03

Profiling 3.0.0 found three defects and one cost regression. This release fixes them and
makes the kit work outside Claude Code.

### Fixed

- **The kit could install itself into permanent silence.** The `CLAUDE.md` pointer was
  written only when no `CLAUDE.md` existed — which is almost never in a real project — so
  `AGENTS.md` was never auto-loaded and nothing was printed about it. An existing
  instruction file is now appended to (never overwritten), re-running adds no second
  pointer, and an install that wires nothing warns loudly and prints the line to add.
- **A compact install could never be upgraded**, because `find_docs()` used a numbered
  process document as the marker for an installed kit.

### Added

- **`docs/CARD.md`** — the operating card. 2,252 tokens covering tiers, the seven
  evidence words, the check sequence, the severity ladder, verdicts and traceability. It
  replaces reading `02`, `04`, `06` and `07` for ordinary work; those become named
  escalation, and the full document wins wherever they disagree. `validate.py` reads the
  rules the card actually asserts and fails if it invents or drops one.
- **`--harness <list>`** — pointer files for Claude Code, Gemini CLI, Amp, Copilot,
  Cursor, Windsurf, Cline and Aider. Codex, Jules, Zed, Factory and opencode read
  `AGENTS.md` directly and are told so. Pointers reference; they never copy.
- **`--profile compact`** — installs the card, roles, templates and project records but
  omits the numbered `process/` documents. For a small context window or a weaker model.
- **`--hooks`** — two deterministic Claude Code guards: a commit with no work item ID is
  denied, and an edit to a path in `.ai-sdlc/protected.txt` is denied. Merged into an
  existing `settings.json` without disturbing it.
- **`process/10-multi-agent.md`** — claiming, single-writer files, review fan-out, why a
  subagent's result is *Reported* and not *Verified*, and handoff. Conditional.
- Charter: **Agent environment** and **Concurrency** tables. `/sdlc-doctor` checks that
  something points at `AGENTS.md` and rates its absence the highest finding it can make.

### Changed

- **The always-list costs 11,624 tokens instead of 18,222** — a 36% cut, and 26% below
  where 3.0.0 started. A Tier 2 change with two roles: 22.7k full, 17.3k compact.
- `AGENTS.md`'s per-tier figures are measured, and CI fails if they drift.

### Upgrading

`--upgrade` delivers `CARD.md` and `10-multi-agent.md`. Merge the `AGENTS.md` reading-list
changes with the printed `diff` — Tier 2 and Tier 1 now read the card instead of four
process documents, and that is the whole token saving. Copy the new charter tables if the
project needs them. `--harness`, `--profile` and `--hooks` apply to a fresh install.

## 3.0.0 — 2026-09-03

The kit covered web and content projects well and engineering-heavy ones barely. This
release closes that without growing what a web project *reads*: every review, skill, and
gate is fact-gated, and a content site's role roster and installed skills are byte-for-byte
what 2.5.0 produced (a smoke test asserts exactly that).

What does grow is the portable tree on disk. `docs/process/`, `docs/roles/`, and
`docs/templates/` are installed whole in every project, as they always have been, so that
`--upgrade` can manage them and a project can activate a role later without reinstalling.
A content site therefore gains eleven files it never opens: the reading list in
`AGENTS.md` §3 is what bounds an agent's context, and an inactive role's playbook is not
on it. `09-probabilistic-and-data-systems.md` says so in its own opening line.

### Added

- **`Measured`**, a seventh word in the verification vocabulary, for results that are
  numbers rather than passes. It carries method, subject version, N, spread, and date, or
  it is not a claim. A metric with no baseline is not an improvement, it is a number.
- **`process/09-probabilistic-and-data-systems.md`** — models, prompts, retrieval,
  datasets, pipelines, and acquisition. Read only when a change touches one.
- **Three role playbooks**: `data-engineer`, `ml-engineer`, `performance-engineer`.
- **Four extensions to existing playbooks**: `architect` gains asynchronous and
  distributed review plus a clean-code block; `security` gains supply chain and AI/agent
  surfaces; `qa` gains testing non-deterministic systems; `privacy-legal` gains acquired
  data, third-party inference, and generated-content disclosure.
- **Six templates**: `eval-plan`, `data-contract`, `pipeline-runbook`,
  `performance-budget`, `service-catalog`, `model-and-dataset-card`.
- **Seven skills**: `sdlc-eval-gate`, `sdlc-data-contract`, `sdlc-migration`,
  `sdlc-service-contract`, `sdlc-perf-budget`, `sdlc-scrape-compliance`, and
  `sdlc-doctor` (installed always).
- **Four conditional check stages** — `checks.infra`, `checks.data`, `checks.eval`,
  `checks.perf` — with charter rows, installer questions, and CI scaffolding.
- **`.ai-sdlc/profile.json`**, the charter in machine-readable form, so a command or
  skill can branch on the project's facts and commands without parsing prose. The
  charter remains the source of truth and wins on conflict.
- **`/sdlc-doctor`**, the first check that audits an installed project rather than the
  kit's own source: placeholders, blank commands, undecided roles, stale artifacts,
  traceability gaps, worklog size, profile drift.
- Detection for ML/LLM, vector stores, data orchestration and warehouses, messaging,
  IaC, acquisition, and load tooling — each feeding a project-type default.
- A worklog rotation threshold in `07-traceability.md`. The worklog is on the always-read
  list and grew unbounded, one invisible entry at a time.
- Cross-reference validation (roles, templates, skills, and check stages must agree
  everywhere they are named) and a guard that fails if `AGENTS.md`'s stated docs-tree
  size drifts from the measured one.

### Changed

- **Twelve project types and eleven facts**, up from eight and six. `TYPE_FACTS` is keyed
  by fact name rather than position.
- `/sdlc-verify` reads the profile for exact commands, runs the conditional stages, and
  reports `Measured` where the result is a number.
- `AGENTS.md`: prompt, model, retrieval, dataset, and contract changes have explicit tier
  triggers; the reading-list token figures are now measured rather than estimated.
- The installer derives charter command labels from the stage key instead of zipping
  against a parallel list.

### Upgrading

`--upgrade` delivers the new process document, role playbooks, and templates to an
existing installation, and leaves `AGENTS.md` and `docs/project/` alone as always. Two
things need a hand:

- Merge the `AGENTS.md` changes (sections 2, 3, 5, and 7) with the printed `diff`.
- The new charter sections — **Budgets**, **Model & data**, **Data ownership**, the three
  role rows, and the four `checks.*` rows — are not added to an existing charter, because
  the file is project-owned. Copy them from `template/docs/project/charter.md` if the
  project has those surfaces.

New skills are not added by an upgrade; `ls optional/skills` shows what is available.

## 2.5.0 — 2026-08-23

### Added

- Stack adapters for Node/TypeScript, Python, Go, Rust, PHP, Ruby, Maven/Gradle, and .NET.
- ORM, database-driver, migration-tool, and testing-tool detection across those ecosystems.
- `--scaffold-tests` for an instantiated test plan and machine-readable testing profile.
- `--scaffold-ci github|gitlab` for opt-in pipelines generated from confirmed commands.
- Adapter and scaffolding fixtures covering supported language and database families.
- Polyglot command composition so every detected language participates in each quality stage.
- Manifest-managed template upgrades, allowing new testing and data-model guidance to
  reach existing installations without touching project records.

### Safety

- Scaffolding never installs dependencies and never overwrites existing test plans,
  profiles, or CI configuration.
- CI generation refuses repositories with no detected or confirmed quality commands.
- Generated CI is manual-only until a human confirms commands, runtimes, and services.
- Generated database guidance requires real-engine integration tests, migration/restore
  exercises, and synthetic test data.

## 2.4.0 — 2026-08-23

### Added

- Machine-readable manifests for portable managed files.
- Upgrade preflight checks, backups, obsolete-file cleanup, atomic writes, and rollback.
- Stack-neutral validation, continuous integration, and tag-based release automation.
- AI prompt-injection, secret-disclosure, and permission-escalation boundaries.
- Repository licensing, contribution guidance, and a security policy.
- Detection for integration, contract, accessibility, and common namespaced test scripts.

### Changed

- `--docs-dir` now updates the operating contract and Claude commands completely.
- Tier 3 uses a compact reading and worklog path.
- Dry runs and pre-confirmation quits no longer create target directories.
- Detected format, install, typecheck, and lint commands favor non-mutating,
  reproducible, locally installed tools.

## 2.3.0

- Added the navigable installer, localisation role, and architecture seeding.

Earlier history is available in the repository's Git log.

# The runtime: sdlc.py

The mechanical half of the process, and the viewer.

## Scripts for what does not need judgment

A rule written as prose is a request the agent may or may not honour. The same rule as a
check either passes or fails. So the parts of the process a machine can decide are a
script, not a paragraph. Every install gets
`.ai-sdlc/bin/sdlc.py`: standard-library Python, kit-managed, and refreshed by `--upgrade`.

<p align="center">
  <img src="../assets/cli-help.svg" alt="Nuhut SDLC CLI Commands: doctor, verify, plan-check, view, metrics" width="100%">
</p>

```sh
python3 .ai-sdlc/bin/sdlc.py doctor            # audit commands, staleness, profile drift, and
                                               # dependency loops/missing IDs
python3 .ai-sdlc/bin/sdlc.py doctor --strict   # exit 1 on any fail-level finding, for CI
python3 .ai-sdlc/bin/sdlc.py verify            # run charter checks in order and record evidence
python3 .ai-sdlc/bin/sdlc.py verify --parallel # run independent checks concurrently (-j)
python3 .ai-sdlc/bin/sdlc.py plan-check ACME-12 # check git diff against approved plan/spec
python3 .ai-sdlc/bin/sdlc.py view              # draw records as an interactive HTML dashboard
python3 .ai-sdlc/bin/sdlc.py view --serve      # the same page, live: follows records & git history
python3 .ai-sdlc/bin/sdlc.py view --export-html out.html # export self-contained report for CI/CD
python3 .ai-sdlc/bin/sdlc.py metrics           # process measures, leading and lagging
python3 .ai-sdlc/bin/sdlc.py log --since main   # draft worklog lines from commits and verify runs
python3 .ai-sdlc/bin/sdlc.py bite <test command> # do the tests fail without the change?
python3 .ai-sdlc/bin/sdlc.py trailers ACME-12   # print the Work-Item / Agent / Model trailers
python3 .ai-sdlc/bin/sdlc.py review ACME-12 --role security --by codex  # independent review
```

| Command | Key Flags | Description |
| --- | --- | --- |
| **`doctor`** | `--strict` | Audits project records, active roles, check commands, staleness windows, and validates the dependency graph (flags self-dependencies, non-existent backlog IDs, and circular dependency loops). Ages the backlog against the same window: an `In progress` or `In review` row nothing has named since the window passed is a zombie claim; a `Ready`, `Blocked` or `Parked` row older than the window needs a decision. |
| **`verify`** | `--parallel` (`-j`), `--stage`, `--timeout` | Runs the charter's check pipeline in order, writing immutable test evidence (`summary.md`, `summary.json`, and stage `.log` files) to `.ai-sdlc/evidence/<timestamp>/`. `--parallel` runs independent steps concurrently using a worker pool. |
| **`plan-check <ID>`** | | Compares branch changes against the approved plan (`docs/project/plans/<ID>.md` or `.sdlc/specs/<ID>/spec.md`). Highlights unapproved file modifications and planned files left untouched with ANSI terminal colors. |
| **`view`** | `--serve`, `--port`, `--interval`, `--export-html <file>`, `--svg`, `--no-open` | Generates the rich interactive developer dashboard. The Board opens with a cumulative-flow chart of backlog columns over time, rebuilt from the backlog's git history; the home page shows a pass/fail grid of the last verify runs per stage. `--serve` runs a reactive local server on `127.0.0.1`. `--export-html` bundles an offline single-file report for CI/CD artifacts or PR previews. |
| **`metrics`** | `--json` | Calculates quantitative project health metrics: work-in-progress (WIP), verification pass rate, cycle time, lead time, time waiting on humans, lifecycle record gaps, and usage against the charter's optional agent budget per tier. |
| **`log`** | `--since <ref>`, `--write` | Drafts worklog lines, one per work item, from the commits since `<ref>` (IDs from subjects or `Work-Item` trailers) and the verify runs recorded on them. `--write` inserts them under the worklog's marker, newest first, skipping items the worklog already names. Records become byproducts, not essays. |
| **`bite`** | `--base`, `--timeout`, `--restore`, `--json` | Puts the changed product files (never tests, never the kit's paths) back to the base, runs the test command, and restores them. It passes only when the tests pass with the change and fail without it. A backup and marker under `.ai-sdlc/bite/` make an interrupted run recoverable with `--restore`, and the doctor flags one. |
| **`trailers <ID>`** | `--agent`, `--model` | Prints the `Work-Item`, `Agent` and `Model` commit trailers, from flags, `AI_SDLC_AGENT` / `AI_SDLC_MODEL`, or what the harness exposes. |
| **`review <ID>`** | `--role`, `--by claude\|codex\|gemini\|cmd:<command>`, `--model`, `--stage` | Sends one role's playbook, the item's diff, the relevant charter rows and the tier to another harness, headless, and saves the review with the reviewer's and author's identity, labelled independent or self-check. |

**Evidence.** `verify` and `bite` also append one line per stage to
`docs/project/evidence-ledger.jsonl`: commit, whether the tree was dirty, stage, command,
exit code, output hash and time. The logs stay in the git-ignored evidence folder; the
ledger is committed, so a reviewer or CI can check a claim against it. The doctor flags a
worklog entry that says *Verified* when the ledger has no run for that item's change, and
fails a built Tier 1 item without a review from a model family other than the author's.

`verify` exists so a "Verified" claim can cite a file the script wrote instead of the
agent's memory of a run. `/sdlc-doctor` and `/sdlc-verify` call the script first and keep
the judgment for themselves: severity, behavioural checks, and what to fix first. It works
with any agent tool that can run `python3`. `/sdlc-review` opens every Tier 1 ship review
with `plan-check`, so a diff that drifted from its approved plan is visible before any role
reads it.

### Seeing the work

Records written for an agent are hard for a person to read once a project is real: a
worklog runs to thousands of lines, and one item's story is spread over a backlog row, a
plan, two reviews and a worklog entry. `sdlc.py view` reads them all at the moment you run
it and opens one comprehensive, navigable page joined by work item ID:

<p align="center">
  <img src="../assets/viewer-preview.svg" alt="Nuhut SDLC Interactive Viewer Dashboard: Git Graph, Blockages & Flow, Lifecycle Inspector, and Map" width="100%">
</p>

The viewer organizes project reality across six dedicated views:

- **Map:** the whole project as a mind map (status, owner role, documents), folding and
  unfolding, with clipped titles, child count badges, doctor findings, and a quick-jump
  `Blockages & Flow` button.
- **Board:** Kanban columns (Now, Next, Blocked, Parked, Later, Done), filtered by owner,
  tier, or text search. Cards show dependency blockers and downstream impact.
- **Activity:** what is in flight right now, recent worklog entries, and a collapsible
  summary of uncommitted working tree changes.
- **Blockages & Flow:** a dedicated dependency and blockage command center:
  - **Directed Flow Board:** 3-column triage (`Root Blockers` ➔ `Blocked Tasks` ➔ `Waiting on Human`).
  - **Bottleneck Matrix:** items ranked by blast radius (number of downstream tasks blocked).
  - **Human Decision Log:** items parked awaiting human sign-off with stall durations.
  - **Dependency Table:** explicit relationships and quick navigation.
- **Git Graph:** visual topological Git commit graph positioned prominently above the fold:
  - Multi-branch commit lanes with branch splits, merges, and commit dots.
  - Commit badges (`main`, `review:passed`), author avatars, and relative timestamps.
  - Interactive commit drawer showing full commit message, SHA, author, and changed files.
  - Uncommitted working tree summary banner and local branches overview.
- **Documents:** every project artifact with frontmatter status (`draft`, `approved`, `stale`),
  accountable owner, and age. Click to open with interactive outlines and cross-linked IDs.

#### Item Lifecycle Stepper

Click any work item ID anywhere to open its deep inspector. The lifecycle stepper runs
from Frame to Close (`Frame` ➔ `Plan` ➔ `Design Review` ➔ `Build` ➔ `Verify` ➔ `Ship Review` ➔ `Log` ➔ `Close`).
Green means the record for that step exists. An amber **?** means the item's tier and
status call for a record that does not exist yet (such as a Tier 1 item in progress with
no plan, or a Done item with no worklog entry). That is a real gap to close, not a display
fault.

#### Keyboard Shortcuts & Navigation

| Shortcut | Action |
| --- | --- |
| **`⌘K`** or **`Ctrl+K`** | Open Command Palette to search all work items, documents, and headings. |
| **`?`** | Toggle the Keyboard Shortcuts & Help modal. |
| **`1` - `6`** | Switch views instantly: `1` Map, `2` Board, `3` Activity, `4` Blockages, `5` Git Graph, `6` Documents. |
| **`/`** | Focus the header search input. |
| **`Esc`** | Close open modal, commit drawer, or clear active search filter. |

**A daily routine that works:** open **Blockages & Flow** first to clear bottlenecks, then
**Activity**. Before calling an item done, open its inspector and check that no step is amber.

With `--serve` the page is live: leave it open while agents work, and it redraws
within a couple of seconds of any record changing or a new commit, keeping your place, folds
and filters. It serves only on 127.0.0.1, refuses requests addressed to any other host,
and has no way to write. Ctrl+C stops it; `--port` and `--interval` tune it. Rows the view
cannot read are listed on the page rather than dropped.

With `--export-html <path>`, `sdlc.py view` generates a standalone, self-contained single-file
HTML bundle embedding the entire data model. It runs offline without a local server, making
it ideal for CI/CD artifact publishing, PR status reports, and static team dashboards.

The opt-in `--hooks` go one step further for Claude Code. They deny the tool call itself:

- a commit with no work item ID, or with a credential in it
- a file write containing a credential, with a warning when personal data is written to a record
- an edit to a single-writer path
- an edit to a reproducing test locked while its defect is fixed
- a command, such as a production deploy, that `.ai-sdlc/gates.txt` says a human must pass

A skill makes a violation rare, and a hook makes it close to impossible. See
`optional/hooks/README.md` for what each hook can and cannot see. With `--harness gemini`
the same six rules are registered in `.gemini/settings.json`, and with `--harness cursor`
the three shell rules in `.cursor/hooks.json`; `adapter.sh` translates the payload and
the verdict, so each rule still lives in one script.

The opt-in `--git-hooks` cover the two commit-time rules for **every** agent and every
human, because git runs them, not the harness: a `pre-commit` that refuses staged
credentials and a `commit-msg` that refuses a message with no work item ID
(`--git-hooks secrets` installs only the first). The scripts live in
`.ai-sdlc/git-hooks/`; the project's existing hook, husky file or `core.hooksPath`
directory gets one line appended and is otherwise left alone, and with pre-commit.com
or lefthook the entry to add is printed instead. `git commit --no-verify` bypasses them,
deliberately and visibly. The enforcement nobody can skip is CI: `--scaffold-ci` puts
`sdlc.py doctor --strict` before the quality commands.

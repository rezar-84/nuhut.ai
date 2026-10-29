# The viewer

One page that joins up a project's records: backlog, worklog, plans, reviews, ADRs,
verify runs, commits and the project's own stack. Records written for agents get long. A
worklog runs to thousands of lines, and one item's story is spread over a backlog row, a
plan, two reviews and a worklog entry. The viewer reads them all and links them by work
item ID.

```sh
python3 .ai-sdlc/bin/sdlc.py view                  # write .ai-sdlc/view/index.html and open it
python3 .ai-sdlc/bin/sdlc.py view --serve          # the same page, live, on 127.0.0.1
python3 .ai-sdlc/bin/sdlc.py view --serve --github # plus open GitHub issues and pull requests
python3 .ai-sdlc/bin/sdlc.py view --export-html report.html   # one offline file for CI or a PR
```

Want to look before installing anything? `python3 tools/demo_project.py` builds a
fictional project with every view populated (see the [README](../README.md#try-it-in-one-minute)).

<p align="center"><img src="../assets/screens/dashboard.jpg" alt="Dashboard: Needs you, Health and Flow" width="100%"></p>

## The views

| Key | View | What it is for |
| --- | --- | --- |
| `1` | **Inbox** | Work item threads and the project-wide activity feed |
| `2` | **Board** | Kanban across the lifecycle columns, or a table |
| `3` | **Dashboard** | What needs a decision, then health, flow, tests, runs, doctor |
| `4` | **Blockages** | Dependency chains, root blockers, decisions waiting on people |
| `5` | **Git** | The commit graph, with work items and trailers on each commit |
| `6` | **Documents** | Every record with its status and age; **Specs** lives here |
| `7` | **Project** | Stack, build errors, security, deploy, environment, work, agents, kit settings |

### Inbox

<p align="center"><img src="../assets/screens/inbox.jpg" alt="Inbox: a work item's lifecycle thread with its next action" width="100%"></p>

- **Threads** groups work items into *Needs you* (Blocked, Parked), Active, Ready and
  Completed. An item with activity you have not opened gets a dot.
- **Activity feed** lists every item's events, newest day first: commits, verify runs,
  reviews, gates, worklog entries, records and spec changes. One item's day is one row
  ("5 commits · 1 verify run"). Filter by kind, or show *Unread only*.
- A thread shows the item's lifecycle as a stream:
  - frame, plan (with plan-vs-diff drift), spec change
  - commits with their `Agent` and `Model` trailers, verify runs
  - reviews, gates, worklog
- At the bottom sits the **next action**, with *why* it was chosen and the exact
  `sdlc.py` command. `r` runs it on a live page; a static page copies it.
- Read state lives in your browser only. The first visit marks everything read.

### Board

<p align="center"><img src="../assets/screens/board-panel.jpg" alt="Board with an item open in the side panel" width="100%"></p>

The columns are Now, Next, Blocked, Parked, Later and Done (plus Dropped on request). You can
filter by owner, tier or text, and group by epic, owner or tier.

Cards show:
- lifecycle pips, and `MISS:` stamps for a missing record
- dependency blockers
- an unread dot
- the last verify result
- an age badge: days in the column, amber at 3, red at 7
- who has claimed the item

A `wip_limit` in the charter shows the Now count as `n/limit`.

The board maps common status words to its columns: Planned and Pending go to Next,
Completed and "Done on …" to Done, On hold to Parked, Cancelled to Dropped. Anything it
still cannot place sits under Other, with a note saying which statuses those are.

### Dashboard

- **Needs you:** only what a person has to act on. That means failing doctor findings, a
  failed verify run, build and security failures from the Project lens, and every blocked or
  parked item with who it waits on. `j`/`k` walk the list.
- **Health:** shippable or not, the last verify run, Done, in flight, and git traceability.
  Each says what it covers.
- **Flow:** items per column over committed days.
- Summaries with *View all* links to full pages:
  - **Tests & verify** (`#/dashboard/tests`): every run × stage, a stage table with
    duration trend, pass rate and a flaky flag. Click a cell for its log.
  - **Runs & logs** (`#/dashboard/runs`): verify runs and commands run from the page,
    filterable, with the log beside the list.
  - **Doctor** (`#/dashboard/doctor`): findings grouped by rule, failures first.
  - **Parallel work** (`#/dashboard/parallel`): who holds what, and which Ready items can
    start together ([multi-agent work](multi-agent.md)).

### Project

<p align="center"><img src="../assets/screens/project-security.jpg" alt="Project lens: security findings" width="100%"></p>

What the project is made of, read live from its own files.

| Page | Shows |
| --- | --- |
| Stack & dependencies | Languages, frameworks, data, auth, hosting, CI; direct dependencies per manifest with the lockfile each uses |
| Build & errors | `file:line` errors lifted from the latest failing verify logs, one click from the full log |
| Security | Vulnerable packages (from `sdlc.py audit`), credentials found in records, a committed or un-ignored `.env`, secrets in compose files, unpinned or root containers, open security-review findings |
| Deploy & runtime | Deploy platforms with evidence, CI workflows, Dockerfiles, compose services, the dev container |
| Environment | Variable **names** used in code vs in `.env.example`-style templates. Values are never read. |
| Work | The backlog by column, plus open GitHub issues and PRs with `--github` |
| Agents & skills | Skills, commands, subagents, hooks, MCP servers and plugins, from the kit, the project and (live page only) your user level. Also duplicates, kit files changed locally, and the context skill descriptions cost every turn. |
| Kit settings | Effort, independent review, tier rules, decision style, method, reviewer, token saver, and safe repairs |

<p align="center"><img src="../assets/screens/project-build.jpg" alt="Project lens: build errors lifted from the typecheck log" width="100%"></p>

### Specs

Under Documents ▸ Specs, when the charter turns them on:
- capabilities with their requirements and scenarios
- pending changes marked on the requirements they touch
- specs other tools wrote (OpenSpec, Spec Kit), labelled by source

See [specs](specs.md).

<p align="center"><img src="../assets/screens/specs.jpg" alt="Specs: a capability with a pending change from a work item" width="100%"></p>

## Around every view

- **Side panel.** Click a card, run, commit, document or finding and it opens beside the
  page. The list stays usable, and `j`/`k` move the selection with the panel following. Three
  tabs:
  - **Item:** what you clicked, with a back arrow through its links.
  - **Activity:** what changed while the page was open.
  - **Issues:** everything that would otherwise be a warning above some page.

  Closing it folds it to a rail of those tabs, and dragging its edge resizes it. Below
  1100px it is a slide-over.
- **Activity bar** (bottom): live state, branch, the last verify result, doctor, waiting
  items, the running or last command, issues and unread. Each one links to its source.
  Only verify failures, doctor regressions, items becoming blocked and finished commands
  raise a toast.
- **Back.** Pages opened from a list (an item's full page, a document, a Dashboard or Project
  page, a search) show a Back link to it, such as *← Inbox · ACME-4*.
- **Agents chip** (header): the agent profile at a glance. Click it for the effort,
  independent review, reviewer and token saver controls.

## Keyboard

| Keys | Does |
| --- | --- |
| `1`–`7` | Switch views |
| `⌘K` / `Ctrl+K`, `/` | Search items, documents and headings, and run actions |
| `j` / `k`, `↑` / `↓` | Move through the Inbox, Board cards or Needs you; the panel follows |
| `h` / `l`, `←` / `→` | Board: move between columns |
| `o`, `Enter` | Open the selected item's page / its panel |
| `r` | Inbox: run (or copy) the selected thread's next action |
| `]` | Open or fold the side panel |
| `n` | Notifications (the panel's Activity tab) |
| `Backspace`, `Alt+←` | Back to the list you came from |
| `t` | Dark or light theme |
| `?` | All shortcuts |
| `Esc` | Close a dialog, or fold the panel |

## Live and static

`view --serve` keeps the page in step with the records. It polls a cheap fingerprint and
redraws within a couple of seconds of a record changing or a new commit. Your place, folds
and filters are kept, and it waits while you type.

On a live page you can:
- run `verify`, `doctor` and `audit`, and a thread's next action, with the output kept under
  `.ai-sdlc/runs/` (redacted, newest 50)
- read any verify stage's log
- change kit settings, which are written to the charter

A static page (`view` or `--export-html`) is one self-contained file. It works offline, and
there its buttons copy the equivalent command instead.

## What it never does

- **It serves only on 127.0.0.1** and refuses requests addressed to any other host (DNS
  rebinding). Every action needs a session token the page carries.
- **It never reads a secret value.** Environment files are read for variable names only,
  and only from templates; a real `.env` is checked for existence and whether git ignores
  it. MCP servers are listed by name and transport, never their arguments, environment or
  headers. Command output is redacted before it is kept.
- **User-level items stay off static pages.** Skills, commands and MCP servers from
  `~/.claude` appear only on the live page (`--no-user` hides them there too), never in an
  exported file.
- **It runs nothing on its own.** The dependency audit and GitHub queries run when you ask:
  `audit`, the button, or `--github`.
- **It never edits a record**, apart from the settings you change on Kit settings, which
  are written to the charter.

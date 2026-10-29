# Documentation map

This tree is the delivery system for {{PROJECT_NAME}}. `AGENTS.md` at the repository
root is the contract; everything here is the detail behind it.

**A person catching up** does not need to read these files one by one. From the
repository root, run `python3 .ai-sdlc/bin/sdlc.py view` for a page that joins them all
up (see "The viewer" below), or add `--serve` to keep that page live while agents work.

## Cold start — an agent arriving with no context

Read in this order and stop when you have enough:

1. `project/charter.md` — what this is, who it is for, ID prefix, active roles, stack,
   environments, risk defaults. **Nothing else in this tree is reliable if the charter
   is empty.**
2. `project/backlog.md` — what is planned, in flight, and done.
3. `project/worklog.md` (most recent entries) — what actually happened, and why.
4. `project/assumptions-and-risks.md` — what is unknown, unverified, or contested.
5. The specific artifact your task touches (architecture, design system, test plan…).

Do not bulk-read `process/` and `roles/` up front. Open a process doc when you hit the
step it governs; open a role playbook when you are performing that role's review.

## `CARD.md` — the operating card

The standard compressed into one page: tiers, the evidence vocabulary, the check
sequence, the severity ladder, verdicts, traceability, and a table saying which document
to open next. It replaces reading `process/02`, `04`, `06`, and `07` for ordinary work —
those stay as escalation, and **the full document wins wherever they disagree**.

Read it on every Tier 1 and Tier 2 change. It is also the routing for an agent tool
that does not load skills; tools that read `.agents/skills/` get the same routing from
the skill descriptions.

## The viewer: `sdlc.py view`

The records here are written for agents, and they get long. The viewer reads all of them
when you run it (backlog, worklog, plans, reviews, defects, postmortems, ADRs, and the git
history) and joins them by work item ID into one page you click through.

```sh
python3 .ai-sdlc/bin/sdlc.py view            # build the page and open it
python3 .ai-sdlc/bin/sdlc.py view --serve    # live: the page follows the records
python3 .ai-sdlc/bin/sdlc.py view --export-html dist/dashboard.html # export self-contained report
python3 .ai-sdlc/bin/sdlc.py metrics         # process numbers in the terminal
python3 .ai-sdlc/bin/sdlc.py --help          # every command, grouped, with an example each
```

| Tab | Answers |
| --- | --- |
| **Inbox** | What happened to each item, and what is next? Threads by item (plan, commits, verify runs, reviews, worklog) with the next command and why; an activity feed across all items, with unread marks. |
| **Board** | Where is every item? Now, Next, Blocked, Parked, Later, Done, with age, claims, last verify result and dependency blockers on each card. |
| **Dashboard** | What needs a person now? Failing checks, security problems and items waiting on someone, then health, flow, and full pages for tests and verify runs, runs and logs, doctor findings, and parallel work. |
| **Blockages** | Where is work stuck? Root blockers, blocked items, decisions waiting on people, blast radius. |
| **Git** | How did the code evolve? The commit graph with each commit's work item and agent. |
| **Documents** | Every record with its status, owner and age; **Specs** shows living specs when the charter turns them on. |
| **Project** | What is the project made of? Stack and dependencies, build errors from the verify logs, security findings, deploy and CI, containers, environment variable names, the agents' skills and MCP servers, and the kit settings. |

Click any ID to open that item: its row, plan, reviews, worklog entries, commits and
every record that mentions it, with a lifecycle stepper from Frame to Close. An amber
**?** on a step means the item's tier and status call for a record that does not exist
yet. That is a real gap, not a display fault. Search in the header (`⌘K` or `/`) finds IDs,
titles, documents and headings; press `?` for keyboard shortcuts; the browser's back button works throughout.

- **A snapshot or live.** Without `--serve` the page is a snapshot: run the command again
  to refresh it. With `--serve` it redraws within a couple of seconds of any record or
  commit changing, and keeps your place. The bar at the bottom says Live, or Disconnected if you
  stopped the server.
- **Headless export.** `--export-html <file>` bundles an offline single-file report with
  all data embedded, suitable for CI/CD artifacts and PR reviews without a local server.
- **Read-only.** It never writes to these files, and it adds no format for anyone to
  keep. The snapshot goes to `.ai-sdlc/view/`, which git ignores; live mode serves only on
  127.0.0.1.
- **Nothing is hidden.** Rows that do not follow the formats here (an ID that is not
  `{{PREFIX}}-###`, for example) are listed on the Map page under "could not read", so
  they can be fixed.

## `process/` — how work is done

Portable standards. Identical in every project that installs this kit. Do not add
project facts here.

| File | Answers |
| --- | --- |
| `00-operating-model.md` | What is the loop? Which lifecycle applies, and how do Lean, Normal, and Beast effort modes change work above the risk floor? |
| `01-lifecycle-gates.md` | What are the phases G0–G6, what must exist to enter and to leave each one? |
| `02-role-reviews.md` | Who reviews what, at which stage, with what verdict, and what happens on a Block? |
| `03-ready-and-done.md` | When is a task ready to start? When is it actually finished? |
| `04-quality-gates.md` | What must be tested, in what order do checks run, how are bugs severity-rated? |
| `05-change-control.md` | Branches, commits, PRs, approvals, ADRs, releases, rollback, managed platforms. |
| `06-evidence-and-claims.md` | What may be stated as fact, what needs a source, how unknowns are recorded. |
| `07-traceability.md` | ID scheme, what gets logged where, how staleness is detected. |
| `08-content-and-translation.md` | Source language, what may be machine-translated, who reviews it, and what multilingual code and layout must do. |
| `09-probabilistic-and-data-systems.md` | How do I change a model, prompt, index, dataset, or pipeline — and what may I claim about a system whose output is a distribution? |
| `10-multi-agent.md` | How do several agents work this repository at once without overwriting each other, and how are reviews fanned out? |
| `11-epics.md` | How do several connected items run under one plan, with the human checkpoints the project chooses, instead of one stop per item? |
| `12-sensitive-data-in-records.md` | What may a record hold, what must it never hold, and what happens when a person pastes a secret or personal data? |
| `13-stack-evaluation.md` | How is a stack or version chosen: verified from the official source, compared on stated criteria, and recorded with its dates? |
| `15-specs.md` | When the charter turns Specs on: what a living spec is, when a work item needs a spec change, and how it is applied on close. |
| `14-decision-style.md` | Who makes a choice the request did not settle (Ask, Guide, Autopilot), how is a non-specialist asked, and what does no style lift? |

## `roles/` — who reviews

Sixteen playbooks, one per professional perspective. Each has the same shape: mission, when to
engage and when to skip, what it reads, a design-review checklist, a ship-review
checklist, a severity calibration table, what it owns, and where it hands findings off.
See `roles/README.md` for the roster and how to run a review.

## `platforms/` — deployment checklists *(only if the project named a platform)*

One checklist per deployment platform in the charter's **Deployment platforms** row —
the failure modes specific to that platform, which the stack-neutral `devops-sre`
playbook and release runbook cannot name. Installed only for platforms this project
uses; absent when it deploys nowhere or on a platform the kit has no checklist for.
`platforms/README.md` lists every checklist the kit offers.

## `templates/` — blank artifacts

Copy these into `project/` when the project needs one. Never edit a file in `templates/`
to hold project content.

| Template | Copy to | Create when |
| --- | --- | --- |
| `product-brief.md` | `project/product-brief.md` | At G1, always |
| `discovery-audit.md` | `project/discovery-audit.md` | Replacing or migrating an existing system |
| `user-stories.md` | `project/user-stories.md` | Any user-facing scope |
| `architecture.md` | `project/architecture.md` | Any project with more than one moving part |
| `data-model-api.md` | `project/data-model-api.md` | Persistent data or a public/internal API exists |
| `design-system.md` | `project/design-system.md` | A user interface exists |
| `content-seo-plan.md` | `project/content-seo-plan.md` | Public discoverable content exists |
| `measurement-plan.md` | `project/measurement-plan.md` | Success is measured by user behaviour |
| `security-privacy.md` | `project/security-privacy.md` | Always, even if the answer is "no user data" |
| `threat-model.md` | `project/threat-model.md` | Auth, tenancy, payments, PII, or public exposure |
| `test-plan.md` | `project/test-plan.md` | Always |
| `release-runbook.md` | `project/release-runbook.md` | Anything that deploys |
| `service-catalog.md` | `project/service-catalog.md` | More than one independently deployed unit |
| `data-contract.md` | `project/data-contract-<name>.md` | Anything outside this project reads a dataset, table, or event it produces |
| `pipeline-runbook.md` | `project/pipeline-runbook.md` | A scheduled or triggered pipeline exists |
| `eval-plan.md` | `project/eval-plan.md` | An output is judged by quality rather than correctness |
| `model-and-dataset-card.md` | `project/model-card-<name>.md` | A model is trained or tuned here, or a dataset is curated |
| `performance-budget.md` | `project/performance-budget.md` | A latency, throughput, or cost budget is claimed |
| `adr.md` | `project/adr/NNNN-slug.md` | Per material decision |
| `plan.md` | inline in the response, or `project/plans/{{PREFIX}}-###.md` | Per Tier 1–2 task |
| `spec.md` | `project/specs/<capability>.md` | Specs on: describing what one capability does now |
| `spec-change.md` | `project/specs/changes/{{PREFIX}}-###.md` | Specs on: a Tier 1–2 item that changes observable behaviour |
| `epic.md` | `project/epics/{{PREFIX}}-###.md` | Per epic, when the development method is `Epic` |
| `role-review.md` | `project/reviews/{{PREFIX}}-###-<stage>.md` | Per Tier 1 review only; Tier 2 and 3 record verdicts in the worklog entry |
| `worklog-entry.md` | appended to `project/worklog.md` | Per completed task |
| `defect-report.md` | `project/defects/{{PREFIX}}-###.md` | A bug report or QA defect is filed by testers |
| `postmortem.md` | `project/postmortems/YYYY-MM-DD-slug.md` | After an S0/S1 incident |

## `project/` — this project's reality

The only directory that changes daily. Every document in it carries frontmatter:

```yaml
---
status: draft | approved | stale
owner: <person or role accountable>
last-reviewed: YYYY-MM-DD
---
```

Two exceptions, both deliberate. **ADRs** carry their own decision lifecycle instead
(`Proposed | Approved | Superseded by NNNN | Deprecated` — see `templates/adr.md`); an
ADR is a dated record of a decision, so it never goes `stale`, it gets superseded. And
the `README.md` in each subdirectory is part of the kit, not a project record.

`status: stale` is a legitimate and useful state. Marking a document stale is better
than leaving a confident, wrong document in place — but the marking must be accompanied
by a backlog item to fix it.

## `.claude/` — commands and skills

Outside this tree, but installed with it. `.claude/commands/` holds the six `/sdlc-*`
slash commands that drive the loop when you type them: `/sdlc-plan`, `/sdlc-build`,
`/sdlc-verify`, `/sdlc-review`, `/sdlc-log`, and `/sdlc-doctor` — which audits these
documents rather than the code, for the gaps and staleness that nothing else announces.
On a tool whose `/` menu lists skills instead (Antigravity, Codex, Cursor, Gemini CLI),
the first five are installed as skills of the same name under `.agents/skills/`;
`sdlc-doctor` is already a skill. The table in `CARD.md` says what each name runs.

`.claude/skills/` holds the skills chosen for this project. They are model-invoked: an
agent loads one when the situation its description names appears — a request with no work
item, a claim about to be made, a release, an incident. They point back into `process/` and
`roles/` rather than restating them, so a skill cannot drift away from the standard it
enforces. Which ones are present depends on what this project is; `sdlc-intake`,
`sdlc-evidence-check`, `sdlc-charter-audit`, and `sdlc-adr` are installed everywhere.

Project-specific rules never go in either place — they go in `AGENTS.md` under "Project
overrides", or in `project/charter.md`, so that re-installing the kit cannot overwrite them.

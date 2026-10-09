# Plans

One file per Tier 1 work item: `{{PREFIX}}-###.md`, from `../../templates/plan.md`.

## What lands here

| Tier | Where the plan lives |
| --- | --- |
| 1 | A file here. It is the artifact the design review reads and the approval refers to. |
| 2 | Inline in the response, same content, summarised in the worklog entry. |
| 3 | One sentence in the response. |

A plan is not a description of the change — it is the reasoning that makes the change
reviewable: the approach, the alternatives rejected and why, the blast radius, the test
strategy, and what is deliberately *not* being done.

A plan the build then departs from is updated, not abandoned. Record the deviation and
why, in the plan and in the worklog entry — in the same commit as the change that departs,
so the plan never describes code that does not exist. `python3 .ai-sdlc/bin/sdlc.py
plan-check <ID>` compares the plan's "Files that change" with the branch's diff and lists
the gaps; `/sdlc-review` runs it before the conformance pass.

Full rules: `../../process/00-operating-model.md` (step 2, PLAN).

## Index

| Work item | Title | Status |
| --- | --- | --- |
| | | |

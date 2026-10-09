---
status: draft
owner: _(role)_
last-reviewed: YYYY-MM-DD
---

# Plan — {{PREFIX}}-### <title>

**Tier:** 1 | 2 | 3 **Effort:** Lean | Normal | Beast **Depends on:** _(IDs, or none)_

## Problem

_(What is wrong or missing today, for whom, and what it costs them. Not the solution.)_

## Outcome

_(One sentence: what will be true afterwards that is not true now, stated observably. Or
link to upstream spec: `specs/...md`)_

## Approach

_(How. Concrete enough that someone else could implement it. Name the actual files,
modules, endpoints, tables, or screens. Reference upstream specification if one exists.)_

## Files that change

_(One backticked path or glob per line — `src/billing/**`, `db/migrations/0042_*.sql`.
`sdlc.py plan-check` compares this list with the branch's diff, so a file the build touches
that is not here, or a file here the build never touched, is a question the reviewer asks.)_

- `path/or/glob`

## Order of work

_(Numbered steps in the order they land, each small enough to verify on its own. Say which
step is the riskiest.)_

1. _(step)_

## Alternatives rejected

| Option | Why not |
| --- | --- |
| _(the obvious one)_ | _(the real reason, not "not a good fit")_ |

## Affected surfaces

- **Code:** _(modules — the files themselves are listed under "Files that change")_
- **Data:** _(schema, migrations, backfills)_
- **Contracts:** _(APIs, events, formats others depend on)_
- **Docs to update:** _(which `project/` artifacts this will falsify)_

## Failure modes

_(What happens when the dependency is down, the input is hostile, the list is empty, two
people act at once, the migration half-applies.)_

## Test strategy

- **Acceptance criteria mapping:** _(which Given/When/Then scenarios or spec criteria map to tests)_
- **Unit:** _(what)_
- **Integration:** _(what boundary)_
- **Negative cases:** _(what must be refused — required for Tier 1)_
- **Manual:** _(what automation cannot judge)_
- **Proof:** _(the exact commands or checks whose passing output shows this is done — the
  evidence `/sdlc-verify` will record. For a defect, the reproducing test named here fails
  before the fix.)_

## Rollback

_(How this is undone, and whether that has ever been done.)_

## Out of scope

_(What this deliberately does not do. Anything here that someone might expect gets a
backlog ID.)_

## Assumptions

_(Each one also goes in `project/assumptions-and-risks.md`.)_

## Review

| Role | Verdict | Notes |
| --- | --- | --- |
| _(role)_ | Pass / Pass with conditions / Block | _(link to review file)_ |

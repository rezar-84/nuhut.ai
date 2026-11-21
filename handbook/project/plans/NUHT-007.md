---
status: draft
owner: architect
last-reviewed: 2026-11-21
---

# Plan — NUHT-007 Fresh-context review as a recorded independence level

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-005

## Problem

A review record has two independence values: `independent` (the reviewer's model family
differs from the author's) and `self-check` (everything else). In-session `/sdlc-review`
is always a self-check. The reviewer has the author's whole conversation, so it tends to
accept the author's reasoning. The NUHT-002 ship review shows the cost: a self-check passed
with plan globs that made `plan-check` unable to fail (re-review finding C1, an S3). The
later cross-family re-review caught it.

`sdlc.py review --by <harness>` already gives the reviewer only the role playbook, the diff,
the charter rows and the tier. That is a fresh-context review. But when the harness belongs
to the author's model family, the record still says `self-check`, with the same weight as an
in-session review. The kit cannot tell the two apart. So it has no way to ask for the
cheaper of the two independent kinds.

Prior art: Google's Elephant-Goldfish Model (Apache-2.0) makes fresh-context review its
only review kind and refuses to review in the author's context.

## Outcome

A review record says one of `independent`, `fresh-context` or `self-check`. The charter can
require a fresh-context review where it now requires nothing, and `/sdlc-review` starts a
subagent for Tier 1 design reviews by default. A cross-family review still counts as the
only `independent` kind.

## Approach

- `sdlc.py review` (`optional/runtime/sdlc.py`, `review()` and the record writer near
  line 1769). When the reviewer runs headless with only the prompt `review_prompt` builds,
  and its family matches the author's, record `fresh-context` rather than `self-check`.
  The label must not start with the word `independent`: `finish.py:467` matches
  `^independent\b`. Doctor's `check_identity` compares model families, so a same-family
  review already fails it. Neither may change.
- `review --stage design` sends the item's plan file in place of the diff. Today it
  sends only the diff (`review_prompt`), which is empty before the build, so a headless
  design review has nothing to read.
- A new charter row, **Fresh-context review required for**, with the values
  `none` · `Tier 1` · `Tier 1 and 2`. It defaults to `none`, so existing projects behave as
  they do now. `doctor` and `finish` treat `independent` as meeting it too.
- `/sdlc-review` (`.claude/commands/sdlc-review.md`, the generated `.agents/skills/`
  copies). For a Tier 1 design review, start a subagent with only the plan, the playbooks
  and the charter rows, and record the result through `sdlc.py review --by cmd:` so the
  record is written by the runtime, not by hand. A harness without subagents records a
  self-check and says so. It does not stop the review.
- `sdlc.py config --fresh-review` and the viewer's Kit Control panel get the new row, the
  same way `--independent-review` works now.
- `02-role-reviews.md` "Independent review" gets the three levels and what each clears.

## Spec changes

none. The kit does not use its own Specs row.

## Files that change

- `optional/runtime/sdlc.py`
- `optional/runtime/finish.py`
- `optional/runtime/view/js/**`
- `optional/runtime/view.html`
- `.ai-sdlc/bin/sdlc.py`
- `.ai-sdlc/bin/finish.py`
- `.ai-sdlc/bin/view.html`
- `template/docs/process/02-role-reviews.md`
- `template/docs/project/charter.md`
- `handbook/process/02-role-reviews.md`
- `.claude/commands/sdlc-review.md`
- `optional/claude-commands/sdlc-review.md`
- `install.py`
- `tests/smoke.py`
- `docs/cli.md`
- `CHANGELOG.md`

## Order of work

1. Tests: a same-family `review --by cmd:` records `fresh-context`; a fresh-context record
   does not clear `Independent review required for: Tier 1`; it does clear
   `Fresh-context review required for: Tier 1`; an `independent` record clears both.
2. The runtime label and the charter row (`independent_review_policy` gets a sibling).
   **Riskiest step**: every place that reads `Independence` must keep treating only
   `independent` as independent.
3. `config`, the Kit Control panel and the installer's charter default.
4. `/sdlc-review` subagent dispatch and the handbook text.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Count a fresh-context review as `independent` | It shares the author model's blind spots. It would quietly lower the bar that projects set with `Independent review required for`. |
| Make fresh-context the default for every Tier 1 review | Token cost on every project, with no opt-in. A default of `none` keeps upgrades silent, as the 4.x independent-review default did. |
| Stop the review when the harness has no subagents (EGM's rule) | It blocks the loop in Gemini CLI and Cursor setups. Recording a self-check is honest and keeps work moving. |

## Affected surfaces

- **Code:** review recording, the doctor gate, finish, config, viewer Kit Control.
- **Data:** a new value in review-record headers. Old records stay valid: `self-check` and
  `independent` keep their meaning.
- **Contracts:** the charter gains a row. `sdlc.py review --json` gains a value for
  `independence`. Both are contracts installed projects consume, which is why this is Tier 1.
- **Docs to update:** `02-role-reviews.md`, `docs/cli.md`, the charter template, CHANGELOG.

## Failure modes

- A hand-written review file claims `fresh-context` with no runtime record. Doctor accepts
  only labels the runtime wrote (a review file with a `**Reviewed:**` line from
  `sdlc.py review`). A hand-written claim counts as a self-check.
- The author's model is unknown (no trailers). The label is `self-check`, as it is now.
- A charter written by an older kit has no new row. Treat it as `none`.

## Test strategy

- **Acceptance criteria mapping:** the four checks in step 1.
- **Design stage:** `review --stage design` on an item with a plan and no commits sends
  the plan text, and refuses when there is no plan.
- **Unit:** `independent_review_policy` and its sibling parse every value, including
  blank and malformed ones.
- **Integration:** `tests/smoke.py`: install, author a commit with trailers, review with
  `--by cmd:` as the same family, then `doctor` and `finish`.
- **Negative cases:** a `fresh-context` record must not clear the independent gate. A
  hand-edited `Independence: fresh-context` line without runtime provenance must not clear
  the fresh-context gate. A malformed charter value is refused by `config`.
- **Manual:** run `/sdlc-review` on a Tier 1 design in Claude Code and confirm a subagent
  ran and the record came from the runtime.
- **Proof:** `python3 .ai-sdlc/bin/sdlc.py verify --item NUHT-007`.

## Rollback

Revert the commits. Records written with `fresh-context` would then read as unknown labels,
which the old code already treats as not independent. Not yet rehearsed.

## Out of scope

- Several reviewer copies per role (EGM's A/B runs). Revisit after this is used.
- Fresh-context ship reviews by default.

## Assumptions

- The headless `review` prompt carries no author conversation. Verified by reading
  `review_prompt` (`optional/runtime/sdlc.py:1710`): it holds the playbook, diff, charter
  rows and tier only.

## Review

| Role | Verdict | Notes |
| --- | --- | --- |
| architect | _(pending)_ | Design review not run. Parked for owner approval first. |

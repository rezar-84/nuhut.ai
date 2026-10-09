<!-- Copy this block to the TOP of docs/project/worklog.md. Newest first. -->

For Tier 3, use this compact form unless the change uncovers risk, a durable decision,
or unresolved work:

```markdown
- YYYY-MM-DD · {{PREFIX}}-### · <request> · effort: Lean|Normal|Beast · changed: <files> · verified: <command/result>
  · deferred: nothing | <follow-up ID and reason>
```

Tier 1 and Tier 2 use the full entry below.

## {{PREFIX}}-### — <title>

**Date:** YYYY-MM-DD **Tier:** 1|2|3 **Effort:** Lean|Normal|Beast
**Status:** Done | Partial | Parked | Reverted
_(`Done` and `Parked` must match the backlog row. `Partial` and `Reverted` describe this
entry only; the row stays open at the loop step actually reached — `In progress` before
VERIFY, `In review` after — and this entry says which and why.)_
**Branch/commits:** `<branch>` / `<range>`

### What changed

_(Plain language, readable by someone who was not here and does not know the codebase.)_

### Why

_(The reasoning. Especially where the obvious approach was rejected, or where the result
looks strange without the context.)_

### Verified

_(Actual commands and actual results. Not "tests pass".)_

```
<command>
<real output, or a faithful summary: "142 passed, 0 failed, 3 skipped">
```

_(One line for each of the ten check stages in `../process/04-quality-gates.md`, in that
order — all of them, including the ones that did not run. The charter's Commands table
supplies the command for each; its `Install` and `Run locally` rows are not stages and are
not reported here. A stage missing from this record is indistinguishable from one that
passed. Use the six words from `../process/06-evidence-and-claims.md`: Verified ·
Reported · Assumed · Unknown · Not run · Absent — plus *Measured* for a score, latency,
or freshness number, which carries its method, subject version, N, spread, and date.)_

- [x] `checks.lint` — Verified — _(result)_
- [ ] `checks.integration` — **Not run** — _(why, and what would be needed)_
- [ ] `checks.e2e` — **Absent** — _(the charter names no command; this is a QA finding,
  not a neutral fact)_
- [x] manual — _(what you actually did, in what environment, in what states)_

### Not done

_(Deferred, stubbed, mocked, hardcoded, or partially implemented — each with a follow-up
ID. This is the section future readers need most and the one most often left out. If
there is genuinely nothing, write "nothing deferred".)_

- _(thing)_ → {{PREFIX}}-###

### Discovered

_(Pre-existing bugs found, docs found stale, assumptions refuted, surprises. Include what
you did not fix — especially what you did not fix.)_

### Decisions

_(Anything durable. Link the ADR if one was written; if a decision was durable and no ADR
was written, say why.)_

### Assumptions used

_(From `assumptions-and-risks.md`. What breaks if any of them is wrong.)_

### Plan

_(Tier 1: link the file in `project/plans/`. Tier 2: the plan itself belongs here — the
approach, the alternatives rejected and why, and what you deliberately did not do. This
is the only durable home a Tier 2 plan gets, and `07-traceability.md` requires the chain
`ID → plan` to be walkable.)_

### Reviews

_(Every role engaged, its verdict, and its findings. Tier 1: link
`project/reviews/{{PREFIX}}-###-*.md`. Tier 2: the verdicts go here, in full — Tier 2
writes no review file, so this section is the record `03-ready-and-done.md` means when it
requires verdicts to be recorded.)_

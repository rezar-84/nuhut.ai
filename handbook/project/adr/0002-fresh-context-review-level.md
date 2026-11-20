---
status: proposed
owner: rezar-84
last-reviewed: 2026-11-21
---

# ADR 0002 — A third review independence level: fresh context

- **Status:** Proposed
- **Date:** 2026-11-21
- **Deciders:** rezar-84
- **Work item:** NUHT-007

## Context

A review record says `independent` (the reviewer's model family differs from the
author's) or `self-check` (anything else). A same-family reviewer started with no
conversation history, as `sdlc.py review --by` already does, is recorded as a self-check.
So the kit gives it the same weight as a review written in the author's own session. On
`kit-v5` an in-session self-check passed a plan whose globs made `plan-check` vacuous. A
cross-family re-review caught it (NUHT-002 ship re-review, finding C1).

## Decision

Review records get a third value, `fresh-context`. It means the same model family as the
author, but a runtime-started reviewer that saw only the playbook, the charter rows and the
plan or diff. A new charter row, **Fresh-context review required for** (default `none`),
can require it. `independent` meets both gates. `fresh-context` never meets the
`Independent review required for` gate.

## Consequences

- Projects can ask for context isolation without needing a second model vendor.
- The label does not start with `independent`, so the existing gate checks
  (`^independent\b`) are unchanged.
- Hand-written review files cannot claim the new level. Only runtime-written records count.
- One more charter row, and one more value in `review --json`. Both are contracts installed
  projects consume.

## Version facts

No external versions are involved.

## Alternatives considered

### Treat fresh-context as independent

Rejected. It would quietly lower the bar projects set when they chose cross-family review.

### Require fresh context for every Tier 1 review by default

Rejected for now. It costs tokens on every project without anyone opting in, and it changes
behaviour on upgrade.

## Reversibility

Reverting the code leaves records carrying an unknown label. The current code already reads
an unknown label as not independent. The charter row is ignored by older runtimes.

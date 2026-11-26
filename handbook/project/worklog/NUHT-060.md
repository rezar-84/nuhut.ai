## NUHT-060 — review's item diff sweeps in other items' commits made between the item's first and last (touch: optional/runtime/sdlc.py, tests/smoke.py)

**Date:** 2026-11-26 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `aacf832..aacf832`

### What changed

- fix(NUHT-060): review's diff holds only the item's own commits (aacf832)

Files: `CHANGELOG.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

The review diff spanned the item's first to last commit, sweeping in other items' work; reviewers judged unrelated code and long branches overflowed the CLI argument limit. Rejected: passing the prompt on stdin only, which fixes the length but not the scope.

### Verified

- `checks.lint` — Verified: pass — run 20261126T054525Z, commit aacf832
- `checks.unit` — Verified: pass — run 20261126T054525Z, commit aacf832
- `checks.build` — Verified: pass — run 20261126T054525Z, commit aacf832

### Not done

Prompts are still passed as a CLI argument; a very large item could still exceed the limit.

### Discovered

Four ship reviews failed with Argument list too long; the NUHT-024 review covered other items' code.

### Decisions

none

### Assumptions used

An item's work is exactly the commits carrying its Work-Item trailer.

### Plan

Inline: item_diff joins each item commit's diff against its parent; tested in test_review_diff_scope.

### Reviews

software-engineer (same session, not independent): Pass

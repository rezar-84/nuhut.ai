## NUHT-058 — Fast verify labels stages the charter declares absent as Not run (touch: optional/runtime/sdlc.py, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `2a08043..2a08043`

### What changed

- fix(NUHT-058): a fast run reports declared-absent stages as Absent (2a08043)

Files: `CHANGELOG.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

Stages the charter declares absent were labelled Not run (fast verify), which suggests CI covers a stage that does not exist.

### Verified

- `checks.lint` — Verified: pass — run 20261125T111737Z, commit 2a08043
- `checks.unit` — Verified: pass — run 20261125T111737Z, commit 2a08043
- `checks.build` — Verified: pass — run 20261125T111737Z, commit 2a08043

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

Inline: verify checks absent and blank stages before the fast-mode skip; tested in test_fast_verify.

### Reviews

software-engineer (same session, not independent): Pass

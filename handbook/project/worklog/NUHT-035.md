## NUHT-035 — Move smoke tests to unittest with selection, a fast unit tier and a parallel pty tier (touch: tests/)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `0bd719a..8964d1e`

### What changed

- fix(NUHT-035): hold the semver unit tests to the 6.0 release levels (8964d1e)
- Merge branch 'v6/NUHT-035' into kit-v6 (8977ae1)
- feat(NUHT-035): add tests/run.py runner and tests/unit parser tests (0bd719a)

Files: `tests/unit/test_semver.py`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/install.md`, `tests/smoke.py`, `.github/workflows/ci.yml`, `tests/run.py`, `tests/unit/_paths.py`, `tests/unit/test_plan_parsing.py`, `tests/unit/test_review_responses.py`

### Why

tests/run.py adds --only, --list and --jobs; tests/unit/ holds unittest cases. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T113710Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T113710Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T113710Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T113710Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

tests/run.py adds --only, --list and --jobs; tests/unit/ holds unittest cases. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-015 — install.sh version floor and wording; finish swallows exceptions silently (touch: install.sh, optional/runtime/finish.py, tests/smoke.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `f4b3b14..20baa89`

### What changed

- test(NUHT-015): commit the finish-error fixtures with a Work-Item trailer (20baa89)
- fix(NUHT-015): require Python 3.8 in install.sh and report unexpected finish failures (f4b3b14)

Files: `tests/smoke.py`, `CHANGELOG.md`, `install.sh`, `optional/runtime/finish.py`

### Why

install.sh checks Python 3.8+ with correct wording; finish reports the exceptions it used to swallow. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T083446Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T083446Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T083446Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T083446Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

install.sh checks Python 3.8+ with correct wording; finish reports the exceptions it used to swallow. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

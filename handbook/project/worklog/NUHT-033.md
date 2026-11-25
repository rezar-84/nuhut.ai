## NUHT-033 — Standards discovery: extract codebase conventions via lens

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `49a3967..49a3967`

### What changed

- feat(NUHT-033): standards discovery in sdlc.py lens --area standards (49a3967)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/lens.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

lens --area standards extracts codebase conventions. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T111906Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T111906Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T111906Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T111906Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

lens --area standards extracts codebase conventions. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

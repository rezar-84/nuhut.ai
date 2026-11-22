## NUHT-028 — Hotfix fast path with a doctor check for the retroactive review (touch: optional/runtime/sdlc.py, template/docs/process/05-change-control.md)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `a2f0a6f..bf8d00c`

### What changed

- test(NUHT-028): commit the hotfix fixtures with a Work-Item trailer (bf8d00c)
- feat(NUHT-028): hotfix fast path with a retroactive review check in doctor (a2f0a6f)

Files: `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `handbook/process/05-change-control.md`, `handbook/templates/postmortem.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `template/docs/process/05-change-control.md`, `template/docs/project/charter.md`, `template/docs/templates/postmortem.md`

### Why

hotfix marks the fast path; doctor flags a hotfix without a retroactive review inside the charter window. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T103309Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T103309Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T103309Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T103309Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

hotfix marks the fast path; doctor flags a hotfix without a retroactive review inside the charter window. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

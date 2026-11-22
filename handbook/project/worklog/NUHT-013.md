## NUHT-013 — Test-lock and protected-path guards miss shell writes (sed -i, redirects, tee, python -c) (touch: optional/runtime/hooks.py, tests/smoke.py, template/docs/process/05-change-control.md)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `1031fcc..ecee839`

### What changed

- fix(NUHT-013): see interpreter and archive writes; widen the trust anchors (ecee839)
- feat(NUHT-013): guard locked and protected paths against shell writes (1031fcc)

Files: `handbook/process/05-change-control.md`, `optional/runtime/hooks.py`, `template/docs/process/05-change-control.md`, `tests/smoke.py`, `CHANGELOG.md`, `optional/git-hooks/pre-commit`

### Why

The shell guard recognises sed -i, redirects, tee, interpreters with inline code, rsync, tar, patch and git apply against locked paths. Rejected: blocking all shell writes, which breaks normal work. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T081641Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T081641Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T081641Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T081641Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

The shell guard recognises sed -i, redirects, tee, interpreters with inline code, rsync, tar, patch and git apply against locked paths. Rejected: blocking all shell writes, which breaks normal work. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-032 — Worktree setup/run scripts for claim and dispatch

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `82193fc..e3d1222`

### What changed

- fix(NUHT-032): never allocate a port without the lock; no empty worktrees (e3d1222)
- feat(NUHT-032): run worktree setup and teardown scripts on claim, release and dispatch (82193fc)

Files: `optional/runtime/claims.py`, `tests/smoke.py`, `CHANGELOG.md`, `docs/cli.md`, `docs/multi-agent.md`, `handbook/process/10-multi-agent.md`, `optional/runtime/dispatch.py`, `optional/runtime/sdlc.py`, `template/docs/process/10-multi-agent.md`, `template/docs/project/charter.md`

### Why

claim and dispatch run per-worktree setup and teardown scripts; a timed-out port lock refuses the claim. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T110954Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T110954Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T110954Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T110954Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

claim and dispatch run per-worktree setup and teardown scripts; a timed-out port lock refuses the claim. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

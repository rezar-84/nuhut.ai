## NUHT-034 — Webhook notifications for blocked, approval-needed and review-blocking events

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `33a0ac9..33a0ac9`

### What changed

- feat(NUHT-034): webhook notifications for parked, review-blocked and approval-needed items (33a0ac9)

Files: `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/extensions.md`, `install.py`, `optional/runtime/finish.py`, `optional/runtime/net.py`, `optional/runtime/notify.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

notify sends webhooks for blocked, approval-needed and review-blocking events. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T112811Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T112811Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T112811Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T112811Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

notify sends webhooks for blocked, approval-needed and review-blocking events. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-023 — People registry: owner and claims name humans (touch: optional/runtime/shards.py, optional/runtime/claims.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `5e417d9..5e417d9`

### What changed

- feat(NUHT-023): people registry for owners, claims, doctor and the viewer (5e417d9)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/claims.py`, `optional/runtime/dispatch.py`, `optional/runtime/sdlc.py`, `optional/runtime/status.py`, `optional/runtime/view.html`, `optional/runtime/view.py`, `optional/runtime/view/js/04-helpers.js`, `optional/runtime/view/js/12-dashboard.js`, `optional/runtime/view/js/15-dashboard-doctor.js`, `optional/runtime/view/js/17-tooltip-drawer.js` (+3 more)

### Why

people.json maps git identities and logins to people; owner and claims name them; status reports a missing entry. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T094749Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T094749Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T094749Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T094749Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

people.json maps git identities and logins to people; owner and claims name them; status reports a missing entry. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-021 — Split sdlc.py command routing into a command table (touch: optional/runtime/sdlc.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `7626276..041f8be`

### What changed

- fix(NUHT-021): keep the COMMANDS table test off the core deploy group (041f8be)
- refactor(NUHT-021): route sdlc.py subcommands through a COMMANDS table (7626276)

Files: `docs/cli.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `CHANGELOG.md`

### Why

sdlc.py routes through a command table instead of an if chain. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T092942Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T092942Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T092942Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T092942Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

sdlc.py routes through a command table instead of an if chain. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-025 — Merge driver for item shards; rendered backlog and worklog gitignored (touch: optional/runtime/shards.py, install.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `4130b73..8e128c9`

### What changed

- fix(NUHT-025): the guided preview counts the .gitattributes lines it will write (8e128c9)
- test(NUHT-025): status reports the installed nuhut-shard driver until fix merge-driver (e4b01ce)
- feat(NUHT-025): field-level merge driver for item shards (4130b73)

Files: `install.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/multi-agent.md`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`

### Why

merge-shard driver and fix merge-driver; rendered backlog and worklog gitignored; the guided preview counts the .gitattributes lines. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

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

merge-shard driver and fix merge-driver; rendered backlog and worklog gitignored; the guided preview counts the .gitattributes lines. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

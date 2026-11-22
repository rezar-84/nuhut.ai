## NUHT-040 — Bugs agents notice: sdlc.py bug, severity on items, open S0-S2 in status and at session start, touch-path warnings, generated defects index (touch: optional/runtime/sdlc.py, optional/runtime/shards.py, optional/runtime/status.py, optional/runtime/hooks.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `7754d1c..7754d1c`

### What changed

- feat(NUHT-040): sdlc.py bug, defect severity, open defects at session start and in status (7754d1c)

Files: `CHANGELOG.md`, `README.md`, `docs/cli.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `optional/runtime/status.py`, `tests/smoke.py`

### Why

sdlc.py bug with severity and a filled defect report; severity and found_by on shards; render builds the defects index; status and guard start show open S0-S2; claim warns on overlapping touch paths. Rejected: an edit-time hook warning (hook rule plumbing; claim time reaches the agent before it edits).

### Verified

- `checks.lint` — Verified: pass — run 20261122T122406Z, commit 489e0f7
- `checks.unit` — Verified: pass — run 20261122T122406Z, commit 489e0f7
- `checks.integration` — Verified: pass — run 20261122T122406Z, commit 489e0f7
- `checks.build` — Verified: pass — run 20261122T122406Z, commit 489e0f7

### Not done

doctor warning for open defects with no severity (proposed under NUHT-041)

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

sdlc.py bug with severity and a filled defect report; severity and found_by on shards; render builds the defects index; status and guard start show open S0-S2; claim warns on overlapping touch paths. Rejected: an edit-time hook warning (hook rule plumbing; claim time reaches the agent before it edits).

### Reviews

self-reviewed

## NUHT-030 — Issue-tracker sync extension: GitHub Issues, then Linear and Jira

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `36bc9d9..5c9afc5`

### What changed

- fix(NUHT-030): link items by issue title only for mapped authors (5c9afc5)
- feat(NUHT-030): issues pull|push through gh as the github-issues built-in extension (36bc9d9)

Files: `optional/extensions/github-issues/issues.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/extensions.md`, `optional/extensions/github-issues/nuhut-extension.json`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`

### Why

github-issues extension pulls issues into the backlog; titles link items only for authors mapped in people.json. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T105137Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T105137Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T105137Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T105137Z, commit 8e128c9

### Not done

Linear and Jira extensions; a person copies issues.py into .ai-sdlc/extensions/github-issues/ (trust anchor)

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

github-issues extension pulls issues into the backlog; titles link items only for authors mapped in people.json. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

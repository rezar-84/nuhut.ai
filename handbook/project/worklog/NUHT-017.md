## NUHT-017 — Move claude, codex, gemini, cursor support into built-in extensions (one agent table) (touch: optional/extensions/, install.py, optional/runtime/sdlc.py, optional/runtime/dispatch.py, optional/runtime/hooks.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `5378114..5378114`

### What changed

- refactor(NUHT-017): move claude, codex, gemini and cursor support into the built-in extensions (5378114)

Files: `CHANGELOG.md`, `docs/cli.md`, `docs/harnesses.md`, `install.py`, `optional/extensions/claude/nuhut-extension.json`, `optional/extensions/codex/nuhut-extension.json`, `optional/extensions/cursor/nuhut-extension.json`, `optional/extensions/gemini/nuhut-extension.json`, `optional/runtime/dispatch.py`, `optional/runtime/hooks.py`, `optional/runtime/lens.py`, `optional/runtime/registry.py` (+4 more)

### Why

Claude, Codex, Gemini and Cursor moved into built-in extensions read by registry.py, replacing the hard-coded tables. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T085317Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T085317Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T085317Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T085317Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

ADR 0003 (Proposed)

### Assumptions used

none

### Plan

Claude, Codex, Gemini and Cursor moved into built-in extensions read by registry.py, replacing the hard-coded tables. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

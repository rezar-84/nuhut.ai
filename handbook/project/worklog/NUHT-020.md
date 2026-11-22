## NUHT-020 — New harness extensions: OpenCode, Kiro, ACP agents (no core changes) (touch: optional/extensions/)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `c996665..01555ab`

### What changed

- docs(NUHT-020): --by names every registry agent, not three tools (01555ab)
- feat(NUHT-020): OpenCode, Kiro and ACP agents as data-only built-in extensions (c996665)

Files: `docs/cli.md`, `optional/runtime/sdlc.py`, `CHANGELOG.md`, `docs/harnesses.md`, `optional/extensions/acp/nuhut-extension.json`, `optional/extensions/core/nuhut-extension.json`, `optional/extensions/kiro/nuhut-extension.json`, `optional/extensions/opencode/nuhut-extension.json`, `tests/smoke.py`, `validate.py`

### Why

OpenCode, Kiro and ACP added as data-only extensions with no core change. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T092033Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T092033Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T092033Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T092033Z, commit 8e128c9

### Not done

real-CLI format checks for OpenCode, Kiro and ACP (NUHT-036)

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

OpenCode, Kiro and ACP added as data-only extensions with no core change. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-018 — ext CLI: list, add, remove, update, search, validate; overlays; catalog (touch: optional/runtime/registry.py, optional/runtime/sdlc.py, docs/cli.md)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `fba9d5e..4b3a2d0`

### What changed

- fix(NUHT-018): ask before ext update runs new code; find ext in --help (4b3a2d0)
- feat(NUHT-018): sdlc.py ext CLI, Extensions allowed gate, pinned code, overlays, catalog (fba9d5e)

Files: `docs/cli.md`, `docs/extensions.md`, `optional/runtime/ext.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `catalog.json`, `install.py`, `optional/runtime/finish.py`, `optional/runtime/hooks.py`, `optional/runtime/net.py` (+3 more)

### Why

ext list/add/remove/update/search/validate with hash pins and an Extensions allowed charter row; update prompts before re-pinning changed code. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T090221Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T090221Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T090221Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T090221Z, commit 8e128c9

### Not done

catalog 404 ends when catalog.json reaches main

### Discovered

nothing

### Decisions

ADR 0003 (Proposed)

### Assumptions used

none

### Plan

ext list/add/remove/update/search/validate with hash pins and an Extensions allowed charter row; update prompts before re-pinning changed code. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

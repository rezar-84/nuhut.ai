## NUHT-031 — MCP server extension: backlog, verify, finish, doctor as tools (stdlib JSON-RPC)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `1e93fb1..5a813bd`

### What changed

- fix(NUHT-031): keep install.py --help within its 60 lines (5a813bd)
- Merge branch 'v6/NUHT-031' into kit-v6 (17bed63)
- feat(NUHT-031): serve the records as read-only MCP tools over stdio (1e93fb1)

Files: `install.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/install.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `optional/runtime/mcp_server.py`

### Why

sdlc.py mcp serves backlog, verify, finish and doctor over stdio JSON-RPC, stdlib only. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T110044Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T110044Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T110044Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T110044Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

sdlc.py mcp serves backlog, verify, finish and doctor over stdio JSON-RPC, stdlib only. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

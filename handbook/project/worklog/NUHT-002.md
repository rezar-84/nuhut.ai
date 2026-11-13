## NUHT-002 — M2: Sharded zero-conflict store, git-ref leases, Tier 2 parallel scope globs, universal --json & cached doctor

**Date:** 2026-11-13 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Branch/commits:** `kit-v5` / `c5118ca..4fc0cb8`

### What changed

- chore(NUHT-003): sync profile commands and record NUHT-001..002 ledger shards (4fc0cb8)
- feat(runtime): sharded zero-conflict store, git-ref CAS leases, universal --json, and incremental doctor cache (c5118ca)

Files: `README.md`, `docs/cli.md`, `install.py`, `optional/runtime/claims.py`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `optional/runtime/view.py`, `tests/smoke.py`

### Why

Replaced single-file multi-agent bottlenecks with sharded items/, worklog/, and ledger/ records, git-ref CAS leases, Tier 2 touch globs, universal --json, and <500ms cached doctor.

### Verified

- `checks.lint` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.unit` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.integration` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.build` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8

### Not done

nothing deferred

### Discovered

nothing

### Decisions

ADR 0001: per-item JSON/Markdown/JSONL shards with transparent 4.x fallback

### Assumptions used

Git 2.20+ available for worktrees and --force-with-lease ref pushes

### Plan

[NUHT-002.md](plans/NUHT-002.md)

### Reviews

- [NUHT-002-design.md](reviews/NUHT-002-design.md)
- [NUHT-002-ship.md](reviews/NUHT-002-ship.md)

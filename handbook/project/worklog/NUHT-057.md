## NUHT-057 — finish --commit: the item's records go in one commit with its trailers (touch: optional/runtime/sdlc.py, optional/claude-commands/sdlc-finish.md, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `61fd7d2..61fd7d2`

### What changed

- feat(NUHT-057): finish --commit commits the item's records (61fd7d2)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/claude-commands/sdlc-finish.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

Each item needed a hand-written bookkeeping commit for its ledger, worklog and status, costing a step per item and inviting mistakes (one was committed as Done before finish passed). finish --commit commits exactly those records with the item's trailers. Rejected: making it the default, which would surprise people who commit records with their code.

### Verified

- `checks.lint` — Verified: pass — run 20261125T111535Z, commit 61fd7d2
- `checks.unit` — Verified: pass — run 20261125T111535Z, commit 61fd7d2
- `checks.build` — Verified: pass — run 20261125T111535Z, commit 61fd7d2

### Not done

nothing deferred

### Discovered

Fast verify labels stages the charter declares absent as Not run (fast verify) instead of Absent; fixed next.

### Decisions

none

### Assumptions used

Records finish writes live under <docs>/project/ (items, worklog, ledger); ledger shard names carry the item ID.

### Plan

Inline: finish_record_paths picks the item's shard, worklog entry and ledger shards from git status; commit_finish_records commits only those paths. Tested in test_finish_commit.

### Reviews

software-engineer (same session, not independent): Pass

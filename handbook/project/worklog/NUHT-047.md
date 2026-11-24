## NUHT-047 — status and parallel offer Ready items that already have code commits (touch: optional/runtime/claims.py, optional/runtime/status.py, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `678eb11..678eb11`

### What changed

- fix(NUHT-047): built Ready items are not offered as Ready to take (678eb11)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/claims.py`, `optional/runtime/status.py`, `tests/smoke.py`

### Why

Seven Tier 1 items with code on kit-v6 were listed as Ready to take, so `status`, `parallel` and `dispatch` invited a second build. The check sits in `claims.parallel()` because all three read it. Rejected: a new "Built" status value, which changes the shard schema and the viewer's columns (Tier 1). The item stays Ready, and its commits decide where it is listed.

### Verified

- `checks.lint` — Verified: pass — run 20261124T213544Z, commit 678eb11
- `checks.unit` — Verified: pass — run 20261124T213544Z, commit 678eb11
- `checks.integration` — Verified: pass — run 20261124T213544Z, commit 678eb11
- `checks.build` — Verified: pass — run 20261124T213544Z, commit 678eb11

### Not done

The viewer's parallel panel does not show the new `built` list yet; nothing reads it there. `commit_paths` is not cached, so this is one `git diff-tree` per commit of a Ready item with commits (it stops at the first code change).

### Discovered

NUHT-048: `-y` installs keep detected check commands only in profile.json. The review's claim that the commit hook acts on other repos was wrong (commits to a literal `cd`/`-C` target are skipped); the guards do block harmless commands, such as `git commit -m` inside a quoted string.

### Decisions

none

### Assumptions used

A commit whose only changed paths are under `<docs>/project/` is bookkeeping, as `newest_code_commit` already assumes.

### Plan

[NUHT-047.md](plans/NUHT-047.md)

### Reviews

software-engineer (same session, not independent): Pass. The check runs only for unclaimed Ready items, and existing parallel, dispatch and status tests pass in the full run.

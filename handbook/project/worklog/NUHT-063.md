## NUHT-063 — Approvals survive finish's records commit and stale merged item branches; another item's run is not evidence (touch: optional/runtime/finish.py, optional/runtime/sdlc.py, tests/smoke.py)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `f30f476..92b77be`

### What changed

- test(NUHT-063): denial cases from the ship review (92b77be)
- fix(NUHT-063): approvals survive finish's records commit and stale item branches (f30f476)

Files: `tests/smoke.py`, `CHANGELOG.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`

### Why

The owner's approval loop left six items Parked: stale merged item branches and finish's own records commit voided approvals, and another item's failing run blocked NUHT-027. Approvals now bind to the newest code commit, a merged branch is not the merge candidate, and a run tagged for another item is never this item's evidence. Rejected: deleting the stale branches only, which would leave the trap for every project.

### Verified

- `checks.lint` — Verified: pass — run 20261126T063515Z, commit 92b77be
- `checks.unit` — Verified: pass — run 20261126T063515Z, commit 92b77be
- `checks.integration` — Verified: pass — run 20261126T063515Z, commit 92b77be
- `checks.build` — Verified: pass — run 20261126T063515Z, commit 92b77be

### Not done

nothing deferred

### Discovered

Importing the runtime in a test wrote __pycache__ into the test repository and dirtied it; the import now turns bytecode off.

### Decisions

none

### Assumptions used

Records-only means every changed path is under <docs>/project/ other than the charter.

### Plan

[NUHT-063.md](plans/NUHT-063.md)

### Reviews

- [NUHT-063-ship-security.md](reviews/NUHT-063-ship-security.md)

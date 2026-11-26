## NUHT-024 — Approvals read from GitHub PR reviews instead of charter names (touch: optional/runtime/finish.py)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `08dfad3..a03f7ec`

### What changed

- docs(NUHT-024): ship review and responses (a03f7ec)
- fix(NUHT-024): approvals needs none outside Tier 1 and Strict Tier 2 (5528b9a)
- feat(NUHT-024): read Tier 1 approvals from the item branch's GitHub PR reviews (08dfad3)

Files: `docs/cli.md`, `optional/runtime/finish.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `handbook/process/05-change-control.md`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `template/docs/process/05-change-control.md`, `template/docs/project/charter.md`

### Why

Tier 1 approvals were names typed into the charter. finish now reads GitHub PR reviews on the item branch's head and counts only Approvers who are not the author. Rejected: counting any approving review, which let a non-approver or the author approve.

### Verified

- `checks.lint` — Verified: pass — run 20261122T095655Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T095655Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T095655Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T095655Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

A PR with no readable author and an unreadable tier were counted too leniently (fixed in NUHT-061).

### Decisions

ADR 0004 for the findings declined in its review.

### Assumptions used

none

### Plan

[NUHT-024.md](plans/NUHT-024.md)

### Reviews

- [NUHT-024-ship-security-2.md](reviews/NUHT-024-ship-security-2.md)
- [NUHT-024-ship-security.md](reviews/NUHT-024-ship-security.md)

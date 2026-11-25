## NUHT-041 — Block a release while an S1 defect is open

**Date:** 2026-11-25 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `2f58d0d..60286b9`

### What changed

- chore(NUHT-041): verify run on cf5f471 (60286b9)
- fix(NUHT-041): a fix counts only in this deploy's range; the ladder comes from the default branch (cf5f471)
- fix(NUHT-041): a fix is a trailer-attributed code commit; re-ratings bind to the report (eac27b8)
- feat(NUHT-041): an agent lowers an S0-S2 only after an independent blind re-rating (8ceeb17)
- feat(NUHT-041): deploy record refuses over open S0/S1 defects; S2 needs an approver's acceptance (2f58d0d)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/releases.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `optional/runtime/shards.py`, `README.md`

### Why

An agent could lower a blocking severity on its own word, and a release could ship over an open S0 or S1 defect. A downgrade now needs a person at a terminal, or a blind re-rating by another model family, and `deploy record` refuses open S0 and S1 defects unless this deploy's range carries their fix. Rejected: allowing any second agent to confirm, which a `cmd:` reviewer could fake.

### Verified

- `checks.lint` — Verified: pass — run 20261123T201711Z, commit 60286b9
- `checks.unit` — Verified: pass — run 20261123T201711Z, commit 60286b9
- `checks.integration` — Verified: pass — run 20261123T201711Z, commit 60286b9
- `checks.build` — Verified: pass — run 20261123T201711Z, commit 60286b9

### Not done

Signed re-ratings were dropped under ADR 0004 (NUHT-045).

### Discovered

Two security review rounds blocked on findings that records in the agent's environment can be forged; they were declined under ADR 0004 on 2026-11-25.

### Decisions

ADR 0004: re-ratings and approvals record intent; GitHub branch protection authenticates.

### Assumptions used

The trusted CARD.md severity ladder is read from the default branch.

### Plan

[NUHT-041.md](plans/NUHT-041.md)

### Reviews

- [NUHT-041-ship-security-2.md](reviews/NUHT-041-ship-security-2.md)
- [NUHT-041-ship-security.md](reviews/NUHT-041-ship-security.md)

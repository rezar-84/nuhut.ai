## NUHT-043 — Tier 1 approvals row (1 or 2), sdlc.py approve in a terminal, GitHub reviews only from Approvers (touch: optional/runtime/finish.py, optional/runtime/sdlc.py, optional/runtime/shards.py)

**Date:** 2026-11-25 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `e5a5de2..6ed35e3`

### What changed

- chore(NUHT-043): verify run on cf5f471 (6ed35e3)
- fix(NUHT-043): a local approval survives only bookkeeping commits (638e712)
- fix(NUHT-043): local approvals are opt-in and bound to the approved commit (ebbcb2c)
- feat(NUHT-043): Tier 1 approvals row (1 or 2), sdlc.py approve in a terminal, GitHub reviews only from Approvers (e5a5de2)

Files: `optional/runtime/finish.py`, `tests/smoke.py`, `template/docs/process/05-change-control.md`, `template/docs/project/charter.md`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`

### Why

A one-person project could never close Tier 1 work, because two GitHub approvals were required. The **Tier 1 approvals** row (1 or 2, read from the default branch) and opt-in local approvals from a terminal fix that. Rejected: counting a local approval as authentication, which a security review showed to be forgeable.

### Verified

- `checks.lint` — Verified: pass — run 20261123T200748Z, commit 60286b9
- `checks.unit` — Verified: pass — run 20261123T200748Z, commit 60286b9
- `checks.integration` — Verified: pass — run 20261123T200748Z, commit 60286b9
- `checks.build` — Verified: pass — run 20261123T200748Z, commit 60286b9

### Not done

Signed local approvals were dropped under ADR 0004 (NUHT-045).

### Discovered

Review findings 1, 2, 4 and 5 (unsigned records, no authenticated person) were declined under ADR 0004 on 2026-11-25.

### Decisions

ADR 0004: local approvals are records of intent and stay opt-in.

### Assumptions used

A GitHub review counts only from someone in Approvers on the default branch.

### Plan

[NUHT-043.md](plans/NUHT-043.md)

### Reviews

- [NUHT-043-ship-security-2.md](reviews/NUHT-043-ship-security-2.md)
- [NUHT-043-ship-security.md](reviews/NUHT-043-ship-security.md)

## NUHT-061 — Retro ship-review fixes: a newer failing run blocks finish; approvals fail closed on unknown authors and tiers (touch: optional/runtime/finish.py, tests/smoke.py, docs/cli.md)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Done
**Approved:** the owner; approved: rezar-84 (local)
**Branch/commits:** `kit-v6` / `5ce5a8f..f7a725c`

### What changed

- test(NUHT-061): ship review conditions (f7a725c)
- fix(NUHT-061): a newer failing run blocks finish; approvals fail closed (5ce5a8f)

Files: `tests/smoke.py`, `CHANGELOG.md`, `docs/cli.md`, `docs/multi-agent.md`, `optional/runtime/finish.py`

### Why

The retro ship reviews of the 6.0 items found gate bugs: a newer failing run was ignored after an older full pass, a PR with no readable author still counted reviews, and an unreadable tier needed no approvals. Each now fails closed. Rejected: fixing every finding in this item; the rest are tracked in NUHT-062.

### Verified

- `checks.lint` — Verified: pass — run 20261126T060150Z, commit f7a725c
- `checks.unit` — Verified: pass — run 20261126T060150Z, commit f7a725c
- `checks.integration` — Verified: pass — run 20261126T060150Z, commit f7a725c
- `checks.build` — Verified: pass — run 20261126T060150Z, commit f7a725c

### Not done

Deferred findings are in NUHT-062.

### Discovered

The shard loader turns an unreadable tier into 2 (tracked in NUHT-062). Running the full verify alongside a Codex review overloaded the machine and timed out a pty test.

### Decisions

ADR 0004 for the declined findings.

### Assumptions used

none

### Plan

[NUHT-061.md](plans/NUHT-061.md)

### Reviews

- [NUHT-061-ship-qa.md](reviews/NUHT-061-ship-qa.md)

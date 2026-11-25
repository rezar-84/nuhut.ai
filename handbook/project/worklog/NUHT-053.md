## NUHT-053 — Fast verify: Tier 2 and 3 close on the charter's fast stages; CI and Tier 1 run every stage (touch: optional/runtime/sdlc.py, optional/runtime/finish.py, template/docs/project/charter.md, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `d0d6175..319a3e4`

### What changed

- fix(NUHT-053): ship review round 1 (319a3e4)
- feat(NUHT-053): fast verify for Tier 2 and 3; CI and Tier 1 run every stage (d0d6175)

Files: `docs/cli.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `CHANGELOG.md`, `optional/runtime/finish.py`, `template/docs/project/charter.md`, `tests/run.py`

### Why

A full verify cost about 10 minutes per item here, locally and again in CI. The **Verify at finish** row lets Tier 2 and 3 items close on a fast set of stages, while CI runs every stage and Tier 1 keeps the full run. Rejected: selecting tests by changed files, which needs a map from source files to tests that no test runner gives the kit generically.

### Verified

- `checks.lint` — Verified: pass — run 20261125T070818Z, commit 319a3e4
- `checks.unit` — Verified: pass — run 20261125T070818Z, commit 319a3e4
- `checks.integration` — Verified: pass — run 20261125T070818Z, commit 319a3e4
- `checks.build` — Verified: pass — run 20261125T070818Z, commit 319a3e4

### Not done

No separate `ci-check` test for the fast path; it calls the same `verify_state` with the item's tier. This repository's fast mode takes effect when the charter row reaches `main`.

### Discovered

11 installer tests that drive a pty take about 300 of the suite's 600 seconds; `tests/run.py --fast` leaves them out. Review finding 1 (the note parsed as stages) did not reproduce, but the parser was hardened anyway.

### Decisions

ADR 0004: the omitted stages are enforced by the host's required CI job.

### Assumptions used

CI's job runs every charter stage; this repository's `ci.yml` runs `tests/smoke.py`.

### Plan

[NUHT-053.md](plans/NUHT-053.md)

### Reviews

- [NUHT-053-ship-qa.md](reviews/NUHT-053-ship-qa.md)

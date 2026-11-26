## NUHT-022 — ci-check: enforce trailers, ledger run on HEAD, review file and path-derived tier floor in PR CI (touch: optional/runtime/sdlc.py, install.py)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `20d7b8d..25f0816`

### What changed

- docs(NUHT-022): ship review and responses (25f0816)
- fix(NUHT-022): warn on Model: unknown; scaffold CI with no commands (2253924)
- feat(NUHT-022): ci-check judges a pull request's trailers, ledger, reviews and tier floor (20d7b8d)

Files: `docs/install.md`, `install.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/harnesses.md`, `docs/runtime.md`, `handbook/process/05-change-control.md`, `template/docs/process/05-change-control.md`, `template/docs/project/charter.md`

### Why

Nothing checked a pull request's records in CI. ci-check fails missing trailers, a missing ledger record on the item's newest code commit, a Tier 1 item without a review, and a tier lowered against the base. Rejected: running the PR's own checker, which a PR could edit.

### Verified

- `checks.lint` — Verified: pass — run 20261122T093843Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T093843Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T093843Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T093843Z, commit 8e128c9

### Not done

A scaffolded workflow with no check commands still passes (NUHT-062).

### Discovered

Base-checker selection was hardened later in NUHT-044.

### Decisions

ADR 0004 for the findings declined in its review.

### Assumptions used

none

### Plan

[NUHT-022.md](plans/NUHT-022.md)

### Reviews

- [NUHT-022-ship-devops-sre.md](reviews/NUHT-022-ship-devops-sre.md)

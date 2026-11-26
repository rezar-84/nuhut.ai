## NUHT-014 — Release pipeline: skip docs-only pushes, serialize runs, rebase before bot push, drop dead release.yml (touch: .github/workflows/version.yml, .github/workflows/release.yml, tools/semver.py)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `fcd573a..08e5063`

### What changed

- docs(NUHT-014): ship review and responses (08e5063)
- fix(NUHT-014): read BREAKING CHANGE from the whole footer block (fefac67)
- test(NUHT-014): skip the backlog record when looking for release.yml references (feff51f)
- feat(NUHT-014): release only on feat/fix/perf/refactor/revert, serialise the release job (fcd573a)

Files: `CHANGELOG.md`, `tests/unit/test_semver.py`, `tools/semver.py`, `validate.py`, `tests/smoke.py`, `.github/workflows/release.yml`, `.github/workflows/version.yml`, `CONTRIBUTING.md`, `docs/install.md`

### Why

Every push released, queued runs raced, and the bot pushed straight to main. Docs-only pushes now release nothing, runs are serialized, a superseded run stops, and the dead release.yml is gone. Rejected: release on tags only, which loses the automatic version bump.

### Verified

- `checks.lint` — Verified: pass — run 20261122T082541Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T082541Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T082541Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T082541Z, commit 8e128c9

### Not done

Resumable release creation, unit tests in the release job and multiline BREAKING CHANGE parsing (NUHT-062).

### Discovered

nothing new beyond the review's findings

### Decisions

ADR 0004 for the findings declined in its review.

### Assumptions used

none

### Plan

[NUHT-014.md](plans/NUHT-014.md)

### Reviews

- [NUHT-014-ship-devops-sre.md](reviews/NUHT-014-ship-devops-sre.md)

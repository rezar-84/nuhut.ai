## NUHT-046 — Pin GitHub Actions to commit SHAs and CI images to digests in ci.yml and the scaffolds

**Date:** 2026-11-25 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `e7f5396..f9816a1`

### What changed

- fix(NUHT-046): ship review round 1 (f9816a1)
- chore(NUHT-046): pin GitHub Actions to commit hashes (e7f5396)

Files: `tests/smoke.py`, `validate.py`, `.github/dependabot.yml`, `.github/workflows/ci.yml`, `.github/workflows/version.yml`, `CHANGELOG.md`, `install.py`

### Why

A tag can be moved to other code, and the workflows run with the repository token, including the release job that pushes to main. Actions are pinned to commit hashes with the version as a comment, Dependabot keeps them current, and validate.py refuses an unpinned action and a scaffold pin that drifts. Rejected: pinning the scaffolds' container images to digests, which would freeze adopters off security fixes.

### Verified

- `checks.lint` — Verified: pass — run 20261125T113252Z, commit f9816a1
- `checks.unit` — Verified: pass — run 20261125T113252Z, commit f9816a1
- `checks.integration` — Verified: pass — run 20261125T113252Z, commit f9816a1
- `checks.build` — Verified: pass — run 20261125T113252Z, commit f9816a1

### Not done

Container images in the GitLab and Bitbucket scaffolds stay on tags (see the plan).

### Discovered

nothing

### Decisions

none

### Assumptions used

Dependabot's github-actions ecosystem updates hash pins and their version comments together.

### Plan

[NUHT-046.md](plans/NUHT-046.md)

### Reviews

- [NUHT-046-ship-devops-sre.md](reviews/NUHT-046-ship-devops-sre.md)

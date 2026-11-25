## NUHT-011 — Self-install kit_version drifts from VERSION after a release (touch: validate.py, .github/workflows/version.yml, .ai-sdlc/manifest.json, .ai-sdlc/profile.json, AGENTS.md, tests/smoke.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `1e3693a..1e3693a`

### What changed

- fix(NUHT-011): restamp the self-install with VERSION on release (1e3693a)

Files: `.github/workflows/version.yml`, `CHANGELOG.md`, `tests/smoke.py`, `tools/semver.py`, `validate.py`

### Why

Release stamps the self-install (manifest, profile, AGENTS.md) and validate.py fails on drift. Rejected: running install.py --upgrade at release, which touches unrelated files. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T075825Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T075825Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T075825Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T075825Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

Release stamps the self-install (manifest, profile, AGENTS.md) and validate.py fails on drift. Rejected: running install.py --upgrade at release, which touches unrelated files. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

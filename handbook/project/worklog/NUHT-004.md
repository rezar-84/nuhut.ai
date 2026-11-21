## NUHT-004 — Release hygiene: CI Python 3.8 runner, installer names the unreleased version (touch: .github/workflows/ci.yml, install.py, tests/smoke.py, CHANGELOG.md, docs/install.md)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `3b18878..6ecebdc`

### What changed

- fix(NUHT-004): a shallow clone says its unreleased state is unknown (6ecebdc)
- fix(NUHT-004): run CI's Python 3.8 leg on ubuntu-22.04; installer names unreleased work (3b18878)

Files: `CHANGELOG.md`, `install.py`, `tests/smoke.py`, `.github/workflows/ci.yml`, `docs/install.md`

### Why

CI's 3.8 leg failed at setup-python on ubuntu-latest (24.04 has no 3.8 build), and installs from kit-v5 printed v4.0.0 with nothing saying the code was unreleased. Rejected: bumping VERSION to 5.0.0 by hand. tools/semver.py takes the last commit that changed VERSION as the release base, so a manual bump would leave the merge to main with nothing to release, and no v5.0.0 tag would be created. Rejected: stamping a dev version into the manifest, which would churn AGENTS.md and the manifest on every commit and break upgrade comparisons.

### Verified

- `checks.lint` — Verified: pass — run 20261120T235639Z, commit b34ee52
- `checks.unit` — Verified: pass — run 20261120T235639Z, commit b34ee52
- `checks.integration` — Verified: pass — run 20261120T235639Z, commit b34ee52
- `checks.build` — Verified: pass — run 20261120T235639Z, commit b34ee52

### Not done

ubuntu-22.04 will be retired by GitHub at some point; then the 3.8 leg needs a container image (python:3.8). Not filed yet: no retirement date is known (Unknown).

### Discovered

Version workflow on main fails at 'Validate before releasing' (smoke tests fail on main at 4907e16), so no release has ever been tagged, not even v4.0.0 (Reported: GitHub Actions API, runs on 2026-11-06..10). kit-v5's smoke passes, so the merge should clear it.

### Decisions

none

### Assumptions used

setup-python ships 3.8 for ubuntu-22.04 (Assumed; confirmed only when CI runs on push).

### Plan

CI's 3.8 leg failed at setup-python on ubuntu-latest (24.04 has no 3.8 build), and installs from kit-v5 printed v4.0.0 with nothing saying the code was unreleased. Rejected: bumping VERSION to 5.0.0 by hand. tools/semver.py takes the last commit that changed VERSION as the release base, so a manual bump would leave the merge to main with nothing to release, and no v5.0.0 tag would be created. Rejected: stamping a dev version into the manifest, which would churn AGENTS.md and the manifest on every commit and break upgrade comparisons.

### Reviews

Fresh-context ship review (claude-code subagent, same model family as the author, so recorded as a self-check) of 0831487..821415b: Pass with conditions, 5 x S3 and 3 x S4. All fixed in 6ecebdc/3bbff99/b34ee52 with failing-first smoke tests. F5 (shallow clone) was this item's.

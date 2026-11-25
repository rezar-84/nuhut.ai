## NUHT-052 — A fresh install's doctor: blank Commands reported twice, empty records reported as never reviewed (touch: install.py, optional/runtime/sdlc.py, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `42130c2..42130c2`

### What changed

- fix(NUHT-052): a fresh install's doctor names only open decisions (42130c2)

Files: `CHANGELOG.md`, `install.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

A fresh `-y` install showed 12 doctor warnings, 4 of them noise. Three said that records the install had just created empty were never reviewed, and the blank Commands rows were reported twice. Rejected: aiming for zero warnings, which would hide real decisions such as Approvers, Default branch and Active roles.

### Verified

- `checks.lint` — Verified: pass — run 20261125T052236Z, commit 42130c2
- `checks.unit` — Verified: pass — run 20261125T052236Z, commit 42130c2
- `checks.integration` — Verified: pass — run 20261125T052236Z, commit 42130c2
- `checks.build` — Verified: pass — run 20261125T052236Z, commit 42130c2

### Not done

nothing deferred

### Discovered

The install manifest does not hash record files, so doctor cannot tell an untouched record from an edited one. Dating the records at install avoids needing to.

### Decisions

none

### Assumptions used

A record created empty has nothing to review on the day it was created, which is the rule the installer already applies to generated test and eval plans.

### Plan

`Installer.tailor` dates the backlog, worklog and assumptions records on a fresh install. `check_charter` folds the detected commands into its single Commands finding, and `check_profile` no longer reports them separately. Tested in test_adopt_detected_commands.

### Reviews

software-engineer (same session, not independent): Pass. The fresh install now shows 8 warnings, each an open decision.

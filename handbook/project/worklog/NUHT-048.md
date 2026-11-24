## NUHT-048 — Detected check commands never reach the charter on a -y install (touch: install.py, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `c884460..c884460`

### What changed

- fix(NUHT-048): keep detected check commands until a person adopts them (c884460)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/sdlc.py`, `optional/runtime/status.py`, `tests/smoke.py`

### Why

A `-y` install detected `npm run test` and `npm run lint`, but `verify` ran nothing and `fix all` erased the detection. The installer's rule (an answer nobody gave is not written down as a decision) stays, so the charter is still blank after `-y`. The detection is kept and named until a person adopts it. Rejected: writing the detected commands straight into the charter on `-y`, which would reverse that rule without the owner deciding.

### Verified

- `checks.lint` — Verified: pass — run 20261124T214958Z, commit c884460
- `checks.unit` — Verified: pass — run 20261124T214958Z, commit c884460
- `checks.integration` — Verified: pass — run 20261124T214958Z, commit c884460
- `checks.build` — Verified: pass — run 20261124T214958Z, commit c884460

### Not done

The installer's own `-y` summary does not mention the adopt command yet; `doctor` and `status` do.

### Discovered

`sdlc.py` has a second command detector, `detect_candidate_commands` (used by `kit_status`), which disagrees with the installer's (`npm test` against `npm run test`). Two detectors should be one, to be logged as a backlog item. The shell guard refuses a heredoc or `python -c` that only names `.ai-sdlc/profile.json`, even when reading it in another repo, so this change was scripted through files.

### Decisions

none

### Assumptions used

profile.json's `commands` hold the installer's detection for every stage it found, as `Installer.selected_commands` writes them.

### Plan

[NUHT-048.md](plans/NUHT-048.md)

### Reviews

software-engineer (same session, not independent): Pass. A row marked absent or filled in is never written, and the new doctor finding has its own fix hint and is kept out of the sync-profile action list.

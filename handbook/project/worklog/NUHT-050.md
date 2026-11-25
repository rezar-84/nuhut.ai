## NUHT-050 — Two check-command detectors disagree (install.py detect vs sdlc.py detect_candidate_commands) (touch: optional/runtime/sdlc.py, install.py)

**Date:** 2026-11-25 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `6f4c7ca..6f4c7ca`

### What changed

- fix(NUHT-050): the viewer suggests the installer's detected command (6f4c7ca)

Files: `CHANGELOG.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

The viewer's repair panel suggested `npm test` while doctor and status named `npm run test`. The runtime cannot import the installer's detector, so the profile's detection now wins, and the runtime scan stays as a fallback for installs whose profile holds none. Rejected: deleting the scan, which would leave older installs with no suggestions.

### Verified

- `checks.lint` — Verified: pass — run 20261125T051145Z, commit 6f4c7ca
- `checks.unit` — Verified: pass — run 20261125T051145Z, commit 6f4c7ca
- `checks.integration` — Verified: pass — run 20261125T051145Z, commit 6f4c7ca
- `checks.build` — Verified: pass — run 20261125T051145Z, commit 6f4c7ca

### Not done

The fallback scan still covers fewer ecosystems than the installer's detector.

### Discovered

nothing

### Decisions

none

### Assumptions used

`config --json` prints the same `kit_status` model the viewer reads.

### Plan

kit_status takes the profile's detected commands over its own repository scan, and the scan uses the installer's command forms; tested in test_adopt_detected_commands. Alternatives are under Why.

### Reviews

software-engineer (same session, not independent): Pass.

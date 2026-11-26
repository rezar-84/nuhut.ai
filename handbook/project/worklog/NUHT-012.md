## NUHT-012 — finish accepts stale, stage-only or self-waived verify evidence (touch: optional/runtime/finish.py, optional/runtime/sdlc.py, tests/smoke.py)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `6db41ed..1f92e72`

### What changed

- docs(NUHT-012): ship review and responses (1f92e72)
- fix(NUHT-012): trust records only from git, and attribute only real trailers (593ccb1)
- feat(NUHT-012): bind finish's verify evidence to the item and its approvers (6db41ed)

Files: `install.py`, `optional/runtime/finish.py`, `optional/runtime/hooks.py`, `optional/runtime/registry.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `CHANGELOG.md`, `docs/cli.md`, `docs/install.md`, `optional/claude-commands/sdlc-finish.md`

### Why

finish accepted a stale, stage-only or self-waived verify run as evidence. It now needs a full run on the item's newest code commit, and only an Approver may waive. Rejected: trusting any run tagged with the item, which let old evidence close changed code.

### Verified

- `checks.lint` — Verified: pass — run 20261122T080733Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T080733Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T080733Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T080733Z, commit 8e128c9

### Not done

Dirty-run evidence binds only to the parent commit (NUHT-062).

### Discovered

Retro ship review: a newer failing --stage run was ignored after an older full pass (fixed in NUHT-061).

### Decisions

ADR 0004 for the findings declined in its review.

### Assumptions used

none

### Plan

[NUHT-012.md](plans/NUHT-012.md)

### Reviews

- [NUHT-012-ship-qa.md](reviews/NUHT-012-ship-qa.md)

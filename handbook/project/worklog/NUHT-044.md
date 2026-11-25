## NUHT-044 — NUHT-038 follow-ups: other hosts' CI files are Tier 1, advisory is info without a remote, 5.x base falls back, this repo's CI runs ci-check (touch: optional/runtime/sdlc.py, install.py, .github/workflows/ci.yml)

**Date:** 2026-11-25 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `41d75e3..aa56d5c`

### What changed

- chore(NUHT-044): verify run on cf5f471 (aa56d5c)
- fix(NUHT-044): an unreadable base ref fails the CI job instead of counting as no kit (79b2003)
- fix(NUHT-044): CI falls back to the change's checker only for a base with no kit or a 5.x kit (4a4ad3c)
- feat(NUHT-044): every host's CI file is Tier 1; advisory is info without a remote; 5.x base falls back; this repo runs ci-check (41d75e3)

Files: `.github/workflows/ci.yml`, `install.py`, `tests/smoke.py`, `optional/runtime/sdlc.py`

### Why

CI files for other git hosts were not Tier 1 paths, a repository with no remote got a warning it could not act on, and a 5.x project's first upgrade PR failed with a usage error. Every host's CI file is now Tier 1. No remote is an info line. The CI checker falls back only when the base branch has no kit or a 5.x kit, and fails on anything else. Rejected: falling back on any error, which a broken base could exploit.

### Verified

- `checks.lint` — Verified: pass — run 20261123T201711Z, commit 60286b9
- `checks.unit` — Verified: pass — run 20261123T201711Z, commit 60286b9
- `checks.integration` — Verified: pass — run 20261123T201711Z, commit 60286b9
- `checks.build` — Verified: pass — run 20261123T201711Z, commit 60286b9

### Not done

Branch protection on `main` is the owner's GitHub setting (review finding 3).

### Discovered

This repository's own CI now runs `doctor --strict` and `ci-check` (the `records` job).

### Decisions

none

### Assumptions used

`git ls-tree` on the base ref tells a kit-less base from an unreadable one.

### Plan

[NUHT-044.md](plans/NUHT-044.md)

### Reviews

- [NUHT-044-ship-devops-sre-2.md](reviews/NUHT-044-ship-devops-sre-2.md)
- [NUHT-044-ship-devops-sre.md](reviews/NUHT-044-ship-devops-sre.md)

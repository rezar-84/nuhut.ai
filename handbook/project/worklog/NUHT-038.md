## NUHT-038 — CI context beyond GitHub: GitLab, Bitbucket, Gitea and NUHUT_BASE/NUHUT_HEAD; more --scaffold-ci targets; doctor reports advisory-only repos (touch: optional/runtime/sdlc.py, optional/runtime/registry.py, install.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `2e087b9..489e0f7`

### What changed

- merge(NUHT-038): CI context beyond GitHub (489e0f7)
- feat(NUHT-038): CI context for GitLab, Bitbucket, Gitea, Azure, Jenkins; more scaffolds; doctor reports advisory repos (2e087b9)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `docs/install.md`, `install.py`, `optional/runtime/registry.py`

### Why

ci-check and trusted_ref read the CI target branch and head from GitHub, Gitea, GitLab, Bitbucket, Azure, Jenkins or NUHUT_BASE/NUHUT_HEAD; --scaffold-ci bitbucket|gitea|generic; doctor warns enforcement: advisory. Built by a worktree agent. Rejected: changing the default --head on GitHub (HEAD is the merge commit there).

### Verified

- `checks.lint` — Verified: pass — run 20261122T124320Z, commit 489e0f7
- `checks.unit` — Verified: pass — run 20261122T124320Z, commit 489e0f7
- `checks.integration` — Verified: pass — run 20261122T124320Z, commit 489e0f7
- `checks.build` — Verified: pass — run 20261122T124320Z, commit 489e0f7

### Not done

non-GitHub CI files as Tier 1 paths (gate change, owner decision); server-side hook and approval readers (NUHT-039)

### Discovered

this repo's own CI never runs sdlc.py, so doctor reports it advisory

### Decisions

none

### Assumptions used

none

### Plan

ci-check and trusted_ref read the CI target branch and head from GitHub, Gitea, GitLab, Bitbucket, Azure, Jenkins or NUHUT_BASE/NUHUT_HEAD; --scaffold-ci bitbucket|gitea|generic; doctor warns enforcement: advisory. Built by a worktree agent. Rejected: changing the default --head on GitHub (HEAD is the merge commit there).

### Reviews

self-reviewed

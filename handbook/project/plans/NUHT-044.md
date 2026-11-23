---
status: current
owner: architect
last-reviewed: 2026-11-23
---

# Plan: NUHT-044 Follow-ups from NUHT-038

**Tier:** 1 (changes the tier floor, a governance gate) **Effort:** Lean **Depends on:**
NUHT-038. **Approval to build:** the owner, 2026-11-23, in session ("best and recommended
way" for each NUHT-038 point).

## Outcome

1. `ci_tier1_globs` always includes every CI file the kit recognises (`CI_FILES`), not only
   `.github/workflows/**`: a change to any of them can switch the checks off.
2. `doctor` reports `enforcement: advisory` as info when there is no git remote (local-only
   git is a choice), and as a warning when there is a remote but no CI runs the checks.
3. The scaffolded CI falls back to the change's own `ci-check`, with a warning, when the
   target branch's `sdlc.py` has no `ci-check` (5.x), instead of failing with a usage error.
4. This repository's `.github/workflows/ci.yml` gains a `records` job: `doctor --strict` on
   every push, the base branch's `ci-check` on pull requests.
5. GitLab's automatic `records` job stays automatic: it runs only the kit's own checks, as
   the GitHub scaffold does on every pull request.

## Files that change

`optional/runtime/sdlc.py`, `.ai-sdlc/bin/sdlc.py`, `install.py`,
`.github/workflows/ci.yml`, `tests/smoke.py` (`test_ci_check`, `test_ci_context`,
`test_scaffolding`), `CHANGELOG.md`.

## Failure modes

- The fallback lets the first upgrade PR run its own checker, so that one PR can edit the
  checker it is judged by. The warning says so; the same trade-off already applies when the
  target has no kit.
- The `records` job does not judge a merge pushed straight to `main`; the v6 history
  predates `ci-check` and would fail it.

## Rollback

Revert the commit.

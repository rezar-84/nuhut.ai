---
status: current
owner: security
last-reviewed: 2026-11-13
---

# Plan — NUHT-001 Control-plane security hardening, unified Python hook engine, runtime bug fixes & contract reconciliation

**Tier:** 1 **Effort:** Normal **Depends on:** none

## Problem

`sdlc.py view --serve` exposed `action_token` in `/model.json` and allowed `checks.*` edits over HTTP; shell hooks depended on `jq` and BSD-incompatible `sed`, failed open on parser errors, and missed linked worktrees and symlinks; and ten minor runtime and documentation drift items accumulated across 4.x.

## Outcome

`view --serve` authenticates `/action` via an `HttpOnly; SameSite=Strict` cookie plus strict `Origin` validation while refusing `checks.*` command edits over HTTP, all hooks delegate to stdlib `hooks.py` without `jq`, and CI verifies both Ubuntu and macOS cleanly.

## Approach

Harden `optional/runtime/view.py` and viewer JS (`optional/runtime/view/`), build `optional/runtime/hooks.py` as the single stdlib evaluator behind Claude Code, Gemini CLI (`AfterAgent` included), Cursor, and git hooks, fix edge cases in `specs.py`, `finish.py`, `claims.py`, `sdlc.py`, `slop.py`, and `lens.py`, reconcile skill/process docs, and add `macos-latest` to `.github/workflows/ci.yml`.

## Files that change

- `.agents/skills/**`
- `.ai-sdlc/bin/**`
- `.ai-sdlc/manifest.json`
- `.ai-sdlc/profile.json`
- `.claude/commands/**`
- `.claude/hooks/**`
- `.claude/settings.json`
- `.claude/skills/**`
- `.cursor/hooks.json`
- `.cursor/rules/**`
- `.cursorrules`
- `.gemini/settings.json`
- `.github/workflows/**`
- `.gitignore`
- `AGENTS.md`
- `CHANGES-REPORT.md`
- `CLAUDE.md`
- `GEMINI.md`
- `handbook/CARD.md`
- `handbook/README.md`
- `handbook/process/**`
- `handbook/roles/**`
- `handbook/templates/**`
- `install.py`
- `optional/git-hooks/**`
- `optional/hooks/**`
- `optional/runtime/**`
- `optional/skills/**`
- `template/AGENTS.md`
- `template/docs/CARD.md`
- `template/docs/process/02-role-reviews.md`
- `template/docs/process/06-evidence-and-claims.md`
- `template/docs/process/07-traceability.md`
- `template/docs/roles/accessibility.md`
- `template/docs/roles/data-engineer.md`
- `template/docs/roles/ml-engineer.md`
- `template/docs/roles/qa.md`
- `template/docs/roles/security.md`
- `template/docs/roles/ux-designer.md`
- `tests/smoke.py`
- `validate.py`

_Amended 2026-11-15 after the kit-v5 ship re-review (finding C1): the earlier list was 24 repo-wide globs shared by NUHT-001..003, so plan-check could not fail. This list is what the item's commits touched. The three items share one branch, so run `sdlc.py plan-check NUHT-001 --base main`; files from later items on the branch still show as unplanned._

## Order of work

1. Harden `view.py` HTTP cookie/Origin CSRF controls, payload validation, and process-group (`os.killpg`) timeout cleanup; rebuild `view.html`.
2. Implement `optional/runtime/hooks.py` (highest-risk step, since hook false positives or false negatives affect every guarded tool call) and wire thin POSIX shims + `install.py` Gemini `AfterAgent` registration.
3. Land runtime fixes in `specs.py`, `finish.py`, `claims.py`, `sdlc.py`, `slop.py`, and `lens.py`.
4. Reconcile contract docs/skills, add `macos-latest` CI matrix and `fetch-depth: 0` in `release.yml`, and expand `tests/smoke.py`.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Keep bash + `jq` hooks with portable `sed` | Still requires `jq` installed on every developer and CI machine and duplicates JSON/path logic across scripts. |
| Allow `checks.*` edits over localhost HTTP with CSRF cookie | Any browser tab bug on `127.0.0.1` would become arbitrary shell command registration; CLI/editor-only `checks.*` eliminates the remote-exec surface. |

## Affected surfaces

- **Code:** `optional/runtime/view.py`, `optional/runtime/hooks.py`, `optional/runtime/sdlc.py`, `optional/runtime/finish.py`, `optional/runtime/specs.py`, `optional/runtime/claims.py`, `install.py`
- **Data:** `.ai-sdlc/manifest.json` and `.gemini/settings.json` hook wiring
- **Contracts:** `/model.json` (no longer emits `action_token`), `/action` (`Cookie` + `Origin` required), `finish` CLI flags (`--why`, `--from-json`)
- **Docs to update:** `docs/runtime.md`, `docs/cli.md`, `CHANGELOG.md`, `handbook/project/adr/0001-v5-software-factory-architecture.md`

## Failure modes

- Malformed JSON stdin or missing `python3` in hook shims: fail closed (`deny` / exit 2) on `PreToolUse` and git commit hooks rather than silently allowing a secret or gated command.
- Subprocess hangs during `verify`, `bite`, `audit`, or `review`: run in a dedicated session (`start_new_session=True`) and terminate the process group via `os.killpg`.

## Test strategy

- **Acceptance criteria mapping:** Security cookie/Origin/checks tests, `hooks.py` symlink/worktree/secret/test-lock tests, and runtime regression checks in `tests/smoke.py`.
- **Unit:** `python3 optional/runtime/sdlc.py --selftest`
- **Integration:** `python3 tests/smoke.py`
- **Negative cases:** Forged cross-origin `/action` POST, non-dict JSON body, HTTP `checks.unit` mutation, symlink escape to `.env`, unapproved `test-lock.txt` shell edit.
- **Manual:** Inspect rebuilt `optional/runtime/view.html`.
- **Proof:** `python3 tools/build_view.py --check`, `python3 optional/runtime/sdlc.py --selftest`, `python3 validate.py`, `python3 tests/smoke.py`.

## Rollback

Revert the M1 commit on `kit-v5` and run `./install.sh <project> --repair` on upgraded installs.

## Out of scope

- Sharded multi-agent store (`NUHT-002`) and headless multi-worker dispatcher (`NUHT-003`).

## Assumptions

- Target developer and CI environments provide `python3` (3.8+), already required by `install.sh` and `sdlc.py`.

## Review

| Role | Verdict | Notes |
| --- | --- | --- |
| product-manager, architect, security, qa | Pass | [NUHT-001-design.md](../reviews/NUHT-001-design.md), [NUHT-001-ship.md](../reviews/NUHT-001-ship.md) |

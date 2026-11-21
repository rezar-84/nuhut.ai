## NUHT-006 — plan-check --pre: refuse plans that name missing files before the build (touch: optional/runtime/sdlc.py, .ai-sdlc/bin/sdlc.py, tests/smoke.py, docs/cli.md, README.md, CHANGELOG.md)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `4ba9260..b34ee52`

### What changed

- fix(NUHT-005): make the escalation gate fail closed (b34ee52)
- fix(NUHT-006): read git paths unquoted; accept (new) inside the backticks (3bbff99)
- feat(NUHT-006): plan-check --pre checks a plan before the build; --strict fails too-broad plans (568f999)
- docs(NUHT-007): plan and ADR 0002 for a fresh-context review level; file NUHT-005..009 (4ba9260)

Files: `CHANGELOG.md`, `docs/cli.md`, `docs/viewer.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `README.md`, `handbook/templates/plan.md`, `optional/claude-commands/sdlc-plan.md`, `template/docs/templates/plan.md`

### Why

A plan's file list was only checked after the build, and the too-broad warning from 0831487 did not affect --strict, so the vacuous-plan failure from the NUHT-002 re-review (C1) could still pass a gate. Rejected: checking function signatures like EGM's readiness stage, which needs a parser per language and breaks the stdlib, stack-agnostic rule.

### Verified

- `checks.lint` — Verified: pass — run 20261121T000412Z, commit b34ee52
- `checks.unit` — Verified: pass — run 20261121T000412Z, commit b34ee52
- `checks.integration` — Verified: pass — run 20261121T000412Z, commit b34ee52
- `checks.build` — Verified: pass — run 20261121T000412Z, commit b34ee52

### Not done

nothing deferred

### Discovered

0831487 shipped the .ai-sdlc/bin counting and the too-broad warning without tests; tests added here. Ship review F4: git's quotePath broke glob matching for non-ASCII names in every plan-check (pre-existing), fixed in 3bbff99.

### Decisions

none

### Assumptions used

none

### Plan

A plan's file list was only checked after the build, and the too-broad warning from 0831487 did not affect --strict, so the vacuous-plan failure from the NUHT-002 re-review (C1) could still pass a gate. Rejected: checking function signatures like EGM's readiness stage, which needs a parser per language and breaks the stdlib, stack-agnostic rule.

### Reviews

Fresh-context ship review (claude-code subagent, same model family as the author, so recorded as a self-check) of 0831487..821415b: Pass with conditions, 5 x S3 and 3 x S4. All fixed in 6ecebdc/3bbff99/b34ee52 with failing-first smoke tests. F4 and part of F8 were this item's.

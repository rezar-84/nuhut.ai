## NUHT-055 — Hooks: commit checks move to git hooks, no guessing at inline code, sdlc.py hooks list/on/off (touch: optional/runtime/hooks.py, optional/runtime/sdlc.py, install.py, tests/smoke.py)

**Date:** 2026-11-25 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `7d913ba..8c8aa71`

### What changed

- fix(NUHT-055): ship review round 2 (8c8aa71)
- fix(NUHT-055): ship review round 1 (a67d1cf)
- feat(NUHT-055): guard hooks without the false alarms; sdlc.py hooks on/off (7d913ba)

Files: `install.py`, `optional/runtime/hooks.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `benchmarks/effort-modes/run.py`, `benchmarks/kit-value/run.py`, `docs/cli.md`

### Why

The agent hooks blocked harmless commands: `git commit` inside quoted text, and inline code that only named a guarded path. The commit checks now run as git hooks, which see the real message and diff. Inline code is refused only when it names an enforcement file. A person can switch any hook off. Rejected: removing every hook, which drops the accurate direct-write checks too.

### Verified

- `checks.lint` — Verified: pass — run 20261125T110104Z, commit db2c321
- `checks.unit` — Verified: pass — run 20261125T110104Z, commit db2c321
- `checks.integration` — Verified: pass — run 20261125T110104Z, commit db2c321
- `checks.build` — Verified: pass — run 20261125T110104Z, commit db2c321

### Not done

This repository still registers the old Bash hooks until the owner runs `install.py . --upgrade`, which retires them once the git hooks are wired.

### Discovered

The doctor cache timing test flaked under the parallel fast tier (fixed in NUHT-056). The benchmark harness's setup commit needed `--no-verify` now that `--hooks` brings git hooks. The narrower inline rule still blocks an inline edit that only mentions an enforcement file; that cost is accepted.

### Decisions

ADR 0004: these hooks are guardrails; review findings that they cannot prove a person were declined under it.

### Assumptions used

git runs hooks from core.hooksPath, else the repository's hooks folder; husky reads .husky.

### Plan

[NUHT-055.md](plans/NUHT-055.md)

### Reviews

- [NUHT-055-ship-security-2.md](reviews/NUHT-055-ship-security-2.md)
- [NUHT-055-ship-security.md](reviews/NUHT-055-ship-security.md)

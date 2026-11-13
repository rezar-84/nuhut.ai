## NUHT-003 — M3: Multi-worker headless dispatcher (dispatch.py), self-healing defect policy & effort-modes benchmark suite

**Date:** 2026-11-13 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Branch/commits:** `kit-v5` / `c6234f1..4fc0cb8`

### What changed

- chore(NUHT-003): sync profile commands and record NUHT-001..002 ledger shards (4fc0cb8)
- fix(runtime): accept absent stage rationale in charter_commands and update 4.0 upgrade test (ea628c9)
- feat(factory): multi-worker dispatch, self-healing defect policy, and effort-modes benchmark (c6234f1)

Files: `optional/runtime/sdlc.py`, `tests/smoke.py`, `.gitignore`, `CHANGELOG.md`, `README.md`, `benchmarks/effort-modes/README.md`, `benchmarks/effort-modes/fake_agent.py`, `benchmarks/effort-modes/measure.py`, `benchmarks/effort-modes/run.py`, `benchmarks/effort-modes/tasks/adjacent-ops-risk/accept.sh`, `benchmarks/effort-modes/tasks/adjacent-ops-risk/prompt.md`, `benchmarks/effort-modes/tasks/adjacent-ops-risk/repo/config_loader.py` (+49 more)

### Why

Added headless multi-worker sdlc.py dispatch, charter-governed Discovered defects triage, multi-harness kit-value support, and the complete effort-modes benchmark suite.

### Verified

- `checks.lint` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.unit` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.integration` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.build` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8

### Not done

paid live LLM benchmark runs remain opt-in

### Discovered

nothing

### Decisions

ADR 0001: wave-based isolated worktree dispatch and bite-gated defect promotion

### Assumptions used

gh or glab CLI installed when --pr is requested

### Plan

[NUHT-003.md](plans/NUHT-003.md)

### Reviews

- [NUHT-003-design.md](reviews/NUHT-003-design.md)
- [NUHT-003-ship.md](reviews/NUHT-003-ship.md)

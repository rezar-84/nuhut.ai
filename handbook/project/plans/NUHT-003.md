---
status: current
owner: architect
last-reviewed: 2026-11-13
---

# Plan — NUHT-003 Multi-worker headless dispatcher (dispatch.py), self-healing defect policy & effort-modes benchmark suite

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-002

## Problem

Operators still had to claim worktrees, invoke builder CLIs, run `verify`, retry failures, run `finish`, and merge branches by hand for routine Tier 2 and Tier 3 queues; discovered defects had no charter-governed promotion rule; and `benchmarks/effort-modes/` lacked its executable runner, measurer, and five protocol tasks.

## Outcome

`sdlc.py dispatch` executes conflict-free waves of Ready items across isolated worktrees with bounded verification retries and viewer telemetry, the charter's `Discovered defects` row governs `Parked` vs `Auto-Ready (bite)` triage, and both `kit-value` and `effort-modes` benchmarks run end-to-end across multiple harnesses.

## Approach

Implement `optional/runtime/dispatch.py` (`sdlc.py dispatch`) and wire factory telemetry into `view.py` + `view/js/*`, add the `Discovered defects` charter row (`Parked` | `Auto-Ready (bite)`) and `sdlc.py config --discovered-defects` / `item triage`, upgrade `benchmarks/kit-value/{measure.py,run.py}`, and build `benchmarks/effort-modes/{run.py,measure.py,fake_agent.py,tasks/*}`.

## Files that change

- `optional/runtime/**`
- `optional/hooks/**`
- `optional/git-hooks/**`
- `optional/skills/**`
- `template/**`
- `install.py`
- `validate.py`
- `tests/smoke.py`
- `docs/**`
- `benchmarks/**`
- `handbook/**`
- `.github/workflows/**`
- `.agents/**`
- `.claude/**`
- `.cursor/**`
- `.gemini/**`
- `.cursorrules`
- `.gitignore`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `README.md`
- `CHANGELOG.md`
- `CHANGES-REPORT.md`

## Order of work

1. Build `optional/runtime/dispatch.py` with `<git-common-dir>/nuhut/worktrees/<ID>` isolation, serialized git ref/worktree lock (`coord_lock`), repair retries, `finish` closeout, conflict-free wave merges / `--pr`, and redacted `.ai-sdlc/dispatch/<run>.json` telemetry — riskiest step due to concurrent git worktree lifecycle management.
2. Add charter `Discovered defects` (`Parked` | `Auto-Ready (bite)`) across `template/docs/`, `sdlc.py config`, `item add --discovered`, `item triage`, and `dispatch.py`.
3. Update `benchmarks/kit-value/` (`NON_CEREMONY_RECORDS`, `absent` charter rows, `--harness`) and implement `benchmarks/effort-modes/` (`run.py`, `measure.py`, `fake_agent.py`, and 5 fixture tasks), wired into `validate.py`.
4. Add end-to-end `dispatch`, self-healing triage, and benchmark smoke suites in `tests/smoke.py`, and update user documentation and self-hosted records.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Auto-promote discovered defects to `Ready` without `bite` | Unreproduced agent bug reports can hallucinate defects and trigger cascading edits; requiring a passing `sdlc.py bite` run proves a real failing test exists first. |
| Place worker worktrees in `../<repo>-<ID>` during `dispatch` | Pollutes the user's parent directory when running N workers; `<git-common-dir>/nuhut/worktrees/<ID>` keeps both repo and parent directory clean. |

## Affected surfaces

- **Code:** `optional/runtime/dispatch.py`, `optional/runtime/sdlc.py`, `optional/runtime/view.py`, `optional/runtime/view/js/*`, `install.py`, `validate.py`, `benchmarks/**`
- **Data:** `.ai-sdlc/dispatch/<run>.json`, `template/docs/project/charter.md` (`Discovered defects` row)
- **Contracts:** `sdlc.py dispatch`, `sdlc.py item triage`, `sdlc.py item add --discovered`, `sdlc.py config --discovered-defects`, `model.json` `factory` summary
- **Docs to update:** `README.md`, `docs/cli.md`, `docs/multi-agent.md`, `docs/runtime.md`, `docs/roadmap.md`, `CHANGELOG.md`, `benchmarks/*/README.md`

## Failure modes

- Builder exits 0 without changing any product/test files: `dispatch` treats an empty product diff as an unfulfilled attempt and feeds diagnostics into the retry turn or fails cleanly.
- Merge conflict at wave join despite `touch` globs: `dispatch` runs `git merge --abort`, leaves the worker branch intact, and records `merged: false` without dirtying `HEAD`.
- Tier 1 item queued without an approved plan: `dispatch` skips unplanned Tier 1 items and leaves finished Tier 1 items `Parked` without auto-merging.

## Test strategy

- **Acceptance criteria mapping:** `test_dispatch_and_self_healing` (2-worker parallel Wave 1, Attempt 1 -> Attempt 2 repair retry, Wave 2 dependency unlock, discovered defect filing, `Auto-Ready (bite)` promotion gate, viewer telemetry) and `test_benchmarks_harnesses_and_effort_modes` in `tests/smoke.py`.
- **Unit:** `python3 optional/runtime/sdlc.py --selftest`, `python3 benchmarks/effort-modes/measure.py --selftest`, `python3 benchmarks/effort-modes/score.py --selftest`
- **Integration:** `python3 tests/smoke.py`
- **Negative cases:** `Auto-Ready (bite)` without `bite` ledger proof stays `Parked`; Tier 1 discovered defect stays `Parked`; unplanned Tier 1 skipped by `dispatch`.
- **Manual:** Check `python3 tools/build_view.py --check` and `python3 validate.py --reading-lists`.
- **Proof:** `python3 tools/build_view.py --check`, `python3 optional/runtime/sdlc.py --selftest`, `python3 validate.py`, `python3 tests/smoke.py`, `python3 .ai-sdlc/bin/sdlc.py doctor --strict`.

## Rollback

Revert the M3 commit on `kit-v5` and rebuild `view.html` if needed; `.ai-sdlc/dispatch/` telemetry is local and git-ignored.

## Out of scope

- Live paid API benchmark publication runs (opt-in by operator with pinned API credentials).

## Assumptions

- Operators invoking `dispatch --pr` have `gh` or `glab` authenticated when pull-request creation is requested; otherwise `dispatch` pushes the branch and reports the missing CLI cleanly.

## Review

| Role | Verdict | Notes |
| --- | --- | --- |
| product-manager, architect, security, qa | Pass | [NUHT-003-design.md](../reviews/NUHT-003-design.md), [NUHT-003-ship.md](../reviews/NUHT-003-ship.md) |

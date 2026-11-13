---
status: current
owner: architect
last-reviewed: 2026-11-13
---

# Review — NUHT-003 Multi-worker headless dispatcher (dispatch.py), self-healing defect policy & effort-modes benchmark suite

**Stage:** ship **Tier:** 1
**Author:** antigravity
**Reviewer agent:** antigravity
**Reviewer model:** gemini
**Independence:** self-check (charter `Independent review required for: none`)
**Reviewed:** `optional/runtime/{dispatch.py,sdlc.py,shards.py,view.py}`, `benchmarks/{kit-value,effort-modes}/**`, `tests/smoke.py`, `docs/**`

---

## Conformance (ship review, Tier 1 and 2)

**plan-check:** 0 unplanned paths (`sdlc.py plan-check NUHT-003`).

**Acceptance criteria:** `test_dispatch_and_self_healing` verifies 2-worker parallel Wave 1 execution, Attempt 1 -> Attempt 2 verification repair loop, Wave 2 dependency unlock, `Discovered defects` (`Parked` and `Auto-Ready (bite)` with `sdlc.py bite`), viewer `factory.dispatch_runs` telemetry, and zero `doctor` failures; `test_benchmarks_harnesses_and_effort_modes` verifies `kit-value` and `effort-modes` end-to-end with `score.py`.

**Out of scope held:** yes.

---

## architect, security, qa, product-manager

**Verdict:** Pass

**Checked:** `dispatch.py` worktree isolation under `<git-common-dir>/nuhut/worktrees/<ID>`, empty-diff rejection, `git merge --abort` fallback, secret redaction in `.ai-sdlc/dispatch/*.json`, `choice()` regex handling for parenthesised charter options (`Auto-Ready (bite)`), and `importlib` module isolation in `benchmarks/effort-modes/measure.py`.

**Not checked:** Live `gh pr create` / `glab mr create` network calls against GitHub/GitLab APIs.

### Findings

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |

---

## Outcome

**Overall:** Pass

**Blocking findings:** none

**Waivers:** none

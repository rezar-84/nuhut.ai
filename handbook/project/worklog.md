---
status: active
owner: rezar-84
last-reviewed: 2026-11-13
---

# Worklog — nuhut.ai

> Append-only. **Newest entry at the top.** One entry per completed work item, written
> at the LOG step of the loop, using `../templates/worklog-entry.md`.
>
> This is where a future reader — human or agent — learns *why* the system looks the way
> it does, what was actually verified, and what is still wrong. The backlog says what;
> this says why, and what it cost.

**Rules**

- Every entry names its `NUHT-###`.
- **Never rewrite history.** If an entry was wrong, append a correction that references
  it. The record of a mistaken belief is part of the record.
- The **Not done** section is mandatory. Deferred, stubbed, mocked, and hardcoded things
  are listed with follow-up IDs. An entry with no "Not done" section is either
  exceptional or incomplete, and it is usually the second.
- Verification is reported with real commands and real results. "Tests pass" is not a
  verification record.
- When this file gets long, move older entries to `worklog-archive/YYYY.md` and leave a
  pointer here. Do not truncate.

---

<!-- New entries go here, above the older ones. -->

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

## NUHT-002 — M2: Sharded zero-conflict store, git-ref leases, Tier 2 parallel scope globs, universal --json & cached doctor

**Date:** 2026-11-13 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Branch/commits:** `kit-v5` / `c5118ca..4fc0cb8`

### What changed

- chore(NUHT-003): sync profile commands and record NUHT-001..002 ledger shards (4fc0cb8)
- feat(runtime): sharded zero-conflict store, git-ref CAS leases, universal --json, and incremental doctor cache (c5118ca)

Files: `README.md`, `docs/cli.md`, `install.py`, `optional/runtime/claims.py`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `optional/runtime/view.py`, `tests/smoke.py`

### Why

Replaced single-file multi-agent bottlenecks with sharded items/, worklog/, and ledger/ records, git-ref CAS leases, Tier 2 touch globs, universal --json, and <500ms cached doctor.

### Verified

- `checks.lint` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.unit` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.integration` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.build` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8

### Not done

nothing deferred

### Discovered

nothing

### Decisions

ADR 0001: per-item JSON/Markdown/JSONL shards with transparent 4.x fallback

### Assumptions used

Git 2.20+ available for worktrees and --force-with-lease ref pushes

### Plan

[NUHT-002.md](plans/NUHT-002.md)

### Reviews

- [NUHT-002-design.md](reviews/NUHT-002-design.md)
- [NUHT-002-ship.md](reviews/NUHT-002-ship.md)

## NUHT-001 — M1: Control-plane security hardening, unified Python hook engine, runtime bug fixes & contract reconciliation

**Date:** 2026-11-13 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Branch/commits:** `kit-v5` / `936705a..4fc0cb8`

### What changed

- chore(NUHT-003): sync profile commands and record NUHT-001..002 ledger shards (4fc0cb8)
- feat(runtime,hooks)!: harden view --serve auth, add stdlib hooks.py engine, self-host handbook & reconcile contracts (936705a)

Files: `.cursor/hooks.json`, `.cursor/rules/agents.mdc`, `.cursorrules`, `.gemini/settings.json`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.gitignore`, `CHANGES-REPORT.md`, `GEMINI.md`, `handbook/CARD.md`, `handbook/README.md`, `handbook/process/00-operating-model.md` (+104 more)

### Why

Hardened view --serve with HttpOnly cookie + Origin checks, consolidated hooks into stdlib hooks.py, fixed 4.x runtime edge cases, and reconciled skills/docs across macOS and Linux.

### Verified

- `checks.lint` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.unit` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.integration` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8
- `checks.build` — Verified: pass — run 20261113T014834Z, commit 4fc0cb8

### Not done

nothing deferred

### Discovered

nothing

### Decisions

ADR 0001: stdlib hooks.py and CLI-only checks.* mutations

### Assumptions used

Python 3.8+ available on developer and CI machines

### Plan

[NUHT-001.md](plans/NUHT-001.md)

### Reviews

- [NUHT-001-design.md](reviews/NUHT-001-design.md)
- [NUHT-001-ship.md](reviews/NUHT-001-ship.md)

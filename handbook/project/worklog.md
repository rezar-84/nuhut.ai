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

## NUHT-010 — Guided installer draws 40 columns on Python 3.8-3.10 when the terminal reports size 0 (touch: install_ui.py, tests/smoke.py, CHANGELOG.md)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `617c497..617c497`

### What changed

- fix(NUHT-010): draw the guided installer at 80x24 when the terminal reports size 0 (617c497)

Files: `CHANGELOG.md`, `install.py`, `install_ui.py`, `tests/smoke.py`

### Why

CI's 3.8 leg, once NUHT-004 let it install Python, failed one smoke check: the guided installer's help wrapped at 32 columns. Python 3.8-3.10 return 0x0 from shutil.get_terminal_size() for a terminal that reports size 0 (3.11 returns the fallback), and Term.width() floored that at 40. Rejected: loosening the test's string match, which would hide a real cramped layout for users on 3.8-3.10. The item was filed as a discovered defect, which the charter parks by default; it was moved to In progress because it blocked the v5.0.0 release rezar-84 asked for.

### Verified

- `checks.lint` — Verified: pass — run 20261121T003325Z, commit 617c497
- `checks.unit` — Verified: pass — run 20261121T003325Z, commit 617c497
- `checks.integration` — Verified: pass — run 20261121T003325Z, commit 617c497
- `checks.build` — Verified: pass — run 20261121T003325Z, commit 617c497

### Not done

nothing deferred

### Discovered

Setup.term_cols() in install.py had the same bug and returned 0; fixed in the same commit. A full 3.8 smoke run alongside a 3.14 verify hit a 10 s pty timeout from load; rerun alone, all passed.

### Decisions

none

### Assumptions used

none

### Plan

CI's 3.8 leg, once NUHT-004 let it install Python, failed one smoke check: the guided installer's help wrapped at 32 columns. Python 3.8-3.10 return 0x0 from shutil.get_terminal_size() for a terminal that reports size 0 (3.11 returns the fallback), and Term.width() floored that at 40. Rejected: loosening the test's string match, which would hide a real cramped layout for users on 3.8-3.10. The item was filed as a discovered defect, which the charter parks by default; it was moved to In progress because it blocked the v5.0.0 release rezar-84 asked for.

### Reviews

self-reviewed (qa): root cause reproduced on 3.8.20, new test fails on 3.14 with a stubbed 0x0 size before the fix and passes after; full smoke passes on 3.8.20 (local) and 3.14 (verify run 20261121T003325Z).

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

## NUHT-005 — Review triage: paraphrase step and Contest/Escalate/Fix/Decline responses, escalations in Needs you (touch: template/docs/process/02-role-reviews.md, template/docs/templates/role-review.md, handbook/process/02-role-reviews.md, handbook/templates/role-review.md, optional/runtime/sdlc.py, .ai-sdlc/bin/sdlc.py, .claude/commands/sdlc-review.md, optional/commands/, tests/smoke.py, CHANGELOG.md, docs/)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `4ba9260..b34ee52`

### What changed

- fix(NUHT-005): make the escalation gate fail closed (b34ee52)
- feat(NUHT-005): answer review findings (Fix/Contest/Escalate/Decline); paraphrase-first design reviews (821415b)
- docs(NUHT-007): plan and ADR 0002 for a fresh-context review level; file NUHT-005..009 (4ba9260)

Files: `CHANGELOG.md`, `docs/cli.md`, `docs/viewer.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `handbook/process/02-role-reviews.md`, `handbook/templates/role-review.md`, `optional/claude-commands/sdlc-review.md`, `optional/runtime/view.html`, `optional/runtime/view/js/12-dashboard.js`, `template/docs/process/02-role-reviews.md` (+1 more)

### Why

From the Elephant-Goldfish Model comparison: reviews had no structured author answer, so a finding only a person can settle had nowhere to wait. Escalations now block finish and show in Needs you. Rejected: a doctor fail for open escalations, which would turn every pending decision into a red failure; a warn routed to Needs you matches 'waiting on a person'.

### Verified

- `checks.lint` — Verified: pass — run 20261120T234923Z, commit b34ee52
- `checks.unit` — Verified: pass — run 20261120T234923Z, commit b34ee52
- `checks.integration` — Verified: pass — run 20261120T234923Z, commit b34ee52
- `checks.build` — Verified: pass — run 20261120T234923Z, commit b34ee52

### Not done

NUHT-007 (fresh-context review level) is Parked for owner approval; NUHT-008/009 Deferred.

### Discovered

Ship review F1-F3: the first parser failed open (escaped pipes, 'pending' in Decided by, 'Escalated', column order, '### Responses'). Fixed in b34ee52.

### Decisions

none (ADR 0002 is NUHT-007's, proposed)

### Assumptions used

none

### Plan

From the Elephant-Goldfish Model comparison: reviews had no structured author answer, so a finding only a person can settle had nowhere to wait. Escalations now block finish and show in Needs you. Rejected: a doctor fail for open escalations, which would turn every pending decision into a red failure; a warn routed to Needs you matches 'waiting on a person'.

### Reviews

Fresh-context ship review (claude-code subagent, same model family as the author, so recorded as a self-check) of 0831487..821415b: Pass with conditions, 5 x S3 and 3 x S4. All fixed in 6ecebdc/3bbff99/b34ee52 with failing-first smoke tests. F1-F3, F6-F8 were this item's.

## NUHT-004 — Release hygiene: CI Python 3.8 runner, installer names the unreleased version (touch: .github/workflows/ci.yml, install.py, tests/smoke.py, CHANGELOG.md, docs/install.md)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `3b18878..6ecebdc`

### What changed

- fix(NUHT-004): a shallow clone says its unreleased state is unknown (6ecebdc)
- fix(NUHT-004): run CI's Python 3.8 leg on ubuntu-22.04; installer names unreleased work (3b18878)

Files: `CHANGELOG.md`, `install.py`, `tests/smoke.py`, `.github/workflows/ci.yml`, `docs/install.md`

### Why

CI's 3.8 leg failed at setup-python on ubuntu-latest (24.04 has no 3.8 build), and installs from kit-v5 printed v4.0.0 with nothing saying the code was unreleased. Rejected: bumping VERSION to 5.0.0 by hand. tools/semver.py takes the last commit that changed VERSION as the release base, so a manual bump would leave the merge to main with nothing to release, and no v5.0.0 tag would be created. Rejected: stamping a dev version into the manifest, which would churn AGENTS.md and the manifest on every commit and break upgrade comparisons.

### Verified

- `checks.lint` — Verified: pass — run 20261120T235639Z, commit b34ee52
- `checks.unit` — Verified: pass — run 20261120T235639Z, commit b34ee52
- `checks.integration` — Verified: pass — run 20261120T235639Z, commit b34ee52
- `checks.build` — Verified: pass — run 20261120T235639Z, commit b34ee52

### Not done

ubuntu-22.04 will be retired by GitHub at some point; then the 3.8 leg needs a container image (python:3.8). Not filed yet: no retirement date is known (Unknown).

### Discovered

Version workflow on main fails at 'Validate before releasing' (smoke tests fail on main at 4907e16), so no release has ever been tagged, not even v4.0.0 (Reported: GitHub Actions API, runs on 2026-11-06..10). kit-v5's smoke passes, so the merge should clear it.

### Decisions

none

### Assumptions used

setup-python ships 3.8 for ubuntu-22.04 (Assumed; confirmed only when CI runs on push).

### Plan

CI's 3.8 leg failed at setup-python on ubuntu-latest (24.04 has no 3.8 build), and installs from kit-v5 printed v4.0.0 with nothing saying the code was unreleased. Rejected: bumping VERSION to 5.0.0 by hand. tools/semver.py takes the last commit that changed VERSION as the release base, so a manual bump would leave the merge to main with nothing to release, and no v5.0.0 tag would be created. Rejected: stamping a dev version into the manifest, which would churn AGENTS.md and the manifest on every commit and break upgrade comparisons.

### Reviews

Fresh-context ship review (claude-code subagent, same model family as the author, so recorded as a self-check) of 0831487..821415b: Pass with conditions, 5 x S3 and 3 x S4. All fixed in 6ecebdc/3bbff99/b34ee52 with failing-first smoke tests. F5 (shallow clone) was this item's.

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

### Approval

Merge to `main` and release `v5.0.0` approved by rezar-84 on 2026-11-21, in the session. One approver: the charter lists one (`Approvers: rezar-84`), while `process/05-change-control.md` asks for two at Tier 1. The charter row "May merge to the default branch" is `no`; rezar-84 authorised the agent to run this one merge, and the row is unchanged.

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

### Approval

Merge to `main` and release `v5.0.0` approved by rezar-84 on 2026-11-21, in the session. One approver: the charter lists one (`Approvers: rezar-84`), while `process/05-change-control.md` asks for two at Tier 1. The charter row "May merge to the default branch" is `no`; rezar-84 authorised the agent to run this one merge, and the row is unchanged.

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

### Approval

Merge to `main` and release `v5.0.0` approved by rezar-84 on 2026-11-21, in the session. One approver: the charter lists one (`Approvers: rezar-84`), while `process/05-change-control.md` asks for two at Tier 1. The charter row "May merge to the default branch" is `no`; rezar-84 authorised the agent to run this one merge, and the row is unchanged.

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

## NUHT-040 — Bugs agents notice: sdlc.py bug, severity on items, open S0-S2 in status and at session start, touch-path warnings, generated defects index (touch: optional/runtime/sdlc.py, optional/runtime/shards.py, optional/runtime/status.py, optional/runtime/hooks.py)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `7754d1c..7754d1c`

### What changed

- feat(NUHT-040): sdlc.py bug, defect severity, open defects at session start and in status (7754d1c)

Files: `CHANGELOG.md`, `README.md`, `docs/cli.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `optional/runtime/status.py`, `tests/smoke.py`

### Why

sdlc.py bug with severity and a filled defect report; severity and found_by on shards; render builds the defects index; status and guard start show open S0-S2; claim warns on overlapping touch paths. Rejected: an edit-time hook warning (hook rule plumbing; claim time reaches the agent before it edits).

### Verified

- `checks.lint` — Verified: pass — run 20261122T122406Z, commit 489e0f7
- `checks.unit` — Verified: pass — run 20261122T122406Z, commit 489e0f7
- `checks.integration` — Verified: pass — run 20261122T122406Z, commit 489e0f7
- `checks.build` — Verified: pass — run 20261122T122406Z, commit 489e0f7

### Not done

doctor warning for open defects with no severity (proposed under NUHT-041)

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

sdlc.py bug with severity and a filled defect report; severity and found_by on shards; render builds the defects index; status and guard start show open S0-S2; claim warns on overlapping touch paths. Rejected: an edit-time hook warning (hook rule plumbing; claim time reaches the agent before it edits).

### Reviews

self-reviewed

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

## NUHT-037 — view --serve over the network: --host tailscale|<ip>, access key in the link, read-only unless --allow-actions (touch: optional/runtime/view.py, docs/cli.md)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `91daa9c..f3ae880`

### What changed

- merge(NUHT-037): view --serve remote mode (f3ae880)
- feat(NUHT-037): view --serve --host with access key and read-only remote mode (91daa9c)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `docs/viewer.md`, `optional/runtime/view.py`

### Why

view --serve --host tailscale|<ip> with a per-start access key in the link (cookie after first use), read-only unless --allow-actions. Built by a worktree agent; the key replaces the Host allowlist off loopback so tailscale serve needs no config. Rejected: an --allow-host list (user asked for no hostname config).

### Verified

- `checks.lint` — Verified: pass — run 20261122T120513Z, commit 489e0f7
- `checks.unit` — Verified: pass — run 20261122T120513Z, commit 489e0f7
- `checks.integration` — Verified: pass — run 20261122T120513Z, commit 489e0f7
- `checks.build` — Verified: pass — run 20261122T120513Z, commit 489e0f7

### Not done

Origin check behind a proxy that rewrites Host (X-Forwarded-Host) untested; cookie names are per host, not per port

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

view --serve --host tailscale|<ip> with a per-start access key in the link (cookie after first use), read-only unless --allow-actions. Built by a worktree agent; the key replaces the Host allowlist off loopback so tailscale serve needs no config. Rejected: an --allow-host list (user asked for no hostname config).

### Reviews

self-reviewed

## NUHT-035 — Move smoke tests to unittest with selection, a fast unit tier and a parallel pty tier (touch: tests/)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `0bd719a..8964d1e`

### What changed

- fix(NUHT-035): hold the semver unit tests to the 6.0 release levels (8964d1e)
- Merge branch 'v6/NUHT-035' into kit-v6 (8977ae1)
- feat(NUHT-035): add tests/run.py runner and tests/unit parser tests (0bd719a)

Files: `tests/unit/test_semver.py`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/install.md`, `tests/smoke.py`, `.github/workflows/ci.yml`, `tests/run.py`, `tests/unit/_paths.py`, `tests/unit/test_plan_parsing.py`, `tests/unit/test_review_responses.py`

### Why

tests/run.py adds --only, --list and --jobs; tests/unit/ holds unittest cases. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T113710Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T113710Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T113710Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T113710Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

tests/run.py adds --only, --list and --jobs; tests/unit/ holds unittest cases. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-034 — Webhook notifications for blocked, approval-needed and review-blocking events

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `33a0ac9..33a0ac9`

### What changed

- feat(NUHT-034): webhook notifications for parked, review-blocked and approval-needed items (33a0ac9)

Files: `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/extensions.md`, `install.py`, `optional/runtime/finish.py`, `optional/runtime/net.py`, `optional/runtime/notify.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

notify sends webhooks for blocked, approval-needed and review-blocking events. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T112811Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T112811Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T112811Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T112811Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

notify sends webhooks for blocked, approval-needed and review-blocking events. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-033 — Standards discovery: extract codebase conventions via lens

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `49a3967..49a3967`

### What changed

- feat(NUHT-033): standards discovery in sdlc.py lens --area standards (49a3967)

Files: `CHANGELOG.md`, `docs/cli.md`, `optional/runtime/lens.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`

### Why

lens --area standards extracts codebase conventions. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T111906Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T111906Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T111906Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T111906Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

lens --area standards extracts codebase conventions. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-032 — Worktree setup/run scripts for claim and dispatch

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `82193fc..e3d1222`

### What changed

- fix(NUHT-032): never allocate a port without the lock; no empty worktrees (e3d1222)
- feat(NUHT-032): run worktree setup and teardown scripts on claim, release and dispatch (82193fc)

Files: `optional/runtime/claims.py`, `tests/smoke.py`, `CHANGELOG.md`, `docs/cli.md`, `docs/multi-agent.md`, `handbook/process/10-multi-agent.md`, `optional/runtime/dispatch.py`, `optional/runtime/sdlc.py`, `template/docs/process/10-multi-agent.md`, `template/docs/project/charter.md`

### Why

claim and dispatch run per-worktree setup and teardown scripts; a timed-out port lock refuses the claim. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T110954Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T110954Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T110954Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T110954Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

claim and dispatch run per-worktree setup and teardown scripts; a timed-out port lock refuses the claim. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-031 — MCP server extension: backlog, verify, finish, doctor as tools (stdlib JSON-RPC)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `1e93fb1..5a813bd`

### What changed

- fix(NUHT-031): keep install.py --help within its 60 lines (5a813bd)
- Merge branch 'v6/NUHT-031' into kit-v6 (17bed63)
- feat(NUHT-031): serve the records as read-only MCP tools over stdio (1e93fb1)

Files: `install.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/install.md`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `optional/runtime/mcp_server.py`

### Why

sdlc.py mcp serves backlog, verify, finish and doctor over stdio JSON-RPC, stdlib only. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T110044Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T110044Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T110044Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T110044Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

sdlc.py mcp serves backlog, verify, finish and doctor over stdio JSON-RPC, stdlib only. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-030 — Issue-tracker sync extension: GitHub Issues, then Linear and Jira

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `36bc9d9..5c9afc5`

### What changed

- fix(NUHT-030): link items by issue title only for mapped authors (5c9afc5)
- feat(NUHT-030): issues pull|push through gh as the github-issues built-in extension (36bc9d9)

Files: `optional/extensions/github-issues/issues.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/extensions.md`, `optional/extensions/github-issues/nuhut-extension.json`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`

### Why

github-issues extension pulls issues into the backlog; titles link items only for authors mapped in people.json. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T105137Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T105137Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T105137Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T105137Z, commit 8e128c9

### Not done

Linear and Jira extensions; a person copies issues.py into .ai-sdlc/extensions/github-issues/ (trust anchor)

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

github-issues extension pulls issues into the backlog; titles link items only for authors mapped in people.json. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-029 — DORA delivery metrics in metrics and the viewer (touch: optional/runtime/view.py, optional/runtime/view/)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `8d4f289..8d4f289`

### What changed

- feat(NUHT-029): DORA delivery measures in metrics and the viewer (8d4f289)

Files: `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/viewer.md`, `optional/runtime/sdlc.py`, `optional/runtime/view.html`, `optional/runtime/view.py`, `optional/runtime/view/js/12-dashboard.js`, `tests/smoke.py`

### Why

DORA metrics from release and deploy records in metrics and the viewer. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T104227Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T104227Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T104227Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T104227Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

DORA metrics from release and deploy records in metrics and the viewer. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

## NUHT-028 — Hotfix fast path with a doctor check for the retroactive review (touch: optional/runtime/sdlc.py, template/docs/process/05-change-control.md)

**Date:** 2026-11-22 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `a2f0a6f..bf8d00c`

### What changed

- test(NUHT-028): commit the hotfix fixtures with a Work-Item trailer (bf8d00c)
- feat(NUHT-028): hotfix fast path with a retroactive review check in doctor (a2f0a6f)

Files: `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `handbook/process/05-change-control.md`, `handbook/templates/postmortem.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `template/docs/process/05-change-control.md`, `template/docs/project/charter.md`, `template/docs/templates/postmortem.md`

### Why

hotfix marks the fast path; doctor flags a hotfix without a retroactive review inside the charter window. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Verified

- `checks.lint` — Verified: pass — run 20261122T103309Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T103309Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T103309Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T103309Z, commit 8e128c9

### Not done

nothing deferred

### Discovered

nothing

### Decisions

none

### Assumptions used

none

### Plan

hotfix marks the fast path; doctor flags a hotfix without a retroactive review inside the charter window. Built by the v6 roadmap workflow on kit-v6 (plan, design review NUHT-016-design-review.md, build waves, ship review NUHT-016-ship-review.md); verified with its own full verify --item run.

### Reviews

self-reviewed

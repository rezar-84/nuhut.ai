---
status: active
owner: product-manager
last-reviewed: 2026-11-13
---

# Backlog — nuhut.ai

> **This table stays terse. One line per item.** Narrative — what happened, what was
> verified, what was discovered — goes in `worklog.md`, found via the ID.
>
> Column rules, the eight status values, and why the separation matters:
> `../process/07-traceability.md`.
>
> **How the sections and the eight statuses line up.** An item's row moves between
> sections as its status changes; the `Status` cell is always the precise value.
>
> | Section | Statuses it holds | Columns |
> | --- | --- | --- |
> | Now | `In progress`, `In review` | the six-column spec |
> | Next | `Ready` | the six-column spec |
> | Blocked | `Blocked` | six-column spec **+ Who can unblock, Since** |
> | Parked | `Parked` | six-column spec **+ Waiting on whom, For what decision, Since** |
> | Later | `Deferred` | six-column spec **+ Becomes relevant when** |
> | Done | `Done` | six-column spec **+ Completed** |
> | Dropped | `Dropped` | six-column spec **+ Why dropped, When** |
>
> Every section carries the six mandated columns, in order, and adds its own to the
> right. A row never loses a cell by moving — that is how the Owner role and Tier of a
> finished item survive to be looked up later.

## Now

Actively in progress. Keep this short enough to be real — if everything is here, nothing
is prioritised.

| ID | Task | Tier | Owner role | Depends on | Status |
| --- | --- | --- | --- | --- | --- |

## Next

Agreed, not started. Ordered by priority.

| ID | Task | Tier | Owner role | Depends on | Status |
| --- | --- | --- | --- | --- | --- |
| NUHT-012 | finish accepts stale, stage-only or self-waived verify evidence (touch: optional/runtime/finish.py, optional/runtime/sdlc.py, tests/smoke.py) | 1 | qa |  | Ready |
| NUHT-014 | Release pipeline: skip docs-only pushes, serialize runs, rebase before bot push, drop dead release.yml (touch: .github/workflows/version.yml, .github/workflows/release.yml, tools/semver.py) | 1 | devops-sre |  | Ready |
| NUHT-016 | ADR 0003 and registry.py: nuhut-extension.json manifest, loader, version range (touch: optional/runtime/registry.py, install.py, optional/runtime/sdlc.py) | 1 | architect |  | Ready |
| NUHT-022 | ci-check: enforce trailers, ledger run on HEAD, review file and path-derived tier floor in PR CI (touch: optional/runtime/sdlc.py, install.py) | 1 | devops-sre |  | Ready |
| NUHT-024 | Approvals read from GitHub PR reviews instead of charter names (touch: optional/runtime/finish.py) | 1 | security | NUHT-023 | Ready |
| NUHT-027 | Release records and deploy ledger (environment, version, items); rename claim release to unclaim (touch: optional/runtime/) | 1 | devops-sre |  | Ready |

## Blocked

Cannot proceed. The blocker must be a real, identified thing with an owner — not "needs
more thought".

| ID | Task | Tier | Owner role | Depends on | Status | Who can unblock | Since |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Parked — awaiting a human

Built and verified as far as an agent can take it; stopped at an approval or a waiver
only a named human can give. This is a finished state for the agent, not an excuse to
proceed. See "Waiting on a human" in `../process/00-operating-model.md`.

| ID | Task | Tier | Owner role | Depends on | Status | Waiting on whom | For what decision | Since |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NUHT-007 | Fresh-context review as a recorded independence level | 1 | architect |  | Parked | rezar-84 | plan and ADR approval: changes a Tier 1 governance gate | 2026-11-21 |

## Later

Valid, not now. Include the condition that would make it now.

| ID | Task | Tier | Owner role | Depends on | Status | Becomes relevant when |
| --- | --- | --- | --- | --- | --- | --- |
| NUHT-008 | Plugin bootstrap for Claude Code / Codex that runs install.py | 2 | devops-sre |  | Deferred | NUHT-005 and v5.0.0 are released |
| NUHT-009 | sdlc-drift: compare living specs and ADRs with code | 2 | architect |  | Deferred | the Specs row is on in a real project and drift is reported |
| NUHT-036 | Run the kit-value benchmark against bench-baseline-v0 and publish results (touch: benchmarks/) | 3 | qa |  | Deferred | Before v6 release notes make benefit claims |

## Done

Newest first. Move to `worklog-archive/` once this section gets long — the worklog is the
permanent record, and the entry is found by ID.

| ID | Task | Tier | Owner role | Depends on | Status | Completed |
| --- | --- | --- | --- | --- | --- | --- |
| NUHT-035 | Move smoke tests to unittest with selection, a fast unit tier and a parallel pty tier (touch: tests/) | 2 | qa |  | Done | 2026-11-22 |
| NUHT-034 | Webhook notifications for blocked, approval-needed and review-blocking events | 2 | devops-sre | NUHT-018 | Done | 2026-11-22 |
| NUHT-033 | Standards discovery: extract codebase conventions via lens | 2 | architect |  | Done | 2026-11-22 |
| NUHT-032 | Worktree setup/run scripts for claim and dispatch | 2 | devops-sre |  | Done | 2026-11-22 |
| NUHT-031 | MCP server extension: backlog, verify, finish, doctor as tools (stdlib JSON-RPC) | 2 | software-engineer | NUHT-018 | Done | 2026-11-22 |
| NUHT-030 | Issue-tracker sync extension: GitHub Issues, then Linear and Jira | 2 | product-manager | NUHT-018 | Done | 2026-11-22 |
| NUHT-029 | DORA delivery metrics in metrics and the viewer (touch: optional/runtime/view.py, optional/runtime/view/) | 2 | devops-sre | NUHT-027 | Done | 2026-11-22 |
| NUHT-028 | Hotfix fast path with a doctor check for the retroactive review (touch: optional/runtime/sdlc.py, template/docs/process/05-change-control.md) | 2 | devops-sre |  | Done | 2026-11-22 |
| NUHT-026 | status / next: one-line next actions in the CLI (touch: optional/runtime/sdlc.py) | 3 | software-engineer |  | Done | 2026-11-22 |
| NUHT-025 | Merge driver for item shards; rendered backlog and worklog gitignored (touch: optional/runtime/shards.py, install.py) | 2 | software-engineer |  | Done | 2026-11-22 |
| NUHT-023 | People registry: owner and claims name humans (touch: optional/runtime/shards.py, optional/runtime/claims.py) | 2 | product-manager |  | Done | 2026-11-22 |
| NUHT-021 | Split sdlc.py command routing into a command table (touch: optional/runtime/sdlc.py) | 2 | software-engineer | NUHT-016 | Done | 2026-11-22 |
| NUHT-020 | New harness extensions: OpenCode, Kiro, ACP agents (no core changes) (touch: optional/extensions/) | 2 | software-engineer | NUHT-017 | Done | 2026-11-22 |
| NUHT-019 | Generate Claude, Gemini, Codex and Kiro plugin wrappers from the extension manifest (touch: .claude-plugin/, install.py) | 2 | devops-sre | NUHT-017, NUHT-008 | Done | 2026-11-22 |
| NUHT-018 | ext CLI: list, add, remove, update, search, validate; overlays; catalog (touch: optional/runtime/registry.py, optional/runtime/sdlc.py, docs/cli.md) | 2 | software-engineer | NUHT-016 | Done | 2026-11-22 |
| NUHT-017 | Move claude, codex, gemini, cursor support into built-in extensions (one agent table) (touch: optional/extensions/, install.py, optional/runtime/sdlc.py, optional/runtime/dispatch.py, optional/runtime/hooks.py) | 2 | software-engineer | NUHT-016 | Done | 2026-11-22 |
| NUHT-015 | install.sh version floor and wording; finish swallows exceptions silently (touch: install.sh, optional/runtime/finish.py, tests/smoke.py) | 2 | software-engineer |  | Done | 2026-11-22 |
| NUHT-013 | Test-lock and protected-path guards miss shell writes (sed -i, redirects, tee, python -c) (touch: optional/runtime/hooks.py, tests/smoke.py, template/docs/process/05-change-control.md) | 2 | security |  | Done | 2026-11-22 |
| NUHT-011 | Self-install kit_version drifts from VERSION after a release (touch: validate.py, .github/workflows/version.yml, .ai-sdlc/manifest.json, .ai-sdlc/profile.json, AGENTS.md, tests/smoke.py) | 2 | devops-sre |  | Done | 2026-11-22 |
| NUHT-010 | Guided installer draws 40 columns on Python 3.8-3.10 when the terminal reports size 0 (touch: install_ui.py, tests/smoke.py, CHANGELOG.md) | 2 | qa |  | Done | 2026-11-21 |
| NUHT-006 | plan-check --pre: refuse plans that name missing files before the build (touch: optional/runtime/sdlc.py, .ai-sdlc/bin/sdlc.py, tests/smoke.py, docs/cli.md, README.md, CHANGELOG.md) | 2 | architect |  | Done | 2026-11-21 |
| NUHT-005 | Review triage: paraphrase step and Contest/Escalate/Fix/Decline responses, escalations in Needs you (touch: template/docs/process/02-role-reviews.md, template/docs/templates/role-review.md, handbook/process/02-role-reviews.md, handbook/templates/role-review.md, optional/runtime/sdlc.py, .ai-sdlc/bin/sdlc.py, .claude/commands/sdlc-review.md, optional/commands/**, tests/smoke.py, CHANGELOG.md, docs/**) | 2 | qa |  | Done | 2026-11-21 |
| NUHT-004 | Release hygiene: CI Python 3.8 runner, installer names the unreleased version (touch: .github/workflows/ci.yml, install.py, tests/smoke.py, CHANGELOG.md, docs/install.md) | 2 | devops-sre |  | Done | 2026-11-21 |
| NUHT-003 | M3: Multi-worker headless dispatcher (dispatch.py), self-healing defect policy & effort-modes benchmark suite | 1 | architect | NUHT-002 | Done | 2026-11-21 |
| NUHT-002 | M2: Sharded zero-conflict store, git-ref leases, Tier 2 parallel scope globs, universal --json & cached doctor | 1 | architect | NUHT-001 | Done | 2026-11-21 |
| NUHT-001 | M1: Control-plane security hardening, unified Python hook engine, runtime bug fixes & contract reconciliation | 1 | security |  | Done | 2026-11-21 |

## Dropped

**Never delete a row — move it here.** The record that something was considered and
rejected stops it being proposed, discussed, and rejected again. The ID stays reserved.

| ID | Task | Tier | Owner role | Depends on | Status | Why dropped | When |
| --- | --- | --- | --- | --- | --- | --- | --- |

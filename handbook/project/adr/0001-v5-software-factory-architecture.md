---
status: approved
owner: rezar-84
last-reviewed: 2026-11-13
---

# ADR 0001 — v5 Software Factory architecture (unified Python hooks, sharded records, and headless dispatch)

- **Status:** Approved (rezar-84, 2026-11-21)
- **Date:** 2026-11-13
- **Deciders:** rezar-84
- **Work item:** NUHT-001, NUHT-002, NUHT-003

## Context

In Nuhut 4.x, parallel agent sessions in isolated git worktrees collided on three shared append files (`backlog.md`, `worklog.md`, and `evidence-ledger.jsonl`), required external shell utilities (`jq`, GNU/BSD `sed`) inside harness hooks, exposed `action_token` inside `/model.json` when running `sdlc.py view --serve`, and lacked a headless coordinator to execute waves of scoped Tier 2 and Tier 3 items automatically while keeping Tier 1 under human approval.

The project charter requires zero third-party runtime dependencies across Python 3.8+ on macOS and Linux, backward compatibility for existing 4.x repositories, and strict human approval gates on Tier 1 work.

## Decision

We consolidate hook evaluation into a stdlib Python module (`optional/runtime/hooks.py`) invoked by thin POSIX shell shims across Claude Code, Gemini CLI, Cursor, and git hooks; store per-item state, worklog entries, and verification ledger runs as conflict-free shards (`items/<ID>.json`, `worklog/<ID>.md`, `ledger/<run>.jsonl`) with deterministic `sdlc.py render` views and git-ref compare-and-swap claim leases (`refs/nuhut/claims/<ID>`, `refs/nuhut/seq`); and ship a pluggable wave coordinator (`optional/runtime/dispatch.py`) that executes Ready Tier 2 and Tier 3 items in isolated worktrees while keeping Tier 1 plans, merge approvals, and default `Parked` discovered-defect triage human-governed.

## Consequences

**Accepted:**
- Existing 4.x repositories retain single-file records until the maintainer runs `sdlc.py fix migrate-shards --apply`, so the runtime reads both layouts.
- Materialized `backlog.md` and `worklog.md` summaries are regenerated via `sdlc.py render` rather than hand-edited once sharded mode is active.

**Gained:**
- N parallel branches merge cleanly with zero git conflicts on item state, worklog entries, or evidence ledger runs.
- Every hook runs fail-closed on Python 3.8+ stdlib without `jq` or platform-specific `sed`, resolving linked git worktrees and symlinks consistently.
- `sdlc.py doctor` caches unchanged repository snapshots in `.ai-sdlc/cache/doctor.json` for sub-500ms warm execution.
- `sdlc.py dispatch` automates conflict-free multi-worker build/verify/review/finish waves across `claude`, `codex`, `gemini`, or custom `cmd:` runners.

**Follow-ups:**
- Merge `kit-v5` to `main` and cut `v5.0.0` once `rezar-84` approves the Parked Tier 1 items (`NUHT-001`, `NUHT-002`, `NUHT-003`).

## Alternatives considered

### SQLite database committed to git
Binary SQLite files cannot be diffed or merged across git branches, breaking Nuhut's git-native audit trail.

### External Redis or HTTP coordination server
Violates the zero-dependency, offline-capable stdlib charter constraint; git refs (`git push --atomic` / `--force-with-lease`) provide distributed compare-and-swap coordination over existing git remotes.

### Unrestricted autonomous bug-fix loops
Allowing agents to self-create and immediately execute unverified backlog items risks unbounded scope drift and token burn; charter-governed `Discovered defects` (`Parked` by default, or `Auto-Ready (bite)` requiring a passing `sdlc.py bite` reproduction) keeps self-healing bounded.

## Reversibility

Running `git revert` on the `kit-v5` commits or restoring 4.x flat files from rendered `backlog.md` and `worklog.md` reverses the runtime changes without data loss, because every shard renders deterministically back to the 4.x Markdown tables and JSONL ledger schema.

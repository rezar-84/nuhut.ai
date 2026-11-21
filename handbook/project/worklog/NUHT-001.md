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

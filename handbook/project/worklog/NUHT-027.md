## NUHT-027 — Release records and deploy ledger (environment, version, items); rename claim release to unclaim (touch: optional/runtime/)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `6e9c277..c3595b5`

### What changed

- docs(NUHT-027): ship review and responses (c3595b5)
- fix(NUHT-027): release --json stays one document; name near-miss IDs (ef33b5e)
- feat(NUHT-027): deploy record/list release records and ledger; unclaim replaces release (6e9c277)

Files: `install.py`, `optional/runtime/claims.py`, `optional/runtime/sdlc.py`, `optional/runtime/shards.py`, `tests/smoke.py`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `docs/multi-agent.md`, `docs/troubleshooting.md`, `docs/viewer.md`, `handbook/process/10-multi-agent.md` (+7 more)

### Why

User projects had no record of what shipped where. deploy record writes a release record and a deploy ledger line (environment, version, commit range, items), and claim release became unclaim. Rejected: deriving deploys from git tags, which cannot say which environment runs what.

### Verified

- `checks.lint` — Verified: pass — run 20261122T102357Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T102357Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T102357Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T102357Z, commit 8e128c9

### Not done

Deploy ledger ordering under union merge, locking and append durability, and viewer error display (NUHT-062).

### Discovered

Docs for the release alias drifted from the code (fixed in NUHT-061).

### Decisions

ADR 0004 for the findings declined in its review.

### Assumptions used

none

### Plan

[NUHT-027.md](plans/NUHT-027.md)

### Reviews

- [NUHT-027-ship-devops-sre.md](reviews/NUHT-027-ship-devops-sre.md)

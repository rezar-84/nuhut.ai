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

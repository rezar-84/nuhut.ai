## NUHT-016 — ADR 0003 and registry.py: nuhut-extension.json manifest, loader, version range (touch: optional/runtime/registry.py, install.py, optional/runtime/sdlc.py)

**Date:** 2026-11-26 **Tier:** 1 **Effort:** Normal
**Status:** Parked
**Approved:** rezar-84
**Branch/commits:** `kit-v6` / `85dd39f..8ae3d82`

### What changed

- chore(NUHT-016): verify runs and finish for NUHT-037, 038, 040, 042 (8ae3d82)
- chore(NUHT-016): intake follow-ups for remote view, non-GitHub CI and defect awareness (50d1200)
- chore(NUHT-016): record per-item verify runs and close 19 v6 items (efecef1)
- docs(NUHT-016): ship review record, CHANGELOG and 6.0 upgrade notes (c5fc127)
- feat(NUHT-016): extension registry and built-in manifests (44a3523)
- docs(NUHT-016): design review of the v6 roadmap and Tier 1 plans (cf01f39)
- chore(NUHT-016): mark the v6 roadmap items Ready on the owner's direction (c74d529)
- docs(NUHT-016): landscape comparison, v6 roadmap, ADR 0003 extension system, items NUHT-011..036 (85dd39f)

Files: `CHANGELOG.md`, `docs/install.md`, `docs/cli.md`, `install.py`, `optional/extensions/claude/nuhut-extension.json`, `optional/extensions/codex/nuhut-extension.json`, `optional/extensions/core/nuhut-extension.json`, `optional/extensions/cursor/nuhut-extension.json`, `optional/extensions/gemini/nuhut-extension.json`, `optional/runtime/dispatch.py`, `optional/runtime/registry.py`, `optional/runtime/sdlc.py` (+5 more)

### Why

Agent tools were wired by hand in about 25 places across four files, and no third party could add one. ADR 0003 makes each tool, check and hook rule an entry in one nuhut-extension.json manifest that registry.py loads, with a nuhut version range, and code entry points run only for ids the charter allows. Rejected: a plugin API with arbitrary code from day one, which would run unreviewed code inside the hook engine.

### Verified

- `checks.lint` — Verified: pass — run 20261122T084410Z, commit 8e128c9
- `checks.unit` — Verified: pass — run 20261122T084410Z, commit 8e128c9
- `checks.integration` — Verified: pass — run 20261122T084410Z, commit 8e128c9
- `checks.build` — Verified: pass — run 20261122T084410Z, commit 8e128c9

### Not done

The finding 19 fix in .ai-sdlc/extensions/github-issues/issues.py is not synced into this repository's self-install; it is a trust anchor, so the owner copies it or runs install.py . --upgrade.

### Discovered

The 6.0 ship review found 33 issues across the release (smoke failures, semver footer parsing, trailer merging, trusted reads in subdirectories); each has a Fix response in NUHT-016-ship-review.md.

### Decisions

ADR 0003 (extension system, Proposed).

### Assumptions used

Extension manifests are data; only `commands`, hook rules and doctor checks run code, and only for ids in the charter's Extensions allowed row on the default branch.

### Plan

[NUHT-016.md](plans/NUHT-016.md)

### Reviews

- [NUHT-016-design-review.md](reviews/NUHT-016-design-review.md)
- [NUHT-016-ship-review.md](reviews/NUHT-016-ship-review.md)

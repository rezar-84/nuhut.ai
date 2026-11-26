## NUHT-059 — A routing check in validate.py: each skill's description picks its own prompts and no two collide (touch: validate.py, tests/skill-routing.json, optional/skills/)

**Date:** 2026-11-26 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v6` / `09269ff..09269ff`

### What changed

- feat(NUHT-059): validate checks that each skill's description picks its own prompts (09269ff)

Files: `CHANGELOG.md`, `CONTRIBUTING.md`, `optional/skills/sdlc-content-seo/SKILL.md`, `optional/skills/sdlc-doctor/SKILL.md`, `optional/skills/sdlc-evidence-check/SKILL.md`, `optional/skills/sdlc-postmortem/SKILL.md`, `optional/skills/sdlc-service-contract/SKILL.md`, `tests/skill-routing.json`, `tests/smoke.py`, `validate.py`

### Why

Nothing checked that a skill fires on the prompts people type; a description missing the right words fails silently. validate.py now scores 72 prompts against the descriptions and fails on a misroute or a collision. It found five descriptions missing everyday words. Rejected: graded runs of a real agent per skill, which spend tokens and belong outside CI.

### Verified

- `checks.lint` — Verified: pass — run 20261125T114726Z, commit 09269ff
- `checks.unit` — Verified: pass — run 20261125T114726Z, commit 09269ff
- `checks.build` — Verified: pass — run 20261125T114726Z, commit 09269ff

### Not done

Graded behaviour runs per skill are not built. The shared skill structure (When not to use, Red flags, excuses table) is the next item.

### Discovered

Five skill descriptions lacked words people use (rolled back, accurate, health check, meta descriptions, queue message).

### Decisions

none

### Assumptions used

Word overlap between a prompt and a description approximates how an agent picks a skill; it is a floor, not a guarantee.

### Plan

Inline: check_skill_routing in validate.py with tests/skill-routing.json; smoke test test_skill_routing covers missing cases, misroutes and collisions.

### Reviews

qa (same session, not independent): Pass

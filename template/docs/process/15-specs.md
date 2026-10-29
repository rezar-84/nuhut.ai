# 15 — Living specs

**Read this when** the charter's **Specs** row is `on`. Otherwise nothing in it applies;
plans and acceptance criteria carry behaviour as before.

A spec says what the system does now, as requirements with scenarios
(`project/specs/<capability>.md`). A plan says what one work item will change. Keeping the
two apart is the point: after a hundred items, nobody can reconstruct current behaviour
from a hundred plans, but anyone can read one spec.

## When a spec change is required

- **Tier 1 and Tier 2 items whose plan changes behaviour** someone outside the code can
  observe: an API response, a rule, a permission, a screen's outcome. The plan's
  **Spec changes** line links `project/specs/changes/<ID>.md`, or says `none` and why.
- **Tier 3**, refactors, and changes no user or caller can observe: none.

## How

1. While planning, write `project/specs/changes/<ID>.md` from
   `templates/spec-change.md`: ADDED, MODIFIED (the whole requirement as it will read)
   and REMOVED requirements, each under the capability it belongs to.
2. Tests come from the scenarios: every WHEN/THEN is a test or an acceptance check.
3. On close, `python3 .ai-sdlc/bin/sdlc.py spec apply <ID> --write` merges it and archives
   the change. It matches MODIFIED and REMOVED by exact requirement name and refuses on a
   missing or repeated name, rather than guessing.
4. `sdlc.py doctor` warns about a requirement with no scenario, a change that names a
   requirement that does not exist, and a Done item whose change was never applied.

## Specs written elsewhere

An `openspec/` folder is read as-is (same headings), and Spec Kit feature specs
(`specs/<feature>/spec.md` beside `.specify/`) best-effort: `FR-###` lines and
Given/When/Then scenarios. Both appear in the viewer with their source. The kit never
rewrites them, and never fails a check on them.

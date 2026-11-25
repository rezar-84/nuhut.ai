# NUHT-047: Ready items with code commits are not "Ready to take"

Tier 2 · fix · software-engineer

## Problem

`claims.parallel()` makes every unclaimed Ready (Next column) item with a plan a
candidate. On kit-v6, seven Tier 1 items (NUHT-012, 014, 016, 022, 024, 027, 041) are
Ready although commits with their `Work-Item` trailer already change code. `status`
prints them under "Ready to take" and suggests `claim NUHT-012`; `parallel` and
`dispatch` would schedule them for a second build.

## Change

- `claims.parallel()`: an item whose `Work-Item` commits change a path outside
  `<docs>/project/` is not a candidate. It goes to a new `built` list. A commit that
  touches only records (a plan file, the item shard) does not count as built.
- `status`: a "Built, not finished" section lists those items with
  `finish <ID> --dry-run` as the next command. "Ready to take" no longer shows them.

## Files that change

- `optional/runtime/claims.py`
- `optional/runtime/status.py`
- `.ai-sdlc/bin/claims.py`, `.ai-sdlc/bin/status.py` (byte-identical copies)
- `tests/smoke.py`

## Tests

In `test_status`: a Ready item with a code commit carrying its trailer is absent from
Ready and present under "Built, not finished"; a Ready item whose only trailer commit
touches its plan file stays Ready. Shown failing before the change.

## Rollback

Revert the commit. No stored data changes.

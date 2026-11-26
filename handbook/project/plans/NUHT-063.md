# NUHT-063: Approvals survive finish's records commit and stale item branches

Tier 1 (it changes the approval and evidence gates) · fix · security. This was found when
the owner's approval loop of 2026-11-26 left NUHT-012, 014, 016, 022, 024 and 027 Parked.

## Problem

- **A stale item branch voided approvals.** `local_approvals` compared an approval with
  the item's local branch when one existed. The old `v6/NUHT-012` … `v6/NUHT-027` branches
  were already merged, their tips predated the approval, and the approval was voided.
- **finish's own records commit voided approvals.** An approval was bound to the item's
  newest commit of any kind. `finish --commit` (NUHT-057) writes a records commit with the
  item's trailer after an approval, which then voided it.
- **Another item's verify run blocked this item.** A run tagged for NUHT-061 that ran on
  NUHT-027's records commit counted as NUHT-027 evidence. With NUHT-061's "a newer failing
  run blocks" rule, it blocked NUHT-027.

## Change

- `item_branch`: a branch already merged into HEAD is not the merge candidate; HEAD is
  used instead.
- `local_approvals`: binds to `newest_code_commit` (records-only commits skipped).
- `evidence_matches`: a ledger row tagged for another item is never this item's evidence.

## Files that change

- `optional/runtime/finish.py`, `optional/runtime/sdlc.py` (plus their `.ai-sdlc/bin/` copies)
- `tests/smoke.py`: `test_tier1_approval_count_and_local_approval`, `test_fast_verify`
- `CHANGELOG.md`

## Tests

All three were shown failing before the change:
- "a records-only commit with the item's trailer keeps the approval";
- "a branch named for the item that is already merged is not the merge candidate";
- "a run tagged for another item does not count as this item's evidence".

## Rollback

Revert the commit. Approvals then void again on records commits and stale branches.
That is stricter, not looser.

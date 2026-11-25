---
status: current
owner: architect
last-reviewed: 2026-11-23
---

# Plan: NUHT-043 How many approvers Tier 1 needs, and approving without GitHub

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-024 (approvals), NUHT-012 (trusted
records). **Approval to build:** the owner, 2026-11-23, in session ("number of approvers is
based on project config, maybe 1 or 2"; finding 18 left to the recommended rule).

## Problem

Tier 1 needs two approvals, hard-coded. A one-person project lists one approver, so no
Tier 1 item can close. Approvals are read only from GitHub reviews, and GitHub does not let
a PR's author approve it, so a solo owner cannot approve at all, and a project on another
host has no way to approve. Ship review finding 18: any mapped reviewer who is not the
author counts, whether or not they are in **Approvers**.

## Outcome

- Charter row **Tier 1 approvals**: `2` (default, also when missing) or `1`, read from the
  default branch through `trusted_text`, so a branch cannot lower it for itself.
- `sdlc.py approve <ID> --by <handle>`: the approver must be in **Approvers** on the default
  branch, and an agent's session with no terminal is refused (`finish.check_waiver`, now
  with `act="approve"`). Kept in the shard's `local_approvals` as `{handle, commit, as, at}`
  against the item's newest `Work-Item:` commit; it stops counting when a newer commit
  names the item.
- `approvals()` counts GitHub reviews and local approvals, each handle once.
- A GitHub review counts only when its handle is in **Approvers** (`not-an-approver`).

## Files that change

- `optional/runtime/sdlc.py`: `tier1_approvals()`, `approve` command
- `optional/runtime/finish.py`: `approvals()`, `local_approvals()`, `approve()`,
  `check_waiver(act=)`, `SOLO_HINT`
- `optional/runtime/shards.py`: `local_approvals` kept by `normalize_item`
- `.ai-sdlc/bin/*`: byte-identical copies
- `template/docs/project/charter.md`, `template/docs/process/05-change-control.md`
- `tests/smoke.py`: `test_tier1_approval_count_and_local_approval`, `test_github_approvals`
- `docs/cli.md`, `README.md`, `CHANGELOG.md`, `handbook/project/charter.md`

## Alternatives rejected

- **Count the charter fallback names.** They are a list, not an act of approval.
- **Let one approval suffice whenever Approvers lists one person.** The count would then
  fall silently when a team shrinks; the row makes it a decision.

## Failure modes

- A local approval is not signed: anyone who can write the shard can forge one, as with
  waivers (finding 14). The terminal check binds when the approval is given, not later.
- An agent that runs `approve` through a pseudo-terminal passes the terminal check. Same
  limit as waivers.

## Test strategy

Written first, failing on the old code: default 2; row 1 sets the count; agent without a
terminal refused; non-approver refused; approver approves and the count is met as
`local`; a later commit unmeets it; a branch lowering the row gains nothing; a mapped
non-approver's GitHub review is `not-an-approver`.

## Rollback

Revert the commit. Shards keep an extra `local_approvals` field that older readers drop.

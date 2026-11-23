---
status: current
owner: architect
last-reviewed: 2026-11-23
---

# Plan: NUHT-041 Block a release while an S0 or S1 defect is open

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-040 (severity on items), NUHT-027
(`deploy record`). **Approval to build:** the owner, 2026-11-22, in session.

## Problem

The severity ladder in `CARD.md` says an S1 is a release blocker and an S2 blocks unless a
named human waives it in writing. Nothing enforces either rule. `deploy record` writes a
release record whatever is open.

## Outcome

- `deploy record` refuses while an open defect is S0 or S1, unless the deployed range carries
  a commit whose `Work-Item:` trailer is that defect. That exception is the fix shipping.
- It refuses an open S2 unless `--accept-defects <ID,...> --by <approver> --reason "..."`
  names it. The approver is checked with the same rule a verify waiver uses
  (`finish.check_waiver`: the charter's Approvers row on the default branch, and no agent
  session without a terminal). The record keeps `accepted_defects: [{id, severity, by,
  reason}]`.
- S0 and S1 cannot be accepted. The ways out are a fix in the range, a severity change
  (`item set --severity`, kept in the shard's history), or Dropped.
- `--dry-run` reports the same refusal and writes nothing.
- A promotion of an already recorded version to another environment is checked the same
  way against the items in the stored record.

## Addition, 2026-11-23: who may lower a severity

The owner's decision: a severity is lowered by a person, or by an agent after a second
agent confirms it without bias.

- Raising a severity, or moving between S3 and S4, is free.
- Lowering an S0, S1 or S2 from an agent's session with no terminal needs a blind
  re-rating (`sdlc.py rerate <ID> --by <agent>`) taken at the current severity by an agent
  of another model family, and no re-rating at that severity may rate it more severe than
  the new value, so running it again until one agrees does not work.
- The re-rating prompt holds the ladder and the defect report with every severity removed.
  `cmd:` reviewers are recorded, never counted.
- Each change goes in the shard's `severity_history`; each re-rating in `severity_reviews`
  and `reviews/<ID>-severity[-n].md`.
- Not done: `ci-check` flagging a downgrade with no record. The record is in the shard,
  which `ci-check` does not diff yet.

## Files that change

- `optional/runtime/releases.py`: `release_blockers()` and the check in `record()`
- `optional/runtime/sdlc.py`: `deploy record --accept-defects`, `--reason`; output
- `.ai-sdlc/bin/releases.py`, `.ai-sdlc/bin/sdlc.py`: byte-identical copies
- `tests/smoke.py`: `test_release_defect_gate`
- `docs/cli.md`, `CHANGELOG.md`, `template/docs/process/04-quality-gates.md` if it names the
  release rule

## Alternatives rejected

- **Allow accepting an S1.** The ladder has no waiver for S1, and an accepted S1 is a lowered
  severity without a record. Changing the severity leaves one.
- **Block in `ci-check`.** A PR is not a release; open defects on main should not block
  unrelated PRs.
- **Block in `tools/semver.py` for the kit's own release.** Separate; the kit's release is
  gated by `version.yml` and a human merge.

## Failure modes

- Records unreadable: the check fails closed with the error, the same as other record reads.
- A defect with no severity is not blocking (unrated), and `status` does not list it.

## Test strategy

The smoke test is written first and must fail on the current code:
- open S1 refuses, naming the defect;
- a deploy whose range has the S1's `Work-Item:` commit passes;
- an open S2 refuses without acceptance;
- `--accept-defects` by a non-approver is refused;
- acceptance by an approver records `accepted_defects`;
- an S1 in `--accept-defects` is still refused;
- a Done defect does not block;
- `--dry-run` refuses the same way.

## Rollback

Revert the commit. Release records written meanwhile keep an extra field, which readers
ignore.

## Out of scope

Blocking a release on an open S3 or S4, and signing acceptances (waivers are not signed
either; ship review finding 14).

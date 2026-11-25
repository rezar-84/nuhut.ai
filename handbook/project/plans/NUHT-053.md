# NUHT-053: Fast verify

Tier 1 (it changes the evidence `finish` and `ci-check` accept) · feat · software-engineer.
Approved to build by rezar-84 on 2026-11-25 (the "speed fixes first" decision).

## Problem

`finish` accepts only a run that covered every charter stage on the item's newest code
commit. In this repository that is the full smoke suite: about 10 minutes per item, run
locally and then again in CI. The same applies in every project with a slow integration
stage, and it was the largest cost in the last session.

## Change

- **Charter row `Verify at finish`.** It is `full` (the default, as today) or
  `fast: <stages>`. `sdlc.verify_fast_stages()` reads it from the default branch
  (`trusted_text`, as **Tier 1 approvals** is read), so a branch that turns it on gains
  nothing until it merges. Only stages the charter gives a command count.
- **`verify --item <ID>`.** On a Tier 2 or 3 item, with the row set to fast, it runs only
  the fast stages, marks the ledger rows `mode: fast` and says so. `--full` runs every
  stage. A Tier 1 item always runs every stage.
- **Who accepts the run.** `finish.verify_state(..., tier)` treats a run covering the
  fast stages as full at Tier 2 and 3. `ci-check` passes the tier through.
- **CI.** CI's own job keeps running every stage. It is the full check, and it binds only
  when the host requires the job (ADR 0004).

## Files that change

- `optional/runtime/sdlc.py`, `optional/runtime/finish.py`, and their `.ai-sdlc/bin/` copies
- `template/docs/project/charter.md`
- `tests/smoke.py` (`test_fast_verify`, plus the `test_upgrade_to_41` allowlist)
- `docs/cli.md`, `CHANGELOG.md`
- This repository: `handbook/project/charter.md` gets `fast: lint, unit, build`, and
  `checks.unit` becomes a smoke subset of about a minute.

## Risks

- **A failure surfaces later.** It is found in CI at the pull request rather than at
  `finish`. Mitigated by requiring the CI job (the owner's branch-protection setting) and
  by keeping Tier 1 on full verify.
- **The fast set is too thin.** It is a charter decision, read from the default branch.

## Tests

`test_fast_verify` covers:
- a branch's own row is not trusted;
- with fast on the default branch, a Tier 2 item runs only the fast stages, and the ledger says `mode: fast`;
- `finish` accepts that run;
- `--full` runs every stage;
- a Tier 1 item always runs every stage, and `finish` takes that run.

It was shown failing before the change.

## Rollback

Set the row to `full`, or revert the commit. Runs already recorded as `mode: fast` stop
counting under `full`, so the affected items need a full `verify --item`.

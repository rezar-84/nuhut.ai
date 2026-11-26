---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-014

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (590 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## devops-sre

Verdict: Block

Paraphrase: NUHT-014 consolidates publication into `version.yml`, with a planning job that classifies commits and a serialized release job that validates, bumps, tags, and publishes eligible changes on `main`. The release job checks for superseding commits twice and pushes the release commit and tag atomically, but GitHub Release creation remains a separate operation. Semantic-version calculation now ignores non-release commit types and searches trailing footer paragraphs for breaking changes; validation also checks the computed version against changelog headings and extension examples.

Checked: Static review of the supplied diff, charter rows, and DevOps/SRE playbook, including release sequencing, concurrency guards, partial failures, recovery, validation coverage, and footer parsing.

Not checked: Execution of tests, GitHub Actions runs, repository settings, approval enforcement, non-production rollout or rollback, and files or charter command rows not supplied. No verification results were provided.

Findings:
| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | Tier 1 release change; release runbook/evidence absent from supplied material | No exact rollback procedure or recorded non-production execution is supplied. The playbook explicitly requires both for Tier 1 changes. | Recovery from a faulty release workflow remains unproven. | Provide a rollback procedure covering workflow restoration and already-published release state; execute it outside production and record the result under NUHT-014. |
| 2 | S2 | `.github/workflows/version.yml`, `git push --atomic` followed by `gh release create` | Publication is not resumable after a successful push and failed GitHub Release creation. Rerunning the original job encounters a changed `origin/main` and exits as superseded; the removed tag workflow provides no recovery route. | The version commit and tag can exist without a GitHub Release, with retries reporting supersession instead of repairing publication. | Add an idempotent recovery path that verifies the existing tag and creates the missing release without another bump. Document and exercise failure immediately after the atomic push. |
| 3 | S2 | `.github/workflows/version.yml`, validation steps; `tests/unit/test_semver.py` | The release job explicitly runs compilation, `validate.py`, and smoke tests, but does not explicitly run the added unit tests. No supplied evidence establishes that those commands execute them or cover the charter’s full sequence. | The new footer regression tests may not gate publication. | Run the unit suite in the release gate, or demonstrate the existing invocation that runs it; reconcile the gate with the full charter command sequence. |
| 4 | S2 | `tools/semver.py`, `_footer_only()` / `footer()` | A multiline breaking-change paragraph with an unindented continuation is excluded when followed by a separate trailer paragraph. For example, `BREAKING CHANGE: removed API\nUse the replacement.` followed by a blank line and `Co-Authored-By: ...` stops backward scanning before the breaking marker. | A breaking change can still receive a minor or patch release depending on trailer layout. | Recognize multiline breaking-footer values before subsequent trailers and add a regression test for this case. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Decline | Shipped in 6.0.0 (merged to main and pushed); later commits build on it, so reverting this item alone is not a meaningful rehearsal. The rollback for a kit release is reinstalling the previous version: `install.py <project> --upgrade` from the v5.0.0 tag, which the upgrade path and its tests cover (test_upgrade_to_41). | |
| 2 | Decline | Tracked as NUHT-062: make release creation resumable when the tag exists at HEAD. | |
| 3 | Decline | Tracked as NUHT-062 (it changes the release job, which needs the owner's approval). | |
| 4 | Decline | Tracked as NUHT-062. | |

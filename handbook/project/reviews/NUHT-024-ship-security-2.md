---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-024

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (1281 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change reads GitHub PR reviews through `gh`, maps reviewers to registered people, and counts distinct approvals on the PR head while excluding bots, self-approvals, and superseded verdicts. `finish` uses that count to move gated items from Parked to Done and stores approval provenance in item shards. Missing GitHub evidence leaves gated items Parked; the follow-up change exempts Standard Tier 2 and Tier 3 items. The approval path nevertheless has trust-boundary and fail-open gaps.

Checked: Both supplied commits, mirrored runtime changes, CLI wiring, approval persistence, documentation, and supplied test cases; static examination against the supplied security playbook and charter rows.

Not checked: Test execution, live GitHub responses, helper implementations outside the diff, merge enforcement, branch protection, threat model, security/privacy records, or agent credential restrictions.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | Both `finish.py` copies: `mapping_trusted` | `people_source != "working-tree" or not rt.trusted_ref(project)` explicitly accepts working-tree identity mappings when no trusted reference exists. Missing trusted configuration increases trust instead of denying it. | Branch-controlled mappings can establish reviewer identities and satisfy the human approval count when the trusted reference is unavailable. | Require a trusted registry source for counted approvals. Otherwise remain Parked with an explicit diagnostic. Add a denial test for an absent trusted reference and attacker-edited registry. |
| 2 | S1 | Both `finish.py` copies: repository discovery and PR validation | The repository returned by `gh repo view` is used without comparison to an independently trusted project repository. `isCrossRepository == False` establishes only that the PR is internal to the selected repository; fetched repository fields and `baseRefName` are not validated. | A redirected repository selection can supply approvals from another repository containing the same commits and branch name. Those approvals can close the local item without approval of the intended repository’s merge. | Bind the query to a trusted repository identity and permitted target branch, and validate the returned PR against both. Test a different repository with identical branch/head data and an unintended base branch. |
| 3 | S1 | Both `finish.py` copies: PR author validation | A missing or invalid PR author becomes an empty `author_key`; counting continues. The code therefore cannot establish reviewer independence but still permits approval. | Malformed evidence can bypass the self-approval exclusion and satisfy the gate. | Reject approval evidence unless the PR author is valid and independence can be evaluated. Add missing-author and malformed-author denial tests. |
| 4 | S2 | Both `finish.py` copies: revised `required` calculation | Every tier other than the exact strings `"1"` and Strict `"2"` receives zero required approvals and `met=True`; there is no explicit rejection of an unexpected non-`None` tier. | Invalid classification can be reported as approval satisfied rather than invalid evidence. Whether normal callers can produce this depends on helpers absent from the diff. | Validate the tier against the supported values before computing requirements; reject unknown values. Test malformed tiers and confirm caller normalization. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Decline | Declined under ADR 0004 (approved 2026-11-25): without a trusted ref the kit reads the working tree, as everywhere else; authentication is the host's required checks and reviews, not a local record. | |
| 2 | Decline | Declined under ADR 0004 (approved 2026-11-25): without a trusted ref the kit reads the working tree, as everywhere else; authentication is the host's required checks and reviews, not a local record. `gh` acts as the signed-in user on the repository it names. | |
| 3 | Fix | NUHT-061: a PR with no readable author falls back and counts no GitHub review. Test: "a PR with no readable author counts no GitHub review (NUHT-024 retro, finding 3)". | |
| 4 | Fix | NUHT-061: an unreadable tier is judged as Tier 1 in `approvals`. | |

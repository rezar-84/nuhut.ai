---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-063

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (252 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change makes local approvals depend on the item's newest code commit instead of its newest commit of any kind, allowing approvals to survive records-only commits. It also ignores a discovered item branch whose tip is already an ancestor of HEAD, while retaining the early return for the currently checked-out item branch. Evidence matching now excludes runs explicitly tagged for another item while retaining eligibility for untagged runs. The supplied diff does not show how `newest_code_commit` distinguishes harmless bookkeeping from security-relevant changes, so I cannot establish the boundary of the approval exemption.

Checked: Supplied runtime and installed-copy hunks, approval and evidence regression tests, plan, changelog, and item record against the supplied security playbook and charter rows.

Not checked: Full approval enforcement and its callers; `newest_code_commit`, `_is_ancestor`, and branch-discovery implementations; threat model; approval provenance; actual test execution or failing-before-fix evidence. Review used only the supplied material.

Findings:
| # | Sev | Location | Finding | Consequence | Fix |
|---|---|---|---|---|---|
| 1 | S2 | `optional/runtime/finish.py:local_approvals` and installed copy | Approval freshness now depends on `newest_code_commit`, but its classification and empty-result behavior are absent from the supplied material. The added test establishes only that appending whitespace to an item shard preserves approval. It does not establish that security-relevant record changes invalidate approval. | The review cannot rule out stale approval surviving changes to governance or approval-bearing records. This is an enforcement assurance gap, not a demonstrated bypass. | Supply the classifier and downstream freshness checks. Add denial tests for substantive security-bearing record changes and the no-code-commit case; demonstrate fail-closed behavior where approval coverage cannot be established. |
| 2 | S2 | `tests/smoke.py`: NUHT-063 approval and evidence tests | New coverage demonstrates acceptance of bookkeeping and a stale branch, plus exclusion of another item's failing run. It does not exercise the changed boundaries' denial cases: an unmerged candidate with unapproved work, a same-item newer failing run through this filter, or rejection of another item's passing run as substitute evidence. | Security gate regressions could satisfy the added tests while accepting unapproved work or insufficient verification. | Add those negative cases and provide executed results, including failing-before-fix evidence for the defect regressions. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Fix | `newest_code_commit` (sdlc.py) skips only commits whose every path is under `<docs>/project/` other than the charter (`records_path`); a commit that touches the charter or any code counts. Test: "a commit with the item's trailer that changes the charter voids the approval (NUHT-063 review)". | |
| 2 | Fix | Denial cases added: "an unmerged item branch with work after the approval voids it (NUHT-063 review)"; "another item's failing or passing run is not this item's evidence (NUHT-063)". A same-item newer failing run still blocks through the filter: "a newer failing --stage run blocks finish after an older full pass". | |

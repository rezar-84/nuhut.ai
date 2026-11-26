---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-061

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (257 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## qa

Verdict: Pass with conditions

Paraphrase: This change makes `verify_state` reject a fresh failing run before skipping partial or incomplete runs, preventing an older full pass from masking that failure. The approvals gate treats an unrecognised tier as Tier 1 and falls back when the PR author cannot be read, because reviewer independence cannot then be established. Both runtime copies receive identical changes, two smoke scenarios are added, and the documentation clarifies how the deprecated `release` alias reports its warning.

Checked: Static review of the supplied diff against the QA playbook and charter rows; gate ordering, runtime-copy consistency, regression assertions, and plan-to-test coverage.

Not checked: Test execution, failing-before-fix evidence, full function and fixture context, acceptance criteria outside the supplied plan, test-plan coverage records, supported-platform execution, or actual GitHub/CLI journeys. No charter Commands rows or verification results were supplied.

Findings:
| # | Sev | Location | Finding | Consequence | Fix |
|---|---|---|---|---|---|
| 1 | S2 | `tests/smoke.py`; `approvals` tier fallback | No regression test is supplied for the new unknown-tier approval requirement. This is one of the three gate fixes in the plan. | Removing the fallback could restore approval bypass without either added test detecting it. | Add a named test showing an unreadable tier requires Tier 1 approvals and refuses insufficient approvals; demonstrate it fails without the fix. |
| 2 | S2 | `tests/smoke.py::test_fast_verify` | The new scenario discards the selected verify command’s exit status and output, then checks only that finish output lacks `verify   pass` and contains `fail` somewhere. It does not explicitly establish that the intended lint failure occurred or that the verification gate reports failure. | An unrelated error could satisfy the assertion without exercising the intended newer-failure-over-older-pass behavior. | Assert the selected run fails at lint, establish the older full pass is current, and assert finish’s verification result specifically reports failure. Demonstrate the test fails with the original implementation. |
| 3 | S3 | `tests/smoke.py::test_github_approvals` | The missing-author test checks refusal and its note, but not that zero GitHub reviews are counted, as the plan requires. Only a null author is exercised. | Partial counting or malformed-author handling could regress without this test detecting it. | Assert no GitHub approvers count, and cover an absent author and malformed or empty author login. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Fix | test_github_approvals calls `approvals` with tier "x": "an unreadable tier is judged as Tier 1 and needs approvals (finding 4)"; it fails with the fallback removed. The shard loader already turns an unreadable tier into 2, a separate leniency tracked in NUHT-062. | |
| 2 | Fix | test_fast_verify asserts the --stage lint run exits non-zero with `checks.lint` Verified: fail, and that finish's verify line reports the failure. | |
| 3 | Fix | The missing-author check now covers a null, absent and empty-login author, and asserts no GitHub approver is counted. | |

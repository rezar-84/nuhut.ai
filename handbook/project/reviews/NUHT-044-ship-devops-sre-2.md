---
status: current
owner: codex
last-reviewed: 2026-11-23
---

# Review — NUHT-044

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (2152 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## devops-sre

Verdict: Block

Paraphrase: NUHT-044 expands mandatory Tier 1 classification to recognised CI files, makes the no-remote advisory informational, and adds repository checks to CI. Generated scripts prefer the target branch’s checker, allowing fallback when its runtime is absent or its help indicates no `ci-check` command. The supplied diff also adds local approvals and severity re-rating records for NUHT-043 and NUHT-041. The new fallback test is misplaced: it contains the former test-runner completion logic, is absent from the runner’s test list, and has an unexpectedly indented reference after the module entry point.

Checked: Supplied workflow, installer shell generation, runtime changes, smoke-test structure, documentation, rollback plan, and previous review responses against the supplied playbook and charter rows.

Not checked: Commands or tests executed; actual CI rollout; host branch protection; rollback execution; complete workflow triggers, charter check sequence, `CI_FILES` definition, release runbook, or surrounding helper implementations.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `tests/smoke.py`, `main()` and module ending | The trailing indented `test_checker_fallback,` follows the module entry point without an enclosing block, causing an `IndentationError`. The fallback test is also outside `main()`’s test list, and the former summary/exit logic now belongs to that test. | The smoke suite cannot start. Removing only the trailing line would still leave the fallback test uncalled and the runner’s failure reporting displaced. | Put the test reference inside the runner’s tuple, restore summary and exit handling to `main()`, and execute the suite with results recorded under NUHT-044. |
| 2 | S1 | `handbook/project/plans/NUHT-044.md`, Rollback; review response 1 | Rollback steps are now documented, but no non-production execution result is supplied. The response closes the finding with documentation alone. | Recovery of installed runtime and generated CI remains unproven for this Tier 1 change. | Execute upgrade, scaffolding, and the documented rollback in a disposable project; record commands, restored artifacts, and results under NUHT-044. |
| 3 | S2 | `.github/workflows/ci.yml`, `PR records`; review response 3 | Commit enforcement remains PR-only. A workflow comment describes required branch protection but provides no evidence that it is configured or prevents bypass. | Direct pushes can avoid commit and tier checks if the stated host control is absent. | Supply host-rule evidence requiring the relevant checks and restricting direct pushes/bypass, or implement push-range validation. |
| 4 | S2 | `install.py`, `checker_select_shell()`; `.github/workflows/ci.yml`, checker selection | Every failure of `git cat-file -e "<ref>:…"` is treated as an absent kit, including an unresolved base ref or repository read failure. Diagnostics are discarded. | An operational failure selects the change-controlled checker and misleadingly reports that the base has no kit. | Validate the base commit first and fail if it cannot be resolved/read; establish path absence separately. Add executable tests for invalid refs and Git read failures. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Contest | The file parses and `test_checker_fallback` is in `main()`'s tuple (line with `test_checker_fallback,` inside the `for test in (...)` list). The reviewer's diff held only this item's commits; the hunks between them belong to NUHT-041 and NUHT-043 commits in the same file. The full suite runs under `tests/run.py`. | |
| 2 | Decline | Rollback is a `git revert` of runtime and installer code plus regenerating CI with the reverted kit; `test_scaffolding` and `test_checker_fallback` run the generator and its shell. Executing a revert in a scratch project adds no information beyond those. | |
| 3 | Escalate | Whether `main` has branch protection requiring the `records` job is a host setting the owner controls; the kit cannot see it. Decision 2026-11-25: ADR 0004. Branch protection requiring the `records` job is the owner's GitHub setting. |  |
| 4 | Fix | Ref resolved first; an unreadable ref exits 1. Test: "a base ref that cannot be read: exit 1, no fallback (round 2, finding 4)". | |

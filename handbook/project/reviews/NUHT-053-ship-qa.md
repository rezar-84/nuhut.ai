---
status: current
owner: codex
last-reviewed: 2026-11-25
---

# Review — NUHT-053

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (582 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## qa

Verdict: Block

Paraphrase: This change lets Tier 2 and 3 items run and satisfy verification with a subset of stages configured on the default branch. It marks those runs as fast and passes the item tier into the evidence checks used by `finish` and `ci-check`; Tier 1 retains the full required stage set. It also adds `--full` and a test-runner option that excludes serial tests. However, the stage parser consumes explanatory prose as configuration, so the supplied charter inadvertently includes integration in its fast set.

Checked: Static review of the supplied runtime changes, mirrored copies, charter configuration, documentation, plan, and tests against the QA playbook.

Not checked: Test execution, failing-before-change evidence, existing helper implementations outside the diff, actual CI workflows or branch protection, supported-platform execution, and acceptance-criteria/test-plan records not supplied.

Findings:
| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S2 | `optional/runtime/sdlc.py:verify_fast_stages` and mirrored copy; `handbook/project/charter.md` | The parser strips formatting and tokenizes the entire cell, including its explanation. The supplied explanation contains `checks.integration,`, which becomes the recognized stage `integration`. The test uses a bare configuration cell and misses this. | This repository's fast mode still runs integration, defeating the intended reduction in verification time. | Parse only the configuration portion, with an explicit boundary before explanatory text. Add a regression using the exact supplied charter cell and assert the resulting stage list excludes integration. |
| 2 | S2 | `tests/smoke.py:test_fast_verify` | Tests show successful fast and full runs, but do not establish the critical refusal paths: Tier 1 rejecting fast-only evidence, failed or missing fast stages being rejected, explicit stage selections remaining insufficient, and switching back to `full` invalidating fast-only evidence. Tier 3 and the changed `ci-check` path are also untested here. | Regressions in the relaxed evidence gate could accept insufficient evidence without these tests detecting them. | Add named positive and negative tests for both evidence consumers, including rollback and Tier 3. Demonstrate that important refusal assertions fail when their enforcement is removed. |
| 3 | S2 | Plan “CI”; verification output and CLI documentation | Full CI execution is the stated replacement for omitted local stages, but no workflow or end-to-end evidence is supplied showing that omitted-stage failures prevent merge. The new output states “CI runs every stage” unconditionally. | The central mitigation for reduced local coverage remains unverified, and the output promises behavior that this code does not establish. | Supply a realistic CI boundary test showing a fast-passing item with a failing omitted stage fails the full job. Document the required-job prerequisite alongside the CLI behavior and qualify the runtime message. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Fix | Did not reproduce: the note in `_( )_` is stripped before parsing, and `test_fast_verify` now uses a cell with a note naming `checks.integration` ("with fast on the default branch, a Tier 2 item runs only the fast stages"). Hardened anyway: `verify_fast_stages` reads only the first code span. | |
| 2 | Fix | `test_fast_verify` adds: "a fast run stops counting once the item is Tier 1", "turning fast off on the default branch makes the fast run insufficient", "a Tier 3 item runs only the fast stages too", "a failing fast stage fails the fast run", "finish refuses a failed fast run". `ci-check` calls the same `verify_state` with the item's tier; no separate ci-check case. | |
| 3 | Fix | The runtime message and `docs/cli.md` now say the omitted stages stop a merge only when the host requires the CI job. A CI boundary test is out of scope: whether the host requires the job is the owner's GitHub setting (ADR 0004). | |

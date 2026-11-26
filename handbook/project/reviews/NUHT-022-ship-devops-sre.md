---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-022

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (1382 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## devops-sre

Verdict: Block

Paraphrase: This change adds `ci-check`, which examines a PR’s commit range for attribution, work-item evidence, Tier 1 review files, and tier violations. The generated GitHub workflow runs automatically on pull requests, extracts the base branch’s runtime, and uses it to check the PR head against the base charter before running configured quality commands. Scaffolding now permits an empty quality-command set, leaving record checks and a TODO. Trailer generation defaults to human attribution when no agent is detected and warns when a detected agent’s model is unknown.

Checked: Supplied workflow generation, checker selection and failure paths, CLI diagnostics, documentation, and smoke-test additions against the supplied DevOps/SRE playbook and charter rows.

Not checked: Command execution, actual GitHub rollout, branch protection or CODEOWNERS configuration, helper implementations outside the diff, full charter check sequence, and rollback execution. No external files or sources consulted.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | NUHT-022 deployment and rollback evidence | No exact rollback procedure or recorded non-production rollback execution is supplied for this Tier 1 change. This is an evidence gap, not proof that rollback is impossible. | Recovery from a required check that blocks PRs remains unproven. Reverting installed files alone may leave generated workflows or branch requirements incompatible. | Document how to restore the runtime, generated workflow, and associated required-check configuration; execute rollout and rollback in a disposable repository and record results under NUHT-022. |
| 2 | S2 | `install.py`, `ci_text()` base-checker selection | Selection checks only whether the base contains `sdlc.py`, not whether that version supports `ci-check`. An existing installation predating this command selects the old checker instead of taking the bootstrap fallback. | The first upgrade PR can fail with an unsupported-command error, preventing adoption when `quality` is required. | Define a capability-aware bootstrap procedure with explicit trust handling. Test a generated workflow against a base containing the previous runtime, including its companion modules. |
| 3 | S2 | `install.py`, removal of empty-command rejection and `NO_CHECKS_TODO` | An automatic quality workflow can now contain no executable quality checks; the TODO does not fail the job. The supplied code does not establish that record checks reject this configuration. | A green required status can represent only record validation, without building or testing the change. | Fail explicitly when required commands are unconfigured, or require an explicit records-only configuration that clearly distinguishes its status. Test the resulting job’s exit behaviour, not just generated text. |
| 4 | S2 | `tests/smoke.py`, generated-workflow assertions | Workflow tests inspect strings but do not execute the extracted base runtime with the PR workspace and event file. No actual non-production workflow run is supplied. | Runtime extraction, version compatibility, and PR checkout integration can fail despite these assertions passing. | Execute the generated workflow in a disposable repository for both an existing-runtime upgrade and a fresh installation; record successful and deliberately failing PR checks under NUHT-022. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Decline | Shipped in 6.0.0 (merged to main and pushed); later commits build on it, so reverting this item alone is not a meaningful rehearsal. The rollback for a kit release is reinstalling the previous version: `install.py <project> --upgrade` from the v5.0.0 tag, which the upgrade path and its tests cover (test_upgrade_to_41). | |
| 2 | Contest | Fixed after this commit by NUHT-044: `Installer.checker_select_shell` runs the base runtime's `ci-check --help` and falls back only when the base has no kit or a 5.x kit; test_checker_fallback. | |
| 3 | Decline | Tracked as NUHT-062. | |
| 4 | Decline | test_checker_fallback runs the extracted base runtime against the PR workspace; a real hosted workflow run is CI's own job, not a smoke test. | |

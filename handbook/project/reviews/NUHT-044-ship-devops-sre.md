---
status: current
owner: codex
last-reviewed: 2026-11-23
---

# Review — NUHT-044

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (266 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## devops-sre

Verdict: Block

Paraphrase: This change expands the mandatory Tier 1 file patterns to include all CI locations recognised by the kit and lowers the no-remote advisory from warning to info. Generated CI scripts probe the base branch’s checker for `ci-check` support and fall back to the proposed change’s checker when that probe fails. The repository gains a records job that runs strict doctor checks and, for pull requests, checks commits against the base branch’s charter.

Checked: Supplied runtime changes, CI workflow, installer-generated shell, smoke-test changes, work-item record, and plan against the supplied DevOps/SRE playbook and charter rows.

Not checked: Executed checks, actual CI rollout, branch protection, rollback execution, full workflow triggers, `CI_FILES` contents, release runbook, or surrounding implementation; these were not supplied.

Findings:
| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `handbook/project/plans/NUHT-044.md`, Rollback | “Revert the commit” provides no recorded non-production rollback execution for this Tier 1 change. | Recovery of installed runtime files and generated CI configuration remains unproven. | Document exact rollback steps for repository and installed/scaffolded artifacts; execute them in a disposable project and record results under NUHT-044. |
| 2 | S1 | `install.py` and `.github/workflows/ci.yml`, checker selection | Any archive, file-presence, or capability-probe failure selects the change-controlled checker. This does not distinguish a known legacy base from a broken modern checker or extraction failure; the warning labels all failures as pre-6.0. | An operational failure silently weakens enforcement and gives operators a misleading diagnosis. | Allow fallback only for positively identified legacy or absent-kit bases; fail on unexpected errors and preserve diagnostics. Execute tests covering legacy fallback, modern success, and modern failure instead of only checking generated strings. |
| 3 | S2 | `.github/workflows/ci.yml`, `PR records` condition | Commit enforcement runs only on pull requests, and the plan explicitly excludes direct pushes to `main`. No supplied evidence establishes host rules preventing that bypass. | Direct pushes can avoid the newly introduced commit and tier checks. | Provide evidence that protected branches require the records check and prohibit bypass, or validate newly pushed commit ranges using an explicit historical baseline. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Fix | Rollback steps written in `plans/NUHT-044.md`: revert the commit, re-run `install.sh <project> --scaffold-ci <host>` to regenerate CI files, and `install.sh <project> --upgrade` to restore `.ai-sdlc/bin`. | |
| 2 | Fix | Fallback only for a base with no kit or a pre-6.0 kit; extraction failure or a checker that fails to start exits 1 with its own message (`checker_select_shell`). Executed, not string-checked: `test_checker_fallback` covers no kit, 5.x, 6.0 and broken. | |
| 3 | Contest | The `records` job comment says a direct push to main is not judged and that branch protection requiring the job is what stops it; that is the host's setting, and doctor's enforcement line says "binds only if the host requires that job". Evidence: `.github/workflows/ci.yml` comment; `check_enforcement` message in `optional/runtime/sdlc.py`. | |

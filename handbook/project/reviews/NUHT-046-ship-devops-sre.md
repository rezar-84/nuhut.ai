---
status: current
owner: codex
last-reviewed: 2026-11-25
---

# Review — NUHT-046

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (220 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## devops-sre

Verdict: Block

Paraphrase: This change pins checkout and Python setup actions in the repository’s GitHub workflows to commit hashes and adds weekly Dependabot updates. The installer emits a pinned checkout action for GitHub scaffolds while retaining the tag for Gitea. The validator checks action references in `.yml` workflows for a hash and version comment, and the smoke test checks the generated GitHub checkout reference.

Checked: Supplied diff against the supplied DevOps/SRE playbook and charter rows, focusing on reproducibility, pin maintenance, enforcement coverage, and rollback.

Not checked: Execution of tests, upstream hash provenance, actual workflow runs, branch protection, human approvals, or rollback execution. No files or external sources were consulted.

Findings:
| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `handbook/project/plans/NUHT-046.md` — Rollback | “Revert the commit” gives a rollback direction, but no executed non-production rollback result is supplied. The playbook explicitly requires this for Tier 1. | Recovery remains unproven for the release workflow change. | Execute the revert and relevant workflow checks in a non-production branch or repository; record the procedure and results under NUHT-046. |
| 2 | S2 | `validate.py` — workflow glob | Enforcement scans only `*.yml`; `.yaml` workflows escape inspection. | A future executable GitHub workflow can introduce mutable action references while validation succeeds. | Scan both extensions and add negative tests demonstrating that unpinned references fail in each. |
| 3 | S3 | `install.py` — `PINNED_CHECKOUT` | Dependabot’s configured GitHub Actions updates do not maintain the pin embedded in Python. The comment assigns maintenance to scaffold adopters but leaves maintenance of the installer’s source pin unspecified. | Repository workflows can receive updates while newly generated workflows continue using an older action. | Document a maintainer procedure to update the installer pin alongside workflow updates, and add a consistency check to detect drift. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Fix | Rollback rehearsed in a throwaway worktree: revert `46774a4` restored the tags and removed `dependabot.yml`; `validate.py` and `test_scaffolding` passed. Recorded in the plan's Rollback section. | |
| 2 | Fix | `validate.py` scans `*.yml` and `*.yaml`, through `unpinned_actions`. Test in `test_scaffolding`: "validate refuses a tag or branch action and accepts a pinned one (NUHT-046 review)". | |
| 3 | Fix | `validate.py` fails when `install.py` `PINNED_CHECKOUT` differs from the `actions/checkout` pin in the workflows, and names the fix: when Dependabot moves the pin, update install.py to match. | |

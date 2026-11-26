---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-027

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (2017 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## devops-sre

Verdict: Block

Paraphrase: This change adds deployment bookkeeping: it resolves Git commits, collects work-item trailers, writes a version record, and appends deployment events to a ledger. The CLI and dashboard infer each environment’s deployed version from its last ledger entry; the command records a deployment but does not perform or verify one. Installation adds the runtime module and a union merge rule for the ledger. The change also introduces `unclaim`, preserves `release` as a deprecated alias, and adds suggestions for incorrectly padded work-item IDs.

Checked: Static review of both supplied commits against the supplied DevOps/SRE playbook and charter rows, including installation, persistence, concurrency, failure visibility, compatibility, documentation, and test coverage shown.

Not checked: Commands or tests were not run. Pipeline enforcement, actual installation and rollback, underlying Git and atomic-write helpers, platform configuration, and execution evidence were not supplied. The commits have intervening context not included here.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | Release-runbook changes; NUHT-027 evidence | No exact rollback procedure or recorded non-production rollback execution is supplied for this Tier 1 change. The template addition covers only recording a deployment. | Recovery of the installed runtime, installer changes, and new records remains unproven. | Document rollback steps, including treatment of existing deployment records and `.gitattributes`; execute installation, upgrade, and rollback outside production and record results under NUHT-027. |
| 2 | S2 | `install.py: apply_git_attributes`; `releases.py: deployed` | Union merging preserves lines without establishing deployment chronology, while `deployed()` treats file order as authoritative. An older event merged from another branch can become the last line. | CLI and dashboard can report the wrong deployed version after a normal merge. | Define an ordering or conflict-resolution protocol that survives branch merges; test divergent deployment histories merged in both directions. |
| 3 | S2 | `releases.py: record` in both runtime copies | Version validation and writing are an unlocked read-modify-write sequence. Two writers can both observe an absent version and record different commits; simultaneous promotions can overwrite each other’s `envs` updates. Atomic replacement alone does not prevent this. | The promised version immutability can fail, and release records can disagree with ledger events. | Serialize the complete transaction with a portable lock or equivalent concurrency control, recheck state inside it, and test conflicting writers and simultaneous promotions. |
| 4 | S2 | `releases.py: record`, `append_ledger` | The release record is written before the ledger append, without recovery for an append failure. `os.write()` also has no check for a short write. | A failed command can leave changed state despite the documented “nothing written” guarantee; a truncated event can subsequently be skipped. | Implement recoverable transaction semantics, handle incomplete writes, and document partial-failure recovery. Add fault-injection tests between writes and during append. |
| 5 | S2 | `releases.py: ledger_lines`; `view.py`; dashboard deploy card | Ledger read errors are returned as an empty ledger with zero skipped lines. Viewer exceptions populate `deploys.error`, but the card never displays it. | An unreadable or failed deployment inventory appears as “nothing recorded,” concealing an operational failure. | Distinguish missing files from read failures, return an actionable CLI error, and display an unavailable/error state in the dashboard. Test permission and read failures. |
| 6 | S3 | `docs/cli.md`, `CHANGELOG.md`, `docs/multi-agent.md`; second commit’s `_cmd_claims` | Documentation still promises unchanged JSON and a stderr deprecation line, but the later commit adds a `deprecated` JSON field and suppresses that line for successful `--json` calls. | Automation owners receive an inaccurate compatibility contract. | Update the documentation to describe the final output behavior and its error-path behavior. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Decline | Shipped in 6.0.0 (merged to main and pushed); later commits build on it, so reverting this item alone is not a meaningful rehearsal. The rollback for a kit release is reinstalling the previous version: `install.py <project> --upgrade` from the v5.0.0 tag, which the upgrade path and its tests cover (test_upgrade_to_41). | |
| 2 | Decline | Tracked as NUHT-062. | |
| 3 | Decline | Tracked as NUHT-062. | |
| 4 | Decline | Tracked as NUHT-062. | |
| 5 | Decline | Tracked as NUHT-062. | |
| 6 | Fix | NUHT-061: docs/cli.md and docs/multi-agent.md now say the deprecation note goes to stderr, or into a `deprecated` JSON field with --json. | |

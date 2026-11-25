---
status: current
owner: codex
last-reviewed: 2026-11-23
---

# Review — NUHT-043

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (903 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change makes the Tier 1 approval threshold configurable through the default-branch charter, defaulting to two. It adds local approvals stored in item shards and combines them with GitHub reviews, counting each eligible handle once. GitHub reviewers must now belong to the charter’s Approvers list, while local approvals count when their stored commit matches the newest commit tagged for the item. The local path does not establish authenticated human identity or protect approval records from fabrication.

Checked: Supplied diff, charter rows, and security playbook; approval creation, persistence, counting, freshness, fallback behavior, and supplied test assertions.

Not checked: Execution or denial tests; implementations of `trusted_text`, `item_commits`, `runner_identity`, `_interactive`, agent detection, and shard loading outside the diff; deployment enforcement, threat model, and security/privacy records.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
|---|---|---|---|---|---|
| 1 | S0 | `optional/runtime/finish.py`: `local_approvals()`; mirrored `.ai-sdlc/bin/finish.py` | Approval authority comes directly from editable shard fields. A writer can insert an allowed `handle` and matching `commit`; counting checks neither authenticated provenance nor whether `approve()` ran. The plan acknowledges this bypass. | An agent or repository contributor can fabricate sufficient human approvals and satisfy the gate. | Require independently authenticated approval evidence, protected from repository writers or cryptographically verified against trusted approver keys. Reject unsigned shard assertions; add direct-forgery denial tests. |
| 2 | S0 | `optional/runtime/finish.py`: `check_waiver(..., act="approve")`; mirrored copy | With `interactive=True`, both agent rejection and runner-identity comparison are skipped, leaving the caller’s `--by` value to select an approver. Without a terminal, matching process-controlled identity can still pass when agent detection is absent. The success test uses `DEVNULL` and pipes despite claiming terminal approval. | A caller can impersonate a charter approver, including through an agent-created pseudo-terminal. Terminal presence does not authenticate a human. | Authenticate the approving principal through a trusted mechanism outside agent-controlled arguments, environment, and Git configuration. Add denial tests for pseudo-terminals, mismatched identities, and spoofed environment values. |
| 3 | S1 | `optional/runtime/finish.py`: `approve()`, `local_approvals()`, and `approvals()` | Local evidence binds to the newest item-tagged commit, whereas GitHub evidence binds to the PR head. Later changes without that item trailer do not invalidate local approval, and local evidence is combined with GitHub results without requiring its commit to equal the PR head. | Changed code can retain a satisfied approval gate without human approval of the actual merge candidate. | Bind local approval to the exact candidate revision and validate it against the current PR head or equivalent merge target. Add a denial test where a subsequent code commit omits or changes the work-item trailer. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Escalate | Correct: a local approval is an unsigned record in a writable shard, the same limit as waivers (NUHT-016 finding 14). Mitigated in this change: `approve` and local approvals now work only where the charter's **Local approvals** row is `on` on the default branch (default `off`), so a team relying on GitHub reviews gains no forgeable path; `test_tier1_approval_count_and_local_approval` "local approvals are off until the charter turns them on". Signing them is NUHT-045, which waits on the owner. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 2 | Escalate | Correct: a terminal does not prove a person, and agent detection reads the environment. Same model as `finish --waive`. No mechanism in the kit authenticates a person outside GitHub; NUHT-045 (signed approvals) is the fix and waits on the owner. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 3 | Fix | `approve` now records HEAD (which must contain the item's newest commit) and a local approval counts only while nothing outside the docs folder changed between that commit and the PR head, else the item branch, else HEAD (`finish.local_approvals`, `_records_only_since`). Test: "a code commit without the item's trailer after the approval voids it (review finding 3)"; "a records-only commit after the approval keeps it". | |

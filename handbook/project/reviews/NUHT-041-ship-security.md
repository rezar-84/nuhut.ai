---
status: current
owner: codex
last-reviewed: 2026-11-23
---

# Review — NUHT-041

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (4572 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change makes `deploy record` reject open S0–S2 defects, with exceptions for commits attributed to the defect and approver acceptance of S2. It adds severity re-rating, stores local approvals and review results in item shards, and uses those records to permit approvals or severity reductions. It also extends CI integration and exposes the viewer remotely behind a shared access key, with actions disabled by default. Several controls trust writable records, process context, or commit messages as proof of authorisation or remediation.

Checked: Static review of the supplied runtime changes and their mirrored copies, CI scaffolding, workflow, tests, plans, documentation, and charter changes against the supplied security playbook.

Not checked: No commands or denial tests executed. Unshown helpers, hook enforcement, threat model, security/privacy records, architecture, host branch protection, actual agent permissions, and ledger evidence authenticity were not checked.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `optional/runtime/releases.py`: `release_blockers`, `fix_shipped` | Any attributed commit anywhere in deployment history exempts an open defect. A reporting, planning, or incomplete-fix commit suffices; a reverted fix still counts. Furthermore, `git log --grep` matches body lines, not just parsed trailers. | An unresolved S0/S1 can pass the release-record gate without remediation or acceptance. | Require an explicit, verified resolution bound to the deployed code and current defect revision. Parse actual trailers, and test reporting-only commits, body mentions, reopened defects, and reverted fixes. |
| 2 | S0 | `optional/runtime/finish.py`: `check_waiver`; `optional/runtime/sdlc.py`: `severity_change` | Interactive execution skips both agent refusal and runner/approver matching. A caller with a pseudo-terminal can name any charter approver; `severity_change` also treats absence of an agent marker as proof of a person, even without a terminal. | Caller-controlled process context permits impersonating an approver, accepting S2 defects, and bypassing severity review. | Authenticate the human through a trusted mechanism outside the agent-controlled process. Bind approval to that identity; neither a terminal nor environment variables should grant authority. |
| 3 | S1 | `optional/runtime/finish.py`: `local_approvals`; `optional/runtime/sdlc.py`: `severity_change`; `optional/runtime/shards.py`: `_flat_records` | Local approvals and independent review claims are accepted directly from writable shard fields. There is no provenance verification; `independent: yes` is sufficient, and dissenting review rows can be removed. The supplied plan explicitly acknowledges approval forgery. | A shard writer can satisfy human approval counts or manufacture permission to downgrade blocking defects. | Verify approvals and review attestations against a protected store or signatures from trusted identities. Enforce record integrity at consumption and reject tampering in CI. |
| 4 | S1 | `optional/runtime/sdlc.py`: `blind_rerate_prompt`, `rerate`, `severity_change` | Repository-controlled report, title, and ladder text enter the review prompt, whose resulting rating grants downgrade permission. Reviews are bound only to the severity string, not the report or code revision. | Crafted report instructions can influence the gate; an old favourable review remains usable after the defect materially changes. | Treat model ratings as advisory pending authenticated approval, clearly separate untrusted evidence, and bind attestations to hashes of the reviewed report, policy, and code. |
| 5 | S1 | `optional/runtime/view.py`: `serve`, remote cookies and URLs | Remote access permits plain HTTP on arbitrary interfaces, sends the bearer key in a URL, and sets cookies without `Secure`. A warning does not protect transport; an address in the configured range alone does not establish Tailscale protection. | A network observer can capture the key, read records, and invoke permitted actions when `--allow-actions` is enabled. | Require HTTPS or a verified protected transport for remote access, use secure cookies, and exchange credentials without query-string exposure. |
| 6 | S1 | `.github/workflows/ci.yml`; `install.py`: checker fallback | Missing or failing base-checker capability detection falls back to executing the change’s own checker. This includes errors beyond an intentionally unsupported old version. | The change under review can supply a checker that reports success, defeating the merge check during fallback. | Fail closed and bootstrap upgrades using a separately trusted, pinned checker or an explicit protected administrator procedure. |
| 7 | S2 | `.github/workflows/ci.yml`; `install.py`: CI scaffolds | Newly added actions use mutable version tags, and generated jobs use the floating `python:3.12` image tag. | Upstream tag changes introduce executable build code that was not reviewed with this change. | Pin actions to full commit SHAs and images to digests, with a documented update process. |
| 8 | S2 | `handbook/project/items/NUHT-037.json`; associated worklog and security records | The remote HTTP control-plane change is marked Done at Tier 2 with self-review, although the supplied charter makes `view --serve` Tier 1. No threat-model update accompanies the new network surface in the supplied diff. | The recorded completion bypasses the declared security review requirements and leaves the expanded trust boundary undocumented. | Reclassify the item as Tier 1, complete its required security review and approval evidence, and update the threat model before closure. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Fix | `releases.fix_shipped` now reads git's own trailer parser (`%(trailers:key=Work-Item)`) and counts a commit only when it changes a file outside the docs folder. Tests in `test_release_defect_gate`: "a commit naming the defect that only touches records is not its fix", "a Work-Item line in the body, not the trailer block, is not a fix"; both fail on the old code. A reverted fix still counts: a revert does not reopen the defect, which is the defect's status to carry. | |
| 2 | Escalate | Same model as verify waivers: terminal presence and the agent environment are what the kit can see. Signed approvals and acceptances are NUHT-045, waiting on the owner. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 3 | Escalate | Local approvals are now opt-in (charter **Local approvals**, default `off`). Review rows in the shard are as writable as the ledger; removing a dissenting row shows in git history. Signing is NUHT-045. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 4 | Fix | The report goes into the prompt between `<<<UNTRUSTED DEFECT REPORT` markers with an instruction to ignore claims inside it, and each re-rating records `report`, a sha256 of title, touch paths and report; `severity_change` counts only re-ratings whose hash matches the current report. Test: "editing the report after a re-rating voids it (review finding 4)". | |
| 5 | Escalate | `--host tailscale` binds the Tailscale address, where traffic is WireGuard-encrypted; `--host <ip>`/`0.0.0.0` already warns that traffic is plain HTTP. The key appears in the URL once and the server answers with a redirect that drops it. A `Secure` cookie cannot be set over plain HTTP. Whether to refuse non-Tailscale addresses without a `--plain-http` flag is a usability decision for the owner, who asked for no host configuration. Decision 2026-11-25: Accepted as is. `view --serve` keeps warning off Tailscale and does not refuse. | rezar-84 |
| 6 | Fix | Fallback now happens only when the base has no `.ai-sdlc/bin/sdlc.py` (`git cat-file -e`) or has one whose `--help` runs and names no `ci-check`; an extraction failure or a crashing base checker exits 1 (`install.Installer.checker_select_shell`, used by every scaffold and this repo's `ci.yml`). Executed test: `test_checker_fallback` (no kit, 5.x kit, 6.0 kit, broken kit). | |
| 7 | Decline | Real, S2, and true of every existing workflow in this repository and the scaffolds before this change. Tracked as NUHT-046 with an update process, waiting on the owner. | |
| 8 | Fix | NUHT-037 is now Tier 1 and Parked, waiting on its Tier 1 ship review and approval. | |

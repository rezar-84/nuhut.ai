---
status: current
owner: codex
last-reviewed: 2026-11-23
---

# Review — NUHT-041

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (5077 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change blocks release recording for open S0–S2 defects, except when history contains an attributed non-documentation commit or an approver accepts an S2. It adds model-assisted severity reductions and optional local approvals, persisting their evidence in item shards. It also expands CI integration and permits remote viewer access using a shared bearer key, with remote actions disabled by default. Several enforcement paths still accept caller-controlled identity, editable evidence, or historical commit attribution as sufficient authority.

Checked: Static examination of the supplied runtime implementations and mirrored changes, installer scaffolds, workflow, tests, charter changes, plans, review responses, and documentation against the supplied security playbook.

Not checked: Commands and denial tests were not run. Unshown helpers, actual hook coverage, branch protection, agent sandbox permissions, threat model, security/privacy records, architecture, and authenticity or freshness of recorded verification evidence were not independently checked.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S0 | `optional/runtime/finish.py`: `check_waiver`; `optional/runtime/sdlc.py`: `severity_change`; mirrored copies | Interactive execution skips agent rejection and approver identity matching. Severity reduction also treats missing agent detection as human authority. A pseudo-terminal is not human authentication; the supplied success tests actually use pipes and `DEVNULL`. | A caller can impersonate a charter approver, accept S2 defects, or bypass independent severity review. | Authenticate the human outside caller-controlled arguments, environment, Git configuration, and terminal state. Add denial tests for pseudo-terminals and spoofed identity. |
| 2 | S0 | `finish.py`: `local_approvals`; `handbook/project/charter.md` | Approval counting trusts unsigned shard `handle` and `commit` fields without authenticating their origin. Opt-in limits exposure but does not prevent forgery, and this diff enables it for this repository. | A shard writer can fabricate the human approval required to satisfy the gate. Parking signing work as NUHT-045 leaves this bypass active. | Keep unsigned approvals advisory; require verified signatures or evidence from a protected approval service before counting them. |
| 3 | S1 | `sdlc.py`: `severity_change`; `shards.py`: `_flat_records` | A matching report hash and editable `independent: yes` field suffice to count a severity review. Neither reviewer provenance nor preservation of dissenting reviews is verified. The plan explicitly omits CI checking of direct downgrades. | A writer can fabricate favourable reviews, remove dissent, or directly lower severity and evade the release-record restriction. | Enforce severity transitions at the trusted consumption boundary using authenticated, append-only review evidence; reject unauthorized shard changes. |
| 4 | S1 | `releases.py`: `fix_shipped`, `release_blockers` | Any historical commit with the defect trailer and a change outside the docs folder permanently exempts the defect. An unrelated edit, incomplete fix, or subsequently reverted fix qualifies—even when the defect is currently open again. | An unresolved S0/S1 passes the release-record gate. Trailer parsing and excluding records-only commits do not establish remediation. | Require verified resolution evidence tied to the current defect revision and deployed code. Test incomplete fixes, reverted fixes, and reopened defects. |
| 5 | S1 | `finish.py`: `_records_only_since` | Every change under the docs folder is exempt from approval invalidation, including the charter and `project/people.json`, which this change uses as security policy and identity records. | An approval can remain valid after unreviewed changes to governance or approver mappings, provided the later commit does not become the item's newest attributed commit. | Bind approvals to the exact candidate revision, or narrowly allow only non-security record changes; explicitly invalidate on charter and identity changes. |
| 6 | S1 | `sdlc.py`: `blind_rerate_prompt`, `rerate`, `severity_change` | Model output grants downgrade permission after consuming repository-controlled evidence and a working-tree severity ladder. Untrusted-report markers are instructions to the model, not an external enforcement boundary; the fingerprint excludes the ladder and code revision. | Manipulated policy or crafted evidence can obtain a rating that clears a blocking severity without authenticated human authorization. | Load policy from a trusted revision, bind reviews to policy and code as well as the report, and require authenticated approval for reductions that remove a release block. |
| 7 | S1 | `view.py`: `serve`, remote authentication cookies | Arbitrary remote interfaces serve plain HTTP, transmit the bearer key in a URL, and set cookies without `Secure`. A warning and subsequent redirect do not protect the initial request or later traffic. | A network observer can steal access and invoke enabled actions. | Require HTTPS or an established protected transport for remote access; use secure cookies and avoid credentials in query strings. |
| 8 | S1 | `.github/workflows/ci.yml`; `install.py`: `checker_select_shell` | Missing or legacy base checkers still select the proposed change's own executable checker. Additionally, any `git cat-file -e` failure is classified as “no kit,” including an unavailable base ref. | During bootstrap or ref failure, the change can provide a checker that simply succeeds. | Use a separately trusted, pinned bootstrap checker or protected administrator procedure. Distinguish missing files from invalid refs and operational failures; fail closed on the latter. |
| 9 | S2 | `.github/workflows/ci.yml`; `install.py`: CI scaffolds | New jobs use mutable action tags and floating `python:3.12` images. NUHT-046 records deferred work, not a compensating control. | Upstream tag changes introduce executable CI code without review of this change. | Pin actions to full commit SHAs and images to digests, with a documented update process. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Escalate | Repeat of round 1 finding 2. NUHT-045. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 2 | Escalate | Repeat of round 1 finding 3. NUHT-045. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 3 | Escalate | Repeat of round 1 finding 3 for review rows. NUHT-045; `ci-check` checking severity transitions is listed as not done in the plan. Decision 2026-11-25: Declined, ADR 0004 (the kit records intent; GitHub branch protection authenticates). | rezar-84 |
| 4 | Fix | A fix now counts only inside this deploy's range (`fix_shipped(..., from_sha)`), so a fix from an earlier deploy does not exempt a defect that is still open; it must be closed. Test: "the next deploy blocks again while the fixed S1 is still open: close it". Whether a commit actually fixes the defect is the defect's own status, not something a deploy can judge. | |
| 5 | Fix | Same as NUHT-043 round 2 finding 3: `finish.BOOKKEEPING`. | |
| 6 | Fix | Ladder from the default branch, in the hash. Requiring a person for every downgrade that clears a release block is the owner's call; the owner chose "a human, or an agent after a second agent confirms". | |
| 7 | Escalate | Repeat of round 1 finding 5 (NUHT-037). Decision 2026-11-25: Accepted as is. `view --serve` keeps warning off Tailscale and does not refuse. | rezar-84 |
| 8 | Fix | The base ref is resolved first (`git rev-parse --verify`) and an unreadable ref exits 1; absence is checked with `git ls-tree`. Test: "a base ref that cannot be read: exit 1, no fallback (round 2, finding 4)". The bootstrap fallback for no kit or a 5.x kit stays, warned, as the owner asked for the 5.x upgrade path. | |
| 9 | Decline | NUHT-046. | |

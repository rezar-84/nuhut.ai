---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-012

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (2949 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## qa

Verdict: Block

Paraphrase: This change attributes work exclusively through `Work-Item` trailers and makes `finish` look for a complete verification run associated with the newest code commit. It excludes records from freshness checks, restricts waivers using trusted approver records and runner identity, and compares extension pins against the default branch. The follow-up adds agent detection, stored-waiver checks, attribution warnings, and trusted reads for monorepo installations. The supplied tests exercise several successful and refused flows, but leave important ways of accepting invalid evidence uncovered.

Checked: Static examination of both supplied diffs, including evidence filtering, run selection, dirty-tree handling, waiver checks, trusted-ref selection, and smoke-test assertions against the supplied QA playbook and charter rows.

Not checked: Tests were not run. Acceptance criteria, test-plan records, verification output, bite evidence, omitted intervening changes, and the complete surrounding implementation were not supplied; platform coverage and end-to-end results therefore remain unverified.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `optional/runtime/sdlc.py:evidence_matches` and mirrored installed copy | For a tagged run on a descendant commit belonging to another item, matching requires each row’s result to start with `Verified`. Failed rows that do not satisfy that predicate disappear before `verify_state` examines the run. A fully failed later run can disappear entirely, leaving an earlier successful run eligible. | `finish` can accept older passing evidence after a newer applicable verification failure. | Match run provenance independently of stage result, retain every row of an applicable run, and test a passing run followed by failed and mixed-result runs on a descendant commit. |
| 2 | S1 | `optional/runtime/finish.py:verify_state` and mirrored installed copy | The loop skips partial or selected runs before checking failures. After a full passing run, a newer `verify --stage unit` failure on the same commit is ignored and the older pass is returned. | A known failed check does not block finishing the item. | Make applicable newer failures block before falling back to earlier complete evidence. Add a regression asserting refusal after a full pass followed by a selected-stage failure. |
| 3 | S1 | `optional/runtime/finish.py:verify_state`; `sdlc.py:verify` | Dirty evidence is bound only to the parent SHA and a Boolean. Verify uncommitted version A, change it to untested version B, then commit B on that parent: the freshness predicate still accepts A’s run. The added test covers only the case where verified content is committed unchanged. | Untested committed code can satisfy the verification gate. | Record a fingerprint of the checked content and compare it with the resulting commit, or require a clean verification run after committing. Test modification between verification and commit. |
| 4 | S1 | `optional/runtime/registry.py:trusted_ref` and mirrored installed copy | Without `origin/HEAD` or a usable `GITHUB_BASE_REF`, the trusted branch comes from the editable working-tree charter/profile. In a local repository with `main` and `work`, changing `Default branch` to `work` lets that branch supply its own approvers and extension pins. The new branch-redirection test covers only a clone with `origin/HEAD`. | The claimed protection against branch-local approval and pin changes is bypassed in the fallback configuration. | Establish the trusted ref independently of branch-controlled files, or refuse security-sensitive operations when it cannot be established. Add a local-repository regression that changes the default-branch row alongside approvers and pins. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Contest | Failed rows are kept: `verify` records `Verified: fail` and `Verified: fail (timed out ...)`, both of which start with `Verified`, so `evidence_matches` keeps them; only Not run and Absent stages, which have no ledger row, are absent. | |
| 2 | Fix | NUHT-061: `verify_state` returns fail for any failing run on the code being finished, partial or not, before it falls back to an older full pass. Test: "a newer failing --stage run blocks finish after an older full pass". | |
| 3 | Decline | A dirty run on the commit's parent is accepted by design (verify, then commit). Tracked as NUHT-062 for a content hash; CI re-runs every stage on the committed code. | |
| 4 | Decline | Declined under ADR 0004 (approved 2026-11-25): without a trusted ref the kit reads the working tree, as everywhere else; authentication is the host's required checks and reviews, not a local record. | |

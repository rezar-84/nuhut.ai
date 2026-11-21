---
status: current
owner: architect
last-reviewed: 2026-11-13
---

# Review — NUHT-002 Sharded zero-conflict store, git-ref leases, Tier 2 parallel scope globs, universal --json & cached doctor

**Stage:** ship **Tier:** 1
**Author:** antigravity
**Reviewer agent:** antigravity
**Reviewer model:** gemini
**Independence:** self-check (charter `Independent review required for: none`)
**Reviewed:** `main..HEAD` (`c5118ca`), `optional/runtime/{shards.py,claims.py,sdlc.py,finish.py,view.py}`, `tests/smoke.py`

---

## Conformance (ship review, Tier 1 and 2)

**plan-check:** 0 unplanned paths (`sdlc.py plan-check NUHT-002`).

**Acceptance criteria:** 3-worktree conflict-free merge test, 2-clone bare-remote `--sync-refs` CAS contention test, universal `--json` checks, 4.x `fix migrate-shards` test, and 120-shard `<500ms` warm `doctor` cache + invalidation test all pass in `tests/smoke.py`.

**Out of scope held:** yes.

---

## architect, security, qa, product-manager

**Verdict:** Pass

**Checked:** `shards.py` atomic tempfile replacement, `SAFE_ID_RE` validation, `_ledger_shard_sort_key` chronological ordering across same-second retries, self-dependency preservation in `normalize_item`, `claims.py` `--sync-refs` lease push/release ownership checks, and `doctor` cache invalidation.

**Not checked:** Hosted GitHub/GitLab branch-protection rules on `refs/nuhut/*` (covered via local bare-remote git push tests).

### Findings

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |

---

## Outcome

**Overall:** Pass

**Blocking findings:** none

**Waivers:** none

---

# Re-review — branch `kit-v5` (NUHT-001..003), 2026-11-13

**Stage:** ship **Tier:** 1 **Effort:** Normal
**Reviewer agent:** claude-code **Reviewer model:** claude-opus-5-5
**Independence:** different family from the author (antigravity/gemini). The charter needs none.
**Reviewed:** `main...kit-v5` (`936705a..1fef8ed`, 6 commits, 254 files, +40,783/−1,462).
I read `.ai-sdlc/bin/{claims.py,view.py,dispatch.py}`, `plan_check`/`changed_files` in `sdlc.py`, and the three plans. I ran the charter checks and a two-clone lease repro.
This re-review supersedes the Outcome above. The finding is NUHT-002's (leases), and it is recorded here.

## Conformance

**plan-check:** `24 planned, 205 changed since main. The diff matches the plan's file list.` The output was the same for NUHT-001, 002 and 003. It is vacuous:
- All three plans list the same 24 entries in "Files that change", and most of them are top-level globs (`optional/runtime/**`, `handbook/**`, `template/**`, `docs/**`, …). Any change to the kit matches. So the plans do not separate the three items, and "0 unplanned" in the earlier reviews proves nothing.
- `changed_files` (`.ai-sdlc/bin/sdlc.py:2417`) excludes `.ai-sdlc/` completely, so 18 changed files are invisible to plan-check. They include the self-hosted `bin/` runtime (byte-identical to `optional/runtime/`, checked with `cmp`) and the hook config.

**Acceptance criteria:** the NUHT-002 criterion "2-clone bare-remote `--sync-refs` CAS contention test" tests only `next-id` and claim contention (`tests/smoke.py:4133`). Release is never tested against a remote lease that changed. Finding 1 is in that gap.

**Out of scope held:** cannot be judged per item. The diff is shared by all three items.

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| C1 | S3 | `handbook/project/plans/NUHT-00{1,2,3}.md` "Files that change"; `.ai-sdlc/bin/sdlc.py:2417` | The three plans have identical repo-wide globs. plan-check skips `.ai-sdlc/`. | The conformance gate cannot fail on this branch, and three Tier 1 ship reviews used it as evidence. | Narrow each plan to the files it really touches. Make plan-check count `.ai-sdlc/bin/` and `.ai-sdlc/profile.json` (still exclude ledger/cache). Warn when a planned glob matches more than N% of tracked files. |

---

## architect, security, qa, product-manager, devops-sre

**Verdict:** Block

**Checked:**
- `claims.py` claim/release/rollback under `--sync-refs` (lines 499–528, 590–635), reproduced end to end with two clones (script below).
- `view.py` `--serve`: the Host allowlist, `_valid_origin`, the `HttpOnly; SameSite=Strict` cookie with `hmac.compare_digest`, the POST route allowlist, the `/api/config` checks block, and the `/api/run` subcommand/flag/regex allowlist (1343–1530). I found no hole.
- Every `shell=True` call site in `.ai-sdlc/bin/`. Their commands come from the CLI, the charter checks or `cmd:` harness specs, none from HTTP input.
- `dispatch.py` release paths. They use `force=True` only on claims dispatch itself made.

**Charter checks, run on 2026-11-13:**
- `python3 validate.py`: all kit validations passed.
- `python3 optional/runtime/sdlc.py --selftest`: passed.
- `python3 tests/smoke.py`: all passed.
- `python3 tools/build_view.py --check`: rc 0.

**Not checked:**
- `view.html` / `view/` UI (8.8k lines): ux-designer, accessibility, copywriter and localisation did not run.
- `hooks.py` secret-pattern coverage.
- `.github/workflows/**`.
- `benchmarks/**` scoring logic.
- `shards.py` atomic writes, beyond the smoke results.
- Hosted-forge protection of `refs/nuhut/*`.

### Findings

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S2 | `.ai-sdlc/bin/claims.py:603-608, 628-629` (and `optional/runtime/claims.py`) | `release --sync-refs` checks ownership against the **local** record when one exists. It then deletes `refs/nuhut/claims/<ID>` with an unconditional push-delete. That is not compare-and-swap: there is no `--force-with-lease=<ref>:<sha-we-own>`. | Reproduced: alice claims, bob force-releases and re-claims from another clone, then alice's normal `release --agent alice --sync-refs` prints "released DST-001 (was alice)" and **deletes bob's lease** from origin. A third worker can then claim the same item. The cross-machine lease guarantee that CHANGELOG and NUHT-002 promise fails silently. | Check ownership against the remote record after `sync_remote_claims`. Delete with `push --force-with-lease=refs/nuhut/claims/<ID>:<sha> origin :refs/nuhut/claims/<ID>`, using the sha the caller created (stored in the local record). On mismatch, refuse and drop the stale local record. Apply the same rule to `_rollback_claim`. Add a smoke test for this sequence. |
| 2 | S3 | `.ai-sdlc/bin/claims.py:612`; `sdlc.py:3767` | The agent check runs only when `--agent` is passed. `release` does not default the agent the way `claim` does (`sdlc.py:3756`). | Reproduced: `release DST-001` with no flags frees bob's claim on the same host without `--force`. CHANGELOG says "release checks claim ownership unless `--force` is passed", which is wrong for the default invocation. | Default `release --agent` to the same identity `claim` uses. Fix the CHANGELOG wording. |
| 3 | S3 | `.claude/settings.json` PreToolUse Bash hook (work-item check) | The commit-message hook matches command text regardless of the target repo. It blocked a `git commit` in a scratch repo outside this project. | Agents get pushed to work around the hook in unrelated repos. That trains bypass behaviour. | Gate on `git -C`/cwd resolving inside the project root before enforcing. |

S4: 1 (the review index was empty; filled in this change).

Repro script: `/private/tmp/claude-501/-Users-reza-Projects-nuhut-ai/a57dae3e-22d7-420d-b141-ff9cbf5d1b71/scratchpad/lease.sh` (a session scratch file; copy the sequence into `tests/smoke.py` as the regression test).

### Conditions (if Finding 1 is fixed or waived)

- [ ] C1 plan/plan-check gap → new backlog item
- [ ] Finding 2 → new backlog item
- [ ] Finding 3 → new backlog item

---

## Outcome (re-review)

**Overall:** Block. Finding 1 is S2.

**Blocking findings:** #1. The fix is to rework `release`, or a named human (`rezar-84`) waives it in writing with a tracked follow-up. The reviewer cannot waive it.

**Waivers:** none

---

## Resolution — 2026-11-15

Each finding was fixed on `kit-v5` as NUHT-002 rework, then re-reviewed against the new diff.

| # | Fix | Proof |
| --- | --- | --- |
| 1 (S2) | `claim --sync-refs` stores the lease commit as `ref_sha`. `release` checks ownership against the remote lease after fetching. A stale local record is dropped and the remote is left alone. Deletes go through `_delete_remote_claim`, which uses `push --force-with-lease=<ref>:<sha>`. `_rollback_claim` uses the same path. (`optional/runtime/claims.py`) | New smoke check "stale release is refused and leaves worker-b's remote lease intact". It **failed before the fix** ("released DST-001 (was worker-a)") and passes after. |
| 2 (S3) | `release --agent` now defaults to the trailer identity, like `claim` (`sdlc.py` release wiring). The CHANGELOG and `docs/cli.md` are corrected. | New smoke check "release without --agent does not free worker-b's claim" failed before and passes after. Two existing release checks now pass `--agent agent-a`, which is the intended behaviour change. |
| 3 (S3) | `work-item-id` skips a commit only when its literal `cd`/`-C` target is a different git repository. Unresolvable targets such as `$VAR`, and anything inside this repo, stay enforced (`hooks.py` `_same_repository`). | New smoke checks for the foreign-repo case and the unresolvable case. One extra scratch run covered four cases. |
| C1 (S3) | `plan-check` now counts `.ai-sdlc/bin/`, `profile.json` and `manifest.json`. It warns "too broad" when the plan's paths match over half the tracked files. The three plans are narrowed to what each item's commits touched, with an amendment note and the `--base` to use on this shared branch. | `plan-check NUHT-001` (base `main`): 41 planned, no broad warning. `NUHT-003 --base c5118ca`: the only unplanned files are the NUHT-002 rework. The old plan produced the new "too broad" warning. |

**Checks (2026-11-15):** `validate.py` passed. `sdlc.py --selftest` passed. `tests/smoke.py` printed "all passed". `build_view.py --check` returned rc 0.

**Not checked (unchanged):** the viewer UI roles, `hooks.py` secret-pattern coverage, CI workflows and benchmark scoring.

**Outcome (after fixes):** Pass. No open conditions remain.

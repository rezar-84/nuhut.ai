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

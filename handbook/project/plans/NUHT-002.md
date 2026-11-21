---
status: current
owner: architect
last-reviewed: 2026-11-13
---

# Plan — NUHT-002 Sharded zero-conflict store, git-ref leases, Tier 2 parallel scope globs, universal --json & cached doctor

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-001

## Problem

Parallel worktrees editing `backlog.md`, `worklog.md`, and `evidence-ledger.jsonl` produced guaranteed merge conflicts on join; `parallel` required full Tier 1 plan files even for Tier 2 items; claims only existed in the local git dir; several `sdlc.py` commands lacked `--json`; and `doctor` re-parsed all records on every invocation.

## Outcome

Parallel worktrees write conflict-free per-item shards (`items/<ID>.json`, `worklog/<ID>.md`, `ledger/<run>.jsonl`), coordinate distributed claims and IDs via `refs/nuhut/*` when `--sync-refs` is passed, expose `--json` across `sdlc.py`, and run warm `doctor` checks in under 500ms.

## Approach

Add `optional/runtime/shards.py` with transparent 4.x fallback, add `sdlc.py item`, `sdlc.py render`, `sdlc.py next-id`, and `sdlc.py fix migrate-shards`, extend `claims.py` with `--sync-refs` compare-and-swap git refs and Tier 2 `touch` globs, add `--json` flags across remaining CLI commands, and add SHA-keyed `.ai-sdlc/cache/doctor.json` caching.

## Files that change

- `.ai-sdlc/bin/claims.py`
- `.ai-sdlc/bin/finish.py`
- `.ai-sdlc/bin/hooks.py`
- `.ai-sdlc/bin/sdlc.py`
- `.ai-sdlc/bin/shards.py`
- `.ai-sdlc/bin/view.py`
- `.ai-sdlc/manifest.json`
- `CHANGELOG.md`
- `README.md`
- `docs/cli.md`
- `install.py`
- `optional/runtime/claims.py`
- `optional/runtime/finish.py`
- `optional/runtime/hooks.py`
- `optional/runtime/sdlc.py`
- `optional/runtime/shards.py`
- `optional/runtime/view.py`
- `tests/smoke.py`

_Amended 2026-11-15 after the kit-v5 ship re-review (finding C1): the earlier list was 24 repo-wide globs shared by NUHT-001..003, so plan-check could not fail. This list is what the item's commits touched plus the release-lease and hook-scoping rework. The three items share one branch, so run `sdlc.py plan-check NUHT-002 --base 936705a`; files from later items on the branch still show as unplanned._

## Order of work

1. Implement `optional/runtime/shards.py` (`items/`, `worklog/`, `ledger/`, deterministic `render`, `migrate-shards`, chronological ledger shard ordering) — riskiest step because all readers (`sdlc.py`, `finish.py`, `claims.py`, `view.py`) must remain 4.x compatible.
2. Extend `optional/runtime/claims.py` with `<git-common-dir>/nuhut/seq.json`, `--sync-refs` CAS leases (`refs/nuhut/claims/<ID>`, `refs/nuhut/seq`), ownership checks on `release`, and Tier 2 `touch` globs in `parallel`.
3. Add universal `--json` output across `sdlc.py` commands and implement `.ai-sdlc/cache/doctor.json`.
4. Migrate `nuhut.ai`'s own `handbook/project/` records to shards and add N-way parallel worktree merge, git-ref CAS, and `<500ms` cache tests in `tests/smoke.py`.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Custom git `merge=union` driver on `backlog.md` and `worklog.md` | `merge=union` scrambles multi-line Markdown sections and requires local `.git/config` setup on every clone before merges work. |
| Force breaking migration of all 4.x repositories on `--upgrade` | Mutating `docs/project/` during `--upgrade` violates the installer's guarantee that user project records are never touched without explicit `fix --apply`. |

## Affected surfaces

- **Code:** `optional/runtime/shards.py`, `optional/runtime/claims.py`, `optional/runtime/sdlc.py`, `optional/runtime/finish.py`, `optional/runtime/view.py`, `install.py`
- **Data:** `<docs>/project/{items,worklog,ledger}/`, `<git-common-dir>/nuhut/seq.json`, `refs/nuhut/*`, `.ai-sdlc/cache/doctor.json`
- **Contracts:** New subcommands `item`, `render`, `next-id`, `fix migrate-shards`; `--sync-refs` on coordination commands; `--json` across CLI commands
- **Docs to update:** `docs/cli.md`, `docs/multi-agent.md`, `docs/runtime.md`, `README.md`, `CHANGELOG.md`

## Failure modes

- Concurrent `--sync-refs` claims from two clones: `git push --force-with-lease=refs/nuhut/claims/<ID>:`: second writer fails CAS push cleanly and reports the remote owner.
- Same-second verification retries writing multiple ledger shards: `_ledger_shard_sort_key` parses integer run suffixes (`-2`, `-10`) so chronological order holds.
- Stale `doctor` cache after shard edit: SHA-256 input digest includes shard filenames, mtimes/hashes, `HEAD`, and claims, invalidating immediately on any mutation.

## Test strategy

- **Acceptance criteria mapping:** 3-worktree concurrent build/verify/finish merge test, 2-clone bare-remote `--sync-refs` CAS contention test, and 120-shard `<500ms` `doctor` cache hit + invalidation test in `tests/smoke.py`.
- **Unit:** `python3 optional/runtime/sdlc.py --selftest`
- **Integration:** `python3 tests/smoke.py`
- **Negative cases:** Traversal/invalid item IDs (`../x`), second clone claiming leased item, non-owner `release` without `--force`, self-dependency cycle invalidating `doctor` cache.
- **Manual:** Verify `sdlc.py render --check` on `handbook/project/`.
- **Proof:** `python3 validate.py`, `python3 tests/smoke.py`, `python3 .ai-sdlc/bin/sdlc.py doctor --strict`.

## Rollback

Run `sdlc.py render` to materialize `backlog.md` and `worklog.md`, concatenate `ledger/*.jsonl` to `evidence-ledger.jsonl` if desired, and revert the M2 commit.

## Out of scope

- Headless multi-worker wave execution (`NUHT-003`).

## Assumptions

- Git 2.20+ is available for `git worktree` and `--force-with-lease` ref pushes.

## Review

| Role | Verdict | Notes |
| --- | --- | --- |
| product-manager, architect, security, qa | Pass | [NUHT-002-design.md](../reviews/NUHT-002-design.md), [NUHT-002-ship.md](../reviews/NUHT-002-ship.md) |

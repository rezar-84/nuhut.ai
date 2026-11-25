---
status: draft
owner: qa
last-reviewed: 2026-11-22
---

# Plan: NUHT-012 Binding verify evidence for finish

**Tier:** 1 **Effort:** Normal **Depends on:** none

## Problem

`finish` decides whether an item is verified from `evidence_matches`
(`optional/runtime/sdlc.py:1662`) through `verify_state` (`optional/runtime/finish.py:106`).
Five gaps let it accept evidence that does not prove the item:

- **Tagged runs float.** A run made with `verify --item X` counts for X whatever commit it
  ran on and however dirty the tree was (`sdlc.py:1673`). A run made weeks ago on another
  branch, or one made with unrelated edits in the tree, satisfies `finish X`.
- **Partial runs count.** `verify --stage lint` writes ledger rows only for the selected
  stages (`sdlc.py:1468-1472`) and nothing marks the run as partial. `verify_state` takes the
  last run and passes it if none of its rows failed, so a lint-only run closes the item.
- **Stale runs count.** Any run on any of the item's commits counts, so a run on the first
  commit still passes after later commits change the code.
- **Self-waivers.** `finish --waive verify --by <name>` accepts any string
  (`finish.py:433-448`). An agent can waive its own checks with `--by claude-code`.
  Tier 1 is already refused; Tier 2 and 3 are not guarded.
- **Loose attribution.** `item_commits` (`sdlc.py:1588-1602`) and `commit_index`
  (`sdlc.py:1568-1585`) attribute a commit to every ID its message mentions, so "follows up
  NUHT-012" in another item's commit makes that commit, and its verify runs, NUHT-012's.

## Outcome

`finish` passes Verify only on a full run (every charter stage that has a command) made
clean on the item's newest code commit or a descendant of it, or dirty on that commit's
parent. The "newest code commit" is the item's newest commit that changes a path outside
`<docs>/project/**`, so a records-only commit (ledger, worklog, status) never makes a run
stale. A waiver names someone in the charter's Approvers row as it stands on the default
branch, and the person running the waiver must be that approver. A commit belongs to an
item only through its `Work-Item:` trailer.

## Approach

- **Attribution** (`sdlc.py` `item_commits` and `commit_index`). Match on
  `tags.get("Work-Item") == item` only. Drop the `pattern.search(body)`, `id_ranges` and
  `ids_in(body, ...)` matches. The `known` argument of `commit_index` stays for callers but
  no longer widens the match. The `finish` message at `finish.py:399` changes from "with
  the ID in the message" to "with a `Work-Item: <ID>` trailer (`sdlc.py trailers <ID>`)".
- **Ledger records the selection** (`sdlc.py` `verify`, ledger rows at line 1469). When
  `selected` is set, each row gets `"selected": sorted(selected)`. A full run writes no new
  field, so older rows keep their meaning. `shards.ledger_row_key` is unchanged.
- **Newest code commit** (`sdlc.py`, new helper `newest_code_commit(project, item)`). The
  item's newest trailer-attributed commit whose `git diff-tree --name-only -r` (first
  parent for a merge) has a path outside `<docs>/project/**`. Commits that change only
  records are skipped. When every commit is records-only, the newest commit is used.
- **evidence_matches** (`sdlc.py:1662`), made time-invariant so doctor and the viewer give
  the same answer whenever they run. A row tagged `item` no longer counts on the tag
  alone. It counts when the run was clean and `git merge-base --is-ancestor <an item
  commit> <row.commit>` holds, or the run was dirty on the parent of an item commit
  (verify, then commit). There is no comparison with HEAD. The untagged rules are
  unchanged. Doctor's `check_verified_claims` and the viewer (`view.py:538`) keep using
  this function.
- **verify_state** (`finish.py:106`), the finish-time rules on top. Freshness lives here
  only, because it runs at finish time:
  - **Partial runs.** Drop runs with a `selected` field. Also drop any run whose rows do not
    cover every stage that has a command in `charter_commands(project.charter)`. This
    catches partial runs logged before this change, which have no `selected` field.
  - **Stale runs.** Keep a run only when it is clean and its commit is the newest code
    commit or a descendant of it, or it is dirty on the newest code commit's parent.
  - **Two new states**, each with its own message (one assertion each in
    `test_finish_evidence_binding`):
    - `"partial"`: "latest run <run> covered lint only; missing: unit, build. Run
      `sdlc.py verify --item <ID>` with no --stage".
    - `"stale"`: "latest run <run> is on <sha7>; the item's newest commit is <sha7>. Run
      `sdlc.py verify --item <ID>`".
- **Trusted records** (`sdlc.py`, new helper `trusted_text(project, rel)`, returning
  `(text, source)`). It reads `git show <ref>:<rel>`, where `<ref>` is `origin/<default>`
  or else `<default>` from `default_branch()`. It falls back to the working tree, with
  `source = "working-tree"`, only when there is no git, no such ref, or the file does not
  exist on it yet. NUHT-016/018 (Extensions allowed), NUHT-022 and NUHT-024
  (`people.json`) reuse this helper. It is the cross-cutting rule of ADR 0003 decision 8.
- **Waiver approvers** (`finish.py`, new helper `waiver_approvers(rt, project)`). It reads
  the `Approvers` row through `trusted_text` and splits it on commas, semicolons and
  ` and `. It strips `@`, backticks and whitespace and lowercases each name. When
  `people.json` exists (NUHT-023), each name resolves through it to a handle, and a
  name that is not a handle is a doctor warning. A placeholder cell (`rt.unfilled`) gives
  an empty list. There is no separate `Waiver approvers` row.
  - `finish --waive --by <name>` is refused unless the name is on that list. The message
    names the row to fill. A blank list refuses every waiver.
  - **Who is waiving.** The ledger waiver row records `waived_by` and `waived_as`, the
    runner's identity: `NUHUT_USER`, else `git config user.name`, resolved through
    `people.json` when present. When no TTY is attached and that identity does not map to
    the named approver, the waiver is refused ("an agent cannot waive for <name>; ask
    <name> to run it"). `docs/cli.md` says so, and says that `NUHUT_USER` is an
    honour-system value an agent process could also set.
  - `waivers()` keeps only ledger waivers whose `waived_by` is on the current list. When
    it drops one, `finish` names it: "waiver by <name> on <date> no longer counts: <name>
    is not in Approvers".
- **Upgrade notice.** These changes apply to existing installs on `--upgrade`, so:
  - `CHANGELOG.md` and `docs/install.md` gain an "Upgrading to 6.0" section that lists the
    three behaviour changes (trailer-only attribution, approver-only waivers, a
    placeholder Approvers row refuses every waiver) and the fix for each.
  - `install.py` `upgrade()` prints a post-upgrade notice when the charter's Approvers row
    is unfilled, naming `sdlc.py config` and the row.
  - Doctor gains an info finding "N items lost commit attribution (no Work-Item trailer);
    see `sdlc.py trailers`".
- Copy `optional/runtime/sdlc.py` and `optional/runtime/finish.py` byte-identical to
  `.ai-sdlc/bin/`.
- **Docs.** In `docs/cli.md`, the `finish` row says the waiver name must be an approver, the
  run must be full and current, and commits are matched by trailer. The `verify` row says
  `--stage` runs never satisfy finish. `/sdlc-finish` gets the same three facts in
  `optional/claude-commands/sdlc-finish.md`, `.claude/commands/sdlc-finish.md` and
  `.agents/skills/sdlc-finish/SKILL.md`. `CHANGELOG.md` gets a bullet under
  `## Unreleased`.

## Spec changes

none. The kit does not use its own Specs row.

## Files that change

- `optional/runtime/sdlc.py`
- `optional/runtime/finish.py`
- `install.py`
- `.ai-sdlc/bin/sdlc.py`
- `.ai-sdlc/bin/finish.py`
- `optional/claude-commands/sdlc-finish.md`
- `.claude/commands/sdlc-finish.md`
- `.agents/skills/sdlc-finish/SKILL.md`
- `tests/smoke.py`
- `docs/cli.md`
- `docs/install.md`
- `CHANGELOG.md`

## Order of work

1. Write `test_finish_evidence_binding` in `tests/smoke.py`, add it to the tuple in
   `main()`, and prove that each check fails on the current code.
2. Attribution by trailer only. This is the riskiest step, because it changes which
   commits every caller sees.
3. Record the `selected` field in the ledger, and tighten the tagged rule in
   `evidence_matches`.
4. Add the partial-run and stale-run rules to `verify_state`, with the new owed message.
5. Add the waiver approver list and filter `waivers()`. Update the existing
   `test_finish` fixture so its `--by Sam` waiver has `Sam` in Approvers.
6. Copy the runtime files to `.ai-sdlc/bin/`, update the docs and the CHANGELOG, and run
   `python3 validate.py`.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Keep body mentions for commits that have no trailer (legacy) | A commit mentioning the ID is the loophole itself; doctor already skips items with no commits, so legacy items drop out of judgement instead of passing falsely |
| Store "partial": true instead of the stage list | The list costs nothing and lets the viewer say which stages ran |
| Refuse `--stage` together with `--item` | `verify --stage unit --item X` is a fair inner-loop command; it only must not close the item |
| Match the waiver name against the commit's Agent trailer | An agent can pass any other name; an allow-list held in the charter is the only check a human controls |

## Affected surfaces

- **Code:** `sdlc.py` (`item_commits`, `commit_index`, `verify`, `evidence_matches`),
  `finish.py` (`verify_state`, `waivers`, `finish`).
- **Data:** ledger rows from `verify --stage` gain a `selected` list. Existing rows are read
  as before.
- **Contracts:** commit attribution is now trailer-only, for `finish`, `doctor`, `view`,
  `dispatch.py:567` and `metrics`. Waivers need an approver name.
- **Docs to update:** `docs/cli.md`, the `/sdlc-finish` command and skill copies,
  `CHANGELOG.md`.

## Failure modes

- **Detached HEAD or no git.** If `merge-base` fails, the HEAD branch does not count. The
  rule fails closed.
- **Charter stage added after the run.** The run no longer covers every stage, so `finish`
  asks for a fresh run. That is the intended result.
- **Empty or placeholder Approvers.** Every waiver is refused. The message says to fill
  the Approvers row.
- **Several items in one commit.** Only the trailer's item gets the commit. A merge commit
  that lists a range (`NUHT-001..006`) no longer attributes itself; the item commits behind
  it still do.

## Test strategy

- **Acceptance criteria mapping:** each Problem bullet maps to one check in
  `test_finish_evidence_binding`.
- **Unit:** none separate. The smoke test drives the real CLI in a temporary repository.
- **Integration:** `sdlc.py verify` and `sdlc.py finish` in a temporary git repository with
  a two-stage charter.
- **Negative cases (all must be refused):**
  - A `verify --item X` run made on an unrelated commit before X's commits, with other edits
    in the tree: finish owes verify.
  - A `verify --stage unit --item X` run on X's commit: finish owes verify, and the ledger
    row carries `"selected": ["unit"]`.
  - A full run on X's first commit, followed by a second X commit: finish says the run is
    stale.
  - `finish X --waive verify --by claude-code` when Approvers is `Sam`: refused, no ledger
    row written.
  - A commit for another item whose body mentions X: `item_commits(X)` does not include it.
  - A partial run and a stale run each print their own message (`partial`, `stale`).
  - `finish X --waive verify --by Sam` with no TTY while `NUHUT_USER=claude-code`: refused.
  - An Approvers row changed only on the working branch to add `claude-code`: the waiver
    by `claude-code` is still refused, because the row is read from the default branch.
- **Positive cases:** a full clean run on X's newest commit passes. Verify, commit the
  code, then commit the ledger and worklog separately: finish still passes (records-only
  commits do not make the run stale). Doctor after finish plus an unrelated commit reports
  no new finding (time-invariant `evidence_matches`). A dirty run on its
  parent, followed by the commit, passes. `--waive verify --by Sam`, with `Sam` in
  Approvers, passes at Tier 2.
- **Manual:** none.
- **Proof:** `python3 -c "import sys;sys.argv=['x'];sys.path.insert(0,'tests');import
  smoke;smoke.test_finish_evidence_binding();print(smoke.failures)"` prints `[]`; the same
  command for `test_finish` prints `[]`; `python3 validate.py` passes. Before the fix, the
  first command lists the negative checks as failures.

## Risks

- **Legacy history.** Commits from before 4.0, and most of this repository's own early
  commits, have no `Work-Item` trailer. After the change, those items have no commits:
  doctor stops judging their worklog claims, and the viewer shows no commits for them.
  This is accepted. A false pass is worse than no judgement.
- **Brace rule.** No literal doubled curly braces may appear in the runtime files.

## Rollback

Revert the commit. The ledger's `selected` field is additive and ignored by the old code.
No data migrates.

## Out of scope

- CI enforcement of trailers and of the ledger run on HEAD: NUHT-022.
- Approvals read from GitHub reviews instead of charter names: NUHT-024.
- A people registry for the names that Approvers holds: NUHT-023.

## Assumptions

- The Approvers row is the right holder of waiver authority until NUHT-024 replaces it.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| A4 | Records-only commit makes the run stale; NUHT-022 rule drifts | Fix | "Newest code commit"; NUHT-022 now calls `verify_state` |
| S7 | `evidence_matches` depends on HEAD; brief differs from plan | Fix | Time-invariant `evidence_matches`; freshness only in `verify_state`; "dirty-on-other-work" dropped |
| S2 | Approvers editable on the branch; `--by` is just a name | Fix | `trusted_text`; `waived_as` identity check with no TTY |
| U1 | Silent break on upgrade | Fix | "Upgrade notice" |
| U2 | `partial` and `stale` merged into one message | Fix | Two states, two messages |
| U4 | Extra `Waiver approvers` row | Fix | Row dropped; Approvers only |

## Review

| Role | Verdict | Notes |
| --- | --- | --- |
| qa | | |
| security | | |

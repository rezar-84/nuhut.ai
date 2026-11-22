---
status: draft
owner: security
last-reviewed: 2026-11-22
---

# Plan: NUHT-024 Approvals read from GitHub PR reviews

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-023 (people registry), NUHT-012
(`trusted_text`), NUHT-021 (command table)

## Problem

A Tier 1 item's approval today is a status and a name copied from the charter.
`optional/runtime/finish.py:517-519` parks the item and writes the charter's **Approvers**
cell (`rt.labelled(project.charter, "Approvers")`) as the person it waits on. Nothing
records who actually approved, or where that approval came from. A team that approves in
GitHub PR reviews has that evidence in GitHub and none of it in the records, so the
two-approver rule in `process/05-change-control.md` ("Approvals") cannot be checked. The
only "approval" the runtime reads is the `AI_SDLC_APPROVAL` environment variable
(`hooks.py:452`, `sdlc.py:4696`). Any process can set it, so it must never count as a
merge approval.

## Outcome

`sdlc.py approvals <ID>` and `sdlc.py finish <ID>` (Tier 1, and Tier 2 under Strict tier
rules) read the item branch's PR reviews through `gh pr view <branch> --json
reviews,number,headRefOid,author,state,headRepositoryOwner,headRepository,isCrossRepository,baseRefName`
when `gh` is on PATH and authenticated, and only when that PR is this repository's own,
is open or merged, and its head is the item branch's local commit. Each
approving reviewer whose GitHub login maps to a `people.json` handle (NUHT-023) is
recorded with `"source": "github"`. When `gh` is absent, fails or finds no PR, the charter
**Approvers** names are recorded with `"source": "charter"` as a fallback, and the item
stays Parked. `AI_SDLC_APPROVAL` is never read as an approval.

## Approach

- **`finish.py`: `approvals(rt, project, item, run=subprocess.run)`.** Returns
  `{"source", "approvers", "ignored", "required", "met", "pr", "note"}`.
  - **Branch.** Use the current branch when it names the item. Otherwise use
    `claims._existing_item_branch` (`claims.py:438`). With no item branch, take the
    charter fallback and give the reason in `note`.
  - **gh call.** Run `shutil.which("gh")`, then `gh repo view --json nameWithOwner` to get
    the repository, then `gh pr view <branch> --repo <nameWithOwner> --json
    reviews,number,headRefOid,author,state,headRepositoryOwner,headRepository,isCrossRepository,baseRefName`,
    with `cwd=project.root`, a 20 s timeout and a list argv (no shell).
  - **PR identity.** The PR counts only when `isCrossRepository` is false, `state` is
    `OPEN` or `MERGED`, and `headRefOid` equals `git rev-parse <item branch>`. For a
    `MERGED` PR whose branch is gone or moved, it is enough that `headRefOid` is an
    ancestor of the default branch and contains the item's newest commit
    (`git merge-base --is-ancestor`). Otherwise the result falls back to the charter
    source with `note: pr-mismatch` and a reason such as "pr head differs from local",
    and the item stays Parked.
  - **gh failures.** A non-zero exit, a timeout, invalid JSON or a missing `gh`
    each fall back to the charter, and each names its reason in `note`. None of them
    raises. `dispatch.py:355` is the existing `gh` precedent.
  - **Counting rule.** Take the latest review per `author.login` by `submittedAt`. It
    counts when all of these hold:
    - its `state` is `APPROVED`
    - its `commit.oid` equals `headRefOid`, so a stale approval of older code does not
      count
    - the login is not the PR author and not a bot (a `[bot]` suffix or
      `author.is_bot`)
    - the login maps to a `people.json` handle

    A login that fails any of these goes to `ignored` with the reason (`stale`,
    `self-approval`, `bot`, `unmapped`, `changes-requested`, `dismissed`).
  - **Login mapping.** Uses the NUHT-023 people accessor, matching logins without regard
    to case. `people.json` is read from the default branch through NUHT-012's
    `trusted_text` (`git show <default>:<docs>/project/people.json`), never from the
    working tree when the default branch has it, so a PR cannot map a second account to a
    handle and count it. `people.json` is a default Tier 1 path in `ci-check` (NUHT-022)
    and on NUHT-013's human-owned list.
  - **Identity namespace.** The charter's Approvers cells hold `people.json` handles.
    NUHT-012's `waiver_approvers` resolves through the same registry, so the waiver check
    and the approval count agree about each person.
  - **Recorded value.** The handle is what gets recorded, not the raw login. Logins are checked
    against `^[A-Za-z0-9-]{1,39}$` before they are printed or stored, so `gh` output
    cannot inject text into the backlog or the worklog.
  - **Required count.** Tier 1 needs 2 approvals. Tier 2 under Strict tier rules needs 1.
    `met` is true when that many distinct handles approved the current head.
  - **Small teams.** The required count does not change with team size; changing it is a
    Tier 1 governance change (AGENTS.md section 9). When the trusted Approvers row lists
    fewer distinct people than the count, finish says so: "1 of 2: this project lists 1
    approver; see process/05 Approvals". `05-change-control.md` "Approvals" gets the
    matching sentence: such an item stays Parked until a human closes it.
  - **Never `AI_SDLC_APPROVAL`.** The function does not read the environment. A test sets
    the variable and asserts that nothing changes.
- **`finish.py:517-519` Tier 1 / Strict gate.** Replace the bare charter read with
  `approvals()`.
  - When `met` is true, the item moves to Done. `completed` is set and the approvers are
    recorded.
  - When `met` is false, the item stays Parked. `waiting_on` reads, for example,
    `alice (github), charter: rezar-84`, and `park_reason` reads `merge approval (Tier 1):
    1 of 2 on <sha7>`.
  - The output gains an `approval` line that lists each approver with its source, and
    each ignored login with its reason.
  - Under `--dry-run`, nothing is written and `gh` still runs.
- **Recording.** In a sharded project, the item shard's `approvers` holds the record
  `{"handle", "login", "source", "commit", "at"}`. With the charter source, `login`,
  `commit` and `at` are blank. `shards.py:233-235` today normalises `approvers` to a list
  of strings. It will keep strings as they are, accept these dicts, and drop any other
  type. In an unsharded project, the Parked row's Waiting-on cell carries the same text,
  and the drafted worklog entry gains an `Approved:` line.
- **`sdlc.py approvals <ID> [--json]`.** A read-only report of the same result. It exits
  0 when `met` is true and 1 otherwise. The parser is registered next to `finish`
  (`sdlc.py:3799`), the dispatch next to `sdlc.py:4070`, and an example goes in the
  examples table (`sdlc.py:3721`).
- **Docs.**
  - The `approvals` row goes in `docs/cli.md` and the `README.md` command table
    (`validate.py` requires both).
  - `process/05-change-control.md` "Approvals" gains one paragraph: GitHub approvals
    count only on the current head, from mapped people other than the author, and the
    charter names are the fallback.
  - The template charter's Approvers hint says that its names are the fallback.

## Files that change

- `optional/runtime/finish.py`
- `optional/runtime/sdlc.py`
- `optional/runtime/shards.py`
- `.ai-sdlc/bin/finish.py`
- `.ai-sdlc/bin/sdlc.py`
- `.ai-sdlc/bin/shards.py`
- `template/docs/process/05-change-control.md`
- `handbook/process/05-change-control.md`
- `template/docs/project/charter.md`
- `docs/cli.md`
- `README.md`
- `CHANGELOG.md`
- `tests/smoke.py`

## Tests (written first)

A new `test_github_approvals()` in `tests/smoke.py` runs against a temporary install. It
puts a stub `gh` (a shell script that prints a JSON fixture and exits with a chosen code)
first on `PATH`, and writes a `people.json` that maps `alice` and `bob`.

- **Two approvals on the head.** `finish` on a Tier 1 item moves it to Done, and the
  shard's `approvers` holds two records with `source: github` and the head commit.
- **One approval.** The item stays Parked, the output says `1 of 2`, and `approvals`
  exits 1.
- **Negative: stale approval.** A review whose `commit.oid` is not `headRefOid` goes to
  `ignored` as `stale`.
- **Negative: self-approval and bot.** The PR author's own approval and a `x[bot]` login
  are ignored.
- **Negative: unmapped login.** An approving login missing from `people.json` is ignored
  as `unmapped`, and its handle is not invented.
- **Negative: later changes requested.** An `APPROVED` review followed by
  `CHANGES_REQUESTED` from the same login does not count.
- **Negative: `AI_SDLC_APPROVAL`.** With `AI_SDLC_APPROVAL=ticket` set and no `gh`, the
  item stays Parked and every approver is `source: charter`.
- **Fallback.** No `gh` on PATH, `gh` exiting 1, and `gh` printing invalid JSON each
  give Parked with charter-sourced approvers and a `note`, never a traceback.
- **Negative: cross-repo PR.** `isCrossRepository: true` with two approvals: Parked,
  `note: pr-mismatch`.
- **Negative: head mismatch.** `headRefOid` differs from the local item branch: Parked,
  `note` names "pr head differs from local".
- **Negative: closed PR.** `state: CLOSED` is not counted.
- **Negative: working-tree mapping.** A `people.json` edited only in the working tree to
  map `mallory` to a handle: `mallory`'s approval is `unmapped`.
- **Solo team.** Approvers lists one person: the output contains "this project lists 1
  approver".
- **Hostile login.** A login of the form `a|b\n## Done` is rejected by the pattern and
  never reaches `backlog.md`.

Run it alone: `python3 -c "import sys;sys.argv=['x'];sys.path.insert(0,'tests');import
smoke;smoke.test_github_approvals();print(smoke.failures)"`, then `python3 validate.py`.

## Risks

- **NUHT-023 shape.** This plan assumes that the people registry exposes a lookup from a
  GitHub login to a handle. If NUHT-023 lands without a `github` field per person, this
  item adds that field, and this list gains the registry file before the build.
- **Weakening the gate.** Moving a Tier 1 item to Done on GitHub evidence is new. The
  counting rule is deliberately narrow: head commit only, two distinct mapped humans,
  never the author, never a bot, never the environment. Anything short of that leaves the
  item Parked as it is today.
- **gh trust.** The output of `gh` is treated as untrusted data. It is parsed as JSON,
  logins are checked against a pattern, and nothing from it is interpreted as a command or
  as markup.
- **Brace rule.** No literal doubled curly braces may appear in the runtime files, because
  of the installer's placeholder substitution. Any template-like regex is spelled
  `[{][{]`.
- **Network latency.** `finish` makes one `gh` call, with a 20 s ceiling. `guard` and
  `doctor` never call it.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| A10/S8 | PR picked by branch name; head not bound to local commits | Fix | "PR identity"; `--repo`; new negative tests |
| A10/S8/S2 | `people.json` editable in the same PR | Fix | Read through `trusted_text` from the default branch; Tier 1 path; human-owned in hooks |
| U8 | Three identity namespaces | Fix | "Identity namespace": Approvers hold handles |
| U8 | Small-team path via `item set --status Done` after one approval | Contest | Lowering Tier 1's two-approver rule is a Tier 1 governance change that AGENTS.md section 9 reserves for the owner. The plan adds the explicit "1 of 2: this project lists 1 approver" message and documents that the item stays Parked for a human; the relaxation itself is an open question for the owner in the review record |

## Rollback


Revert the commit. Without `approvals()`, `finish` goes back to parking Tier 1 items on
the charter names. Shards that already hold dict approvers stay readable, because
`shards.py` before this item already kept `approvers` as a list.

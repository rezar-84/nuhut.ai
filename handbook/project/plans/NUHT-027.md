---
status: draft
owner: devops-sre
last-reviewed: 2026-11-22
---

# Plan: NUHT-027 Release records and deploy ledger; claim `release` becomes `unclaim`

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-021 (command table). Uses NUHT-023's
person lookup when it has landed (NUHT-029 depends on this)

## Problem

A user project can say what was built, reviewed and verified, but not what shipped or
where. Nothing records which version runs in which environment, which commits and work
items a version contains, or who deployed it. The release runbook asks for a tag and a
worklog entry, and NUHT-029 (DORA metrics) has no deploy data to count. The name is also
taken: `sdlc.py release <ID>` frees a work item claim (`optional/runtime/sdlc.py:3967`),
so the obvious word for "record a release" already means something else.

## Outcome

`sdlc.py deploy record --version 1.4.0 --env staging` writes
`handbook/project/releases/1.4.0.json` (in a user project, `<docs>/project/releases/`)
and appends one line to `<docs>/project/deploys.jsonl`. `sdlc.py deploy list` prints which
version runs in each environment, and the viewer's Dashboard shows the same table.
`sdlc.py unclaim <ID>` frees a claim. `sdlc.py release <ID>` still works the same way,
exits with the same codes, and prints one deprecation line on stderr.

## Approach

- **New module `optional/runtime/releases.py`** (stdlib only, Python 3.8+, no doubled
  curly braces; regexes spell braces as `[{]`):
  - `validate_version(s)`: `^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$` and no `..`. The version
    becomes a file name, so this check is the path-traversal guard. `validate_env(s)`:
    `^[a-z0-9][a-z0-9_-]{0,31}$`.
  - `resolve_ref(project, ref)`: refuses a ref that starts with `-`, so it cannot be read
    as a git option, then runs `git rev-parse --verify --quiet <ref>^{commit}` through
    `project.git`. An unknown ref is an error, never an empty range.
  - `default_from(project, env)`: the `to` commit of the newest line in the ledger for
    that env. If there is none, the newest release record of any env. If there is none,
    the range starts at the root commit.
  - `collect(project, rt, from_sha, to_sha)`: runs
    `git log --format=%H%x00%B%x1e <from>..<to>` (the whole history when there is no
    `from`) and parses trailers with `rt.trailers` (`optional/runtime/sdlc.py:1501`), the
    same parser `commit_index` uses (`sdlc.py:1567`). It returns
    `{"commits": n, "items": sorted Work-Item IDs}`. Only items named in the `Work-Item:`
    trailer count; IDs mentioned in the message body do not.
  - `record(project, rt, version, env, from_ref, by)`: builds
    `{"schema": 1, "version", "env", "from", "to", "commits", "items", "date"
    (UTC ISO-8601), "by", "agent"}`. `by` is the person: `--by` when given, else the
    NUHT-023 person (`NUHUT_USER`, else `git config user.name` mapped to a `people.json`
    handle). Until NUHT-023 lands, the fallback is `git config user.name`, and `null` when
    that is unset. `agent` is `identity()[0]` (`sdlc.py:1523`), stored separately so the
    deploy ledger answers who deployed, not which tool ran. Email addresses are never stored.
    - **New version:** write `releases/<version>.json` atomically with
      `_shards_mod._atomic_write_text`.
    - **Promotion:** the file exists with the same `to` commit, so only the ledger line
      is added and the env is added to the record's `envs` list.
    - **Conflict:** the file exists with a different `to` commit, so the command refuses
      with exit 1 and names both commits. A version is never rewritten, as
      `process/05-change-control.md` says of tags.
  - `append_ledger(project, line)`: one `json.dumps(sort_keys=True)` line, written with a
    single `os.write` on an `O_APPEND` descriptor, so concurrent writers do not interleave
    within a line.
  - `deployed(project)`: reads the ledger, skips malformed lines and counts them, and
    returns `{env: newest line}` plus `{"skipped": n}`.
- **`optional/runtime/sdlc.py`:**
  - Add a `deploy` command group in the NUHT-021 command table, in the noun-verb form of
    `item add|set|list` and `spec list|show`: `deploy record` (`--version` and `--env`
    required, `--from`, `--to` default `HEAD`, `--by`, `--dry-run`, `--json`) and
    `deploy list` (`--json`). Add a dispatch branch that calls
    `runtime_module("releases")` (`sdlc.py:1314`).
  - Add an `unclaim` subparser with the arguments `release` has today (`sdlc.py:3967`)
    and keep `release` as the same parser with help text "deprecated: use unclaim".
  - The handler at `sdlc.py:4444-4478` accepts both. For `release` it writes
    one stderr line that repeats the user's own arguments, for example
    `release: deprecated, use: sdlc.py unclaim ACME-12 --remove-worktree`, before acting.
    The CHANGELOG bullet commits to removing the alias in 7.0.
    stdout, `--json` output and exit codes do not change, so existing scripts that parse
    them keep working.
  - Update `MAIN_HELP` (`sdlc.py:3693`), `EXAMPLES` (`sdlc.py:3757`, adding
    `unclaim`, `deploy record` and `deploy list`), the claim hint at `sdlc.py:4462` and the
    doctor fix hint at `sdlc.py:450` to name `unclaim`.
- **`optional/runtime/claims.py:836-853`:** doctor messages say `unclaim`.
  `claims.release()` keeps its Python name. `finish.py` and `dispatch.py` call it, and
  renaming it is internal churn with no user-visible effect.
- **`optional/runtime/view.py`:** `_build_inner` (around `view.py:620`) adds
  `model["deploys"]` from `releases.deployed(project)` inside a try/except, so a broken
  ledger never stops the view opening. `watched_paths` already walks `project/` for
  `.json` and `.jsonl` (`view.py:1172`), so live mode picks up new records without a
  change.
- **`optional/runtime/view/js/12-dashboard.js`:** an "Environments" card (built with
  `ckCard`, `10-dashboard-helpers.js:35`) shows one row per env: version, date, by, and
  the item count. The row opens the release record in the side panel. The card has an
  empty state that names `sdlc.py deploy record`. All text goes through `el(...,
  {text})`, never `innerHTML`, because ledger content is untrusted. Then run
  `python3 tools/build_view.py` and copy `view.html`.
- **`install.py`:** add `releases.py` to `RUNTIME_FILES` (`install.py:75`), and write
  `<docs>/project/deploys.jsonl merge=union` into `.gitattributes` (added once, never
  duplicated), so ledgers appended on many branches merge without conflict. NUHT-025
  keeps this line when it adds the item-shard driver.
- **Docs:**
  - `docs/cli.md` and `README.md` gain `unclaim`, `deploy record` and `deploy list`. They
    keep `release`, marked deprecated.
  - `docs/multi-agent.md` uses `unclaim`, and `docs/viewer.md` describes the card.
  - `template/docs/process/10-multi-agent.md` and its handbook copy say `unclaim`.
  - `template/docs/templates/release-runbook.md` and its handbook copy gain a
    Post-release step: "`sdlc.py deploy record --version <v> --env <env>`".
- **Copies:** copy every changed runtime file byte-identical to `.ai-sdlc/bin/`.

## Spec changes

none: the kit repository's Specs row is off; the record format is documented in
`docs/cli.md`.

## Files that change

- `optional/runtime/releases.py` (new)
- `optional/runtime/sdlc.py`
- `optional/runtime/claims.py`
- `optional/runtime/view.py`
- `optional/runtime/view/js/12-dashboard.js`
- `optional/runtime/view.html`
- `.ai-sdlc/bin/releases.py` (new)
- `.ai-sdlc/bin/sdlc.py`
- `.ai-sdlc/bin/claims.py`
- `.ai-sdlc/bin/view.py`
- `.ai-sdlc/bin/view.html`
- `install.py`
- `tests/smoke.py`
- `docs/cli.md`
- `docs/multi-agent.md`
- `docs/viewer.md`
- `README.md`
- `template/docs/process/10-multi-agent.md`
- `handbook/process/10-multi-agent.md`
- `template/docs/templates/release-runbook.md`
- `handbook/templates/release-runbook.md`
- `CHANGELOG.md`

## Order of work

1. Write `test_release_records()` and `test_unclaim_alias()` in `tests/smoke.py`, add
   them to the tuple in `main()`, and run each alone to prove it fails.
2. `releases.py` with validation, range collection, record, ledger and `deploy list`.
   **Riskiest step:** a version string reaches a file path and a ref reaches git.
3. `deploy record` and `deploy list` subcommands, plus `RUNTIME_FILES`.
4. The `unclaim` rename with the deprecated `release` alias, and the hint and doctor
   message wording.
5. The viewer model key, the Dashboard card, `build_view.py`.
6. Docs, the template and handbook pairs, CHANGELOG, and the `.ai-sdlc/bin/` copies.
   Then run `python3 validate.py`.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Reuse `release` for release records and break the claim command | `release <ID>` is public: docs, dispatch scripts and the smoke suite call it. Changing what it does without notice breaks people. |
| Derive deploys from git tags only | Tags give a version, not an environment, not who deployed it, and not when. Many projects deploy untagged commits to staging. |
| One growing `releases.json` | Concurrent writers would conflict on one file, and every release would rewrite history. One file per version plus an append-only ledger keeps each write small and lets git merge them. |
| Count IDs mentioned anywhere in commit bodies | Prose mentions ("follow-up to NUHT-012") would show up as shipped items. Only the `Work-Item` trailer is a claim of authorship. |

## Affected surfaces

- **Code:** `releases.py` (new), `sdlc.py`, `claims.py`, `view.py`, Dashboard JS.
- **Data:** new `<docs>/project/releases/<version>.json` and
  `<docs>/project/deploys.jsonl` in user projects. No existing data changes.
- **Contracts:** the CLI gains `unclaim`, `deploy record` and `deploy list`. `release` is
  deprecated but behaves the same. The record schema (`schema: 1`) and the ledger line
  format are new contracts that NUHT-029 reads.
- **Docs to update:** `docs/cli.md`, `README.md`, `docs/multi-agent.md`,
  `docs/viewer.md`, the multi-agent process doc and the release runbook (template and
  handbook).

## Failure modes

- **Hostile version or env** (`../../x`, `a/b`, an empty string, 200 characters): refused
  before any path is built, and nothing is written.
- **A ref that looks like an option** (`--output=/tmp/x`) or an unknown ref: refused with
  exit 1, and git is never called with it as an option.
- **Not a git repository, or no commits:** a clear error, exit 1, no files written.
- **The same version recorded twice for a different commit:** refused. For the same
  commit it is a promotion, so only the ledger line is added.
- **Two agents record at once:** each record file is written atomically. Ledger lines
  are single `O_APPEND` writes, and the last line per env wins in `deploy list`.
- **A malformed or hand-edited ledger line:** skipped and counted. `deploy list` and the
  viewer still render.
- **Missing ledger:** `deploy list` prints "nothing recorded yet" with the
  `deploy record` command, and the viewer card shows its empty state.
- **Untrusted text in the viewer** (a `by` or version containing HTML): rendered as
  text nodes.
- **Old scripts calling `release`:** the same stdout, JSON and exit code. The only
  difference is the stderr note.

## Test strategy

- **Acceptance criteria mapping:** the Outcome's four claims each map to one assertion
  group in the tests below.
- **Unit:** `releases.validate_version` and `validate_env` tables of accepted and
  refused values. `deployed()` on a ledger with a malformed line.
- **Integration (`test_release_records`)**, in a temporary installed repo with commits
  carrying `Work-Item:` trailers:
  - `deploy record --version 1.0.0 --env staging` writes the record with the right
    items and commit count, and adds one ledger line.
  - Recording the same version for `prod` is a promotion: the ledger gains a line and the
    record gains the env.
  - A second version defaults `--from` to the previous record, so only the new items
    appear.
  - `deploy list --json` maps each env to its version, and the view model carries `deploys`.
- **Integration (`test_unclaim_alias`):**
  - `unclaim` frees a claim.
  - `release` frees a claim with the same JSON output and prints the deprecation note on
    stderr.
- **Negative cases (Tier 1):**
  - The version `../evil` is refused and writes no file outside `releases/`.
  - The env `Prod/1` is refused.
  - `--from --upload-pack=x` is refused.
  - An unknown `--from` exits 1.
  - Re-recording `1.0.0` at a different commit is refused, and the original file is
    unchanged.
- **Manual:** open `sdlc.py view` and check that the Environments card and its empty
  state read well in light and dark themes and at phone width.
- **Proof:**
  - `python3 -c "import sys;sys.argv=['x'];sys.path.insert(0,'tests');import smoke;smoke.test_release_records();print(smoke.failures)"`
  - the same command with `test_unclaim_alias`
  - `python3 validate.py`
  - `cmp optional/runtime/releases.py .ai-sdlc/bin/releases.py`, and the same for each
    copied file

## Risks

- **Path traversal through `--version`.** Mitigated by the validation regex, plus a
  check that the resolved path stays under `releases/`.
- **Argument injection through `--from`.** Mitigated by refusing a leading `-` and by
  `rev-parse --verify`.
- **Personal data in tracked files.** `by` is a people handle or git user name, never an email
  address. The docs say so.
- **Help-text drift.** `validate.py`'s `docs_stay_true` fails if a new subcommand is
  missing from `docs/cli.md` or `README.md`.
- **Brace rule.** No literal doubled curly braces in `releases.py` or the JS, because of
  the installer's placeholder substitution.

## Rollback

Revert the commit. The new files under `project/releases/` and `deploys.jsonl` are data
in user projects that nothing else reads, so they can stay or be deleted. `release`
never stopped working, so no caller needs to change back. Not yet exercised.

## Out of scope

- Running deploys, or checking the charter's "Who may deploy" column (a later item).
- DORA metrics from the ledger (NUHT-029).
- Removing the deprecated `release` alias (a future major version, after one release
  with the deprecation note).
- Renaming the internal `claims.release()` function.

## Assumptions

- The `Work-Item` trailer is the record of which item a commit belongs to (AGENTS.md
  section 9).
- Projects that deploy from untagged commits still want a version label, and the commit
  SHA works as one.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| U7 | `release-record` and `deployed` break noun-verb naming | Fix | `deploy record` and `deploy list` |
| U7 | `release` alias note too vague | Fix | stderr note repeats the user's arguments; removal in 7.0 in CHANGELOG |
| U7 | `by` is the agent, not the person | Fix | `by` is the person, `agent` stored separately |
| A12 | `deploys.jsonl` conflicts on merge | Fix, adapted | This item writes the `merge=union` line itself, because it creates the ledger and lands before NUHT-025 |

## Review


| Role | Verdict | Notes |
| --- | --- | --- |
| devops-sre | _(pending)_ | |
| security | _(pending)_ | |

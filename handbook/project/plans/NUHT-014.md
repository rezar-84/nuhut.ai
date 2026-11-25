---
status: draft
owner: devops-sre
last-reviewed: 2026-11-22
---

# Plan: NUHT-014 Release pipeline

**Tier:** 1 **Effort:** Normal **Depends on:** none (owner approval to edit the release
process, AGENTS.md section 9)

## Problem

The release pipeline in `.github/workflows/version.yml` has four faults, and the repository
carries a workflow that never runs.

- **Every push to `main` releases.** `tools/semver.py` `level_of()` (lines 69-78) returns
  `"patch"` for every type that is not `feat`, and also for a subject that is not a
  Conventional Commit at all. A docs-only merge cuts a patch release and runs the 7-minute
  smoke suite to do it.
- **Runs race.** The concurrency group is `version-${{ github.ref }}` (lines 15-17), so it
  only covers runs on the same ref. Two runs on `main` that overlap with a run started some
  other way, or a human push landing during the smoke suite, can both compute the same
  version. Nothing re-reads `origin/main` before the bot pushes (lines 49-62), so the push
  is rejected late or, worse, a tag is created for a commit that is not on `main`.
- **No tag check.** If `v$v` already exists, `git tag` or `gh release create` fails partway,
  after the release commit was made, and the summary does not say why.
- **Breaking-change detection is too loose.** `level_of()` treats `BREAKING CHANGE:` at the
  start of any body line as a major bump, including a line in the middle of a description
  that quotes the spec. Conventional Commits only gives it that meaning in the footer.
- **`release.yml` is dead.** A tag pushed with `GITHUB_TOKEN` does not trigger other
  workflows, so `.github/workflows/release.yml` never runs; `version.yml` already publishes
  the GitHub release itself (line 61 says so). The dead file still appears in the charter
  and in AGENTS.md section 9 as the thing that needs approval to edit.

## Outcome

A push to `main` whose commits since `VERSION` last changed are all `docs`, `chore`,
`test`, `ci` (or other non-release types, or non-conventional subjects) skips the release
job, and `semver.py next --json` reports level `none` for it. Release runs on `main` are
serialised in one `release` group, a run whose `origin/main` has moved past the tested
commit exits 0 and leaves the release to the queued newer run, so the released tree is
always the one validate and smoke ran on, a tag that already exists stops the run with a clear error
before anything is pushed, and `.github/workflows/release.yml` no longer exists or is
referred to as live.

## Approach

- **`tools/semver.py`**
  - New constants: `RELEASE_TYPES = {"feat": "minor", "fix": "patch", "perf": "patch",
    "refactor": "patch", "revert": "patch"}`. Every other type (`docs`, `chore`, `test`,
    `ci`, `build`, `style`, and anything unknown) maps to `"none"`.
  - `level_of(subject, body)`:
    1. `breaking_footer(body)` returns true only when a line of the **footer** starts with
       `BREAKING CHANGE:` or `BREAKING-CHANGE:`. The footer is the last paragraph of the body
       (text after the last blank line), and only when every non-empty line in it is a
       trailer (`Token: value`, `Token #value`, or the `BREAKING CHANGE:` form). A body that
       is one paragraph counts as a footer under the same rule. A quoted (`> `) or indented
       line never matches.
    2. A subject that does not match `HEADER` returns `"none"`, unless the footer is
       breaking (then `"major"`).
    3. A `!` after the type returns `"major"`, whatever the type.
    4. Otherwise the largest level among the subject's types, from `RELEASE_TYPES`.
  - The module docstring (lines 2-8) and the `bump` message for level `none` (line 212)
    change to say there are no releasable commits (only docs, chore, test or ci), rather
    than no commits at all.
  - `prerelease()` is unchanged: a branch with no releasable commits still gets
    `X.Y.(Z+1)-dev.N+sha` so branch builds stay distinguishable.
- **`.github/workflows/version.yml`**, split into three jobs:
  - `prerelease` (branches other than `main`): today's "Report the prerelease version"
    step, unchanged. Keeps the per-ref concurrency group.
  - `plan` (main only): checkout with `fetch-depth: 0`, run `semver.py next --json`, and
    expose `level` and `next` as job outputs. Writes "Nothing to release" to the step
    summary when the level is `none`.
  - `release` (`needs: plan`, `if: needs.plan.outputs.level != 'none'`), with
    `concurrency: { group: release, cancel-in-progress: false }`. Steps:
    1. Validate: `python3 validate.py` and `python3 tests/smoke.py`, as today.
    2. `git fetch origin main --tags`, then compare `git rev-parse origin/main` with
       `GITHUB_SHA`. If they differ, print `superseded by a newer push; that run releases`
       and exit 0. There is no rebase, so the released tree is always the tested one.
    3. Recompute: `level` from `semver.py next --json`. If it is now `none` (a later run
       already released these commits), exit 0 with "Already released".
    4. `v=$(python3 tools/semver.py bump)`, then `python3 validate.py`.
    5. Tag guard: if `git rev-parse -q --verify "refs/tags/v$v"` or
       `git ls-remote --exit-code --tags origin "refs/tags/v$v"` finds the tag, exit 1 with
       `::error::tag v$v already exists; VERSION and the tags disagree, fix by hand`.
       Nothing has been committed or pushed at this point.
    6. Commit, tag, `git push --atomic origin HEAD:main "v$v"`, `gh release create`, as
       today. `--atomic` means the branch and the tag land together or not at all.
  - The top-level `concurrency` block is removed; each job carries its own. The
    `chore(release):` skip guard stays on every job, and now also requires
    `github.actor == 'github-actions[bot]'`, so a human push whose last commit happens to
    start with `chore(release):` still releases the commits pushed with it.
  - The comment at line 61 about `release.yml` is replaced by one saying why this workflow
    publishes the release itself.
- **Delete `.github/workflows/release.yml`** (owner directed). Update the places that name
  it as live: `handbook/project/charter.md` line 31 (CI row),
  `AGENTS.md` section 9 line 145 (the approval rule now names
  `.github/workflows/version.yml`, the release pipeline), and the NUHT-014 row in
  `docs/landscape.md` line 41 (marked resolved in v6). The worklog and older plans keep
  their history unchanged.
- **`CHANGELOG.md`**: one bullet under `## Unreleased`.

## Spec changes

none: the change is to the kit's own release automation. No installed project's
behaviour or CLI changes; `semver.py` is a repository tool, not a runtime file.

## Files that change

- `tools/semver.py`
- `.github/workflows/version.yml`
- `.github/workflows/release.yml` (deleted)
- `tests/smoke.py`
- `AGENTS.md`
- `handbook/project/charter.md`
- `docs/landscape.md`
- `CHANGELOG.md`

## Order of work

1. Write the failing checks in `tests/smoke.py` (below) and run
   `test_semver` and `test_release_workflow` alone to show they fail.
2. Change `level_of()` and the footer parser in `tools/semver.py`; `test_semver` passes.
3. Rewrite `.github/workflows/version.yml` and delete `release.yml`; `test_release_workflow`
   passes. **Riskiest step**: a workflow cannot be run locally, so the YAML is checked by
   the static test and proven on the first real push to `main` after merge.
4. Update `AGENTS.md`, the charter, `docs/landscape.md` and `CHANGELOG.md`; `python3
   validate.py` passes.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| One workflow-level `concurrency: release` group for every push | GitHub keeps one pending run per group and cancels the older pending one, so a branch push could cancel a queued `main` release. The group goes on the `release` job only. |
| `paths-ignore: ["handbook/**", "docs/**"]` on the trigger | Paths say nothing about intent: a `fix` can touch only docs (the installed handbook ships from `template/`), and a `chore` can touch code. The commit type is the signal the kit already uses. |
| Keep `release.yml` and push the tag with a PAT so it runs | Adds a long-lived secret to the repository for no gain; `version.yml` already publishes the release. |
| Rebase onto `origin/main` and release in the same run | The release would cover commits this run never smoke-tested. The newer push's run is already queued in the `release` group and tests the newer tree, so exiting costs only a short delay (design review). |

## Affected surfaces

- **Code:** `tools/semver.py` (repository tool, also called by `install.py`
  `display_version()`, which already treats level `none` as "no unreleased commits").
- **Data:** none.
- **Contracts:** `semver.py next --json` keeps its keys; only the `level` value for
  non-release commits changes from `patch` to `none`. The installer banner stops saying
  "N unreleased commits" for a docs-only checkout.
- **Docs to update:** `handbook/project/charter.md`, `AGENTS.md` section 9,
  `docs/landscape.md`, `CHANGELOG.md`.

## Failure modes

- **Human push during the smoke suite.** `origin/main` no longer equals `GITHUB_SHA`, so
  this run exits 0 and the queued run releases. `--atomic` push fails cleanly if a push
  lands between fetch and push; the next run on `main` then releases.
- **Two `main` runs queued.** The `release` group runs them one at a time; a pending run is
  replaced by a newer one, which still sees every commit since `VERSION` changed, so no
  commit goes unreleased.
- **Tag exists but `VERSION` is behind** (a half-finished earlier release). The guard stops
  before commit and push, and the error names the tag.
- **Force-push to `main`.** `origin/main` differs from `GITHUB_SHA`, so this run releases
  nothing and the run for the forced push decides.
- **Hostile commit text.** Subjects and bodies are only matched with regexes and written to
  `CHANGELOG.md` as today; no commit text reaches a shell. The workflow passes `level` and
  `next` between jobs as outputs, and both are checked against `none|patch|minor|major` and
  `^[0-9]+\.[0-9]+\.[0-9]+$` before use.

## Test strategy

- **Acceptance criteria mapping:** each Outcome clause maps to a check below.
- **Unit** (`tests/smoke.py` `test_semver`, loading `tools/semver.py` with `importlib`):
  - `level_of("docs: x", "")`, `"chore(deps): x"`, `"test: x"`, `"ci: x"`, `"build: x"`
    are `none`; `"Update README"` (non-conventional) is `none`.
  - `"fix: x"`, `"perf: x"`, `"refactor: x"`, `"revert: x"` are `patch`; `"feat: x"` and
    `"docs,feat: x"` are `minor`; `"docs!: x"` is `major`.
  - `level_of("chore: x", "Body.\n\nBREAKING CHANGE: drops y")` is `major`, and so is a
    non-conventional subject with that footer.
  - `level_of("fix: x", "The spec says\nBREAKING CHANGE: means major\nin prose.\n\nRefs: #1")`
    is `patch` (not in the footer), and `"> BREAKING CHANGE: quoted"` in the footer is not
    breaking.
- **Integration** (`test_semver`, after the existing release commit at line 3815): commit
  `docs(x): only docs`, `chore(y): tidy` and `Update notes`; `next` stays `5.0.0`,
  `next --json` has level `none`, `bump` prints "nothing to release" and leaves `VERSION`
  at `5.0.0`; the installer banner shows `5.0.0` alone. The existing feat/fix commits that
  follow still give a minor.
- **Static workflow check** (new `test_release_workflow` in `tests/smoke.py`, appended to the
  tuple in `main()`): `.github/workflows/release.yml` does not exist; `version.yml`
  contains `group: release`, `cancel-in-progress: false`, `needs.plan.outputs.level !=
  'none'`, a `GITHUB_SHA` comparison with `origin/main` and no `git rebase`,
  `github-actions[bot]` in the skip guard, a tag-exists check before `git commit`, and
  `--atomic`; no tracked file names `release.yml` except the records that keep history
  (`handbook/project/**` other than `charter.md`, `CHANGELOG.md`, `docs/landscape.md`).
- **Negative cases:** a docs-only push is refused a release; an existing tag stops the run;
  a quoted or mid-body `BREAKING CHANGE:` is refused a major.
- **Manual:** the first push to `main` after merge: a docs-only commit shows the `release`
  job skipped; a `fix` commit releases one patch.
- **Proof:**
  `python3 -c "import sys;sys.argv=['x'];sys.path.insert(0,'tests');import smoke;smoke.test_semver();print(smoke.failures)"`,
  the same for `smoke.test_release_workflow()`, and `python3 validate.py`.

## Risks

- **Untested YAML.** Actions cannot run locally. The static test guards the shape; the
  first real run on `main` is the proof, and a broken workflow releases nothing rather than
  something wrong.
- **Delayed release.** When `main` moves during a run, the release waits for the queued
  run's smoke suite. That is the price of releasing only tested trees.
- **Fewer releases.** `chore` and `build` no longer release. A `chore` that changes shipped
  files must be typed `fix` or `refactor`; this goes in the CHANGELOG bullet.
- **Governance text.** Changing AGENTS.md section 9 and deleting `release.yml` are
  owner-approval actions; the owner directed both on 2026-11-22, and the merge to `main`
  stays a human step.

## Rollback

Revert the commit. `release.yml` comes back unchanged and `version.yml` returns to
releasing on every push. No tag or `VERSION` change is made by this item itself.

## Out of scope

- Moving the smoke suite out of the release job (it stays as the release gate).
- Signing tags or release artifacts.
- Changing how `CHANGELOG.md` sections are written.

## Assumptions

- `revert` releases a patch: reverting a shipped `feat` or `fix` changes what users get.
- `build` and `style` are non-release types alongside `docs`, `chore`, `test` and `ci`.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| A11/S12 | Rebase releases an untested tree | Fix | Step 2 exits 0 when `origin/main` moved; rebase removed |
| A11 | Release types ambiguous (`revert`) | Fix | `RELEASE_TYPES` in this plan is the one list: feat minor; fix, perf, refactor, revert patch; `test_semver` has a `revert` case |
| S12 | Skip guard reads only the message | Fix | Guard also checks `github.actor == 'github-actions[bot]'` |

## Review


| Role | Verdict | Notes |
| --- | --- | --- |
| devops-sre | _pending_ | |
| security | _pending_ | |

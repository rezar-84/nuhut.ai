---
status: draft
owner: devops-sre
last-reviewed: 2026-11-22
---

# Plan: NUHT-022 ci-check: PR enforcement of trailers, ledger evidence, review file and tier floor

**Tier:** 1 **Effort:** Normal **Depends on:** NUHT-012 (shared `verify_state` and
`trusted_text`), NUHT-021 (command table)

## Problem

Every rule the kit has about a change is checked locally, and only if the agent runs the
check. The commit hooks can be skipped with `--no-verify`, a Tier 1 item can merge without a
review file, and a change to `.github/workflows/` can be declared Tier 3. The scaffolded CI
does not catch any of this. `install.py` `ci_text()` (line 4160) emits a GitHub workflow
whose only trigger is `workflow_dispatch`, and the comment it writes says "Manual-only by
default". `docs/landscape.md` line 48 records the gap: "No PR or CI enforcement; the
scaffolded workflow only runs by hand". A reviewer who reads a PR has nothing mechanical to
say that the record behind it exists.

## Outcome

`sdlc.py ci-check [--base <ref>] [--head <ref>|event] [--charter-ref <ref>] [--json]`
exits 1 on a PR range that contains any of these:

- a commit, merge commits included, without a `Work-Item` trailer, or without both
  `Agent` and `Model` unless it says `Agent: human`, or with the literal value `unknown`
- an item whose ledger record does not satisfy `finish.verify_state` (full and current,
  the same rule `finish` applies)
- a Tier 1 item with no review file
- a commit whose changed paths match a Tier 1 glob while its item is declared Tier 2 or 3
- an item whose tier is lower than in the base branch's backlog

It exits 0 on a clean range and 2 on a usage error. `install.py --scaffold-ci github`
writes a `quality.yml` that runs on `pull_request` as well as `workflow_dispatch`, and
runs `doctor --strict` and `ci-check`. It also writes `.github/pull_request_template.md`.

## Approach

- **Range.** Resolve `--base`. The default is the charter's Default branch through
  `default_branch()` (sdlc.py line 2511), else `main`. A value starting with `-` is refused,
  as `plan_check()` already does at line 2650. `merge_base = git merge-base <base> HEAD`;
  an empty result exits 2 and says the clone is shallow, so use `fetch-depth: 0`. The head
  comes from `--head` (default `HEAD`). `--head event` reads `pull_request.head.sha` from
  the JSON file at `$GITHUB_EVENT_PATH`, so the workflow needs no GitHub expression and
  the generated file stays free of doubled braces. With the real PR head, GitHub's
  synthetic merge commit is never in range. Commits come from
  `git log --format=%H%x01%P%x01%B%x00 <merge_base>..<head>`, merge commits included.
  They are parsed with the existing `trailers()` (line 1501), not `_parsed_commits()`,
  which reads `--all`.
- **Trailer check.** Each commit in the range must have a non-empty `Work-Item`, and
  either both `Agent` and `Model` or `Agent: human` (then `Model` is not required). The
  literal value `unknown` fails with the fix "set AI_SDLC_AGENT or use Agent: human".
  Commits whose author name is in a documented bot allow-list (`dependabot[bot]`,
  `github-actions[bot]`) are exempt from this check only; their paths still go through
  the tier floor as unattributed, so a bot commit touching a Tier 1 glob fails. A failure
  names the short sha, the subject and the missing keys, and points to
  `sdlc.py trailers <ID>`.
  - `sdlc.py trailers <ID>` prints `Agent: human` and no Model line when `identity()`
    detects no agent, instead of `unknown`.
  - The convention goes in `template/docs/process/05-change-control.md` and its handbook
    copy.
- **Ledger check.** Items in the range are the set of `Work-Item` values. For each one,
  `finish.verify_state` (from NUHT-012) is called, and only its full-and-current result
  passes; `partial` and `stale` fail with NUHT-012's messages. `ci-check` and `finish`
  therefore share one rule and cannot drift. Waived rows never count. The finding text
  says it checks the record, not the result: "no committed verify record for <ID> on its
  newest code commit". The fix printed is `sdlc.py verify --item <ID>` and then a commit
  of the ledger. The generated workflow also runs the charter's check commands itself
  (`ci_text()` already emits one step per command), so the result is regenerated in CI
  and the ledger check only proves the record was kept. Items at Tier 3 under Standard tier rules (`tier_rules()`, line 727) owe no
  verify, as in `required_steps()` (line 748), so they are skipped. This keeps
  `finish` and `ci-check` in agreement.
- **Review check.** For items at Tier 1 according to `item_tier()` (line 1700),
  `review_records()` (line 1923) must return at least one file. The fix printed is
  `/sdlc-review <ID>` or `sdlc.py review <ID> --role <role> --by <tool>`.
- **Tier floor.** The globs are the backticked path globs in the existing charter row
  **Always Tier 1 here** (prose in the row stays as advice for reviewers). The row is
  read from `--charter-ref` (the base branch in CI) through NUHT-012's `trusted_text`, so
  a PR cannot weaken the row it is judged by. Globs are matched with `glob_regex()`
  (line 2491). When the row has no backticked glob, the defaults are `auth/**`,
  `migrations/**`, `.github/workflows/**`, `infra/**` and `.ai-sdlc/**`, each matched at
  any depth (`**/auth/**`), plus `<docs>/project/people.json`. The defaults always also
  include the kit's own enforcement surfaces (`.ai-sdlc/**`, `.github/workflows/**`,
  `people.json`), even when the row lists globs. `<docs>/project/charter.md` counts as a
  Tier 1 path only when a security-bearing row (Approvers, Always Tier 1 here,
  Extensions allowed, Notify webhook, Tier rules, Independent review required for)
  differs between the base and the commit, so a `last-reviewed` bump stays Tier 2. For
  each commit, `git diff-tree --no-commit-id --name-only -r <sha>` gives its files; for a
  merge commit it is `git diff --name-only <first-parent> <merge>`, so content added by
  the merge itself is judged.
- **Tier lowering.** For each item in the range, the tier in the base branch's backlog
  (`git show <base>:<docs>/project/items/<ID>.json`, or the backlog row) is compared with
  the head's. A lower tier at head fails, naming both. A match while that commit's item is at Tier 2 or 3 fails, naming the path, the
  glob and the item. An item with no readable tier (no backlog row) is a separate
  failure, "unknown item", because it cannot be judged.
- **Output.** One line per finding in the style of `print_plan_precheck()`, for example
  `fail  trailers  ab12cd3 "fix: x"  missing Agent, Model`, then a summary line. `--json`
  prints `{"base", "merge_base", "commits", "items", "findings": [{"check", "item", "sha",
  "detail", "fix"}]}`.
- **Wiring.** Add a `ci-check` subparser beside `plan-check` (line 3818) with `--base` and
  `--json`. Add a dispatch branch beside line 4611, a help row in the command table near
  line 3696, and examples in the table at line 3725. Then copy `sdlc.py` byte-identical to
  `.ai-sdlc/bin/sdlc.py`. No new runtime file, so `RUNTIME_FILES` (install.py line 75) does
  not change.
- **Installer.** `ci_text("github")` (install.py line 4160):
  - Triggers: `on:` gains `pull_request:` beside `workflow_dispatch:`. It is never
    `pull_request_target`, so a fork PR gets no secrets and only `contents: read`.
  - Checkout: `actions/checkout@v4` gets `with: fetch-depth: 0`.
  - Steps: `doctor --strict` is followed by a `PR records` step, guarded by
    `if: github.event_name == 'pull_request'`. It runs the base branch's checker, not the
    PR's:
    `git archive "origin/$GITHUB_BASE_REF" .ai-sdlc/bin | tar -x -C "$RUNNER_TEMP/base"`,
    then `python3 "$RUNNER_TEMP/base/.ai-sdlc/bin/sdlc.py" --root "$GITHUB_WORKSPACE"
    ci-check --base "origin/$GITHUB_BASE_REF" --head event --charter-ref
    "origin/$GITHUB_BASE_REF"`. When the base has no `.ai-sdlc/bin/sdlc.py` (the PR that
    installs the kit), it runs the head copy and prints a warning saying so. The base and
    head come from environment variables and the event file, so the text has no
    doubled-brace expression.
  - The closing comment changes to say the PR trigger is on, why the commands must still
    be confirmed, and that the check binds only with branch protection that requires the
    `quality` status and CODEOWNERS on `.github/workflows/**` and `.ai-sdlc/**`.
    `docs/install.md` says the same.

  The GitLab output is unchanged. `scaffold()` (line 4186) also calls `install_text()`
  for `.github/pull_request_template.md` from a new `pr_template_text()`, which gives
  Work-Item, Tier, verify evidence, review file and plan link, plus a checklist that names
  `ci-check`. `install_text()` never overwrites (line 3466). The candidates list at line
  3531 gains the template path, so `ensure_inside` and `--dry-run` cover it.
- **Charter.** No new row. The hint of **Always Tier 1 here** in
  `template/docs/project/charter.md` (line 257) becomes "(surfaces, and backticked path
  globs such as `infra/**` that ci-check enforces)". `handbook/project/charter.md`
  (line 171) gains backticked globs for this repository's own surfaces:
  `optional/runtime/hooks.py` and `.github/workflows/**`.

## Files that change

- `optional/runtime/sdlc.py`
- `.ai-sdlc/bin/sdlc.py`
- `install.py`
- `tests/smoke.py`
- `template/docs/project/charter.md`
- `handbook/project/charter.md`
- `template/docs/process/05-change-control.md`
- `handbook/process/05-change-control.md`
- `docs/cli.md`
- `README.md`
- `docs/install.md`
- `docs/runtime.md`
- `docs/harnesses.md`
- `CHANGELOG.md`

## Order of work

1. Write `test_ci_check()` in `tests/smoke.py` and flip the `"  pull_request:" not in
   workflow` assertion in `test_scaffolding()` (line 2337). Run both and see them fail.
2. Write `ci_check()` and `print_ci_check()` in `sdlc.py`, then the subparser and the
   dispatch. This is the riskiest step: the range and merge-base handling and the
   per-commit tier attribution.
3. Change `ci_text()`, add `pr_template_text()` and extend `scaffold()` and the candidates
   list in `install.py`.
4. Charter rows, process doc, CLI docs, README, CHANGELOG. Copy to `.ai-sdlc/bin/`. Run
   `validate.py`.

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Make `doctor --strict` do these checks | Doctor audits the whole record set with no notion of a PR range. Mixing the two would make doctor's result depend on which branch CI compares against. |
| A GitHub Action in its own repository | It adds a dependency outside the kit and leaves GitLab and local runs without the check. A stdlib subcommand runs anywhere. |
| `pull_request_target` so the check can post comments | It runs with write tokens on fork code. A failing job with readable output is enough. |
| Tier floor judged on the whole PR diff | One Tier 1 item in a PR would let a Tier 3 commit through, or one Tier 3 item would wrongly fail an unrelated Tier 1 commit. Per-commit attribution names the actual offender. |

## Affected surfaces

- **Code:** `sdlc.py` gains a subcommand, and `install.py` scaffolding changes.
- **Data:** none. The check only reads the ledger, the reviews and the backlog.
- **Contracts:** the new `ci-check` CLI and its JSON shape. The scaffolded workflow now
  triggers on PRs, which changes the meaning of the existing `--scaffold-ci github` flag
  for new scaffolds. Existing `quality.yml` files are never rewritten.
- **Docs to update:** `docs/cli.md`, `README.md`, `docs/install.md` ("Generated jobs are
  manual-only"), `docs/runtime.md` (lines 84-85), `docs/harnesses.md` (line 27), the
  change-control process doc, and the charter template.

## Failure modes

- **Shallow clone.** The merge-base is empty, so exit 2 with the `fetch-depth: 0` fix.
  The check never passes silently on an empty range it could not compute.
- **Empty range** (the branch equals the base). Print "no commits since <base>" and exit 0.
- **Hostile commit messages.** Bodies are only parsed by regex and never executed.
  Trailer values are printed raw, so control characters are stripped before printing to
  keep terminal escapes out of CI logs.
- **Hostile `--base`.** A leading `-` is refused. The value is passed to git as an argv
  element, never through a shell.
- **Rebased or squashed PR.** Ledger rows keep the old shas, and the ledger check fails
  with a "re-run verify on the rebased commits" hint. This is intended: the evidence
  then really is for different code.
- **Ledger written after the last commit.** The row exists only once it is committed.
  The message says to commit the ledger.
- **Unknown Work-Item** (an item not in the backlog). Reported as `unknown item`, never
  treated as Tier 3.

## Tests (written first)

- **Acceptance criteria mapping:** one fixture per Outcome bullet in `test_ci_check()`.
  It uses a temp git repo with an installed kit, a `main` base and a feature branch.
- **Clean range passes.** A Tier 2 item with trailers on every commit and a clean ledger
  row on its commit exits 0.
- **Negative cases (required for Tier 1):**
  - A commit without `Model` exits 1, and the output names the sha and `Model`.
  - The item has no ledger row for any commit in the range: exit 1, naming `verify --item`.
  - A waived ledger row does not count.
  - A Tier 1 item with no `reviews/<ID>-*.md` exits 1. Adding the file clears it.
  - A Tier 3 commit touching `infra/main.tf` exits 1 with the default globs. The same
    with backticked `deploy/**` in **Always Tier 1 here** passes, and touching
    `deploy/x` fails. Touching `.ai-sdlc/bin/sdlc.py` under Tier 3 fails either way.
  - `--base -x` exits 2. A base that is not a ref exits 2.
  - A merge commit with no trailers in the range fails the trailer check.
  - A merge commit that adds `infra/x.tf` under a Tier 3 item fails the tier floor.
  - A commit with `Agent: human` and no Model passes; `Agent: unknown` fails with the
    `AI_SDLC_AGENT` fix.
  - A PR that removes the globs from **Always Tier 1 here** and touches `infra/x` under
    Tier 3 still fails, because the row is read from `--charter-ref`.
  - A PR that lowers an item from Tier 1 to Tier 3 fails.
  - A ledger record that is partial or stale fails with the same message `finish` gives.
  - `--head event` with a fixture `GITHUB_EVENT_PATH` reads the head sha.
- **Scaffold:** `test_scaffolding()` asserts `pull_request:` and `workflow_dispatch:` are
  both in `quality.yml`, along with `fetch-depth: 0`. It also asserts that `ci-check` comes
  after `doctor --strict`, that it runs from `$RUNNER_TEMP/base` with `--charter-ref`,
  that there is no doubled `{` in the file, that
  `.github/pull_request_template.md` exists and names `ci-check`, and that the dry run
  still writes nothing.
- **Manual:** read the scaffolded workflow once, checking it is valid YAML and that the
  PR step's `if:` guard is right.
- **Proof:** these commands:
  - `python3 -c "import sys;sys.argv=['x'];sys.path.insert(0,'tests');import smoke;smoke.test_ci_check();print(smoke.failures)"`
  - the same for `test_scaffolding`
  - `python3 validate.py`
  - `python3 .ai-sdlc/bin/sdlc.py ci-check --base main` on this branch

## Risks

- **False failures on existing projects.** History before 4.0 has no trailers. The check
  only reads the PR range, so it applies to new commits only.
- **Brace rule.** Neither `sdlc.py` nor the generated workflow may carry literal doubled
  curly braces. The workflow reads `$GITHUB_BASE_REF` and does not use a GitHub
  expression, and the test asserts this.
- **Charter budget.** No new row; the hint change adds a few words. Check with
  `python3 validate.py --reading-lists`.
- **Governance gate.** Adding a CI gate changes Tier 1 governance (AGENTS.md section 9).
  It needs the human approvals at ship.

## Rollback

Revert the commit. `ci-check` is additive. A project already scaffolded keeps its
`quality.yml`, and its owner deletes the `PR records` step or the `pull_request:` trigger
to turn the check off. Nothing has been rolled back yet.

## Out of scope

- A GitLab merge-request trigger and a `ci-check` step for `.gitlab-ci.yml`. These are
  left manual and could be a follow-up.
- GitHub approvals or required-reviewer enforcement (a later v6 item, NUHT-022 to NUHT-029
  range).
- Posting PR comments or status checks through the API.

## Assumptions

- PR CI checks out a full clone (`fetch-depth: 0`), with the base branch available as
  `origin/<base>`.
- Ledger rows and review files are committed on the PR branch before CI runs.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| A4 | Ledger rule differs from finish | Fix | Ledger check calls `finish.verify_state`; depends on NUHT-012 |
| A5/S3 | PR runs its own checker and charter | Fix | Base-ref checker via `git archive`; `--charter-ref` |
| S3 | Ledger is self-attested | Fix | Message says it checks the record; the charter commands already run as workflow steps; branch protection and CODEOWNERS documented |
| S4 | `--no-merges` and `diff-tree` skip merges | Fix, adapted | `--head event` reads the PR head from `$GITHUB_EVENT_PATH` instead of a `pull_request.head.sha` expression, which would put doubled braces in the generated file |
| U3 | Humans cannot pass the trailer check | Fix | `Agent: human`; `unknown` rejected; bot allow-list for trailers only |
| U4 | Duplicate `Tier 1 paths` row | Fix | Row dropped; globs read from **Always Tier 1 here** |
| S2 | `charter.md` as a default Tier 1 path | Fix, narrowed | Only a change to a security-bearing row counts, so routine charter edits stay Tier 2 |

## Review


| Role | Verdict | Notes |
| --- | --- | --- |
| devops-sre | _(pending)_ | |
| security | _(pending)_ | |

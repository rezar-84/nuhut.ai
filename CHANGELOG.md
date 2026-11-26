# Changelog

This project follows semantic versioning. User-visible changes are recorded here.

## Unreleased

### Upgrading to 6.0

- **Commits are attributed by trailer only.** Items committed without a `Work-Item:` trailer lose their commits; `doctor` reports how many. Fix: commit further work with the trailer (`sdlc.py trailers <ID>`).
- **Only an approver can waive verify.** `finish --waive verify --by <name>` must name someone in the charter's **Approvers** row on the default branch. Fix: list the people who may waive there and merge it.
- **A placeholder Approvers row refuses every waiver.** Fix: fill the row; `--upgrade` prints a notice while it is blank.
- **`sdlc.py trailers` prints `Agent: human` and no Model when it detects no agent**, instead of `unknown`, which `ci-check` rejects. Fix: set `AI_SDLC_AGENT` in an agent's environment, or keep `Agent: human` for commits a person makes.
- **Agents can no longer edit the kit's code, wiring or evidence.** The trust anchors now also cover `.ai-sdlc/bin/**` (outside the kit's own repository), `.ai-sdlc/profile.json`, `.ai-sdlc/git-hooks/**`, `.claude/settings.json`, `.gemini/settings.json`, `.cursor/hooks.json`, the evidence ledger and its shards. Fix: make those changes yourself, or through `install.py --upgrade`, `sdlc.py verify` and `finish`, which write them as before.
- **An agent's session cannot waive verify, or use a recorded waiver, without a terminal**, even when `NUHUT_USER` or `git user.name` is the approver's. Fix: the approver runs `finish <ID> --waive verify --by <name> --reason ...` in their own terminal.
- **`ext update` asks before re-pinning changed code of an allowed extension**, and without a terminal refuses unless given `--yes`. Fix: add `--yes` to scripts that update extensions.
- **A GitHub review counts toward Tier 1 only from someone in Approvers (ship review finding 18).** Before, any reviewer that `people.json` mapped, other than the PR author, counted. Fix: list everyone whose approval should count in the charter's **Approvers** row on the default branch.
- **Changes to the other hosts' CI files are Tier 1 (NUHT-044).** `ci-check` fails a Tier 2 or 3 item that changes `.gitea/workflows/**`, `.forgejo/workflows/**`, `.gitlab-ci.yml`, `bitbucket-pipelines.yml`, `azure-pipelines.yml`, `Jenkinsfile` or `ci/nuhut-check.sh`, as it already did for `.github/workflows/**`. Fix: raise the item to Tier 1.
- **The first upgrade PR from 5.x no longer fails with a usage error.** The scaffolded CI runs the target branch's `ci-check`; a 5.x target branch has none, so the job now runs the PR's own copy with a warning when the target has no kit or one whose `--help` names no `ci-check`. Any other failure (the archive cannot be extracted, the target's checker crashes) fails the job instead of falling back. Fix for CI files scaffolded by an earlier 6.0 build: run `install.sh <project> --scaffold-ci <host>` again.
- **`--git-hooks` pre-commit applies `.ai-sdlc/protected.txt` only to commits made from an agent's session**, as in 5.x where the list bound only agent edits; `test-lock.txt` still binds every committer. A person who regenerates `package-lock.json` or a `**/generated/**` file commits it as before.

- **How many approvers Tier 1 needs is a charter row (NUHT-043).** The new **Tier 1 approvals** row is `2` (the default when the row is missing) or `1` for a one-person project, and is read from the default branch, so a branch that lowers it gains nothing until it merges. New `sdlc.py approve <ID> --by <handle>`, off unless the charter's new **Local approvals** row is `on` on the default branch: an approver from **Approvers** approves what is checked out (HEAD, which must contain the item's newest commit) in their own terminal; an agent's session without one is refused, as for verify waivers. It is kept in the shard's `local_approvals` and counts in `approvals` and `finish` as `source: local` while only bookkeeping (item shards, the ledger, worklog and backlog renders, release records) has changed since the approved commit; a change to the charter, `people.json`, a review or code voids it. It is an unsigned record, which is why it is opt-in. A GitHub review now counts only from someone in Approvers (`not-an-approver` otherwise). When the count is out of reach, `approvals` says how a solo project sets the row.
- **An agent cannot lower a blocking severity on its own word (NUHT-041).** `item set <ID> --severity` that lowers an S0, S1 or S2 from an agent's session without a terminal is refused unless the item has a blind re-rating from the new `sdlc.py rerate <ID> --by <agent>`, taken at its current severity by an agent of another model family, and no re-rating at that severity rates it more severe than the new value. `rerate` sends the severity ladder and the defect report with every severity removed, marked as untrusted data, and records a hash of the severity ladder (read from the default branch), title, touch paths and report; a re-rating counts only while that hash is unchanged. It saves `reviews/<ID>-severity[-n].md` and appends to the shard's `severity_reviews`; a `cmd:` reviewer is recorded, never counted. A person at a terminal may lower it. Every change is kept in `severity_history` with `how` (`free`, `person`, `re-rated`) and `--severity-reason`.
- **Open S0 and S1 defects block a release (NUHT-041).** `deploy record` refuses while an open defect is S0 or S1, unless this deploy's range (from the last deploy to the deployed commit) has a fix for it: a commit whose trailer block (as git parses it, not a line in the body) has the defect's `Work-Item:` and that changes a file outside the docs folder; once the fix ships, close the defect, or the next deploy blocks again. These cannot be accepted. An open S2 is refused unless an approver accepts it with `--accept-defects <ID> --by <approver> --reason "..."`, checked like a verify waiver, and the release record keeps `accepted_defects`. `--dry-run` reports the same refusal.
- **Agents are told about open defects (NUHT-040).** New `sdlc.py bug "<title>" --severity S0..S4 [--touch] [--repro] [--found-by]` adds a `defect` item owned by `qa` and writes `docs/project/defects/<ID>.md` from the defect-report template with its header and steps filled in; the status follows the charter's **Discovered defects** row. Item shards gain optional `severity` and `found_by` fields (`item add|set --severity`, `--found-by`). `render` rebuilds the Index table in `docs/project/defects/README.md` from the defect items and keeps rows for IDs that are not items. `status` lists open S0–S2 defects; `guard start` (the Claude Code SessionStart hook) prints them on stdout, so the agent reads them as context; `claim` warns when the claimed item's `touch` paths overlap an open defect's.
- **`view --serve --host` reaches the live page from another machine (NUHT-037).** `--host tailscale` binds this machine's Tailscale IPv4 (from `tailscale ip -4`); `--host <ip>` or `0.0.0.0` binds that, with a warning that traffic is plain HTTP outside `100.64.0.0/10`. Off loopback, each start prints `http://<addr>:<port>/?k=<key>` with a fresh random key that is never written to a file; every request needs the key or the HttpOnly, SameSite=Strict cookie a valid `?k=` sets (then a redirect drops it from the address bar), and any Host header is accepted so `tailscale serve` and reverse proxies work. The page is read-only there: POST endpoints answer `403` and the page shows copyable commands, unless `--allow-actions` is given, which still needs the session cookie and an Origin matching the request's Host. The default, `127.0.0.1`, behaves as before. `--host` and `--allow-actions` without `--serve` are an error.
- **Fixes from the 6.0 ship review (NUHT-016 review).** The trusted ref that Approvers, `people.json`, Extensions allowed and Notify webhook are read from now comes from `origin/HEAD` (followed to the branch its own charter names), then `$GITHUB_BASE_REF`, and only then the working tree's Default branch row, so a branch can no longer name itself the default branch (NUHT-012). Trusted records are read with `git show <ref>:./<path>`, so a kit installed in a subdirectory of a repository reads them (NUHT-022). Project-extension code loads only while its hashes match the pins on the default branch as well as in the working tree (NUHT-018). `trailers()` joins an earlier trailer paragraph only when the last one has no Work-Item, Agent or Model, so a body line such as `Agent: x` no longer becomes a trailer; `doctor` flags a Verified worklog entry for an item whose commits mention it without a `Work-Item:` trailer; the commit-msg hook asks for the trailer and warns when a message it accepts will not be attributed (NUHT-012). The shell guard treats `node`/`ruby`/`perl`/`php -e`, interpreters and shells reading stdin or a heredoc, `awk`, `git apply` and `patch` as inline code, and sees `rsync`, `tar -C` and `unzip -d` destinations (NUHT-013). `trailers` warns on stderr when it prints `Model: unknown`. `release --json` carries its deprecation note in the JSON instead of on stderr (NUHT-021). `approvals` needs no approval outside Tier 1 and Strict Tier 2 and exits 0 (NUHT-024). A non-UTF-8 `.gitattributes` no longer aborts the install (NUHT-027). A claim that cannot take the port lock is refused instead of allocating a port unlocked (NUHT-032), and claim refuses to create an empty worktree before the first commit, which `status` now reports with the branch name (NUHT-026). `status` reports the identity gap `claim` warns about, and that warning names `<docs>/project/people.json` (NUHT-023). `issues pull` links an item by title only for an issue whose author `people.json` maps, and marks other imported titles untrusted (NUHT-030). `ext search` says when the catalog is empty and names `NUHUT_CATALOG_URL` and `ext add` on a fetch error; `sdlc.py --help` lists `ext` and prints extension commands before its footer (NUHT-018). `--scaffold-ci` with no detected commands writes the `doctor` and `ci-check` steps and a TODO instead of aborting. `hotfix` and `unclaim` name the item a mis-padded ID probably means (`DEMO-1` for `DEMO-001`). The `upgrade` note about a blank Approvers row no longer names the charter path, and a same-version refresh names its backup folder by time. `docs/cli.md` lists `ext`, `dispatch` and `merge-shard` in its groups and every registry agent for `--by`.
- **`BREAKING CHANGE:` is found again when a trailer paragraph follows it (NUHT-014).** `tools/semver.py` reads the footer as the trailing run of paragraphs made only of `Token: value` lines, not just the last paragraph, so a `Co-Authored-By:` paragraph after the footer no longer turns a major into a minor. `validate.py` fails when the Unreleased section says "Upgrading to N.0" but the computed next release is not N.0.0, and when an example range in `docs/extensions.md` or ADR 0003 refuses the next release.
- **GitHub issue sync, and extension commands that run (NUHT-030).** `sdlc.py` now loads the `commands` entry points of extensions into its command table: a record `{"id": "<name>", "file": "<file>.py"}` gives one name, and the file's `register(add, runtime)` adds a plain command or verbs under it. These files load only when the command line names something other than a core command, a project extension's commands load only when **Extensions allowed** lists it and its pins match, and a record named like a core command is ignored with a warning. The new `github-issues` built-in extension uses this for `sdlc.py issues pull` and `issues push`, through `gh`. `pull` reads `gh issue list --json number,title,labels,url` and parks each issue that no item maps to as a new Parked item that waits on the backlog owner, or links the item an issue's `<ID>: ...` title names. It never reads issue bodies and reduces titles to one plain line. `push <ID>...|--all` opens issues titled `<ID>: <title>` whose body holds only the ID, type, tier and status. Item shards gain an optional `issue` field that `item set` keeps and the shard merge driver treats as a conflict field. `--dry-run` and `--json` on both. `docs/extensions.md` documents the extension and plans Linear and Jira as later extensions.
- **Webhook notifications (NUHT-034).** The charter's optional **Notify webhook** row names an environment variable (`^NUHUT_[A-Z0-9_]{1,40}$`, e.g. `NUHUT_WEBHOOK_URL`) that holds the URL, never the URL itself; it is read from the default branch and is off by default. `sdlc.py config --notify-webhook <NAME>|off` writes it. An item set to Parked, a `finish` refused by an escalated review finding, and a `finish` that parks a Tier 1 item (or Strict Tier 2) for approval POST a small JSON payload (IDs, title, tier, status; no diff) through `net.py`, which gains `post_json`: https only (http only to 127.0.0.1 or localhost under `NUHUT_ALLOW_HTTP=1`), no scheme or host change on redirect, 5 s timeout, the response ignored, and errors that name only scheme and host. A failure warns and never blocks. `--ids-only` in the row drops titles. New command `sdlc.py notify [--test] [--ids-only]` and runtime module `notify.py`.
- **`finish` binds verify evidence to the item (NUHT-012).** It passes Verify only on a full run (every charter stage with a command, no `--stage`) made clean on the item's newest code commit or a descendant of it, or dirty on that commit's parent. Records-only commits do not make a run stale, and uncommitted records or `.ai-sdlc/` state do not make a run dirty. A partial run and a stale run each get their own message. `verify --stage` rows record `selected`. `evidence_matches` no longer counts a tagged run on the tag alone: the run must be clean with one of the item's commits in its history, and the answer does not depend on HEAD. Commits are attributed only by the `Work-Item` trailer, which is now also read from a trailer paragraph followed by a separate `Co-Authored-By:` paragraph. A waiver must name an approver from the charter's Approvers row read from the default branch (new `trusted_text` helper), records `waived_as` (`NUHUT_USER`, else `git config user.name`), is refused with no terminal when that identity is not the approver, and stops counting when the approver leaves the row. `doctor` gains an info finding for items that lost commit attribution and warns on an approver that `people.json` does not know; its cache version is bumped.
- **OpenCode, Kiro and ACP agents are built-in extensions (NUHT-020).** New data-only manifests in `optional/extensions/opencode/`, `kiro/` and `acp/` (installed to `.ai-sdlc/extensions/`), each with `"nuhut": "builtin"` because their agents argv reaches a subprocess. `--harness opencode`, `kiro` and `acp` wire tools that read `AGENTS.md` and get the shared skills; all three declare `hooks.dialect: null`, so the installer prints "guards do not run for this tool" for each. `review --by opencode` and `dispatch` run `opencode run "<prompt>"`; `review --by kiro` runs `kiro-cli chat --no-interactive "<prompt>"` and build adds `--trust-all-tools`; the generic ACP record has no argv, so it is reviewed through `--by cmd:`. `sdlc.py lens` reads `.opencode/`, `.kiro/` and `.kiro/settings/mcp.json`. The opencode harness record moves out of `core` and is titled OpenCode. No installer or runtime code changed; `validate.py` and the v5 parity tests now compare `sdlc.py` `V5_AGENTS` with the v5 tools only. `docs/harnesses.md` documents the three tools.
- **Merge-time checks on any git host (NUHT-038).** One reader of CI context in `registry.py` (`ci_base`, `ci_head`) serves `ci-check` and the trusted ref. The target branch comes from `NUHUT_BASE`, then `GITHUB_BASE_REF` (GitHub, Gitea, Forgejo), `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` (GitLab), `BITBUCKET_PR_DESTINATION_BRANCH`, `SYSTEM_PULLREQUEST_TARGETBRANCH` (Azure Pipelines, `refs/heads/` removed) and `CHANGE_TARGET` (Jenkins multibranch); a value that is not a plain branch name is refused. `ci-check` with no `--base` now uses it before the charter's Default branch, and the new `--head env` reads `NUHUT_HEAD`, the GitHub event file, `CI_COMMIT_SHA` or `BITBUCKET_COMMIT`, else `HEAD`; `--head event` is unchanged. `install.py --scaffold-ci` gains `bitbucket` (`bitbucket-pipelines.yml`), `gitea` (`.gitea/workflows/nuhut.yml`) and `generic` (`ci/nuhut-check.sh`, for any other CI, given `NUHUT_BASE`), each running `doctor --strict` and the target branch's `ci-check` with full history; the `gitlab` file gains a `records` job that does the same on merge requests. The generated GitHub workflow is unchanged. `doctor` reports `enforcement: advisory` when the repository has no remote (info: local-only git is a choice) or has one but no recognised CI file runs `sdlc.py` (a warning), and `enforcement: CI (<provider>)` otherwise; its cache version is bumped.
- **`sdlc.py ci-check` judges a pull request (NUHT-022).** For the commits in `merge-base(base, head)..head`, merge commits included, it fails a commit without `Work-Item`, or without both `Agent` and `Model` unless it says `Agent: human`, or with the value `unknown` (`dependabot[bot]` and `github-actions[bot]` skip only this rule). It fails an item whose committed ledger record is not a full, current verify run (the rule `finish` applies, through `finish.verify_state`), a Tier 1 item with no review file, a commit whose paths match a Tier 1 glob while its item is Tier 2 or 3, and an item whose tier is lower than in the base branch's backlog. The Tier 1 globs are the backticked globs in the charter's **Always Tier 1 here** row, read at `--charter-ref` through `trusted_text`; with none, `auth/`, `migrations/` and `infra/` at any depth; `.ai-sdlc/**`, `.github/workflows/**` and `people.json` always, and the charter when a security-bearing row changes. `--head event` reads `pull_request.head.sha` from `$GITHUB_EVENT_PATH`; `--json` prints the result. `install.py --scaffold-ci github` now writes a workflow that runs on `pull_request` with `fetch-depth: 0`, runs `doctor --strict` and then the base branch's `ci-check` (the PR's own copy, with a warning, when the base has none), and writes `.github/pull_request_template.md`. The workflow comment and `docs/install.md` say the check binds only with branch protection requiring `quality` and CODEOWNERS on `.github/workflows/**` and `.ai-sdlc/**`. The charter's Always Tier 1 here hint names the globs, and `05-change-control.md` documents `Agent: human` and the tier floor.
- **Tier 1 approvals are read from GitHub PR reviews (NUHT-024).** `finish` (Tier 1, and Tier 2 under Strict tier rules) and the new read-only `sdlc.py approvals <ID> [--json]` read the item branch's pull request through `gh` (`--repo` from `gh repo view`). A review counts only when the PR is this repository's own, open or merged, with its head equal to the local item branch, and the reviewer's latest verdict is `APPROVED` on that head, from someone other than the PR author, not a bot, whose login `people.json` on the default branch maps to a handle. Tier 1 needs 2, Strict Tier 2 needs 1; with enough, `finish` moves the item (also an already Parked one) to Done and records `{handle, login, source: github, commit, at}` in the shard's `approvers`. Otherwise the item stays Parked, the charter's Approvers are recorded with `source: charter`, and the output names each ignored review and why. `AI_SDLC_APPROVAL` never counts. The Parked row's Waiting-on now reads `bob; approved: alice (github)`.
- **People registry (NUHT-023).** New `docs/project/people.json` (installed empty) lists people as `{handle, name, roles, github}` and is read from the default branch through `trusted_text`. `item add|set --owner` accepts a role slug or a registered person, stored as the handle; with a registry anything else is refused. A claim records `person` beside `agent` and `host`: `NUHUT_USER`, or `git config user.name` when the registry maps it. Otherwise it records `person: null`, never a guess, and warns once per process (`no person identity: ...`), inside the result with `--json`; under `CI=true` read-only lookups stay quiet. An unknown agent on `claim` is warned about too. `dispatch` records the person who started it on each worker claim. `claims` and the viewer show the person (*unknown person* when null), and the viewer shows a handle owner by name. `doctor` warns about open items owned by neither a role nor a handle (one line per owner), gives one count of claims without a person, and warns about an Approvers entry that is a name rather than a handle. New `handle_for_github()` maps a GitHub login to its handle. The charter's Approvers placeholder now asks for handles. `status` treats an empty registry as none. Doctor's cache version is bumped.
- **Gate fixes from the retro ship reviews (NUHT-061).** A failing run on the code being finished blocks `finish` even when an older full run passed. A PR with no readable author counts no GitHub review, and an unreadable tier needs Tier 1 approvals. Remaining findings are tracked in NUHT-062.
- **`review` reviews the item's own commits (NUHT-060).** Its diff ran from the item's first commit to its last, so other items' work committed in between went to the reviewer too, and a long branch made the prompt too long to pass to the reviewer CLI. It now joins the item's commits, oldest first.
- **Skills are checked to fire on the right prompts (NUHT-059).** `validate.py` scores 72 prompts in `tests/skill-routing.json` against the skill descriptions (word weighting and cosine similarity, stdlib only) and fails when a prompt picks the wrong skill or two descriptions nearly match. It found five descriptions missing the words people use; doctor, evidence-check, postmortem, service-contract and content-seo now carry them.
- **GitHub Actions are pinned to commit hashes (NUHT-046).** This repository's workflows and the scaffolded GitHub workflow run `actions/checkout` and `actions/setup-python` by commit hash with the version as a comment; `.github/dependabot.yml` keeps them current, and `validate.py` refuses an unpinned action here. The Gitea scaffold keeps `@v4`.
- **A fast run reports declared-absent stages as Absent (NUHT-058)**, not as "Not run (fast verify)".
- **`finish --commit` commits the item's records (NUHT-057).** The shard, worklog entry and ledger rows `finish` and `verify --item` leave go in one commit with the item's trailers, so there is no hand-written bookkeeping commit; other staged work stays out of it. `/sdlc-finish` uses it.
- **Guard hooks without the false alarms, and a switch for each (NUHT-055).** The work-item and credential checks on commits now run only as git hooks (`commit-msg`, `pre-commit`), which read the real message and the staged diff; `install.sh --hooks` installs them with the agent hooks, and `--upgrade` removes the old agent hooks that matched `git commit` in shell text and misfired on quoted text. The shell guards no longer refuse inline code (heredocs, `sh -c`, an interpreter's `-e`) that merely names a guarded path; the `pre-commit` check catches what it writes. New `sdlc.py hooks list|on|off <name>`: a person turns a hook off in a terminal (`.ai-sdlc/hooks-off.txt`), an agent's session cannot. The installer's hook help lists each hook, what it blocks and what it cannot see. With `--hooks`, every commit names its item, the first one included.
- **Fast verify (NUHT-053).** The charter's new **Verify at finish** row is `full` (the default, as before) or `fast: <stages>`, for example `fast: lint, unit, build`. It is read from the default branch. With `fast`, `verify --item` on a Tier 2 or 3 item runs only those stages, records the run as `mode: fast`, and `finish` and `ci-check` accept it; CI's job still runs every stage before merge. Tier 1 always runs every stage, and `verify --item <ID> --full` runs every stage for any item. For this to stop a failing change, the host must require the CI job.
- **A fresh install's first `doctor` run is shorter (NUHT-052).** It drops from 12 warnings to 8, each a decision a person still has to make. The installer dates the backlog, worklog and assumptions records it creates empty, as it already did for the generated test and eval plans, so they are no longer reported as never reviewed. The charter is not dated, because its rows wait for answers. Blank Commands rows are one finding, which names any commands the installer detected and `fix adopt-commands --apply`, instead of two.
- **The viewer suggests the same check command as `doctor` (NUHT-050).** Its repair panel guessed commands from a second scan of the repository, which could disagree with what the installer detected (`npm test` against `npm run test`). It now takes the installer's detection where there is one, and the scan, which uses the installer's command forms, only as a fallback.
- **Detected check commands are no longer lost after a `-y` install (NUHT-048).** The installer kept the commands it detected only in `.ai-sdlc/profile.json` and left the charter's Commands rows blank, so `verify` ran nothing, and `fix sync-profile` (also run by `fix all`) erased the detection. The charter still stays blank until a person decides, but `doctor` and `status` now name the detected commands, `sync-profile` keeps them, and the new `fix adopt-commands [--apply]` writes them into the blank rows. A row marked `absent` or filled in is never changed.
- **Built items are no longer offered as Ready to take (NUHT-047).** A Ready item whose own `Work-Item` commits already change a path outside `docs/project/` was listed by `status` and scheduled by `parallel` and `dispatch` as if it had not been built, inviting a second build. `status` now lists it under **Built, not finished** with `finish <ID> --dry-run` as the next step, and `parallel --json` reports it under `built`. A commit that only touches records, such as its plan, does not count.
- **`sdlc.py status` says what to do next.** One read-only screen for this branch and person: the setup this clone is missing, with a fix for each (an unconfigured merge driver, an identity `people.json` does not know, `gh` missing or logged out while Tier 1 items are open); your claimed items and the next step each owes, by the rules `finish --dry-run` applies; items Parked on you; Ready items you could take; and the doctor finding count. `--json` prints the same. It is listed first in `sdlc.py --help` under *Start here*. There is no `next` alias, so it cannot be confused with `next-id`. New: `docs/joining.md`, a checklist for joining a project that already has the kit (NUHT-026).
- **Hotfix fast path.** `sdlc.py item set <ID> --hotfix`, or its shortcut `sdlc.py hotfix <ID>`, marks an item a hotfix: the tier stays, and the item records `hotfix: true` and the time. `finish` then closes it without the pre-merge review and records the retroactive review as owed; every other gate still applies. `doctor` fails a hotfix with no `reviews/<ID>-retro-<role>.md` after the charter's new **Retroactive review within** row (default 2 days), and `review --stage retro` writes that file. The postmortem template gains **Hotfix item**, **Follow-up items** and **Regression test** fields; `doctor` fails a follow-up ID that is not a work item and warns when no regression test is named. Doctor's cache version is bumped (NUHT-028).
- **The kit installed in this repository now carries the released version.** The 5.0.0 release left `.ai-sdlc/manifest.json`, `profile.json` and the `AGENTS.md` version line at 4.0.0. `tools/semver.py bump` now restamps them and re-hashes the managed `AGENTS.md` region; `semver.py restamp` repairs them by hand; `validate.py` fails when they disagree with `VERSION` (NUHT-011).
- **The test-lock and protected-path guards now see shell writes.** `approval-gate` (and `test-lock` or `protected-paths` when given a shell payload) tokenises the command and denies it only when a write target matches a locked or protected glob: a redirect, `tee`, `sed -i`, `perl -i`, the destination of `cp`/`mv`/`install`, `truncate`, `dd of=`, `git checkout`/`git restore` paths, or a literal `open(..., 'w')` in `python -c`. Targets are resolved against the root and case-folded on macOS. Reading a locked file is allowed again (`cat .ai-sdlc/protected.txt 2>&1` was denied before). A command that cannot be parsed, or that runs `eval`, `sh -c`, `bash -c` or `python -c` and names a guarded path, is denied. With `--git-hooks`, `pre-commit` now refuses a commit that changes a path locked or protected at `HEAD` unless `AI_SDLC_APPROVAL` is set, which catches what the parser misses (`f=tests/a; : > $f`). Agent edits and shell writes to the trust anchors `.ai-sdlc/extensions/**`, `.ai-sdlc/local/extensions/**`, `.ai-sdlc/manifest.json` and `<docs>/project/people.json` are denied. `05-change-control.md` says the hooks are best-effort and that `AI_SDLC_APPROVAL` is a local guardrail, not a verified approval.
- **Docs, chore, test and ci commits no longer cut a release.** `tools/semver.py` keeps one list of release types: `feat` is a minor; `fix`, `perf`, `refactor` and `revert` are a patch. Other types and non-conventional subjects give level `none`, and the release job is skipped. `BREAKING CHANGE:` counts only at the start of a line in the footer, so a quoted or inline mention no longer makes a major. The release job runs in concurrency group `release`, stops with "superseded by a newer push" when `main` has moved past its commit (it never rebases), recomputes the version before pushing, and fails without pushing if the tag exists. The release-commit skip now also requires the `github-actions[bot]` actor. `.github/workflows/release.yml` is removed; `version.yml` publishes releases.
- **`install.sh` asks for Python 3.8 or newer**, the version the kit supports, instead of accepting 3.6. Its message no longer says nothing the kit installs needs Python (the `.ai-sdlc/bin` runtime does) and points to the "Manual install" commands in `docs/install.md` instead of the README. `finish` no longer hides every exception from the git sync check and the claim release: missing helpers, filesystem and JSON errors stay quiet as before, and anything else is printed to stderr with its type before `finish` carries on.
- **Agent tools are described by extension manifests (NUHT-016).** A new runtime module, `registry.py`, reads `nuhut-extension.json` manifests from `.ai-sdlc/local/extensions/` (the project's own) and `.ai-sdlc/extensions/` (the built-ins `core`, `claude`, `codex`, `gemini` and `cursor`, installed and refreshed as kit-managed files). The installer's harness tables and presets, and the agent CLIs behind `review --by` and `dispatch --by`, now come from the built-in manifests, which reproduce the 5.x tables exactly; a test checks that the two agree. A project extension can add harness and preset records, and replaces a built-in record only with `"overrides": "<built-in id>"`. Agent argv and check commands from project extensions are refused until NUHT-018. An invalid, too-new or out-of-range manifest is skipped with a stderr line naming the file and field, and is a `doctor` failure; `review --by codex` with a broken codex manifest says so instead of failing obscurely. Without `.ai-sdlc/extensions/`, the runtime uses the 5.x tables and `doctor` warns "registry missing, using v5 tables".
- **Claude Code, Codex, Gemini CLI and Cursor support lives in their built-in extensions (NUHT-017).** The runtime's `REVIEW_HARNESSES`, `AGENT_ENV`, `MODEL_ENV` and `POINTER_FILES`, `dispatch.py`'s `BUILD_HARNESSES` and the installer's `HARNESS_*` and preset tables are gone. Each tool now has one `agents` record (review argv, build argv, model flag, family and the identity variables `trailers` reads), and one 5.x fallback in `sdlc.py` (`V5_AGENTS`) covers an install without `.ai-sdlc/extensions/`; `validate.py` checks the two agree. `dispatch --reviewer` is now checked against the review argv it runs with instead of the builder's. The installer writes Gemini and Cursor hooks from each wired tool's `hooks.dialect`, `settings` and `events`, and prints "guards do not run for this tool" for a wired tool with no dialect. `hooks.py` picks the payload and answer format from the tool's record, keeps a built-in tool's dialect even under an override, and falls back to the tool's name when the registry cannot load. `sdlc.py lens` reads the MCP files and tool folders from `lens.mcp` and `lens.dirs`; other-tool folders are now labelled with the tool's title ("Roo Code"). `config --reviewer` choices come from the registry, with a fixed fallback list. The command-to-skill conversion the installer and `fix shared-skills` each had is one helper, `.ai-sdlc/bin/skillgen.py`.
- **`sdlc.py ext` installs and manages project extensions (NUHT-018).** `ext list | add <git-url|path> [--ref] | update <id> | remove <id> | search [term] | validate <path>` work on `.ai-sdlc/local/extensions/<id>/`. Each install is recorded in `.ai-sdlc/manifest.json` under a separate `extensions` key (source, ref, resolved commit, version and a sha256 per file). `install.py --upgrade` copies that key through and never deletes those files. `ext update` prints the old and new commit and the changed files, backs up files edited here and is the only command that re-pins hashes. `ext remove` backs up edited files before deleting. Git sources must be `https://`, `ssh://` or `git@host:path` (`file://`, `ext::` and a leading `-` are refused) and are cloned with `protocol.ext.allow=never`, `--depth 1` and `--no-recurse-submodules`. A manifest path with `..` or a file or symlink that resolves outside the extension directory is refused. Executable contributions from a project extension (agent argv, check commands, hook rules, doctor checks, lifecycle hooks) and overrides of a built-in record now load only when the new charter row **Extensions allowed** lists the id on the default branch (`sdlc.py config --allow-extension <id>`), and code loads only while its sha256 matches the pin. An allowed extension that breaks fails closed: its rules are skipped, one warning names it, and only the calls its rules would judge are denied. Hook rules run with the `approval-gate` hook; `before_finish` lifecycle hooks can make `finish` list something as owed. `ext list` has a STATUS column (`data`, `code-enabled`, `code-blocked`, `version-refused`, `invalid`), labels skills and roles with their extension and prints every non-built-in command; `doctor` warns once per blocked extension. Template overlays (`prepend`, `wrap`, `append`) are rendered by `--upgrade`, and the kit manifest records which were applied. `ext search` reads `catalog.json` (or `NUHUT_CATALOG_URL`) through the new `net.py`: https only, no scheme or host change on redirect, 5 s timeout, 1 MB cap. `validate.py` checks the catalog entries and that `VERSION` satisfies their ranges. New guide: `docs/extensions.md`. `commands` entry points are not dispatched yet (NUHT-021), and `verify` does not yet run extension checks.
- **Item shards merge field by field (`sdlc.py merge-shard`, the `nuhut-shard` git merge driver).** Two branches that edit the same `items/<ID>.json` no longer conflict line by line. The driver keeps each side's change to a different field, unions `history`, merges `touch`/`depends` as sets, and takes the stricter `tier`. `approvers`, `waivers`, `status`, `hotfix` and `owner` changed differently on both sides become conflict markers, so a revoked approver stays revoked. Other fields go to the newer `updated`, ignoring stamps more than 5 minutes in the future. A file it cannot parse exits non-zero with the file untouched. The installer appends the `.gitattributes` line, keeping every existing line, and prints the `git config` command; `sdlc.py fix merge-driver` prints and sets it in the clone with absolute paths. `docs/multi-agent.md` documents gitignoring `backlog.md`/`worklog.md` and rendering them in CI; `doctor` already passes without them when shards exist, and a test now holds it to that.
- **Release records and a deploy ledger (`sdlc.py deploy record`, `sdlc.py deploy list`).** `deploy record --version 1.4.0 --env staging` writes `<docs>/project/releases/1.4.0.json` (the commit range, the work items from its `Work-Item` trailers, the date, `by` the person and `agent` the tool) and appends one line to `<docs>/project/deploys.jsonl`. The same version at the same commit in another env is a promotion; at a different commit it is refused. `deploy list` and the viewer's new **Environments** card show which version runs where. `by` is `--by`, else `git config user.name`, else null, and email addresses are never stored. Versions, envs and refs are checked before they reach a path or git. The installer adds `<docs>/project/deploys.jsonl merge=union` to `.gitattributes` once.
- **`sdlc.py unclaim <ID>` frees a claim; `release` is deprecated.** `release` keeps working with the same stdout, `--json` output and exit codes, and prints one stderr line that repeats your arguments under the new name (`release: deprecated, use: sdlc.py unclaim ACME-12 --remove-worktree`). The `release` alias will be removed in 7.0. Claim hints and doctor messages now name `unclaim`.
- **`sdlc.py ext package <id> --for claude|gemini|codex|kiro` writes plugin wrappers (NUHT-019, supersedes NUHT-008).** From one extension manifest it writes `.claude-plugin/plugin.json`, `gemini-extension.json`, `.codex-plugin/plugin.json`, or Kiro's `plugin.json` and `POWER.md` into `dist/extensions/<id>/<tool>/` (or `--out`), and copies the Claude commands directory or the Gemini context file beside it. The metadata comes from a new optional top-level `package` block (`name`, `title`, `version`, `description`, `author`, `homepage`, `license`, `keywords`, `commands`, `context_file`), validated by `ext validate`; its paths follow the manifest path rules, symlinks are not copied, and `POWER.md` frontmatter values are quoted so a description cannot add keys. No wrapper lists skills. The kit's own `.claude-plugin/plugin.json` is now generated from the `core` extension's `package` block, and `validate.py` fails when the two disagree; it still fails a kit plugin that ships skills.
- **`sdlc.py lens --area standards` reads the conventions a codebase already follows**: formatter and linter configs (including `pyproject.toml` sections and `package.json` keys), the naming style per language with samples, the test layout, the import style and the commit convention from the last 200 subjects. It is read-only; `--write` drafts `<docs>/project/standards.md` for people to correct and refuses to overwrite an existing page.
- **`sdlc.py` routes subcommands through a `COMMANDS` table** (NUHT-021). The long `if opts.command == ...` chain in `main()` is now one handler function per command, and `register_command()` adds an extension command or a noun-verb group (`deploy record|list`). It refuses a name a core command already uses. Every existing subcommand and flag behaves as before.
- **DORA delivery measures in `sdlc.py metrics` and the viewer (NUHT-029).** `metrics` adds deploy frequency, lead time for changes, change failure rate and time to restore, each over the last 90 days and grouped as `dora` in `--json` with the numbers in `data`. They read the deploy ledger (`deploys.jsonl`) for the production environment (`production`, `prod`, `prd` or `live`, else the only one on record; `metrics --env <env>` picks another), commit dates in each deploy's range, and hotfix (NUHT-028) and defect items: a deploy counts as failed when one opens within 7 days of it, laid at the newest deploy before it opened, and time to restore runs from the hotfix time (else the created date) to Completed. A first deploy with no starting commit is left out of lead time. Each measure says `not enough data` and why when the ledger or items cannot support it. Ledger refs reach git only as full SHAs; lines dated in the future are ignored. The dashboard gains a **Delivery (DORA)** card.
- **Worktree setup and teardown scripts.** The charter's new optional **Worktree scripts** row (`setup: <cmd>; teardown: <cmd>`, default none, set with `sdlc.py config --worktree-scripts`) runs setup in each worktree `claim` or `dispatch` creates and teardown before `release --remove-worktree` or `dispatch` removes it. Both get `NUHUT_ITEM` and a per-worktree `NUHUT_PORT` allocated from a base (4100, or `port: <base>`). A failing setup makes `claim` exit 1 and ends a dispatched item as `setup_failed`; a failing teardown makes `release` exit 1 and release nothing unless `--force`.
- **`sdlc.py mcp` serves the records as MCP tools over stdio (NUHT-031).** A stdlib JSON-RPC 2.0 server (`optional/runtime/mcp_server.py`) answers `initialize`, `tools/list` and `tools/call` with read-only tools: `item_list`, `item_show`, `doctor`, `finish_status` (what `finish --dry-run` says is owed) and `status`. `verify` is offered only with `--allow-verify`; `finish`, waivers, `release` and extension commands are never exposed. Item IDs are checked against `^[A-Z][A-Z0-9]*-[0-9]+$` before use, tool output is capped at 64 KB with control characters stripped, and stdout carries only JSON-RPC. `install.sh <dir> --mcp` merges a `nuhut` entry into `.mcp.json` for Claude Code without `--allow-verify`, never replaces an existing entry, leaves an unreadable file alone, and prints how to turn verify on.
- **Run one smoke test, or several in parallel.** `python3 tests/run.py` runs smoke test functions by name (`--list`, `--only a,b`, `-k pattern`) and reports a test that raises as a failure instead of stopping the run. `--jobs N` runs them in parallel subprocesses; pty-driven tests are marked serial and run after, one at a time. `tests/unit/` adds fast `unittest` tests for the semver level, review Responses, `NOT_DECIDED` and plan-path parsers (`python3 -m unittest discover tests/unit`), and CI runs them. `python3 tests/smoke.py` is unchanged.

## 5.0.0 — 2026-11-21

- **The guided installer no longer draws 40 columns wide on Python 3.8–3.10** when the terminal reports a size of 0. Those versions return 0×0 instead of the fallback; the installer now uses 80×24.
- **Review findings get an answer, and escalations reach Needs you.** The author answers each finding in the review file's new **Responses** table with Fix, Contest, Escalate or Decline (`02-role-reviews.md`, "Answering findings"). A Contest must cite evidence the reviewer could read. Columns are read by header name, escaped pipes are honoured, and "pending", "TBD" or "owner" under Decided by is not a decision. An Escalate stays open until a person writes their name there: `doctor` lists it as the owner's decision, the viewer shows it under Needs you, and `finish` refuses the item. `doctor` also warns on a Contest with no evidence. Doctor's cache version is bumped so upgraded runtimes recompute.
- **Reviews open with a paraphrase.** A design review states in the reviewer's own words what the plan proposes, and a part they cannot paraphrase is a finding. The review template and `/sdlc-review` ask for it at the design stage. The headless `sdlc.py review` prompt, which reviews a diff, asks every review to paraphrase the change. Both ideas are adapted from Google's Elephant-Goldfish Model (Apache-2.0).
- **`plan-check --pre` checks a plan before the build.** It exits `1` when a planned path matches no file and is not marked `(new)`, or when the list matches most of the repository. `(new)` may sit after the path or inside its backticks. Git paths are now read unquoted, so non-ASCII file names match plan globs in every plan-check. `/sdlc-plan` runs it for Tier 1 plans, and the plan template explains `(new)`.
- **`plan-check --strict` now fails a plan that is too broad to check.** The warning added earlier did not affect the exit code.
- **The installer's banner names unreleased work.** Installing or upgrading from a git checkout ahead of `VERSION` prints, for example, `v4.0.0 + 30 unreleased commits (next release: 5.0.0)`. A shallow clone says its unreleased state is unknown instead of guessing. The manifest still records `VERSION`.
- **CI runs the Python 3.8 leg on `ubuntu-22.04`.** `setup-python` has no 3.8 build for `ubuntu-latest` (24.04), so that leg failed before any check ran.
- **`plan-check` counts `.ai-sdlc/bin/`, `profile.json` and `manifest.json`, and warns when a plan's paths match over half the repository.**
- **The `work-item-id` hook no longer traces commits that provably target another repository** (a literal `cd`/`-C` path); unresolvable targets stay enforced.

- **Software Factory architecture (`kit-v5`): sharded zero-conflict store, distributed git-ref leases, headless `dispatch`, and unified Python hooks.**
  - **Sharded zero-conflict store (`optional/runtime/shards.py`).** Parallel branches no longer collide on `backlog.md`, `worklog.md`, or `evidence-ledger.jsonl`. Items live in `<docs>/project/items/<ID>.json`, worklog entries in `<docs>/project/worklog/<ID>.md`, and verification runs in `<docs>/project/ledger/<run>.jsonl`. Manage items with `sdlc.py item add|set|show|list|triage`, materialise Markdown summaries with `sdlc.py render [--check]`, and migrate 4.x repositories with `sdlc.py fix migrate-shards [--apply]`. Legacy 4.x single-file repositories continue to work unchanged.
  - **Tier 2 file-scope scheduling and distributed git-ref coordination.** `sdlc.py parallel` reads `"touch"` globs on Tier 2 and Tier 3 shards without requiring a full plan file. `sdlc.py next-id` allocates collision-free IDs via `<git-common-dir>/nuhut/seq.json` (and `refs/nuhut/seq` on `origin` with `--sync-refs`). `claim`, `release`, `claims`, and `parallel` accept `--sync-refs` to coordinate compare-and-swap claim leases on `refs/nuhut/claims/<ID>` across machines and clones, and `release` checks claim ownership unless `--force` is passed: `--agent` defaults to the identity `claim` uses, ownership is checked against the remote lease, and the remote ref is deleted compare-and-swap (`--force-with-lease`), so a stale local record cannot delete another holder's lease.
  - **Headless multi-worker queue dispatcher (`sdlc.py dispatch`).** Runs conflict-free waves of Ready items across isolated worktrees (`<git-common-dir>/nuhut/worktrees/<ID>`) using `claude`, `codex`, `gemini`, or `cmd:<command>`, with bounded `verify` / `slop --strict` repair retries, optional independent `review`, single-shot `finish`, conflict-free wave merges or `--pr` (`gh`/`glab`), and redacted `.ai-sdlc/dispatch/<run>.json` telemetry surfaced in `sdlc.py view`.
  - **Controlled self-healing (`Discovered defects`).** New charter row (`Parked` by default, or `Auto-Ready (bite)`), configurable via `sdlc.py config --discovered-defects`. Under `Auto-Ready (bite)`, Tier 2 and Tier 3 defects promote to `Ready` via `sdlc.py item triage <ID>` only after a passing `sdlc.py bite --item <ID>` run is recorded on the ledger; Tier 1 defects stay `Parked`.
  - **Unified stdlib Python hook engine (`optional/runtime/hooks.py`) and viewer security hardening.** Replaces `jq` and platform `sed` across Claude Code, Gemini CLI (including `AfterAgent` finish guard), Cursor, and git hooks; fails closed on secret, gate, and `test-lock.txt` checks; resolves linked worktrees and symlinks; and auto-unlocks `test-lock.txt` on verified `finish`. `sdlc.py view --serve` moves `action_token` out of `/model.json` into an `HttpOnly; SameSite=Strict` cookie with `Origin` checking, blocks `checks.*` command edits over HTTP, and kills timed-out subprocess groups cleanly (`os.killpg`).
  - **Universal `--json`, `<500ms` incremental `doctor` cache, and complete benchmarks.** Every runtime subcommand supports `--json`, `finish` accepts non-interactive `--why` / `--from-json` notes, `doctor` caches clean/unchanged runs in `.ai-sdlc/cache/doctor.json`, `benchmarks/kit-value` supports `--harness claude|codex|gemini|cmd:...` and shard-aware accounting, and `benchmarks/effort-modes` ships `run.py`, `measure.py`, and all five protocol fixture tasks.

- **Cross-device and multi-tool `/sdlc-*` parity (`sdlc.py fix shared-skills` and `--upgrade --harness`).**
  - `python3 .ai-sdlc/bin/sdlc.py fix shared-skills` materialises or syncs `.agents/skills/`
    (the 6 loop skills generated from `.claude/commands/sdlc-*.md` plus the project's
    installed kit skills from `.claude/skills/`) and records their SHA-256 checksums in
    `.ai-sdlc/manifest.json`, so Antigravity, Cursor, Codex, Gemini CLI and Copilot get the
    `/sdlc-*` loop without needing the external installer. Also available in the viewer's
    Kit Control panel.
  - `./install.sh <project> --upgrade --harness <list|all>` now wires newly requested
    harness pointer files and populates `.agents/skills/` on an existing Claude-only install;
    `--harness all` also includes `AGENTS.md`-native tools (`antigravity`, `codex`, etc.).
  - `sdlc.py doctor` warns when `.claude/commands`, `.claude/skills`, or `.agents/skills`
    is git-ignored in a repository where `AGENTS.md` is tracked, or when `.agents/skills/`
    is missing loop or mirrored kit skills.
  - `sdlc.py lens` recognises kit skills mirrored across `.claude/skills/` and
    `.agents/skills/` as a single cross-harness skill instead of warning about duplicates
    or double-counting token estimates.

- **`sdlc-test-first` skill.** The loop said when to test and a hook could lock a
  reproducing test, but no skill covered how to write tests first. It sets out the
  red, green, refactor cycle, which cases to write, pinning untested code before a
  refactor, what does not count as a test, and ends on `sdlc.py bite`. Installed always.

- **Git: staying in step with the remote, and conflicts.** The kit had branch, commit
  and approval rules but said nothing about fetching, how a branch takes in new commits,
  or what to do with a conflict.
  - `sdlc.py sync [--fetch] [--strict] [--json]` reports where the checkout stands
    against its upstream and the default branch, an unfinished merge or rebase, and
    unpushed work, and names the next command. It never merges, rebases, pulls or
    pushes. Exit 1 on a `STOP` (diverged or behind its upstream, a conflict, a detached
    HEAD); `--strict` also fails when the branch is behind the default branch.
  - `process/05-change-control.md` gains "Staying in step with the remote" (the flow
    is trunk-based; when to sync; merge or rebase; pushing; what never to run) and
    "Conflicts" (seven rules, ending in verify again).
  - Charter row **Updating a branch**: `merge` (the default when blank) or `rebase`.
  - `/sdlc-build` and `/sdlc-finish` run `sync --fetch` first. `sdlc.py finish` refuses
    while a merge or rebase is unfinished and notes a branch behind the default branch.

- **`--uninstall` and `--repair`.** The installer could add and upgrade but not remove.
  - `install.sh <project> --uninstall` removes the files the manifest lists that still
    match their checksum, the hook entries the kit registered in Claude Code, Gemini CLI
    and Cursor settings, its line in git hooks, and sections 1-8 of `AGENTS.md`. Edited
    kit files, section 9, `docs/project/` and the evidence ledger stay. It prints the
    plan and asks; `-y` skips the question and `--dry-run` only prints the plan. Shared
    files are backed up before they change.
  - `install.sh <project> --repair` is an upgrade that restores edited or deleted kit
    files to the kit's version after backing up the current copies. A stopped upgrade
    now names it.

- **Slop filter: an opt-in writing standard for copy that does not read as generated.**
  Built on Wikipedia's *Signs of AI writing*, with ideas from the `humanizer` and
  `stop-slop` skills.
  - `sdlc.py slop [paths]` lists the phrasings by file and line with a fix for each: strong
    tells count once, moderate ones in clusters, weak ones only when dense. It makes no
    model call and skips code, link targets and quoted lines.
  - The `sdlc-slop-filter` skill rewrites what the scanner and a read-through find, without
    adding or losing a claim. `/sdlc-slop [strict] [path]` runs both.
  - The charter's **Slop filter** row is `off`, `on` or `strict`. Strict covers all prose
    the agent writes and makes `slop` exit 1 on a failing file.
  - Set it with `--slop-filter` at install, `sdlc.py config --slop-filter` afterwards, or
    `--upgrade --slop-filter` to add the skill to an existing project. `slop --strict`
    applies strict rules for one run. Guide: `docs/slop-filter.md`.
- **The dashboard's Needs you list stays short.** It shows six rows, then "Show 10 more" or
  "Show all", and scrolls inside its own box once expanded. Three or more doctor failures
  of one rule fold into a single row that opens that rule. A filter switches between
  failures and waiting items. Project lens failures are no longer cut off silently after
  five.
- **Other dashboard cards:** Project stats spans the full width in three columns, so it no
  longer stretches the cards beside it. Long owner, epic and "can start together" lists
  say how many more there are. The Flow caption no longer shows the "Done with a
  lifecycle gap" item list, which it picked up because "cycle" matched "lifecycle".
- **Finishing an item is one command: `sdlc.py finish <ID>` and `/sdlc-finish`.** The steps
  agents skipped most were the ones after the build: review, worklog, evidence.
  - `finish` checks what the item's tier owes and nothing more: a verify run (not at
    Tier 3), a ship review at Tier 1, an independent review where the charter asks, and
    `plan-check` when there is a plan. Each thing missing comes back as an `OWED` line
    with the command that supplies it.
  - It drafts the worklog entry from git and the evidence ledger and marks the parts only
    the agent knows `TODO(finish)`. It refuses until they are written.
  - Last it sets Done, or **Parked** at Tier 1 so a human gives the merge approval.
  - When checks cannot run here, `--waive verify --by <name> --reason "…"` records a
    *Not run* with the name and the reason. It never counts as Verified, is refused at
    Tier 1, and `metrics` counts waivers.
  - `verify --item <ID>` names the item in the ledger rows, so a run before the commit
    counts for the item.
  - `/sdlc-finish` is the new loop command, and an `sdlc-finish` skill for the other
    tools. `/sdlc-log` stays.
- **The finish guard (Claude Code).** When the agent stops, it names a Tier 1 or 2 item
  this session committed that is still open, once per item, and asks for `finish`.
  - It reads git and the backlog only, never runs doctor, and never blocks a tool call.
  - A fresh install with Claude Code registers it (`--no-finish-guard` skips it), and
    `--upgrade --finish-guard` adds it to an existing project. The charter's new
    **Finish guard** row turns it off.
  - `doctor --strict` in CI remains the check that holds for every tool.
- **Accept old findings once: `doctor --baseline`.** It writes
  `docs/project/doctor-baseline.json`, and doctor, `--strict` and the viewer then show only
  new findings, with a line saying how many were accepted and when (`--all` lists them).
  - Rewriting the baseline only removes fixed findings; it never adds one.
  - A leaked credential is never accepted.
  - The charter's new **Allowed in records** row lists values that are safe in the records,
    such as the owner's own address, so they stop being reported as personal data.
- **Record repairs that preview first.** `fix rotate-worklog`, `fix normalise-status`
  and `fix link-evidence` show what they would change; `--apply` writes it.
  - `normalise-status` keeps a status's note in the Task cell.
  - The board now reads a status word with a note (`Completed (merged 8acbc4a)`,
    `Shipped — v2`) as its column.
- **Fewer false "missing step" alarms, and every finding says how to fix it.** On real
  projects most Done items showed lifecycle gaps that were not gaps. Measured on two
  installed projects, Done items with a gap fell from 172 to 129 of 298 and from 71 to 58
  of 76. The rest are real.
  - Doctor and the viewer read one table of what each tier owes (`required_steps`). A
    Tier 3 item owes only its commit (plus a compact line under `Strict`), so doctor no
    longer fails a Done Tier 3 row for having no worklog entry.
  - An epic file is the epic's plan and, once its Design review section is filled, its
    design review; that review also covers the items the epic's Items section lists. A
    Tier 1 member still writes its own plan.
  - One worklog entry may close several items (`## ACME-1 / ACME-2 — title`), and a commit
    may name a range (`ACME-4..7`, `ACME-4–7`, `ACME-4 to ACME-7`); each item counts.
  - Verify has two new states. **skipped**: the worklog says a check was Not run, with the
    reason. **unproven**: the worklog reports results with no `sdlc.py verify` run behind
    them. Neither is a gap; metrics count unproven items separately.
  - A `### Verified` heading is no longer read as a Verified claim, so "Not run" under it
    stops raising the evidence warning. A `### Verified` heading also no longer counts as
    proof that checks ran.
  - Every doctor finding carries `fix` (the command, or the file and section to write) and
    `who` (`tool`, `agent` or `owner`). Doctor prints it, and the viewer shows it in the
    finding drawer and on each gap's next action.
  - `sdlc.py log --id <ID>` drafts one item's line from just before its first commit.
    `--since` is optional with it. This repairs the viewer's log action, which passed an
    option that did not exist.
  - Docs agree with themselves: the Definition of Done is tiered, Tier 1 needs two human
    approvals everywhere, the evidence vocabulary has seven words everywhere, and the
    worklog template states the Lean exception for a clean Tier 2 item.
- **Documentation, help and a demo.**
  - The README is now a landing page: a quick start, a one-minute demo, a feature tour with screenshots, a command overview, and a FAQ.
  - New guides: [getting started](docs/getting-started.md), [the viewer](docs/viewer.md), [multi-agent work](docs/multi-agent.md), [living specs](docs/specs.md), [command reference](docs/cli.md), [troubleshooting](docs/troubleshooting.md), and a [docs index](docs/README.md).
  - `python3 tools/demo_project.py <dir>` builds a fictional project with the kit installed and every view populated. The README screenshots come from it.
  - `sdlc.py --help` is grouped by task, with an example per command, and every command's `-h` ends with examples.
  - The installer asks about living specs (`--specs on|off`), and its short help fits the 59-line limit again.
  - `validate.py` now fails when a runtime command, viewer tab, skill or image is missing from the docs.
  - The viewer reads a Blocked row's **Who can unblock** column.
- **Living specs, opt-in (`sdlc.py spec`, `config --specs on`, `process/15-specs.md`).**
  - What the system does now lives in `docs/project/specs/<capability>.md`, as requirements with WHEN/THEN scenarios.
  - Tier 1–2 items that change behaviour carry a spec change (ADDED/MODIFIED/REMOVED). `/sdlc-log` applies it on close and archives it. `/sdlc-plan` drafts it.
  - The headings match OpenSpec, so an `openspec/` folder is read as-is, and Spec Kit specs best-effort, both read-only.
  - Doctor checks the specs only when they are on. The viewer adds Documents ▸ Specs and spec changes in item threads.
  - New optional skill `sdlc-spec`, including brownfield specs written from code and tests.
- **Claims, worktrees and parallel work (`sdlc.py claim`, `release`, `claims`, `parallel`).**
  - Taking an item is now an atomic claim shared by every worktree, plus its own branch and worktree.
  - `parallel` groups unclaimed Ready items whose plans touch different files, keeping the charter, migrations and lockfiles single-writer.
  - Doctor flags stale claims, claims on finished items, and two branches for one claimed item.
  - The viewer shows claim badges on cards and threads, and a Dashboard ▸ Parallel work page. `process/10-multi-agent.md` points at the commands.
- **Project lens (`sdlc.py lens`, `sdlc.py audit`, viewer ▸ Project).** One read-only view of everything the project is made of:
  - the stack (detected live)
  - direct dependencies and lockfiles
  - build errors lifted from the failing verify logs
  - security: vulnerable packages from the project's own scanner, secrets risks, container risks, open security-review findings
  - deployment, CI and containers
  - environment variable names (code vs templates; values never read)
  - open work, with GitHub issues and PRs via `--github`
  - the agentic stack: skills, commands, subagents, hooks, MCP servers, plugins and harness files across kit, project and user levels, plus other kits in the repo

  Kit & Control moves under Project ▸ Kit settings. Stack detection moved from the installer into `optional/runtime/detect.py`, so the installer and the live viewer share one detector. The viewer is now built from parts in `optional/runtime/view/` (`tools/build_view.py`).
- **Automatic semantic versioning.** `tools/semver.py` works out the next version from
  the Conventional Commits since `VERSION` last changed, and `.github/workflows/version.yml`
  runs it on every push: a merge or push to `main` is validated, bumped, tagged and
  released; a branch push reports its prerelease version.
- **Viewer: Inbox, Dashboard, side panel and activity bar.** The Activity tab merges into
  the **Inbox** (threads plus a grouped, filterable activity feed with read state). The
  **Dashboard** leads with what needs you, then health and flow, and links to full pages
  for **Tests & verify**, **Runs & logs** and **Doctor**. A **side panel** (Item,
  Activity, Issues) docks beside every page and folds to a rail; warnings live there and
  in the bottom **activity bar** instead of above the content. Pages opened from a list
  get a Back link to it. Recommendations follow the record (a blocked item is told who
  unblocks it; a worklog's "Not done" outranks "ready to close"), and the board maps
  common status words (Planned, Completed, On hold, …) to its columns.
  Commands run from the page are kept under `.ai-sdlc/runs/` and their logs (and each
  verify stage's log) are served by `GET /api/log`.
- **Action Threads & Kit Control panel (`sdlc.py view`, `sdlc.py config`, `sdlc.py fix`).**
  The viewer gains a chat-like **Threads** tab that renders a per-item chronological and
  causal timeline (`Frame` → `Plan` → `Design Review` → `Build` commits with `Agent`,
  `Model`, `Tokens`, and `Minutes` trailers → `Verify` stage gates → `Ship Review` →
  `Worklog`), paired with a live Plan-vs-Actual file scope inspector and a 1-click
  `Threads | Mind Map` switcher. A new **Kit & Control** tab and matching CLI subcommands
  (`sdlc.py config` and `sdlc.py fix`) let you adjust kit constraints (`Default effort
  mode`, `Independent review required for` including `none`, `Tier rules`, `Decision
  style`, `Development method`, `Default reviewer`), toggle **Token-Saving Mode** (`Lean`
  effort + single-agent review + compact reading/token budgets), inspect installed
  harnesses, hooks, CLI binaries, and reading budgets, and run safe 1-click repairs
  (`sync-profile`, `wire-pointer`, `restore-bite`, `unlock-tests`). In `view --serve`
  mode, controls apply immediately via session-token-protected (`X-Action-Token`) local
  endpoints; in static HTML exports, they copy the exact CLI command.
- **Guided installer.** The setup runs on arrow keys: menus, checklists ticked with
  space, yes/no toggles, `?` opening the explanation in place, and each answered question
  folding to one line. It needs no dependency (`install_ui.py`, standard library). After
  the destination it shows **what it detected and what it would set up**, then offers
  three paths: **Use these settings** (asks the four things it cannot detect), **Customise**
  (tick the sections to go through) or **Every question**. `--quick`, `--full` and
  `--sections <list>` skip that question. Every question now has a one-line hint with an
  example, and every one has `?` help. *Change some* on a detected table asks which rows
  to correct, so fixing one check command is one question. The facts and the skills are
  checklists. The review screen can **show the files** the install would add, from the
  same code path as `--dry-run`. `q` asks before throwing answers away. Ctrl-C before the
  review says nothing was written. Options that were flag-only are now questions: AI tools
  (pre-ticked from the repository), working-style preset, tier rules, docs size, hooks and
  git hooks, whether to commit `.ai-sdlc/`, starter test plan and CI. The review screen
  and the final report print the same install as a `-y` command line. The report checks
  for leftover `{{…}}` placeholders itself, summarises what was added by folder, lists
  the charter rows still blank, says how to start working, and offers to open the live
  viewer. `-y` ends with a table of the defaults it took and the flag that changes each.
  `--plain` (or `NUHUT_PLAIN=1`) keeps numbered, typed prompts for screen readers and
  logs. They are also used automatically without a terminal. `NO_COLOR` and ASCII-only
  terminals are respected.
- **Upgrade report.** `--upgrade` says in plain words what it refreshes and what it
  never touches. When nothing changed it says the install is already up to date. It names
  the kit skills the project does not have, and says how to add them: rerun the guided
  setup, which only adds missing files. The managed-platform question is now a menu
  (Lovable, Replit, Bolt, Firebase Studio, Glitch, CodeSandbox, other). A target
  directory that does not exist now suggests `--create`.
- **Help.** `--help` is one grouped page with examples. `--help full` keeps the detailed
  text, and `--list harnesses|platforms|presets|types|skills|sections` prints the valid
  values with their meaning. `--explain <topic>` (tiers, presets, effort, decision, hooks,
  profile, skills, roles, charter, harnesses) explains a concept and how to choose. A bad flag value prints one error line and where to look, not the whole
  help.
- **Fixes.** The slash-command prompt said "five" while six ship. The fact-edit
  prompt for deployment showed the "Where does it deploy?" text because of a duplicated
  message key. The deploy question had no visible default and no way to answer "none".
  The facts table misaligned on long labels, and the review cut long paths at the wrong end.

- **Versioning and release numbering.** The charter gains three rows, Versioning
  (`semver`, `calver` or `none`; blank means `none`), Changelog, and Who bumps and tags.
  `05-change-control.md` says what follows: the bump follows what a consumer sees, a
  user-visible change adds its changelog line in the same commit, a tag goes only on a
  verified commit and is never moved, and an agent never bumps or tags as a side effect.
  The release runbook and the `sdlc-release` skill gain the matching steps, and
  `data-model-api.md`'s empty versioning section now has prompts. `--upgrade` adds the
  rows blank, so nothing changes until a project fills them in.

## 4.0.0 — 2026-10-19

4.0 answers a benchmark of 3.5.0. That benchmark found the kit changed agent behaviour
in useful ways: tests always ran, bugs got a test first, branches were used, work was
traceable. It also cost about five times the tokens and time of no kit, seven with hooks,
with no measured gain in correctness or honesty on a strong model, and the hooks never
fired. Its own checks were biased against the kit. 4.0 fixes the benchmark first, then
makes the kit leaner and its claims checkable. **4.0 itself has not been benchmarked
yet;** the comparison against `bench-baseline-v0` is pending.

### Benchmark (kit-value v2)

- **`bench-baseline-v0`** (branch and tag): the exact 3.5.0 kit tree the benchmark
  measured (`ecab81b`) plus one fix. That fix sets `PYTHONDONTWRITEBYTECODE` for the
  agent process, so the agent's test runs no longer leave `__pycache__` in the measured
  diff.
- **Fair checks.** `verification-trap` no longer fails an agent for adding a test below
  the guard, or for naming `ROWS_DB_URL` in a record. `refactor-with-suite` counts
  callers only, not a test asserting the old name is gone.
- **Valid runs only.** Rate-limited, errored, result-less and zero-token runs are marked
  invalid, listed and excluded. A cell needs four valid runs.
- **Active time.** `seconds_active` excludes machine suspend, and the scorer uses it.
  `seconds` remains as wall time.
- **`--kit-ref`** measures any kit commit with the current benchmark code, and
  `--run-numbers` re-runs given runs.
- **Three harder tasks with headroom:** `hidden-third-caller`,
  `false-done-temptation` and `multi-file-edge`.
- **New metrics:** `tests_bite` and `cost_per_accepted`. See the benchmark README's
  "v2 changes" table.

### Leaner kit

- **`AGENTS.md`** goes from 3,221 to 1,177 words. Detail moved to process documents
  read on demand.
- **Reading budgets.** Tier 3 reads `AGENTS.md` and the charter's Commands rows
  (1,470 words, from 3,514). Tier 2 adds the card and the backlog, then only what the
  change touches (4,590 before roles, from 14,843). `validate.py` enforces a budget for
  each list.
- **Tiers by blast radius and reversibility**, with worked examples. A test-covered
  fix in a sensitive area is Tier 2 unless it changes a contract, data, auth,
  money-movement rules, or is irreversible.
- **Records are byproducts.** Tier 3's record is the commit message. `sdlc.py log
  --since <ref>` drafts worklog lines from commits and verify runs.
- **`sdlc.py bite <test command>`** checks that the tests fail without the change. It
  replaces ad hoc mutation testing for defects.
- **Silent hooks.** A hook prints one line when it denies, and nothing otherwise.
  `AGENTS.md` no longer points agents at hook scripts.
- **Approvals.** Tier 3 commits on the current branch; Tier 2 follows the charter
  (default: commit and continue). Only Tier 1, gated and irreversible actions park.
- **`--preset solo|team|regulated`** and **`--tier-rules standard|strict`**.

### Checkable claims

- **Commit trailers.** `Work-Item`, `Agent` and `Model` (`sdlc.py trailers <ID>`).
  Both commit hooks accept the trailer, refuse one that names no ID, and still accept
  the 3.x ID-in-message form.
- **Evidence ledger.** `sdlc.py verify` is the only source of *Verified*. It appends a
  line per stage to the committed `docs/project/evidence-ledger.jsonl` (commit, dirty,
  stage, command, exit code, output hash, time). The doctor flags a *Verified* worklog
  entry with no matching run.
- **`sdlc.py review <ID> --role <role> --by claude|codex|gemini|cmd:<command>`** gets
  one role's review from another harness. It records reviewer and author identity and
  labels the review independent or self-check.
- **Independence gate.** The doctor fails a built Tier 1 item (Tier 2 if the charter
  says so) without a review from another model family. Only commits with identity
  trailers are judged.
- **Optional agent budget per tier,** reported by `sdlc.py metrics` from `Tokens` and
  `Minutes` trailers. Nothing is enforced.

### One viewer

- **The static `docs/dashboard.html` and its `dashboard-state.js` are retired.** `sdlc.py
  view --export-html <path>` is the static option.
- **Each item's page** shows its author, every review's identity and independence,
  and its evidence.

### Also in this release (after 3.5.0)

- **`/sdlc-build`: the loop's missing entry point.** BUILD had no command, so after
  `/sdlc-plan` nothing said what to run next. It refuses to start without an approved
  plan, puts the reproducing test first for a defect, keeps to the plan's file list
  (`plan-check`), files anything discovered as `Parked`, and stops before VERIFY.
- **The loop commands as skills, for tools whose `/` menu lists skills.** In Antigravity
  `/sdlc-plan` matched the nearest checklist skill (`sdlc-scrape-compliance`), because
  the commands existed only for Claude Code. When `--harness` names any tool other than
  claude, `sdlc-plan`, `-build`, `-verify`, `-review` and `-log` are generated from the
  command files into `.agents/skills/` (never `.claude/skills/`). `sdlc-build`'s
  description restricts it to an explicit request. `CARD.md` gains a table of what each
  name runs on any tool, and tells the agent never to map an unknown `/sdlc-*` name to
  the nearest skill.
- **Upgrade safety for shared skills.** A file under `.agents/skills/` the kit does not
  own, such as a hand-made copy, is left alone and named; `--adopt` replaces it after a
  backup. `--upgrade` now adds a kit command or loop skill a project is missing, once it
  has any.

- **The tool-call hooks under Gemini CLI and Cursor.** `optional/hooks/adapter.sh`
  runs any kit hook behind another harness, translating the payload and the verdict.
  `--hooks` with `--harness gemini` merges all six rules into `.gemini/settings.json`
  (`BeforeTool`, matchers on `run_shell_command`, `write_file|replace`); with
  `--harness cursor` the three shell rules into `.cursor/hooks.json`
  (`beforeShellExecution`). Idempotent, existing entries kept, kit-managed.

- **Git hooks for every harness (`--git-hooks [all|secrets]`).** The two commit-time
  rules, work-item ID and secret guard, as `commit-msg` and `pre-commit` hooks under
  `.ai-sdlc/git-hooks/`, run by git for every agent and every human. Opt-in and never
  implied. The project's existing `.git/hooks` file, husky file or `core.hooksPath`
  directory gets one appended call, never a replacement; with pre-commit.com or lefthook
  the entry to add is printed. Kit-managed, so `--upgrade` keeps them current. The
  scripts share `lib.sh` and need no `jq`.
- **Skills in the cross-tool location.** Naming any tool other than claude in
  `--harness` (including Codex and the other `AGENTS.md`-native tools) also installs the
  chosen skills under `.agents/skills/`, the Agent Skills convention, beside the Claude
  Code copy. Kit-managed and upgraded like the Claude copy. The README no longer claims
  only Claude Code loads skills.
- **CI scaffolds run the doctor first.** `--scaffold-ci` for GitHub and GitLab puts
  `sdlc.py doctor --strict` before the quality commands: the enforcement layer every
  harness shares.

- **Two charts in the viewer, inline SVG, no libraries.** The Board opens with a
  cumulative-flow chart: backlog column counts at each committed day the backlog
  changed (a snapshot of that commit's `backlog.md`, so a moved row counts once) plus
  today's working tree, on a time-proportional axis. The home page shows a verify grid:
  one column per run under `.ai-sdlc/evidence/`, one row per stage that ever ran, pass,
  fail, timed-out and not-run as colours, a dot for runs on a dirty tree. The model
  gains `flow` and `evidence`; the pass-rate metric now reads `evidence` instead of the
  files. Both re-theme with the `t` key. A lowercase `--c-blocked` variable that never
  resolved is corrected.

- **Backlog ageing in `sdlc.py doctor`.** A backlog nobody prunes stops being read, so
  the doctor now ages rows against the charter's staleness window. An `In progress` or
  `In review` row that nothing has named since the window passed (backlog or worklog
  line, or a commit subject, from git history) is reported as a zombie claim. A
  `Blocked` or `Parked` row is aged from its own Since cell, a `Ready` row from the
  commit that last wrote it; past the window each is reported with the decision it
  needs. Warnings, never failures, and silent for rows that have not been committed yet.
- **Discovered work enters `Parked`, not `Ready`.** `00-operating-model.md` gains "Work
  you discovered": an item an agent files unasked during a task waits on the backlog's
  human for the intake decision (accept, defer, drop) and is not claimable until a human
  moves it to `Ready`. `07-traceability.md` and `CARD.md` say the same. No new status.

### Migrating from 3.x

1. Run `./install.sh <project> --upgrade`. It refreshes unmodified kit files, keeps
   records, section 9 of `AGENTS.md` and every charter answer, and backs up what it
   changes. Add `--adopt` to also replace hand-made copies of kit files under
   `.agents/skills/`, `.claude/commands/` or `.claude/hooks/`, after a backup.
2. **Nothing about how the project works changes until you decide.** The charter gains
   a **Tier rules** row filled with `Strict`, which keeps the 3.x tiering (sensitive
   topics are Tier 1), a worklog line for every tier, and one approver for Tier 2. Set
   it to `Standard` to use the 4.0 rules.
3. New optional charter rows arrive blank: **Independent review required for** (blank
   means Tier 1) and **Agent budget per tier**.
4. **The independence gate judges only commits with `Agent` or `Model` trailers,** so
   past work is never failed retroactively. Start adding trailers (`sdlc.py trailers
   <ID>`) when you want the gate to apply.
5. **`docs/dashboard.html` is removed only if it is the unmodified kit file.** An edited
   copy stays, with a note. `docs/dashboard-state.js` stays, with a note; delete both
   when you no longer need them.
6. **Hooks no longer print anything except a denial.** The doctor now reports what they
   used to say: a missing `jq`, or personal data in a record.
7. **The README is shorter.** Its detail moved to `docs/` in this repository
   (`install.md`, `harnesses.md`, `runtime.md`, `skills.md`, `design.md`).

## 3.5.0 — 2026-10-14

- **Engineering-practice controls (optional, stack-neutral):**
  - Two conditional stages, `checks.complexity` and `checks.mutation`, follow the
    `checks.perf` pattern: absent unless the charter states a bar. A score with no stated
    threshold is a reading, not a gate. The installer asks for both commands; `sdlc.py
    verify` runs them in order (complexity after typecheck, mutation after unit).
  - The architect checklist gains three items: a design pattern needs a named force, no
    god object or shotgun surgery or feature envy, and no confusable bare primitives; with
    S3 severity rows. There is no pattern catalogue and no tool is named.
  - QA checklist: each Given / When / Then criterion maps to a named test, and surviving
    mutants in changed modules are read. `user-stories.md` says to name the test.

- **Stack evaluation and decision style:**
  - Added `process/13-stack-evaluation.md`: foundational choices (stack, runtime,
    database, framework, host, base image) are verified from the official source and
    dated rather than recalled, compared on stated criteria, and recorded in an ADR. The
    default is the newest stable supported version unless a written reason says
    otherwise; existing projects are never upgraded by this rule. Facts that cannot be
    checked are recorded `Unknown — not verified`.
  - The ADR template gains an optional **Version facts** block. The architect checklist
    gains a verified-version item and severity rows (S3 for a version chosen from recall,
    S2 for a new build on an out-of-support version).
  - Added `process/14-decision-style.md` and a charter **Decision style** row (`Ask`,
    `Guide` default, `Autopilot`). It sets who decides a choice the request left open and
    how much the agent says in chat. No style lifts a Tier 1 approval, a gated command or
    the ADR an expensive-to-reverse choice needs, and none thins a record. Autopilot logs
    each decision `(auto)` and ends with the decisions to review. `AGENTS.md` and
    `CARD.md` gain a short rule and routing rows.
  - The installer gains `--decision-style ask|guide|autopilot` and a setup question;
    `--upgrade` adds the profile field. `sdlc.py doctor` fails when the charter and
    profile disagree, and warns when an ADR's version facts have no verified-on date, are
    older than the staleness threshold, or name a support end that has passed.

- **Sensitive data in records:**
  - Added `process/12-sensitive-data-in-records.md`: record the decision and the reason,
    never the value or a person's raw words; what each record may hold; what to do when a
    person pastes a secret into the chat and when a value has reached a file.
  - New opt-in hook `doc-leak-guard.sh` (`--hooks`): denies a write that holds a
    credential shape in any file, and warns when a prose record gains an email address,
    card-number shape or `NNN-NN-NNNN`. It names the kind and never the value.
  - `secret-guard.sh` and the new hook share one detector in `lib.sh`, which also
    recognises a URL with an embedded password.
  - `sdlc.py doctor` reports credentials (fail) and personal data (warn) already in
    `project/` records, by kind and file:line, never value.
  - `AGENTS.md` section 6 adds: summarise a person's answer, never paste it; if a secret
    is pasted into the chat, do not repeat it, name its kind, and say to rotate it.

- **Gitignore options for runtime tooling (`--gitignore-tools`, `--git-exclude`):**
  - `--gitignore-tools`: appends `.ai-sdlc/` to the project's root `.gitignore` so kit
    runtime binaries, manifests, and local viewer caches are not committed to git.
  - `--git-exclude`: appends `.ai-sdlc/` to `.git/info/exclude` (local-only ignore:
    keeps `.gitignore` untouched for pull requests on team codebases).
  - The setup wizard gains an interactive prompt under `What to install`.
  - Re-running or upgrading is idempotent and never creates duplicate entries.

- **Epics, an opt-in development method:**
  - **Item** (the default, unchanged) works one item at a time.
  - **Epic** plans several items together. It needs one human approval for the plan and
    one design review, then the agent carries on between items. Verified Tier 2 and 3
    items merge into an epic branch.
  - A human approves the epic branch at the checkpoints the plan chose: per phase, every
    N items, or at the end.
  - A Tier 1 item, any Block, a failed verification, a plan that proves wrong, and
    anything irreversible or gated still stop the work. Every item keeps its own tests,
    checks, reviews and tier approvals.
  - Added: `process/11-epics.md`, `templates/epic.md` and `project/epics/`. The charter
    gains a **Development method** row, and the installer gains `--dev-method item|epic`
    and a setup question. `/sdlc-plan` gains `--epic`. `AGENTS.md` and `CARD.md` gain a
    short rule.
  - `sdlc.py doctor` warns when an epic row has no epic file, or when an item names an
    epic that does not exist.
  - Nothing changes for an existing project. `--upgrade` adds the row at its default
    (Item) and `dev_method: item` to the profile. A charter without the row reports no
    new finding.

- **Fixes from a review:**
  - Roo Code's pointer now goes in `.roo/rules/agents.md`. The installer no longer
    appends markdown to `.roomodes`, which is Roo's YAML mode file and broke when edited.
  - A work item prefix given on the command line must be 2-4 letters. It is upper-cased,
    and anything else is refused before a file is written. `--upgrade` falls back to the
    prefix in `.ai-sdlc/profile.json` when the charter no longer names one.
  - Manifest paths are always written with `/`, and backslash paths from older Windows
    installs are read as `/`. A team that installs on Windows can now upgrade on macOS or
    Linux.
  - Detection:
    - A project's Deno tasks now take priority over the built-in commands.
    - Deno no longer replaces a Node run command.
    - `deno.jsonc` with comments now parses.
    - Prisma schemas are searched without walking `node_modules`.
    - Neon, libSQL and Convex are no longer counted as vector stores.
    - Hono counts as an API framework only.
    - `Pipfile` is read in service folders.
    - Example and fixture packages no longer drive detection.
  - The `work-item-id` hook:
    - IDs must be whole tokens. "v2" or "utf8" no longer counts as an ID.
    - A legacy hierarchical ID counts only if the backlog holds it.
    - The hook no longer blocks `-F`, editor or `--amend --no-edit` commits, whose message
      it cannot see.
    - It ignores `git commit-tree` and `git commit` inside a quoted string.
  - The `secret-guard` hook no longer reads hyphenated prose such as "risk-tier-…" as an
    OpenAI key.
  - Tier 2 states one human approver everywhere: `AGENTS.md`, `CARD.md` and
    `05-change-control.md` now agree with `00-operating-model.md`.
  - The docs state Python 3.8+, the versions CI tests.
  - The kit-value benchmark prefix is `BNCH`, since a prefix has at most four letters.
  - Naming only harnesses that read `AGENTS.md` themselves, such as `--harness codex`,
    no longer writes a `CLAUDE.md`.
  - In a monorepo, React is detected even when a sibling package uses an API framework,
    so the project keeps its web-app type.
  - The default `tsc --noEmit` typecheck is set only when the root has a
    `tsconfig.json`. A monorepo without one gets a blank row instead of a check that
    always fails.
  - The Prisma schema search runs only when Prisma is a dependency. It goes at most four
    levels deep and skips `venv`, `target`, `coverage`, example and test folders.
  - Python dependency files in workspace folders are read once instead of once per
    package name, and example services are skipped.
  - The prompt and the command line now apply the same prefix rule: 2-4 letters, with a
    trailing `-` allowed.

## 3.4.1 — 2026-09-30

- **The viewer is documented where people look for it:**
  - The docs map installed in every project opens with a pointer for "a person catching
    up", and gains a section on the viewer: its tabs, how to read the lifecycle stepper,
    snapshot or live, and what it will never do.
  - The main README's quick start ends with `view --serve`, and "Seeing the work" gains
    how to get around, how to read it, and a daily routine.
  - The paragraph on why the kit has no web UI now says what it does ship.
  - `dashboard.html` and `/sdlc-doctor` point to the viewer. The developer commands in
    the README and CONTRIBUTING compile and self-test `view.py`.
  - `AGENTS.md` updates the docs-size figure (about 87,000 tokens) that agents budget
    their reading by.

- **Live mode: `sdlc.py view --serve`.** The view is served on 127.0.0.1 and redraws
  within a couple of seconds of a record changing or a new commit. It keeps the open tab,
  folds, filters, open panels and scroll, and waits while you type in a filter.
  - The page checks a cheap fingerprint and fetches the model only when it moves. The
    server rebuilds at most once per interval, however many tabs are open, and keeps the
    last good model if a record is caught half-written.
  - The header shows "Live" or "Disconnected". A stopped server leaves the last data on
    screen.
  - It serves exactly three read-only paths and refuses a Host header that is not this
    machine. The page carries record contents, so DNS rebinding cannot reach it.
  - `--port` (default 8765, the next free one if taken, `0` for any) and `--interval`
    tune it. It needs Python 3.7 or newer.

## 3.4.0 — 2026-09-29

This release also carries the 3.3.0 changes below, which went out under that version
number without their own heading.

- **`sdlc.py view`: the records drawn as an interactive page.** It reads the backlog,
  worklog, plans, reviews, defects, postmortems, ADRs and git history each time it runs, and
  joins them by work item ID. The page has a map, board, activity feed, waiting-on-you
  queue, item pages with a lifecycle stepper, documents with an outline, and search.
  - The page goes to `.ai-sdlc/view/index.html`, which git ignores, and works offline.
    Record text is only ever inserted as text.
  - Rows it cannot read are listed on the page rather than dropped.
  - `view.py` and `view.html` are installed and upgraded with the runtime.
- **`sdlc.py metrics`: process measures from the records and git.** Each is labelled
  leading or lagging and names its source: work in progress, time waiting on a human,
  verify pass rate, throughput, lead time, Done items with a lifecycle gap, and plans
  updated after the build started. The view's home page shows them too.
- **The lessons loop:**
  - `AGENTS.md` §9 gains "Known agent mistakes".
  - `/sdlc-review` and `sdlc-postmortem` add a line there when a finding is seen a second
    time, and propose a hook or check when the mistake is decidable from a tool call.
  - `doctor` warns when the list passes 30 lines.
- **Evaluating the agent's own setup** (`04-quality-gates.md`): 20–50 real tasks, run when
  `AGENTS.md`, skills, hooks or the model change. Every S0/S1 caused by the agent's
  behaviour adds one.
- **Agents in pipelines and environments** (`04-quality-gates.md`):
  - The agent acts up to the production gate and never past it.
  - Agent CI jobs start read-only and write only as PRs, with short-lived scoped
    credentials.
  - Rollback is rehearsed; `doctor` warns when a runbook's "Last executed" date is missing
    or stale.
  - The charter's Environments table gains "What an agent may do there".
- **Findings enter as intake items** (G6, `sdlc-intake`): alerts, scheduled scans and
  pipeline triage get the same five-line intake as a person's request. Dismissals are
  recorded with a reason.
- **One system of record per kind of record**: a charter row and a rule in
  `07-traceability.md`.
- **OPSEC:**
  - Secrets and personal data never go into a record (`AGENTS.md`).
  - `security.md` gains a checklist for the coding agent's own access, and severity rows
    for pasted secrets, readable secrets and unvetted agent tooling.
  - `sdlc.py verify` masks credential-shaped strings in saved logs and says so.
- **Skill, instruction or check?** A decision rule and a "test that it fires" step in
  `optional/skills/README.md`.
- **Worktrees** (`10-multi-agent.md`): one claimed item per working tree, split by the
  plan's files.
- **Claude harness examples** (`optional/harness/claude/`, never installed): a
  `settings.example.json` that keeps secrets out of reach, with the sandbox on, and a
  `verifier` subagent that reports and never fixes.
- **Fixes:**
  - `secret-guard` missed a credential in a repository's first commit made with
    `commit -a`.
  - Removed the legacy display name for the Advanced acquisition profile.
  - Two README claims that cited no source were rewritten to rest on the kit's own
    reasoning.

- **The kit is now called Nuhut** (chickpea), with a logo and a lifecycle diagram in
  `assets/`. Only the name in prose changed: installer messages, the README, the
  `AGENTS.md` header comment, the dashboard, and the LICENSE holder. The `/sdlc-*`
  commands, the `.ai-sdlc/` paths, the plugin ID and the install commands keep the working
  name `ai-sdlc`, so existing installs upgrade unchanged. The README says whether the kit's
  effect on agents has been measured (not yet).

- **Security: the hooks failed open** in three cases an agent can hit by accident. All three
  are fixed and pinned by smoke tests.
  - **Run from a subdirectory:** the hooks were registered as `sh .claude/hooks/x.sh` and
    read `.ai-sdlc/*.txt` relatively. They are now registered through
    `$CLAUDE_PROJECT_DIR` and run from the project root.
  - **A path through `.` or `..`:** it slipped past the glob. Paths are now normalised
    before matching.
  - **A filename containing a quote:** it produced invalid JSON, which the harness treats
    as allow. Every decision is now built by `jq`, through the new shared
    `.claude/hooks/lib.sh`.
  - **Upgrades:** hooks are now kit-managed. `--upgrade` refreshes them and re-anchors
    older registrations in `.claude/settings.json`. Hook files from before this need
    `--upgrade --adopt`, and the upgrade says so.
  - The kit-value benchmark README now says to run bypass-mode runs in a container or VM.

- **Rules the kit only asked for are now enforced** (from a gap analysis against
  Anthropic's AI-native SDLC playbook, whose core rule is "a skill is advisory, a hook is
  deterministic"):
  - Three new opt-in hooks (`--hooks`), all deny-only, since a `deny` holds in every
    permission mode and a documented `ask` does not:
    - `test-lock.sh` denies edits to a reproducing test listed in
      `.ai-sdlc/test-lock.txt`, and to that list.
    - `secret-guard.sh` denies a commit whose staged additions carry a provider-shaped
      credential. It names the kind, never the value.
    - `approval-gate.sh` denies a command matching `.ai-sdlc/gates.txt` unless the session
      was started with `AI_SDLC_APPROVAL=<ticket>`, and denies edits to that list.
  - Each list file is seeded with comments only, so no hook does anything until the
    project adds a line.
  - `05-change-control.md` gains "Fixing a defect": commit the failing reproducing test
    first, lock it, then fix without editing it. `roles/qa.md` defect triage points
    there.
  - `AGENTS.md` §9 says which approvals get a gate. Existing installs keep their §9, as
    `--upgrade` never touches it.
- **Plans can be checked against the diff**:
  - `templates/plan.md` gains "Files that change", "Order of work" and a **Proof** line
    in the test strategy.
  - `sdlc.py plan-check <ID>` lists files the branch changed that the plan does not
    name, and planned paths nothing touched. Plans that predate the new section are read
    from their "Affected surfaces → Code" bullet, `{a,b}` sets included, and
    `<ID>-<slug>.md` names are found.
  - Tried read-only on the plans of two existing installs.
- **Review has a conformance pass and a nit cap**:
  - `02-role-reviews.md`, `/sdlc-review` and `templates/role-review.md` open every Tier
    1/2 ship review with a conformance pass: plan-check, each acceptance criterion traced
    to code and test, and out of scope held. It carries its own severity table.
  - Reviews report at most five S4 findings; the rest are given as a count.
  - The Important/Nit vocabulary is mapped onto the S0–S4 ladder.

- **A runtime for the mechanical half of doctor and verify** (`.ai-sdlc/bin/sdlc.py`,
  installed always, kit-managed, added to older installs by `--upgrade`):
  - `sdlc.py doctor` checks from the files what `/sdlc-doctor` used to ask the model to
    read: unsubstituted placeholders, a missing contract pointer, blank charter commands
    and approvers, undecided modes and roles, stale `last-reviewed` dates, Done items with
    no worklog entry, IDs that do not join across the backlog, worklog and git, worklog
    size, and profile drift. Findings are `fail` or `warn`, and `--strict` exits 1 only on
    `fail`, so a fresh install does not break CI.
  - `sdlc.py verify` runs the charter's `checks.*` commands in the verify order, and writes
    each stage's raw output, exit code, duration and log hash to
    `.ai-sdlc/evidence/<timestamp>/`, which git ignores. A "Verified" claim can now cite a
    file the script wrote.
  - `/sdlc-doctor`, `/sdlc-verify`, and the `sdlc-doctor` and `sdlc-evidence-check` skills
    run the script first and keep only the judgment: severity, behaviour, what to fix
    first. By hand is the fallback when the script or `python3` is absent.
  - Tried read-only on two existing installs. On one it found six worklog IDs missing
    from the backlog, a 3,272-line worklog past rotation, and a profile whose commands were
    never filled in. On the other it found a charter that predates the mode rows.

- **Kit-value benchmark** (`benchmarks/kit-value/`): a pinned, repeatable comparison of
  no kit, the kit, and the kit with `--hooks`, over five fixture tasks (a shared-caller
  bug, a trust boundary, a one-word typo, a refactor, and a verification trap whose suite
  cannot pass). Besides correctness and cost it measures fabricated verification claims
  (commands claimed as passing that the transcript never ran), commit and worklog
  traceability, and records created for a Tier 3 change. `run.py` isolates each run in a
  fresh workspace and a throwaway Claude config; `score.py` refuses N<4 and reports each
  arm against the control. No result is claimed yet.
  - The effort-mode scorer's validation now lives in `benchmarks/lib/scoring.py`, shared
    by both benchmarks. Its CLI and output are unchanged.
  - `validate.py` runs both scorers' and the measurement self-tests, and checks each task
    has its prompt, fixture and checks. `tests/smoke.py` drives the runner end to end
    with a fake agent.

- **Ephemeral test environment lifecycle and teardown**:
  - `AGENTS.md` (§7 & §8) and `CARD.md`: added a binding rule requiring agents to
    tear down ephemeral test environments (Docker containers, compose services,
    mock daemons, local test servers) immediately upon completion (pass, fail,
    or abort), leaving no idle containers or orphaned processes on the dev host.
  - `process/00-operating-model.md`: step 5 (`VERIFY`) mandates environment teardown
    before entering `SHIP REVIEW`.
  - `process/03-ready-and-done.md`: added a Definition of Done gate under Quality
    requiring all test environments to be stopped and host resources released.
  - `process/04-quality-gates.md`: added an Ephemeral test environments & resource
    teardown section with lifecycle encapsulation, resource bounds, and an S3/S2
    severity rating for orphaned test resources.
  - `roles/devops-sre.md` and `roles/qa.md`: added host & test-environment hygiene
    to design-review, ship-review, and severity calibration tables.
  - `templates/test-plan.md` and `charter.md`: added a dedicated test environment
    lifecycle table and command encapsulation guidance.
  - `optional/claude-commands/sdlc-verify.md`: added step 7 for teardown.

- **Corrections to the 3.3 additions**:
  - `project/defects/` now exists, with an index; two documents already pointed at it.
  - `templates/defect-report.md` no longer carries its own copy of the severity ladder,
    which had already drifted (it left out cross-tenant exposure and latent S0-class
    defects). It points at `04-quality-gates.md` instead.
  - `roles/qa.md` defect triage places an S2 in `Now` unless a named human waives it,
    matching the ladder, instead of `Next`.
  - `03-ready-and-done.md`: an upstream spec satisfies readiness only when it actually
    contains an observable outcome, testable criteria, and its open questions — as
    `sdlc-intake` already said.
  - `roles/security.md`: a charter that does not require MFA means the reviewer does not
    block on it, not that the reviewer may not mention it. Privileged access without MFA
    is recorded as a risk.

- **Upgrades reach `AGENTS.md`, the commands, and the charter**:
  - `AGENTS.md` now marks sections 1–8 as kit-managed. `--upgrade` replaces them and
    records their checksum, so a local edit there stops the upgrade instead of being
    overwritten; section 9, "Project overrides", is never touched. Before this, an
    upgraded project's process documents referred to effort modes and a solution ladder
    that its `AGENTS.md` did not contain.
  - The `/sdlc-*` commands are managed files, tracked in the manifest like the docs.
  - The charter gains, blank and in the right table, any row a newer kit added — never an
    edit to an existing row.
  - `--adopt` takes over `AGENTS.md` and the commands in a project installed before this
    version, once, after a backup. A plain `--upgrade` says when it is needed.
  - `-y` writes a mode row only when `--effort-mode` or `--acquisition-profile` was given.
    A row still listing every option is *undecided*, and `/sdlc-doctor` reports it as a
    question rather than an invalid value.

- **Deployment platform checklists; the core is stack-neutral again**:
  - The process documents, role playbooks, charter, and release runbook no longer name a
    vendor. The previous additions of Dokploy, Traefik, Cloudflare, GA4/GTM, Search
    Console, AWS, and GCP specifics — and the pre-filled environment rows and example
    URLs in the charter and runbook, which an agent would have read as facts — are
    replaced with neutral checks and blank rows.
  - The platform-specific failure modes moved to `optional/platforms/`, one checklist per
    platform: Cloudflare Workers & Pages, Cloudflare in front of an origin, Vercel,
    Netlify, Fly.io, Railway, Render, Heroku/Dokku, Dokploy, Coolify, Kamal, a
    self-managed VPS, Kubernetes, AWS, Google Cloud/Firebase, Azure, and DigitalOcean App
    Platform. Each installs into `docs/platforms/` only for a platform the project uses.
  - The installer detects platforms from deploy configuration (never from an SDK import,
    and never from a bare Traefik label), pre-selects them in a new wizard question, and
    records the answer in the charter's new **Deployment platforms** row and in
    `profile.json` → `deploy_platforms`. `--deploy <list>` answers it for `-y` runs;
    detection alone installs nothing.
  - `roles/devops-sre.md`, `sdlc-release`, the release runbook, and `/sdlc-doctor` read
    the row and its checklists. `validate.py` keeps the catalog, the files, and the index
    in step.

- **Lean / Normal / Beast effort modes**:
  - Added a project default plus explicit work-item override, resolved independently of
    risk tier. Lean minimises optional work, Normal keeps the balanced workflow, and
    Beast maximises investigation and verification without widening product scope.
  - Added the repository → standard-library → native-platform → installed-dependency →
    minimum-custom-code ladder and root-cause caller tracing to the operating contract.
  - Added installer flags, charter fields, profile schema 2, plan/worklog recording,
    reviewer/subagent propagation, validation, and upgrade-safe defaults.
- **Separate acquisition profiles**:
  - Replaced the ambiguous Beast scraping waiver with `Standard` and `Advanced`
    capability profiles. `Advanced` enables additional
    extraction techniques on owned or explicitly authorised targets.
  - Reachability no longer substitutes for permission: authentication, paywalls,
    CAPTCHA, explicit denial, and other access controls remain stop conditions without
    target-owner authorisation or an approved route.

- **External Services & Platform Awareness (Cloudflare, SSL, Search Console, GA4/GTM, AWS/GCP)**:
  - Expanded `charter.md` Stack & Sources of truth tables to explicitly register Cloud providers,
    CDN/Edge/WAF (Cloudflare/CloudFront), SSL/TLS certificates, Search Console verification, and GTM/GA4.
  - Added operational checks in `roles/devops-sre.md` for CDN cache invalidation, SSL termination
    (preventing flexible SSL redirect loops), and Cloud IAM least-privilege.
  - Added verification checks in `roles/seo.md` to prevent accidental clobbering of Search Console
    ownership verification tags/files and ensure sitemap delivery.
  - Added Tag Manager governance in `roles/cro-analyst.md` to prevent GTM scripts from violating CSP
    and enforce environment separation for analytics stream IDs.
  - Updated `templates/release-runbook.md` with post-deploy CDN cache purge and SSL/domain health smoke checks.
- **Flexible Access Level Models & Opt-In MFA/OTP**:
  - Added explicit `Access level model` (`Public`, `Simple`, `RBAC`, `Workspace-Scoped`, `ABAC`)
    and `MFA / OTP policy` (`Not required`, `Optional`, `Enforced for Admin`, `Enforced for all`)
    settings in `charter.md` and `templates/security-privacy.md`.
  - Calibrated `roles/security.md` to prevent dogmatic enforcement of MFA/OTP when declared
    not required, while adding checks for standard practices: auth endpoint rate-limiting,
    CORS/CSRF protections, and session invalidation on password reset.
- **Defect tracking & tester bug reports**:
  - Added `templates/defect-report.md` for capturing tester bug reports, reproduction
    steps, observed vs. expected behaviors, and severity calibrations.
  - Added defect triage and backlog-injection workflows in `roles/qa.md`,
    `07-traceability.md`, `CARD.md`, and the `templates/` registry in `docs/README.md`.
- **Spec-driven development (Spec Kit / Kiro) integration**:
  - `/sdlc-plan` and `sdlc-intake` now explicitly ingest upstream specification files
    (e.g., `specs/`, `spec.md`, or Spec Kit artifacts), adopting problem definitions,
    user stories, and acceptance criteria without asking redundant questions.
  - `03-ready-and-done.md` clarifies that an upstream spec satisfies the FRAME Definition
    of Ready criteria (outcomes, testable criteria, bounded unknowns).
  - `plan.md` and `test-plan.md` templates gained explicit acceptance-criteria mapping
    to connect Given/When/Then scenarios and negative assertions directly into test suites.

## 3.2.0 — 2026-09-03

The question this release answers is whether the kit needs a GUI. Researched rather than
guessed, the answer was: one small read-only page, and distribution — not a web product.
Steering an agent session belongs to the agent harness itself (such as a terminal, an IDE
integration, or Claude Code Remote Control), while the repository kit provides read-only
visibility over the project's records.

### Added

- **`docs/dashboard.html`** — a read-only status page over the installed state. Open it
  from the filesystem; no server, no dependency, no build. Shows open work by status and
  tier, artifacts stale or undated, roles unticked with nobody's reason, check stages with
  no command, budgets and baselines, and whether anything points at `AGENTS.md`.
  The page is kit-managed and upgradeable; its state lives in `docs/dashboard-state.js`,
  a project record derived from the files and never from the wizard's answers. It states
  its own generation date and declares itself untrustworthy past the charter's staleness
  window. `validate.py` fails if it invents a backlog status the standard lacks, or if a
  form or `contenteditable` appears in it.
- **`/sdlc-doctor` refreshes the page's state** and is told not to write a value it did
  not read from a file.
- **Claude Code plugin packaging** (`.claude-plugin/`) — `/plugin marketplace add
  rezar-84/nuhut.ai`. Commands only: skills are model-invoked and cost context in
  every turn whether they fire or not, so choosing them per project stays with the
  installer, which is the whole point of the fact model.
- **README positioning** for Spec Kit, Kiro and Tessl (complementary — they specify a
  feature, this governs a change), for the AI app builders (a place to install this, not a
  thing to replace), and for why there is no web UI.

### Not built, deliberately

A web installer, and a Lovable-style surface driving local agents. Both are argued in the
README and the decision record; the second belongs in a separate repository that consumes
this kit, if it is ever built at all.

## 3.1.0 — 2026-09-03

Profiling 3.0.0 found three defects and one cost regression. This release fixes them and
makes the kit work outside Claude Code.

### Fixed

- **The kit could install itself into permanent silence.** The `CLAUDE.md` pointer was
  written only when no `CLAUDE.md` existed — which is almost never in a real project — so
  `AGENTS.md` was never auto-loaded and nothing was printed about it. An existing
  instruction file is now appended to (never overwritten), re-running adds no second
  pointer, and an install that wires nothing warns loudly and prints the line to add.
- **A compact install could never be upgraded**, because `find_docs()` used a numbered
  process document as the marker for an installed kit.

### Added

- **`docs/CARD.md`** — the operating card. 2,252 tokens covering tiers, the seven
  evidence words, the check sequence, the severity ladder, verdicts and traceability. It
  replaces reading `02`, `04`, `06` and `07` for ordinary work; those become named
  escalation, and the full document wins wherever they disagree. `validate.py` reads the
  rules the card actually asserts and fails if it invents or drops one.
- **`--harness <list>`** — pointer files for Claude Code, Gemini CLI, Amp, Copilot,
  Cursor, Windsurf, Cline and Aider. Codex, Jules, Zed, Factory and opencode read
  `AGENTS.md` directly and are told so. Pointers reference; they never copy.
- **`--profile compact`** — installs the card, roles, templates and project records but
  omits the numbered `process/` documents. For a small context window or a weaker model.
- **`--hooks`** — two deterministic Claude Code guards: a commit with no work item ID is
  denied, and an edit to a path in `.ai-sdlc/protected.txt` is denied. Merged into an
  existing `settings.json` without disturbing it.
- **`process/10-multi-agent.md`** — claiming, single-writer files, review fan-out, why a
  subagent's result is *Reported* and not *Verified*, and handoff. Conditional.
- Charter: **Agent environment** and **Concurrency** tables. `/sdlc-doctor` checks that
  something points at `AGENTS.md` and rates its absence the highest finding it can make.

### Changed

- **The always-list costs 11,624 tokens instead of 18,222** — a 36% cut, and 26% below
  where 3.0.0 started. A Tier 2 change with two roles: 22.7k full, 17.3k compact.
- `AGENTS.md`'s per-tier figures are measured, and CI fails if they drift.

### Upgrading

`--upgrade` delivers `CARD.md` and `10-multi-agent.md`. Merge the `AGENTS.md` reading-list
changes with the printed `diff` — Tier 2 and Tier 1 now read the card instead of four
process documents, and that is the whole token saving. Copy the new charter tables if the
project needs them. `--harness`, `--profile` and `--hooks` apply to a fresh install.

## 3.0.0 — 2026-09-03

The kit covered web and content projects well and engineering-heavy ones barely. This
release closes that without growing what a web project *reads*: every review, skill, and
gate is fact-gated, and a content site's role roster and installed skills are byte-for-byte
what 2.5.0 produced (a smoke test asserts exactly that).

What does grow is the portable tree on disk. `docs/process/`, `docs/roles/`, and
`docs/templates/` are installed whole in every project, as they always have been, so that
`--upgrade` can manage them and a project can activate a role later without reinstalling.
A content site therefore gains eleven files it never opens: the reading list in
`AGENTS.md` §3 is what bounds an agent's context, and an inactive role's playbook is not
on it. `09-probabilistic-and-data-systems.md` says so in its own opening line.

### Added

- **`Measured`**, a seventh word in the verification vocabulary, for results that are
  numbers rather than passes. It carries method, subject version, N, spread, and date, or
  it is not a claim. A metric with no baseline is not an improvement, it is a number.
- **`process/09-probabilistic-and-data-systems.md`** — models, prompts, retrieval,
  datasets, pipelines, and acquisition. Read only when a change touches one.
- **Three role playbooks**: `data-engineer`, `ml-engineer`, `performance-engineer`.
- **Four extensions to existing playbooks**: `architect` gains asynchronous and
  distributed review plus a clean-code block; `security` gains supply chain and AI/agent
  surfaces; `qa` gains testing non-deterministic systems; `privacy-legal` gains acquired
  data, third-party inference, and generated-content disclosure.
- **Six templates**: `eval-plan`, `data-contract`, `pipeline-runbook`,
  `performance-budget`, `service-catalog`, `model-and-dataset-card`.
- **Seven skills**: `sdlc-eval-gate`, `sdlc-data-contract`, `sdlc-migration`,
  `sdlc-service-contract`, `sdlc-perf-budget`, `sdlc-scrape-compliance`, and
  `sdlc-doctor` (installed always).
- **Four conditional check stages** — `checks.infra`, `checks.data`, `checks.eval`,
  `checks.perf` — with charter rows, installer questions, and CI scaffolding.
- **`.ai-sdlc/profile.json`**, the charter in machine-readable form, so a command or
  skill can branch on the project's facts and commands without parsing prose. The
  charter remains the source of truth and wins on conflict.
- **`/sdlc-doctor`**, the first check that audits an installed project rather than the
  kit's own source: placeholders, blank commands, undecided roles, stale artifacts,
  traceability gaps, worklog size, profile drift.
- Detection for ML/LLM, vector stores, data orchestration and warehouses, messaging,
  IaC, acquisition, and load tooling — each feeding a project-type default.
- A worklog rotation threshold in `07-traceability.md`. The worklog is on the always-read
  list and grew unbounded, one invisible entry at a time.
- Cross-reference validation (roles, templates, skills, and check stages must agree
  everywhere they are named) and a guard that fails if `AGENTS.md`'s stated docs-tree
  size drifts from the measured one.

### Changed

- **Twelve project types and eleven facts**, up from eight and six. `TYPE_FACTS` is keyed
  by fact name rather than position.
- `/sdlc-verify` reads the profile for exact commands, runs the conditional stages, and
  reports `Measured` where the result is a number.
- `AGENTS.md`: prompt, model, retrieval, dataset, and contract changes have explicit tier
  triggers; the reading-list token figures are now measured rather than estimated.
- The installer derives charter command labels from the stage key instead of zipping
  against a parallel list.

### Upgrading

`--upgrade` delivers the new process document, role playbooks, and templates to an
existing installation, and leaves `AGENTS.md` and `docs/project/` alone as always. Two
things need a hand:

- Merge the `AGENTS.md` changes (sections 2, 3, 5, and 7) with the printed `diff`.
- The new charter sections — **Budgets**, **Model & data**, **Data ownership**, the three
  role rows, and the four `checks.*` rows — are not added to an existing charter, because
  the file is project-owned. Copy them from `template/docs/project/charter.md` if the
  project has those surfaces.

New skills are not added by an upgrade; `ls optional/skills` shows what is available.

## 2.5.0 — 2026-08-23

### Added

- Stack adapters for Node/TypeScript, Python, Go, Rust, PHP, Ruby, Maven/Gradle, and .NET.
- ORM, database-driver, migration-tool, and testing-tool detection across those ecosystems.
- `--scaffold-tests` for an instantiated test plan and machine-readable testing profile.
- `--scaffold-ci github|gitlab` for opt-in pipelines generated from confirmed commands.
- Adapter and scaffolding fixtures covering supported language and database families.
- Polyglot command composition so every detected language participates in each quality stage.
- Manifest-managed template upgrades, allowing new testing and data-model guidance to
  reach existing installations without touching project records.

### Safety

- Scaffolding never installs dependencies and never overwrites existing test plans,
  profiles, or CI configuration.
- CI generation refuses repositories with no detected or confirmed quality commands.
- Generated CI is manual-only until a human confirms commands, runtimes, and services.
- Generated database guidance requires real-engine integration tests, migration/restore
  exercises, and synthetic test data.

## 2.4.0 — 2026-08-23

### Added

- Machine-readable manifests for portable managed files.
- Upgrade preflight checks, backups, obsolete-file cleanup, atomic writes, and rollback.
- Stack-neutral validation, continuous integration, and tag-based release automation.
- AI prompt-injection, secret-disclosure, and permission-escalation boundaries.
- Repository licensing, contribution guidance, and a security policy.
- Detection for integration, contract, accessibility, and common namespaced test scripts.

### Changed

- `--docs-dir` now updates the operating contract and Claude commands completely.
- Tier 3 uses a compact reading and worklog path.
- Dry runs and pre-confirmation quits no longer create target directories.
- Detected format, install, typecheck, and lint commands favor non-mutating,
  reproducible, locally installed tools.

## 2.3.0

- Added the navigable installer, localisation role, and architecture seeding.

Earlier history is available in the repository's Git log.

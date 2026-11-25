---
status: current
owner: architect
last-reviewed: 2026-11-22
---

# Review — NUHT-016 v6 roadmap, built: the kit-v6 branch before it merges

**Stage:** ship **Tier:** 1
**Author:** claude-code
**Reviewer agent:** fresh-context subagents, one per lens (correctness, security, usability), each finding then verified by a second subagent
**Reviewer model:** claude-opus-5-5 (same model family as the author)
**Independence:** self-check (same model family; charter `Independent review required for: none`)
**Reviewed:** `main..kit-v6` at `8964d1e`: `optional/runtime/*.py`, `optional/extensions/github-issues/issues.py`, `install.py`, `tools/semver.py`, `tests/smoke.py`, `tests/unit/test_semver.py`, `CHANGELOG.md`, `docs/cli.md`, `docs/extensions.md`, `docs/install.md`

A self-check clears nothing on its own. The two human approvals for this Tier 1 work are
still owed, and finding 18 is escalated to a person.

---

## Conformance (ship review, Tier 1 and 2)

**Acceptance criteria:** the branch must pass its own smoke suite on Python 3.8 and compute
the release its notes describe (6.0.0). Before the fixes, five smoke checks failed and
`tools/semver.py next` printed 5.1.0. After them, the five named checks pass and
`semver.py next` prints 6.0.0 (finding 1 and 21).

**Out of scope held:** the fixes change no backlog, worklog or item status, and no release
was cut.

**How the fixes were checked:** every code fix has a check in `tests/smoke.py` or
`tests/unit/test_semver.py`, either new or the one that was already failing. Each new
check was first run against an archive of the branch before the runtime fixes, and failed
there. Then 38 affected test functions were run one at a time on Python 3.14, and the
key ones again on Python 3.8.20. `python3 validate.py` passed. Findings 21, 25 and 32 are
checked by `validate.py` or are docs only. The full suite was not run.

**Commits:** `fefac67` (NUHT-014), `593ccb1` (NUHT-012), `ecee839` (NUHT-013), `ef33b5e`
(NUHT-027), `e3d1222` (NUHT-032), `b13d70d` (NUHT-026), `5528b9a` (NUHT-024), `4b3a2d0`
(NUHT-018), `5c9afc5` (NUHT-030), `2253924` (NUHT-022), `5a813bd` (NUHT-031), `01555ab`
(NUHT-020), and this record with the CHANGELOG (NUHT-016).

---

## correctness, security, usability

**Verdict:** Pass with fixes. One finding is escalated (18). Two are declined in part (17, 23).

**Checked:** attribution (`trailers`, `item_commits`, `mentioned_only`, the commit-msg
hook); trusted records (`trusted_ref`, `trusted_text`, `registry.trusted_allowed`, the
extension pins); waivers and approvals in `finish.py`; the shell guard and trust anchors
in `hooks.py`; the release tooling; the installer's upgrade path; `ext`, `status`,
`claim` and the help text.

**Not checked:** hosted GitHub behaviour (branch protection, `actions/checkout` refs),
Windows, and the full smoke suite under load.

### Findings and responses

| # | Sev | Location | Finding | Response | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | high | `tests/smoke.py` | The smoke suite fails on kit-v6 (5 checks), so CI and the release job fail | Fix | Each named check passes after the fixes below: `upgrade touches only standards` (8), `trailers are read from the last paragraph only` (3), `Verified with no ledger run for the item is flagged` (4), `--help is short and grouped` (installer help back to 60 lines; it had grown with `--mcp`), and `test_distributed_git_refs` (9) |
| 2 | high | `tools/semver.py:80` | `BREAKING CHANGE` read only from the last paragraph, so a footer before a `Co-Authored-By` paragraph releases as minor | Fix | `footer()` is the trailing run of paragraphs that start with a footer token; `test_breaking_footer_before_a_trailer_paragraph_is_major` |
| 3 | medium | `optional/runtime/sdlc.py` `trailers()` | Any earlier `Key: value` paragraph merges into the trailer block | Fix | An earlier paragraph joins only when the last one has none of Work-Item, Agent, Model; the existing smoke check passes |
| 4 | medium | `hooks.py` commit-msg, `check_verified_claims` | The hook accepts commits nothing attributes; Verified claims for them are skipped | Fix | `doctor` warns on a Verified entry for an item in `mentioned_only()`, which now also catches a wrong-case `Work-Item:`; the hook warns when it accepts a message without an exact trailer |
| 5 | medium | `sdlc.py` `trusted_text` | `git show ref:rel` fails when the kit is in a subdirectory | Fix | `show_at()` reads `ref:./rel` (sdlc.py and registry.py, also `_ci_charter_rows`); `test_trusted_records_review` monorepo checks |
| 6 | medium | `install.py` `apply_deploy_attributes` | A non-UTF-8 `.gitattributes` aborts the install half-written | Fix | Caught, file left alone, line to add printed; `test_install_review_fixes` |
| 7 | medium | `hooks.py` pre-commit | `protected.txt` now blocks every human commit after upgrade | Fix | Pre-commit applies `protected.txt` only in an agent's session (5.x semantics); `test-lock.txt` binds everyone; documented in `05-change-control.md`, CHANGELOG and `docs/install.md`; `test_shell_write_guards` |
| 8 | low | `install.py` upgrade note | The blank-Approvers note names the charter path and breaks a smoke check | Fix | The note no longer names the path |
| 9 | low | `sdlc.py` `release` alias | Deprecation line on stderr breaks merged-stream JSON | Fix | With `--json` the note is a `deprecated` field; `test_unclaim_alias` |
| 10 | low | `claims.py` port lock | A timed-out port lock still allocates a port | Fix | The claim is refused; `test_worktree_scripts` |
| 11 | low | `tests/unit/test_semver.py` | No test tells the old and new footer rules apart | Fix | Two cases added: trailer paragraph after the footer (major), token in a body paragraph (patch) |
| 12 | high | `sdlc.py` `default_branch`, `registry.trusted_allowed` | A branch names itself the default branch and so the trusted ref | Fix | `registry.trusted_ref()`: origin/HEAD first (followed to the branch its own charter names), then `$GITHUB_BASE_REF`, then the working tree; `test_trusted_records_review`. Residual: a repository with no remote still takes the working tree's row |
| 13 | high | `registry.py` pins | Code pins come from the working-tree manifest | Fix | Code loads only while the hash also matches the pin on the default branch (`trusted_pins`); `test_trusted_records_review` |
| 14 | high | `finish.py` stored waivers | A hand-written ledger row with `waived_by` closes an item | Fix (partial) | A recorded waiver is held to `check_waiver` in the run that uses it, so an agent's run without a terminal cannot use one; the ledger and its shards are trust anchors. Not done: binding waivers to a signature |
| 15 | medium | `finish.py` `check_waiver` | The agent check passes whenever git user.name is the human's | Fix (partial) | Without a terminal, any detected agent environment refuses the waiver; `test_finish_evidence_binding`. Residual: a process that unsets those variables |
| 16 | medium | `hooks.py` shell guard | `node`/`ruby`/`perl -e`, heredocs, rsync, tar, git apply get through | Fix | Interpreters and stdin scripts count as inline code; rsync, tar/unzip, patch and git apply are recognised; `test_shell_write_guards` (16 new cases) |
| 17 | medium | `hooks.py` `_trust_anchors` | Anchors miss the guard code, profile, hook wiring and ledger; pre-commit enforces none | Fix, Decline in part | Fixed: `.ai-sdlc/bin/**` (outside the kit's own repo, where it is copied from tracked sources), `profile.json`, `git-hooks/**`, hook settings files, the ledger. Declined: anchors in pre-commit. Those records are read from the default branch now (12, 13), so committing them on a branch changes nothing until merge, and the files that run from the working tree (`.ai-sdlc/bin`, settings) take effect before any commit, so a commit check adds no protection while it would block every agent install, upgrade and verify commit. Declined: the charter rows, since the Default branch row no longer decides the trusted ref (12) |
| 18 | medium | `finish.py` `approvals` | Any mapped non-author reviewer counts; Approvers and roles are not checked | Escalate | Changing a Tier 1 governance gate needs human approval (AGENTS.md section 9), and the NUHT-024 plan chose this rule. A person decides whether a review counts only from **Approvers**, and how domain ownership is checked |
| 19 | low | `issues.py` `pull` | Anyone's issue title can link an item or enter the backlog | Fix | Title linking only when people.json maps the author's login; other imports say their title is untrusted text; `test_issue_sync` |
| 20 | medium | `sdlc.py` `trailers` | Prints `Model: unknown` with no warning inside an agent | Fix | stderr warning naming `--model` and `AI_SDLC_MODEL`; `05-change-control.md`; `test_ci_check` |
| 21 | high | `CHANGELOG.md` | Notes say 6.0, the release computes 5.1.0 | Fix | Commit `fefac67` carries a `BREAKING CHANGE:` footer; `semver.py next` prints 6.0.0; `validate.py` fails when an "Upgrading to N.0" heading and the computed release disagree |
| 22 | high | `docs/extensions.md:114` | The example's range refuses the computed release | Fix | Resolved by 21; `validate.py` checks the example ranges in the guide and ADR 0003 against the next release |
| 23 | medium | `hooks.py` work-item guard | The denial asks for an ID in the message; trailers are what count | Fix, Decline in part | The denial asks for the `Work-Item:` trailer and the hook warns on an unattributed commit. Declined: refusing the 3.x forms (`#N`, `GH-N`, subject IDs), which existing projects' hooks accept and a smoke check holds; the warning and doctor (4) cover them |
| 24 | medium | `finish.py` `approvals` | Every non-Tier-1 item needs 1 approval | Fix | Tier 1 needs 2, Strict Tier 2 needs 1, others 0 with exit 0; `test_github_approvals` |
| 25 | medium | `sdlc.py` `MAIN_HELP` | `--help` has no `ext`; cli.md groups miss ext, dispatch, merge-shard | Fix | `ext` under Setup, extension commands before the footer, cli.md groups updated |
| 26 | medium | `sdlc.py`, `status.py` identity | status and claim disagree with an empty people.json; wrong path in the warning | Fix | status reports the gap; the warning names `<docs>/project/people.json`; `test_status_review_fixes` |
| 27 | medium | `ext.py` catalog | `ext search` 404s and the catalog is empty | Fix (partial) | Empty catalog and fetch errors name `ext add` and `NUHUT_CATALOG_URL`; `test_extension_cli`. The 404 itself ends when catalog.json reaches main |
| 28 | medium | `ext.py` `update` | Re-pins changed live code with no prompt | Fix | Changed executable files are marked; for an allowed id it asks in a terminal and needs `--yes` without one; `test_extension_cli` |
| 29 | low | `install.py` upgrade output | 5.0.0, 5.1.0 and 6.0 in one output; `vX-to-vX` backup name | Fix | The next release computes to 6.0.0 (21); a same-version refresh names its backup by time |
| 30 | low | `status.py`, `claims.py` | An unborn HEAD shows `(no git)` and claim makes an empty worktree | Fix | status names the branch and says no commits yet; claim refuses a worktree; `test_status_review_fixes` |
| 31 | low | `install.py` `--scaffold-ci` | No detected commands aborts the whole install | Fix | The workflow is written with doctor and ci-check and a TODO naming `config --set-check`; `test_scaffolding` |
| 32 | low | `docs/cli.md:51` | `dispatch --by` lists only three tools | Fix | cli.md and the argparse help name registry agents |
| 33 | low | `sdlc.py` help IDs | Mixed ID formats; `DEMO-1` errors hide the cause | Fix | One format in the help; `hotfix` and `unclaim` name the near match; `unclaim` says when the item is not in the backlog; `test_unclaim_alias` |

### Not synced

`.ai-sdlc/extensions/github-issues/issues.py` is a trust anchor, so an agent cannot copy
the finding 19 fix into this repository's self-install. A person copies it from
`optional/extensions/github-issues/issues.py`, or runs `install.py . --upgrade`.

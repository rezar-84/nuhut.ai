# NUHT-055: Guard hooks without the false alarms, and a switch for each

Tier 1 (it changes guard gates) · feat · security. Approved by rezar-84 on 2026-11-25:
"fix all, remove hook so you can do it autonomous", then the scoped plan (shell-text guards
out, commit checks to git hooks, per-hook on/off).

## Problem

In the last session the agent hooks refused about five harmless commands:
- `git commit -m` inside a quoted string;
- a heredoc that only read `.ai-sdlc/profile.json`;
- inline code that wrote a different file.

The causes:
- The work-item and credential checks matched `git commit` anywhere in a command's text.
- The shell guards refused any inline code that *named* a guarded path, because the hook
  cannot see what such code writes.
- There was no way to turn one hook off except by editing `settings.json`.

## Change

- **Commit checks move to git hooks only.** `work-item-id` and `secret-guard` are no longer
  registered as agent hooks. git's `commit-msg` and `pre-commit` hooks read the real
  message and the staged diff. `--hooks` installs them with the agent hooks; `--upgrade`
  removes the old registrations (`retire_hook_commands`), and the scripts stay installed
  but unregistered.
- **Inline code is not guessed at.** `_shell_denial` no longer refuses inline code that
  names a guarded path. Direct writes (`sed -i`, `>`, `tee`, `cp`, `mv`, and so on) are
  still refused, and the `pre-commit` backstop catches what inline code writes once it is
  committed.
- **A switch per hook.** `sdlc.py hooks list|on|off <name>` writes
  `.ai-sdlc/hooks-off.txt`, which every hook reads before it runs, agent and git hooks
  alike. `off` is refused to an agent's session without a terminal. The file is a trust
  anchor, so an agent's edit tools cannot write it.
- **Installer help.** The installer lists each hook: what it blocks, what it cannot see,
  and how to turn it off. The summary says that commits need a trailer once hooks are on.

## Files that change

- `optional/runtime/hooks.py`, `optional/runtime/sdlc.py` (plus their `.ai-sdlc/bin/` copies)
- `install.py`
- `benchmarks/*/run.py`: the harness's own setup commit uses `--no-verify`
- `tests/smoke.py`: new `test_hooks_command`, registration counts 6→4 (Gemini) and 3→1
  (Cursor), and the inline cases move from "denied" to "left to the commit backstop"
- `docs/cli.md`, `README.md`, `CHANGELOG.md`

## Risks

- **An inline write to a locked test is no longer stopped while the agent works.** It is
  stopped at commit, and in CI.
- **Cursor and Gemini lose their shell-side commit checks.** The git hooks cover every
  tool.
- **`hooks-off.txt` can be written from the shell.** An agent could do that through
  inline code. Per ADR 0004 these hooks are guardrails, not authentication.

## Tests

`test_hooks_command` was shown failing before the change (9 of 13 checks). It covers:
- registration;
- the git hooks being installed;
- inline code allowed while a direct write is still denied;
- `list`, `off` refused to an agent, `off` and `on` by a person;
- an unknown name refused;
- `--upgrade` retiring the old entries.

## Rollback

Revert the commit and re-run `install.sh <project> --hooks`, which registers the old
hooks again. `hooks-off.txt` is ignored by older kits.

# Hooks — the rules that are not persuasion

Everything else in this kit asks an agent to follow a rule. These make five of them
mechanical, by running before the tool call rather than after the fact. A skill or a
process document is advisory, since it makes the violation rare. A hook is what makes it
close to impossible, so any rule that must hold without exception belongs here as well.

**Claude Code only**, and **opt-in**: `./install.sh <dir> <PREFIX> --hooks`. Nothing
installs them by accident, because a hook executes on your machine on every matching tool
call and that is not something to acquire without deciding to.

## What is here

| Hook | Fires on | Does |
| --- | --- | --- |
| `work-item-id.sh` | `git commit` | Denies a commit whose message carries no `<PREFIX>-###`. `AGENTS.md` §6 requires the ID in the branch, the commit and the worklog; this is the one of the three a machine can check. |
| `protected-paths.sh` | `Write` / `Edit` | Denies an edit to a path listed in `.ai-sdlc/protected.txt` — the charter's platform-owned files, generated files, or anything else single-writer. Does nothing until that file has entries. |
| `test-lock.sh` | `Write` / `Edit` | Denies an edit to a reproducing test listed in `.ai-sdlc/test-lock.txt` while its defect is fixed, and an edit to that list itself. `process/05-change-control.md`, "Fixing a defect": the agent appends the lock from the shell after committing the failing test, and a human removes it. |
| `secret-guard.sh` | `git commit` | Denies a commit whose staged additions contain a provider-shaped credential (private-key header, AWS, GitHub, GitLab, Slack, Stripe live, Anthropic, OpenAI, Google keys). Names the kind and never the value. A line containing `EXAMPLE` is skipped, for deliberate fixtures. |
| `approval-gate.sh` | `Bash`, and `Write` / `Edit` of its list | Denies a command matching a glob in `.ai-sdlc/gates.txt` (production deploys, `terraform apply`, production migrations: whatever `AGENTS.md` §9 says needs a human), and tells the agent to hand the exact command to a human. It passes when the session was started with `AI_SDLC_APPROVAL=<ticket or ID>`, which the agent cannot set from inside the session. |

All five are **deterministic**. None asks a model whether the rule was followed. The three
list files are seeded with comments only, so until the project adds a line, the hooks that
read them do nothing.

**Deny, never ask.** A `deny` is honoured in every permission mode, including bypass mode
and headless `claude -p` runs. The harness documents no such guarantee for `ask`, and a
gate that is only sometimes shut is not a gate.

**What they cannot see.** They check the tool call, not the shell's side effects. A
`sed -i` on a locked test, a new file staged and committed in one command, or a deploy
wrapped in a script with an innocent name all get past them. These hooks are guard rails
for an agent that is trying to comply. Anything that must hold against an agent that is not
trying belongs in `permissions.deny` and the sandbox.

## What is deliberately not here

An evidence hook on `Stop` — "you claimed done without running anything" — was designed
and dropped. A hook cannot reliably tell whether the command that mattered ran this
session, so it would fire on turns that did nothing wrong. A guard that cries wolf gets
switched off within a day, and it takes the two working guards with it when it goes.
Evidence stays enforced where it can be enforced honestly: `sdlc-evidence-check`, and
`/sdlc-verify` running the charter's real commands through `.ai-sdlc/bin/sdlc.py verify`,
which records each stage's output and exit code under `.ai-sdlc/evidence/` for a claim to
cite.

The same reasoning applies to anything you add here. **Only automate a rule whose
violation is decidable from the tool call itself.**

## How they hold up

Each hook sources `lib.sh` and runs from the project root, which it gets from the
harness's `$CLAUDE_PROJECT_DIR`. The installer registers them the same way. A path is
resolved against the caller's directory, its `.` and `..` segments are collapsed, and
only then is it compared with a list. Every decision is built by `jq`, so no filename or
command can break the JSON. A hook that could not produce a decision would allow the
call, so all three rules are pinned by smoke tests.

`--upgrade` keeps installed hooks current and re-anchors older `sh .claude/hooks/…`
registrations. Hooks from before they were kit-managed are replaced only with `--adopt`,
like the commands.

## Requirements and failure mode

The scripts need `jq` and POSIX `sh`. **If `jq` is missing they allow the call** and say
so once, rather than blocking your work over a missing dependency — they are guard rails
for an agent, not a security boundary. Anything that must not happen belongs in
`permissions.deny` in `.claude/settings.json`, which the harness enforces itself.

## Escaping them

Deliberately possible, and deliberately visible: commit outside the tool, or remove the
hook from `.claude/settings.json`. The point is to make the wrong thing take a decision,
not to make it impossible.

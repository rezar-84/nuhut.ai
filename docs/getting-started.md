# Getting started

From nothing to a first work item that is planned, built, verified and closed, in about
fifteen minutes.

## Requirements

- **Python 3.8+** and **git**. Nothing else: the installer and the runtime use only
  Python's standard library.
- An AI coding agent: Claude Code, Codex, Cursor, Gemini CLI, Copilot, Windsurf, Cline,
  Roo, Amp, Aider, Antigravity, Jules, Zed, Factory or opencode. Anything that reads
  `AGENTS.md` works ([the full table](harnesses.md)).
- Optional: `node` makes `validate.py` syntax-check the viewer when you contribute to the
  kit. `gh` gives the viewer GitHub issues and PRs.

## 1. Install into your project

```sh
git clone https://github.com/rezar-84/nuhut.ai.git
cd nuhut.ai
./install.sh /path/to/your-project
```

The guided setup shows what it detected (stack, check commands, AI tools) and asks only
what it cannot know: a one-line description, the work item prefix (`ACME` makes items
`ACME-1`, `ACME-2` …), what you are building, and which AI tools you use. Press `?` on any
question for an explanation. Nothing is written until you confirm the review screen, and
the installer never overwrites a file.

It adds:

| Path | What it is |
| --- | --- |
| `AGENTS.md` | The contract every agent reads first |
| `docs/project/charter.md` | Your project's settings: prefix, roles, stack, check commands, risk defaults |
| `docs/project/backlog.md`, `worklog.md` | Work items, and what actually happened |
| `docs/process/`, `docs/roles/`, `docs/templates/` | The process, read on demand, never all at once |
| `.ai-sdlc/bin/` | The runtime (`sdlc.py`) and the viewer |
| `.claude/commands/`, `.claude/skills/` | The `/sdlc-*` commands and the skills that apply to this project |

Commit it: `git add -A && git commit -m "chore: install Nuhut"`.

## 2. Check the setup

```sh
cd /path/to/your-project
python3 .ai-sdlc/bin/sdlc.py doctor
```

A fresh install reports warnings, not failures, mostly blank charter rows. Open
`docs/project/charter.md` and fill in what you know: what the project is, who it is for,
and the check commands (`checks.unit`, `checks.lint` …) if detection missed any. A blank
cell is read as *Unknown*, which is safe. A wrong one is not.

## 3. Open the viewer

```sh
python3 .ai-sdlc/bin/sdlc.py view --serve
```

Leave it open beside your agent. It follows the records as they change ([the viewer](viewer.md)).

## 4. A first work item

Ask your agent for a small, real change. In Claude Code:

```
/sdlc-plan Add a "Remember me" checkbox to the login form
```

Other tools have the same loop as skills (`sdlc-plan` …), or follow `AGENTS.md` directly.
The agent will:

1. **Frame** the request as `ACME-1` in the backlog, and pick a **risk tier** by blast
   radius and reversibility. This one is Tier 2: new behaviour, covered by tests, undone by
   a revert.
2. **Plan** it briefly: the files that change, the test strategy, the rollback.
3. **Build** it (`/sdlc-build ACME-1`), committing with trailers that name the item and the
   agent:
   ```
   Work-Item: ACME-1
   Agent: claude
   Model: claude-opus-5-5
   ```
4. **Verify** with the real commands (`/sdlc-verify`, which runs `sdlc.py verify`). Only a
   recorded run makes a result *Verified*; the run lands in the evidence ledger.
5. **Log** it (`/sdlc-log ACME-1`): a worklog entry, the backlog row moved to Done, any
   document the change made untrue corrected.

Watch the Inbox while it works: the thread fills with the plan, commits, the verify run and
the worklog entry.

A Tier 1 change (auth, stored data, money, a release pipeline, anything hard to reverse)
adds a design review, a ship review from a different model family, an ADR, and a stop
for your approval. A Tier 3 change (a typo, a test, a patch bump) is just a commit with the
item in its message.

## 5. Make it yours

- **How much the agent decides:** the charter's *Decision style* (Ask, Guide, Autopilot)
  and *Default effort mode* (Lean, Normal, Beast). Change them in the viewer under
  Project ▸ Kit settings, or with `sdlc.py config`.
- **Enforcement:** `./install.sh /path --hooks` refuses unsafe commits and edits in Claude
  Code, Gemini CLI and Cursor; `--git-hooks` does it for every tool and every person.
- **Several agents at once:** [claims, worktrees and parallel work](multi-agent.md).
- **Specs of what the system does:** [living specs](specs.md) (off by default).
- **CI:** `sdlc.py doctor --strict` and `sdlc.py verify` in your pipeline, or
  `--scaffold-ci github` for a starter.

## Upgrading later

```sh
./install.sh /path/to/your-project --upgrade
```

It replaces only kit files you have not changed, keeps every record and setting, adds new
charter rows, and backs up what it changes.

## Removing it

Everything the kit added is listed in `.ai-sdlc/manifest.json`. Remove `.ai-sdlc/`,
`AGENTS.md`, the `docs/` tree it installed, `.claude/commands/sdlc-*`,
`.claude/skills/sdlc-*` and the pointer lines in `CLAUDE.md` and similar files. Your code
is never touched. Before deleting the backlog, worklog and ADRs, decide whether to keep
them: they are your project's history.

# Agent tools and enforcement

What each layer of the kit needs from the agent tool, and what each tool gets.

## Which agent tools this works with

`AGENTS.md` is the contract, and most tools now read it directly. The rest each look in
their own file, so the installer points them at it — appending to a file that already
exists, never overwriting, and never copying the contract itself.

| Tool | Wiring |
| --- | --- |
| Codex, Jules, Zed, Factory, opencode, Antigravity | Nothing to do — they read `AGENTS.md`. Name them in `--harness` anyway to get the shared skills below. |
| Claude Code | `CLAUDE.md`, plus slash commands, skills and optional hooks |
| Gemini CLI · Amp · Copilot · Cursor · Windsurf · Cline · Roo Code · Aider | `--harness gemini,amp,copilot,cursor,windsurf,cline,roo,aider` (or `all`) |

What each layer of the kit needs from the tool:

| Layer | Claude Code | Any tool that reads `AGENTS.md` |
| --- | --- | --- |
| Contract, process, roles, templates, card | yes | yes |
| Runtime (`doctor`, `verify`, `plan-check`, `view`, `metrics`) | yes | yes — it is a shell command |
| Skills | `.claude/skills/` | `.agents/skills/`, the cross-client location of the [Agent Skills](https://agentskills.io) standard; installed when `--harness` names any tool other than claude |
| Loop commands (`sdlc-plan`, `-build`, `-verify`, `-review`, `-log`, `-doctor`) | `/` commands in `.claude/commands/` | skills of the same name in `.agents/skills/`, so they appear in a `/` menu that lists skills (Antigravity); `CARD.md` names what each runs on any tool |
| Tool-call hooks (`--hooks`) | yes | Gemini CLI: all six rules; Cursor: the three shell rules; both through `.claude/hooks/adapter.sh`. Other tools: no |
| Git hooks (`--git-hooks`) | yes | yes — git runs them for every agent and every human |
| CI (`--scaffold-ci`) | yes | yes — the doctor runs strictly before the quality commands |

```sh
./install.sh /path/to/project ACME -y --harness claude,cursor,copilot
```

**If nothing points at `AGENTS.md`, the kit is installed and inert** — and nothing about
the repository looks wrong. The installer warns when it wires nothing, and
`/sdlc-doctor` rates that the most severe finding it can report.

Skills are the same `SKILL.md` files on every tool. For a tool that does not load
skills, the routing lives in the last table of `docs/CARD.md`: *when X is true, read Y*.

## Reading cost, and small models

Measured in words, and enforced by `validate.py`. A list that grows past its budget
fails CI. `python3 validate.py --reading-lists` prints them:

| Change | Reads | 3.5.0 | 4.0 | Budget |
| --- | --- | --- | --- | --- |
| Every change | `AGENTS.md` | 3,221 | 1,177 | 1,200 |
| Tier 3 | `AGENTS.md`, the charter's Commands rows | 3,514 | 1,470 | 1,500 |
| Tier 2 | adds `CARD.md` and the backlog, then only what the change touches | 14,843 | 4,590 | 5,500 |
| Tier 1, four roles | adds the charter, three process documents, three templates, the roles | 21,779 | 19,126 | 22,000 |

The 3.5.0 figures use that version's own reading lists. Tier 2's figure is before any
role playbook, which the change's surfaces add.

`--profile compact` installs the card, roles, templates and project records but omits the
numbered `process/` documents the card summarises. One source for every rule either way —
it is a packaging choice, not a second copy written in shorter words. A Tier 1 change
then has no escalation document to appeal to, so choose it deliberately; the charter's
**Agent environment** table records which profile is installed and the minimum context
window the reading list assumes.

`--docs-dir` is for a project whose `docs/` already means something else. The installed
contract, commands, and skills all follow the chosen name automatically.

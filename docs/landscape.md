# Landscape, gaps and the v6 direction

Written 2026-11-22, after `v5.0.0`. It compares Nuhut with similar tools, lists the gaps
those comparisons show, and links each gap to a work item. The earlier comparison that shaped
4.x (Spec Kit, OpenSpec, BMAD, Kiro) is in [roadmap.md](roadmap.md). Plans are tracked in
`handbook/project/backlog.md` as NUHT-011 to NUHT-036.

## Similar tools

| Tool | What it is | Worth learning from it |
| --- | --- | --- |
| [T3 Code](https://github.com/pingdotgg/t3code) | Desktop, web and mobile GUI that drives Claude Code, Codex, Cursor, OpenCode and ACP agents | A worktree per thread, diff review, commit and PR from the app, issues pulled from Linear and GitHub. It has no process layer, so it can sit on top of a Nuhut project. |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | Spec-driven workflow (`/speckit-specify`, `-plan`, `-tasks`, `-implement`) | `extension.yml` manifests with a version range, catalogs, presets that wrap, prepend or append core templates, lifecycle hooks such as `before_plan` |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | Change proposals: propose, apply, archive into living specs | Profiles that choose which commands install; shared planning stores across repositories |
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | Persona-based agile workflow | Installable modules; `bmad status` says what to do next |
| [Kiro](https://kiro.dev/docs/specs/) | Spec IDE with hooks | Tasks run in waves from a dependency graph; JSON hook files; "Powers" that load on keyword match |
| [Agent OS](https://github.com/buildermethods/agent-os) | Codebase standards | Discovers conventions in an existing codebase |
| [Taskmaster](https://github.com/eyaltoledano/claude-task-master) | Task manager as an MCP server | Typed MCP tools instead of shell calls; a configurable tool set |
| [Conductor](https://www.conductor.build/), [Claude Squad](https://github.com/smtg-ai/claude-squad), [Vibe Kanban](https://github.com/BloopAI/vibe-kanban), Nimbalyst | Parallel agent workspaces | Setup, run and archive scripts for each worktree; diff comments sent back to the agent |
| [Claude Code plugins](https://code.claude.com/docs/en/plugins-reference), [Gemini extensions](https://geminicli.com/docs/extensions/reference/), Codex plugins | Packaging formats | A folder of skills, commands, hooks and MCP servers, one manifest with a version range, a git-hosted marketplace |
| [Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model) | Review protocol | Paraphrase-first reviews and Fix/Contest/Escalate/Decline responses, adopted in v5.0.0 |

**Where Nuhut is ahead.** Its evidence ledger, risk tiers, reviews by a second model
family, `doctor` audits and the local viewer have no close equivalent in any of these
tools. No other tool covers as many agent tools with zero dependencies.

**Where Nuhut fits.** The GUIs (T3 Code, Conductor) run agents, while Nuhut is the process
and the evidence those agents leave behind. The natural integration is a T3 Code or
Conductor workspace in each claimed worktree, with Nuhut's hooks and `finish` running
inside it.

## Gaps

### The kit claims more than it enforces (Phase 0, v5.0.x)

| Gap | Item |
| --- | --- |
| The self-install in this repository still reports `kit_version` 4.0.0 after the 5.0.0 release | NUHT-011 |
| `finish` accepts a verify run on an older commit, a single-stage run, or a waiver signed with any name | NUHT-012 (Tier 1, needs approval) |
| The test-lock and protected-path guards check file-tool writes but miss shell writes such as `sed -i`, redirects and `tee` | NUHT-013 |
| Every push to `main` releases, two queued runs race, and `release.yml` never runs | NUHT-014 (needs approval) |
| `install.sh` accepts Python 3.6 and says nothing installed needs Python; `finish` swallows two exceptions | NUHT-015 |

### Several people on one project (Phase 2)

| Gap | Item |
| --- | --- |
| No PR or CI enforcement; the scaffolded workflow only runs by hand | NUHT-022 |
| An item's owner is a role and a claim records agent and host, never a person | NUHT-023 |
| Tier 1 approval is a status and a name in the charter, not a GitHub review | NUHT-024 |
| Two people editing the same item shard get a git conflict | NUHT-025 |
| No one-line "what next" in the CLI | NUHT-026 |
| No guide for joining a project that already has the kit installed | NUHT-026 ([joining.md](joining.md)) |

### Release, deploy and operate (Phase 3)

| Gap | Item |
| --- | --- |
| User projects get release guidance but no release record, no deploy ledger, and no record of which version runs in which environment | NUHT-027 |
| The hotfix path's retroactive review is not checked | NUHT-028 |
| Metrics measure process gaps, not delivery (lead time, deploy frequency, failure rate, recovery time) | NUHT-029 |

### Supporting more tools (Phase 1 and Phase 4)

| Gap | Item |
| --- | --- |
| Tool support is hard-coded in about 25 places; the reviewer and builder tables disagree | NUHT-016, NUHT-017 |
| No third-party extension format, catalog or template overlays | NUHT-016, NUHT-018 |
| Plugin packaging exists only for Claude Code | NUHT-019 (absorbs NUHT-008) |
| OpenCode, Kiro and ACP agents need core changes to support | NUHT-020 |
| `sdlc.py` is 4,735 lines routed through a long `if` chain | NUHT-021 |
| No issue-tracker sync, MCP server, worktree setup scripts, standards discovery or webhooks | NUHT-030 to NUHT-034 |

Items already record `depends`, and `claim` and `parallel` refuse an item whose
dependencies are unfinished. Dependency-aware waves therefore extend what exists rather
than add something new.

### Proof of value

- The smoke suite is one 4,614-line script that takes about seven minutes (NUHT-035).
- The 3.5.0 benchmark found about five times the cost with no measured correctness gain, and
  the 4.x and 5.x re-run has not been done (NUHT-036).

## How a team works with the kit

| Phase | Today | Target |
| --- | --- | --- |
| Understand | `lens`, the viewer, `doctor --baseline`, getting-started | Adds `status` and a guide for joining an existing install (NUHT-026) |
| Plan | Intake, tier, plan, `plan-check --pre`, shards, claims | Owners are people; Tier 1 plans are approved in a PR review |
| Build | Claim or dispatch into a worktree, test first, hooks | Worktree setup scripts; works inside T3 Code or Conductor workspaces |
| Verify and review | Local `verify`, `review --by`, `finish` | CI re-runs verify and `ci-check`; GitHub approval is recorded as the approval |
| Release and deploy | The `sdlc-release` skill and runbook | Release record, deploy ledger, check the live environment, rollback |
| Operate and fix | Incident mode, test lock, postmortem template | A hotfix fast path whose retroactive review `doctor` checks; postmortems linked to follow-up items |

## Extension system

The design is in [ADR 0003](../handbook/project/adr/0003-extension-system.md). In short:

- An extension is a folder with a `nuhut-extension.json` manifest.
- It can declare harnesses, agent CLIs, check stages, presets and content as data, with no
  code.
- It can add hook rules, doctor checks and subcommands as Python files. These run only
  when the charter allows them.
- The built-in tools (Claude Code, Codex, Gemini, Cursor) move into built-in extensions
  first. Adding a new tool then needs no core change.

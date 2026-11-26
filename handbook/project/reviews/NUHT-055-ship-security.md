---
status: current
owner: codex
last-reviewed: 2026-11-25
---

# Review — NUHT-055

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (1001 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change moves commit-message and staged-secret checks from agent shell hooks to Git hooks, and makes `--hooks` install both kinds. It adds a working-tree file that disables individual guards, with a CLI restriction based on environment variables and terminal presence. It also removes the generic denial of inline code mentioning protected paths, relying on later commit checks, and retires legacy Claude hook registrations during upgrade.

Checked: Supplied enforcement changes, installer migration, disable-switch handling, documentation claims, and changed tests against the supplied security playbook and charter rows.

Not checked: Code outside the supplied diff, actual hook wiring at runtime, CI enforcement, threat model, security/privacy records, architecture, or ADR 0004. No tests executed; approval claims in the plan were not independently verified.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `optional/runtime/sdlc.py::_cmd_hooks` and runtime copy | Human authorisation is inferred from caller-controlled environment variables and `stdin.isatty()`. An agent with a terminal passes the check; a process without the recognised variables also passes without a terminal. | An agent can disable security guards, including `approval-gate`, despite the charter requiring human approval for weakening hooks. | Enforce approval through a trusted mechanism outside agent control. Add denial tests for agent-created terminals and cleared environment variables. |
| 2 | S1 | `optional/runtime/hooks.py::_shell_denial`, `hook_off`, `run_agent_hook` and runtime copy | Removing inline denial also permits writes to live trust anchors. The tests explicitly permit clearing `.ai-sdlc/gates.txt` and changing the manifest; the plan acknowledges inline writes to `hooks-off.txt`. Hooks consume the modified working-tree state before any commit. | An agent can disable or alter enforcement and use that weakened state immediately. A later commit check cannot prevent actions already taken, and the disable file also suppresses commit checks. | Preserve protection of enforcement code and configuration at write/use time through an agent-inaccessible boundary. Separate harmless reads from writes without granting unrestricted inline mutation. Test a write followed by a normally denied action before committing. |
| 3 | S1 | `install.py::upgrade` | Upgrade removes old commit guards even when replacement Git hooks are absent; it only adds an installation note. Earlier `--hooks` installations could have agent hooks without Git hooks. | An ordinary upgrade can remove staged-secret and work-item enforcement until a person performs another installation step. | Install and verify replacement wiring before retiring old hooks; retain old guards if migration cannot complete. Test upgrade from an agent-hooks-only installation, including actual denied commits. |
| 4 | S2 | `install.py::retire_hook_commands` | Retirement identifies hooks solely by a command ending in `work-item-id.sh` or `secret-guard.sh`, without checking the kit-owned path. | Upgrade can delete an unrelated security hook with the same basename, contradicting the promise to preserve existing hooks. | Match recognised kit-owned command paths and supported legacy forms. Test that unrelated same-basename hooks survive. |
| 5 | S2 | `optional/runtime/sdlc.py::_cmd_hooks.installed` and runtime copy | The listing reports a hook as “on” based only on script-file existence, without checking registration or Git hook wiring. | Users can receive false assurance that security checks execute when scripts are merely present. | Distinguish script presence from active wiring; report unverified wiring explicitly and test detached or missing registrations. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Decline | ADR 0004 (approved 2026-11-25): nothing running in the agent's environment can prove a person is present; `hooks off` refuses an agent's session without a terminal as a guardrail, like waivers. A host-required CI job is the check that holds. | |
| 2 | Fix | `_shell_denial` refuses inline code that names an enforcement file again: the guard lists, `hooks-off.txt`, `.claude/hooks`, hook settings, `.ai-sdlc/git-hooks` and `.ai-sdlc/bin` (`_enforcement_files`). Ordinary locked and protected paths are left to the commit check. Tests: "inline code that names the off list is refused (review finding 2)"; the node/perl/ruby writes to `protected.txt` and `gates.txt` are back in the denied list. | |
| 3 | Fix | `--upgrade` installs the git hooks first when an install has agent hooks but no git hooks, and retires the old registrations only once `commit-msg` and `pre-commit` are present; otherwise they stay and a note says so. Test: "--upgrade installs the git hooks before it retires the old agent commit hooks". | |
| 4 | Fix | `retire_hook_commands` matches only the kit's own command forms (`sh "$CLAUDE_PROJECT_DIR"/.claude/hooks/<name>` and the older relative one). Test: "--upgrade keeps a project's own hook with the same script name (review finding 4)". | |
| 5 | Fix | `hooks list` says `on` only when the hook is wired (registered in settings, or called from the git hook in `core.hooksPath`, `.git/hooks` or `.husky`), `not wired` when only the script exists. Test: "a hook whose script exists but is not registered is listed as not wired (finding 5)". | |

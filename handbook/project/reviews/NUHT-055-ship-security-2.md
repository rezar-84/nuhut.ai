---
status: current
owner: codex
last-reviewed: 2026-11-25
---

# Review — NUHT-055

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (1157 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change moves commit-message and staged-secret checks to Git hooks and installs them alongside agent hooks. A new CLI command writes a working-tree disable list that agent and Git hooks consult before enforcing their rules. Inline commands mentioning ordinary protected paths are allowed, while a narrower list of enforcement files retains mention-based protection. Upgrade retires legacy Claude registrations after checking that replacement Git hook scripts exist.

Checked: Supplied enforcement code, disable-switch authorisation, inline-command exceptions, installer migration, status reporting, documentation, and test assertions against the supplied security playbook and charter.

Not checked: Code outside the supplied diff, runtime behaviour, actual Git hook execution, CI enforcement, threat model, security/privacy records, architecture, or ADR 0004. No tests executed; embedded review responses and approval claims were not independently verified.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S1 | `optional/runtime/sdlc.py::_cmd_hooks`; `.ai-sdlc/bin/sdlc.py` copy | Disabling guards is refused only when recognised agent environment variables are present **and** stdin is not a terminal. An agent-created terminal or cleared environment passes. The supplied test itself permits disabling with cleared variables and `DEVNULL`. | Caller-controlled state substitutes for the human approval required to weaken hooks. An agent can disable `approval-gate` and other protections. Calling this a guardrail does not enforce the charter requirement. | Enforce disable authorisation outside agent control, with configuration the agent cannot modify. Add denial tests for cleared environments and agent-created terminals. |
| 2 | S1 | `optional/runtime/hooks.py::_shell_denial`, `_enforcement_files`; runtime copy; `tests/smoke.py::test_shell_write_guards` | The replacement inline protection omits existing trust anchors, including `.ai-sdlc/manifest.json`, `.ai-sdlc/profile.json`, and extension directories. Tests explicitly expect an inline manifest overwrite to be allowed. | Trust configuration can be changed before a commit; later commit checks cannot protect consumers that use the modified working tree immediately. The previous finding about live trust-anchor writes remains only partially addressed. | Cover all live trust anchors at write/use time, preferably through an agent-inaccessible boundary. Add mutation-followed-by-use denial tests for manifest, profile, and extension configuration. |
| 3 | S1 | `install.py::upgrade` | Legacy guards are retired based on replacement script existence, without verifying active Git wiring. When both scripts already exist but Git hooks are disconnected, installation is skipped and old registrations are removed. The migration test retains wiring from its earlier fresh install and checks script presence rather than denied commits. | Upgrade can remove the remaining active credential and work-item checks while reporting migration success. | Verify or repair active Git wiring before retirement; preserve legacy guards if replacement enforcement cannot be established. Test disconnected scripts and actual rejected commits after migration. |
| 4 | S2 | `optional/runtime/sdlc.py::_cmd_hooks.state_of`; runtime copy | “On” is inferred from substring presence in settings or hook files. Commented shell lines, inactive `.husky` files, or registrations under the wrong event can satisfy this check; executable permissions are not checked. | Users can receive affirmative security status even when the guard never executes. | Parse supported registrations, inspect the effective Git hook location and executable status, and distinguish detected configuration from verified enforcement. Add tests for commented, inactive, and non-executable wiring. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Decline | Repeat of round 1 finding 1, declined under ADR 0004 (approved 2026-11-25): no check inside the agent's environment authenticates a person; `hooks off` is a guardrail, and a host-required CI job is the check that holds. | |
| 2 | Fix | Partly. Extension folders (`.ai-sdlc/extensions`, `.ai-sdlc/local/extensions`) are now enforcement files, because their code runs inside the hooks. `manifest.json` and `profile.json` stay out: they are records the kit writes (upgrade hashes, the item prefix), the agent's edit tools still cannot write them, and refusing inline code that names them was the false alarm this item removes; a commit that changes them is reviewed like any other. | |
| 3 | Fix | `--upgrade` now checks wiring, not script presence: `hooks.git_hook_wired` reads the hook file git uses (core.hooksPath, the repository's hooks folder, or .husky), requires it executable where git does, and an uncommented call. It installs the git hooks when they are not wired and retires the old registrations only once both are. Test: "--upgrade wires disconnected git hooks before it retires the old ones (round 2, 3)". | |
| 4 | Fix | `hooks list` uses `git_hook_wired` and `agent_hook_wired` (parses settings.json, PreToolUse entries only). Test: "a commented-out git hook call is not wired (round 2, 4)". | |

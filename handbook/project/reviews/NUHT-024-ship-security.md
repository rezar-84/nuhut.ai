---
status: current
owner: codex
last-reviewed: 2026-11-26
---

# Review — NUHT-024

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (14341 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change lets `finish` count GitHub reviews on an item branch’s PR head and move sufficiently approved items from Parked to Done, while recording reviewer identities. It also changes trusted-record lookup and hook enforcement, adds automatic worktree shell scripts, and exposes selected CLI operations through MCP. Additional changes introduce webhook notifications, extension packaging and commands, GitHub issue synchronisation, new agent harnesses, and delivery metrics. These paths cross repository-content, process-execution, filesystem and network trust boundaries.

Checked: Static inspection of the supplied diff and tests against the supplied security playbook and charter rows, including approval binding, trust fallbacks, hook bypasses, subprocess execution, packaging paths, MCP limits and agent permissions. Findings on runtime sources also apply to their `.ai-sdlc/bin/` copies.

Not checked: Tests were not run. Unshown helper implementations, live GitHub responses, branch protection, sandbox configuration, credential access, threat-model records and security/privacy records were not available within the requested review scope.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
|---|---|---|---|---|---|
| 1 | S1 | `optional/runtime/finish.py`: `approvals()` | `baseRefName` is requested but never checked. An OPEN PR targeting any branch can satisfy the approval gate when its head matches the local item branch. | Reviews for a different merge destination can close a Tier 1 item as approved for its intended merge. | Bind approvals to the trusted target branch and repository identity; add denial tests for an otherwise valid PR targeting another branch. |
| 2 | S1 | `optional/runtime/finish.py`: `finish()` | `escalations = [] if already else ...` skips unresolved escalations for already Parked items, while the new transition explicitly permits those items to become Done. | A Parked item with sufficient approvals and passing verification can close despite an unresolved escalated security finding. | Recheck escalations whenever transitioning to Done, including Parked items; test this transition with an unresolved finding. |
| 3 | S1 | `optional/runtime/hooks.py`: `_agent_session()`, `_guarded_paths_in_commit()` | Protected-path enforcement now depends on environment variables the invoking process can remove. The fixed list also omits the newly declared `OPENCODE` marker. | An agent can receive the human exemption and commit protected changes without human approval. | Keep enforcement independent of caller-controlled environment markers; require externally verified authorisation for exceptions. Test missing and cleared markers. |
| 4 | S1 | `optional/runtime/hooks.py`: `_kit_checkout()`, `_trust_anchors()` | Merely creating `install.py` and `optional/runtime/hooks.py` causes the runtime directory to lose trust-anchor protection. Neither marker is protected by this new rule. | An installed project can impersonate the kit checkout, then alter the enforcement code itself. | Establish this exception through trusted installation metadata outside agent write access, rather than file existence; test fabricated markers. |
| 5 | S0 | `optional/runtime/claims.py`: `worktree_scripts()`, `run_worktree_script()` | Automatic setup and teardown execute commands from the working-tree charter with `shell=True` and the complete inherited environment. No trusted-version or explicit command authorisation check appears at execution. | A crafted charter change becomes arbitrary command execution during ordinary claim or cleanup operations, with access to available credentials. | Require trusted, explicitly authorised script configuration and reviewed executable content; restrict environment and execution permissions. Test that branch-only script changes cannot execute. |
| 6 | S1 | `optional/runtime/registry.py`: `trusted_ref()`, `trusted_pins()`; `finish.py`: `mapping_trusted` | When authoritative refs or records are absent, security decisions fall back to working-tree configuration and pins. With no trusted ref, `mapping_trusted` explicitly accepts working-tree identity mappings. | Missing trust metadata permits a branch to supply the identities, allowlist or hashes that authorise its own content. | Fail closed for security-bearing reads; provide a separate human-authorised bootstrap path. Test absent refs, missing manifests and branch-selected defaults. |
| 7 | S1 | `optional/extensions/kiro/nuhut-extension.json`: `agents.build` | The default builder uses `--trust-all-tools` while declaring no hook enforcement. No compensating permission boundary is shown. | Repository or prompt content reaches an agent with blanket tool approval, exceeding the task’s required privileges. | Remove blanket trust and supply a constrained tool policy or enforced sandbox, retaining human approval for sensitive actions. |
| 8 | S2 | `optional/runtime/ext.py`: `cmd_package()`, `_copy_tree()` | Source containment checks do not protect destination paths. `open(..., "w")` and `shutil.copyfile()` follow existing destination symlinks. | A prepared output tree can redirect packaging writes outside the requested directory and overwrite files accessible to the process. | Reject destination symlinks and escaping ancestors; use safe creation and replacement within a validated output root. Add destination-symlink tests. |
| 9 | S2 | `optional/runtime/mcp_server.py`: `Server.run()`; `claims.py`: `run_worktree_script()` | Output limits apply only after subprocess output has been fully buffered. MCP timeout cleanup kills only the immediate child, then performs an unbounded `communicate()`. | Excessive output can exhaust memory; descendants retaining pipe handles can keep the server blocked after its timeout. | Bound output while reading, terminate the process group on timeout, and bound cleanup waits. Test output flooding and descendants holding pipes open. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 2 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 3 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 4 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 5 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 6 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 7 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 8 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |
| 9 | Contest | This review's diff ran from the item's first commit to its last and so held other items' work (worktree scripts, Kiro, ext package, MCP); fixed in NUHT-060. NUHT-024-ship-security-2.md is the review of NUHT-024's own commits. | |

---
name: sdlc-managed-platform
description: Apply the rules for a repository co-owned by an AI app builder or cloud IDE — Lovable, Replit, Bolt, Firebase Studio, Glitch, CodeSandbox — covering platform-owned files, the sync model, history rewrites, and deploys. Use before editing platform config, rebasing or force-pushing, changing build settings, or releasing in such a project.
---

# Managed platform rules

Authority: the charter's **Managed platform** table, plus "Managed platforms" in
`{{DOCS_DIR}}/process/05-change-control.md`. Where that table conflicts with a process
document, the table wins — it describes a system that will keep acting on this repository
whether or not the process agrees.

## Establish first

Read the charter's table: platform, sync model, platform-owned files, where the platform's
own agent reads its instructions, and how deploys happen. If it says "none" but the
repository carries platform markers (`.replit`, `replit.nix`, `.bolt/`, `.idx/`,
`glitch.json`, `sandbox.config.json`, a Lovable project), stop and fix the charter first —
every rule below depends on that table being true.

## Standing rules

1. **Never hand-edit a platform-owned file.** Config, generated manifests, and lockfiles the
   platform regenerates are its output. Change the setting through the platform, or the
   platform will overwrite you — usually at the worst moment.
2. **Never rewrite history on a branch the platform syncs.** No force-push, no rebase of
   pushed commits, no amending a synced commit. Two-way sync plus rewritten history produces
   conflicts a human has to untangle by hand.
3. **Assume another agent is editing concurrently.** Pull before you work, keep changes small
   and quickly merged, and expect files you did not touch to have moved.
4. **A merge the platform auto-deploys is a release.** It goes through the release gates
   (`sdlc-release`) and needs authorisation *before* merge, because the merge is the deploy.
5. **One contract, not two.** The platform's instruction file or knowledge base points at
   `AGENTS.md` instead of restating it. Two drifting copies of the rules is the failure mode
   this rule exists to prevent.
6. **Secrets live in the platform's secret store**, never in a synced file, and never in the
   client bundle the platform builds.

## Before you act

State which of the rules above applies to what you are about to do. If a task requires
editing a platform-owned file or rewriting synced history, stop and ask — that is a decision
for the person who owns the platform account, not something to work around.

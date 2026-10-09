---
name: sdlc-release
description: Prepare and run a release — build the runbook, take the go/no-go against the quality gates, deploy, verify in the real environment, and keep the rollback ready. Use when shipping to a real environment, cutting a release or tag, or when a merge will auto-deploy, including on platforms that publish from a UI.
---

# Release

Template: `{{DOCS_DIR}}/templates/release-runbook.md`. Environments, deploy permissions,
deployment platforms, and the default branch: the charter. Playbook:
`{{DOCS_DIR}}/roles/devops-sre.md`, plus `{{DOCS_DIR}}/platforms/<platform>.md` for each
platform the charter names that has one — its deploy and rollback items are part of the
go/no-go.

A deploy is outward-facing and hard to reverse, so it needs explicit authorisation before it
happens — not a report after.

## Before

1. **Go/no-go.** Every stage in the charter's Commands table run and reported as Verified /
   Not run / Absent (`sdlc-evidence-check`). A failing or skipped gate is a no-go unless a
   named approver accepted it in writing — record who, and why.
2. **Scope.** The exact commit range going out and the work item IDs in it. Anything in the
   range that nobody reviewed is a stop.
3. **Migrations.** Reversible, ordered relative to the deploy, and rehearsed against
   realistic data. State explicitly whether the old code can run against the new schema — if
   it cannot, this is a two-step release, not one.
4. **Config and secrets.** Every new variable present in the target environment before the
   deploy, not discovered by a crash after it.
5. **Rollback.** Written down and actually possible: the command, the artifact to roll back
   to, the data implications, and how long it takes. "Roll forward" is not a rollback plan.
6. **Authorisation.** The charter says who may deploy this environment. Get explicit
   approval from a named human before triggering anything outward-facing.

## During

Announce the start, deploy, then verify in the environment itself — health, the primary user
path exercised for real, the error rate, and the specific behaviour the change was supposed
to alter. "The pipeline is green" is not verification of a release.

## After

Record in the worklog what shipped, the range, who approved, what was verified and how, what
is being watched, and the rollback that stays valid. Anything that went wrong feeds
`sdlc-postmortem`.

## Managed platforms

If the charter declares a platform that publishes from its own UI, the runbook documents
that publish and its rollback affordance — not a deploy command that does not exist. A merge
the platform auto-deploys **is** a release and gets everything above.

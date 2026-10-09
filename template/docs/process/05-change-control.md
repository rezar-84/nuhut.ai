# 05 — Change control

How a change moves from a working copy to production, and how it comes back if it was
wrong.

---

## Branches

```
<type>/{{PREFIX}}-###-short-slug
```

`type` ∈ `feat` · `fix` · `docs` · `chore` · `refactor` · `test` · `perf` · `sec`

One branch per work item. If a branch grows a second unrelated purpose, split it — a
mixed branch cannot be reviewed properly or reverted cleanly.

Never commit directly to the default branch unless the charter's Environments section
records "Direct commits to it: allowed". A blank there means not allowed.

If the charter's "Managed platform" table says a platform syncs or builds only the
default branch, follow what that table records — it may legitimately narrow or override
the branch rules above. See "Managed platforms" below.

---

## Commits

- Small, scoped, and individually coherent. A reviewer should be able to read one commit
  and understand one decision.
- Imperative mood, present tense: `add`, `fix`, `remove` — not `added`, `fixes`.
- Reference the work item ID.
- Never mix a refactor with a behaviour change in the same commit. Reviewing a diff
  where formatting, moving, and changing are entangled is how real bugs get waved
  through.

```
<type>(<scope>): <what changed, imperative, ≤72 chars>

<why it changed — the reasoning a future reader will not be able to infer>
<what was verified>

Refs: {{PREFIX}}-###
```

### Never commit

Secrets, tokens, private keys, `.env` contents, customer or personal data, large
binaries, generated artifacts that belong in a build, or anything under a licence the
project cannot honour. If a secret is committed, it is **compromised** — rotate it; do
not merely remove it in a follow-up commit.

---

## Pull requests

Body must contain:

1. **What** — the change in plain language.
2. **Why** — the problem, linked to the work item.
3. **How** — the approach, and alternatives rejected.
4. **Verification** — the checks run and their real results. Screenshots or output for
   anything user-visible.
5. **Risk** — tier, blast radius, and the rollback procedure.
6. **Review verdicts** — links to `project/reviews/` for Tier 1.
7. **Follow-ups** — what was deliberately left, with IDs.

Keep PRs small enough to review attentively. A PR nobody can hold in their head gets
approved on trust, which defeats the purpose.

---

## Approvals

| Change | Approval |
| --- | --- |
| Tier 3 | Self-merge permitted if all checks pass. |
| Tier 2 | **One human approver.** |
| Tier 1 | **Two human approvers**, at least one with domain ownership of the affected surface. |
| Anything named under "Human approval required for" in `AGENTS.md` | As named there, regardless of tier. |
| Tier 2 or 3 items inside an epic | Merged into the epic branch by the agent once checks pass and no review holds a Block. The approval above is given once per checkpoint, when the epic branch is proposed for the default branch (`11-epics.md`). A Tier 1 item inside an epic is approved on its own. |

An agent may prepare, propose, and justify a change. An agent does not approve its own
Tier 1 work, and does not count as either of the two approvers.

Never bypass a failing security, migration, accessibility, or data-integrity check. If
the check is wrong, that is a separate tracked change with its own justification.

---

## Architecture Decision Records

Write an ADR when a decision is **expensive to reverse** or when a future reader would
otherwise have to reverse-engineer the reasoning from the code.

**Write one for:** the stack, storage, and hosting choices; authentication and
authorisation model; tenancy/isolation model; public interface shape; a new significant
dependency; a data model that others will build on; anything you chose against the
obvious option.

**Do not write one for:** naming, formatting, or anything a lint rule can express.

Rules:
- Numbered sequentially, never renumbered: `project/adr/<NNNN>-<slug>.md`.
- Status: `Proposed` → `Approved` → (`Superseded by NNNN` | `Deprecated`).
- **Never edit the decision of an approved ADR.** Write a new one that supersedes it and
  link both directions. The record of what was decided *and later abandoned* is the most
  valuable part of the archive.
- Record the rejected options with the actual reason, not "not a good fit".

Template: `templates/adr.md`.

---

## Releases

Follow `project/release-runbook.md`. Every release states:

- what is included (the work item IDs);
- migration steps and their order relative to the deploy;
- the smoke checks that prove it worked;
- the monitoring window and what would trigger a rollback;
- the rollback procedure, which must have been executed at least once in a non-production
  environment.

**Migrations:** forward and reverse paths, both tested. Expand-then-contract for schema
changes so that old and new code can run simultaneously. Never hand-edit a production
datastore — a manual fix that is not a migration is invisible to every other environment
and to the next deploy.

**Irreversible operations** (data deletion, destructive migration, external
notifications, payments) require explicit human authorisation on the specific action.
Authorisation for one such action does not carry to the next.

---

## Managed platforms

Some projects are co-owned by a managed platform — an AI app builder or cloud IDE that
also edits, syncs, generates files in, or deploys the repository. The charter's
"Managed platform" table declares which one and what it owns. Where that table conflicts
with this document, the table wins: breaking the platform's sync or configuration is a
real outage, not a process victory.

Whenever the charter declares a platform:

- **Never hand-edit, move, or delete platform-owned files** (the charter lists them).
  If one must change, change it through the platform itself, or verify the edit against
  the platform's documented behaviour first and record that in the worklog.
- **Never rewrite history the platform has seen.** No force-push, rebase, or deletion of
  any branch the platform syncs — a diverged sync can silently drop the platform's
  commits or yours.
- **Assume another agent edits this repository too.** Sync before starting, keep changes
  small, and expect upstream commits you did not make. Do not revert or "fix" the
  platform's commits without a human decision — that is a Tier 1 stop-and-ask.
- **Deploys happen the platform's way.** If the platform publishes the default branch
  automatically, then merging *is* deploying — give the merge the ceremony of a release,
  and the release runbook documents the platform's publish and rollback affordances
  rather than a deploy command.
- **Keep the two contracts pointed at each other.** If the platform's own agent reads an
  instruction file or knowledge base, it should point at `AGENTS.md` rather than
  restate it, so the platform's agent and this process cannot drift apart.

---

## Fixing a defect

The test comes first, and the fixer does not get to rewrite it.

1. Write a test that reproduces the defect. Run it and confirm it fails **for the reason
   the report describes** — a test that fails on an import error reproduces nothing.
2. Commit that test on its own, with the item's ID, before any fix.
3. Where the opt-in hooks are installed, lock it: append its path to
   `.ai-sdlc/test-lock.txt`. The `test-lock` hook then denies edits to it.
4. Fix the code until the test passes, without editing the test. If the test turns out
   to be wrong, stop and say so; changing it is a human decision, like releasing the lock.
5. After verification, a human removes the lock line.

A test that existed before the fix and that the fixer could not change is the evidence
that the defect is gone. Editing it to pass is the S1 in `roles/qa.md`.

---

## Rollback and hotfix

- Prefer rolling back over rolling forward when the cause is not understood within the
  first minutes. Diagnose from a stable state.
- A hotfix still gets an ID, a test that reproduces the failure, and a worklog entry —
  written immediately after the fire is out, not "later".
- Any S0/S1 incident produces a postmortem (`templates/postmortem.md`) focused on the
  system that allowed it, not on who typed it.

---
name: sdlc-charter-audit
description: Audit the project charter for blank, stale, or contradictory cells and report exactly what is Unknown. Use before relying on the charter (check commands, active roles, risk defaults, environments), right after installing the SDLC kit, when its last-reviewed date is older than the staleness threshold, or when any document appears to contradict it.
---

# Charter audit

`{{DOCS_DIR}}/project/charter.md` is the only file that tells an agent what this project
is. Every other document defers to it, so a blank cell there silently degrades everything
downstream. This skill makes that damage visible instead of letting it propagate.

## What to check

1. **Blank vs absent.** A blank cell means *nobody has filled this in* — it is Unknown.
   Only the literal word **absent**, with a reason, means the project genuinely lacks that
   stage. Report every blank as a gap; never read one as "not applicable".
2. **Commands.** Do they exist and run? Compare against `package.json` scripts, the
   `Makefile`, CI workflow files, or the language's convention. A command that no longer
   exists is worse than a blank one, because it will be run and believed.
3. **Stack.** Does the table match what the repository actually contains — lockfile,
   framework imports, data layer, CI provider?
4. **Active roles.** Every unticked row needs a reason. A blank reason means nobody
   decided, and the default is that the role is *unreviewed*, not *inactive*.
5. **Risk defaults and modes.** Are approvers named? Is "Never Tier 1 here" justified?
   Is the default effort exactly Lean, Normal, or Beast, and acquisition exactly Standard
   or Advanced? A row still listing every option is undecided — the default applies.
   Treat a legacy `Operating mode: Beast mode` row as ambiguous, not as a
   valid value. Without a justified tier exception,
   "when in doubt, tier up" makes almost everything Tier 1 and the process stalls.
6. **Environments and default branch.** Do they match the real remotes and workflows?
7. **Managed platform.** If the repository shows platform markers (`.replit`, `.bolt/`,
   `.idx/`, a platform config directory) and the table says "none", that contradiction will
   produce broken advice. See the `sdlc-managed-platform` skill.
8. **Staleness.** A `last-reviewed` date older than the charter's staleness threshold makes
   the `{{DOCS_DIR}}/project/` documents hypotheses rather than facts. Say so.

## Rules

- Do not fill a cell with a guess. Propose a value, mark it `_(unverified — needs
  confirmation: <what, from whom>)_`, and ask.
- Facts you can establish from the repository itself (stack, commands, branch) may be
  filled in directly — say which ones you established, and from what evidence.
- Facts only a human holds — accountable human, approvers, budgets, jurisdictions, data
  categories, timeline — are asked for, never inferred.

## Output

A table of section → status (complete / incomplete / contradicts the repo / stale), the
questions only a human can answer, and the smallest set of edits that would make the
charter safe to rely on.

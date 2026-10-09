# 11 — Epics: several items, one plan

For work bigger than one item: a feature that is really five or ten connected changes.
An epic gives them one plan, one design review, and human checkpoints you choose, instead
of a separate plan and a separate stop for each item.

**Read this when** the request, the work item, or the charter's **Development method**
says `Epic`. Skip it entirely otherwise; working item by item needs nothing here.

Everything else in `AGENTS.md` and `process/` still applies to every item inside an epic.
An epic changes **how often a human is asked**, and **how much planning and recording is
shared**. It never changes a tier, a check, a review, or an approval a tier requires.

---

## 1. Choosing the method

Resolve the method at FRAME, in this order (the same order as effort mode):

1. an explicit method in the current request ("do this as an epic", "one item at a time")
2. the work item's recorded method
3. the charter's **Development method**
4. `Item`

| Method | What it means |
| --- | --- |
| **Item** | Today's loop, one item at a time. Each item has its own plan, gates, and stops. This is the default, and a project that never names a method works exactly as before. |
| **Epic** | One plan covers several items, and the agent carries on from one item to the next until it reaches a checkpoint or a hard stop (section 4). |

Inside an epic, the epic's plan picks **how often to check in**:

| Checkpoints | The agent stops for a human |
| --- | --- |
| **Per phase** (default) | at the end of each phase the plan names, and at the end |
| **Every N items** | after every N completed items, and at the end |
| **At the end** | only when every item is done, or at a hard stop |

Fewer checkpoints mean more work between human looks, and more to redo if an early
assumption was wrong. Choose **At the end** only when the items are Tier 2 or 3, the
project's checks are trustworthy, and the epic is small enough to review in one sitting.

Changing method or checkpoints mid-epic is allowed. Record it in the epic file and the
worklog, as for effort mode.

## 2. The epic record

An epic is a work item: it gets the next ID and a backlog row whose Task starts
`Epic:`. Its items are ordinary work items, with their own IDs and backlog rows. The
backlog format does not change.

The epic's file, `project/epics/{{PREFIX}}-###.md` from `templates/epic.md`, holds:

- the outcome and scope, and what is deliberately out
- the item table: ID, outcome, tier, phase, dependencies, status
- the shared plan: approach, files and contracts the items share, order, risks
- the design review of the whole plan
- the checkpoint log: what was done, verified, and decided at each one

**Each item's task cell names its epic**: the epic's own row reads `Epic: <title>`, and an
item's reads `<item> (in {{PREFIX}}-010)`. That is the only link the backlog needs.

## 3. Running an epic

**FRAME and PLAN, once.** Write the epic file. Split the work into items with one
observable outcome each, as `03-ready-and-done.md` requires, but plan them together:
shared schema, shared contracts, order, and the riskiest item first. Classify every item's
tier now. Splitting so that a Tier 1 change looks like several Tier 2 changes is the same
violation it is outside an epic.

**DESIGN REVIEW, once.** The roles the items select review the epic plan together. Record
verdicts in the epic file. A Block stops the epic, as it would stop an item.

**Approval to start.** A human approves the epic plan before the first BUILD, unless every
item is Tier 3. This approval is what lets the agent continue between items without asking
again. Record who approved it and when.

**BUILD, VERIFY, SHIP REVIEW, per item, without stopping in between.** For each item, in
plan order:

- The item still gets its own branch, its own tests, its own real check run, and its own
  ship review at its tier. The item's plan is the epic plan's row for it. A separate plan
  file is needed only for a Tier 1 item.
- A verified Tier 2 or 3 item merges into the **epic branch**, not the default branch. The
  agent may make that merge once the item's checks pass and its reviews have no Block.
- The item's worklog entry may be the short form, naming the epic. The full narrative
  goes in the next checkpoint entry.
- Mark the item `Done` in the epic table when it is merged to the epic branch. It becomes
  `Done` in the backlog when the epic branch reaches the default branch.

**Checkpoint.** At each checkpoint the agent stops and writes one worklog entry covering
the items since the last one: what changed, what was verified, with output, and what is
still open. It also proposes the epic branch for merge. The human merge approval that a
tier requires (`05-change-control.md`) is given here, once for those items: the highest
tier among them sets how many approvers are needed. Then the epic continues.

Reading the always-list is per session, not per item. Re-read a role playbook only when
an item selects a role the epic plan did not.

## 4. Hard stops: these interrupt any epic, whatever the checkpoints

The agent stops, finishes what does not depend on the decision, and parks the affected
item, never the whole epic unless everything depends on it, when:

- **an item is Tier 1.** It gets its own plan file, reviews, and two approvers before it
  merges anywhere, as outside an epic. Items that do not depend on it may continue.
- **any review records a Block** (S0, S1, or S2).
- **verification fails** and the fix is outside the item's agreed scope.
- **the plan turns out to be wrong**: a new item, a changed contract, or a tier that rises.
  Update the epic file, then treat it as a checkpoint. A changed plan needs the plan
  approval again.
- **anything irreversible or outward-facing** is next, or a gated surface (`AGENTS.md`
  "Human approval required for").

Parked items go in the backlog's Parked section with what they wait on, as today. A later
session resumes from the epic file's item table.

## 5. Working alone vs. working in parallel

Items without dependencies on each other may run in parallel worktrees, each claimed as
`10-multi-agent.md` describes, all merging into the epic branch. Items that touch the same
files run in order. The checkpoint is the same either way.

## 6. When not to use an epic

- One outcome, a known file list: that is one item. An epic of one is ceremony.
- Mostly Tier 1 work: every Tier 1 item stops anyway, so an epic saves little.
- The scope is not understood yet: run a discovery item first. An epic plan built on
  guesses fails at item two and wastes everything after it.

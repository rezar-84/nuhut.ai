# 07 — Traceability and logging

Any change should be answerable, months later, by: *why does this exist, who decided it,
what was verified, and what was left undone?* Four records carry that, and each has one
job. Keeping their jobs separate is what stops any of them becoming unreadable.

---

## Identifiers

```
{{PREFIX}}-###
```

The prefix is declared in `project/charter.md` (2–4 uppercase letters). Numbers are
sequential, never reused, never renumbered. Once an ID appears anywhere — branch,
commit, review, worklog — it is permanent, even if the work is dropped.

**Legacy and adopted projects.** When adopting an existing codebase, existing issue
numbers (e.g. hierarchical `Snn.n`, epics `Enn`, bugs `Bnn`, or external tracker numbers)
remain valid in `project/backlog.md` and are understood by the viewer and runtime without
renumbering. New work uses `{{PREFIX}}-###`.

**The next ID** is the highest number that appears anywhere under `project/` — including
`Dropped` rows, the worklog archive, and review filenames — plus one. Do not take it from
the last row of the active backlog table; dropped and archived items are exactly the ones
that have already been moved out of it.

Every branch, commit, review file, and worklog entry carries its ID. That single string
is the join key across all four records.

Work that ships without an ID gets one **retroactively** — logged with a note that it
was retroactive. An untracked change is not erased by pretending it did not happen.

---

## The four records

| Record | File | Contains | Shape | Grows by |
| --- | --- | --- | --- | --- |
| **Backlog** | `project/backlog.md` | What is planned, in flight, done. | Terse table. One line per item. | New rows, status edits |
| **Worklog** | `project/worklog.md` | What actually happened and why. | Prose entries, newest first. | Append only |
| **Decisions** | `project/adr/NNNN-*.md` | Why the durable choices were made. | One file per decision. | New files; existing ones superseded, not edited |
| **Reviews** | `project/reviews/{{PREFIX}}-###-<stage>.md` | What each role checked and found. | One file per review. | New files |
| **Defects** | `project/defects/{{PREFIX}}-###.md` | Bug reports filed by testers / users. | One file per defect. | New files |

### The separation rule

**The backlog table stays terse. Narrative goes in the worklog.**

This is the single most important formatting rule in the kit, and the one most often
broken. The temptation, when finishing a rich piece of work, is to write the story into
the backlog's description cell. Do that a dozen times and the table has multi-paragraph
cells, the status column is unscannable, and the document that was supposed to answer
"what is left?" in five seconds cannot answer it at all.

Anything beyond the row's six columns goes in the worklog entry, which the row
implicitly points to via its ID.

---

## The backlog row

The authoritative column order. It is a positional markdown table, so the order is part
of the specification.

```
| ID | Task | Tier | Owner role | Depends on | Status |
```

Every section of `project/backlog.md` carries these six, in this order, and may add
section-specific columns **to the right** (Blocked adds who can unblock; Done adds a
completion date). A row keeps all six wherever it sits — an item does not stop having an
owner or a tier because it finished.

| Column | Rule |
| --- | --- |
| **ID** | `{{PREFIX}}-###`. Sequential, never reused, never renumbered. |
| **Task** | **One line.** What will be true afterwards. If it needs two sentences, it is two items. |
| **Tier** | 1 / 2 / 3 per "Risk tiers" in `AGENTS.md`. Assigned at FRAME, before planning. |
| **Owner role** | The role accountable, from the charter's active roster. |
| **Depends on** | Other IDs, or a named human input ("owner: brand assets"). Blank if none. |
| **Status** | One of the eight values below. No others, no synonyms. |

### Status values

| Status | Meaning |
| --- | --- |
| **Ready** | Passes the Definition of Ready (`03-ready-and-done.md`). Anyone could pick it up. |
| **Blocked** | Cannot start. The blocker is named in Depends-on, and it is a real identified thing, not "needs more thought". |
| **In progress** | Actively being built. One or two at a time, not fifteen. |
| **In review** | Built, awaiting role review — or holding a *Block* verdict that is being fixed. A Block does not send an item back to `Blocked`; that status means work never started. |
| **Parked** | Complete as far as an agent can take it; waiting on a named human for an approval or a waiver. See "Waiting on a human" in `00-operating-model.md`. |
| **Done** | Meets the Definition of Done, worklog entry written. Nothing is `Done` without a worklog entry. |
| **Deferred** | Valid, not now. Say when it becomes relevant again. |
| **Dropped** | Will not be done. One-line reason, and the row stays. |

### Writing a good one-line task

| Poor | Better |
| --- | --- |
| Improve the dashboard | Show last successful sync time per report on the dashboard |
| Fix the auth bug | Deny report access when a membership has been revoked |
| SEO work | Add reciprocal language alternates to all published pages |
| Refactor | Extract the entitlement check out of the route handler into the service layer |

The test: could someone else tell whether it is finished, without asking you?

---

## What a good worklog entry contains

Use `templates/worklog-entry.md`. Non-negotiable sections:

- **What changed** — plain language, readable by someone who was not here.
- **Why** — the reasoning, especially where the obvious approach was rejected.
- **Effort mode** — Lean, Normal, or Beast, including any explicit override or mid-item
  change. This is independent of the risk tier.
- **Verified** — the actual commands and their actual results. Not "tests pass" but
  which suite, how many, against what.
- **Not done** — deferred, stubbed, mocked, or hardcoded, each with the follow-up ID.
  This section is the one future readers need most and the one most often omitted.
- **Discovered** — pre-existing bugs found, docs found stale, assumptions refuted. Even
  if you did not fix them. Especially if you did not fix them.
- **Assumptions used** — anything from the register this work depends on.

An entry that says only what changed is a `git log` with extra steps. The value is in
*why*, *what was verified*, and *what is still wrong*.

---

## Staleness

Every artifact in `project/` carries `last-reviewed: YYYY-MM-DD`.

- When you change something a document describes, you update the document and the date
  in the same change — or mark it `status: stale` and open a backlog item. Both are
  acceptable; leaving it confidently wrong is not.
- An agent reading a document older than the charter's staleness threshold treats it as
  a **hypothesis**, verifies the parts it depends on against the code, and reports the
  drift it finds.
- Document drift is a real defect and belongs in review findings, rated on the ladder in
  `04-quality-gates.md` like anything else.

---

## Traceability chain

For any line of shipped code, this chain should be walkable in both directions:

```
code  ←→  commit  ←→  {{PREFIX}}-###  ←→  backlog row
                            │
                            ├─→ plan (what we intended)
                            ├─→ review files (what each role checked)
                            ├─→ ADR (why the durable choice)
                            └─→ worklog entry (what happened, verified, left open)
```

If any link is missing, that is a finding. The most common break is a change that was
made "quickly" without an ID — from which point nothing downstream can be found.

**When a tracker holds the record too.** Name one system as authoritative for each kind
of record, in the charter's "System of record" row. The other system holds a link, never
a second copy that can drift. At minimum, the tracker item carries the commit SHA and the
repository record carries the tracker ID.

---

## Housekeeping

- **Do not delete backlog rows.** Move them to `Dropped` with a reason. Deleting
  guarantees the idea will be proposed again, discussed again, and rejected again.
- **Do not rewrite worklog history.** If an entry was wrong, append a correction that
  references it. The record of a mistaken belief is part of the record.
- **Archive, do not truncate.** When the worklog gets long, move older entries to
  `project/worklog-archive/YYYY.md` and leave a pointer. Same for completed backlog
  items: a `Done` archive section keeps the active table short.
- **Rotate at 1,000 lines**, or at the start of a new quarter if that comes first. Move
  every closed entry older than the current quarter into
  `project/worklog-archive/YYYY-Qn.md`, keep the last few in place for continuity, and
  leave a dated pointer line naming the archive file.

  This threshold exists because nothing else enforces one. `worklog.md` is on the
  always-read list for every Tier 1 and Tier 2 change, so it grows until it is the
  largest file each session loads, and the growth is invisible to the person adding one
  entry at a time. Rotating is not tidying — it is the difference between an agent
  reading recent history and an agent spending its context on last year's.
- **Review the registers at CLOSE.** Backlog, assumptions, and risks are read and
  reconciled at the end of every work item, not only when someone remembers.

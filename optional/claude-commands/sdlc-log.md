---
description: Close a work item — worklog entry, backlog status, follow-ups, doc updates
argument-hint: "[optional: the work item ID being closed]"
---

Run the LOG → CLOSE steps of the loop per `{{DOCS_DIR}}/process/00-operating-model.md` for the
work just completed.

$ARGUMENTS

1. **Check the Definition of Done** in `{{DOCS_DIR}}/process/03-ready-and-done.md`. Anything
   unmet is either fixed now or becomes a tracked follow-up named in the entry — never
   an unstated gap.

2. **Write the worklog entry** at the top of `{{DOCS_DIR}}/project/worklog.md`, using every
   section of `{{DOCS_DIR}}/templates/worklog-entry.md`. Leave none of them out — **Not done**
   and **Discovered** are the two future readers need most and the two most often
   omitted. If either is genuinely empty, say so explicitly rather than deleting it.

3. **Update the backlog** — status change with a pointer, never a bare status flip.
   Create rows for every follow-up, each a single line
   (`{{DOCS_DIR}}/process/07-traceability.md`). Narrative stays in the worklog; the table stays
   terse.

4. **Reconcile `{{DOCS_DIR}}/project/assumptions-and-risks.md`** — close what was resolved, note
   what a refuted assumption means for work already shipped, add what is newly unknown.

5. **Update the docs the change falsified** — corrected and re-dated, or marked
   `status: stale` with a backlog item (`{{DOCS_DIR}}/process/07-traceability.md`). Leaving a
   confidently wrong document is not an option.

6. **Write an ADR** if a durable decision was made and none exists
   (`{{DOCS_DIR}}/templates/adr.md`). If a decision was durable and you are not writing an ADR,
   say why.

7. **Report** what is done, what is verified, and what is open — plainly, without
   hedging and without overstating.

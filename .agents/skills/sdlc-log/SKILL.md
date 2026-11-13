---
name: sdlc-log
description: "Close a work item — worklog entry, backlog status, follow-ups, doc updates. Use when the user invokes /sdlc-log or asks to close, log or wrap up a work item that is built, verified and reviewed."
---

<!-- Generated from the kit's optional/claude-commands/sdlc-log.md by install.py. Kit-managed: change the kit, not this file. -->

Run the LOG → CLOSE steps of the loop per `handbook/process/00-operating-model.md` for the
work just completed.

the request given with this skill: the text after its name, or the request in the conversation that called for it (expected: `[optional: the work item ID being closed]`).

**For a built item, `/sdlc-finish <ID>` does this in one step:** it checks the evidence and
reviews, drafts the entry and sets the status. Use this command for the parts it leaves to
you, or where the runtime is not installed.

1. **Check the Definition of Done** in `handbook/process/03-ready-and-done.md`. Anything
   unmet is either fixed now or becomes a tracked follow-up named in the entry — never
   an unstated gap.

2. **Draft or write the worklog entry** in `handbook/project/worklog.md`:
   - For **Tier 3** under `Standard` tier rules, the commit message carrying the ID is the
     record — no worklog entry is required unless the change uncovered risk, a durable
     decision, or unresolved work. (Under `Strict` tier rules or `Lean` mode, run
     `python3 .ai-sdlc/bin/sdlc.py log --since <ref> --write` to insert the 1-line
     compact entry.)
   - For **Tier 1 and Tier 2**, start by running
     `python3 .ai-sdlc/bin/sdlc.py log --since <ref>` to draft lines from commits and
     `sdlc.py verify` runs, then expand at the top of `handbook/project/worklog.md`
     using every section of `handbook/templates/worklog-entry.md`. Leave none of them
     out — **Not done** and **Discovered** are the two future readers need most and the
     two most often omitted. If either is genuinely empty, say so explicitly rather than
     deleting it. (In `Lean` mode on a clean Tier 2 item with no open risks, the 1-line
     `sdlc.py log --write` entry suffices.)

3. **Update the backlog** — status change with a pointer, never a bare status flip.
   Create rows for every follow-up, each a single line
   (`handbook/process/07-traceability.md`). Narrative stays in the worklog; the table stays
   terse.

4. **Reconcile `handbook/project/assumptions-and-risks.md`** — close what was resolved, note
   what a refuted assumption means for work already shipped, add what is newly unknown.

5. **Update the docs the change falsified** — corrected and re-dated, or marked
   `status: stale` with a backlog item (`handbook/process/07-traceability.md`). Leaving a
   confidently wrong document is not an option. If the item has a spec change
   (`handbook/project/specs/changes/<ID>.md`), merge it into the living specs with
   `python3 .ai-sdlc/bin/sdlc.py spec apply <ID> --write`; a refusal (a MODIFIED or REMOVED
   name that does not match) is fixed in the change file, never forced.

6. **Write an ADR** if a durable decision was made and none exists
   (`handbook/templates/adr.md`). If a decision was durable and you are not writing an ADR,
   say why.

7. **Report** what is done, what is verified, and what is open — plainly, without
   hedging and without overstating.

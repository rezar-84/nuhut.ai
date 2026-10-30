---
description: Finish a built work item — evidence, review, worklog entry and status in one step
argument-hint: "<work item ID>"
---

Finish the work item, per `{{DOCS_DIR}}/process/00-operating-model.md` (SHIP REVIEW → LOG →
CLOSE), with the runtime doing the mechanical part:

$ARGUMENTS

1. **Run it:**

   ```sh
   python3 .ai-sdlc/bin/sdlc.py finish <ID>
   ```

   It reads the item's tier and checks only what that tier owes. It needs a
   `sdlc.py verify --item <ID>` run on the item's commits (not at Tier 3), a ship review
   at Tier 1, and an independent review where the charter's policy asks for one. It runs
   `plan-check` when there is a plan. Then it drafts the worklog entry from git and the
   evidence ledger and sets the backlog row to Done. At Tier 1 it sets **Parked** for
   the human merge approval instead; it never approves on anyone's behalf.

2. **Each `OWED` line says what is missing and the command that supplies it.** Do that,
   then run `finish` again. Do not edit records to make a line go away.

3. **When the checks genuinely cannot run here** (no database, no device), a named
   person may waive them, never at Tier 1:

   ```sh
   python3 .ai-sdlc/bin/sdlc.py finish <ID> --waive verify --by <name> --reason "..."
   ```

   The waiver is recorded as *Not run* with the name and reason. It never counts as
   Verified, and `sdlc.py metrics` counts waivers. Do not waive on your own initiative:
   ask the person, and give their words as the reason.

4. **Fill the drafted entry.** For Tier 1 and 2, `finish` writes every section it can
   from git and the ledger and marks the rest `TODO(finish)`: Why, Not done,
   Discovered, Decisions, Assumptions, and for Tier 2 the plan and review verdicts.
   Replace each one with the real content. Write "nothing deferred" or "none" when that
   is the truth; never delete a section. `finish` refuses while a `TODO(finish)` is
   left.

5. **Then do the closing work no script can.** Reconcile
   `{{DOCS_DIR}}/project/assumptions-and-risks.md`. Update or mark stale the docs the change
   falsified. Add backlog rows for follow-ups. Merge the item's spec change
   (`sdlc.py spec apply <ID> --write`) when there is one. Write an ADR for a durable
   decision.

6. **Report** the final `finish` output: what is done, what is verified, what was
   waived and by whom, and what is open.

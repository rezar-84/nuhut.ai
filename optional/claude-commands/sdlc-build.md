---
description: Build an approved plan — implement it to the plan, tests alongside, scoped to its ID
argument-hint: "<work item ID> [optional: the part of the plan to build now]"
---

Run the BUILD step of the loop in `AGENTS.md` for:

$ARGUMENTS

Follow "4. BUILD" in `{{DOCS_DIR}}/process/00-operating-model.md`. This command is the
step between `/sdlc-plan` and `/sdlc-verify`; it does not plan and it does not declare
anything verified.

1. **Find the approved plan, or stop.** Name the work item ID. Read its backlog row and
   its plan: Tier 1 at `{{DOCS_DIR}}/project/plans/<ID>.md`, Tier 2 in the conversation or
   the worklog, Tier 3 as its one sentence. If there is no plan, the design review holds a
   Block, or a Tier 1 plan lacks the approval `{{DOCS_DIR}}/process/05-change-control.md`
   requires, **do not start**: say which, and run `/sdlc-plan` first. Building without a
   plan is the failure this whole loop exists to prevent.

2. **Check the Definition of Ready** items that depend on the plan
   (`{{DOCS_DIR}}/process/03-ready-and-done.md`, "Checkable at BUILD"). An unmet item
   makes the row `Blocked` with the reason, not a guess.

3. **Claim it.** Set the backlog row to `In progress`, and work on a branch that carries
   the ID (`{{DOCS_DIR}}/process/05-change-control.md`).

4. **For a defect, the reproducing test comes first.** Write it, watch it fail for the
   reported reason, commit it, and lock it as `05-change-control.md`, "Fixing a defect",
   describes. Then fix the cause, at the boundary where every caller shares it, not only
   the reported symptom.

5. **Implement to the plan.** Tests alongside, including the failure and rejection paths.
   Keep to the plan's file list: `python3 .ai-sdlc/bin/sdlc.py plan-check <ID>` shows any
   drift. If reality forces a deviation, say so and record it in the plan; a plan quietly
   abandoned mid-build is how untraceable systems are made.

6. **Stay inside the ID.** Anything else you notice becomes a new backlog row, entered
   as `Parked` ("Work you discovered" in `00-operating-model.md`), never fixed in passing.
   Update any `project/` record this change falsifies, in the same change.

7. **Stop at the end of BUILD.** Commit with the ID in the message. Report what was built,
   what deviated from the plan and why, and what is next: `/sdlc-verify`. Do not call
   anything *Verified* here; that word belongs to the step that ran the checks.

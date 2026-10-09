---
description: Frame a request as a tracked work item and produce a reviewed plan
argument-hint: "[--mode lean|normal|beast] [--epic] <what you want built or changed>"
---

Run the FRAME → PLAN → DESIGN REVIEW steps of the loop in `AGENTS.md` for:

$ARGUMENTS

Follow `{{DOCS_DIR}}/process/00-operating-model.md`. Specifically:

1. **Read** `{{DOCS_DIR}}/project/charter.md` first — nothing else is reliable without it. If it
   is blank, fill in what you can establish from the repository (stack, commands,
   default branch) and **ask the user** for what you cannot: accountable human,
   approvers, jurisdictions, data categories, budgets. Do not invent them, and do not
   proceed past FRAME on a Tier 1 item with those blank — park it
   (`{{DOCS_DIR}}/process/00-operating-model.md`, "Waiting on a human"). Then read
   `{{DOCS_DIR}}/project/assumptions-and-risks.md`.

2. **Frame.** Restate the request in one sentence. If your restatement could plausibly
   mean something different from what was asked, ask now. Assign the next
   `{{PREFIX}}-###` — the highest number used anywhere in `{{DOCS_DIR}}/project/`, including
   `Dropped` rows, plus one; numbers are never reused. Classify the risk tier per "Risk
   tiers" in `AGENTS.md`, and add a terse row to `{{DOCS_DIR}}/project/backlog.md`. Check the
   Definition of Ready items knowable at FRAME (`{{DOCS_DIR}}/process/03-ready-and-done.md`) —
   if one fails, record the blocker rather than guessing past it. Resolve effort mode in
   this order: `--mode` or explicit request → recorded work-item override → charter
   default → `Normal`; record it separately from the risk tier. Resolve the development
   method the same way: `--epic` or an explicit request → the work item → the charter's
   **Development method** → `Item`. If it is `Epic`, follow
   `{{DOCS_DIR}}/process/11-epics.md` instead of steps 3–4 below: write
   `{{DOCS_DIR}}/project/epics/<ID>.md` from `{{DOCS_DIR}}/templates/epic.md`, add a backlog
   row per item ending `(in <ID>)`, review the epic plan once, and ask the human to
   approve it and to choose the checkpoints before any BUILD.

3. **Plan.** Read the existing implementation before proposing anything; most bad plans
   are written against an imagined codebase. If an upstream specification already exists
   (e.g. from GitHub Spec Kit, Kiro, `specs/`, or a provided spec file), adopt its problem
   statement, user stories, and acceptance criteria directly rather than re-asking what is
   already specified; reference the spec in the plan's approach. Apply the solution ladder
   from `AGENTS.md`, then produce a plan from
   `{{DOCS_DIR}}/templates/plan.md` — Tier 1 as a file in `{{DOCS_DIR}}/project/plans/`, Tier 2 inline,
   Tier 3 as a sentence. Include the alternatives you rejected and the reason each lost,
   the failure modes, the rollback, and what you are deliberately not doing.

4. **Design review.** Run `/sdlc-review` against the plan. Reviews at this stage read the
   plan and the current code, not a diff.

5. **Report** the tier, the plan, the findings, and the overall verdict. If any role
   returns Block, stop and say what needs deciding — do not proceed and note it.

Do not write implementation code in this command.

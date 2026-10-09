---
description: Run a multi-role review of the current changes (or a named artifact)
argument-hint: "[optional: a path, commit range, plan file, or work item ID]"
---

Run a role review per `{{DOCS_DIR}}/process/02-role-reviews.md` on:

$ARGUMENTS

(If no argument is given, review the uncommitted and unpushed changes on the current
branch.)

1. **Establish what you are reviewing.** Read the actual diff and the surrounding code.
   Run the thing if it runs. State the commit range or files you examined.

2. **Conformance pass first** (Tier 1 and 2, ship review). Ask whether the diff does what
   the plan and the acceptance criteria said, and nothing else. For Tier 1, run
   `python3 .ai-sdlc/bin/sdlc.py plan-check <ID>` and quote its output, then decide for
   each gap whether it is a plan that should have been updated or an unreviewed change.
   Walk each acceptance criterion to its code and test. Severities are in
   `02-role-reviews.md`, "The conformance pass".

3. **Select roles** by change surface and tier, using the table in
   `{{DOCS_DIR}}/process/02-role-reviews.md` and the active roster in
   `{{DOCS_DIR}}/project/charter.md`. Include the charter's project-specific role checks. Do not
   review with every role reflexively, and do not skip a role whose surface was touched.
   Apply the work item's effort mode: Lean uses the minimum applicable set, Normal uses
   the standard set, and Beast adds only roles materially adjacent to the change.

4. **For each role**, work through its playbook in `{{DOCS_DIR}}/roles/` against the real
   artifact. Produce:
   - **Checked:** what you examined and how — required even when there are no findings.
   - **Not checked:** what this review does not cover. Never imply coverage you lack.
   - **Findings:** severity (S0–S4 per `{{DOCS_DIR}}/process/04-quality-gates.md`), location as
     `file:line`, what is wrong, what goes wrong because of it, and what would fix it.
   - **Verdict:** derived from the worst severity, per the table in `02-role-reviews.md`.
     You rate the finding; the ladder decides the verdict. At most five S4 findings per
     review; give the rest as a count.

5. **Look hardest at what the change did not touch but should have** — the missing
   migration, the untouched test, the second code path with the same bug, the document
   the change just made wrong.

6. **Avoid the anti-patterns** listed at the end of `02-role-reviews.md`, which you
   should have open while reviewing.

7. **Record** to `{{DOCS_DIR}}/project/reviews/{{PREFIX}}-###-<design|ship>.md` using
   `{{DOCS_DIR}}/templates/role-review.md` for Tier 1; summarise in the response for Tier 2.

**A finding seen before.** If this review raises a finding an earlier review or
postmortem already raised, the correction becomes one line under "Known agent mistakes" in
`AGENTS.md` section 9, in the same change. The second occurrence is the signal. The first
is noise.

On a Block, stop and escalate with the finding, the options, and a recommendation
(`02-role-reviews.md`, "On a Block").

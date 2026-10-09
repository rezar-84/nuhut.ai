---
description: Run the project's full check sequence and report real results
argument-hint: "[optional: a stage, path, or work item ID to scope the run]"
---

Run the VERIFY step of the loop per `{{DOCS_DIR}}/process/04-quality-gates.md`, scoped to:

$ARGUMENTS

(If no argument is given, run the full sequence against the current working tree.)

**Run the script, not the commands by hand:**

```sh
python3 .ai-sdlc/bin/sdlc.py verify            # every stage
python3 .ai-sdlc/bin/sdlc.py verify --stage unit,lint
```

It does steps 1 and 2 below mechanically. It takes the commands from the charter, reports
any profile drift, runs each stage in order, and writes the raw output, exit codes and a
`summary.md` to `.ai-sdlc/evidence/<timestamp>/`. **Quote that summary for step 3**; its
Verified, Not run and Absent results are the evidence words, and the log files hold the
real output to paste. Steps 3–8 remain yours. Do steps 1 and 2 by hand only if the script
is missing or `python3` is not available.

1. **Get the command list.** Read `.ai-sdlc/profile.json` → `commands` if it exists: it is
   the charter's Commands table in machine-readable form, and it is the fastest route to
   the exact strings. Then read `{{DOCS_DIR}}/project/charter.md` → Commands and reconcile.
   **The charter wins on any conflict** — a human maintains it, the profile is derived —
   and a difference between the two is itself a finding to report and fix.

   Use the commands verbatim. Never invent one or infer it from the ecosystem: a guessed
   command that happens to exit zero produces a confidently false verification.

2. **Run each stage in order**, per the table in `04-quality-gates.md`:

   format → lint → typecheck → `checks.infra` → unit → integration → `checks.data` →
   contract → `checks.eval` → build → dependency/secret scan → accessibility →
   end-to-end → `checks.perf`

   The four conditional stages exist only where the project has that surface; where the
   charter has no command for one, it is **Absent**, which is a complete answer.

3. **Report each stage** in the vocabulary of `{{DOCS_DIR}}/process/06-evidence-and-claims.md`,
   with no synonyms:
   - **Verified**, and whether it passed or failed, with the real summary (counts,
     duration). Never describe a failing suite as "mostly passing" — paste the output.
   - **Measured** for a stage whose result is a number rather than a pass — evaluation,
     performance, data freshness. It carries method, subject and its version, N, spread,
     and date, and it is compared against the recorded baseline. A number with no
     baseline is a reading, not a gate: say so, and treat the missing baseline as the
     finding.
   - **Not run** — the stage exists, you did not execute it. Say why.
   - **Absent** — the charter has no command for this stage. An absent stage is a QA
     finding with a reason, not a neutral fact.

4. **Do not fix anything to make a check pass** in this command, and never disable, skip,
   or loosen one (`04-quality-gates.md`).

5. **Two stages do not simply go green.** An infrastructure plan showing a destroy, a
   replacement, or a permission widening is a review item for a named human before it is
   applied. A data-quality failure stops the pipeline; it never publishes and warns.

6. **Then verify behaviour, not only the build.** For anything user-facing, exercise the
   actual path in its real states: empty, loading, error, unauthorised, oversized input —
   and every supported locale, size, and permission level the charter names. For anything
   with a permission model, test the denial cases explicitly. For a probabilistic output,
   exercise the refusal path and the empty-retrieval path
   (`{{DOCS_DIR}}/process/09-probabilistic-and-data-systems.md`).

7. **Tear down ephemeral test environments.** If any stage or behavioural check spun up
   Docker containers, background servers, or mock daemons, stop and tear them down now
   (`docker compose down`, stopping test containers, killing spawned background
   processes). Confirm no orphaned test processes or containers remain running.

8. **Summarise** as a table of stage → result, then state plainly what is verified, what
   is not, and what you could not check from here.

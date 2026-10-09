# 02 — Role reviews

The mechanism that turns a single agent into a review board. This is the highest-value
part of the kit and also the easiest to fake, so the rules below are mostly about
preventing fake reviews.

---

## What a role review is

You adopt one role's playbook from `docs/roles/`, read the actual artifact — plan, diff,
running system — through that role's concerns only, and produce findings.

**It is not** a paragraph of praise per role. **It is not** a restatement of what the
change does. **It is not** a list of generic best practices that were not checked against
this code.

### The evidence rule for reviews

Every finding names a location and a consequence:

> `<file>:<line>` (or `<screen>` / `<endpoint>` / `<doc section>`) — *what is wrong* —
> *what goes wrong because of it* — *what would fix it*.

Every review states what it checked, including when it found nothing:

> Checked: all 6 new endpoints for authorisation on the object (not just the route),
> the two migrations for a down path, and the audit log for token leakage. No findings.

A review that cannot say what it checked did not happen. Write "not reviewed — no access
to X" rather than implying coverage you do not have.

### When an input does not exist

A role's **Reads** list names artifacts a project may not have created yet. A missing
input is never a reason to review from imagination, and never a silent gap. Report it in
the `Not checked` line as **Absent** (`06-evidence-and-claims.md`), name what you could
not therefore check, and raise it as a finding owned by whichever role owns that artifact
— usually S3, or higher where the missing artifact is the thing that would have caught a
real risk. "There is no threat model, so nobody has enumerated who can reach this" is a
security finding, not a formality.

---

## Stages

| Stage | Reads | Catches |
| --- | --- | --- |
| **Design review** — after PLAN, before BUILD | the plan + current code | wrong approach, missing constraint, unconsidered failure mode, scope that violates a policy |
| **Ship review** — after VERIFY, before merge/release | the diff + the running result | dead affordances, missing states, drifted copy, unhandled errors, missing tests, doc drift |

Design review is cheap and prevents expensive rework. Do not skip it to "just start
coding" on a Tier 1 or Tier 2 item.

### The conformance pass

Every ship review of a Tier 1 or Tier 2 item starts with one pass that belongs to no role:
**does the diff do what the plan and the acceptance criteria said, and nothing else?**

- For Tier 1, run `python3 .ai-sdlc/bin/sdlc.py plan-check <ID>` first. It lists the files
  the branch changed that the plan's "Files that change" does not name, and the planned
  paths nothing touched. Each gap is either a plan the build should have updated or a
  change nobody reviewed the approach for. The script finds the gaps and the reviewer
  decides which they are.
- Walk each acceptance criterion to the code and the test that proves it.
- Read the plan's "Out of scope" against the diff.

| Finding | Sev |
| --- | --- |
| An acceptance criterion not met, with the work called done | S1 (as in `roles/qa.md`) |
| Behaviour the plan put out of scope, shipped without a decision | S2 |
| A file or surface changed outside the plan, with the plan not updated | S3 |
| The plan describes code that does not exist (a planned step silently dropped) | S3 |

Record the conformance pass in the review file as its own section, before the roles.

---

## Who reviews what

Start from the charter's active roles, then select by **change surface** — what the work
actually touches — rather than reviewing with every role every time.

Effort mode adjusts breadth only after required roles are selected: Lean stops at the
minimum set below, Normal uses that set as written, and Beast adds a role only when an
adjacent consequence is concrete and named. No mode may omit a role selected by the
surface or add irrelevant reviews for appearance.

| The change touches… | Roles that must engage |
| --- | --- |
| Scope, priority, or what a user can do | product-manager |
| Module boundaries, dependencies, data flow, build/runtime shape | architect |
| Any screen, flow, or interaction | ux-designer, accessibility |
| Visual language, tokens, layout, imagery, brand expression | brand-designer |
| Any user-visible text | copywriter |
| Publicly discoverable content, URLs, metadata, structure | seo |
| Any user-visible text in a project that ships in more than one language | localisation |
| A conversion path, funnel step, form, pricing, or CTA | cro-analyst |
| Authentication, authorisation, secrets, input handling, sessions, isolation | security |
| Build, deploy, infra, config, observability, backups | devops-sre |
| Any behaviour with acceptance criteria | qa |
| Personal data, tracking, consent, retention, terms, claims about the business | privacy-legal |

**Tier 1** additionally engages product-manager, architect, security, and qa regardless
of surface — those four are the standing board for high-risk work.

**Tier 3** usually engages zero or one role. A typo fix in body copy engages copywriter,
nothing else.

---

## Verdicts

A role does not decide on its own authority whether a finding blocks. It rates each
finding on the severity ladder in `04-quality-gates.md`, and the ladder decides the
verdict. This is the only place blocking is defined; a role playbook that seems to say
otherwise is wrong, and the ladder wins.

| Verdict | When | Consequence |
| --- | --- | --- |
| **Pass** | Nothing found, or only S4 findings. | Proceed. |
| **Pass with conditions** | Worst finding is S3. | Each S3 becomes a backlog item with an ID and an owner before merge, not "later". |
| **Block** | Any S0, S1, or S2 finding. | Work stops. An S2 — and only an S2 — may be released by a named human's written waiver with a tracked follow-up (`04-quality-gates.md`). S0 and S1 are never waivable. |

The same three words are used for the review's overall outcome: it is the most severe
verdict any single role returned.

If you know the Important/Nit vocabulary, S0–S2 are *Important*: they block. S3 is tracked
work, and S4 is a *nit*: a real observation that changes no verdict.

### On a Block

1. Stop building. Do not "note and proceed".
2. Either fix it and re-review, or escalate to a human with the finding, the options,
   and a recommendation.
3. **You may not waive your own blocker.** A waiver requires a named human, a written
   reason, and a tracked follow-up item. Record all three in the review file.

This rule exists because the single most common way an agent-run process degrades is a
review that finds a real problem, notes it politely, and continues anyway. That is worse
than not reviewing — it launders the problem into a document that looks like diligence.

---

## Running a review well

**Do:**
- Read the real artifact. Open the files. Run the thing if it runs.
- Stay in role. The security reviewer does not comment on button radius; the brand
  reviewer does not comment on query performance. Cross-role concerns get handed to the
  owning role, not opined on.
- Rank by consequence, not by how easy the finding was to spot.
- Look hardest at what the change *did not* touch but should have — the missing
  migration, the untouched test, the doc now contradicted, the second code path with the
  same bug.
- Be specific enough that a fix requires no further investigation.

**Do not:**
- Pad with findings you do not believe, to look thorough. Three real findings beat
  fifteen padded ones, and padding trains the reader to skim.
- Repeat the same finding across roles. Assign it to the role that owns it and reference
  it from the others.
- Bury the review in nits. Report at most **five S4 findings per review**, choosing the
  ones most worth fixing, and give the rest as a count. Never report what the charter's
  checks already enforce (a lint rule, a formatter) or anything in generated files.
- Review your own plan sympathetically. The purpose is to find what you missed. Actively
  try to break your own approach; assume it is wrong and look for the reason.

---

## Record format

One file per review: `project/reviews/{{PREFIX}}-###-<design|ship>.md`, from
`templates/role-review.md`. Findings carry S0–S4 severity per `04-quality-gates.md`.

**Tier 1 only.** For Tier 2 the same content goes in the response and, durably, in the
worklog entry's **Reviews** section — no file. For Tier 3 it is one line in that section.
Add a row to the index in `project/reviews/README.md` for each file you create.

---

## Anti-patterns, named so they can be called out

| Anti-pattern | What it looks like | Fix |
| --- | --- | --- |
| **Rubber stamp** | "SEO review: metadata looks good. Pass." | State what was checked and how. |
| **Generic advice** | "Consider adding rate limiting" on a change with no endpoint. | Findings must be grounded in this diff. |
| **Severity inflation** | Everything is S1, so nothing is. | Reserve S0/S1 for actual data loss, security, or total unavailability. |
| **Severity deflation** | A cross-tenant leak logged as S3 because it is "unlikely". | Severity is by consequence, not by likelihood. |
| **Self-waiver** | "Blocked on X — proceeding as X is low risk." | Escalate. Only a human waives. |
| **Review theatre** | Thirteen role sections on a typo fix. | Select roles by surface and tier. |
| **Finding without location** | "Some error handling is missing." | Name the file and line. |

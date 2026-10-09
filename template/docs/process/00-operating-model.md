# 00 — Operating model

How an agent turns a request into shipped, documented, verified work.

---

## The loop

```
FRAME → PLAN → DESIGN REVIEW → BUILD → VERIFY → SHIP REVIEW → LOG → CLOSE
```

Each step below states its purpose, its output, and how it collapses for low-risk work.
Nothing is skipped; low-risk work simply produces a sentence where high-risk work
produces a document.

### 1. FRAME

Turn a request into a bounded unit of work.

- Restate the request in one sentence, in your own words. If your restatement and the
  request could plausibly mean different things, ask now — before planning, not after
  building.
- Assign or reuse a work item ID (`{{PREFIX}}-###`) and add it to
  `project/backlog.md`. A request that is really three tasks becomes three IDs.
- Classify the **risk tier** (see "Risk tiers" in `AGENTS.md`). This decides everything
  downstream, including how much of this document applies.
- Resolve the **effort mode** independently of risk: explicit request → recorded
  work-item override → charter default → `Normal`. Record it in the plan and worklog.
- Check `project/assumptions-and-risks.md` — the thing you are about to build may
  already be blocked on a decision nobody made.
- Check the Definition of Ready items marked **checkable at FRAME**
  (`03-ready-and-done.md`). The rest are gated at BUILD entry, because they depend on the
  plan you have not written yet.

**Output:** a backlog row with ID, one-line description, tier, owner role, dependencies,
and a status from the enum in `07-traceability.md`.

### 2. PLAN

Decide the approach before touching code.

- Read the existing implementation first. Most plans are wrong because they were written
  against an imagined codebase.
- Apply the solution ladder in `AGENTS.md`: no implementation → repository reuse →
  standard library → native platform → installed dependency → minimum custom code.
- State the approach, the files/areas affected, the data or contract changes, the test
  strategy, and the rollback story.
- Name the alternatives you rejected and why — one line each. This is what makes a plan
  reviewable rather than merely readable.
- List what you are *not* doing, so scope drift is visible.

**Output:** Tier 1 → `project/plans/{{PREFIX}}-###.md` from `templates/plan.md`.
Tier 2 → the same content, inline in the response. Tier 3 → one sentence.

### 3. DESIGN REVIEW

Vet the plan through the relevant role playbooks *before* building. Catching a
misconceived approach here costs minutes; catching it after implementation costs the
implementation.

See `02-role-reviews.md` for which roles engage at which tier. Reviews at this stage read
the plan and the current code, not a diff.

**Output:** Tier 1 → `project/reviews/{{PREFIX}}-###-design.md`. Tier 2 → findings
summarised in the response and in the worklog entry's **Reviews** section. Tier 3 → the
one role the surface selects, in a line; often that line is "no role's surface touched".

**A Block here stops the work.** Revise the plan and re-review, or escalate to a human.

### 4. BUILD

- Implement to the plan. If reality forces a deviation, say so explicitly and record it
  — a plan quietly abandoned mid-build is how untraceable systems are made.
- Write tests alongside the change, including failure and rejection paths.
- Keep the change scoped to the ID. Unrelated improvements become new backlog rows.
- Update any `project/` artifact the change falsifies, in the same change.
- For a defect, inspect all callers and shared paths and fix the common cause once where
  that is the correct boundary; do not patch only the reported symptom.

### 5. VERIFY

Run the checks the charter names, in the order given by `04-quality-gates.md`. Report the
actual result.

- Use the six words in `06-evidence-and-claims.md` exactly — *Verified*, *Reported*,
  *Assumed*, *Unknown*, *Not run*, *Absent* — and no synonyms. A check that exists and you
  did not run is *Not run*, with the reason. A check the charter has no command for is
  *Absent*. A result that is a number rather than a pass or a fail is *Measured*, and is
  not sayable without the five things that section requires of it.
- Failing output is pasted or summarised faithfully. Never describe a failing suite as
  "mostly passing".
- For anything user-facing, verify the behaviour, not only the build: exercise the actual
  path, in the actual states (empty, loading, error, unauthorised, long content).
- Tear down ephemeral test environments: if verification spun up containers, background
  servers, or mock daemons (e.g. Docker, Compose, local databases), stop and clean them
  up before proceeding to SHIP REVIEW, whether the checks passed or failed. Never leave
  idle test services consuming memory or holding ports.

### 6. SHIP REVIEW

Re-run the relevant role playbooks against the *diff and the running result*, not the
plan. Different findings surface here than at design time: dead buttons, missing empty
states, copy that says something the legal review would not allow, a migration with no
down path.

**Output:** Tier 1 → `project/reviews/{{PREFIX}}-###-ship.md`. Tier 2 → summarised.
Tier 3 → skipped.

### 7. LOG

For Tier 1 and Tier 2, append an entry to `project/worklog.md`, filling in every section
of `templates/worklog-entry.md`; `07-traceability.md` explains why each section exists.
For Tier 3, append the compact entry defined at the end of that template: date, ID,
request, changed files, verification result, and anything deferred. Expand to the full
template if the change uncovers risk, a durable decision, or unresolved work.

The worklog is prose and can be long; the backlog is a table and stays terse. Never fold
narrative into the backlog.

### 8. CLOSE

- Backlog status updated to one of the eight values in `07-traceability.md` — with a
  pointer to the worklog entry or the blocker, never a bare status change.
- New items created for everything discovered and not fixed.
- `assumptions-and-risks.md` updated: resolved entries closed, new unknowns added.
- Docs the change falsified are updated or marked `stale` (`07-traceability.md`).
- State completion plainly: what is done, what is verified, what is open.

---

## Waiting on a human

Parts of this kit require a person: two approvers for Tier 1 and one for Tier 2
(`05-change-control.md`), a named human for any waiver (`02-role-reviews.md`),
authorisation for anything irreversible or outward-facing. An agent running unattended
will reach those points with nobody to ask. A pull request awaiting its reviewer is one
of them — the work is `Parked`, not `Done`.

**That is a stopping condition, not an obstacle to route around.** Say so plainly rather
than downgrading the tier, splitting the work until no piece looks Tier 1, or recording
your own approval.

When you reach one:

1. **Finish everything that does not depend on the decision.** Build it, test it, review
   it. Parked work should need only the approval, not more work.
2. Set the backlog status to **`Parked`** and fill the Parked table: who is being waited
   on, for exactly what decision, and since when. "Needs review" is not a decision; "may
   we drop the legacy `session_token` column, which is unreadable after this migration"
   is.
3. Write the worklog entry now, not after approval. State what is built, what was
   verified, and what the human is deciding — including the option you recommend and why.
4. Leave the branch unmerged and say so in your closing report.

A later session resumes by reading the Parked table first: if the decision has been
recorded, continue from where the entry says the work stopped; if not, do not restart the
work, and do not re-ask if the question is already logged.

### Interrupted mid-loop

A session can also end without an answer being needed — context runs out, the user leaves.
Before you stop, the backlog status must name the loop step you actually reached
(`In progress` before VERIFY, `In review` after), and the worklog entry must exist even
if it says "incomplete — stopped after BUILD, checks not run". An item left `In progress`
with no entry is indistinguishable from an item nobody started, which is how work gets
silently done twice or not at all.

---

## Lifecycle modes

The loop is the same; the emphasis differs.

### Bootstrap — a new or newly adopted project

Run the gates in `01-lifecycle-gates.md` from G0. The first deliverables are documents,
not code: charter, product brief, discovery audit (if replacing something), architecture,
and a threat model if the risk surface warrants one. Resist writing code before the
charter names the stack — that decision is an ADR, not an accident.

### Change — the normal mode

The loop as written, scaled by tier.

### Incident — something is broken in production

Order changes: **contain → diagnose → fix → verify → log → postmortem.** Process is
compressed but not skipped, and the postmortem is mandatory for S0/S1
(`templates/postmortem.md`). Never let an incident fix bypass review permanently — it
gets a retroactive review and a real backlog ID within the next working session.

### Exploration — spike, prototype, research

Timeboxed and explicitly labelled. Its output is knowledge, not shippable code. A spike
branch is never merged directly; it produces a plan or an ADR, and the real
implementation runs the full loop. Say "this is a spike" in the worklog so nobody
mistakes it for a decision.

## Effort modes — Lean, Normal, Beast

These are three levels of work above the same risk floor, not three new risk tiers. The
mode is resolved at FRAME and stays attached to the work item:

| | Lean | Normal | Beast |
| --- | --- | --- | --- |
| **Explore** | Relevant path, contracts, and callers; structure-first for a large file | Complete affected flow | Affected and adjacent flows, history, operational effects, likely regressions |
| **Decide** | First solution-ladder rung that fully satisfies the request | Compare the obvious alternatives | Compare up to three viable approaches using repository evidence |
| **Review** | Minimum roles selected by tier and touched surface | Standard selection | Materially relevant and adjacent roles, never every role reflexively |
| **Verify** | Smallest meaningful tests, then every tier-required check | Standard test strategy and check sequence | Required checks plus relevant adversarial, recovery, concurrency, scale, or mutation checks |
| **Record** | Concise but complete form required by the tier | Standard templates | Expanded reasoning, alternatives, failure analysis, and operational consequences |

Beast maximises confidence, not implementation size: it cannot widen the requested
product scope or add speculative architecture. Lean cannot delete a required check,
review, record, approval, rollback, validation, security, privacy, accessibility, or
data-integrity control. If the user changes mode mid-item, record a plan delta and the
reason; never use the change to legitimise a skipped obligation retroactively.

An orchestrator passes the resolved effort mode, risk tier, and task boundary explicitly
to every reviewer or subagent. Do not rely on hidden session state or assume parent
context propagates.

---

## Deciding how much process applies

Ask, in order:

1. **Can this hurt someone or something?** (money, data, privacy, availability,
   reputation, legal exposure) → Tier 1, no exceptions.
2. **Does it change behaviour a user or another system depends on?** → Tier 2.
3. **Is it reversible in one commit with no consequence?** → Tier 3.

Two failure modes are equally bad, and the second is the more common with agents:

- **Under-process:** shipping an auth change with no review or test.
- **Over-process:** producing five review documents for a typo fix, burying real
  findings in ceremony, and exhausting the reader's attention so that the one real
  finding is skimmed.

Process is a tool for catching mistakes, not a performance of diligence.

---

## Working agreements

- **Read before writing.** Never rewrite a file you have not read.
- **One thing at a time.** Finish the loop for one ID before starting the next, unless
  they are genuinely independent.
- **Ask at the right time.** Do everything that does not depend on the answer first,
  then ask. Blocking with nothing delivered is for cases where any assumption could be
  unsafe or make the work useless.
- **Report faithfully.** If a step was skipped, say so. If a test fails, show it. A
  correct report of partial work is worth more than a confident report of imagined work.
- **Prefer the smallest change that fully solves the problem.** Then say what a larger
  change would have bought, and log it.

# 01 — Lifecycle gates *(appendix: standing up a project)*

> **Read this only when bootstrapping.** Seven gates carry a *new or newly adopted
> project* from idea to operation, once. They answer "what has to exist before this
> project is real?"
>
> **Ongoing work does not use gates.** Every change after bootstrap runs the loop in
> `00-operating-model.md`, and roles are selected by change surface and tier per
> `02-role-reviews.md` — not by gate. Two sequencing models running at once is how a
> process starts giving two answers to the same question, so the kit only has one: the
> loop. This document is the exception that applies once.

A gate is *passed* when its exit criteria are met and the artifacts it names exist. There
is no separate gate log; the artifacts are the record. The charter's **Artifacts in use**
checklist is where you see how far bootstrap has got.

---

## G0 — Discovery

**Purpose:** understand the problem, the users, and the ground truth before proposing
anything.

**Entry:** a request exists.

**Do:**
- Identify who has the problem, what they do today, and what it costs them.
- Audit what already exists: current system, data, content, traffic, integrations,
  contracts, constraints.
- Collect the non-negotiables — legal, regulatory, brand, budget, timeline, existing
  platform commitments.
- Write down what is *unknown*. This list is as valuable as what is known.

**Artifacts:** `project/charter.md`, `project/discovery-audit.md` (if something already
exists), `project/assumptions-and-risks.md` seeded with the unknowns.

**Exit:** the problem statement is written and an owner agrees it is the right problem.
Unknowns are recorded, not resolved — resolving them is later work.

**Common failure:** designing the solution during discovery, then rationalising the
research to fit it.

---

## G1 — Definition

**Purpose:** decide what will be built, for whom, and how success is judged.

**Entry:** G0 exit.

**Do:**
- Product brief: positioning, audiences, jobs-to-be-done, value, scope in/out.
- Success metrics with baselines. A metric without a baseline is a wish
  (`templates/measurement-plan.md`).
- User stories with acceptance criteria, prioritised.
- Explicit **Not now** list. Scope is defined by what you refuse.

**Artifacts:** `project/product-brief.md`, `project/user-stories.md`,
`project/measurement-plan.md`, populated `project/backlog.md`.

**Exit:** product-manager role review passes; every P0 story has testable acceptance
criteria; the scope boundary is written down.

**Common failure:** acceptance criteria that restate the story ("the user can log in")
instead of specifying observable behaviour including failure states.

---

## G2 — Design

**Purpose:** decide how it will work, before building it.

**Entry:** G1 exit for the increment in question.

**Do:**
- Technical architecture and the stack decision, each material choice as an ADR.
- Information architecture / navigation / interaction design, if there is an interface.
- Design system foundations: tokens, type scale, spacing, components, states.
- Data model and API/contract shape.
- Threat model if auth, tenancy, payments, PII, or public exposure are in scope.
- Content and SEO plan if the output is publicly discoverable.

**Artifacts:** `project/architecture.md`, `project/data-model-api.md`,
`project/design-system.md`, `project/threat-model.md`, `project/content-seo-plan.md`,
ADRs.

**Exit:** the architect, security, and — where there is an interface — ux-designer and
brand-designer reviews return *Pass* or *Pass with conditions* (`02-role-reviews.md`).
Every "we'll figure that out later" is a logged assumption with an owner.

**Common failure:** a design that never states its failure modes — what the system does
when the dependency is down, the input is hostile, or the list is empty.

---

## G3 — Build

**Purpose:** implement to the design, with tests, in traceable increments.

**Entry:** G2 exit; task passes Definition of Ready.

**Do:** the BUILD step of the loop, per work item.

**Artifacts:** code, tests, updated `project/` docs, worklog entries.

**Exit:** Definition of Done met for each item (`03-ready-and-done.md`).

**Common failure:** the design document and the implementation diverge and nobody
updates the design document, so it becomes actively misleading. Update it or mark it
`stale` — do not leave it confidently wrong.

---

## G4 — Verification

**Purpose:** prove it does what was specified, and does not do what was forbidden.

**Entry:** G3 exit for the increment.

**Do:**
- Run the full check sequence (`04-quality-gates.md`), not just the fast subset.
- Test the acceptance criteria as written, including negative and boundary cases.
- Run role ship reviews.
- Exercise real states: empty, loading, slow, error, unauthorised, oversized input,
  concurrent action, and — where relevant — every supported locale, device size, and
  permission level.

**Artifacts:** `project/test-plan.md` updated with what is actually covered,
`project/reviews/*-ship.md`, verification notes in the worklog.

**Exit:** no open S0, S1, or S2 findings, except an S2 waived in writing by a named human
per the severity ladder in `04-quality-gates.md`.

**Common failure:** verifying the happy path and calling it done; treating "it compiles"
as verification.

---

## G5 — Release

**Purpose:** get it into users' hands without breaking what already worked.

**Entry:** G4 exit.

**Do:**
- Follow `project/release-runbook.md`: pre-flight checks, migration order, deploy,
  smoke test, monitoring window, rollback trigger and procedure.
- Confirm backups/restores are current and *tested*, not merely configured.
- Announce what changed to whoever depends on it.

**Exit:** deployed, smoke-tested in the target environment, monitored for the agreed
window, rollback proven available.

**Common failure:** a rollback plan that has never been executed, and a migration with
no reverse path.

---

## G6 — Operate & learn

**Purpose:** find out whether it actually worked.

**Do:**
- Watch the metrics named in the measurement plan against their baselines.
- Triage incidents; postmortem anything S0/S1 (`templates/postmortem.md`).
- Feed findings back into the backlog as real items, not vague intentions. That includes
  findings nobody typed: an alert past its threshold, a scheduled scan, a failed pipeline an
  agent triaged. They enter through the same intake, with an ID and a tier. A dismissed
  finding is recorded with its reason, so it does not come back as new.
- Re-review documents whose `last-reviewed` date has aged past the charter's threshold.

**Exit:** none — this gate is continuous. It closes only when the project is retired.
Retirement is a Tier 1 change like any other and runs the loop: its plan covers data
export, redirects, credential revocation, and notifying whatever depends on it.

**Common failure:** shipping and never checking whether the success metric moved, so the
next decision is made on the same guesswork as the last one.

---

## Gate summary

| Gate | Question it answers | Roles engaged at least once |
| --- | --- | --- |
| G0 Discovery | What is really the problem? | product-manager |
| G1 Definition | What are we building and how will we know it worked? | product-manager; copywriter if there is messaging; privacy-legal if regulated |
| G2 Design | How will it work? | architect, security; ux-designer and brand-designer if there is an interface; seo if content is public |
| G3 Build | Is it built as designed? | qa, on each work item via the loop |
| G4 Verification | Does it do what we said, and refuse what we forbade? | qa, security; accessibility if there is an interface; cro-analyst if there is a conversion goal |
| G5 Release | Can we ship and un-ship safely? | devops-sre, security |
| G6 Operate | Did it work? | cro-analyst, product-manager |

These are the roles bootstrap must not finish without hearing from. Whether any given
finding stops the gate is decided the same way as everywhere else: by the severity of the
finding (`04-quality-gates.md`), not by which column a role appears in. Only roles the
charter marks active apply; a role switched off in the charter does not hold a gate.

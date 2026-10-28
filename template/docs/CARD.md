# Operating card — {{PROJECT_NAME}}

The whole standard, compressed. This replaces reading
[`process/02-role-reviews.md`](process/02-role-reviews.md),
[`process/04-quality-gates.md`](process/04-quality-gates.md),
[`process/06-evidence-and-claims.md`](process/06-evidence-and-claims.md), and
[`process/07-traceability.md`](process/07-traceability.md) for ordinary work.

**Open the full document when the card is not enough** — a contested severity, an
unusual evidence question, a traceability edge case, a review whose verdict is being
argued. **The full document wins on any conflict**; this card is a summary, not an
amendment.

---

## The loop

```
FRAME → PLAN → DESIGN REVIEW → BUILD → VERIFY → SHIP REVIEW → LOG → CLOSE
```

Depth scales with tier. Never skip LOG: for Tier 3 the commit message with the ID is the
log, and `sdlc.py log --since <ref>` drafts the rest from commits and verify runs.

## Tiers

| Tier | When | Required |
| --- | --- | --- |
| **1** | changes a contract others consume · stored data or its schema (migration, deletion, backfill) · authentication or authorisation · rules that move money · a release pipeline or infrastructure · a prompt or model in a system that acts · anything hard to reverse | plan · design + ship review · ADR · 2 human approvals · rollback plan |
| **2** | new or changed behaviour that tests can cover and a revert undoes · a new dependency · a refactor across boundaries · a prompt, retrieval or eval-threshold change | short plan · review of touched surfaces · tests · worklog entry · merge as the charter says |
| **3** | copy/typo · patch bump · comment · formatting · adding a test · doc edit | the commit message with the ID · current branch · no review file |

Tier by **blast radius and reversibility**, never by topic or line count. When in doubt,
tier up. Splitting a Tier 1 item until no piece looks Tier 1 violates the contract.

Worked examples:

| Change | Tier | Because |
| --- | --- | --- |
| One-line arithmetic fix in pricing, failing test first | 2 | sensitive area, but test-covered and reverted by one commit; no rule about money movement changes |
| One-line change to an authorisation check | 1 | authorisation |
| Fixing a typo in a payment error message | 3 | copy only |
| Adding a nullable column | 1 | stored data's schema |
| A new optional API field read by no other service yet | 2 | behaviour, reversible, no consumer bound to it |
| Changing what a public API returns for an existing field | 1 | a contract others consume |
| Bumping a dependency's patch version with the suite green | 3 | reversible, no behaviour change intended |

The charter's **Tier rules** row decides which rules apply. `Standard` (the default on a
new install) is this table. `Strict` keeps the 3.x rules, which an upgrade from 3.x sets
so nothing changes silently: any change touching auth, payments, personal data or
public copy is Tier 1, every tier writes a worklog line, and Tier 2 waits for one human
approver.

---

## Effort modes

Resolve independently of tier per [`process/00-operating-model.md`](process/00-operating-model.md):
explicit request → recorded work-item override → charter default → `Normal`. Record the
effective mode in the plan and worklog.

| Mode | Above the unchanged risk floor |
| --- | --- |
| **Lean** | Targeted reading (`CARD.md` only unless a rule is contested); first sufficient rung of no implementation → repository reuse → stdlib → native platform → installed dependency → minimum custom code; minimum applicable roles in a single combined review pass; concise required records (`sdlc.py log --write` one-line worklog); smallest meaningful tests, then every tier-required check. |
| **Normal** | Current balanced flow, obvious alternatives, standard role and test selection. |
| **Beast** | Maximum confidence: adjacent flows/history, up to three viable alternatives, materially adjacent roles, and relevant adversarial/recovery/concurrency/scale checks. Never extra product scope or speculative code. |

No mode weakens requested scope, validation, security, privacy, accessibility, data
integrity, evidence, traceability, rollback, approvals, or tier requirements. Pass the
resolved mode and tier explicitly to subagents; do not rely on hidden session state.

## Development method

Request → work item → charter **Development method** → `Item`. **Item**: one item at a
time, as today. **Epic** ([`process/11-epics.md`](process/11-epics.md)):
- One epic file (`templates/epic.md`) holds the plan, item table, design review and
  checkpoint log.
- A human approves that plan before the first build, unless every item is Tier 3.
- Each item keeps its own branch, tests, checks and ship review at its tier.
- A verified Tier 2 or Tier 3 item merges into the epic branch, and the agent continues.
- At each checkpoint the plan chose (per phase, every N items, or at the end), the agent
  writes one worklog entry and proposes the epic branch. The highest tier merged since
  the last checkpoint sets the approvers.
- **Hard stops, whatever the checkpoints:** a Tier 1 item (its own plan, two approvers,
  park it and carry on with independent items), a Block, a failed verification outside
  scope, a plan that proves wrong, or anything irreversible or gated.

## Decision style

Request → work item → charter **Decision style** → `Guide` ([`process/14-decision-style.md`](process/14-decision-style.md)). **Ask** puts every material choice to the person with options and trade-offs. **Guide** recommends one option in plain language and asks. **Autopilot** takes the recommended option, logs it `(auto)`, and lists `(auto)` choices for review. No style lifts a Tier 1 stop, a gated command, or an ADR.

---

## Evidence — the seven words

Use exactly these. No synonyms. Not "should work", "looks right", "mostly passing".

| Word | Means |
| --- | --- |
| **Verified** | You ran it this session and read the output. |
| **Reported** | A tool, log, or person said so. Name the source. |
| **Assumed** | Proceeding on it, and it is in the assumptions register. |
| **Unknown** | You cannot establish it. A complete answer. |
| **Not run** | The check exists; you did not run it. Say why. |
| **Absent** | No such check exists here. A finding for the owning role, not a neutral fact. |
| **Measured** | The result is a number, not a pass. Conditions below. |

**Measured** carries all five, or it is not a claim: **method · subject and its version ·
N · spread · date and environment**. A number with no baseline is not an improvement, it
is a number. One run of a non-deterministic system is a sample. Comparing two
measurements requires the same subject version, environment, and seed policy — change
the system or the measurement, never both.

**Never invent** a metric, date, benchmark, quote, credential, or citation. Missing fact
→ write `_(unverified — needs confirmation: <what, from whom>)_` and log it in
`project/assumptions-and-risks.md`.

---

## Checks

Run in this order; take the commands verbatim from `project/charter.md` → Commands.

```
format → lint → typecheck → [complexity] → [infra] → unit → [mutation] →
integration → [data] → contract → [eval] → build → scan → a11y → e2e → [perf]
```

Bracketed stages exist only where the project has that surface. **Absent** if the charter
names no command; **Not run** with a reason if you skipped it. Neither is assumed to pass.
`[complexity]`, `[eval]`, and `[perf]` report **Measured**, never "passed". An `[infra]` plan showing a
destroy, replacement, or permission widening goes to a named human before it is applied.
A `[data]` failure stops the pipeline; it never publishes and warns.

Tier 1 and 2 run everything. Tier 3 runs what can plausibly be affected and reports the
rest **Not run — Tier 3, no code path affected**.

Tear down ephemeral test environments immediately: stop and clean up containers, test
databases, and mock daemons on completion (pass or fail). Leaving containers or
background servers running is a defect.

Never disable, skip, or loosen a check to make a change pass. A flaky test is a defect
with a measured failure rate — characterise it, do not re-run until green. For a defect,
commit the failing reproducing test **before** the fix, and do not edit it while fixing.

---

## Severity and verdict

| Sev | Means | Consequence |
| --- | --- | --- |
| **S0** | Irreversible or unbounded harm: data loss, breach or credential leak, one user's data reachable by another, total unavailability, unlawful handling of special-category data, a report that makes every other report untrustworthy. | Stop. Incident process. |
| **S1** | Serious harm, no workaround: a core journey unusable; an S0-kind defect not yet fired (injectable query, reachable known-vulnerable dependency, never-executed recovery path); legal exposure. | Release blocker. |
| **S2** | Real harm, poor workaround: important function degraded, a misleading claim shown to users, an a11y barrier on a still-usable surface. | Blocker unless a named human waives it in writing with a tracked follow-up. |
| **S3** | Localised defect, or a `project/` document that has drifted. | Scheduled fix. |
| **S4** | Cosmetic. | Backlog. |

**S0 vs S1** is not "did it happen yet" — it is whether anything stands between the
defect and the harm. **S2 vs S1** is "poor workaround" vs "no workaround".

| Verdict | When |
| --- | --- |
| **Pass** | Nothing, or only S4. |
| **Pass with conditions** | Worst is S3 — each becomes a backlog item with an ID and owner *before merge*. |
| **Block** | Any S0, S1, or S2. |

A role rates; **the ladder decides the verdict**. **You may not waive your own blocker** —
that needs a named human, a written reason, and a tracked follow-up. Noting a real problem
politely and continuing is worse than not reviewing: it launders the problem into a
document that looks like diligence.

A review that finds nothing must say what it checked and how, and what it did **not**
cover. A Tier 1/2 ship review opens with the **conformance pass**: the diff against the plan
(`sdlc.py plan-check <ID>`) and each acceptance criterion. At most five S4 findings; count
the rest.

---

## Traceability

`{{PREFIX}}-###`. Sequential, never reused, never renumbered, permanent once it appears.
**Next ID** = highest number anywhere under `project/` — including `Dropped` rows, the
worklog archive, and review filenames — plus one, *not* the last row of the active table.
Work that shipped without one gets it retroactively, noted as retroactive.

| Record | File | Grows by |
| --- | --- | --- |
| Backlog | `project/backlog.md` | new rows, status edits |
| Worklog | `project/worklog.md` | append only, newest first |
| Decisions | `project/adr/NNNN-*.md` | new files; superseded, never edited |
| Reviews | `project/reviews/{{PREFIX}}-###-<stage>.md` | new files (Tier 1 only) |

Backlog row, positional: `| ID | Task | Tier | Owner role | Depends on | Status |`

Status: `Ready` · `Blocked` (never started) · `In progress` · `In review` (includes
holding a Block) · `Parked` (waiting on a named human; also where an item you discovered
and filed unasked enters, never `Ready`) · `Done` (worklog entry exists) · `Deferred` ·
`Dropped`. A Tier 3 change needs no backlog row: its commit is its record.

**Keep the backlog terse — narrative goes in the worklog.** This is the most-broken
formatting rule in the kit.

Review records: Tier 1 → a file per review. Tier 2 → the worklog entry's Reviews section.
Tier 3 → none.

---

## The loop's commands, on any tool

These names mean the same loop step on every tool. Claude Code has them as `/` commands,
and tools that list skills (Antigravity, Codex, Cursor, Gemini CLI, Copilot) have them as
skills of the same name. On a tool with neither, read a request in this form as the step
it names. **Never map an unknown `/sdlc-*` name to the nearest skill**: if it is not in
this table, say so and ask.

| Name | Runs | Stops before |
| --- | --- | --- |
| `sdlc-plan` | FRAME → PLAN → DESIGN REVIEW (`process/00-operating-model.md`) | any code |
| `sdlc-build` | BUILD, for an ID whose plan is approved | VERIFY; nothing is called *Verified* |
| `sdlc-verify` | VERIFY, through `sdlc.py verify` (`process/04-quality-gates.md`) | fixing anything |
| `sdlc-review` | DESIGN or SHIP REVIEW by the active roles (`process/02-role-reviews.md`) | merging |
| `sdlc-log` | LOG → CLOSE (`process/03-ready-and-done.md`) | |
| `sdlc-doctor` | the record audit, through `sdlc.py doctor` | fixing what needs a human |

## What to open next

| When | Read |
| --- | --- |
| No work item for this request | `process/07-traceability.md`, and the intake skill if installed |
| About to claim done / passing / verified | The evidence table above; escalate to `process/06-evidence-and-claims.md` |
| A decision expensive to reverse | `templates/adr.md` |
| A role's surface is touched | that `roles/<role>.md` — every one the change selects |
| Standing up a new project | `process/01-lifecycle-gates.md` |
| Branch, commit, PR, approval, rollback, managed platform | `process/05-change-control.md` |
| Is it ready to start / actually finished | `process/03-ready-and-done.md` |
| UI added or changed | `roles/accessibility.md`, `roles/ux-designer.md` |
| Public pages, copy, routes, metadata | `roles/seo.md`, `roles/copywriter.md` |
| Forms, analytics, tracking, logs, public claims | `roles/privacy-legal.md` |
| Auth, uploads, payments, an external interface | `roles/security.md`, `templates/threat-model.md` |
| Shipping to a real environment | `templates/release-runbook.md`, and `platforms/` for each platform the charter names |
| Something broke, or a release was reverted | `templates/postmortem.md` |
| A bug or tester defect is reported | `templates/defect-report.md`, `roles/qa.md` |
| Strings, screens, or locales change | `process/08-content-and-translation.md` |
| A platform co-owns this repo | "Managed platforms" in `process/05-change-control.md` |
| Prompt, model, retrieval, index, dataset, pipeline, or eval changes | `process/09-probabilistic-and-data-systems.md` |
| A schema migration or backfill | `roles/devops-sre.md`, `roles/data-engineer.md` |
| A contract crosses a service boundary | `roles/architect.md` ("Across a service or process boundary") |
| A hot path, query, payload, or cache changes | `roles/performance-engineer.md` |
| Fetching third-party data | `roles/privacy-legal.md`, `roles/data-engineer.md` |
| More than one agent is working this repository | `process/10-multi-agent.md` |
| The development method is `Epic` | `process/11-epics.md`, `templates/epic.md` |
| A stack, runtime, database, framework or host is chosen or moved across a major version | `process/13-stack-evaluation.md`, `templates/adr.md` |
| A choice the request did not settle, or a non-specialist is being asked | `process/14-decision-style.md` |
| A person pastes a secret or personal data, or a record is about to quote one | `process/12-sensitive-data-in-records.md` |

This table is the routing that a tool which loads skills (from `.claude/skills/` or
`.agents/skills/`) gets from their descriptions. On any other agent tool, it is the
routing.

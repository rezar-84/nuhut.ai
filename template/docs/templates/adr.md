---
status: proposed
owner: _(named decider)_
last-reviewed: YYYY-MM-DD
---

# ADR NNNN — <decision in a noun phrase>

- **Status:** Proposed | Approved | Superseded by NNNN | Deprecated
- **Date:** YYYY-MM-DD
- **Deciders:** _(who actually decided — a named human for Tier 1)_
- **Work item:** {{PREFIX}}-###

## Context

_(The forces at play: the requirement, the constraints, what already exists, what the
charter mandates, what we do not know yet. Written so that someone who disagrees with the
decision can still recognise their own concerns here.)_

## Decision

_(What we are doing. Present tense, active: "We store X in Y." One paragraph.)_

## Consequences

**Accepted:**
- _(What this makes harder, slower, more expensive, or locks us into.)_

**Gained:**
- _(What this makes possible or cheaper.)_

**Follow-ups:**
- _({{PREFIX}}-### — work this decision creates.)_

## Version facts

_(For a stack, runtime, database, framework, language, hosting, or base-image choice. Read
from the official release and support pages, never recalled; see
`../process/13-stack-evaluation.md`. A fact that could not be checked is written
`Unknown — not verified`. Delete this section for a decision that picks no version.)_

- **Chosen:**
- **Latest stable:**
- **Support ends:** YYYY-MM-DD
- **Verified on:** YYYY-MM-DD
- **Source:**
- **If not the latest stable, why:**

## Alternatives considered

### <Option>
_(Compared on the criteria in `../process/13-stack-evaluation.md` where this is a stack choice. What it was, and the actual reason it lost. "Not a good fit" is not a reason. "Requires
an operational capability the team does not have and cannot acquire this quarter" is.)_

## Reversibility

_(What it would cost to change our minds in six months, and what would trigger that.)_

---

<!--
Rules (see ../process/05-change-control.md):
- Number sequentially, never renumber, never reuse.
- Never edit the Decision of an Approved ADR. Write a new ADR that supersedes it and
  link both directions. The record of what was decided and later abandoned is the most
  valuable part of the archive.
- Write one when the decision is expensive to reverse, or when a future reader would
  otherwise have to reverse-engineer the reasoning from the code.
-->

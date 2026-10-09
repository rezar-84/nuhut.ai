---
status: draft
owner: architect
last-reviewed: YYYY-MM-DD
---

# Technical architecture — {{PROJECT_NAME}}

> Describes what exists, not what was once planned. When the code and this document
> disagree, **the code is right and this document is a defect** — update it or mark it
> `stale` with a backlog item.

## Stack

**What** the project is built with is declared once, in `charter.md` → Stack. Do not copy
that table here; a second copy is a second thing to update and the one that will be
wrong. This section records only **why**, and the choices the charter has no row for.

| Concern | Choice | Why this, not the obvious alternative | ADR |
| --- | --- | --- | --- |
| _(from the charter's Stack table — one row per choice worth explaining)_ | | | |
| Cache / queue | | | |
| Observability | | | |

## Constraints that shaped this

The constraints themselves live in `charter.md` → Constraints. Record here how each one
actually bent the design — a constraint that changed nothing did not shape anything, and
saying so is also useful.

_(Team size and skills, operational capacity, budget, latency and availability targets,
data residency, existing commitments, regulatory requirements. An architecture is only
judgeable against these — record them or the design cannot be reviewed.)_

## Shape

_(A diagram or an ASCII sketch, plus a paragraph. What are the deployable units, what
talks to what, and where does data live?)_

```
<sketch>
```

## Components

| Component | Responsibility | Owns (data) | Depends on |
| --- | --- | --- | --- |
| | | | |

**Boundary rules** — what may call what, what is public, what is internal. State them
explicitly; an unstated boundary is not a boundary.

## Data flow

_(For the two or three most important operations: where the request enters, what it
touches, what it writes, what it returns. Include where identity and entitlement are
established.)_

## External dependencies

| Service | Used for | Failure behaviour | Timeout | Fallback |
| --- | --- | --- | --- | --- |
| | | | | |

Every row must have a failure behaviour. "It will be fine" is not one.

## Cross-cutting concerns

- **Identity & authorisation:** _(where identity is established, where entitlement is
  enforced — name the layer)_
- **Configuration:** _(how it is supplied and validated)_
- **Error handling:** _(the convention — what is caught where, what surfaces to users)_
- **Logging & tracing:** _(format, correlation, what is never logged)_
- **Background work:** _(scheduling, idempotency, monitoring)_
- **Caching:** _(what, where, invalidation, and the staleness this accepts)_

## Known limitations

_(What this design does not handle well, and at what point it stops being adequate.
Written honestly, this is the most useful section for whoever comes next.)_

## Non-goals

_(Explicitly out of scope for this architecture, so nobody re-litigates it.)_

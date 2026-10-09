---
status: draft
owner: product-manager
last-reviewed: YYYY-MM-DD
---

# Backlog — {{PROJECT_NAME}}

> **This table stays terse. One line per item.** Narrative — what happened, what was
> verified, what was discovered — goes in `worklog.md`, found via the ID.
>
> Column rules, the eight status values, and why the separation matters:
> `../process/07-traceability.md`.
>
> **How the sections and the eight statuses line up.** An item's row moves between
> sections as its status changes; the `Status` cell is always the precise value.
>
> | Section | Statuses it holds | Columns |
> | --- | --- | --- |
> | Now | `In progress`, `In review` | the six-column spec |
> | Next | `Ready` | the six-column spec |
> | Blocked | `Blocked` | six-column spec **+ Who can unblock, Since** |
> | Parked | `Parked` | six-column spec **+ Waiting on whom, For what decision, Since** |
> | Later | `Deferred` | six-column spec **+ Becomes relevant when** |
> | Done | `Done` | six-column spec **+ Completed** |
> | Dropped | `Dropped` | six-column spec **+ Why dropped, When** |
>
> Every section carries the six mandated columns, in order, and adds its own to the
> right. A row never loses a cell by moving — that is how the Owner role and Tier of a
> finished item survive to be looked up later.

## Now

Actively in progress. Keep this short enough to be real — if everything is here, nothing
is prioritised.

| ID | Task | Tier | Owner role | Depends on | Status |
| --- | --- | --- | --- | --- | --- |

_(No rows yet. The first item is `{{PREFIX}}-001`; delete this line once it exists.)_

## Next

Agreed, not started. Ordered by priority.

| ID | Task | Tier | Owner role | Depends on | Status |
| --- | --- | --- | --- | --- | --- |

## Blocked

Cannot proceed. The blocker must be a real, identified thing with an owner — not "needs
more thought".

| ID | Task | Tier | Owner role | Depends on | Status | Who can unblock | Since |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Parked — awaiting a human

Built and verified as far as an agent can take it; stopped at an approval or a waiver
only a named human can give. This is a finished state for the agent, not an excuse to
proceed. See "Waiting on a human" in `../process/00-operating-model.md`.

| ID | Task | Tier | Owner role | Depends on | Status | Waiting on whom | For what decision | Since |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Later

Valid, not now. Include the condition that would make it now.

| ID | Task | Tier | Owner role | Depends on | Status | Becomes relevant when |
| --- | --- | --- | --- | --- | --- | --- |

## Done

Newest first. Move to `worklog-archive/` once this section gets long — the worklog is the
permanent record, and the entry is found by ID.

| ID | Task | Tier | Owner role | Depends on | Status | Completed |
| --- | --- | --- | --- | --- | --- | --- |

## Dropped

**Never delete a row — move it here.** The record that something was considered and
rejected stops it being proposed, discussed, and rejected again. The ID stays reserved.

| ID | Task | Tier | Owner role | Depends on | Status | Why dropped | When |
| --- | --- | --- | --- | --- | --- | --- | --- |

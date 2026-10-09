---
name: sdlc-adr
description: Write or supersede an Architecture Decision Record. Use whenever a decision would be expensive to reverse or a future reader would otherwise have to reverse-engineer it — a new dependency, data model, auth model, hosting or deployment change, protocol or API shape, vendor choice, or a deliberate trade-off against a charter constraint.
---

# ADR — record the decision, not the outcome

An ADR exists so the next person does not re-litigate a settled question, and so a wrong
decision can be found and reversed on purpose rather than discovered by archaeology.

## When one is required

`AGENTS.md` §6: anything expensive to reverse, or that a future reader would otherwise have
to reverse-engineer. In practice: dependencies, data models, auth, hosting, protocol or
interface shape, vendor lock-in, and any deliberate exception to a charter constraint.

If a decision was durable and you are not writing an ADR, say why in the worklog.

## How

1. Read the existing ADRs in `{{DOCS_DIR}}/project/adr/` first. The decision may already
   exist, may be superseded, or may contradict what you are about to record.
2. Use `{{DOCS_DIR}}/templates/adr.md`. Number sequentially; never reuse a number.
3. Write the **context** as the forces, not the conclusion: the charter constraint, the
   load, the team, the deadline, the thing that could not be changed.
4. Record the **alternatives** and why each lost. An ADR with one option is a note, not a
   decision — and the rejected options are what a future reader actually needs.
5. State the **consequences**, including the bad ones: what becomes harder, what is now
   locked in, what will have to be revisited and under what trigger.
6. Link the work item ID and any related ADRs.

## Superseding

Never edit the decision of an accepted ADR. Write a new one, set the old one's status to
`superseded by ADR-###`, and say in the new one what changed in the world — not merely that
someone now prefers something else.

## Output

The ADR file path, its number and title, and a one-line summary in the worklog entry for
the work item that produced it.

---
name: sdlc-data-contract
description: Check a change to a dataset, table, view, event payload, message schema, or pipeline output before it ships — adding, removing, renaming, or retyping a field, changing a grain or meaning, or publishing something new. Use when a schema or published data shape changes, or when another system reads what this change produces.
---

# Data contract — who breaks when this ships

`{{DOCS_DIR}}/roles/data-engineer.md` is the review and
`{{DOCS_DIR}}/process/09-probabilistic-and-data-systems.md` §7–8 the standard. This skill
is the check before a published shape changes.

## First: is it published?

Look in the charter's **Data ownership** table. If nothing outside this project reads it,
this is an ordinary schema change — `architect` and `qa` cover it, and you can stop here.
If something does read it, or you cannot tell, continue. "Whoever queries it" means the
consumer set is unknown, and unknown consumers are broken silently.

## Classify the change

**Additive** — a new optional field, a new enum value where consumers ignore unknowns.
Announce it; no coordination needed.

**Breaking** — removing or renaming a field, narrowing a type, tightening a constraint,
changing a unit, timezone, or default, changing what a null means, or changing the grain.
Requires, before shipping: agreement from every named consumer, a version, and an overlap
window in which both shapes work. **A breaking change discovered by a consumer is this
project's failure**, rated S1.

Changing the *meaning* of a field while its name and type stay the same is the most
dangerous case on this list, because no schema check will catch it and every consumer
will keep working while producing wrong answers.

## Check

- [ ] The grain is unchanged, or the change is announced as breaking. "One row per X" is
      part of the contract even when it is written nowhere.
- [ ] Freshness, volume, uniqueness, ordering, and delivery guarantees still hold — and
      each is a number a check can test, not an adjective.
- [ ] The producer is idempotent, and a consumer that sees the same record twice is safe.
      At-least-once is the assumption unless something proves otherwise.
- [ ] Data-quality gates cover the new shape, in order: schema, freshness, volume,
      nullability, integrity, invariants. A failure **stops the pipeline** — it never
      publishes partial data and logs a warning.
- [ ] Personal data in the change is classified and its deletion path reaches every
      derived copy: caches, exports, search indexes, embeddings (`privacy-legal`).
- [ ] Backfilling existing rows is planned as its own Tier 1 item, not smuggled in.

## Record it

Create or update the contract from `{{DOCS_DIR}}/templates/data-contract.md`, name the
owner and the consumers, and add the row to the charter's **Data ownership** table. Then
say plainly, in the worklog, which consumers you notified and which you could not reach.

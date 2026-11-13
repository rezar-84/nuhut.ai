---
status: draft
owner: data-engineer
last-reviewed: YYYY-MM-DD
---

# Data contract — _(dataset, table, or stream name)_

One contract per published dataset, table, topic, or event type. It exists so a producer
can tell whether a change is safe, and a consumer can tell what they are entitled to rely
on. Copy this file per contract; name it after the thing it describes.

If nothing outside this project reads it, you do not need a contract — say so in the
charter's **Data ownership** table and stop here.

## Identity

| | |
| --- | --- |
| **Name** | _(the physical table, topic, path, or endpoint)_ |
| **Owner** | _(a named person or team. "The data team" is not an owner)_ |
| **Version** | |
| **Status** | _(active / deprecated on YYYY-MM-DD / superseded by …)_ |
| **Consumers** | _(named systems and their owners. "Whoever queries it" is not a consumer set, and an unnamed consumer will be broken silently)_ |

## What one row or message means

**Grain:** _(exactly what one record represents — "one completed order", "one page view
per session per day". Two engineers assuming different grains is a quarter-end
incident.)_

**Semantics that the types do not carry:**

- _(timezone and whether timestamps are event time or processing time)_
- _(currency, unit, and precision)_
- _(what a null means here — absent, unknown, or not applicable are three different things)_
- _(append-only, corrected in place, or soft-deleted)_
- _(which values are enumerated, and where that list is maintained)_

## Schema

| Field | Type | Required | Constraints | Personal data? | Meaning |
| --- | --- | --- | --- | --- | --- |
| | | | _(unique, range, enum, foreign key)_ | _(yes → `privacy-legal`)_ | |

**Keys:** _(primary/natural key, and the dedupe key a consumer should use)_

## Guarantees

The promises a consumer may build on. Each is a number a check can test, not an
adjective — `checks.data` in the charter enforces them.

| Guarantee | Value | What happens when it is breached |
| --- | --- | --- |
| **Freshness** | _(e.g. no more than 2h behind event time, by 06:00 UTC)_ | |
| **Volume** | _(expected range per period)_ | |
| **Completeness** | _(required fields non-null at what rate)_ | |
| **Uniqueness** | _(on which key)_ | |
| **Ordering** | _(guaranteed, per-key, or none — say "none" rather than leaving it blank)_ | |
| **Delivery** | _(at-least-once / at-most-once / exactly-once within a partition — consumers must be idempotent unless this says otherwise)_ | |
| **Retention** | _(how long records are kept and what removes them)_ | |
| **Availability** | _(when it is expected to be queryable)_ | |

**Late, duplicate, and out-of-order records:** _(the stated policy. Silence means the
policy is whatever the code happens to do, which nobody has read.)_

## Change policy

- **Additive changes** — a new optional field, a new enum value where consumers ignore
  unknowns. Announce, do not coordinate.
- **Breaking changes** — removing or renaming a field, narrowing a type, changing a
  meaning, changing the grain, tightening a constraint. Requires: agreement from every
  named consumer **before** shipping, a new version, and an overlap window during which
  both run.
- **Deprecation** — announced with a date, kept alive for _(period)_, and removed only
  after every named consumer has confirmed migration.

A breaking change discovered by a consumer is the producer's failure, and it is rated S1
in `../roles/data-engineer.md`.

## Lineage

| | |
| --- | --- |
| **Produced by** | _(the job or service, and its schedule)_ |
| **Reads from** | _(upstream sources, and their contracts if they have them)_ |
| **Transformations** | _(what is computed, filtered, joined, or aggregated on the way)_ |
| **Runbook** | _(link to `pipeline-runbook.md`)_ |

## Personal and acquired data

| | |
| --- | --- |
| **Personal data classes** | _(or "none" — reviewed by `privacy-legal`)_ |
| **Lawful basis** | |
| **Acquired from** | _(source and the terms it was obtained under, or "produced here")_ |
| **Deletion path** | _(how a deletion request reaches this dataset and everything derived from it — caches, exports, indexes, embeddings)_ |

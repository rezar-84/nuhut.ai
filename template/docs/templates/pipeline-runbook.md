---
status: draft
owner: data-engineer
last-reviewed: YYYY-MM-DD
---

# Pipeline runbook — {{PROJECT_NAME}}

What an operator needs at 3am, when a scheduled job has failed and the person who wrote
it is asleep. One section per pipeline, or one copy of this file per pipeline if there
are many. Written to be *followed*, not read: every step is a command or a decision, not
a description.

## Inventory

| Pipeline | Trigger / schedule | Reads | Writes | Owner | Runbook section |
| --- | --- | --- | --- | --- | --- |
| | _(cron, event, manual)_ | | _(link its `data-contract.md`)_ | | |

## Per pipeline

### _(name)_

**Purpose:** _(one sentence — what would be missing if it never ran again)_

**Normal behaviour**

| | |
| --- | --- |
| **Runs** | _(schedule, timezone, and expected duration)_ |
| **Expected volume** | _(rows or messages per run, and the acceptable band)_ |
| **Cost per run** | _(compute, storage, egress — and what a runaway input would cost)_ |
| **Downstream** | _(who notices within the hour if this does not run)_ |
| **Where to look** | _(dashboard, log stream, run history — the actual link)_ |

**Idempotency:** _(what makes a second run of the same input safe — natural key, dedupe
store, conditional write, or truncate-and-load. If nothing does, that is the finding.)_

**Data-quality gates:** _(which checks run, in the order of
`../process/09-probabilistic-and-data-systems.md` §7, and the fact that a failure stops
the run rather than publishing with a warning.)_

### When it fails

| Symptom | Likely cause | What to do | Safe to just re-run? |
| --- | --- | --- | --- |
| _(exit non-zero)_ | | | |
| _(succeeded but volume anomalous)_ | | | |
| _(did not start at all)_ | | | |
| _(still running past its window)_ | | | |

**A partial run leaves:** _("nothing published" / "records up to checkpoint X" / "the
target table in an intermediate state"). "Some of it went through" is not a state — say
which, and how to tell.)_

**Stop it:** _(the exact command or control, and what happens to work in flight)_

### Replay

_(Re-running a past window from source, without hand-editing state. The whole point of
this section is that it is a procedure and not an improvisation.)_

1. _(command, with the window as a parameter)_
2. _(what to verify afterwards, and against what)_

**Constraints:** _(concurrency with the live schedule, rate limits, and whether replaying
one window can corrupt an adjacent one)_

### Backfill

A backfill is a Tier 1 shape (`AGENTS.md`), even when it is one command.

| | |
| --- | --- |
| **Blast radius** | _(what changes, how many rows, and who consumes them)_ |
| **Batch size and rate** | _(so it does not starve production)_ |
| **Checkpointing** | _(how to resume after stopping halfway)_ |
| **Stopping halfway** | _(what state that leaves, and whether it is publishable)_ |
| **Reverse path** | _(the tested procedure — or the named human who accepted in writing that there is none, and when)_ |
| **Verification** | _(the counts and distributions to compare, before and after)_ |

### Recovery of last resort

_(Where the source of truth is, how far back it goes, and how to rebuild this dataset
from nothing. An untested restore is a belief, not a backup — record when it was last
actually executed, and by whom.)_

| | |
| --- | --- |
| **Source of truth** | |
| **Retention of the source** | |
| **Rebuild procedure** | |
| **Last executed** | _(date, work item ID)_ |

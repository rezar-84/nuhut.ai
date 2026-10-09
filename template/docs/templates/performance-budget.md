---
status: draft
owner: performance-engineer
last-reviewed: YYYY-MM-DD
---

# Performance budgets — {{PROJECT_NAME}}

The numbers a change is held against, and the method that produces each one. The
charter's **Budgets** table is the summary; this is the working detail behind it.

**A budget is a pair.** A latency figure without the percentile, the environment, the
concurrency, and the dataset size cannot be compared to the next one — and detecting a
regression is the only thing a budget is for.

## Budgets

| # | What | Budget | Percentile | Measured on | Concurrency / load | Dataset size | Baseline | Measured when |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | _(e.g. POST /orders end to end)_ | | _(p95 — a mean hides the tail, and the tail is what people report)_ | _(environment)_ | | | | |
| 2 | _(e.g. cost per 1k requests)_ | | n/a | | | | | |
| 3 | _(e.g. nightly pipeline duration)_ | | | | | | | |
| 4 | _(e.g. data freshness lag)_ | | | | | | | |

Write **none set** rather than leaving this empty. An unstated budget is not "no budget",
it is an unmeasured one — and a reader cannot tell a deliberate absence from an unfilled
form.

## Method

For each budget above, whoever measures it next must be able to reproduce the number.

| # | Command | Warm-up | Runs (N) | How the spread is reported | Who can run it |
| --- | --- | --- | --- | --- | --- |
| 1 | _(the exact command — the charter's `checks.perf` should call it)_ | | | | |

**Environment.** _(Hardware or instance class, dataset shape and size, what is faked and
what is real, and what else is running. A benchmark on an empty database measures the
benchmark.)_

**What makes a run invalid:** _(noisy neighbours, cold caches, a dataset that has drifted,
a different runtime version. Say what disqualifies a number, so a bad one is discarded
rather than recorded.)_

## Capacity and headroom

| | |
| --- | --- |
| **Normal load** | |
| **Peak observed** | _(when, and what caused it)_ |
| **Known limit** | _(where it stops meeting the budget, and how that was established)_ |
| **Headroom** | _(the multiple between peak and limit)_ |
| **Growth rate** | _(what eats the headroom, and roughly when)_ |

**Behaviour at and beyond the limit:** _(shed, queue with a bound, or degrade — never
unbounded queueing, which turns a slowdown into an outage and loses the requests
anyway.)_

## Known hot paths

| Path | Why it is hot | Current cost | Guarded by |
| --- | --- | --- | --- |
| | _(volume, size, fan-out, external call)_ | | _(a test, a budget, or nothing — say which)_ |

## Caches

| Cache | Holds | Invalidated by | Staleness tolerated | Correctness risk if wrong |
| --- | --- | --- | --- | --- |
| | | _(a rule, not a hope — a cache with no invalidation story is a correctness defect in a performance costume)_ | | |

## History

Every entry is a *Measured* result under `../process/06-evidence-and-claims.md`: method,
subject version, N, spread, environment, date.

| Date | Work item | Budget # | Before | After | Traded away |
| --- | --- | --- | --- | --- | --- |
| | | | | | _(memory, cost, complexity, correctness — a latency win bought with a doubled bill is a trade, and the record needs both halves)_ |

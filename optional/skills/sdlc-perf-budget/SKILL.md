---
name: sdlc-perf-budget
description: Check a change against a performance budget — a query, a hot path, a payload shape, a cache, a batch size, a concurrency or pool setting, an added external call — and any claim that something is faster, cheaper, or more scalable. Use before optimising, and before reporting a performance result.
---

# Performance budget — the number, or it did not happen

`{{DOCS_DIR}}/roles/performance-engineer.md` is the review. This skill is the stop before
an optimisation, and before the sentence "this is faster now".

## Do not optimise on suspicion

A change made for performance with no measurement is a change made for taste, carrying
all the risk of a rewrite and none of the evidence. Before touching anything:

1. **Find the budget.** The charter's **Budgets** table, or
   `{{DOCS_DIR}}/project/performance-budget.md`. No budget means there is no completion
   condition and no way to fail — set one first, or say plainly that you are changing
   this for another reason.
2. **Measure the baseline** under the conditions the budget names: percentile,
   environment, concurrency, dataset size, warm or cold.
3. **Confirm the thing you are about to change is the thing that is slow.** Profile or
   count; do not infer from reading.

## Check the change

- [ ] Work per request does not grow with total data size on a path that has a budget.
      Fine at today's row count and linear in it is a scheduled outage.
- [ ] No repeated query inside a loop over results — the most common and most expensive
      defect there is.
- [ ] The query plan was read, on realistic data. Fast on a development dataset proves
      nothing.
- [ ] Anything unbounded a caller can request is paginated or capped.
- [ ] A new cache has a stated invalidation rule. A cache with no invalidation story is a
      correctness defect in a performance costume, and it is rated as one.
- [ ] Timeouts, pool sizes, and concurrency limits remain consistent with each other. A
      pool smaller than the concurrency it serves is a queue nobody named.
- [ ] Behaviour beyond capacity is shed, bounded queue, or degrade — never unbounded
      queueing, which turns a slowdown into an outage and loses the requests anyway.

## Report it as Measured

Method, subject and version, N, spread, environment, date — against the recorded
baseline (`{{DOCS_DIR}}/process/06-evidence-and-claims.md`). Also report:

- **The tail**, not only the median. A mean hides what people actually complain about.
- **What it cost.** Memory, cloud spend, complexity, or cache-staleness risk. A latency
  win bought with a doubled bill is a trade, and a review needs both halves to judge it.
- **What got slower.** Something usually did.

Then update `{{DOCS_DIR}}/project/performance-budget.md` with the new baseline, so the
next change has something to be measured against.

"Feels faster", "should be more efficient", and "reduces overhead" are not results.

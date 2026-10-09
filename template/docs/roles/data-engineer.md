# Role — Data Engineer

**Mission:** ensure the data this project produces is correct, traceable, reproducible,
and safe to build on — and that when a pipeline fails, the damage is bounded and the
recovery is a procedure rather than an improvisation.

**Wrong data is worse than no data.** A pipeline that fails loudly costs a morning.
A pipeline that publishes plausible, wrong numbers costs every decision made on them
until someone notices, and nobody knows which decisions those were.

---

## Engage when

- A dataset, table, stream, or event payload is created, changed, or removed.
- A pipeline, job, schedule, or transformation is added or altered.
- A backfill, replay, or historical correction is planned.
- A new data source is introduced, or an existing one changes shape.
- Data is acquired from a third party — crawled, scraped, purchased, or subscribed.
- Retention, partitioning, or storage layout changes.

## Skip when

- The change reads existing data through an established interface and publishes nothing.
  Reading is not free of risk, but it is `architect`'s and `performance-engineer`'s risk,
  not this role's.

## Reads

`project/charter.md` (Data ownership, Model & data, Budgets),
`project/data-contract.md` for anything the change touches, `project/pipeline-runbook.md`,
`project/architecture.md`, `../process/09-probabilistic-and-data-systems.md`, the schema
or migration itself, and the diff.

---

## Design-review checklist

**Contracts**
- [ ] Every dataset, table, or event the change publishes has a stated owner and a
      declared consumer set. "Whoever queries it" is not a consumer set, and a dataset
      with no owner will be wrong within a quarter with nobody accountable.
- [ ] The change to a consumed shape is additive, or versioned, or has a migration path
      agreed with the consumers *before* it ships. A breaking change discovered by a
      consumer is this role's characteristic failure.
- [ ] Semantics are written down, not only types. What one row means, what the grain is,
      what a null means here, which timezone, which currency, whether it is corrected in
      place or append-only. Two engineers reading the same column name and meaning
      different things is a data incident waiting for a quarter-end.
- [ ] Freshness, volume, and availability expectations are stated as numbers a check can
      test, not as adjectives.

**Correctness**
- [ ] The job is idempotent: the same input processed twice produces the same result, not
      duplicates. Where the sink cannot express that, the job carries its own dedupe key
      and it is tested.
- [ ] Late, duplicate, and out-of-order records have a stated policy. Silence means the
      policy is whatever the code happens to do, which nobody has read.
- [ ] The grain is preserved through every join. A join that can fan out is either proven
      not to, or the row-count assertion is part of the pipeline.
- [ ] Time is handled explicitly: event time versus processing time, the window, what
      happens at a boundary, and what happens across a daylight-saving change.
- [ ] Data-quality gates exist in the order `09-probabilistic-and-data-systems.md` §7
      gives — schema, freshness, volume, nullability, integrity, invariants — and a
      failure **stops the pipeline**. Publishing partial data with a warning in a log is
      not a gate.

**Operability**
- [ ] Any window can be replayed from source without hand-editing state, and the
      procedure is in the runbook rather than in someone's shell history.
- [ ] A run that fails midway leaves a defined state: either nothing published, or a
      recorded checkpoint to resume from. "Some of it went through" is not a state.
- [ ] Backfills are batched, bounded, rate-limited so they do not starve production, and
      stoppable halfway without leaving the dataset half-converted.
- [ ] The job's cost per run is stated — compute, storage, and egress — and a runaway
      input cannot turn it into an unbounded bill.
- [ ] A silent stop is detectable. A scheduled job that simply does not run is the
      failure that most often goes unnoticed for weeks.

**Data that is not ours**
- [ ] Personal data in the pipeline is classified, minimised, and carries its lawful
      basis (`privacy-legal`). Personal data does not become impersonal by being
      aggregated in a way that still identifies someone.
- [ ] Acquired data has permission before collection — terms, robots directives, licence,
      and rate limits checked and recorded *before* the fetcher exists, not after it runs.
- [ ] Acquisition is polite by construction: a documented rate limit, backoff on errors,
      an identifying user agent, and caching so a retry is not a second fetch.
- [ ] Provenance is recorded per record — source, fetch date, and the terms it came
      under. Data whose origin is unknown cannot be published, sold, trained on, or
      defended.
- [ ] Deletion reaches derived copies: downstream tables, caches, exports, search
      indexes, and embeddings. A deletion that stops at the source table has not happened.

## Ship-review checklist

- [ ] The data-quality gates ran, and their results are reported as *Measured* with the
      run and date — not asserted.
- [ ] Row counts, distributions, and null rates before and after are compared against the
      baseline. "The job succeeded" is not evidence that the data is right.
- [ ] A sample of real output was read by a human who knows what the numbers should look
      like. Automated checks find the failures you anticipated; only reading finds the
      others.
- [ ] The reverse path was executed, not merely written, for anything that rewrote
      history.
- [ ] Lineage is updated: what this reads, what it writes, what now depends on it.
- [ ] `project/data-contract.md` and `project/pipeline-runbook.md` reflect what now
      exists, and the charter's Data ownership table names the new dataset.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| Published data that is wrong in a way consumers cannot detect | S0 — it is already being used to decide things |
| An irreversible backfill or historical rewrite with no tested reverse path and no named human accepting it | S1 |
| A pipeline that publishes partial output on failure instead of stopping | S1 |
| A non-idempotent job that can duplicate rows on retry | S1 |
| Personal or acquired data with no lawful basis, licence, or recorded provenance | S1 — hand to `privacy-legal`, which owns the verdict |
| A breaking contract change shipped without agreement from a named consumer | S1 |
| A silent-stop failure mode: a scheduled job that can stop running with no alert | S2 |
| No freshness, volume, or integrity check on a dataset others rely on | S2 |
| A join that can silently change the grain, unasserted | S2 |
| Semantics undocumented — a column whose meaning must be inferred from the code | S3 |
| Cost per run unstated on a job with variable input size | S3 |

An S0 here is rated on *consumer detectability*, not on the size of the error. A
wildly wrong number gets noticed; a plausibly wrong one gets used.

---

## Owns

`project/data-contract.md`, `project/pipeline-runbook.md`, the charter's **Data
ownership** table, the data-quality gate definitions, and lineage.

## Hands off to

Lawful basis, licence, and retention obligations → `privacy-legal`. Scheduling,
alerting, restore, and infrastructure → `devops-sre`. Query and job efficiency, and cost
under growth → `performance-engineer`. Boundaries, ownership, and coupling between
producers and consumers → `architect`. Datasets used for training or evaluation →
`ml-engineer`. Test data and fixtures → `qa`.

---

## Questions this role asks that nobody else will

- If this number is wrong, who finds out, and how long does it take?
- What does this pipeline do the second time it runs on the same input?
- Which decision was already made using yesterday's version of this table?
- What happens to this dataset when the source changes shape without telling us?
- Who do I have to ask before I can change this column, and do they know they own it?

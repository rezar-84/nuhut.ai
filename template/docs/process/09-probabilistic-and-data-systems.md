# 09 — Probabilistic and data systems

For work where the output is a distribution rather than a value: models, prompts,
retrieval, rankers, classifiers, agents — and for the pipelines and datasets that feed
them or stand alone. Stack-agnostic: the charter names the tools, this document names
the obligations.

**Read this when** the charter marks the `ml-engineer` or `data-engineer` role active, or
when a change touches a prompt, a model, an index, a dataset, a pipeline, or an
evaluation. Otherwise skip it — nothing here applies to deterministic code.

The rest of `process/` assumes a check passes or fails. This document is what replaces
that assumption when it does not hold. It does not relax any rule; it closes the gap
where a rule would otherwise be unenforceable.

---

## 1. What counts as a dependency here

A system whose behaviour comes from data has dependencies that are not in the lockfile.
Each of these is a dependency in the full sense of `05-change-control.md` — pinned,
recorded, reviewed, and reversible:

| Dependency | Pinned as | Changing it is |
| --- | --- | --- |
| Model or model version | An exact version identifier, never a floating alias | A change to the product |
| Prompt, system message, or instruction file | Versioned in the repository, never edited live | A change to the product |
| Retrieval configuration | Chunking, embedding model, index parameters, top-k, filters | A change to the product |
| The index or corpus itself | A build identifier and the source snapshot it came from | A change to the product |
| Inference parameters | Temperature, sampling, seed, max tokens, tool set | A change to the product |
| Training or fine-tuning data | A dataset version | A change to the product |
| A schema or dataset a consumer reads | A data contract (`templates/data-contract.md`) | A change to somebody else's product |

A floating alias (`latest`, `stable`, an unversioned endpoint) is a dependency that
changes without a commit, without a review, and without anyone knowing. That is a
finding, not a configuration style. If the platform offers no pinned identifier, record
that in the assumptions register as an accepted, named risk.

**"It is just a string" is not a tier argument.** A prompt is executable: it decides
what the system does, what it discloses, and what it refuses. Tier it by the surface it
governs, exactly as you would code.

---

## 2. Tiering, specifically

Applied on top of the risk table in `AGENTS.md`, not instead of it.

- **Tier 1** — the model, prompt, retrieval, or pipeline sits on an authorisation,
  tenancy, payments, safety, PII, or public-claim path; the system takes actions rather
  than producing text; training or fine-tuning on user data; a change to what may be sent
  to a third-party provider; a schema or contract change others consume; a destructive or
  irreversible backfill.
- **Tier 2** — any other change to a prompt, model version, retrieval configuration,
  eval threshold, feature transformation, or pipeline output; a new data source; a new
  evaluation case that changes the baseline.
- **Tier 3** — a comment, a formatting change, a test-only addition, a documentation
  edit. Almost nothing in this domain is Tier 3, because almost nothing here has an
  output you can predict by reading the diff.

---

## 3. Evaluation before change

The rule is one sentence: **you cannot claim an improvement without a baseline you
established before the change, on a subject you did not also change.**

- **The golden set is an artifact**, versioned, owned, and described in
  `templates/eval-plan.md`: where each case came from, why it is in the set, what the
  expected behaviour is, and who decided that. Cases whose provenance nobody knows are
  cases nobody can defend when they fail.
- **Never change the system and the eval in one work item.** If both must change, that
  is two items with two baselines, and the second one re-baselines first. A comparison
  across a changed golden set is not a comparison; reporting it as one is a fabrication
  under Prime Directive 1.
- **The set covers failure, not only success.** Adversarial inputs, out-of-scope
  requests, prompt injection attempts, ambiguous cases where the correct behaviour is to
  refuse or ask, empty and malformed inputs, and the long tail the happy path hides.
- **Report as *Measured***, with everything `06-evidence-and-claims.md` requires of that
  word. An aggregate score alone is not a result: state what regressed, because a mean
  that improved while a safety category got worse is a worse system.
- **Held-out means held out.** Data used to tune prompts, thresholds, or weights is not
  evidence about the system. Leakage between the set you tuned on and the set you report
  on is the S1 failure of this discipline: every number after it is false, and nothing
  about the system's behaviour is known.
- **Human judgement is a measurement too.** If a person or a model grades the output,
  the rubric is written down, the sample size is stated, and grader agreement is checked
  at least once. A model grading its own output is a *Reported* result, not a *Verified*
  one, and its own biases are part of the finding.

---

## 4. Non-determinism

- State the determinism controls in the plan: seed, temperature, sampling policy, and
  whether retries can change the answer.
- **A single run is a sample.** Anything reported from a non-deterministic system carries
  N and a spread, or it is not reported.
- **Flakiness is characterised, not re-run.** A test that fails one run in twenty has a
  failure rate of 5%, and that is the finding. Re-running until green destroys the only
  evidence you had. `04-quality-gates.md` governs what happens next.
- Where a variable output is unacceptable to a consumer, the fix is a constraint —
  schema-validated output, an allowed value set, a deterministic fallback — not a hope
  expressed in the prompt.

---

## 5. Boundaries: what may leave, what may be kept

Declared in the charter's **Model & data** table and enforced by `privacy-legal`:

- **What may be sent** to a third-party model or service, by data class. Personal data,
  credentials, customer content, and regulated data each need a recorded basis, not an
  assumption that the provider is fine.
- **What is retained** — prompts, completions, traces, embeddings, and evaluation logs
  are records like any other, with a retention period and a deletion path. Embeddings
  derived from personal data are personal data; an index is a datastore, and deletion
  that does not reach it has not happened.
- **What may be trained or tuned on**, with the rights to do so established before the
  work rather than after it. Absence of a prohibition is not permission
  (`06-evidence-and-claims.md`).
- **Secrets never enter a prompt, a trace, or an evaluation fixture.** Traces are logs,
  and everything `roles/security.md` says about logs applies to them unchanged.

---

## 6. Behaviour a probabilistic feature must specify before it ships

Not optional extras — a feature missing these is not finished:

- **What it refuses**, and what the user sees when it does.
- **What happens when the provider is down, slow, rate-limiting, or returns malformed
  output.** There is a fallback, or there is a stated, accepted failure.
- **Grounding**: where an assertion in the output is supposed to come from, and what
  happens when the retrieval returns nothing relevant. A confident answer built on an
  empty retrieval is the characteristic failure of this architecture.
- **Where a human is in the loop**, for which decisions, and what they can see in order
  to judge. A human rubber-stamping output they cannot evaluate is not a control.
- **The cost envelope**: tokens or compute per request, the expected volume, and what
  stops a loop, a retry storm, or a large input from becoming an unbounded bill.
- **Disclosure**: where the user is told they are reading generated output, if the
  charter, the domain, or the law requires it (`roles/privacy-legal.md`).

---

## 7. Data quality gates

Where the project produces or consumes datasets, run these in order — cheapest and most
localising first, exactly like the check sequence in `04-quality-gates.md`. The charter
supplies the command as `checks.data`.

1. **Schema** — the shape is what the contract says: columns, types, nullability.
2. **Freshness** — the data is as recent as the contract promises. A stale pipeline that
   still succeeds is the failure that is hardest to notice and easiest to build on.
3. **Volume** — row counts are within the expected band. A silent drop to a tenth is a
   failure even when every row is valid.
4. **Nullability and range** — required fields present, values in their domain.
5. **Referential integrity** — keys resolve, joins do not silently drop rows.
6. **Business invariants** — the things that must be true of this data and no other:
   balances reconcile, states are reachable, totals agree with their parts.

A gate that fails **stops the pipeline and alerts**; it does not publish partial data and
log a warning. Publishing wrong data is worse than publishing none, because everything
downstream will treat it as true.

---

## 8. Pipelines

- **Idempotent.** Running the same job twice on the same input produces the same result,
  not duplicates. Where the sink cannot express that, the job carries its own dedupe key.
- **Replayable.** Any window can be re-run from source without hand-editing state, and
  the procedure is written in `templates/pipeline-runbook.md`.
- **Backfills are a Tier 1 shape**: bounded batches, a stated blast radius, a rate that
  does not starve production, a checkpoint to resume from, and a way to stop halfway
  without leaving the dataset half-converted.
- **Partial failure is defined.** State what a run that fails at step 4 of 7 leaves
  behind, and whether the result is recoverable or must be discarded.
- **Late, duplicate, and out-of-order data** have a stated policy. Silence here means the
  policy is whatever the code happened to do.
- **Lineage is recorded**: for every published dataset, what it came from, what
  transformed it, when, and who owns it. A number in a report nobody can trace to a
  source is not evidence (`06-evidence-and-claims.md`).

---

## 9. Acquired data

Where the project fetches data it did not create — crawling, scraping, third-party
feeds, purchased datasets:

- **Capability and permission are separate.** The charter's `Standard` acquisition
  profile prefers feeds/APIs and bounded requests; `Advanced` may add browser automation,
  OCR, resilient extractors, and authorised session flows. Neither profile authorises a
  target. Login, paywall, CAPTCHA, explicit denial, or another access control stops
  third-party acquisition without explicit owner authorisation or an approved route.

- **Permission before collection.** Terms of service, robots directives, licence, and
  any rate or volume limits are checked and recorded *before* the fetcher is written, not
  after it is running. `roles/privacy-legal.md` owns the verdict.
- **Politeness is a correctness property**: a documented rate limit, backoff on errors,
  a real identifying user agent, and caching so a retry does not become a second fetch.
  A crawler with no ceiling is an outage you are causing on someone else's system.
- **Provenance per record** — source, URL or feed, fetch date, and the terms it was
  obtained under. Data whose origin is unknown cannot be published, sold, trained on, or
  defended.
- **Personal data does not become impersonal by being public.** Scraped personal data
  is personal data, with every obligation intact.
- **Structure changes without warning.** A parser that silently produces empty fields
  when the source changes is a data-quality failure (§7), not a parsing detail.

---

## 10. Rollback

Everything in §1 must be reversible on the same timescale as a code deploy:

- The previous model version, prompt, and retrieval configuration are recoverable from
  the repository, and the runbook says how to put them back.
- An index or corpus rebuild keeps the previous build until the new one is verified.
- A migration or backfill has a reverse path, or its irreversibility is accepted in
  writing by a named human before it runs (`roles/devops-sre.md`).
- Rolling back the code without rolling back the prompt, index, or schema it depends on
  is not a rollback. State the ordering.

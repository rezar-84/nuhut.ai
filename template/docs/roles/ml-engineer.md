# Role — ML / AI Engineer

**Mission:** ensure a system whose output is a distribution rather than a value is
evaluated before it is believed, bounded in what it can do and disclose, reversible when
it is wrong, and honest about what it does not know.

**This role covers both halves of the field** — a trained model and a prompted one. The
mechanics differ; the obligations do not. Something produces an output that cannot be
predicted by reading the diff, so the only evidence about its behaviour is measurement.

---

## Engage when

- A model, model version, prompt, system message, or instruction file changes.
- Retrieval changes: chunking, embedding model, index parameters, filters, top-k, or the
  corpus itself.
- Inference parameters change: temperature, sampling, seed, tool set, token limits.
- An evaluation set, metric, threshold, or grading rubric changes.
- A feature transformation, training set, split, or fine-tune is added or altered.
- The system is given a tool, a permission, or the ability to take an action.
- Any Tier 1 change in a project where the charter marks this role active.

## Skip when

- The change is around the model rather than through it — a UI, a log format, an
  unrelated endpoint — and cannot alter what the model sees, what it can do, or what is
  done with its output. If it changes the input, it is not a skip.

## Reads

`project/charter.md` (Model & data, Budgets), `project/eval-plan.md`,
`project/model-and-dataset-card.md`, `../process/09-probabilistic-and-data-systems.md`,
the prompt or model configuration itself, the eval results, and the diff.

---

## Design-review checklist

**Evaluation before the change**
- [ ] A baseline exists, measured before this change, on a golden set that is **not** also
      changing in this work item. Without one there is no claim to make, and that is the
      finding — not a reason to proceed and see.
- [ ] The golden set is versioned and its cases have provenance: where each came from,
      what the expected behaviour is, and who decided that. Cases nobody can defend are
      cases nobody can act on when they fail.
- [ ] The set covers failure, not only success: adversarial inputs, out-of-scope requests,
      injection attempts, ambiguous cases where the right behaviour is to refuse or ask,
      empty and malformed input, and the categories the aggregate score hides.
- [ ] Metrics are per category as well as in aggregate. A mean that improved while a
      safety or refusal category regressed is a worse system reported as a better one.
- [ ] Nothing tuned on is reported on. Leakage between the tuning set and the reported
      set makes every number after it false — and unlike most defects, it leaves the
      dashboard looking excellent.
- [ ] Where a human or a model grades, the rubric is written, the sample size is stated,
      and agreement has been checked at least once. A model grading its own output is
      *Reported*, not *Verified*.

**Behaviour**
- [ ] What the system refuses is specified, and what the user sees when it does.
- [ ] Grounding is specified: where an assertion in the output is supposed to come from,
      and what happens when retrieval returns nothing relevant. A confident answer over an
      empty retrieval is the characteristic failure of this architecture, and it is
      invisible to any check that only looks at whether a response was produced.
- [ ] Output that a consumer parses is constrained — schema-validated, an allowed value
      set, a deterministic fallback — rather than requested politely in the prompt.
- [ ] The failure path is real: provider down, slow, rate-limiting, truncating, or
      returning malformed output. There is a fallback, or a stated and accepted failure.
- [ ] Where the system takes actions rather than producing text, the permission scope is
      the minimum, is enforced outside the model, and destructive or outward-facing
      actions require a human. A model deciding its own authorisation is not a control.
- [ ] Human review is placed where a person can actually judge — with the evidence in
      front of them. A reviewer approving output they cannot evaluate is a rubber stamp
      that transfers blame rather than reducing risk.

**Dependencies and reproducibility**
- [ ] Model, prompt, retrieval configuration, index build, and inference parameters are
      pinned to exact identifiers and versioned in the repository. A floating alias is a
      dependency that changes without a commit, a review, or anyone knowing.
- [ ] Determinism controls are stated: seed, temperature, sampling, and whether a retry
      can change the answer.
- [ ] The index or corpus records what snapshot it was built from, so a result can be
      reproduced.

**Boundaries and cost**
- [ ] What may be sent to a third-party provider matches the charter's Model & data
      table, by data class, with a recorded basis. Absence of a prohibition is not
      permission.
- [ ] Prompts, completions, traces, and embeddings are treated as records: retention,
      deletion path, and no secrets. Embeddings derived from personal data are personal
      data, and an index is a datastore that deletion must reach.
- [ ] Tokens or compute per request, expected volume, and the resulting cost are stated,
      and something bounds a retry loop, an agent loop, or an oversized input.
- [ ] Rollback is real: the previous model, prompt, and index are recoverable, and the
      ordering between rolling back code and rolling back what it depends on is stated.

## Ship-review checklist

- [ ] The evaluation ran against the versioned set and is reported as *Measured*, with
      method, subject version, N, spread, and date — and against the recorded baseline.
- [ ] Regressions are listed by category, including ones the aggregate absorbed.
- [ ] The refusal, empty-retrieval, and provider-failure paths were exercised, not
      reasoned about.
- [ ] Injection attempts from retrieved and user-supplied content were run against the
      shipped configuration (`security` owns the verdict).
- [ ] Cost and latency per request were measured under a realistic input, not the
      smallest one.
- [ ] `project/eval-plan.md` and `project/model-and-dataset-card.md` reflect what now
      exists, and the charter's Model & data table names the pinned versions in use.
- [ ] A worklog entry records what changed, the before and after numbers, and what got
      worse — because something usually does.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| The system can take a destructive, financial, or outward-facing action without a human, on a path a crafted input can reach | S0 |
| Personal, regulated, or secret data sent to a provider with no recorded basis | S0 — hand to `privacy-legal` and `security` |
| A quality claim with no baseline, or a comparison across a changed golden set | S1 — the claim is fabricated even where the number is real |
| Leakage between the set tuned on and the set reported on | S1 — every subsequent number about the system is false |
| A floating model or prompt version in production | S1 — the product changes with no commit and no rollback point |
| No refusal or empty-retrieval behaviour: the system asserts when it has nothing to assert from | S1 |
| Unbounded token, retry, or agent-loop cost | S2 |
| Output consumed by code but unconstrained in shape | S2 |
| No spread reported for a non-deterministic result | S2 — one draw presented as a property |
| Human review placed where the reviewer cannot see enough to judge | S2 |
| Golden-set cases with no provenance | S3 |

---

## Owns

`project/eval-plan.md`, `project/model-and-dataset-card.md`, the golden set and its
versioning, the charter's **Model & data** table, and the prompt and retrieval
configuration as versioned artifacts.

## Hands off to

Prompt injection, tool-permission trust boundaries, and exfiltration through output →
`security`. Lawful basis, licence to train, retention, and disclosure → `privacy-legal`.
Corpus construction, dataset lineage, and the pipelines that build the index →
`data-engineer`. Inference latency, throughput, and cost under load →
`performance-engineer`. Serving, rollout, and rollback mechanics → `devops-sre`. Whether
the capability is worth its failure rate → `product-manager`. How a wrong or refused
answer is presented → `ux-designer`.

---

## Questions this role asks that nobody else will

- What did this change make worse? Something did — which category absorbed it?
- What does it say when it has nothing to say?
- If this answer is wrong, what does the user do next, and how bad is that?
- Which number here would still look good if the system were broken?
- Can I get yesterday's behaviour back, and how long does that take?

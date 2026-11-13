---
status: draft
owner: ml-engineer
last-reviewed: YYYY-MM-DD
---

# Model and dataset card — _(model or dataset name)_

One card per model the project trains, tunes, or deliberately selects, and per dataset it
curates. It exists so that a year from now somebody can tell what this was built from,
what it is fit for, and what it must not be used for.

A model consumed as a pinned third-party API needs the charter's **Model & data** table,
not a card — unless the project fine-tunes it, in which case the tuning is the model this
card describes.

## Identity

| | |
| --- | --- |
| **Name and version** | |
| **Kind** | _(trained / fine-tuned / prompted configuration / curated dataset)_ |
| **Owner** | |
| **Built on** | _(base model and its exact version, or "from scratch")_ |
| **Artifact location** | _(registry, path, or build identifier)_ |
| **Reproducible from** | _(code commit, config, data version, seed)_ |

## Intended use

**It is for:** _(the task, the population, the input distribution, the operating
conditions)_

**It is not for:** _(the uses that would be plausible and wrong. This section is the one
people skip and later need.)_

- _(e.g. inputs in languages absent from the training data)_
- _(e.g. decisions about a person with legal or material effect)_
- _(e.g. any use where a confident wrong answer is worse than no answer)_

**Out-of-distribution behaviour:** _(what it does with input it was not built for —
degrades, refuses, or produces confident nonsense. The third is the common one, and it
must be stated rather than discovered.)_

## Data

| | |
| --- | --- |
| **Sources** | _(each one, with the terms it was obtained under)_ |
| **Version / snapshot** | |
| **Size** | _(records, and the shape of the distribution)_ |
| **Collection period** | _(and how stale that makes it now)_ |
| **Rights to use this way** | _(established before the work, per `../roles/privacy-legal.md`. Absence of a prohibition is not permission)_ |
| **Personal data** | _(classes, lawful basis, and the deletion path — including out of the trained artifact if that is even possible; if it is not, say so)_ |

**Splits:** _(train / validation / test, how they were separated, and what guarantees they
do not overlap. Leakage here makes every number below false while leaving the dashboard
looking excellent.)_

**Known gaps and skews:** _(who and what is under-represented, and what that predicts
about where it fails. "Unknown" is an acceptable answer; blank is not.)_

**Labels:** _(who labelled, against what rubric, at what agreement rate, and how disputes
were resolved)_

## Evaluation

Full detail in `eval-plan.md`; this is the summary a reader needs without opening it.

| Metric | Category | Result | N | Spread | Dataset version | Measured when |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

**Compared against:** _(the baseline, and the conditions both were measured under)_

**Where it is weakest:** _(the categories with the worst results — stated here rather
than left to be inferred from a table)_

## Operating envelope

| | |
| --- | --- |
| **Inference parameters** | _(temperature, sampling, seed, token limits)_ |
| **Latency and cost** | _(per request, at a realistic input size — see `performance-budget.md`)_ |
| **Monitoring** | _(what is watched in production, and what would indicate drift)_ |
| **Retraining or refresh** | _(trigger and cadence, or "none planned" — which is itself a decision)_ |
| **Rollback** | _(the previous version, where it lives, and how long a rollback takes)_ |

## Risks and mitigations

| Risk | Who it affects | Mitigation | Residual |
| --- | --- | --- | --- |
| | | | _(what remains after the mitigation, and who accepted it)_ |

---
status: draft
owner: ml-engineer
last-reviewed: YYYY-MM-DD
---

# Evaluation plan — {{PROJECT_NAME}}

How the probabilistic parts of this system are measured, so a change can be shown to be
an improvement rather than asserted to be one. Governed by
`../process/09-probabilistic-and-data-systems.md`; the numbers it produces are reported
as *Measured* under `../process/06-evidence-and-claims.md`.

## What is being evaluated

| Surface | What it does | What "good" means here |
| --- | --- | --- |
| _(the retrieval step, the classifier, the agent's tool selection, the summariser)_ | | _(in one sentence a non-specialist would accept)_ |

**Pinned configuration under test** — the exact identifiers, so a result is reproducible.
The charter's **Model & data** table is authoritative; repeat only what this plan needs.

| | |
| --- | --- |
| **Model / version** | |
| **Prompt version** | _(commit or file version — never "the current prompt")_ |
| **Retrieval config** | _(embedding model, chunking, top-k, filters, index build id)_ |
| **Inference parameters** | _(temperature, sampling, seed, max tokens, tool set)_ |

## The golden set

| | |
| --- | --- |
| **Location** | |
| **Current version** | |
| **Owner** | |
| **Size** | _(N, and N per category)_ |
| **Last reviewed by a human** | |

**Provenance.** Where the cases came from and why each is in the set. Cases nobody can
defend are cases nobody can act on when they fail.

| Category | N | Source | Expected behaviour | Who decided that |
| --- | --- | --- | --- | --- |
| _(happy path)_ | | | | |
| _(ambiguous — correct behaviour is to ask or refuse)_ | | | | |
| _(out of scope — correct behaviour is to decline)_ | | | | |
| _(adversarial / injection attempts)_ | | | | |
| _(malformed, empty, oversized input)_ | | | | |
| _(known past failures — regression cases)_ | | | | |

**Held out from tuning:** _(which cases are never used to tune prompts, thresholds, or
weights. Leakage between the tuning set and this one makes every later number false, and
it leaves the dashboard looking excellent.)_

## Metrics and thresholds

Per category, not only in aggregate — a mean that improves while a safety category
regresses is a worse system reported as a better one.

| Metric | Category | How it is computed | Threshold | Current baseline | Measured when |
| --- | --- | --- | --- | --- | --- |
| | | | _(ship / do not ship)_ | | |

**Grading.** _(Automatic, human, or model-graded. If human or model: the rubric, the
sample size, and when grader agreement was last checked. A model grading its own output
is a Reported result, not a Verified one.)_

**Run conditions.** _(N runs, seed and temperature policy, environment, and how the
spread is reported. A single run is a sample, not a result.)_

## How a change is evaluated

1. Baseline measured **before** the change, on golden set version _(…)_ — the version is
   not changing in the same work item.
2. Change made.
3. Re-measured under identical conditions; both numbers reported with method, subject
   version, N, spread, and date.
4. Regressions listed **by category**, including any the aggregate absorbed.
5. `checks.eval` in the charter's Commands table runs this.

Changing the system and the golden set in one work item is a violation, not a shortcut:
a comparison across a changed set is not a comparison.

## What this does not measure

_(State it plainly. Never imply coverage you do not have — the things the set contains no
cases for are where the system will surprise someone.)_

- _(e.g. behaviour in languages other than the source language)_
- _(e.g. real user inputs, as opposed to inputs we imagined)_
- _(e.g. long-conversation or multi-turn drift)_
- _(e.g. cost and latency — see `performance-budget.md`)_

## Failure taxonomy

The named ways this system goes wrong, so a new failure can be filed rather than
re-discovered each time.

| Failure | Looks like | Detected by | Current rate |
| --- | --- | --- | --- |
| _(ungrounded assertion — confident answer over an empty retrieval)_ | | | |
| _(wrong refusal — declines something it should do)_ | | | |
| _(missed refusal — does something it should decline)_ | | | |
| _(format violation — output the consumer cannot parse)_ | | | |

## History

| Date | Work item | Golden set version | Result | What got worse |
| --- | --- | --- | --- | --- |
| | | | | _(something usually does — say what)_ |

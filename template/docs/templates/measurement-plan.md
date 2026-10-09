---
status: draft
owner: cro-analyst
last-reviewed: YYYY-MM-DD
---

# Measurement plan — {{PROJECT_NAME}}

> Written **before** the feature ships. Instrumentation added afterwards cannot answer
> questions about the launch, and "we'll add analytics later" reliably means never.

## What success means

| Outcome | Metric | Baseline | Target | Counter-metric | Source |
| --- | --- | --- | --- | --- | --- |
| | | _(today's real value, or "unknown — {{PREFIX}}-### establishes it")_ | | _(what must not get worse)_ | |

Every metric needs a counter-metric. "More sign-ups" without watching qualification or
retention optimises for the wrong thing and will succeed at it.

## Funnel

The journey from arrival to outcome, with the observable event at each step.

| # | Step | Event name | Fires when | Key properties |
| --- | --- | --- | --- | --- |
| 1 | | | | |

Where drop-off is currently known, record it — that is where changes should be aimed.

## Event conventions

- **Naming:** _(one convention, project-wide — e.g. `object_action` in past tense)_
- **Required properties on every event:** _(session, surface, locale, version…)_
- **Never in a payload:** personal data, credentials, free-text a user typed, anything
  identifying beyond what the privacy notice permits (`../roles/privacy-legal.md`).
- **Where events go:** _(destination, and who can query them)_

## Consent

- What requires consent: _(per jurisdiction)_
- What fires before consent: _(should be nothing that requires it)_
- What the product does when consent is refused: _(it must still work)_

## Instrumentation checklist

Part of the Definition of Done for anything on a measured surface:

- [ ] Every funnel step emits its event, exactly once, with the documented payload.
- [ ] Verified firing in the real environment, not a mock.
- [ ] The funnel is queryable end to end.
- [ ] Baseline captured before the change.
- [ ] Someone is named to look at it after launch, on a stated date.

## Experiments *(if run)*

| ID | Hypothesis | Metric | Guardrails | Sample / duration | Result |
| --- | --- | --- | --- | --- | --- |

**Hypothesis format:** because _(observation)_, we believe _(change)_ will cause
_(effect)_, measured by _(metric)_.

Rules: decide sample size and duration before launching; honour full business cycles;
define guardrail metrics that must not degrade; agree the stopping rule in advance.
Stopping when it first looks significant is not a result.

## Review cadence

| What | When | Who | Where recorded |
| --- | --- | --- | --- |
| Post-launch check | _(e.g. 7 and 30 days after release)_ | | worklog / this file |

The G6 gate exists because shipping without checking the outcome means the next decision
is made on the same guesswork as the last one.

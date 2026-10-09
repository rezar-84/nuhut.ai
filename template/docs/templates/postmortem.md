---
status: draft
owner: _(incident owner)_
last-reviewed: YYYY-MM-DD
---

# Postmortem — <short description>

**Date:** YYYY-MM-DD **Severity:** S0 | S1
**Duration:** <detection → resolution> **Author:** _(who)_

> This document is **blameless**. It examines the system that allowed the failure — the
> checks that did not exist, the signal nobody saw, the step that was easy to get wrong.
> It does not examine who typed the command. A postmortem that concludes "someone should
> be more careful" has found nothing, because the next person will be equally careful and
> equally human.

## Impact

_(Who was affected, how many, for how long, and what they could not do. Data affected,
if any. Be specific and honest — understating impact makes the analysis worthless.)_

## Timeline

| Time | Event |
| --- | --- |
| | _(the change or condition that introduced the fault)_ |
| | _(first user impact — often earlier than detection)_ |
| | _(detection: how, and by whom — a user reporting it is itself a finding)_ |
| | _(mitigation)_ |
| | _(resolution)_ |

## What happened

_(The mechanism. Enough technical detail that a reader can follow the causal chain from
trigger to impact.)_

## Why it was possible

_(Not "a bug was introduced" — every incident involves a mistake. What allowed the
mistake to reach users? Ask "why" until you reach something in the system rather than a
person: a missing test, an unreviewed path, an alert that did not exist, a deploy step
that could half-apply, a config with an unsafe default.)_

## Detection

- How was it detected? _(Monitoring, or a user telling us?)_
- How long between impact and detection?
- What would have detected it sooner, and does that exist now?

## Response

- What went well?
- What slowed us down? _(Missing runbook, unclear ownership, no rollback, no access.)_

## What we are changing

Each item is a real backlog entry with an owner — not an intention.

| # | Action | Prevents | Owner | ID |
| --- | --- | --- | --- | --- |
| 1 | | | | {{PREFIX}}-### |

Prefer changes in this order:
1. **Make it impossible** — a constraint, a type, a guard the code cannot bypass.
2. **Make it caught** — a test, a check, a gate.
3. **Make it visible** — an alert, a metric.
4. **Make it recoverable** — a faster rollback, a backup.
5. **Make it documented** — a runbook. *(Weakest. Documentation is not a control.)*

## What we are not changing

_(Risks consciously accepted, and why. Recording an accepted risk is a legitimate outcome
— pretending it was fixed is not.)_

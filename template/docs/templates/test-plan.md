---
status: draft
owner: qa
last-reviewed: YYYY-MM-DD
---

# Test plan — {{PROJECT_NAME}}

> Records what is actually covered, **including the gaps**. A test plan that lists only
> strengths is a marketing document.

## Commands

The commands live in `charter.md` → Commands, which is the one place an agent reads them
from. Record here only what the charter has no column for:

| Stage | Runs in CI | When it runs, if not every change | Notes |
| --- | --- | --- | --- |
| Format | | | |
| Lint | | | |
| Typecheck | | | |
| Unit | | | |
| Integration | | | |
| Contract _(if anything consumes your interface)_ | | | |
| Build | | | |
| Dependency/secret scan | | | |
| Accessibility | | | |
| End-to-end | | | |

A stage the charter marks **absent** is a QA finding to be justified here, not a neutral
fact.

## Test data

Environments themselves are declared in `charter.md` → Environments. What matters for
testing is the data in them:

| Environment | Data | Why that is permitted |
| --- | --- | --- |
| | _(synthetic / anonymised / production copy)_ | _(required if production data)_ |

## Ephemeral test environments & teardown

When tests require external dependencies (Docker containers, compose services, mock daemons, local test servers):

| Service / Container | Startup command | Readiness / Health check | Teardown command | Memory / CPU limit |
| --- | --- | --- | --- | --- |
| | _(e.g. `docker compose up -d db`)_ | _(e.g. `pg_isready` / HTTP 200)_ | _(e.g. `docker compose down -v`)_ | _(e.g. 512MB / 1 CPU)_ |

**Cleanup guarantee:** _(how teardown is guaranteed on failure/abort — e.g. test runner `afterAll` hook, pytest fixture `yield` teardown, shell `trap ... EXIT`, or Testcontainers auto-reap)_.

## What is covered

### Acceptance criteria scenarios
_(Mapping of Given/When/Then criteria from user stories or upstream specifications into
executable checks, including explicit "must not" negative cases.)_

### Unit
_(Which logic. Which edge cases matter and are covered.)_

### Integration
_(Which seams against which real boundaries. What is substituted, and what that
substitution hides.)_

### Contract
_(Which interfaces are locked, and against whose expectations.)_

### End-to-end
_(The two to five journeys that mean the product is down if broken.)_

### Manual / human
_(What automation cannot judge: language quality by a qualified speaker, screen-reader
experience, visual judgement, acceptance by the requester. Who does it and when.)_

## High-risk matrices

Required where the project has these surfaces (`../process/04-quality-gates.md`):

**Authorisation** — for every protected resource:

| Case | Expected |
| --- | --- |
| Permitted actor, permitted action | Allowed |
| Permitted actor, unpermitted action | Denied |
| Another owner's valid identifier | Denied, **no existence or metadata leak** |
| Revoked or expired access | Denied |
| Tampered identifier | Denied |
| Stale session | Re-authentication |

**Input** — oversized · malformed · wrong type · injection-shaped · unicode & RTL ·
empty · boundary values.

**Data** — migration forward and backward · concurrent writes · idempotency of
retryables · deletion actually deletes.

## Budgets

| Metric | Budget | Current | Measured by |
| --- | --- | --- | --- |
| | | | |

Regression against a budget is S2 by default. An unset budget is unmeasured, not absent.

## Known gaps

_(The honest list. Each with a backlog ID or an explicit acceptance. This section is why
the document is worth reading.)_

| Gap | Risk | Accepted by / tracked as |
| --- | --- | --- |
| | | |

## Flaky tests

| Test | Since | Symptom | Tracked as | Deadline |
| --- | --- | --- | --- | --- |

A flaky test is a defect with a deadline, not a fact of life.

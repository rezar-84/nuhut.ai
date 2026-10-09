---
status: draft
owner: architect
last-reviewed: YYYY-MM-DD
---

# Service catalogue — {{PROJECT_NAME}}

For a system deployed as more than one independently released unit. It answers the two
questions that get asked during an incident and cannot be answered by reading code:
**who owns this**, and **what breaks if it stops**.

If everything ships as one unit, delete this file and keep `architecture.md`.

## Services

| Service | Purpose | Owner | Repository / path | Deployed how | On-call |
| --- | --- | --- | --- | --- | --- |
| | _(one sentence)_ | _(a named person or team)_ | | | _(who is woken, or "nobody — say so out loud")_ |

## Dependencies

One row per edge. A dependency nobody wrote down is one nobody tested the failure of.

| From | To | Kind | Sync? | Timeout | On failure | Critical? |
| --- | --- | --- | --- | --- | --- | --- |
| | | _(HTTP, gRPC, queue, shared datastore)_ | _(sync / async)_ | | _(degrade, fail, retry with backoff, queue)_ | _(does the caller stop working?)_ |

**Cycles:** _(list any, or state there are none. A cycle between services is a deploy
ordering problem and an outage amplifier.)_

**Shared datastores:** _(any store more than one service writes, and which service owns
it. A second service reaching into another's datastore is a boundary violation regardless
of how convenient the credentials are.)_

## Contracts

| Contract | Producer | Consumers | Kind | Version | Contract test run by |
| --- | --- | --- | --- | --- | --- |
| | | _(named — "internal" is not a consumer)_ | _(API / event / dataset)_ | | _(both sides, or it proves only that the producer agrees with itself)_ |

**Breaking-change procedure:** _(the overlap window during which old and new consumers
both run, who must agree, and how deprecation is announced. During a deploy, both
versions are live — the schema must survive that regardless of the plan.)_

## Events and topics

| Topic / stream | Produced by | Consumed by | Delivery | Ordering | Dead letters go | Schema |
| --- | --- | --- | --- | --- | --- | --- |
| | | | _(at-least-once by default — consumers are idempotent unless proven otherwise)_ | _(per-key / none)_ | _(where, and **who looks at them** — an unmonitored dead-letter queue is a data-loss mechanism with a reassuring name)_ | _(link to a `data-contract.md`)_ |

## Service level objectives

| Service | SLI (what is measured) | Objective | Window | Error budget policy |
| --- | --- | --- | --- | --- |
| | _(availability, latency at a percentile, freshness — something a user feels)_ | | _(e.g. 30 days)_ | _(what changes when the budget is spent: freeze, prioritise reliability work, or an explicit "nothing" — say which)_ |

An SLO nobody acts on when it is missed is a number, not an objective.

## Blast radius

| If this stops | Users see | Other services | Data at risk | Degraded mode |
| --- | --- | --- | --- | --- |
| | | | _(loss, staleness, or none)_ | _(what still works, or "nothing")_ |

## Environments and identity

| | |
| --- | --- |
| **Service-to-service auth** | _(how one service proves who it is — not a shared secret in an environment variable unless that is a deliberate, recorded decision)_ |
| **Correlation** | _(the identifier that crosses every hop; without one, nothing can be traced when it fails)_ |
| **Configuration** | _(where per-service configuration lives, and how a change to it is reviewed and rolled back)_ |

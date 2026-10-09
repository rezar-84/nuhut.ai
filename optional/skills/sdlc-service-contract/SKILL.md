---
name: sdlc-service-contract
description: Check a change that crosses a service boundary — an API request or response shape, an event or message payload, a queue topic, an RPC signature, or a shared datastore access. Use when editing an interface another deployable unit calls or consumes, or when adding a new call between services.
---

# Service contract — the deploy you will break is not yours

`{{DOCS_DIR}}/roles/architect.md` ("Across a service or process boundary") is the review.
This skill fires at the boundary, where the cost of being wrong lands on somebody else's
on-call.

## Two versions are always live

During any rolling deploy, old and new run at once. So:

- **Additive only, or versioned.** A removed field, a narrowed type, a renamed key, or a
  newly required parameter breaks the consumer that has not deployed yet — which, during
  the deploy, is all of them.
- **Consumers ignore unknown fields**, or you cannot add one. Confirm that rather than
  assuming it.
- **Deprecate with a date**, keep both alive through an overlap window, and remove only
  once every named consumer has confirmed. `{{DOCS_DIR}}/templates/service-catalog.md`
  holds the consumer list; if it does not exist, the consumer set is unknown and finding
  it out is the first task.

## For an asynchronous boundary

- [ ] **At-least-once is the assumption.** The consumer is idempotent — natural key,
      dedupe store, or conditional write — and that is tested, not asserted. Delivering
      twice is not an edge case; it is Tuesday.
- [ ] **Ordering** is stated: guaranteed, per-key, or none. Say "none" out loud, because
      the next reader will assume otherwise.
- [ ] **A message that cannot be processed** goes somewhere, and *someone looks at it*.
      An unmonitored dead-letter queue is a data-loss mechanism with a reassuring name.
- [ ] **A poison message** cannot block the partition or the queue behind it forever.
- [ ] **Retries** are bounded and backed off. Retries without a budget amplify an
      incident instead of surviving it.
- [ ] **Backpressure** exists: a producer faster than its consumer blocks, sheds, or
      fills something unbounded — and nobody ever chose the third deliberately.

## For a multi-step operation across services

State what happens when step 3 of 5 fails: compensation, a saga, or an accepted
inconsistency with a named reconciliation process. Distributed transactions that assume
a rollback do not exist. "It should not fail there" is not one of the three options.

## Check before shipping

- [ ] Contract tests run on **both** sides. A provider test the consumer never runs
      proves only that the provider agrees with itself.
- [ ] A correlation identifier crosses the new hop, or nothing can be traced when it
      fails.
- [ ] Every new call has a timeout and a defined behaviour on failure — degrade, fail
      fast, or queue — and the caller's own budget accounts for it.
- [ ] No service reads or writes another's datastore, however convenient the credentials.
- [ ] `{{DOCS_DIR}}/project/service-catalog.md` records the new edge, its criticality, and
      the blast radius if it stops.

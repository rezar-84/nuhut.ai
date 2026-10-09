# Role — Architect

**Mission:** ensure the structure of the system supports what it must do today and can
be changed for what it must do next, without hidden coupling, unowned complexity, or
unstated failure behaviour.

**This role does not prescribe a stack or a style.** It reviews whatever the project
chose against the project's own stated constraints, and challenges the choice only when
the constraints are not met.

---

## Engage when

- Module boundaries, dependencies, data flow, or runtime shape change.
- A new dependency, service, datastore, or integration is introduced.
- Any Tier 1 change (standing board member).

## Skip when

- A change entirely inside an existing boundary that adds no dependency and changes no
  contract.

## Reads

`project/charter.md` (stack and constraints), `project/architecture.md`,
`project/data-model-api.md`, existing ADRs, and the actual code around the change.

---

## Design-review checklist

**Fit**
- [ ] The approach satisfies the constraints the charter names — team size, operational
      capacity, budget, latency, existing platform commitments. An elegant design the
      team cannot operate is a bad design.
- [ ] It uses what is already here. A new dependency, pattern, or service must be
      justified against the boring option that already exists in the repository.
- [ ] Consistent with existing ADRs, or explicitly superseding one.

**Structure**
- [ ] Boundaries are clear: what owns this data, what may call what, what is public.
- [ ] Dependencies point in one direction. Cycles between modules are a defect.
- [ ] Business logic is not embedded in the delivery mechanism (transport, UI, CLI,
      job runner) in a way that prevents testing it directly.
- [ ] Shared state has one owner. Two components writing the same data without a
      defined owner will diverge.
- [ ] The change does not require touching many unrelated places — if it does, that is
      the finding, not the change.

**Behaviour under stress**
- [ ] Failure modes are stated: what happens when the dependency is down, slow,
      returning garbage, or rate-limiting.
- [ ] Timeouts, retries, and backoff are specified — and retries are safe (idempotent)
      or explicitly guarded.
- [ ] Partial failure is handled. Multi-step operations state what happens when step 3
      of 5 fails, and whether the result is recoverable or corrupt.
- [ ] Concurrency is considered where two actors can touch the same thing.
- [ ] Growth is considered: what breaks at 10× the data, users, or request rate — and
      is that far enough away to be someone else's problem, deliberately?

**Across a service or process boundary** — apply this block when the change crosses one:
work handed to a queue, a broker, a scheduler, another service, or a workflow engine.
- [ ] The delivery guarantee is named and designed for. At-least-once is the default
      assumption unless something proves otherwise, which means every consumer is
      idempotent — by natural key, by dedupe store, or by a conditional write. "Exactly
      once" as an end-to-end property is a marketing phrase, not an architecture.
- [ ] Ordering requirements are stated. If order matters, what enforces it, and what
      happens to throughput because of it. If it does not matter, say so, because the
      next reader will assume it does.
- [ ] A message that cannot be processed has somewhere to go and someone to look at it.
      A dead-letter queue nobody monitors is a data-loss mechanism with a reassuring name.
- [ ] Retry and redelivery are bounded, and a poison message cannot block the partition
      or the queue behind it forever.
- [ ] The event or message schema evolves additively, is versioned, and old and new
      consumers can run at the same time — because during a deploy they will.
- [ ] A multi-step operation across services states what happens when step 3 of 5 fails:
      compensation, a saga, or an accepted inconsistency with a stated reconciliation.
      Distributed transactions that assume rollback do not exist.
- [ ] Backpressure exists. A producer faster than its consumer either blocks, sheds, or
      fills something unbounded — and the third is the one nobody chose deliberately.
- [ ] Each service owns its data. A second service reaching into another's datastore is
      a boundary violation regardless of how convenient the credentials are.
- [ ] A correlation identifier crosses every hop, or nothing can be traced when it fails
      (`devops-sre`).
- [ ] The failure of any one participant is survivable: state what degrades, what stops,
      and whether the system is still correct in that state.

**Change cost**
- [ ] The decision is reversible, or its irreversibility is acknowledged in an ADR.
- [ ] Contracts that others depend on are versioned or additive.
- [ ] The design does not require a rewrite to accommodate the next known requirement on
      the roadmap.

## Ship-review checklist

- [ ] The implementation matches the design, or the divergence is documented and
      justified — not discovered by a reader later.
- [ ] No layering violation snuck in (data access from a view, transport types leaking
      into domain logic, a UI component reaching into a datastore).
- [ ] Errors are handled at the level that can do something about them, not swallowed or
      blindly re-thrown to a caller with no context.
- [ ] No new global mutable state, hidden singleton, or implicit initialisation order.
- [ ] Configuration is injected, not hardcoded. No environment-specific value baked in.
- [ ] `project/architecture.md` and `project/data-model-api.md` reflect what now exists.
- [ ] New dependencies are pinned, licensed compatibly, and noted in the worklog with
      the reason.

**Clean code — reviewable, not a matter of taste.** Each of these is a finding with a
location and a consequence, or it is not raised:
- [ ] The implementation stopped at the first sufficient solution-ladder rung: existing
      repository code/configuration, standard library, native platform, installed
      dependency, then minimum custom code. A lower rung needs a concrete reason.
- [ ] No duplicated logic that must now be changed in two places to stay correct. Two
      similar-looking blocks that will diverge for different reasons are not duplication;
      say which case this is.
- [ ] No abstraction introduced for a second implementation that does not exist. An
      interface with one implementer is indirection, and it costs every future reader.
- [ ] Names say what the thing is or does. A name that requires reading the body to
      understand is a defect the reader pays for repeatedly.
- [ ] Nothing dead: unused code, commented-out blocks, unreachable branches, flags with
      one value, or a stub that pretends to work. Delete it — history keeps it.
- [ ] A function or module does one thing at one level of abstraction. Where a reviewer
      cannot state what it does in a sentence, that is the finding.
- [ ] Conditional depth and special-case count are not growing without a reason. The
      fifth flag on a function is a design problem being paid in `if` statements.
- [ ] A bug is fixed at the shared cause after callers were inspected, rather than with
      repeated guards on only the reported path.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| Silent data loss or corruption on any partial-failure path | S1 — S0 kind, gated behind a failure that has not happened |
| A retry loop that can amplify an outage into total unavailability | S1 |
| An external call with no timeout on a critical path | S1 |
| A non-idempotent consumer of an at-least-once delivery | S1 — duplicates are not a possibility, they are a schedule |
| An unmonitored dead-letter queue, or messages that can be dropped with no record | S1 |
| A breaking event or message schema change that old and new consumers cannot straddle | S1 |
| Unbounded buffering between a fast producer and a slow consumer | S2 |
| A service reading or writing another service's datastore directly | S2 |
| A data model that makes a required future change impossible without migrating everything | S2 |
| Duplicated logic that must now be changed in two places to stay correct | S3 |
| An abstraction with one implementation, added for a second that does not exist | S3 |
| Dead code, a commented-out block, or a stub that pretends to work | S3 |
| A dependency cycle, or a boundary violation that will spread once merged | S2 |
| Business logic made untestable by where it was placed | S2 |
| A material decision made with no ADR, where a later reader could not reconstruct why | S3 |

"Material" means: expensive to reverse, or a future reader would otherwise have to
reverse-engineer the reasoning from the code. If you are unsure whether a decision is
material, it is — an unnecessary ADR costs a page.

---

## Owns

`project/architecture.md`, `project/data-model-api.md`, `project/adr/`.

## Hands off to

Threat modelling of the design → `security`. Deployment, scaling, and observability of
the design → `devops-sre`. Whether the requirement is worth the complexity →
`product-manager`. Test strategy for the seams → `qa`.

---

## Questions this role asks that nobody else will

- What is the second implementation that will need this abstraction? If there is none,
  why is it an abstraction?
- What does this look like when it fails at 3am, and who can tell what happened?
- What did we just make harder to change, and did we mean to?
- Is this complexity in the problem, or did we add it?

# 04 — Quality gates

What gets tested, in what order checks run, and how problems are rated. Stack-agnostic:
the charter names the actual commands, this document names the *stages*.

---

## Check sequence

Run in this order — cheapest and most localising first, so failures are diagnosed fast.

| # | Stage | Purpose | Charter key |
| --- | --- | --- | --- |
| 1 | Format | Mechanical consistency; removes diff noise. | `checks.format` |
| 2 | Lint | Known-bad patterns. | `checks.lint` |
| 3 | Typecheck / static analysis | Contract violations before runtime. | `checks.typecheck` |
| 4 | Unit | Logic in isolation. | `checks.unit` |
| 5 | Integration | Components against real boundaries — data store, queue, filesystem, auth. | `checks.integration` |
| 6 | Contract | The shape of any interface others consume, or that you consume. | `checks.contract` |
| 7 | Build / package | It actually assembles. | `checks.build` |
| 8 | Dependency, secret & license scan | Known vulnerabilities, leaked credentials, incompatible/viral open-source licences. | `checks.scan` |
| 9 | Accessibility | Automated a11y smoke, where there is an interface. | `checks.a11y` |
| 10 | End-to-end | The real journeys, in a realistic environment. | `checks.e2e` |

**Conditional stages.** These exist only in projects that have the surface, and the
charter's roles table says which. Absent everywhere else — and *Absent* is a complete
answer (`06-evidence-and-claims.md`), not a gap to apologise for.

| # | Stage | Purpose | Charter key | Applies when |
| --- | --- | --- | --- | --- |
| 3a | Infrastructure | Plan/diff the change to real infrastructure and scan it against policy, before it is applied. | `checks.infra` | This repository provisions infrastructure |
| 5a | Data quality | Schema, freshness, volume, integrity, and business invariants over the data this project produces or consumes. Order and meaning: `09-probabilistic-and-data-systems.md` §7. | `checks.data` | There are datasets or pipelines |
| 6a | Evaluation | Score the model, prompt, retrieval, or ranker against the versioned golden set. Never a pass/fail on its own — see below. | `checks.eval` | There is a probabilistic output |
| 10a | Performance | Benchmark or load the paths that carry a budget. | `checks.perf` | A latency, throughput, or cost budget exists |

**Evaluation and performance stages report *Measured*, not passed.** A number is
compared against the budget or threshold the charter records, and against the baseline
from before the change. A run with no baseline is not a gate, it is a reading — say so,
and treat the missing baseline as the finding. `09-probabilistic-and-data-systems.md` §3
governs what a comparison requires.

**Infrastructure and data stages gate differently from the rest.** An infrastructure
plan that shows a destroy, a replacement, or a permission widening is a review item for
a named human before it is applied, not a stage that goes green. A data-quality failure
stops the pipeline; it never publishes and warns.

**How much of it runs, by tier.** Tier 1 and Tier 2 run the whole sequence. Tier 3 runs
the stages that can plausibly be affected — for a copy change that is format, lint,
typecheck and the unit suite — and reports the rest **Not run — Tier 3, no code path
affected**. That is a stated reason, so it is not the unexplained skip that QA rates S2.
A Tier 3 change that touches anything executable is not a Tier 3 change.

**Effort mode does not change that sequence.** Lean chooses the smallest meaningful
tests that prove the acceptance criteria and failure paths, then still runs every stage
the tier requires. Beast adds relevant adversarial, recovery, concurrency, scale, or
mutation checks; it does not turn every possible check into mandatory ceremony.

**Rules:**
- A stage with no command in the charter is reported **absent**, explicitly, every time —
  not silently assumed to pass. "No integration suite exists" is a finding for the QA
  role, not a neutral fact. A stage that exists but you did not run is **not run**, with
  the reason (`06-evidence-and-claims.md`).
- Never disable, skip, or loosen a check to make a change pass. If a check is wrong,
  fix the check as its own tracked item with its own justification.
- A flaky test is a defect. Quarantine it with a tracked ID and a deadline; do not
  normalise re-running until green.
- Anything running in CI must be runnable locally, and vice versa. A check only one of
  them can run will drift.
- **Ephemeral test environments:** Any container, service, mock daemon, or local server
  started for a check must be stopped and torn down when the check finishes, whether it
  passed, failed, or timed out. Leaving containers or background processes idling on the
  host machine is a defect.

---

## Test strategy

Generic across stacks. Scale it to the project — a static site does not need a contract
suite; a payments API needs more than a smoke test.

**Unit** — pure logic, validators, policy decisions, formatters, calculations, state
machines. Fast, no I/O, no network. Where the interesting edge cases live.

**Integration** — the seams: persistence and its constraints, authorisation enforced at
the data layer and not only the route, external service clients against recorded or
faked responses, background jobs, file/blob handling.

**Contract** — if anything else consumes your interface, or you consume someone else's:
lock the shape. Breaking changes must fail a test, not a customer.

**End-to-end** — the two to five journeys that, if broken, mean the product is down.
Not a re-implementation of the unit suite through a browser or shell.

**Manual / human** — what automation genuinely cannot judge: language quality by a
native speaker, screen-reader experience, visual/brand judgement, and acceptance by the
person who asked for the thing.

### Ephemeral test environments & resource teardown

When integration, contract, or end-to-end suites require real services (e.g. Docker
containers, Compose services, databases, mock APIs, local dev servers):

- **Encapsulate lifecycle:** Prefer commands that manage their own teardown (e.g.
  `docker compose run --rm`, test fixtures with automatic teardown hooks,
  Testcontainers, or runner scripts using shell `trap ... EXIT`).
- **Guaranteed teardown:** Teardown must execute even when tests fail, throw an
  unhandled exception, or abort. Ephemeral test services must never be left running to
  consume host memory, CPU, or bind ports after the check finishes.
- **Resource bounds:** Where test containers run locally or on shared runners, set
  explicit CPU and memory limits so a runaway test cannot starve the host.

### Non-negotiable test cases for high-risk surfaces

Where the project has them, these are required — not optional extras:

- **Authorisation:** permitted → allowed; not permitted → denied; *another tenant's or
  user's valid ID* → denied **without leaking existence or metadata**; revoked or
  expired access → denied; tampered identifier → denied; stale session →
  re-authentication.
- **Input:** oversized, malformed, wrong type, injection-shaped, unicode/RTL, empty,
  and boundary values.
- **Data:** migration forward and backward; concurrent writes; idempotency of anything
  retryable; deletion actually deletes (including derived copies, caches, and backups
  policy).
- **Money / irreversible actions:** double-submission, partial failure, and reconciliation.

---

## Severity ladder

Rate by **consequence if it reaches users**, never by likelihood or by how hard it is to
fix.

The examples in each rung are illustrative, not an exhaustive list. Rate an unlisted
finding by matching the *kind* of consequence, not by hunting for its exact wording.

| | Severity | The consequence is… | Response |
| --- | --- | --- | --- |
| **S0** | Critical | **Irreversible or unbounded harm.** Data loss or corruption; a security breach or credential leak; one user's or tenant's data exposed to another; total unavailability; content that can physically harm a user; unlawful handling of special-category or children's data; a report that makes every other report untrustworthy. | Stop the release. Incident process. Fix before anything else. |
| **S1** | Major | **Serious harm with no workaround.** A core journey unusable — cannot sign in, cannot complete the primary task, cannot recover from an error. A latent defect of S0 *kind* that has not yet fired: an injectable query, a reachable known-vulnerable dependency, a recovery path that has never been executed. Legal exposure: an unlicensed asset, an unhonourable deletion promise, a representation a regulator would act on. | Release blocker. |
| **S2** | Significant | **Real harm with a poor workaround.** Important function degraded; an accessibility barrier on a surface that is still usable another way; a materially wrong or misleading claim shown to users; a broken public URL or metadata regression on part of the site. | Blocker unless a named human waives it in writing with a tracked follow-up. |
| **S3** | Minor | **Localised.** A functional or visual defect on one surface, inconsistent behaviour, poor edge-case handling, a `project/` document that has drifted from the code. | Scheduled fix; does not block. |
| **S4** | Trivial | **Cosmetic.** Polish, wording preferences, comment and code-level documentation gaps. | Backlog. |

Two rungs to get right, because they are where miscalibration concentrates:

- **S0 vs S1 is not "did it happen yet".** Severity is by consequence, never by
  likelihood — but a defect whose harm *has already occurred, or needs nothing further to
  occur than a user acting normally or an attacker choosing to*, is S0. The same class of
  defect still gated behind an event that has not happened is S1. An exposed record is S0;
  an injectable query nobody has injected is S0 too, because nothing stands between it and
  an attacker. A backup gap that only costs you on the day the disk dies is S1.
- **S2 vs S1 is "poor workaround" vs "no workaround".** A form that is painful by
  keyboard is S2. A primary journey that cannot be completed by keyboard at all is S1.

**Calibration examples** — the point of these is that the first two are *not* judgement
calls:

- One customer can read another customer's record → **S0**, always, regardless of how
  unlikely the path is.
- A password reset email never arrives → S1.
- A form is painful but usable by keyboard → S2. A *primary* journey that cannot be
  completed by keyboard at all → S1: no workaround.
- A published page states an unverified statistic about the business → S2, or S1 if being
  wrong about it is legally or financially consequential (`06-evidence-and-claims.md`).
- A whole production section is accidentally blocked from indexing → S1: not one broken
  URL, but the site's discoverability gone, with no workaround.
- `architecture.md` now describes a structure the code does not have → S3.
- An orphaned test container or background test server left running on the host machine → S3, or S2 if it exhausts memory, blocks required ports, or hangs subsequent runs.
- A button is 2px misaligned on one breakpoint → S4.

Each role playbook in `../roles/` carries a **Severity calibration** table pre-rating its
characteristic findings against this ladder, so the rating is not re-argued every review.
Those tables are the working reference — use the rating they give. If one genuinely
conflicts with the rungs above, rate by the rungs, record the finding, and raise the
mismatch as a defect in the kit, because it will mislead the next review too.

---

## Budgets

Where a project has measurable budgets, the charter's **Budgets** table records them and
this is where they are enforced. Regressions against a budget are S2 by default. Where
there are enough of them to need working detail — measurement method, environment,
baseline, and history — they live in `project/performance-budget.md`.

Candidate budgets to set, if applicable: page or interaction latency at the 75th and
95th percentiles, payload/bundle size, cold-start time, query count per request, error
rate, availability, build duration, test-suite duration; and where the project has them,
throughput at a stated concurrency, cost per request or per pipeline run, data freshness
lag, and evaluation thresholds per category rather than in aggregate.

**A budget is a pair**: the number, and the method that produces it. A latency figure
without the environment, the concurrency, and the percentile is not comparable to the
next one, so it cannot detect a regression — which is the only thing a budget is for.

If a budget is not set, say so — an unstated budget is not "no budget", it is an
unmeasured one.

---

## CI expectations

- Every stage above runs on every change, or the charter documents which run when and
  why.
- CI runs against a realistic environment — real dependency versions, real data store
  where feasible, not an in-memory substitute that hides the failure mode you care about.
- Nightly or periodic: full end-to-end, dependency vulnerability scan, link/crawl checks
  for public content, and the high-risk matrices above.
- Post-deploy: smoke tests plus synthetic checks on the critical journeys.
- A red main branch is an incident, not a normal state.

## Agents in pipelines and environments

**An agent acts up to the production gate and never past it.** The charter's Environments
table says what an agent may do in each environment. Where it is silent, the answer is:
prepare, do not deploy.

- **Start agent CI jobs read-only:** triaging a failed build, summarising a flaky test,
  drafting the changelog. Add writing jobs later, and only as pull requests through the
  same branch protection a person meets. An agent job never pushes to the default branch.
- **Credentials for agent jobs are short-lived and scoped** to the one job. There are no
  standing production credentials. Each run acts under an identity that separates it from
  the person who triggered it.
- **Rollback is the most rehearsed path in the pipeline.** It is one command, run in
  staging often enough that the runbook's "Last executed" date stays inside the charter's
  staleness threshold. `sdlc.py doctor` warns when it does not.
- **Detection stays deterministic.** A monitor, scanner or failed pipeline may invoke an
  agent, but a script decides that something is wrong. What the agent finds enters as an
  ordinary intake item (G6 in `01-lifecycle-gates.md`), and its fix goes through the same
  review as any other change.

## Evaluating the agent's own setup

`AGENTS.md`, the skills, the hooks and the model are configuration that steers every
change. A change to any of them can make the agent worse without any test failing.

- **Keep the tasks that prove the setup works:** 20–50 real tasks from this project's
  history, each with a prompt and checks that decide acceptance (tests pass, a denied path
  stays denied, the right record is written). `benchmarks/kit-value/` in the kit shows the
  shape.
- **Run them when that configuration changes,** and on a schedule. A change that lowers
  the pass rate is reviewed before it merges, like any other regression.
- **Every S0 or S1 whose cause includes the agent's behaviour adds a task,** written by
  the owner of the postmortem. It stays in the set as a regression test.
- Nothing may be claimed to have improved the agent without a baseline run on the same
  tasks before the change (`06-evidence-and-claims.md`, *Measured*).

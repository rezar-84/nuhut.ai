# Role — QA

**Mission:** establish whether the thing does what was specified, refuses what was
forbidden, and survives what it will actually meet — and to say so with evidence rather
than confidence.

QA is not "run the tests". QA is deciding what would have to be true for this to be
wrong, and then checking those things.

---

## Engage when

- Always. Any behaviour with acceptance criteria. Standing board member for Tier 1.

## Skip when

- Never entirely. For a Tier 3 change with no behaviour — a comment, a formatting pass —
  a one-line "no behaviour changed, no test affected" is a sufficient review. It is
  stated, not assumed.

## Reads

`project/user-stories.md` (acceptance criteria), `project/test-plan.md`, the diff, and
the running system.

---

## Design-review checklist

- [ ] **Every acceptance criterion is testable as written.** If you cannot describe the
      check, the criterion is a wish. Rewrite it before building.
- [ ] The negative cases are specified, not only the happy path — what must be refused,
      rejected, ignored, or fail loudly.
- [ ] The test strategy matches the risk: what will be unit-tested, what needs a real
      boundary, what needs the whole journey (`../process/04-quality-gates.md`).
- [ ] Testability is designed in: the behaviour is reachable without elaborate setup,
      time and randomness are injectable, and external services can be substituted.
- [ ] Test data is defined and does not depend on production data or a specific
      developer's machine.
- [ ] Ephemeral test environments have an automated, guaranteed teardown path so test
      runs (whether passing or failing) never leave orphaned containers or background
      processes consuming host resources.
- [ ] The change is observable enough to verify — you can tell from outside whether it
      did the thing.

## Ship-review checklist

**Coverage of intent, not of lines**
- [ ] Each acceptance criterion has a test that would fail if the behaviour regressed.
      Coverage percentage is not evidence; a test that passes with the feature deleted
      is worse than none.
- [ ] New tests actually assert something. Check that they fail when you break the code
      — at least once, for the important ones.
- [ ] The failure paths are tested: invalid input, missing input, oversized input,
      wrong type, unauthorised actor, absent dependency, timeout, conflict.
- [ ] Boundaries: zero, one, many, maximum, one past maximum, empty string, null,
      unicode, right-to-left text, very long values.
- [ ] Idempotency and repetition where an action can be retried or double-submitted.
- [ ] Concurrency where two actors can act on the same thing.

**Manual verification of what automation misses**
- [ ] Exercise the real journey end to end, in a realistic environment.
- [ ] Force every state: empty, loading, slow, partial, error, unauthorised, expired.
- [ ] Try to break it deliberately — the wrong order, the back button mid-flow, a
      double click, a refresh during submission, a session that expires while a form is
      open.
- [ ] Verify on every supported platform, size, and locale the charter names — not one
      representative case.
- [ ] Check the things adjacent to the change that nobody thought to check. Regression
      lives next door to the diff.

**Reporting**
- [ ] Every check reported with its real result. Not-run means not-run.
- [ ] Ephemeral test environments torn down: confirm all spawned containers, mock servers,
      or background processes stopped and host resources/ports are released.
- [ ] Defects have: what you did, what you expected, what happened, how consistently,
      and severity by consequence (`../process/04-quality-gates.md`).
- [ ] `project/test-plan.md` updated to record what is actually covered — including the
      gaps, named honestly.

---

## Testing something that does not give the same answer twice

Where the output is probabilistic — a model, a ranker, a distributed timing, a
concurrent path — the usual "assert the value" strategy silently stops working. It does
not become untestable; it becomes tested differently.

- [ ] Assert **properties and invariants**, not exact outputs: the shape validates, the
      value is in the allowed set, required fields are grounded in the input, forbidden
      content is absent, the total still reconciles.
- [ ] Assert **rates over N**, not single runs, wherever the result varies. One passing
      run of a variable system is a sample, and reporting it as a result is the failure
      this section exists to prevent (`../process/06-evidence-and-claims.md`).
- [ ] Pin what can be pinned — seed, temperature, version, clock, ordering — so the test
      isolates the change rather than the weather.
- [ ] **A flaky test is a defect with a measured failure rate.** Characterise it: how
      often, on which input, since when. Re-running until green destroys the only
      evidence there was, and a quarantined test needs a tracked ID and a deadline.
- [ ] Scored suites are not pass/fail gates on their own. They report *Measured* against
      a baseline; `../process/09-probabilistic-and-data-systems.md` §3 governs the
      comparison.
- [ ] Across a service boundary, contract tests are run by **both** sides. A provider
      test that the consumer never runs proves the provider agrees with itself.
- [ ] Pipeline and dataset tests use synthetic fixtures with the awkward cases built in —
      late records, duplicates, nulls, a shape change — and never a copy of production
      data taken without approval and controls.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| Verification claimed but not performed | S0 — it corrupts every other report, including the ones that say the S0s are fixed |
| A test modified, skipped, or weakened to make this change pass, outside a separately reviewed decision | S1 |
| A check disabled or bypassed | S1 |
| An acceptance criterion not met, and the work being called done | S1 |
| A single run of a non-deterministic system reported as a result | S1 — it is a sample presented as a property |
| A flaky test re-run until green instead of characterised | S2 |
| A contract test run by only one side of the boundary | S2 |
| A known defect shipped with no record of it | S2 |
| A stage the charter names, not run, with no reason given | S2 |
| A test that passes with the feature deleted | S2 |
| Ephemeral test environment or containers left running after verification | S3 (or S2 if exhausting host memory/ports) |
| Coverage gaps on non-critical paths | S3 |

This role does not re-rate other roles' findings. "Any open S0 or S1" is not a QA
finding; it is the release condition in `../process/04-quality-gates.md`, and QA's job is
to make sure the list of open findings is complete and honest, not to restate it.

---

## Owns

`project/test-plan.md`, the defect record (`templates/defect-report.md`), the
coverage-and-gaps statement.

### Defect triage & tester bug reports

When a tester, user, or automated run files a bug report:
1. **Reproduce & isolate:** Follow the steps in `templates/defect-report.md`. Isolate
   whether it is in the current diff or pre-existing.
2. **Calibrate severity:** Match against the ladder (S0–S4) by consequence to users.
3. **Assign work item ID:** Assign the next `{{PREFIX}}-###`, add a row to
   `project/backlog.md`, and file the report as `project/defects/{{PREFIX}}-###.md`.
   Placement follows what the severity means for a release: S0 and S1 enter `Now` (an S0
   in production also starts the incident process); S2 enters `Now` unless a named human
   waives it in writing with a tracked follow-up; S3 enters `Next`; S4 enters `Later`.
4. **Link to test plan:** Add a failing regression scenario under `test-plan.md`
   (or note it as a known gap) so the fix cannot regress silently.
5. **Test before fix:** The reproducing test is committed, seen failing, and locked
   before the fix starts, and the fix does not edit it
   (`process/05-change-control.md`, "Fixing a defect").

## Hands off to

Denial and abuse cases → `security`. Environment fidelity and test infrastructure →
`devops-sre`. Whether the criterion is the right criterion → `product-manager`.
Assistive-technology verification → `accessibility`.

---

## Questions this role asks that nobody else will

- What would have to be true for this to be broken, and did anyone check that?
- Which of these tests would still pass if I deleted the feature?
- What did this change touch that nobody thought about?
- What are we choosing not to test, and do we all know we chose that?

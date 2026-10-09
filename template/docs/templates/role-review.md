---
status: draft
owner: _(reviewing agent or person)_
last-reviewed: YYYY-MM-DD
---

# Review — {{PREFIX}}-### <title>

**Stage:** design | ship **Tier:** 1 | 2 | 3
**Reviewed:** _(what was actually read — plan file, commit range, running environment)_

---

## Conformance (ship review, Tier 1 and 2)

**plan-check:** _(the output of `sdlc.py plan-check <ID>` for Tier 1, and for each
unplanned or untouched path, whether it is a plan to update or a change to question)_

**Acceptance criteria:** _(each criterion → the code and the test that prove it, or the
finding that it is not met)_

**Out of scope held:** _(yes, or what shipped that the plan excluded)_

---

## <role-name>

**Verdict:** Pass | Pass with conditions | Block

**Checked:** _(what you actually examined and how — required even when there are no
findings. "All 6 new endpoints for object-level authorisation, both migrations for a
reverse path, and the audit output for token leakage.")_

**Not checked:** _(what this review does not cover, and why. Never imply coverage you do
not have.)_

### Findings

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S_ | `file:line` | _(what is wrong)_ | _(what goes wrong because of it)_ | _(what would resolve it)_ |

### Conditions

_(Only for "Pass with conditions". Each becomes a backlog item before merge, with an ID.)_

- [ ] _(condition)_ → {{PREFIX}}-###

---

_(Repeat the block above for each role engaged. Select roles by change surface and tier —
see `../process/02-role-reviews.md`. Do not include a role you did not actually run.)_

---

## Outcome

**Overall:** Pass | Pass with conditions | Block

_(The most severe verdict any single role returned. Not an average, and not a judgement
of your own about whether the findings are worth stopping for.)_

**Blocking findings:** _(list, or none)_

**Waivers:** _(An S2 waiver requires a named human, a written reason, and a follow-up ID.
S0 and S1 are not waivable. An agent may not waive its own blocker — see
`../process/02-role-reviews.md`. If there are none, write "none".)_

| Finding | Waived by | Reason | Follow-up |
| --- | --- | --- | --- |

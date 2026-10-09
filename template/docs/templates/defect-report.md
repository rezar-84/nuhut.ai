---
status: draft
owner: qa
last-reviewed: YYYY-MM-DD
---

# Defect report — {{PREFIX}}-### <title>

**Severity:** S0 | S1 | S2 | S3 | S4 **Found by:** _(tester / tool / user)_
**Environment:** _(staging / local / production)_ **Date:** YYYY-MM-DD
**Related work item / feature:** {{PREFIX}}-### _(or "none")_

---

## Summary

_(One or two sentences: what went wrong, under what circumstances, and the impact on the user.)_

## Steps to reproduce

1. _(Go to …)_
2. _(Perform action with specific inputs …)_
3. _(Click / submit …)_

**Inputs / Payload:**
```
_(exact parameters, query, body, or screen dimensions)_
```

## Expected vs. Observed

- **Expected:** _(what the acceptance criteria or specification states should happen)_
- **Observed:** _(what actually happened, including exact error messages or screen behavior)_

## Evidence

- **Logs / console errors:**
```
_(paste stack trace, network error, or server logs)_
```
- **Screenshots / Recordings:** _(links or references)_

---

## Severity

**Rated:** S_ — _(the one sentence that places it on the ladder in
`{{DOCS_DIR}}/process/04-quality-gates.md` — by consequence to users and data, never by
how easy the fix looks. A latent defect of S0 kind that has not fired yet is still S1 at
least.)_

---

## Triage & resolution

- [ ] **Reproduced by:** _(tester or QA agent)_
- [ ] **Backlog item assigned:** `{{PREFIX}}-###` added to `{{DOCS_DIR}}/project/backlog.md`
- [ ] **Regression test identified:** _(which test will be added to `test-plan.md` to prevent recurrence)_
- [ ] **Assigned owner / role:** _(role responsible for fix)_

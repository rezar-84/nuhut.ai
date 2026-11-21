## NUHT-005 — Review triage: paraphrase step and Contest/Escalate/Fix/Decline responses, escalations in Needs you (touch: template/docs/process/02-role-reviews.md, template/docs/templates/role-review.md, handbook/process/02-role-reviews.md, handbook/templates/role-review.md, optional/runtime/sdlc.py, .ai-sdlc/bin/sdlc.py, .claude/commands/sdlc-review.md, optional/commands/, tests/smoke.py, CHANGELOG.md, docs/)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `4ba9260..b34ee52`

### What changed

- fix(NUHT-005): make the escalation gate fail closed (b34ee52)
- feat(NUHT-005): answer review findings (Fix/Contest/Escalate/Decline); paraphrase-first design reviews (821415b)
- docs(NUHT-007): plan and ADR 0002 for a fresh-context review level; file NUHT-005..009 (4ba9260)

Files: `CHANGELOG.md`, `docs/cli.md`, `docs/viewer.md`, `optional/runtime/finish.py`, `optional/runtime/sdlc.py`, `tests/smoke.py`, `handbook/process/02-role-reviews.md`, `handbook/templates/role-review.md`, `optional/claude-commands/sdlc-review.md`, `optional/runtime/view.html`, `optional/runtime/view/js/12-dashboard.js`, `template/docs/process/02-role-reviews.md` (+1 more)

### Why

From the Elephant-Goldfish Model comparison: reviews had no structured author answer, so a finding only a person can settle had nowhere to wait. Escalations now block finish and show in Needs you. Rejected: a doctor fail for open escalations, which would turn every pending decision into a red failure; a warn routed to Needs you matches 'waiting on a person'.

### Verified

- `checks.lint` — Verified: pass — run 20261120T234923Z, commit b34ee52
- `checks.unit` — Verified: pass — run 20261120T234923Z, commit b34ee52
- `checks.integration` — Verified: pass — run 20261120T234923Z, commit b34ee52
- `checks.build` — Verified: pass — run 20261120T234923Z, commit b34ee52

### Not done

NUHT-007 (fresh-context review level) is Parked for owner approval; NUHT-008/009 Deferred.

### Discovered

Ship review F1-F3: the first parser failed open (escaped pipes, 'pending' in Decided by, 'Escalated', column order, '### Responses'). Fixed in b34ee52.

### Decisions

none (ADR 0002 is NUHT-007's, proposed)

### Assumptions used

none

### Plan

From the Elephant-Goldfish Model comparison: reviews had no structured author answer, so a finding only a person can settle had nowhere to wait. Escalations now block finish and show in Needs you. Rejected: a doctor fail for open escalations, which would turn every pending decision into a red failure; a warn routed to Needs you matches 'waiting on a person'.

### Reviews

Fresh-context ship review (claude-code subagent, same model family as the author, so recorded as a self-check) of 0831487..821415b: Pass with conditions, 5 x S3 and 3 x S4. All fixed in 6ecebdc/3bbff99/b34ee52 with failing-first smoke tests. F1-F3, F6-F8 were this item's.

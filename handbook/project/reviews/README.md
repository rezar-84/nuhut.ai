# Review records

One file per **Tier 1** review: `NUHT-###-design.md` or `NUHT-###-ship.md`,
from `../../templates/role-review.md`. Nothing else lands here.

## What lands here

| Tier | Design review | Ship review | Lands here? |
| --- | --- | --- | --- |
| 1 | Required | Required | **Yes — a file each.** They are the audit trail behind the two human approvals. |
| 2 | Required | Required | No. The verdicts go in the worklog entry's **Reviews** section. |
| 3 | One role, one line | Skipped | No. Same worklog section. |

Add a row to the Index below for every file you create here.

## What makes a record worth keeping

Each role block states **what was checked**, not only what was found. A review that found
nothing is valuable if it says where it looked; it is worthless if it says "looks good".

Everything else — the evidence rule, verdicts, severity, waivers, and the named
anti-patterns — is in `../../process/02-role-reviews.md`. Read it before writing one of
these, not after.

## Index

| Work item | Stage | Date | Outcome |
| --- | --- | --- | --- |
| NUHT-001 | design | 2026-11-13 | see file |
| NUHT-001 | ship | 2026-11-13 | Pass |
| NUHT-002 | design | 2026-11-13 | see file |
| NUHT-002 | ship | 2026-11-15 | Pass (re-review: Block, fixed) |
| NUHT-003 | design | 2026-11-13 | see file |
| NUHT-003 | ship | 2026-11-13 | Pass |
| NUHT-016 | design | 2026-11-22 | Pass with fixes (self-check; see file) |

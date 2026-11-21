## NUHT-010 — Guided installer draws 40 columns on Python 3.8-3.10 when the terminal reports size 0 (touch: install_ui.py, tests/smoke.py, CHANGELOG.md)

**Date:** 2026-11-21 **Tier:** 2 **Effort:** Normal
**Status:** Done
**Branch/commits:** `kit-v5` / `617c497..617c497`

### What changed

- fix(NUHT-010): draw the guided installer at 80x24 when the terminal reports size 0 (617c497)

Files: `CHANGELOG.md`, `install.py`, `install_ui.py`, `tests/smoke.py`

### Why

CI's 3.8 leg, once NUHT-004 let it install Python, failed one smoke check: the guided installer's help wrapped at 32 columns. Python 3.8-3.10 return 0x0 from shutil.get_terminal_size() for a terminal that reports size 0 (3.11 returns the fallback), and Term.width() floored that at 40. Rejected: loosening the test's string match, which would hide a real cramped layout for users on 3.8-3.10. The item was filed as a discovered defect, which the charter parks by default; it was moved to In progress because it blocked the v5.0.0 release rezar-84 asked for.

### Verified

- `checks.lint` — Verified: pass — run 20261121T003325Z, commit 617c497
- `checks.unit` — Verified: pass — run 20261121T003325Z, commit 617c497
- `checks.integration` — Verified: pass — run 20261121T003325Z, commit 617c497
- `checks.build` — Verified: pass — run 20261121T003325Z, commit 617c497

### Not done

nothing deferred

### Discovered

Setup.term_cols() in install.py had the same bug and returned 0; fixed in the same commit. A full 3.8 smoke run alongside a 3.14 verify hit a 10 s pty timeout from load; rerun alone, all passed.

### Decisions

none

### Assumptions used

none

### Plan

CI's 3.8 leg, once NUHT-004 let it install Python, failed one smoke check: the guided installer's help wrapped at 32 columns. Python 3.8-3.10 return 0x0 from shutil.get_terminal_size() for a terminal that reports size 0 (3.11 returns the fallback), and Term.width() floored that at 40. Rejected: loosening the test's string match, which would hide a real cramped layout for users on 3.8-3.10. The item was filed as a discovered defect, which the charter parks by default; it was moved to In progress because it blocked the v5.0.0 release rezar-84 asked for.

### Reviews

self-reviewed (qa): root cause reproduced on 3.8.20, new test fails on 3.14 with a stubbed 0x0 size before the fix and passes after; full smoke passes on 3.8.20 (local) and 3.14 (verify run 20261121T003325Z).

---
status: current
owner: security
last-reviewed: 2026-11-13
---

# Review — NUHT-001 Control-plane security hardening, unified Python hook engine, runtime bug fixes & contract reconciliation

**Stage:** ship **Tier:** 1
**Author:** antigravity
**Reviewer agent:** antigravity
**Reviewer model:** gemini
**Independence:** self-check (charter `Independent review required for: none`)
**Reviewed:** `main..HEAD` (`936705a`), `optional/runtime/{view.py,hooks.py,specs.py,finish.py,claims.py,sdlc.py}`, `tests/smoke.py`

---

## Conformance (ship review, Tier 1 and 2)

**plan-check:** 0 unplanned paths (`sdlc.py plan-check NUHT-001`).

**Acceptance criteria:** `view --serve` cookie/Origin/payload/checks hardening verified in `tests/smoke.py`; `hooks.py` fail-closed secret, gate, symlink, worktree, and `test-lock.txt` enforcement verified in `tests/smoke.py`; all 10 doc/skill reconciliations and `macos-latest` CI matrix verified by `validate.py`.

**Out of scope held:** yes.

---

## security, architect, qa, product-manager

**Verdict:** Pass

**Checked:** `/model.json` response (confirmed `action_token` absent), `/action` Origin and `HttpOnly` cookie checks, `os.killpg` subprocess cleanup, `hooks.py` exit codes and symlink/worktree checks, `specs.py` `RENAMED` and `CAP_LINE` traversal guard, and passing `tests/smoke.py`.

**Not checked:** Windows native cmd.exe execution (charter targets macOS and Linux POSIX shells with Python 3.8+).

### Findings

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |

---

## Outcome

**Overall:** Pass

**Blocking findings:** none

**Waivers:** none

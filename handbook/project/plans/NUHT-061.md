# NUHT-061: Fixes from the retro ship reviews of 6.0 items

Tier 1 (it changes the evidence and approval gates) · fix · qa. This is the fix pass on the
2026-11-26 ship reviews of NUHT-012, 014, 022, 024 and 027. The approved plan says the
fixes may be built.

## Change

- **A newer failing run blocks `finish`** (NUHT-012 #2). `verify_state` returns fail for
  any failing run on the code being finished, including a `--stage` run newer than an
  older full pass.
- **No GitHub review counts on a PR with no readable author** (NUHT-024 #3). Without the
  author, independence cannot be shown; `approvals` falls back with `pr-author-unknown`.
- **An unreadable tier is judged as Tier 1 in `approvals`** (NUHT-024 #4).
- **Docs for the deprecated `release` alias** (NUHT-027 #6). They now say the note goes to
  stderr, or into a `deprecated` JSON field with `--json`.

The other findings are contested, declined under ADR 0004, or tracked in NUHT-062.

## Files that change

- `optional/runtime/finish.py` (plus its `.ai-sdlc/bin/` copy)
- `tests/smoke.py`: `test_fast_verify` and `test_github_approvals`
- `docs/cli.md`, `docs/multi-agent.md`, `CHANGELOG.md`

## Tests

- "a newer failing --stage run blocks finish after an older full pass".
- "a PR with no readable author counts no GitHub review". Shown failing without the fix.

## Rollback

Revert the commit. The two approval changes only make the gate stricter.

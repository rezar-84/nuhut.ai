# NUHT-046: Pin GitHub Actions to commit hashes

Tier 1 (it changes the release workflow) · chore · software-engineer. Approved by rezar-84
on 2026-11-25 (decision 5: "Do it").

## Problem

The workflows ran `actions/checkout@v4` and `actions/setup-python@v5`. A tag can be moved
to other code, and that code runs with the repository token, including in the release job
that pushes to `main`.

## Change

- Every `uses:` in `.github/workflows/*.yml` is pinned to a 40-character commit hash, with
  its version as a comment: `checkout` v4.4.0 `11d5960…`, `setup-python` v5.6.0
  `a26af69…`. The hashes come from `git ls-remote` of each action's tag.
- `.github/dependabot.yml` updates the pins weekly. Each update is a PR that moves the hash
  and the comment together.
- `validate.py` fails on an unpinned action in this repository's workflows.
- The scaffolded GitHub workflow pins `checkout` the same way (`PINNED_CHECKOUT` in
  `install.py`). The Gitea scaffold keeps `@v4`, because its runners may resolve actions
  from a mirror where GitHub's hash does not exist.

## Out of scope

The `python:3.12` images in the GitLab and Bitbucket scaffolds are not pinned to a digest.
A scaffold that froze an image would never receive security fixes unless the project ran
an update bot; the tag keeps them current. The item's title named both; this records why
only the actions are pinned.

## Files that change

- `.github/workflows/*.yml`, `.github/dependabot.yml`
- `install.py`, `validate.py`, `tests/smoke.py` (`test_scaffolding`)
- `CHANGELOG.md`

## Tests

`test_scaffolding`: "GitHub CI pins actions/checkout to a commit, with its version as a
comment (NUHT-046)". It was shown failing before the change. `validate.py` passes with
the pinned workflows.

## Rollback

Revert the commit. The tags still exist upstream.

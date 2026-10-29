# Contributing

Contributions should keep the kit portable, evidence-based, and usable without a runtime
dependency after installation.

## Before opening a change

1. Create a focused branch and explain the behavior being changed.
2. Keep project-specific policy out of `template/docs/process/` and
   `template/docs/roles/`.
3. Update `CHANGELOG.md` under **Unreleased** for user-visible changes.
4. Add or update a smoke test for installer behavior.
5. Run:

   ```sh
   python3 validate.py
   python3 tests/smoke.py
   python3 -m py_compile install.py validate.py tests/smoke.py optional/runtime/sdlc.py optional/runtime/view.py
   python3 optional/runtime/sdlc.py --selftest
   python3 benchmarks/effort-modes/score.py --selftest
   python3 benchmarks/kit-value/score.py --selftest
   python3 benchmarks/kit-value/measure.py --selftest
   ```

   `validate.py` cross-checks the pairings the kit maintains by hand: every role has a
   playbook, a charter row and a README entry; every template is in the docs map; every
   skill has an install rule; every check stage has a charter row. It also measures each
   tier's reading list against its word budget (`python3 validate.py --reading-lists`).
   The smoke suite needs full git history for its upgrade and benchmark tests
   (`git fetch --unshallow --tags`); without it they skip and say so.

## Compatibility

`install.py` uses only the Python standard library and supports Python 3.8 or newer (the versions CI tests).
Installed projects must not need Python or any dependency from this repository.

Do not add a stack-specific requirement to the portable process. Stack detection may
offer a verified default, but the guided review must allow a user to reject or edit it.
Every adapter change needs a fixture proving its language marker, data-layer marker,
migration tooling, test tooling, and commands. Detection must never read secrets or
install a dependency.

## Benchmarks

Whether the kit is worth its context cost is measured, not claimed:
[`benchmarks/kit-value/`](benchmarks/kit-value/README.md) runs the same tasks with no kit,
the kit, and the kit plus hooks. Change a task's checks only with a crafted workspace in
`tests/smoke.py` (`test_kit_value_checks`) that shows the misfire passing and a real
violation failing.

## The viewer

`optional/runtime/view.html` is generated. Edit its parts in `optional/runtime/view/` (the head, stylesheet and shell, plus one file per section of the script, under `js/`). Then run `python3 tools/build_view.py`. `validate.py` fails when the two differ. Stack detection lives in `optional/runtime/detect.py`, shared by the installer and the runtime.

## Versioning

The kit is versioned automatically, with semantic versioning, from Conventional Commit
subjects (`tools/semver.py`, run by `.github/workflows/version.yml` on every push):

- `feat(...)` → minor, a `!` after the type or a `BREAKING CHANGE:` footer → major,
  anything else (fix, docs, chore, refactor) → patch. A subject with several types
  (`docs,feat(kit): ...`) takes the largest.
- **Push or merge to `main`:** after `validate.py` and the smoke tests pass, the workflow
  bumps `VERSION`, `.claude-plugin/plugin.json` and `CHANGELOG.md` (the Unreleased section
  becomes the release), commits `chore(release): vX.Y.Z`, tags it and publishes a release.
- **Push to any other branch:** the job summary shows the prerelease it would become
  (`4.1.0-dev.7+abc1234`); nothing is committed.

Do not edit `VERSION` by hand; write the change under `## Unreleased` in the changelog.
`python3 tools/semver.py next` shows what the next merge will release.

## Pull requests

Describe the risk, the compatibility impact, the test evidence, and any migration or
rollback concern. Changes to managed upgrade behavior need tests for clean upgrades,
locally modified files, obsolete files, and dry runs.

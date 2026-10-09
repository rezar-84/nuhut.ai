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
   ```

## Compatibility

`install.py` uses only the Python standard library and supports Python 3.8 or newer (the versions CI tests).
Installed projects must not need Python or any dependency from this repository.

Do not add a stack-specific requirement to the portable process. Stack detection may
offer a verified default, but the guided review must allow a user to reject or edit it.
Every adapter change needs a fixture proving its language marker, data-layer marker,
migration tooling, test tooling, and commands. Detection must never read secrets or
install a dependency.

## Pull requests

Describe the risk, the compatibility impact, the test evidence, and any migration or
rollback concern. Changes to managed upgrade behavior need tests for clean upgrades,
locally modified files, obsolete files, and dry runs.

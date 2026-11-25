# NUHT-048: Detected check commands are lost after a -y install

Tier 2 · fix · software-engineer

## Problem

On a `-y` install the installer detects check commands (for example `npm run test` from
`package.json`) and writes them only to `.ai-sdlc/profile.json`. The charter's
`checks.*` rows stay blank on purpose: nobody answered, so nothing is declared. Then:

- `verify` reports every stage Absent;
- `doctor` says "The charter wins; correct the profile";
- `fix sync-profile`, also run by `fix all`, erases the detected commands.

## Change

Keep the rule that a `-y` install declares nothing. Stop losing the detection:

- `detected_commands(project)`: the profile's commands for `checks.*` rows that are
  blank. A row marked `absent` or filled in is never listed.
- `fix adopt-commands [--apply]`: previews, and with `--apply` writes them into the
  blank rows.
- `doctor`: a separate warning names the detected commands, with the adopt command as
  its fix. It is no longer reported as "correct the profile", nor offered to
  `sync-profile`.
- `sync-profile`: keeps a detected command while its row is blank.
- `status`: a "commands" setup gap.

## Files that change

- `optional/runtime/sdlc.py`, `optional/runtime/status.py`, and their `.ai-sdlc/bin/` copies
- `tests/smoke.py`
- `docs/cli.md`, `CHANGELOG.md`

## Tests

`test_adopt_detected_commands`: a `-y` install with `test` and `lint` scripts in
`package.json`. It shows doctor, status, sync-profile, preview and apply behaving as
above, and an `absent` row left alone. Shown failing before the change.

## Rollback

Revert the commit. Charter rows already adopted stay as written, and a person can clear
them.

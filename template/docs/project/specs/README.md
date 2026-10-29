# Specs

What the system does **now**, one file per capability (`<capability>.md`), written as
requirements with WHEN/THEN scenarios. Only used when the charter's **Specs** row is `on`
(`python3 .ai-sdlc/bin/sdlc.py config --specs on`).

- A work item that changes behaviour adds `changes/<ID>.md` (template:
  `../../templates/spec-change.md`) with ADDED, MODIFIED and REMOVED requirements.
- On close, `python3 .ai-sdlc/bin/sdlc.py spec apply <ID> --write` merges the change into
  the capability files and moves it to `changes/archive/`.
- `sdlc.py spec validate` checks every requirement says SHALL or MUST and has a scenario
  with both WHEN and THEN, and that MODIFIED and REMOVED name a requirement that exists.

The headings are the ones OpenSpec uses, so an existing `openspec/` folder is read beside
these (read-only), and so are Spec Kit feature specs, best-effort.

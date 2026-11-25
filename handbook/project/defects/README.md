# Defects

One file per reported defect: `NUHT-###.md`, from `../../templates/defect-report.md`.
The ID is the backlog item that tracks the fix — a defect gets its number when it is
triaged, not a second numbering scheme of its own.

Triage is `qa`'s (`../../roles/qa.md` → "Defect triage"). Severity is rated on the ladder
in `../../process/04-quality-gates.md`, by consequence, never by how easy the fix looks.
An S0 or S1 in production is also an incident: it gets a postmortem in `../postmortems/`.

## Index

| ID | Defect | Severity | Found by | Status |
| --- | --- | --- | --- | --- |
| NUHT-010 | Guided installer draws 40 columns on Python 3.8-3.10 when the terminal reports size 0 | unrated | — | Done |
| NUHT-011 | Self-install kit_version drifts from VERSION after a release | unrated | — | Done |
| NUHT-012 | finish accepts stale, stage-only or self-waived verify evidence | unrated | — | Ready |
| NUHT-013 | Test-lock and protected-path guards miss shell writes (sed -i, redirects, tee, python -c) | unrated | — | Done |
| NUHT-015 | install.sh version floor and wording; finish swallows exceptions silently | unrated | — | Done |

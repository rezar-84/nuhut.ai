---
description: Check this project's SDLC documents for gaps, staleness, and drift
argument-hint: "[optional: charter | roles | staleness | traceability | profile]"
---

Audit the installed kit in this repository and report what is wrong with it. Scoped to:

$ARGUMENTS

(If no argument is given, run every section below.)

This command **reports**; it does not fix. Findings become backlog items, and the ones
that need a human decision — an unticked role, a missing approver — stay with the human.

## 0. Run the mechanical checks first

```sh
python3 .ai-sdlc/bin/sdlc.py doctor
```

It decides from the files what does not need judgment: sections 1, 2, 4 (dates), 5, 6
and 7 below, and in section 3 the blank rows, the modes and the roles with no reason.
**Report its findings as they are; do not redo those checks by reading the files
yourself.** A script that reads every row is more reliable than a model that skims them.
Your part is what it cannot decide:
- the severity of each finding;
- in section 3, deployment platforms against `{{DOCS_DIR}}/platforms/`, blank Model & data
  or Budgets cells, and whether the artifacts that ticked roles own exist;
- in section 4, whether a `status: stale` document has a backlog item;
- section 8;
- what to do first.

If the script is missing (installed before the runtime existed) or `python3` is not
available, do every section by hand, as written. The sections below are the
specification either way.

## 1. Substitution

```sh
grep -rn '[{][{]' {{DOCS_DIR}} AGENTS.md .claude 2>/dev/null
```

(The character class is deliberate — a literal double brace in this file would itself be
substituted at install time.)

Any hit is a broken install: an unsubstituted work-item prefix leaves a literal path in
the docs an agent follows. Report every occurrence with its file.

## 2. Is anything pointing at the contract?

Nothing in this kit runs unless an agent is told to read `AGENTS.md`, and every tool
looks in a different file. Check that at least one of these names it:

```sh
grep -ln 'AGENTS.md' CLAUDE.md GEMINI.md AGENT.md CONVENTIONS.md \
  .github/copilot-instructions.md .cursor/rules/*.mdc .windsurfrules .clinerules 2>/dev/null
```

No output is a **finding of the highest severity in this report**: the documents are
installed, the process is not running, and nothing about the repository looks wrong. The
fix is one line — `Read and follow \`AGENTS.md\` in this directory.` — in whichever file
the tool in use actually loads. `.ai-sdlc/profile.json` → `harnesses` records what the
installer wired; a file listed there that no longer mentions `AGENTS.md` was edited since.

Codex, Jules, Zed, Factory and opencode read `AGENTS.md` directly and need no pointer.

## 3. Charter completeness

Read `{{DOCS_DIR}}/project/charter.md`. A blank cell is **Unknown**, not "not applicable"
(`{{DOCS_DIR}}/process/06-evidence-and-claims.md`), and an agent that guesses a check
command because the charter was blank produces confidently false "verified" claims.
Report, in this order of severity:

- Blank rows in **Commands** — each one is a stage that cannot be run or reported.
  Distinguish blank (nobody filled it in) from the word "absent" (deliberate).
- Blank **approvers**, **default branch**, or **staleness window**.
- **Deployment platforms** that disagree with `{{DOCS_DIR}}/platforms/`: a platform named
  in the charter with a kit checklist that is not installed, or an installed checklist
  for a platform the charter no longer names. Either way, report it; do not delete a
  checklist or edit the row yourself.
- Blank cells in **Model & data** or **Budgets** where the corresponding role is ticked.
- Invalid **Default effort mode** / **Acquisition profile** values. A row still listing
  every option is *undecided*, not invalid: the documented default (Normal / Standard)
  applies, and you report it as a question, not an error. A legacy
  `Operating mode: Beast mode` row is ambiguous and must be migrated explicitly; do not
  guess whether it meant completeness or permissive acquisition.
- **Unticked roles with an empty reason column.** A blank reason means nobody decided;
  it does not mean the role does not apply. List each one as a question for a human.
- Ticked roles whose owned artifacts do not exist (see `{{DOCS_DIR}}/README.md` → the
  "Create when" column, which is the only statement of which artifacts this project is
  supposed to have).

## 4. Staleness

For every file in `{{DOCS_DIR}}/project/`, read the frontmatter `last-reviewed` and
compare against today and the charter's staleness window. Report anything older, anything
with a missing or malformed date, and anything marked `status: stale` that has no backlog
item to fix it. ADRs are exempt: they are dated records and are superseded, not refreshed.

## 5. Traceability

Per `{{DOCS_DIR}}/process/07-traceability.md`:

- Backlog rows in a done state with no worklog entry carrying that ID.
- Worklog entries whose ID is not in the backlog.
- Items marked `Parked` with no stated blocker or owner.
- Branches or recent commits referencing an ID that exists in neither.

## 6. Worklog size

Report the line count of `{{DOCS_DIR}}/project/worklog.md`. Past the rotation threshold in
`07-traceability.md`, recommend rotating the closed entries into
`{{DOCS_DIR}}/project/worklog-archive/`. An unbounded worklog quietly becomes the largest
file every future agent reads.

## 7. Profile drift

If `.ai-sdlc/profile.json` exists, compare its `commands`, `roles`, `docs_dir`,
`effort_mode`, and `acquisition_profile`
against the charter. **The charter is the source of truth**; report any difference as
drift to be corrected in the profile, never the other way round. Report a `kit_version`
older than `.ai-sdlc/manifest.json` as an incomplete upgrade.

## 8. Refresh the status page

If `{{DOCS_DIR}}/dashboard.html` exists, rewrite `{{DOCS_DIR}}/dashboard-state.js` from
what you just read, keeping the shape that is already in the file: `generated` (today),
`project`, `prefix`, `kit_version`, `docs_dir`, `profile`, `effort_mode`,
`acquisition_profile`, `wired`, `staleness_days`, and
the arrays `roles` (`name` · `active` · `reason`), `commands` (`stage` · `command`),
`items` (`id` · `task` · `tier` · `owner` · `depends` · `status`), `artifacts` (`file` ·
`status` · `owner` · `last_reviewed`), and `budgets`.

It is a generated project record, not a kit file — overwrite it whole rather than editing
around the edges, and set `generated` to today so the page stops declaring itself stale.
Never write a value you did not read from a file: the page inherits this kit's evidence
rules, and a status page that states something nobody verified is the exact failure the
rest of these documents exist to prevent.

When you report back, tell the human they can see the same records joined up with
`python3 .ai-sdlc/bin/sdlc.py view` (add `--serve` to keep it live). Do not run a
server on their behalf.

## Output

One table: area · finding · severity per `{{DOCS_DIR}}/process/04-quality-gates.md` ·
who can fix it. Then the two or three things worth doing first. If a section is clean,
say so explicitly — "no findings" is a result, and silence is not.

---
name: sdlc-doctor
description: Check the project's own SDLC documents for gaps, staleness, and drift before relying on them — blank charter commands, unticked roles with no reason, artifacts past their staleness window, backlog and worklog IDs that do not match, an oversized worklog, or a profile that disagrees with the charter. Use at the start of a session in an unfamiliar project, before a release, or when a document looks like it may not describe reality.
---

# Doctor — is this project's paperwork still true?

Every rule in this kit assumes the documents describe reality. When they stop doing so,
nothing announces it: a blank check command reads as "no such stage", a two-year-old
architecture document reads as current, and an agent proceeds confidently on both.

Run `/sdlc-doctor` for the full audit. This skill is the short version, for the moments
where the answer changes what you are about to do.

## Check before you rely on it

`python3 .ai-sdlc/bin/sdlc.py doctor` checks 0, 1, 3, 4 and 5 below mechanically, in about
a second. Run it and read its findings instead of reading the tables yourself. Check 2,
about the specific artifact you are about to trust, stays with you.

0. **Is anything pointing at the contract?** Nothing here runs unless a file the agent
   tool actually loads says to read `AGENTS.md` — `CLAUDE.md`, `GEMINI.md`, `AGENT.md`,
   `.github/copilot-instructions.md`, `.cursor/rules/`, and so on. If none does, the kit
   is installed and inert, and nothing about the repository looks wrong. That is the
   first thing to report and the cheapest thing to fix.
1. **The charter first.** `{{DOCS_DIR}}/project/charter.md` — is `last-reviewed` inside
   the staleness window it names? Are the Commands rows you are about to use filled in?
   **A blank cell is *Unknown*, not "absent"** (`{{DOCS_DIR}}/process/06-evidence-and-claims.md`),
   and guessing a command because the charter was blank is how a false "verified" gets
   written.
2. **The artifact you are about to trust.** Its frontmatter `last-reviewed` and `status`.
   `status: stale` is a legitimate state and a useful one — read it as "verify before
   relying on this", not as "ignore".
3. **The roles.** An unticked role with an empty reason means nobody decided. If your
   change touches that role's surface, that is a question for a human, not a permission.
4. **Modes.** `Default effort mode` is exactly Lean, Normal, or Beast; `Acquisition
   profile` is exactly Standard or Advanced. A row still listing every option is
   undecided and the default (Normal / Standard) applies — a question, not an error. A legacy `Operating mode: Beast mode` is
   ambiguous and needs a human migration decision.
5. **The profile.** If `.ai-sdlc/profile.json` disagrees with the charter, **the charter
   wins** — a human maintains it and the profile is derived. Report the drift.

## What to do with a finding

- **Fix what is mechanically fixable** in the same change: a stale date you can verify, a
  missing worklog entry for work that is plainly done, a profile row that drifted.
- **Never invent the answer.** A blank approver, an undecided role, an unwritten check
  command: mark it, log it in `{{DOCS_DIR}}/project/assumptions-and-risks.md`, and say who
  can settle it.
- **Marking a document stale beats leaving a confident wrong one** — but the marking needs
  a backlog item, or it is just a label.

## The one that grows quietly

Check the size of `{{DOCS_DIR}}/project/worklog.md`. Past the rotation threshold in
`{{DOCS_DIR}}/process/07-traceability.md`, rotate closed entries into
`worklog-archive/`. Nobody notices this until the worklog is the largest file every
future session reads.

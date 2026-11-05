---
description: Check prose for the phrasings that read as machine-written, and rewrite them
argument-hint: "[strict] [a file, a directory, or pasted text; default: changed prose files]"
---

Apply the slop filter to:

$ARGUMENTS

(With no argument, the prose files changed against `HEAD`. If the first word is `strict`,
apply strict rules for this run whatever the charter says.)

1. **Find the mode.** Read the **Slop filter** row in `{{DOCS_DIR}}/project/charter.md`:
   `off`, `on` or `strict`. The word `strict` in the arguments wins for this run.

2. **Scan.** Run `python3 .ai-sdlc/bin/sdlc.py slop <paths>`, adding `--strict` for a
   strict run, and quote its output. For pasted text, write it to a scratch file or pipe
   it with `sdlc.py slop -`. The scanner lists each mechanical tell by line with a fix.

3. **Read the text yourself.** Follow the `sdlc-slop-filter` skill if this project has it.
   If it does not, `python3 .ai-sdlc/bin/sdlc.py slop --guide` prints the rules. Then look
   for what no scanner sees: slogan closers, arguments with nobody, paragraphs of equal
   length, cycled synonyms, stacked hedges, text that describes itself.

4. **Rewrite.** Keep every supported claim and add none. Leave code, commands, paths,
   quotes, legal text and link targets untouched. Match a voice sample or house style when
   one exists; it outranks the patterns. Edit files in place when paths were given, and
   return the rewrite in the response when text was pasted.

5. **Scan again** and report: what changed, what was left and why, what was not checked,
   and the scanner's last line. On a strict run the work is not done while the scanner
   still fails a file. If a finding is a deliberate exception, mark the line `slop-ok`
   and name it in the report.

To change the project's setting: `python3 .ai-sdlc/bin/sdlc.py config --slop-filter
off|on|strict`. A match shows where to look, never who wrote the text, so do not report
that anything "is AI-generated".

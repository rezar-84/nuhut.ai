#!/usr/bin/env python3
"""
Install the Nuhut doc kit into a project.

    ./install.sh <target-project-dir> [PREFIX] [options]
    python3 install.py <target-project-dir> [PREFIX] [options]

Run with a terminal, it opens a guided setup: what the project is, what you are building
(several answers allowed), what the repository already contains, and the handful of facts
that decide which roles review the work and which skills are installed. Every question has
a default, `b` goes back, and the review screen at the end lets you jump to any answer
before a single file is written.

Copies AGENTS.md to the project root, docs/ into the project, the slash commands into
.claude/commands/ and the selected skills into .claude/skills/, substituting
{{PROJECT_NAME}}, {{PREFIX}}, {{DOCS_DIR}} and {{KIT_VERSION}}. It never overwrites an
existing file unless --upgrade is given, and --upgrade only ever refreshes the portable
standards -- project records are never rewritten.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

SRC = Path(__file__).resolve().parent
VERSION = (SRC / "VERSION").read_text(encoding="utf-8").strip()
MANIFEST_REL = Path(".ai-sdlc") / "manifest.json"
PROFILE_REL = Path(".ai-sdlc") / "profile.json"
# Retired in 4.0: the static status page. `sdlc.py view --export-html` replaces it.
RETIRED_DOCS = ("dashboard.html",)
RETIRED_STATE = "dashboard-state.js"
# The mechanical half of /sdlc-doctor and /sdlc-verify. Kit-managed: --upgrade refreshes it.
RUNTIME_REL = ".ai-sdlc/bin/sdlc.py"
# Everything under optional/runtime/, installed side by side in .ai-sdlc/bin/.
RUNTIME_FILES = ("sdlc.py", "view.py", "view.html")

# Writing direction is derived from the language tag, never asked: a project that lists
# `fa` is right-to-left whether or not anyone remembered to say so.
RTL_LANGS = {"ar", "arc", "ckb", "dv", "fa", "he", "ps", "sd", "ug", "ur", "yi"}

# ---------------------------------------------------------------- messages
# Every user-facing string lives here so a locale can replace it. `--lang xx` loads
# optional/locales/xx.json and falls back to English per key, so a partial translation is
# usable rather than broken.

EN = {
    "intro.title": "Nuhut kit v{version} -- guided setup",
    "intro.what": "Installs the operating contract your AI coding tools follow: AGENTS.md, docs/,\n  slash commands and skills, tailored to what you are building.",
    "intro.keys1": "Enter = take the value in [brackets]   ? = explain this question   b = back",
    "intro.keys2": "-  = leave blank   s = defaults for this section   S = defaults for everything   q = quit",
    "intro.keys3": "Nothing is written until you confirm at the review screen.",
    "sec.mode": "Setup",
    "sec.tools": "Your AI tools",
    "q.mode": "How do you want to set this up?",
    "h.mode": "Use these settings asks only what cannot be detected (a one-line description, the prefix, what you are building and which AI tools you use) and then shows every answer on the review screen, where any of them can still be changed. Customise lets you pick which sections to go through. Every question walks all ten sections. Nothing is written until you confirm the review screen in every case.",
    "progress": "{n} of {total}",
    "recommended": "(recommended)",
    "err.choice": "type a number from 1 to {max}, or the option's name",
    "q.other": "Type it",
    "none.option": "None",
    "none.word": "none",
    "q.harness": "Which AI coding tools will work in this repository? e.g. 1,2",
    "h.harness": "Every tool reads its own instruction file. Each one ticked gets a short pointer to AGENTS.md (an existing file is appended to, never overwritten); without one the tool never sees the kit. Tools already found in the repository are pre-ticked.",
    "l.harness": "AI tools",
    "q.preset": "How do you work?",
    "h.preset": "Sets the defaults for effort, decision style, development method and tier rules together. Full setup still lets you change each one; they are all rows in the charter afterwards.",
    "l.preset": "Working style",
    "q.tier": "Tier rules",
    "h.tier": "Every change gets a risk tier (1 = high blast radius ... 3 = trivial). Standard keeps low-risk changes light; Strict keeps the heavier 3.x records for every tier. Tier 1 always stops for a named human either way.",
    "l.tier": "Tier rules",
    "q.profile": "How much process documentation should the agent read?",
    "h.profile": "Compact installs the operating card, roles, templates and records, but not the numbered process/ documents. Same rules from one source -- for a small context window or a weaker model.",
    "l.profile": "Docs size",
    "q.enforce": "Enforce the rules mechanically?",
    "h.enforce": "Off by default. Agent hooks (Claude Code; also Gemini CLI and Cursor when wired) deny a commit with no work item ID or with a credential, a write holding a credential, and edits to paths in .ai-sdlc/protected.txt. Git hooks apply to every tool and every human: pre-commit refuses staged credentials, commit-msg refuses a message without an ID. Existing hooks are chained, never replaced.",
    "l.enforce": "Enforcement",
    "q.git_tools": "Should the kit's own tools (.ai-sdlc/) be committed?",
    "q.scaffold_tests": "Write a starter test plan from the detected test tooling?",
    "h.scaffold_tests": "Creates docs/project/test-plan.md and .ai-sdlc/testing-profile.json, both marked as detected and needing confirmation. Never installs a dependency.",
    "l.scaffold_tests": "Starter test plan",
    "q.scaffold_ci": "Write a starter CI workflow?",
    "h.scaffold_ci": "Built from the check commands above. Jobs are manual-only until you confirm the commands and enable push or pull-request triggers. Refused if there are no commands.",
    "l.scaffold_ci": "Starter CI",
    "review.command": "Same install choices without questions (charter answers stay in the charter):",
    "sec.dest": "Destination",
    "sec.project": "Project",
    "sec.build": "What you are building",
    "sec.stack": "Stack",
    "sec.cmds": "Check commands",
    "sec.arch": "Architecture",
    "sec.lang": "Languages and content",
    "sec.process": "Process and risk",
    "sec.standards": "Standards",
    "sec.install": "What to install",

    "q.dest": "Which project directory should this be installed into?",
    "h.dest": "The project you are installing the kit into. Never this kit's own directory.",
    "q.create": "{path} does not exist. Create it?",
    "q.name": "Project name",
    "q.what": "What is it, in one sentence",
    "h.what": "One line a stranger would understand. It becomes the charter's 'What it is'.",
    "q.prefix": "Work item prefix",
    "h.prefix": "2-4 letters. Every branch, commit, review and worklog entry carries it.",
    "q.owner": "Accountable human",
    "h.owner": "The person who approves Tier 1 work. A name, not a team.",
    "q.repo": "Repository",
    "q.types": "What kind of project is this? Choose all that apply, e.g. 1,3",
    "h.types": "Most projects are more than one. The selection decides which roles review your work.",
    "q.facts": "Use these? (y = yes, e = change some)",
    "q.ui": "Is there any interface at all (a CLI counts)?",
    "q.visual": "Is any of it visual (screens, pages, components)?",
    "q.public": "Is any of it publicly discoverable (search, social)?",
    "q.deploys": "Does it deploy to or run somewhere you operate?",
    "q.pii": "Does it hold or process personal data?",
    "q.conv": "Is there a conversion or activation goal to optimise?",
    "q.stack_ok": "Use these? (y = yes, e = change some, n = leave the table blank)",
    "q.cmds_ok": "Use these? (y = yes, e = change some, n = leave the table blank)",
    "q.lang": "Language / runtime",
    "q.pm": "Package manager",
    "q.fw": "Framework(s)",
    "q.db": "Data store(s)",
    "q.auth": "Auth",
    "q.host": "Hosting",
    "q.ci": "CI",
    "q.test": "Test tooling",
    "q.c_install": "Install",
    "q.c_run": "Run locally",
    "q.c_format": "checks.format",
    "q.c_lint": "checks.lint",
    "q.c_typecheck": "checks.typecheck",
    "q.c_unit": "checks.unit",
    "q.c_integration": "checks.integration",
    "q.c_contract": "checks.contract",
    "q.c_build": "checks.build",
    "q.c_scan": "checks.scan",
    "q.c_a11y": "checks.a11y",
    "q.c_e2e": "checks.e2e",
    "q.c_infra": "checks.infra",
    "q.c_data": "checks.data",
    "q.c_eval": "checks.eval",
    "q.c_perf": "checks.perf",
    "q.c_complexity": "checks.complexity",
    "q.c_mutation": "checks.mutation",
    "q.shape": "How is it deployed?",
    "h.shape": "Goes into architecture.md as the Shape section. Detection can list the parts, not how they run.",
    "q.critical": "What must never go down, or never lose data?",
    "h.critical": "The part whose failure is an incident rather than an inconvenience.",
    "q.expensive": "Which decision here would be expensive to reverse later?",
    "h.expensive": "Becomes a Known limitation, and usually the first ADR worth writing.",
    "q.multilingual": "Does it ship in more than one language?",
    "q.languages": "Languages, source language first",
    "h.languages": "Comma-separated BCP-47 tags, e.g. en, fa, tr. The first is the source of truth.",
    "q.catalog": "Where the translatable strings live",
    "h.catalog": "The message catalogue path, e.g. locales/ or messages/. Blank if there is none yet.",
    "q.translation": "How translation happens",
    "h.translation": "Who translates, whether machine translation is used, and who reviews it before users see it.",
    "q.glossary": "Where terminology is decided",
    "q.branch": "Default branch",
    "q.direct": "Are direct commits to {branch} allowed?",
    "q.approvers": "Approver(s) for Tier 1 work",
    "h.approvers": "Named humans. Tier 1 needs two approvals.",
    "q.staleness": "Treat project docs as stale after",
    "q.effort": "Default effort mode",
    "h.effort": "Lean minimizes optional work, Normal is balanced, Beast maximizes investigation and verification. Risk-tier requirements never change.",
    "q.acquisition": "Acquisition profile",
    "q.devmethod": "Development method",
    "h.devmethod": "Item runs one work item at a time and stops at each one's approvals. Epic plans several items together, gets one approval for the plan, and stops at the checkpoints it chooses. Checks, reviews and tier approvals never change.",
    "q.decision": "Decision style -- how much the agent decides for you",
    "h.decision": "How much the agent decides for you. Ask puts every material choice to you with options and trade-offs. Guide recommends in plain language and asks. Autopilot takes the recommended option and logs it for review. Tier 1 surfaces and gated commands always stop for a named human, in every style.",
    "h.acquisition": "Advanced enables more extraction techniques on authorized targets. It never grants permission to bypass access controls.",
    "q.approval": "Human approval required for",
    "q.forbidden": "Forbidden in this project",
    "h.forbidden": "The specific shortcuts that would be tempting here. Blank = fill in later.",
    "q.deploy": "Where does it deploy? Numbers, comma-separated, 0 = none",
    "h.deploy": "Each choice installs that platform's checklist into platforms/. Detected ones are pre-selected; pick Other for anything unlisted.",
    "q.platform": "Managed platform co-owning this repo",
    "h.platform": "An AI app builder or cloud IDE that also edits, syncs, or deploys this repo.",
    "q.a11y": "Accessibility target",
    "q.outcome": "Primary outcome success is measured by",
    "h.outcome": "The one user action: sign-up, activation, task completion, purchase.",
    "q.access_model": "How is access controlled?",
    "h.access_model": "Role-Based (RBAC), Simple Owner/User, Multi-tenant Workspace-Scoped, ABAC/ReBAC, or None (Public).",
    "q.mfa_policy": "Second factor (MFA / OTP)",
    "h.mfa_policy": "Optional / User-enabled, Enforced for Admin/Privileged only, Enforced for all users, or Not required.",
    "q.docsdir": "Install the docs under",

    "l.dest": "Destination",
    "l.name": "Project name",
    "l.what": "What it is",
    "l.prefix": "Work item prefix",
    "l.owner": "Accountable human",
    "l.repo": "Repository",
    "l.types": "Project types",
    "l.shape": "Deployment shape",
    "l.critical": "Must not fail",
    "l.expensive": "Expensive to reverse",
    "l.multilingual": "Ships in 2+ languages",
    "l.languages": "Languages",
    "l.catalog": "Message catalogue",
    "l.translation": "Translation workflow",
    "l.glossary": "Glossary",
    "l.branch": "Default branch",
    "l.direct": "Direct commits to it",
    "l.approvers": "Approvers",
    "l.staleness": "Docs stale after",
    "l.effort": "Default effort mode",
    "l.acquisition": "Acquisition profile",
    "l.devmethod": "Development method",
    "l.decision": "Decision style",
    "l.approval": "Human approval for",
    "l.forbidden": "Forbidden here",
    "l.platform": "Managed platform",
    "l.deploy": "Deployment platforms",
    "l.a11y": "Accessibility target",
    "l.outcome": "Primary outcome",
    "l.access_model": "Access level model",
    "l.mfa_policy": "MFA / OTP policy",
    "l.docsdir": "Docs directory",
    "l.commands": "Slash commands",
    "q.commands": "Install the {n} /sdlc-* slash commands (plan, build, verify, review, ...)?",
    "q.gitignore_tools": "Ignore AI SDLC runtime tools (.ai-sdlc/) in .gitignore?",
    "h.gitignore_tools": "Appends .ai-sdlc/ to the repository's .gitignore so runtime scripts, manifests, and local viewer caches are not committed to git.",
    "l.gitignore_tools": "Kit tools (.ai-sdlc/) in git",
    "q.skills": "Which skills should be installed? e.g. 1,2,5",
    "l.skills": "Skills",
    "q.skills.rich": "Which skills should be installed?",
    "q.types.rich": "What kind of project is this? Tick every one that applies",
    "q.deploy.rich": "Where does it deploy?",
    "q.harness.rich": "Which AI coding tools will work in this repository?",
    "q.pick.rich": "Which ones do you want to change?",
    "q.facts_pick": "Which of these are true? e.g. 1,4",
    "q.facts_pick.rich": "Which of these are true?",
    "h.facts_pick": "Each fact switches reviewer roles and skills on or off. They were worked out from the project types; tick or untick any of them.",
    "x.facts_pick": "ticked = true for this project",
    "l.facts_pick": "Facts",
    "q.facts.rich": "Use these facts?",
    "q.stack_ok.rich": "Use this stack?",
    "q.cmds_ok.rich": "Use these check commands?",
    "k.use": "Use these",
    "k.use_desc": "as listed above",
    "k.edit": "Change some",
    "k.edit_desc": "pick the rows to correct",
    "k.blank": "Leave blank",
    "k.blank_desc": "fill it in later in the charter",

    "hint.detected": "read from the repository -- confirm, do not assume:",
    "hint.cmds": "agents run these verbatim and report the result as evidence.\n  A wrong command here produces confidently false \"verified\" claims.",
    "hint.facts": "These answers decide which roles review your work:",
    "hint.skills": "Skills evaluated against your answers (installed to .claude/skills/):",
    "hint.arch": "found in the repository -- this seeds architecture.md:",
    "hint.i18n": "locales found in the repository: {locales}",
    "none.found": "(none found -- left blank)",
    "not.detected": "(not detected)",

    "err.answer_yn": "answer y or n (Enter = {default})",
    "err.answer_keys": "answer one of: {keys}",
    "err.number_range": "type numbers between 1 and {max}, e.g. 1,3",
    "err.prefix": "2-4 letters only, e.g. ACME",
    "err.required": "type a path, e.g. ~/Projects/my-app",
    "err.at_start": "already at the first question",
    "err.no_dir": "no such directory: {path}",
    "hint.create": "add --create to make it, or check the path",
    "err.is_kit": "refusing: that is the kit's own directory ({path}).",
    "err.in_kit": "refusing: {path} is inside the kit ({src}).",
    "err.kit_copy": "refusing: {path} is a copy of this kit, not a project to install into.",
    "err.give_project": "Give the project you want to install into: install.sh /path/to/your-project",
    "err.no_target": "a destination is required.",

    "review.title": "Review -- nothing has been written yet",
    "review.prompt": "Enter = write these files, a number = change that answer, f = list the files, q = quit",
    "review.quit": "Nothing was written.",
    "review.eof": "no answer -- nothing was written.",
    "review.bad": "type a number from the list, Enter to write, or q to quit",
    "skip.section": "-> rest of this section: defaults",
    "skip.all": "-> rest of the setup: defaults",
    "created": "created {path}",
    "reuse.docs": "an install already exists in {docs}/ -- reusing it; only missing files are added.",
    "exists.docs": "{docs}/ already exists and is not empty; existing files are never overwritten.",
    "keeping.docs": "keeping {docs}/",
    "bad.docs": "not a directory name -- keeping {docs}/",

    # -- the interactive widgets (install_ui.py); {up} {down} {left} {right} {dot} are glyphs
    "intro.rich": "Use {up} {down} and Enter. ? explains any question, {left} or b goes back, q quits.\n  Typed answers work too: a number picks that option.",
    "keys.select": "{up}{down} move {dot} enter choose {dot} ? explain {dot} {left} back {dot} q quit",
    "keys.multi": "{up}{down} move {dot} space tick {dot} a all {dot} n none {dot} / search {dot} enter confirm {dot} ? explain {dot} {left} back",
    "keys.confirm": "{left}{right} switch {dot} y / n {dot} enter confirm {dot} ? explain {dot} b back",
    "keys.text": "Enter keeps [the value shown] {dot} - leaves it blank {dot} ? explains {dot} b goes back",
    "multi.need_one": "tick at least one with space",
    "multi.no_match": "nothing matches -- backspace to widen the search",
    "yes": "Yes",
    "no": "No",
    "quit.confirm": "Quit without writing anything?",
    "cancelled": "Cancelled: nothing was written.",
    "cancelled.partial": "Interrupted while copying: the installation may be partial. It is safe to run again; existing files are never overwritten.",

    # -- the start screen: what was detected, and what would be set up
    "plan.title": "Here is what I found, and what I would set up",
    "plan.found": "Detected in {path}",
    "plan.name": "Project",
    "plan.types": "Building",
    "plan.tools": "AI tools",
    "plan.stack": "Stack",
    "plan.checks": "Check commands",
    "plan.checks_value": "{n} found: {names}",
    "plan.checks_none": "none found -- the charter will say Unknown until you add them",
    "plan.deploy": "Deploys to",
    "plan.platform": "Managed platform",
    "plan.style": "Working style",
    "plan.roles": "Reviewing roles",
    "plan.skills": "Skills",
    "plan.skills_value": "{n} of {total} match these answers",
    "plan.writes": "Will add",
    "plan.nothing": "nothing detected",
    "plan.existing": "An install is already here: only missing files would be added.",
    "plan.dest_first": "Answer where it goes first; then this shows what was detected there.",

    # -- customise
    "q.sections": "Which sections do you want to go through?",
    "h.sections": "Only the ticked sections are asked. Every other answer keeps the detected or recommended value shown at the start, and all of them are listed on the review screen, where any one can still be changed.",
    "l.sections": "Sections asked",
    "q.pick": "Which ones do you want to change? e.g. 2,5",
    "h.pick": "Only the rows you pick are asked; the others keep the value shown.",

    # -- the review screen and the files preview
    "review.rich_title": "Review -- nothing has been written yet",
    "review.rich_hint": "Pick a row to change it, or Write to install. Every value below came from your answers, detection, or a recommended default.",
    "review.write": "Write these files",
    "review.write_desc": "{new} new; existing files are never changed",
    "review.files": "Show the files",
    "review.files_desc": "every path it would add, before anything is written",
    "review.quit_opt": "Quit",
    "review.quit_desc": "write nothing",
    "review.change": "Change an answer",
    "files.title": "Files that would be written into {path}",
    "files.summary": "{new} new files. {kept} already exist and stay untouched.",
    "files.kept": "Already there, left as they are:",
    "files.more": "... and {n} more",
    "files.back": "Press Enter to go back to the review.",

    # -- after the install
    "outro.got": "What you got",
    "outro.later": "Still to fill in -- an agent reads a blank cell as Unknown, never as 'not applicable':",
    "outro.later_more": "... and {n} more rows in the same file",
    "q.viewer": "Open the live project viewer now? (Ctrl-C stops it)",
    "h.viewer": "Runs `.ai-sdlc/bin/sdlc.py view --serve`: a read-only page of the backlog, worklog, plans and reviews that updates as agents work. You can open it any time later with the same command.",

    # -- one line under every question, so nobody has to press ? to know what it wants
    "x.dest": "an existing project folder (~ works). The kit is copied into it.",
    "x.name": "used in the charter and AGENTS.md; the folder name is usually fine",
    "x.what": "e.g. An online shop for handmade rugs, with accounts and checkout",
    "x.prefix": "e.g. SHOP gives IDs like SHOP-12 in branches, commits and the backlog",
    "x.owner": "the one person who approves risky (Tier 1) changes, e.g. Jane Doe",
    "x.repo": "clone URL or path, e.g. github.com/acme/shop -- blank is fine",
    "x.types": "pick every kind that applies: it decides which reviewer roles and skills switch on",
    "x.facts_ok": "derived from the project types; each one switches reviewer roles on or off",
    "x.harness_pick": "each one ticked gets a small pointer file to AGENTS.md; tools found here are pre-ticked",
    "x.stack_ok": "agents treat this table as fact, so correct anything that is wrong",
    "x.cmds_ok": "agents run exactly these commands to prove a change works",
    "x.shape": "e.g. Next.js on Vercel, Postgres on Neon, a worker on Fly",
    "x.critical": "e.g. checkout and order history, or the nightly import",
    "x.expensive": "e.g. the database schema, or the public API's URL format",
    "x.multilingual": "if yes, the translation and right-to-left rules become binding",
    "x.languages": "e.g. en, fa, tr -- the first one is the source language",
    "x.catalog": "e.g. src/locales/ or messages/",
    "x.translation": "e.g. machine-translated, then reviewed by a native speaker",
    "x.glossary": "e.g. docs/glossary.md, or: the product owner decides",
    "x.branch": "where finished work lands, usually main",
    "x.direct": "No means every change goes through a branch first (recommended)",
    "x.approvers": "Tier 1 = hard-to-undo changes (auth, stored data, money, releases); two names",
    "x.staleness": "a project document older than this is re-checked before an agent trusts it",
    "x.preset": "one choice that sets the next four; you can still change each of them",
    "x.effort": "how much investigation and review beyond the required minimum",
    "x.devmethod": "Epic suits a feature made of several related changes",
    "x.decision": "for choices with trade-offs; risky changes always stop for you",
    "x.tier": "every change is sorted into a risk tier; this sets how much record each needs",
    "x.acquisition": "only matters for scrapers and crawlers",
    "x.approval": "the agent stops and asks before any of these; comma-separated",
    "x.forbidden": "e.g. no new dependency without an ADR; never edit generated/",
    "x.platform": "an app builder or cloud IDE that also commits to this repository",
    "x.deploy_targets": "each one ticked installs its deploy checklist; detected ones are pre-ticked",
    "x.a11y": "the standard every screen is reviewed against",
    "x.outcome": "e.g. a visitor completes sign-up, or an order is paid",
    "x.access_model": "how the product decides who may see or change what",
    "x.mfa_policy": "who must use a second factor (an app code or a key) to sign in",
    "x.docsdir": "a folder at the project root; docs is fine unless something else uses it",
    "x.profile": "Full is the safe choice; Compact suits small models and context windows",
    "x.commands": "typed commands in Claude Code; other tools get the same steps as skills",
    "x.enforce": "hooks refuse a bad commit outright instead of trusting the agent",
    "x.git_tools": "Commit suits teams: everyone runs the same checks",
    "x.scaffold_tests": "a draft from what was detected, marked for you to confirm",
    "x.scaffold_ci": "runs the check commands; manual-only until you switch triggers on",
    "x.skills_pick": "instructions an agent loads only when the situation fits; ticked ones match your answers",
    "x.sections": "the rest keep the settings shown above",

    # -- help for the questions that had none
    "h.name": "The human-readable name. It is written into the charter, AGENTS.md and every document title that names the project.",
    "h.repo": "Where the code lives, so an agent can link commits and pull requests. Blank is fine; the charter cell can be filled later.",
    "h.facts_ok": "Each fact switches reviewer roles and skills on or off: an interface brings UX and accessibility review, personal data brings privacy review, deploying brings DevOps review. Choose e to correct any of them.",
    "h.stack_ok": "This becomes the charter's stack table. Agents treat it as fact when choosing libraries and commands, so a wrong entry here leads to wrong code. Choose e to correct single rows, or n to leave the table blank for later.",
    "h.cmds_ok": "Agents run these exact commands and quote their output as evidence; only a command that ran can make a change Verified. A blank one is reported as not run, never as passing. Choose e to change single rows.",
    "h.multilingual": "Yes makes the content and translation process binding: a source language, a message catalogue, a translation workflow, and the localisation reviewer role.",
    "h.glossary": "Where product terms and their approved translations are decided, so every language uses the same words.",
    "h.branch": "The branch finished work is merged into. Agents never commit to it directly unless the next question allows it.",
    "h.direct": "No (recommended): every change is made on a branch and reaches the default branch after its checks. Yes: agents may commit to it directly, and the charter's 'Direct commits to it' row says so.",
    "h.staleness": "After this long without a review, an agent treats a project document as a hypothesis to re-check, not as fact. 90 days suits most projects.",
    "h.approval": "Actions the agent must stop and get a named human's approval for, whatever the tier. Mirrored into AGENTS.md under Project overrides.",
    "h.a11y": "The accessibility standard the accessibility reviewer holds every interface to. WCAG 2.2 AA is the common legal and practical baseline.",
    "h.docsdir": "The folder the process documents, roles, templates and project records go into. Use another name when docs/ already holds something else.",
    "h.commands": "Claude Code slash commands for each loop step: /sdlc-plan, /sdlc-build, /sdlc-verify, /sdlc-review, /sdlc-log and /sdlc-doctor. Other tools get the same steps as skills when you pick them above.",
    "h.skills_pick": "A skill is a short instruction file an agent loads only when its situation arises, for example a privacy review when personal data is touched. Ticked skills match your answers; tick or untick any. They install to .claude/skills/ and, for other tools, .agents/skills/.",
    "h.git_tools": "The .ai-sdlc/ folder holds the kit's runtime (sdlc.py), its manifest and the evidence ledger. Commit it so everyone runs the same checks; ignore it only for a personal experiment.",

    # -- install.sh --explain <topic>
    "explain.tiers": """Risk tiers -- how heavy the process is for one change

Every change is sorted by blast radius and reversibility, not by topic:

  Tier 1  changes a contract others consume, stored data, auth, money-movement
          rules or a release pipeline, or is hard to undo. The agent plans, gets a
          design and a ship review (one from a different model family), writes an
          ADR, and stops for a named human's approval.
  Tier 2  new or changed behaviour that tests cover and a revert undoes. A short
          plan, tests, a worklog line, and a commit as the charter says.
  Tier 3  a typo, a test, a patch bump. The commit message is the record.

Tier rules: Standard keeps Tier 2 and 3 light. Strict keeps the 3.x rules, where
every tier writes the full record. Change it later in the charter's Tier rules row.
Flag: --tier-rules standard|strict""",
    "explain.presets": """Presets -- four settings in one choice

  solo       one person moving fast: Lean effort, Guide decisions, Item method,
             Standard tiers
  team       several people, normal depth (the default): Normal, Guide, Item,
             Standard
  regulated  audited or high-stakes work: Normal effort, every material choice
             asked (Ask), Item, Strict tiers

A flag given as well always wins: --preset solo --decision-style ask. Every value
is a charter row afterwards and can be edited there.
Flag: --preset solo|team|regulated   Values: install.sh --list presets""",
    "explain.effort": """Effort mode -- how far beyond the minimum the agent goes

  Lean    the least optional work: fastest and cheapest
  Normal  balanced investigation and review (default)
  Beast   maximum investigation and verification; slowest

It changes breadth above the risk-tier floor, never the floor itself: a Tier 1
change gets its reviews and approval in every mode. A single request can ask for
another mode ("do this one in Beast").
Flag: --effort-mode lean|normal|beast""",
    "explain.decision": """Decision style -- how much the agent decides for you

  Ask        every material choice is put to you, with options and trade-offs
  Guide      the agent recommends in plain language, then asks (default)
  Autopilot  it takes the recommended option and logs it for your review

In every style, Tier 1 surfaces and gated commands stop for a named human, and
no record is thinned. Development method is separate: Item works one item at a
time; Epic plans several items together with one plan approval.
Flags: --decision-style ask|guide|autopilot   --dev-method item|epic""",
    "explain.hooks": """Enforcement -- rules the tools refuse to break, not just promise

  Agent hooks (--hooks)  Claude Code (and Gemini CLI, Cursor when wired) refuses a
                         commit with no work item ID or with a credential, a file
                         write that holds a credential, and edits to paths listed in
                         .ai-sdlc/protected.txt.
  Git hooks (--git-hooks) git itself refuses staged credentials (pre-commit) and a
                         commit message without an ID (commit-msg), for every tool
                         and every human. --git-hooks secrets installs only the first.

Both are off by default, stay silent unless they refuse something, and chain onto
hooks you already have instead of replacing them.""",
    "explain.profile": """Docs profile -- how much an agent reads per change

  Full     every process document; about 22k tokens of reading for a Tier 2 change
  Compact  the one-page card instead of the numbered process documents; about 8k

Both carry the same rules from one source. Choose Compact for a small context
window or a weaker model; a Tier 1 change then has no longer document to consult.
Flag: --profile full|compact""",
    "explain.skills": """Skills -- instructions loaded only when they apply

A skill is a short file an agent reads when its situation arises: sdlc-intake on
every request, sdlc-privacy-review when personal data is touched, sdlc-release
when something deploys. The guided setup ticks the ones your answers call for;
you can tick or untick any. They install to .claude/skills/, and to
.agents/skills/ when another AI tool is wired.
See every skill and its condition: install.sh --list skills   Flag: --no-skills""",
    "explain.roles": """Roles -- who reviews the work

Role playbooks are reviews an agent runs from a specialist's point of view.
Four are always on: product-manager, architect, security, qa. Your answers switch
on the rest: an interface adds ux-designer and accessibility, a visual one adds
brand-designer, public pages add seo and copywriter, a conversion goal adds
cro-analyst, personal data adds privacy-legal, deploying adds devops-sre, data or
scraping adds data-engineer, models add ml-engineer, a backend, data or model
workload adds performance-engineer, and several languages add localisation.
The roster is a table in the charter and can be edited there.""",
    "explain.charter": """The charter -- the project's facts, in one file

docs/project/charter.md holds what an agent cannot guess: what the project is, the
work item prefix, the stack, the exact check commands, who approves Tier 1 work,
what is forbidden, the working style, and which roles review. The guided setup
fills in what it can; everything else stays blank on purpose, and an agent reads
a blank cell as Unknown rather than 'not applicable'. Edit it like any document.""",
    "explain.harnesses": """AI tools -- making each one read the kit

Every AI coding tool reads its own instruction file. The installer adds a short
pointer to AGENTS.md in each one you pick (CLAUDE.md, .cursor/rules/agents.mdc,
.github/copilot-instructions.md, GEMINI.md, ...). An existing file is appended
to, never overwritten. Codex, Jules, Zed, Factory, opencode and Antigravity read
AGENTS.md directly and need nothing.
Flag: --harness claude,cursor,...   Values: install.sh --list harnesses""",
}

_CATALOG = {}


def t(key, **kw):
    s = _CATALOG.get(key) or EN.get(key) or key
    try:
        return s.format(**kw) if kw else s
    except (KeyError, IndexError):
        return s


def load_locale(code):
    """A locale replaces the strings it has; anything missing stays English."""
    if not code or code == "en":
        return
    path = SRC / "optional" / "locales" / (code + ".json")
    if not path.exists():
        sys.stderr.write("no locale catalogue for %s (%s) -- using English\n" % (code, path))
        return
    try:
        _CATALOG.update(json.loads(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        sys.stderr.write("locale %s is not valid JSON (%s) -- using English\n" % (code, exc))


# ---------------------------------------------------------------- terminal

# The widgets and the Term that prints them live in install_ui.py, next to this file.
sys.path.insert(0, str(SRC))
import install_ui as ui                                # noqa: E402
from install_ui import Term                            # noqa: E402,F401  (re-exported)

TERM = Term()


# ---------------------------------------------------------------- arguments

USAGE = """usage: install.sh [target-project-dir] [PREFIX] [options]

Installs the Nuhut operating contract (AGENTS.md, docs/, slash commands, skills) into
a project. Run it with no options in a terminal for a guided setup that explains every
choice; nothing is written until you confirm the review screen.

Examples
  ./install.sh                                   guided setup: arrow keys, Enter, ? explains
  ./install.sh ~/code/shop SHOP --quick          use what it detects, ask ~4 things
  ./install.sh ~/code/shop --sections process    ask only the sections you name
  ./install.sh ~/code/shop SHOP -y --harness claude,cursor --deploy vercel
                                                 no questions (CI, scripts)
  ./install.sh ~/code/shop SHOP --upgrade        refresh the kit's managed files later

Where and who
  PREFIX                 2-4 letters every work item ID carries, e.g. SHOP-12
  --create               create the target directory if it does not exist
  --docs-dir <name>      install the docs somewhere other than docs/
  --quick | --full       guided setup: detected settings, or every question
  --sections <list>      ask only these sections, e.g. process,install (--list sections)

How the agent works  (all project defaults, changeable later in the charter)
  --preset <name>        solo | team | regulated -- sets the four below together
  --effort-mode <name>   lean | normal | beast   -- how deep it investigates
  --decision-style <n>   ask | guide | autopilot -- how much it decides for you
  --dev-method <name>    item | epic             -- one work item, or a planned group
  --tier-rules <name>    standard | strict       -- how heavy each risk tier is
  --independent-review   none | tier1 | tier1-2  -- when a second model family is required

Which AI tools read it
  --harness <list>       claude, cursor, copilot, gemini, windsurf, cline, roo, amp,
                         aider, or all (default: claude). Codex, Jules, Zed, Factory,
                         opencode and Antigravity read AGENTS.md and need nothing.

Enforcement  (off unless asked for)
  --hooks                Claude Code hooks that refuse unsafe commits and edits
  --git-hooks [secrets]  git hooks every agent and human inherits

What gets installed
  --deploy <list>        platform checklists, e.g. vercel,cloudflare-edge (or none)
  --profile <name>       full (default) | compact -- shorter docs for small models
  --no-skills            no skills in .claude/skills/
  --scaffold-tests       a starter test plan from the detected tooling
  --scaffold-ci <p>      a starter CI workflow: github | gitlab
  --gitignore-tools      keep .ai-sdlc/ out of git via .gitignore
  --git-exclude          ... or via .git/info/exclude (local only)
  --acquisition-profile  standard | advanced -- for scrapers and crawlers

Running it
  -y, --yes              no questions, every default (implied without a terminal)
  --dry-run              list what would be written, write nothing
  --upgrade [--adopt]    refresh managed files; --adopt once for pre-3.3 installs
  --plain                numbered, typed prompts instead of arrow-key menus
  --lang <code>          language for these prompts (default: en)

More
  --help full            every option in detail
  --list <what>          harnesses | platforms | presets | types | skills | sections
  --explain <topic>      tiers | presets | effort | decision | hooks | profile |
                         skills | roles | charter | harnesses -- what each means
"""

USAGE_FULL = """usage: install.sh <target-project-dir> [PREFIX] [options]

  target dir    the project to install into -- required, and never this directory.
                Omit it only when a terminal is attached, and setup will ask for it.
  PREFIX        2-4 letters for work item IDs, e.g. ACME

  --docs-dir <name>  install the docs under a different directory (default: docs)
  --create           create the target directory if it does not exist
  --quick            guided setup, essentials only: where, name, prefix, project
                     types, AI tools, working style, deploy platforms. Everything
                     else takes its default and is shown on the review screen.
  --full             guided setup, every question. Without either flag the setup
                     shows what it detected and asks which one you want.
  --sections <list>  guided setup, asking only the named sections (comma-separated):
                     project, build, tools, stack, cmds, arch, lang, process,
                     standards, install. The rest take their defaults.
  --plain            numbered, typed prompts instead of arrow-key menus. Also chosen
                     automatically without a terminal, with TERM=dumb, or with
                     NUHUT_PLAIN=1 set -- for screen readers and logs.
  --explain <topic>  print what a concept means and how to choose, then exit:
                     tiers, presets, effort, decision, hooks, profile, skills, roles,
                     charter or harnesses.
  --list <what>      print the valid values with their meaning: harnesses,
                     platforms, presets, types or skills.
  -y, --yes          no questions: take every default (also implied when stdin is not a
                     terminal, so CI and piped runs never hang)
  --no-skills        do not install anything into .claude/skills/
  --scaffold-tests   create a detected project test plan and machine-readable profile
  --scaffold-ci <provider>
                     create CI for github or gitlab from detected quality commands
  --hooks            install the opt-in Claude Code hooks: deny a commit with no work
                     item ID or with a credential in it, a file write that holds a
                     credential (and a warning for personal data in a record), an edit to a path in
                     .ai-sdlc/protected.txt or to a test locked in
                     .ai-sdlc/test-lock.txt, and a command matching
                     .ai-sdlc/gates.txt. Merged into .claude/settings.json without
                     touching anything already there. Needs jq at runtime; without it
                     the hooks allow the call and say so. Never implied by another flag.
                     With --harness gemini the same six rules are merged into
                     .gemini/settings.json, and with --harness cursor the three
                     shell rules into .cursor/hooks.json, through
                     .claude/hooks/adapter.sh.
  --git-hooks [all|secrets]
                     install the opt-in git hooks, which every agent and every human
                     inherit from git itself: a pre-commit that refuses staged
                     credentials and a commit-msg that refuses a message with no work
                     item ID (`secrets` installs only the first). Scripts live in
                     .ai-sdlc/git-hooks/; the project's existing hook, husky file or
                     core.hooksPath directory gets a one-line call appended, never
                     replaced. With pre-commit.com or lefthook the entry to add is
                     printed instead. Never implied by another flag.
  --preset <name>    solo, team or regulated: sets effort mode, decision style,
                     development method and tier rules together (solo: lean, guide,
                     item, standard; team: normal, guide, item, standard; regulated:
                     normal, ask, item, strict). Any of those flags given as well wins.
                     New installs only; --upgrade keeps the project's charter.
  --tier-rules <standard|strict>
                     standard (default): tier by blast radius, Tier 3's record is the
                     commit, Tier 2 commits and continues. strict: the 3.x rules.
  --independent-review <none|tier1|tier1-2>
                     when a review from a different model family is required: tier1
                     (default), tier1-2, or none (single-agent / token-saving setup).
  --profile <name>   full (default) or compact. compact installs the operating card,
                     roles, templates and project records but omits the numbered
                     process/ documents: the same rules from one source, about 8k of
                     reading for a Tier 2 change instead of 22k. For a small context
                     window or a weaker model. A Tier 1 change then has no escalation
                     document to appeal to, so choose it deliberately.
  --effort-mode <name>
                     project default: lean, normal (default), or beast. This changes
                     solution and review depth, never the risk-tier safety floor.
  --dev-method <name>
                     project default: item (default) or epic. Epic plans several
                     work items together and stops at chosen checkpoints; every
                     item keeps its checks, reviews and tier approvals.
  --decision-style <name>
                     project default: ask, guide (default) or autopilot. How much the
                     agent decides for the person: it never lifts a Tier 1 stop or a
                     gated command, in any style (process/14-decision-style.md).
  --acquisition-profile <name>
                     standard (default) or advanced. Advanced enables additional data
                     acquisition techniques on authorized targets; it does not grant
                     permission to bypass authentication, CAPTCHA, or access controls.
  --deploy <list>    deployment platforms, comma-separated: cloudflare-workers,
                     cloudflare-edge, vercel, netlify, fly, railway, render, heroku,
                     dokploy, coolify, kamal, vps, kubernetes, aws, gcp, azure,
                     digitalocean, other, or none. Installs each one's checklist into
                     <docs>/platforms/ and records it in the charter. Without it the
                     wizard pre-selects what it detects; -y installs none, because
                     detection is not a decision.
  --harness <list>   comma-separated agent tools to wire up (default: claude). One of
                     claude, gemini, amp, copilot, cursor, windsurf, cline, roo, aider,
                     or "all". Each gets a pointer file naming AGENTS.md; an instruction
                     file that already exists is appended to, never overwritten. Naming
                     any tool other than claude also installs the chosen skills under
                     .agents/skills/, the cross-tool location of the Agent Skills
                     standard, beside the Claude Code copy. Codex,
                     Jules, Zed, Factory, opencode and Antigravity read AGENTS.md
                     directly and need nothing.
  --adopt            with --upgrade: take over kit files an older version left
                     unmanaged -- sections 1-8 of AGENTS.md and the /sdlc-* commands.
                     The previous copies are backed up first. Needed once per project
                     installed before 3.3; the upgrade says when.
  --gitignore-tools  append .ai-sdlc/ to the project's root .gitignore so kit
                     tools, runtime binaries, and local viewer state are ignored.
  --git-exclude      append .ai-sdlc/ to .git/info/exclude (local-only ignore:
                     leaves .gitignore untracked and clean for team repositories).
  --dry-run          list what would be written, write nothing
  --lang <code>      language for this setup's own prompts (default: en)
  --upgrade          refresh manifest-owned portable docs and installed skills. Stops
                     on local edits, backs up changes, removes obsolete managed files,
                     and never touches project records or AGENTS.md.
"""


class Options(object):
    def __init__(self):
        self.target = ""
        self.prefix = ""
        self.docs_dir = "docs"
        self.docs_dir_given = False
        self.upgrade = False
        self.assume_yes = False
        self.want_skills = True
        self.scaffold_tests = False
        self.scaffold_ci = ""
        self.create = False
        self.dry_run = False
        self.gitignore_tools = False
        self.git_exclude = False
        self.harnesses = None   # None: not given; [] : only native harnesses named
        self.profile = "full"
        self.profile_given = False
        self.mode = None            # None: ask; "quick", "custom" or "full"
        self.sections = None        # --sections: the section ids to ask, or None
        self.plain = False
        self.effort_mode = "normal"
        self.acquisition_profile = "standard"
        self.deploy = None          # None: not given; []: explicitly none
        self.adopt = False
        self.effort_given = False
        self.dev_method = "item"
        self.dev_method_given = False
        self.decision_style = "guide"
        self.decision_given = False
        self.acquisition_given = False
        self.hooks = False
        self.preset = ""
        self.tier_rules = "standard"
        self.tier_rules_given = False
        self.independent_review = "tier1"
        self.independent_review_given = False
        self.git_hooks = ""        # "", "all" or "secrets"
        self.native_harnesses = []
        self.lang = "en"


def usage(code=1, text=None):
    """--help prints to stdout; a usage error prints the short page to stderr."""
    (sys.stdout if code == 0 else sys.stderr).write(text or USAGE)
    sys.exit(code)


def bad_value(message, topic=None):
    """A wrong flag value: say what was wrong and where the valid values are, instead of
    burying the one useful line under the whole help page."""
    sys.stderr.write("error: %s\n" % message)
    if topic:
        sys.stderr.write("       see: install.sh --list %s\n" % topic)
    sys.stderr.write("       all options: install.sh --help\n")
    sys.exit(1)


LIST_TOPICS = ("harnesses", "platforms", "presets", "types", "skills", "sections")
SECTION_IDS = ("project", "build", "tools", "stack", "cmds", "arch", "lang", "process",
               "standards", "install")
EXPLAIN_TOPICS = ("tiers", "presets", "effort", "decision", "hooks", "profile", "skills",
                  "roles", "charter", "harnesses")


def print_list(topic):
    if topic == "harnesses":
        print("AI tools (--harness). Each gets a pointer file that names AGENTS.md:\n")
        for name in sorted(HARNESS_ALIASES):
            print("  %-10s %-24s %s" % (name, HARNESS_TITLES.get(name, name),
                                        ", ".join(HARNESS_ALIASES[name])))
        print("\nRead AGENTS.md directly, nothing to install: %s" % ", ".join(HARNESS_NATIVE))
    elif topic == "platforms":
        print("Deployment platforms (--deploy). Each installs a checklist in <docs>/platforms/:\n")
        for pid, label in DEPLOY_PLATFORMS:
            print("  %-20s %s" % (pid, label))
        print("  %-20s %s" % ("other", "anything unlisted -- recorded in the charter, no checklist"))
        print("  %-20s %s" % ("none", "nothing deployed from here"))
    elif topic == "presets":
        print("Presets (--preset). An explicit flag always wins over the preset:\n")
        print("  %-10s %-8s %-10s %-6s %s" % ("", "effort", "decision", "method", "tier rules"))
        for name in ("solo", "team", "regulated"):
            p = PRESETS[name]
            print("  %-10s %-8s %-10s %-6s %s" % (name, p["effort_mode"], p["decision_style"],
                                                  p["dev_method"], p["tier_rules"]))
        print("")
        for name in ("solo", "team", "regulated"):
            print("  %-10s %s" % (name, PRESET_HELP[name]))
    elif topic == "types":
        print("Project types (asked by the guided setup; several can apply):\n")
        for i, label in enumerate(PROJECT_TYPES, 1):
            facts = ", ".join(TYPE_FACTS.get(i, ())) or "-"
            print("  %2d  %-52s %s" % (i, label, facts))
        print("\nThe facts on the right decide which roles review the work and which skills install.")
    elif topic == "sections":
        print("Sections of the guided setup (--sections). The ones not named take defaults:\n")
        for sid in SECTION_IDS:
            print("  %-10s %s" % (sid, t("sec." + sid)))
    elif topic == "skills":
        print("Skills (installed to .claude/skills/ when their condition holds):\n")
        for name, rule, why_on, _ in SKILL_RULES:
            print("  %-26s %-14s %s" % (name, rule, why_on))
    sys.exit(0)


def parse_args(argv):
    o = Options()
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            if i + 1 < len(argv) and argv[i + 1] in ("full", "all"):
                usage(0, USAGE_FULL)
            usage(0)
        elif arg == "--list":
            if i + 1 >= len(argv) or argv[i + 1] not in LIST_TOPICS:
                bad_value("--list needs one of: %s" % ", ".join(LIST_TOPICS))
            print_list(argv[i + 1])
        elif arg in ("--quick", "--full"):
            o.mode = arg[2:]
        elif arg == "--plain":
            o.plain = True
        elif arg == "--sections":
            names = argv[i + 1].split(",") if i + 1 < len(argv) else []
            bad = [n for n in names if n.strip() not in SECTION_IDS]
            if not names or bad:
                bad_value("--sections takes a comma-separated list of: %s"
                          % ", ".join(SECTION_IDS))
            o.sections, o.mode = ["sec." + n.strip() for n in names], "custom"
            i += 1
        elif arg == "--explain":
            if i + 1 >= len(argv) or argv[i + 1] not in EXPLAIN_TOPICS:
                bad_value("--explain needs one of: %s" % ", ".join(EXPLAIN_TOPICS))
            print(t("explain." + argv[i + 1]))
            sys.exit(0)
        elif arg == "--docs-dir":
            if i + 1 >= len(argv):
                bad_value("--docs-dir needs a directory name")
            o.docs_dir, o.docs_dir_given = argv[i + 1], True
            i += 1
        elif arg == "--lang":
            if i + 1 >= len(argv):
                bad_value("--lang needs a language code, e.g. tr")
            o.lang = argv[i + 1]
            i += 1
        elif arg == "--upgrade":
            o.upgrade = True
        elif arg == "--adopt":
            o.adopt = True
        elif arg in ("-y", "--yes", "--non-interactive"):
            o.assume_yes = True
        elif arg == "--no-skills":
            o.want_skills = False
        elif arg == "--scaffold-tests":
            o.scaffold_tests = True
        elif arg == "--scaffold-ci":
            if i + 1 >= len(argv) or argv[i + 1] not in ("github", "gitlab"):
                bad_value("--scaffold-ci requires github or gitlab")
            o.scaffold_ci = argv[i + 1]
            i += 1
        elif arg == "--hooks":
            o.hooks = True
        elif arg == "--git-hooks":
            o.git_hooks = "all"
            if i + 1 < len(argv) and argv[i + 1] in ("all", "secrets"):
                o.git_hooks = argv[i + 1]
                i += 1
        elif arg == "--profile":
            if i + 1 >= len(argv) or argv[i + 1] not in ("full", "compact"):
                bad_value("--profile requires full or compact")
            o.profile, o.profile_given = argv[i + 1], True
            i += 1
        elif arg == "--effort-mode":
            if i + 1 >= len(argv) or argv[i + 1] not in ("lean", "normal", "beast"):
                bad_value("--effort-mode requires lean, normal, or beast")
            o.effort_mode, o.effort_given = argv[i + 1], True
            i += 1
        elif arg == "--dev-method":
            if i + 1 >= len(argv) or argv[i + 1] not in ("item", "epic"):
                bad_value("--dev-method requires item or epic")
            o.dev_method, o.dev_method_given = argv[i + 1], True
            i += 1
        elif arg == "--decision-style":
            if i + 1 >= len(argv) or argv[i + 1] not in ("ask", "guide", "autopilot"):
                bad_value("--decision-style requires ask, guide, or autopilot")
            o.decision_style, o.decision_given = argv[i + 1], True
            i += 1
        elif arg == "--preset":
            if i + 1 >= len(argv) or argv[i + 1] not in PRESETS:
                bad_value("--preset requires one of %s" % ", ".join(sorted(PRESETS)), "presets")
            o.preset = argv[i + 1]
            i += 1
        elif arg == "--tier-rules":
            if i + 1 >= len(argv) or argv[i + 1] not in ("standard", "strict"):
                bad_value("--tier-rules requires standard or strict")
            o.tier_rules, o.tier_rules_given = argv[i + 1], True
            i += 1
        elif arg == "--independent-review":
            if i + 1 >= len(argv) or argv[i + 1] not in ("none", "off", "tier1", "tier1-2"):
                bad_value("--independent-review requires none, tier1, or tier1-2")
            o.independent_review = "none" if argv[i + 1] == "off" else argv[i + 1]
            o.independent_review_given = True
            i += 1
        elif arg == "--acquisition-profile":
            if i + 1 >= len(argv) or argv[i + 1] not in ("standard", "advanced"):
                bad_value("--acquisition-profile requires standard or advanced")
            o.acquisition_profile, o.acquisition_given = argv[i + 1], True
            i += 1
        elif arg == "--deploy":
            if i + 1 >= len(argv):
                bad_value("--deploy requires a comma-separated list", "platforms")
            ids, bad = parse_deploy(argv[i + 1])
            if bad is not None:
                bad_value("unknown deployment platform: %s" % bad, "platforms")
            o.deploy = ids
            i += 1
        elif arg == "--harness":
            if i + 1 >= len(argv):
                bad_value("--harness requires a comma-separated list", "harnesses")
            names = [x.strip().lower() for x in argv[i + 1].split(",") if x.strip()]
            if "all" in names:
                names = sorted(HARNESS_ALIASES)
            native = [x for x in names if x in HARNESS_NATIVE]
            unknown = [x for x in names if x not in HARNESS_ALIASES and x not in HARNESS_NATIVE]
            if native:
                sys.stderr.write(
                    "%s reads AGENTS.md directly and needs no pointer file\n"
                    % ", ".join(native))
            if unknown:
                bad_value("unknown harness: %s" % ", ".join(unknown), "harnesses")
            o.harnesses = [x for x in names if x in HARNESS_ALIASES]
            o.native_harnesses = native
            i += 1
        elif arg == "--create":
            o.create = True
        elif arg == "--dry-run":
            o.dry_run = True
        elif arg == "--gitignore-tools":
            o.gitignore_tools = True
        elif arg == "--git-exclude":
            o.git_exclude = True
        elif arg.startswith("-"):
            bad_value("unknown option: %s" % arg)
        else:
            positional.append(arg)
        i += 1
    if len(positional) > 2:
        bad_value("unexpected argument: %s" % positional[2])
    if positional:
        o.target = positional[0]
    if len(positional) > 1:
        prefix = normalize_prefix(positional[1])
        if not prefix:
            sys.stderr.write("error: work item prefix %r: %s\n" % (positional[1], t("err.prefix")))
            sys.exit(2)
        o.prefix = prefix
    apply_preset(o)
    return o


# ---------------------------------------------------------------- detection
# All read-only and best-effort. Anything not established stays empty: the process reads
# a blank cell as Unknown, which is recoverable, while a wrong check command produces
# confidently false "verified" claims, which is not.

LOCALE_DIRS = ("locales", "messages", "public/locales", "src/locales", "src/i18n",
               "i18n", "app/locales", "config/locales", "lang", "translations",
               "src/messages", "content/i18n")
LOCALE_RE = re.compile(r"^([a-z]{2,3})(?:[-_]([A-Za-z]{2,4}))?(\.(json|ya?ml|po|arb|ts|js|mjs))?$")

I18N_LIBS = (
    ("next-intl", "next-intl"), ("next-i18next", "next-i18next"),
    ("react-i18next", "react-i18next"), ("i18next", "i18next"),
    ("vue-i18n", "vue-i18n"), ("@nuxtjs/i18n", "@nuxtjs/i18n"),
    ("react-intl", "react-intl"), ("@formatjs/intl", "FormatJS"),
    ("svelte-i18n", "svelte-i18n"), ("@angular/localize", "@angular/localize"),
    ("@inlang/paraglide-js", "Paraglide"), ("astro-i18next", "astro-i18next"),
    ("gettext", "gettext"), ("intlayer", "intlayer"),
)

INTEGRATIONS = (
    ("stripe", "Stripe", "payments"),
    ("@stripe/stripe-js", "Stripe", "payments"),
    ("@supabase/supabase-js", "Supabase", "database, auth, storage"),
    ("@aws-sdk/client-s3", "AWS S3", "object storage"),
    ("@google-cloud/storage", "Google Cloud Storage", "object storage"),
    ("resend", "Resend", "transactional email"),
    ("@sendgrid/mail", "SendGrid", "transactional email"),
    ("nodemailer", "SMTP (nodemailer)", "transactional email"),
    ("openai", "OpenAI API", "model inference"),
    ("@anthropic-ai/sdk", "Anthropic API", "model inference"),
    ("twilio", "Twilio", "SMS / voice"),
    ("@sentry/nextjs", "Sentry", "error reporting"),
    ("@sentry/node", "Sentry", "error reporting"),
    ("@sentry/react", "Sentry", "error reporting"),
    ("posthog-js", "PostHog", "product analytics"),
    ("@vercel/analytics", "Vercel Analytics", "web analytics"),
    ("algoliasearch", "Algolia", "search"),
    ("meilisearch", "Meilisearch", "search"),
    ("ioredis", "Redis", "cache / queue"),
    ("bullmq", "BullMQ", "background jobs"),
    ("firebase", "Firebase", "backend services"),
    ("mapbox-gl", "Mapbox", "maps"),
    ("googleapis", "Google APIs", "integration"),
)

PY_INTEGRATIONS = (
    ("stripe", "Stripe", "payments"),
    ("boto3", "AWS", "cloud services"),
    ("sentry-sdk", "Sentry", "error reporting"),
    ("openai", "OpenAI API", "model inference"),
    ("anthropic", "Anthropic API", "model inference"),
    ("celery", "Celery", "background jobs"),
    ("redis", "Redis", "cache / queue"),
)

# Domain markers. Each family answers one question — does this repository do that
# kind of work? — and the answer becomes a project-type default, which becomes a
# fact, which decides roles and skills. Detection is evidence, never a declaration.
ML_NODE = (("langchain", "LangChain"), ("@langchain/core", "LangChain"),
           ("langgraph", "LangGraph"), ("llamaindex", "LlamaIndex"),
           ("ai", "Vercel AI SDK"), ("@ai-sdk/openai", "Vercel AI SDK"),
           ("@ai-sdk/anthropic", "Vercel AI SDK"), ("@ai-sdk/google", "Vercel AI SDK"),
           ("openai", "OpenAI API"), ("@anthropic-ai/sdk", "Anthropic API"),
           ("@google/genai", "Google Gemini SDK"), ("@google/generative-ai", "Google Gemini SDK"),
           ("ollama", "Ollama"), ("@huggingface/inference", "Hugging Face"),
           ("promptfoo", "promptfoo"), ("langfuse", "Langfuse"),
           ("braintrust", "Braintrust"), ("@mastra/core", "Mastra"))
ML_PY = (("langchain", "LangChain"), ("langgraph", "LangGraph"),
         ("llama-index", "LlamaIndex"), ("transformers", "Transformers"),
         ("torch", "PyTorch"), ("tensorflow", "TensorFlow"),
         ("scikit-learn", "scikit-learn"), ("xgboost", "XGBoost"),
         ("vllm", "vLLM"), ("litellm", "LiteLLM"), ("dspy-ai", "DSPy"),
         ("sentence-transformers", "sentence-transformers"),
         ("instructor", "Instructor"), ("haystack-ai", "Haystack"),
         ("ragas", "Ragas"), ("deepeval", "DeepEval"), ("promptfoo", "promptfoo"),
         ("mlflow", "MLflow"), ("wandb", "Weights & Biases"), ("dvc", "DVC"),
         ("bentoml", "BentoML"), ("kubeflow", "Kubeflow"), ("langfuse", "Langfuse"),
         ("google-genai", "Google Gemini SDK"), ("google-generativeai", "Google Gemini SDK"),
         ("anthropic", "Anthropic API"))
VECTOR_NODE = (("@pinecone-database/pinecone", "Pinecone"),
               ("weaviate-ts-client", "Weaviate"), ("weaviate-client", "Weaviate"),
               ("@qdrant/js-client-rest", "Qdrant"), ("chromadb", "Chroma"),
               ("@zilliz/milvus2-sdk-node", "Milvus"), ("@lancedb/lancedb", "LanceDB"))
VECTOR_PY = (("pinecone", "Pinecone"), ("pinecone-client", "Pinecone"),
             ("weaviate-client", "Weaviate"), ("qdrant-client", "Qdrant"),
             ("chromadb", "Chroma"), ("faiss-cpu", "FAISS"), ("faiss-gpu", "FAISS"),
             ("pymilvus", "Milvus"), ("lancedb", "LanceDB"), ("pgvector", "pgvector"))
DATA_NODE = (("@google-cloud/bigquery", "BigQuery"), ("snowflake-sdk", "Snowflake"),
             ("duckdb", "DuckDB"), ("@dbt-labs/dbt", "dbt"))
DATA_PY = (("apache-airflow", "Airflow"), ("dagster", "Dagster"), ("prefect", "Prefect"),
           ("luigi", "Luigi"), ("dbt-core", "dbt"), ("sqlmesh", "SQLMesh"),
           ("pyspark", "Spark"), ("apache-flink", "Flink"), ("apache-beam", "Beam"),
           ("duckdb", "DuckDB"), ("polars", "Polars"),
           ("great-expectations", "Great Expectations"), ("soda-core", "Soda"),
           ("pandera", "Pandera"), ("snowflake-connector-python", "Snowflake"),
           ("google-cloud-bigquery", "BigQuery"))
DATA_FILES = (("dbt_project.yml", "dbt"), ("dagster.yaml", "Dagster"),
              ("airflow.cfg", "Airflow"), ("dags", "Airflow DAGs"),
              ("dbt_project.yaml", "dbt"))
MSG_NODE = (("kafkajs", "Kafka"), ("kafka-node", "Kafka"), ("amqplib", "RabbitMQ"),
            ("nats", "NATS"), ("@aws-sdk/client-sqs", "SQS"),
            ("@google-cloud/pubsub", "Pub/Sub"), ("@temporalio/client", "Temporal"),
            ("bullmq", "BullMQ"), ("bull", "Bull"), ("agenda", "Agenda"))
MSG_PY = (("confluent-kafka", "Kafka"), ("kafka-python", "Kafka"), ("aiokafka", "Kafka"),
          ("pika", "RabbitMQ"), ("kombu", "RabbitMQ"), ("nats-py", "NATS"),
          ("celery", "Celery"), ("dramatiq", "Dramatiq"), ("rq", "RQ"),
          ("temporalio", "Temporal"), ("google-cloud-pubsub", "Pub/Sub"))
IAC_FILES = (("main.tf", "Terraform"), ("versions.tf", "Terraform"),
             (".terraform.lock.hcl", "Terraform"), ("terraform", "Terraform"),
             ("Pulumi.yaml", "Pulumi"), ("ansible.cfg", "Ansible"),
             ("playbooks", "Ansible"), ("Chart.yaml", "Helm"),
             ("kustomization.yaml", "Kustomize"), ("cdk.json", "AWS CDK"),
             ("serverless.yml", "Serverless Framework"),
             ("template.yaml", "AWS SAM / CloudFormation"), ("k8s", "Kubernetes manifests"),
             ("kubernetes", "Kubernetes manifests"), ("charts", "Helm"))
SCRAPE_NODE = (("crawlee", "Crawlee"), ("cheerio", "cheerio"), ("apify", "Apify"),
               ("got-scraping", "got-scraping"))
SCRAPE_PY = (("scrapy", "Scrapy"), ("beautifulsoup4", "BeautifulSoup"),
             ("selectolax", "selectolax"), ("feedparser", "feedparser"),
             ("apify", "Apify"), ("crawlee", "Crawlee"))
LOAD_NODE = (("k6", "k6"), ("artillery", "Artillery"), ("autocannon", "autocannon"),
             ("@types/k6", "k6"), ("lighthouse", "Lighthouse"))
LOAD_PY = (("locust", "Locust"), ("pytest-benchmark", "pytest-benchmark"),
           ("asv", "airspeed velocity"))

# Every agent tool looks for its instructions in a different file, and they nearly all
# now also read AGENTS.md. So AGENTS.md stays the single source of truth and each of
# these is a pointer to it — never a copy, which would drift within a release.
# (relative path, header written when the file is created)
HARNESS_POINTERS = (
    ("CLAUDE.md", "# Project instructions\n\n"),                     # Claude Code
    ("GEMINI.md", "# Project instructions\n\n"),                     # Gemini CLI
    ("AGENT.md", "# Project instructions\n\n"),                      # Amp
    (".github/copilot-instructions.md", "# Copilot instructions\n\n"),
    (".cursor/rules/agents.mdc",
     "---\ndescription: Operating contract for this repository\nalwaysApply: true\n---\n\n"),
    (".cursorrules", ""),                                            # Cursor (classic)
    (".windsurfrules", ""),
    (".clinerules", ""),
    (".roo/rules/agents.md", "# Project instructions\n\n"),          # Roo Code (.roomodes is YAML)
    ("CONVENTIONS.md", "# Conventions\n\n"),                         # Aider
)

# Tools whose own instruction file *is* AGENTS.md need no pointer at all: OpenAI Codex,
# Jules, Zed, Factory, Cursor 1.x, Google Antigravity and others read it directly.
HARNESS_NATIVE = ("codex", "jules", "zed", "factory", "opencode", "antigravity")

HARNESS_ALIASES = {
    "claude": ("CLAUDE.md",),
    "gemini": ("GEMINI.md",),
    "amp": ("AGENT.md",),
    "copilot": (".github/copilot-instructions.md",),
    "cursor": (".cursor/rules/agents.mdc", ".cursorrules"),
    "windsurf": (".windsurfrules",),
    "cline": (".clinerules",),
    "roo": (".roo/rules/agents.md",),
    "aider": ("CONVENTIONS.md",),
}

HARNESS_TITLES = {
    "claude": "Claude Code", "cursor": "Cursor", "copilot": "GitHub Copilot",
    "gemini": "Gemini CLI", "windsurf": "Windsurf", "cline": "Cline", "roo": "Roo Code",
    "amp": "Amp", "aider": "Aider",
}
# The order the guided setup offers them in, most used first.
HARNESS_ORDER = ("claude", "cursor", "copilot", "gemini", "windsurf", "cline", "roo",
                 "amp", "aider")
# Files or directories that show a tool is already used here. Detection only pre-ticks
# the question; the answer decides.
HARNESS_MARKERS = {
    "claude": ("CLAUDE.md", ".claude"),
    "cursor": (".cursor", ".cursorrules"),
    "copilot": (".github/copilot-instructions.md", ".github/instructions"),
    "gemini": ("GEMINI.md", ".gemini"),
    "windsurf": (".windsurfrules", ".windsurf"),
    "cline": (".clinerules",),
    "roo": (".roo", ".roomodes"),
    "amp": ("AGENT.md",),
    "aider": ("CONVENTIONS.md", ".aider.conf.yml"),
}

# Deployment platforms: (id, label). Each id has a checklist in optional/platforms/<id>.md
# that installs into <docs>/platforms/ only when the project uses that platform -- the
# process documents stay stack-neutral, and the platform-specific failure modes live here.
DEPLOY_PLATFORMS = (
    ("cloudflare-workers", "Cloudflare Workers & Pages"),
    ("cloudflare-edge", "Cloudflare proxy / CDN / WAF in front of an origin"),
    ("vercel", "Vercel"),
    ("netlify", "Netlify"),
    ("fly", "Fly.io"),
    ("railway", "Railway"),
    ("render", "Render"),
    ("heroku", "Heroku / Dokku (Procfile buildpack)"),
    ("dokploy", "Dokploy"),
    ("coolify", "Coolify"),
    ("kamal", "Kamal"),
    ("vps", "Self-managed server (VPS / bare metal, systemd, PM2, nginx, Caddy)"),
    ("kubernetes", "Kubernetes (Helm, Kustomize, manifests)"),
    ("aws", "AWS (Lambda, ECS, App Runner, Amplify, EC2)"),
    ("gcp", "Google Cloud / Firebase (Cloud Run, App Engine, Hosting)"),
    ("azure", "Azure (App Service, Functions, Static Web Apps)"),
    ("digitalocean", "DigitalOcean App Platform"),
)
DEPLOY_IDS = tuple(pid for pid, _ in DEPLOY_PLATFORMS)
DEPLOY_LABELS = dict(DEPLOY_PLATFORMS)
DEPLOY_OTHER = "other"

WEB_FRAMEWORKS = ("Next.js", "Nuxt", "Astro", "Remix", "TanStack Start", "TanStack Router",
                  "Angular", "Svelte", "SvelteKit", "Vue", "React", "SolidJS")
API_FRAMEWORKS = ("NestJS", "Express", "Fastify", "FastAPI", "Django", "Flask",
                  "Laravel", "Rails", "Hono", "Elysia")


def add(seq, value):
    if value and value not in seq:
        seq.append(value)


class Detected(object):
    def __init__(self):
        self.lang = []
        self.pm = []
        self.fw = []
        self.db = []
        self.auth = []
        self.host = []
        self.ci = []
        self.test = []
        self.migrations = []
        self.adapters = []
        self.cmds = {}
        self.command_sources = {}
        self.platforms = []
        self.deploy = []           # DEPLOY_PLATFORMS ids with repository evidence
        self.mono_tool = ""
        self.components = []       # (name, kind, path)
        self.services = []
        self.integrations = []     # (service, used for)
        self.i18n_libs = []
        self.locales = []
        self.catalog = ""
        self.ml = []               # models, prompts, retrieval, eval tooling
        self.vector = []           # vector stores / indexes
        self.dataeng = []          # orchestration, transformation, warehouses
        self.messaging = []        # queues, brokers, workflow engines
        self.iac = []              # infrastructure this repository provisions
        self.scrape = []           # third-party acquisition
        self.load = []             # benchmark / load tooling
        self.types = [12]

    def csv(self, field):
        return ", ".join(getattr(self, field))


class Repo(object):
    """Read-only view of the target directory."""

    def __init__(self, root):
        self.root = Path(root)
        self._pkg = None
        self._pkg_read = False

    def has(self, rel):
        return (self.root / rel).exists()

    def text(self, rel):
        p = self.root / rel
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError):
            return ""

    def pkg(self):
        if not self._pkg_read:
            self._pkg_read = True
            try:
                self._pkg = json.loads(self.text("package.json"))
            except ValueError:
                self._pkg = None
        return self._pkg or {}

    def json_file(self, rel):
        try:
            value = json.loads(strip_jsonc(self.text(rel)))
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}

    def deps(self):
        if hasattr(self, "_all_deps") and self._all_deps is not None:
            return self._all_deps
        p = self.pkg()
        out = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            value = p.get(key)
            if isinstance(value, dict):
                out.update(value)
        scan_parents = ["apps", "packages", "services", "libs", "src"]
        workspaces = p.get("workspaces")
        if isinstance(workspaces, list):
            for pattern in workspaces:
                if isinstance(pattern, str) and pattern.endswith("/*"):
                    parent = pattern[:-2].strip("/")
                    if parent and parent not in scan_parents:
                        scan_parents.append(parent)
        for parent in scan_parents:
            p_dir = self.root / parent
            if p_dir.is_dir():
                for child in self.subdirs(parent):
                    if child.name.lower() in NON_PRODUCT_DIRS or child.name.lower().startswith("test"):
                        continue
                    pkg_file = child / "package.json"
                    if pkg_file.is_file():
                        try:
                            sub_p = json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
                            if isinstance(sub_p, dict):
                                for key in ("dependencies", "devDependencies", "peerDependencies"):
                                    val = sub_p.get(key)
                                    if isinstance(val, dict):
                                        out.update(val)
                        except (ValueError, IOError, OSError):
                            pass
        self._all_deps = out
        return out

    def has_ts(self):
        if self.has("tsconfig.json") or self.has("tsconfig.base.json"):
            return True
        for parent in ("apps", "packages", "services", "libs", "src"):
            p_dir = self.root / parent
            if p_dir.is_dir():
                for child in self.subdirs(parent):
                    if (child / "tsconfig.json").is_file():
                        return True
        return False

    def scripts(self):
        s = self.pkg().get("scripts")
        return s if isinstance(s, dict) else {}

    def pydep(self, name):
        pattern = re.compile(r"(^|[^A-Za-z0-9_.-])%s([^A-Za-z0-9_.-]|$)" % re.escape(name),
                             re.IGNORECASE | re.MULTILINE)
        for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"):
            if self.has(f) and pattern.search(self.text(f)):
                return True
        return any(pattern.search(text) for text in self.child_python_manifests())

    def child_python_manifests(self):
        """Python manifests of workspace children, read once: pydep runs per name."""
        if getattr(self, "_child_py", None) is not None:
            return self._child_py
        texts = []
        for parent in ("services", "backend", "packages", "apps"):
            for child in self.subdirs(parent):
                name = child.name.lower()
                if name in NON_PRODUCT_DIRS or name.startswith("test"):
                    continue
                for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"):
                    p = child / f
                    if p.is_file():
                        try:
                            texts.append(p.read_text(encoding="utf-8", errors="replace"))
                        except (IOError, OSError):
                            pass
        self._child_py = texts
        return texts

    def subdirs(self, rel):
        p = self.root / rel
        if not p.is_dir():
            return []
        try:
            return sorted([c for c in p.iterdir() if not c.name.startswith(".")],
                          key=lambda c: c.name)
        except OSError:
            return []


# Children of a scanned parent that hold samples rather than the product itself.
NON_PRODUCT_DIRS = ("fixtures", "fixture", "examples", "example", "samples", "__tests__")


def strip_jsonc(text):
    """Drop // and /* */ comments and trailing commas outside strings, for deno.jsonc."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


WALK_SKIP_DIRS = ("node_modules", "dist", "build", "vendor", "venv", "env", "target",
                  "coverage", "__pycache__", "out", "tmp")


def find_prisma_schema(root, max_depth=4):
    """First prisma/schema.prisma below root, pruning dependency, build and sample
    directories while walking and judging only the part of the path inside the repository."""
    base = str(root).rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(str(root)):
        if dirpath.count(os.sep) - base >= max_depth:
            dirnames[:] = []
        dirnames[:] = sorted(x for x in dirnames
                             if not x.startswith(".") and x not in WALK_SKIP_DIRS
                             and x.lower() not in NON_PRODUCT_DIRS
                             and not x.lower().startswith("test"))
        if os.path.basename(dirpath) == "prisma" and "schema.prisma" in filenames:
            return Path(dirpath) / "schema.prisma"
    return None


def add_markers(text, mappings, destination):
    """Append labels for dependency/config markers found in ecosystem text."""
    lowered = text.lower()
    for marker, label in mappings:
        if marker.lower() in lowered:
            add(destination, label)


def adapter_command(detected, adapter, key, command):
    """Compose one stage across languages, but keep one default per adapter."""
    sources = detected.command_sources.setdefault(key, [])
    if adapter in sources:
        return
    if key in detected.cmds and detected.cmds[key] != command:
        detected.cmds[key] = "%s && %s" % (detected.cmds[key], command)
    else:
        detected.cmds[key] = command
    sources.append(adapter)


def detect_deploy(repo, dep):
    """Deployment platforms with evidence in the repository. Only files that exist to
    configure a deploy count -- an SDK import says the code talks to a cloud, not that it
    runs there -- and a Traefik label alone names no platform: every Docker PaaS uses it."""
    found = []

    def has_any(*rels):
        return any(repo.has(rel) for rel in rels)

    compose = "\n".join(repo.text(f) for f in ("docker-compose.yml", "docker-compose.yaml",
                                               "compose.yml", "compose.yaml"))
    kamal = repo.text("config/deploy.yml")
    sam = repo.text("template.yaml") + repo.text("template.yml")
    app_yaml = repo.text("app.yaml")

    if (has_any("wrangler.toml", "wrangler.json", "wrangler.jsonc")
            or dep("@cloudflare/workers-types") or dep("@opennextjs/cloudflare")
            or dep("@cloudflare/next-on-pages")):
        add(found, "cloudflare-workers")
    if has_any("vercel.json", ".vercel/project.json"):
        add(found, "vercel")
    if has_any("netlify.toml"):
        add(found, "netlify")
    if has_any("fly.toml"):
        add(found, "fly")
    if has_any("railway.json", "railway.toml"):
        add(found, "railway")
    if has_any("render.yaml"):
        add(found, "render")
    if has_any("Procfile") or "heroku" in repo.text("app.json"):
        add(found, "heroku")
    if "dokploy" in compose.lower() or has_any("dokploy.json"):
        add(found, "dokploy")
    if ("coolify" in compose.lower() or "SERVICE_FQDN_" in compose
            or "SERVICE_URL_" in compose):
        add(found, "coolify")
    if has_any(".kamal") or (re.search(r"^service:", kamal, re.M)
                             and re.search(r"^image:", kamal, re.M)):
        add(found, "kamal")
    if (has_any("Caddyfile", "nginx.conf", "ecosystem.config.js", "ecosystem.config.cjs")
            or [p for p in repo.root.glob("*.service") if p.is_file()]):
        add(found, "vps")
    if (has_any("Chart.yaml", "kustomization.yaml", "skaffold.yaml", "helmfile.yaml")
            or repo.subdirs("k8s") or repo.subdirs("helm")):
        add(found, "kubernetes")
    if (has_any("cdk.json", "samconfig.toml", "amplify.yml", "apprunner.yaml",
                "serverless.yml", "serverless.yaml", ".ebextensions")
            or repo.subdirs("copilot") or "AWSTemplateFormatVersion" in sam
            or "AWS::Serverless" in sam):
        add(found, "aws")
    if (has_any("cloudbuild.yaml", "firebase.json", ".firebaserc")
            or re.search(r"^runtime:", app_yaml, re.M)):
        add(found, "gcp")
    if has_any("azure.yaml", "staticwebapp.config.json", "host.json"):
        add(found, "azure")
    if has_any(".do/app.yaml", ".do/deploy.template.yaml"):
        add(found, "digitalocean")
    return found


def parse_deploy(raw):
    """--deploy value -> list of ids, or an error message."""
    ids = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip().lower()
        if not part or part == "none":
            continue
        if part not in DEPLOY_IDS and part != DEPLOY_OTHER:
            return None, part
        add(ids, part)
    return ids, None


def detect(root):
    repo = Repo(root)
    d = Detected()
    deps = repo.deps()
    scripts = repo.scripts()

    def dep(name):
        return name in deps

    # -- node ------------------------------------------------------------------
    if repo.has("package.json"):
        add(d.adapters, "node")
        add(d.lang, "Node.js + TypeScript" if repo.has_ts() else "Node.js")
        if repo.has("bun.lockb") or repo.has("bun.lock"):
            pm = "bun"
        elif repo.has("pnpm-lock.yaml"):
            pm = "pnpm"
        elif repo.has("yarn.lock"):
            pm = "yarn"
        else:
            pm = "npm"
        add(d.pm, pm)

        for name, label in (("next", "Next.js"), ("nuxt", "Nuxt"), ("astro", "Astro"),
                            ("@remix-run/react", "Remix"),
                            ("@tanstack/react-start", "TanStack Start"),
                            ("@tanstack/react-router", "TanStack Router"),
                            ("@nestjs/core", "NestJS"), ("@angular/core", "Angular"),
                            ("express", "Express"), ("fastify", "Fastify"),
                            ("hono", "Hono"), ("elysia", "Elysia"),
                            ("@sveltejs/kit", "SvelteKit"), ("svelte", "Svelte"),
                            ("solid-js", "SolidJS"), ("vue", "Vue")):
            if dep(name):
                add(d.fw, label)
        if dep("react") and not any(f in d.fw for f in WEB_FRAMEWORKS):
            add(d.fw, "React")
        if dep("vite"):
            add(d.fw, "Vite")
        if dep("tailwindcss"):
            add(d.fw, "Tailwind CSS")

        prisma_schema = ""
        if repo.has("prisma/schema.prisma"):
            prisma_schema = repo.text("prisma/schema.prisma")
        else:
            p = find_prisma_schema(repo.root) if (dep("@prisma/client") or dep("prisma")) else None
            if p is not None:
                try:
                    prisma_schema = p.read_text(encoding="utf-8", errors="replace")
                except (IOError, OSError):
                    pass
        if dep("@prisma/client") or prisma_schema or repo.has("prisma/schema.prisma"):
            provider = re.search(r'provider\s*=\s*"([a-z]+)"', prisma_schema) if prisma_schema else None
            add(d.db, "Prisma (%s)" % provider.group(1) if provider else "Prisma")
            add(d.migrations, "Prisma Migrate")
        has_drizzle_config = (repo.has("drizzle.config.ts") or repo.has("drizzle.config.js")
                              or repo.has("drizzle.config.json"))
        if not has_drizzle_config:
            for p in ("packages", "apps", "services"):
                if any(child.is_dir() and (
                        (child / "drizzle.config.ts").is_file()
                        or (child / "drizzle.config.js").is_file()
                        or (child / "drizzle.config.json").is_file())
                       for child in repo.subdirs(p)):
                    has_drizzle_config = True
                    break
        if dep("drizzle-orm") or has_drizzle_config:
            add(d.db, "Drizzle")
        for name, label in (("@supabase/supabase-js", "Supabase (Postgres)"),
                            ("typeorm", "TypeORM"), ("sequelize", "Sequelize"),
                            ("@mikro-orm/core", "MikroORM"), ("knex", "Knex"),
                            ("mongoose", "MongoDB"), ("pg", "PostgreSQL"),
                            ("mysql2", "MySQL"), ("better-sqlite3", "SQLite"),
                            ("sqlite3", "SQLite"), ("mssql", "SQL Server"),
                            ("oracledb", "Oracle")):
            if dep(name):
                add(d.db, label)
        if dep("drizzle-kit") or has_drizzle_config:
            add(d.migrations, "Drizzle Kit")
        if dep("ioredis") or dep("redis"):
            add(d.db, "Redis")
        for name, label in (("next-auth", "Auth.js / NextAuth"),
                            ("@clerk/nextjs", "Clerk"),
                            ("@supabase/supabase-js", "Supabase Auth"),
                            ("passport", "Passport"), ("@nestjs/jwt", "JWT (@nestjs/jwt)"),
                            ("lucia", "Lucia")):
            if dep(name):
                add(d.auth, label)
        for name, label in (("vitest", "Vitest"), ("jest", "Jest"), ("mocha", "Mocha"),
                            ("@playwright/test", "Playwright"), ("cypress", "Cypress"),
                            ("supertest", "Supertest"), ("@pact-foundation/pact", "Pact"),
                            ("@testing-library/react", "Testing Library")):
            if dep(name):
                add(d.test, label)

        if "dev" in scripts:
            d.cmds["run"] = "%s run dev" % pm
        elif "start" in scripts:
            d.cmds["run"] = "%s start" % pm
        script_candidates = {
            "format": ("format:check", "check:format", "format"),
            "lint": ("lint",),
            "typecheck": ("typecheck", "type-check", "check:types"),
            "unit": ("test:unit", "unit", "test"),
            "integration": ("test:integration", "integration"),
            "contract": ("test:contract", "contract"),
            "build": ("build",),
            "scan": ("security", "scan", "audit"),
            "a11y": ("test:a11y", "a11y", "accessibility"),
            "e2e": ("test:e2e", "e2e"),
        }
        for key, candidates in script_candidates.items():
            for script in candidates:
                if script in scripts:
                    d.cmds[key] = "%s run %s" % (pm, script)
                    break
        # A bare `tsc` reads only ./tsconfig.json; a monorepo without one needs its own
        # script, and a blank row is recoverable where a gate that always fails is not.
        if "typecheck" not in d.cmds and repo.has("tsconfig.json") and dep("typescript"):
            d.cmds["typecheck"] = {"npm": "npm exec tsc -- --noEmit",
                                   "pnpm": "pnpm exec tsc --noEmit",
                                   "yarn": "yarn tsc --noEmit",
                                   "bun": "bunx tsc --noEmit"}[pm]
        if "unit" not in d.cmds and pm == "bun":
            d.cmds["unit"] = "bun test"
        if "e2e" not in d.cmds and dep("@playwright/test"):
            d.cmds["e2e"] = {"npm": "npm exec playwright test",
                              "pnpm": "pnpm exec playwright test",
                              "yarn": "yarn playwright test",
                              "bun": "bunx playwright test"}[pm]
        d.cmds["install"] = {"npm": "npm ci" if repo.has("package-lock.json") else "npm install",
                             "pnpm": "pnpm install --frozen-lockfile" if repo.has("pnpm-lock.yaml") else "pnpm install",
                             "yarn": "yarn install", "bun": "bun install"}[pm]
        if "scan" not in d.cmds and pm == "npm":
            d.cmds["scan"] = "npm audit --audit-level=high"
        elif "scan" not in d.cmds and pm == "pnpm":
            d.cmds["scan"] = "pnpm audit --audit-level high"
        for key in d.cmds:
            add(d.command_sources.setdefault(key, []), "node")

    # -- deno ------------------------------------------------------------------
    if repo.has("deno.json") or repo.has("deno.jsonc") or repo.has("deno.lock"):
        add(d.adapters, "deno")
        add(d.lang, "Deno")
        add(d.pm, "deno")
        add(d.test, "deno test")
        deno_cfg = repo.text("deno.json") + repo.text("deno.jsonc")
        if "hono" in deno_cfg.lower():
            add(d.fw, "Hono")
        deno_json = repo.json_file("deno.json") or repo.json_file("deno.jsonc")
        tasks = deno_json.get("tasks", {})
        if not isinstance(tasks, dict):
            tasks = {}

        # A project task wins over the built-in command: adapter_command keeps the first.
        def task_or(names, fallback):
            for name in names:
                if name in tasks:
                    return "deno task %s" % name
            return fallback

        adapter_command(d, "deno", "install", "deno install")
        adapter_command(d, "deno", "unit", task_or(("test", "test:unit"), "deno test"))
        adapter_command(d, "deno", "lint", task_or(("lint",), "deno lint"))
        adapter_command(d, "deno", "format", task_or(("fmt", "format"), "deno fmt --check"))
        adapter_command(d, "deno", "typecheck", task_or(("check", "typecheck"), "deno check"))
        if "run" not in d.cmds:
            if "dev" in tasks:
                d.cmds["run"] = "deno task dev"
            elif "start" in tasks:
                d.cmds["run"] = "deno task start"

    # -- python ----------------------------------------------------------------
    if (repo.has("pyproject.toml") or repo.has("requirements.txt") or repo.has("setup.py")
            or repo.has("Pipfile")):
        add(d.adapters, "python")
        add(d.lang, "Python")
        if repo.has("uv.lock"):
            add(d.pm, "uv")
            adapter_command(d, "python", "install", "uv sync")
        elif repo.has("poetry.lock"):
            add(d.pm, "Poetry")
            adapter_command(d, "python", "install", "poetry install")
        elif repo.has("Pipfile"):
            add(d.pm, "pipenv")
            adapter_command(d, "python", "install", "pipenv install")
        elif repo.has("requirements.txt"):
            add(d.pm, "pip")
            adapter_command(d, "python", "install", "pip install -r requirements.txt")
        for name, label in (("django", "Django"), ("fastapi", "FastAPI"),
                            ("flask", "Flask")):
            if repo.pydep(name):
                add(d.fw, label)
        for name, label in (("sqlalchemy", "SQLAlchemy"), ("django", "Django ORM"),
                            ("psycopg", "PostgreSQL"), ("psycopg2", "PostgreSQL"),
                            ("asyncpg", "PostgreSQL"), ("pymysql", "MySQL"),
                            ("mysqlclient", "MySQL"), ("pymongo", "MongoDB"),
                            ("motor", "MongoDB"), ("redis", "Redis"),
                            ("aiosqlite", "SQLite")):
            if repo.pydep(name):
                add(d.db, label)
        if repo.pydep("alembic") or repo.has("alembic.ini"):
            add(d.migrations, "Alembic")
        if repo.pydep("django") and repo.has("manage.py"):
            add(d.migrations, "Django migrations")
        if repo.pydep("pytest") or repo.has("pytest.ini"):
            add(d.test, "pytest")
            adapter_command(d, "python", "unit", "pytest")
            if repo.has("tests/integration"):
                adapter_command(d, "python", "integration", "pytest tests/integration")
            if repo.has("tests/contract"):
                adapter_command(d, "python", "contract", "pytest tests/contract")
        for name, label in (("hypothesis", "Hypothesis"), ("tox", "tox"),
                            ("nox", "nox"), ("playwright", "Playwright")):
            if repo.pydep(name):
                add(d.test, label)
        if repo.pydep("pip-audit"):
            adapter_command(d, "python", "scan", "pip-audit")
        if repo.pydep("ruff"):
            adapter_command(d, "python", "lint", "ruff check .")
            adapter_command(d, "python", "format", "ruff format --check .")
        if repo.pydep("mypy"):
            adapter_command(d, "python", "typecheck", "mypy .")

    # -- other runtimes --------------------------------------------------------
    if repo.has("go.mod"):
        add(d.adapters, "go")
        add(d.lang, "Go")
        add(d.pm, "go modules")
        add(d.test, "go test")
        adapter_command(d, "go", "install", "go mod download")
        adapter_command(d, "go", "unit", "go test ./...")
        adapter_command(d, "go", "build", "go build ./...")
        adapter_command(d, "go", "format", "test -z \"$(find . -name '*.go' -not -path "
                        "'./vendor/*' -exec gofmt -l {} +)\"")
        adapter_command(d, "go", "lint", "go vet ./...")
        go_mod = repo.text("go.mod")
        add_markers(go_mod, (("gorm.io/gorm", "GORM"), ("github.com/jackc/pgx", "PostgreSQL"),
                             ("github.com/lib/pq", "PostgreSQL"),
                             ("github.com/go-sql-driver/mysql", "MySQL"),
                             ("modernc.org/sqlite", "SQLite"),
                             ("go.mongodb.org/mongo-driver", "MongoDB"),
                             ("github.com/redis/go-redis", "Redis")), d.db)
        add_markers(go_mod, (("github.com/stretchr/testify", "testify"),
                             ("github.com/onsi/ginkgo", "Ginkgo")), d.test)
        if repo.has("sqlc.yaml") or repo.has("sqlc.yml"):
            add(d.db, "sqlc")
            add(d.migrations, "sqlc-managed SQL migrations")
        for migration_dir in ("migrations", "db/migrations"):
            if repo.has(migration_dir):
                add(d.migrations, "SQL migration files (%s)" % migration_dir)
    if repo.has("Cargo.toml"):
        add(d.adapters, "rust")
        add(d.lang, "Rust")
        add(d.pm, "cargo")
        add(d.test, "cargo test")
        adapter_command(d, "rust", "install", "cargo fetch")
        adapter_command(d, "rust", "unit", "cargo test")
        adapter_command(d, "rust", "build", "cargo build --release")
        adapter_command(d, "rust", "format", "cargo fmt --check")
        adapter_command(d, "rust", "lint", "cargo clippy --all-targets --all-features -- -D warnings")
        cargo = repo.text("Cargo.toml")
        add_markers(cargo, (("diesel", "Diesel"), ("sqlx", "SQLx"),
                            ("sea-orm", "SeaORM"), ("mongodb", "MongoDB"),
                            ("redis", "Redis")), d.db)
        add_markers(cargo, (("proptest", "proptest"), ("rstest", "rstest"),
                            ("mockall", "mockall")), d.test)
        if repo.has("migrations"):
            add(d.migrations, "Rust migration directory")
    if repo.has("composer.json"):
        add(d.adapters, "php")
        add(d.lang, "PHP")
        add(d.pm, "Composer")
        adapter_command(d, "php", "install", "composer install --no-interaction --prefer-dist")
        composer = repo.json_file("composer.json")
        php_deps = {}
        for section in ("require", "require-dev"):
            if isinstance(composer.get(section), dict):
                php_deps.update(composer[section])
        if "laravel/framework" in php_deps:
            add(d.fw, "Laravel")
            add(d.db, "Eloquent ORM")
            add(d.migrations, "Laravel migrations")
        if "doctrine/orm" in php_deps:
            add(d.db, "Doctrine ORM")
        for name, label in (("ext-pdo_pgsql", "PostgreSQL"), ("ext-pgsql", "PostgreSQL"),
                            ("ext-pdo_mysql", "MySQL/MariaDB"),
                            ("ext-mongodb", "MongoDB"), ("predis/predis", "Redis")):
            if name in php_deps:
                add(d.db, label)
        for name, label in (("pestphp/pest", "Pest"), ("phpunit/phpunit", "PHPUnit"),
                            ("behat/behat", "Behat"),
                            ("laravel/dusk", "Laravel Dusk")):
            if name in php_deps:
                add(d.test, label)
        php_scripts = composer.get("scripts", {})
        if isinstance(php_scripts, dict):
            for script, key in (("test", "unit"), ("test:unit", "unit"),
                                ("test:integration", "integration"),
                                ("test:contract", "contract"), ("test:e2e", "e2e"),
                                ("lint", "lint")):
                if script in php_scripts:
                    adapter_command(d, "php", key, "composer %s" % script)
        if "php" not in d.command_sources.get("unit", []) and "pestphp/pest" in php_deps:
            adapter_command(d, "php", "unit", "vendor/bin/pest")
        elif "php" not in d.command_sources.get("unit", []) and "phpunit/phpunit" in php_deps:
            adapter_command(d, "php", "unit", "vendor/bin/phpunit")
    if repo.has("Gemfile"):
        add(d.adapters, "ruby")
        add(d.lang, "Ruby")
        add(d.pm, "Bundler")
        adapter_command(d, "ruby", "install", "bundle install")
        gemfile = repo.text("Gemfile")
        if re.search(r"\bgem\s+['\"]rails['\"]", gemfile):
            add(d.fw, "Rails")
            add(d.db, "Active Record")
            add(d.migrations, "Rails migrations")
        add_markers(gemfile, (("gem 'pg'", "PostgreSQL"), ("gem \"pg\"", "PostgreSQL"),
                              ("gem 'mysql2'", "MySQL"), ("gem \"mysql2\"", "MySQL"),
                              ("gem 'sqlite3'", "SQLite"), ("gem \"sqlite3\"", "SQLite"),
                              ("mongoid", "MongoDB"), ("redis", "Redis")), d.db)
        add_markers(gemfile, (("rspec", "RSpec"), ("minitest", "Minitest"),
                              ("cucumber", "Cucumber"), ("capybara", "Capybara")), d.test)
        if "RSpec" in d.test:
            adapter_command(d, "ruby", "unit", "bundle exec rspec")
        elif "Minitest" in d.test:
            adapter_command(d, "ruby", "unit", "bundle exec rake test")
    if repo.has("pom.xml"):
        add(d.adapters, "jvm-maven")
        add(d.lang, "Java")
        add(d.pm, "Maven")
        adapter_command(d, "jvm-maven", "install", "mvn dependency:go-offline")
        adapter_command(d, "jvm-maven", "unit", "mvn test")
        adapter_command(d, "jvm-maven", "build", "mvn package -DskipTests")
    if repo.has("build.gradle") or repo.has("build.gradle.kts"):
        add(d.adapters, "jvm-gradle")
        add(d.lang, "Java / Kotlin")
        add(d.pm, "Gradle")
        adapter_command(d, "jvm-gradle", "install", "./gradlew dependencies")
        adapter_command(d, "jvm-gradle", "unit", "./gradlew test")
        adapter_command(d, "jvm-gradle", "build", "./gradlew assemble")
    java_text = "\n".join(repo.text(name) for name in
                            ("pom.xml", "build.gradle", "build.gradle.kts"))
    if java_text.strip():
        add_markers(java_text, (("spring-boot", "Spring Boot"),
                                ("hibernate", "Hibernate/JPA")), d.fw)
        add_markers(java_text, (("spring-data-jpa", "JPA"),
                                ("hibernate-core", "Hibernate"),
                                ("postgresql", "PostgreSQL"), ("mysql", "MySQL"),
                                ("mariadb", "MariaDB"), ("mssql-jdbc", "SQL Server"),
                                ("ojdbc", "Oracle"), ("mongodb", "MongoDB"),
                                ("redis", "Redis")), d.db)
        add_markers(java_text, (("junit", "JUnit"), ("testng", "TestNG"),
                                ("mockito", "Mockito"), ("rest-assured", "REST Assured"),
                                ("testcontainers", "Testcontainers")), d.test)
        add_markers(java_text, (("flyway", "Flyway"),
                                ("liquibase", "Liquibase")), d.migrations)
    csproj_files = list(Path(root).glob("*.csproj"))
    if csproj_files or list(Path(root).glob("*.sln")):
        add(d.adapters, "dotnet")
        add(d.lang, "C# / .NET")
        add(d.pm, "NuGet")
        adapter_command(d, "dotnet", "install", "dotnet restore")
        adapter_command(d, "dotnet", "unit", "dotnet test")
        adapter_command(d, "dotnet", "build", "dotnet build")
        dotnet_text = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                                 for path in csproj_files[:20])
        add_markers(dotnet_text, (("Microsoft.EntityFrameworkCore", "Entity Framework Core"),
                                  ("Npgsql.EntityFrameworkCore", "PostgreSQL"),
                                  ("Pomelo.EntityFrameworkCore.MySql", "MySQL/MariaDB"),
                                  ("Microsoft.EntityFrameworkCore.SqlServer", "SQL Server"),
                                  ("Microsoft.EntityFrameworkCore.Sqlite", "SQLite"),
                                  ("MongoDB.Driver", "MongoDB"),
                                  ("StackExchange.Redis", "Redis"), ("Dapper", "Dapper")), d.db)
        add_markers(dotnet_text, (("xunit", "xUnit"), ("NUnit", "NUnit"),
                                  ("MSTest", "MSTest"),
                                  ("Microsoft.AspNetCore.Mvc.Testing", "ASP.NET integration tests"),
                                  ("Testcontainers", "Testcontainers")), d.test)
        if "Entity Framework Core" in d.db:
            add(d.migrations, "EF Core migrations")

    # -- hosting, CI, platforms ------------------------------------------------
    d.deploy = detect_deploy(repo, dep)
    for pid in d.deploy:
        add(d.host, DEPLOY_LABELS[pid].split(" (")[0])
    if not d.deploy and (dep("@aws-sdk/client-s3") or repo.pydep("boto3")):
        add(d.host, "AWS")           # a client library: uses AWS, not proven to run there
    if not d.deploy and (dep("@google-cloud/storage") or dep("@google-cloud/bigquery")
                         or repo.pydep("google-cloud-storage")
                         or repo.pydep("google-cloud-bigquery")):
        add(d.host, "Google Cloud")
    if repo.has("Dockerfile") or repo.has("docker-compose.yml") or repo.has("compose.yaml"):
        add(d.host, "Docker")
    for f, label in ((".github/workflows", "GitHub Actions"), (".gitlab-ci.yml", "GitLab CI"),
                     ("Jenkinsfile", "Jenkins"), (".circleci", "CircleCI"),
                     ("azure-pipelines.yml", "Azure Pipelines")):
        if repo.has(f):
            add(d.ci, label)

    if repo.has(".replit") or repo.has("replit.nix") or repo.has("replit.md"):
        add(d.platforms, "Replit")
    if repo.has(".lovable") or "lovable" in repo.text("package.json"):
        add(d.platforms, "Lovable")
    for f, label in ((".bolt", "Bolt"), (".idx", "Firebase-Studio"),
                     ("glitch.json", "Glitch"), ("sandbox.config.json", "CodeSandbox"),
                     (".codesandbox", "CodeSandbox")):
        if repo.has(f):
            add(d.platforms, label)

    # -- architecture ----------------------------------------------------------
    for f, label in (("pnpm-workspace.yaml", "pnpm workspaces"), ("turbo.json", "Turborepo"),
                     ("nx.json", "Nx"), ("lerna.json", "Lerna"), ("go.work", "Go workspace")):
        if repo.has(f):
            d.mono_tool = label
    if not d.mono_tool and repo.pkg().get("workspaces"):
        d.mono_tool = "npm/yarn workspaces"
    if not d.mono_tool and re.search(r"^\[workspace\]", repo.text("Cargo.toml"), re.M):
        d.mono_tool = "cargo workspace"

    for parent, kind in (("apps", "application"), ("packages", "package"),
                         ("services", "service"), ("libs", "library")):
        for child in repo.subdirs(parent):
            if child.is_dir():
                d.components.append((child.name, kind, "%s/%s" % (parent, child.name)))
    if len(d.components) > 16:
        d.components = d.components[:16]

    compose = repo.text("docker-compose.yml") or repo.text("compose.yaml")
    if compose:
        in_services = False
        for line in compose.splitlines():
            if re.match(r"^services:\s*$", line):
                in_services = True
                continue
            if in_services:
                if re.match(r"^\S", line):
                    break
                m = re.match(r"^  ([A-Za-z0-9._-]+):\s*$", line)
                if m:
                    add(d.services, m.group(1))

    for name, service, used_for in INTEGRATIONS:
        if dep(name) and service not in [s for s, _ in d.integrations]:
            d.integrations.append((service, used_for))
    for name, service, used_for in PY_INTEGRATIONS:
        if repo.pydep(name) and service not in [s for s, _ in d.integrations]:
            d.integrations.append((service, used_for))

    # -- domain markers --------------------------------------------------------
    for table, dest in ((ML_NODE, d.ml), (VECTOR_NODE, d.vector), (DATA_NODE, d.dataeng),
                        (MSG_NODE, d.messaging), (SCRAPE_NODE, d.scrape),
                        (LOAD_NODE, d.load)):
        for name, label in table:
            if dep(name):
                add(dest, label)
    for table, dest in ((ML_PY, d.ml), (VECTOR_PY, d.vector), (DATA_PY, d.dataeng),
                        (MSG_PY, d.messaging), (SCRAPE_PY, d.scrape), (LOAD_PY, d.load)):
        for name, label in table:
            if repo.pydep(name):
                add(dest, label)
    for f, label in DATA_FILES:
        if repo.has(f):
            add(d.dataeng, label)
    for f, label in IAC_FILES:
        if repo.has(f):
            add(d.iac, label)
    add_markers(repo.text("Gemfile"),
                (("sidekiq", "Sidekiq"), ("resque", "Resque")), d.messaging)
    add_markers(repo.text("go.mod"),
                (("segmentio/kafka-go", "Kafka"), ("Shopify/sarama", "Kafka"),
                 ("rabbitmq/amqp091-go", "RabbitMQ"), ("nats-io/nats.go", "NATS")),
                d.messaging)
    add_markers(repo.text("go.mod"), (("gocolly/colly", "Colly"),), d.scrape)

    # -- i18n ------------------------------------------------------------------
    for name, label in I18N_LIBS:
        if dep(name):
            add(d.i18n_libs, label)
    if repo.pydep("django") and (repo.has("locale") or "USE_I18N" in repo.text("settings.py")):
        add(d.i18n_libs, "Django i18n")
    if repo.has("config/locales"):
        add(d.i18n_libs, "Rails i18n")
    if re.search(r"\bi18n\s*:", repo.text("astro.config.mjs") + repo.text("next.config.js")
                 + repo.text("next.config.mjs") + repo.text("nuxt.config.ts")):
        add(d.i18n_libs, "framework i18n config")

    for rel in LOCALE_DIRS:
        entries = repo.subdirs(rel)
        if not entries:
            continue
        found_here = []
        for child in entries:
            m = LOCALE_RE.match(child.name)
            if m:
                code = m.group(1) if not m.group(2) else "%s-%s" % (m.group(1), m.group(2))
                found_here.append(code)
        if found_here:
            if not d.catalog:
                d.catalog = rel + "/"
            for code in found_here:
                add(d.locales, code)

    # -- the project types this repository looks like --------------------------
    types = []
    if any(f in d.fw for f in ("Astro",)):
        types.append(2)
    if any(f in d.fw for f in WEB_FRAMEWORKS if f != "Astro"):
        types.append(1)
    if any(f in d.fw for f in API_FRAMEWORKS):
        types.append(3)
    if d.dataeng:
        types.append(6)
    if d.ml or d.vector:
        types.append(7)
    if d.messaging or len(d.services) > 2 or len(
            [c for c in d.components if c[1] == "service"]) > 1:
        types.append(8)
    if d.iac:
        types.append(9)
    if d.scrape:
        types.append(10)
    if not types:
        if not d.lang:
            types = [11]
        elif d.host:
            types = [3]
        else:
            types = [4]
    d.types = sorted(set(types))
    return d


# ---------------------------------------------------------------- the wizard

BACK = "\x00back"
QUIT = "\x00quit"
OTHER = "\x00other"          # a choice option that asks for free text

PROJECT_TYPES = (
    "Web application (users sign in, there is state)",
    "Marketing or content site (public pages)",
    "API / backend service (no interface of its own)",
    "CLI tool or library",
    "Mobile app",
    "Data pipeline / warehouse / ETL",
    "AI / ML system (models, RAG, agents, prompts)",
    "Distributed system / several deployed services",
    "Infrastructure / platform / IaC",
    "Scraper / crawler / third-party data acquisition",
    "Documentation / research only (no shipped code)",
    "Something else / mixed",
)

# What each type implies. Named rather than positional: a wrong flag in an
# eleven-column tuple is invisible, and these decide who reviews the work.
TYPE_FACTS = {
    1:  ("ui", "visual", "deploy", "pii", "conv"),
    2:  ("ui", "visual", "public", "deploy", "conv"),
    3:  ("deploy", "pii"),
    4:  ("ui",),
    5:  ("ui", "visual", "deploy", "pii", "conv"),
    6:  ("deploy", "pii", "data"),
    7:  ("deploy", "pii", "ai", "data"),
    8:  ("deploy", "pii", "dist"),
    9:  ("deploy", "infra"),
    10: ("deploy", "pii", "data", "acquire"),
    11: ("public",),
    12: (),
}
FACT_IDS = ("ui", "visual", "public", "deploy", "pii", "conv",
            "data", "ai", "dist", "infra", "acquire")

FACT_LABELS = {
    "ui": "interface of any kind (incl. CLI)",
    "visual": "visual interface",
    "public": "publicly discoverable content",
    "deploy": "deployed / operated by you",
    "pii": "holds personal data",
    "conv": "conversion / activation goal",
    "data": "owns datasets, pipelines, or a warehouse",
    "ai": "models, prompts, or retrieval on the product path",
    "dist": "several services, or asynchronous messaging",
    "infra": "this repository provisions infrastructure",
    "acquire": "fetches data from third-party sources",
}

SKILL_RULES = (
    # (name, rule, why it is on, why it is off)
    ("sdlc-intake", "always", "every request: tier, ID, reading list before any code", ""),
    ("sdlc-evidence-check", "always", "fires before any 'done / passing / verified' claim", ""),
    ("sdlc-charter-audit", "always", "keeps the charter's blank and stale cells visible", ""),
    ("sdlc-adr", "always", "captures durable decisions instead of losing them", ""),
    ("sdlc-doctor", "always",
     "keeps blank, stale, and drifted project documents from being read as true", ""),
    ("sdlc-accessibility-audit", "ui", "there is an interface to audit",
     "no user interface in this project"),
    ("sdlc-design-review", "visual", "there is a visual interface to hold to the design system",
     "no visual interface"),
    ("sdlc-content-seo", "public", "content is publicly discoverable",
     "nothing is publicly discoverable"),
    ("sdlc-privacy-review", "pii", "personal data is held or processed",
     "no personal data held"),
    ("sdlc-threat-model", "pii_or_deploy", "there is an exposed or data-holding surface to model",
     "nothing deployed and no personal data"),
    ("sdlc-release", "deploy", "this deploys somewhere and needs a repeatable release",
     "nothing is deployed from here"),
    ("sdlc-postmortem", "deploy", "running software eventually has incidents",
     "nothing is operated from here"),
    ("sdlc-i18n-audit", "multilingual", "the code has to carry more than one language",
     "single language, nothing to internationalise"),
    ("sdlc-translation-review", "multilingual", "translated content needs a named reviewer",
     "single language, nothing to translate"),
    ("sdlc-managed-platform", "platform", "a platform co-owns this repository",
     "plain git repository, no co-owning platform"),
    ("sdlc-eval-gate", "ai",
     "model, prompt, and retrieval changes need a baseline before a quality claim",
     "no model, prompt, or retrieval surface"),
    ("sdlc-data-contract", "data_or_acquire",
     "something else consumes the data this project produces",
     "no dataset, table, or event is published from here"),
    ("sdlc-migration", "datalayer",
     "a data layer was detected: migrations and backfills need a reversible plan",
     "no data layer detected"),
    ("sdlc-service-contract", "dist",
     "contracts cross a service boundary and break other people's deploys",
     "one deployable unit, no cross-service contract"),
    ("sdlc-perf-budget", "workload",
     "there is a latency, throughput, or cost budget to hold a change against",
     "no backend, data, or model workload with a budget"),
    ("sdlc-scrape-compliance", "acquire",
     "third-party acquisition has legal, rate, and provenance obligations",
     "nothing is fetched from a third-party source"),
)


class Step(object):
    def __init__(self, sid, section, kind, prompt, default=None, help=None,
                 when=None, before=None, after=None, options=None, validate=None,
                 label=None, cascade=False, secret_default=None, quick=False,
                 none_ok=False):
        self.sid = sid
        self.section = section
        self.kind = kind            # text | yesno | key | choice | multichoice | dest
        self.prompt = prompt        # message key
        self.default = default      # callable(w) or literal
        self.help = help            # message key
        self.when = when            # callable(w) -> bool
        self.before = before        # callable(w)
        self.after = after          # callable(w, value)
        self.options = options      # key: allowed letters; multichoice: list of labels
        self.validate = validate    # callable(w, raw) -> (ok, value_or_message)
        self.label = label or prompt
        self.cascade = cascade      # a change here changes later questions
        self.quick = quick          # asked in Quick mode too; otherwise defaulted there
        self.none_ok = none_ok      # multichoice: 0 / none is a valid answer

    def visible(self, w):
        return self.when(w) if self.when else True

    def default_for(self, w):
        # An answer the user typed is the default when they come back to it -- otherwise
        # `b` and the review screen would silently reset what they had already decided.
        # Answers that were merely defaulted are recomputed, so changing the project name
        # still updates a derived prefix.
        if self.sid in w.explicit and self.sid in w.a:
            return w.a[self.sid]
        if callable(self.default):
            return self.default(w)
        return self.default if self.default is not None else ""


class Wizard(object):
    def __init__(self, options):
        self.o = options
        self.a = {}
        self.explicit = set()
        self.det = Detected()
        self.target = None
        self.interactive = (not options.assume_yes and not options.upgrade
                            and TERM.interactive_in)
        self.skip_section = None
        self.skip_all = False
        self.last_section = None
        self.force = None           # a step the review screen jumped to: always asked
        self.since = 0              # where the current question's lines start, for folding
        self.steps = build_steps(self)

    # -- helpers used by step defaults ----------------------------------------
    def git(self, *args):
        if not self.target:
            return ""
        try:
            out = subprocess.check_output(["git", "-C", str(self.target)] + list(args),
                                          stderr=subprocess.DEVNULL)
            return out.decode("utf-8", "replace").strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    def fact(self, name):
        return self.a.get(name, False)

    def multilingual(self):
        return bool(self.a.get("multilingual"))

    def has_workload(self):
        """A backend, data, or model workload — where a latency, throughput, or cost
        budget is load-bearing. Front-end page speed stays with seo/ux-designer, so a
        content site's roster does not grow."""
        return bool(self.fact("dist") or self.fact("data") or self.fact("ai"))

    def has_data_layer(self):
        """Detected, not declared: migrations are a risk wherever one exists, and the
        repository is better evidence for that than an answer about project type."""
        return bool(self.det.db or self.det.migrations)

    def languages(self):
        raw = self.a.get("languages", "") or ""
        return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]

    def rtl_languages(self):
        return [x for x in self.languages() if x.split("-")[0].lower() in RTL_LANGS]

    def derive_prefix(self):
        name = self.a.get("name") or (self.target.name if self.target else "")
        letters = "".join(c for c in name if c.isalpha()).upper()[:4]
        return letters if len(letters) >= 2 else "PRJ"

    def existing_docs(self):
        """An install already here: reuse it rather than building a second doc tree."""
        if not self.target:
            return ""
        for name in (self.o.docs_dir, "docs", "sdlc-docs"):
            if is_docs_root(self.target / name):
                return name
        return ""

    def recovered_prefix(self):
        found = self.existing_docs()
        if not found:
            return ""
        charter = self.target / found / "project" / "charter.md"
        if not charter.exists():
            return ""
        m = re.search(r"^\| \*\*Work item prefix\*\* \| `([A-Z]{2,4})`", 
                      charter.read_text(encoding="utf-8", errors="replace"), re.M)
        return m.group(1) if m else ""

    def skills(self, rules_only=False):
        """(name, on, why) for every skill this kit ships, judged by the answers.
        rules_only ignores a pick made at the skills question."""
        out = []
        for name, rule, why_on, why_off in SKILL_RULES:
            if not (SRC / "optional" / "skills" / name).is_dir():
                continue
            if rule == "always":
                on = True
            elif rule == "pii_or_deploy":
                on = bool(self.fact("pii") or self.fact("deploy"))
            elif rule == "multilingual":
                on = self.multilingual()
            elif rule == "platform":
                on = bool(self.a.get("platform", "none") not in ("", "none"))
            elif rule == "data_or_acquire":
                on = bool(self.fact("data") or self.fact("acquire"))
            elif rule == "workload":
                on = self.has_workload()
            elif rule == "datalayer":
                on = self.has_data_layer()
            else:
                on = bool(self.fact(rule))
            chosen = None if rules_only else self.a.get("skill:" + name)
            if chosen is not None:
                on = bool(chosen)
            out.append((name, on, why_on if on else why_off))
        return out

    def chosen_skills(self):
        if not self.o.want_skills:
            return []
        return [name for name, on, _ in self.skills() if on]

    def active_roles(self):
        roles = ["product-manager", "architect", "security", "qa"]
        if self.fact("ui"):
            roles += ["ux-designer", "accessibility"]
        if self.fact("visual"):
            roles.append("brand-designer")
        if self.fact("ui") or self.fact("public"):
            roles.append("copywriter")
        if self.fact("public"):
            roles.append("seo")
        if self.fact("conv"):
            roles.append("cro-analyst")
        if self.fact("deploy"):
            roles.append("devops-sre")
        if self.fact("data") or self.fact("acquire"):
            roles.append("data-engineer")
        if self.fact("ai"):
            roles.append("ml-engineer")
        if self.has_workload():
            roles.append("performance-engineer")
        if self.fact("pii"):
            roles.append("privacy-legal")
        if self.multilingual():
            roles.append("localisation")
        return roles

    # -- prompting -------------------------------------------------------------
    def hint(self, step):
        """The one line shown under every question, so nobody has to press ? first."""
        key = "x." + step.sid
        return t(key) if (key in _CATALOG or key in EN) else ""

    def title(self, step):
        """A typed prompt says how to type the answer ("e.g. 1,3"); a menu does not need to."""
        key = step.prompt + ".rich"
        if key in _CATALOG or key in EN:
            return t(key)
        return t(step.prompt, **self.prompt_args(step))

    def keys(self, name):
        return t("keys." + name, **TERM.g)

    def help_for(self, step):
        return t(step.help) if step.help else ""

    def show_hint(self, step):
        """Plain mode: the hint as a dim line above the prompt."""
        if not TERM.rich and self.hint(step):
            TERM.dim(self.hint(step))

    def done(self, step, value_text):
        """Rich mode: fold the finished question into one line."""
        if TERM.rich:
            label = t(step.label, **self.prompt_args(step))
            if step.label == step.prompt:            # no short label: the menu's own title
                label = self.title(step)
            TERM.collapse(self.since, label, value_text)

    def confirm_quit(self):
        r = ui.confirm(TERM, t("quit.confirm"), default=False, keys=self.keys("confirm"),
                       yes=t("yes"), no=t("no"))
        return r is True or r == ui.QUIT

    def _control(self, raw, step):
        """Universal keys. Returns (handled, result)."""
        if raw == "b":
            return True, BACK
        if raw == "q":
            return True, QUIT
        if raw == "?":
            text = self.help_for(step) or "no extra detail for this one."
            if TERM.rich:
                TERM.wrap(text, TERM.D)
            else:
                TERM.dim(text)
            return True, None            # re-ask
        if raw == "s":
            self.skip_section = step.section
            TERM.dim(t("skip.section"))
            return True, step.default_for(self)
        if raw == "S":
            self.skip_all = True
            TERM.dim(t("skip.all"))
            return True, step.default_for(self)
        return False, None

    def _widget_control(self, result, step):
        """A widget's answer that is not a value: (True, result) to return it, (True,
        None) to ask again, (False, None) when it is a value after all."""
        if result == ui.BACK:
            return True, BACK
        if result == ui.QUIT:
            return True, QUIT
        if result == ui.SKIP:
            self.skip_section = step.section
            return True, step.default_for(self)
        if result == ui.SKIP_ALL:
            self.skip_all = True
            return True, step.default_for(self)
        return False, None

    def mode(self):
        return self.a.get("mode") or self.o.mode

    def quick(self):
        return self.mode() == "quick"

    def custom_sections(self):
        if self.o.sections:
            return set(self.o.sections)
        return set(SECTION_KEYS[i - 1] for i in (self.a.get("sections") or [])
                   if 1 <= i <= len(SECTION_KEYS))

    def _outside_custom(self, step):
        return (self.mode() == "custom" and step.section not in ("sec.dest", "sec.mode")
                and step.section not in self.custom_sections())

    def _skipping(self, step):
        if self.interactive and self.force is step:
            return False
        return (not self.interactive or self.skip_all
                or (self.quick() and not step.quick)
                or self._outside_custom(step)
                or (self.skip_section and self.skip_section == step.section))

    def progress(self, section):
        """'3 of 9' for a section header: only the sections that will actually ask."""
        order = []
        for st in self.steps:
            if st.section in ("sec.mode", "sec.dest") or not st.visible(self):
                continue
            if self.quick() and not st.quick:
                continue
            if self._outside_custom(st):
                continue
            if st.section not in order:
                order.append(st.section)
        if section not in order:
            return ""
        return t("progress", n=order.index(section) + 1, total=len(order))

    def ask(self, step):
        if step.kind == "dest" and self.target:      # given on the command line
            return str(self.target)
        if step.section != self.last_section and self.interactive and not self._skipping(step):
            TERM.head(t(step.section), self.progress(step.section))
            self.last_section = step.section
        self.since = TERM.mark()
        if step.before and self.interactive and not self._skipping(step):
            step.before(self)
        if self._skipping(step):
            return step.default_for(self)
        handler = {
            "dest": self.ask_dest,
            "text": self.ask_text,
            "yesno": self.ask_yesno,
            "key": self.ask_key,
            "choice": self.ask_choice,
            "multichoice": self.ask_multi,
            "show": lambda st: "",
        }[step.kind]
        while True:
            value = handler(step)
            # A stray q in the arrow-key setup should not throw away every answer.
            if value == QUIT and TERM.rich and not self.confirm_quit():
                self.since = TERM.mark()
                continue
            return value

    def _text_prompt(self):
        return "%s%s%s  %s%s%s" % (TERM.D, TERM.g["bar"], TERM.R, TERM.C, TERM.g["pointer"], TERM.R)

    def ask_text(self, step):
        default = step.default_for(self)
        if TERM.rich:
            TERM.title(self.title(step), self.hint(step))
        self.show_hint(step)
        while True:
            if TERM.rich:
                raw = TERM.read(self._text_prompt(), default if default else "blank", lead="")
            else:
                raw = TERM.read(t(step.prompt), default if default else "blank")
            if raw is None:
                return QUIT
            handled, result = self._control(raw, step)
            if handled:
                if result is None:
                    continue
                return result
            value = default if raw == "" else ("" if raw == "-" else raw)
            if raw != "":
                self.explicit.add(step.sid)
            if step.validate:
                ok, out = step.validate(self, value)
                if not ok:
                    if TERM.rich:
                        TERM.bar("%s%s %s" % (TERM.Y, TERM.g["warn"], out), "")
                    else:
                        TERM.dim(out)
                    continue
                value = out
            self.done(step, value if value != "" else "(blank)")
            return value

    def ask_yesno(self, step):
        default = bool(step.default_for(self))
        if TERM.rich:
            while True:
                r = ui.confirm(TERM, self.title(step), default=default,
                               hint=self.hint(step), help_text=self.help_for(step),
                               keys=self.keys("confirm"), yes=t("yes"), no=t("no"))
                handled, result = self._widget_control(r, step)
                if handled:
                    return result
                if r != default:
                    self.explicit.add(step.sid)
                self.done(step, t("yes") if r else t("no"))
                return r
        hint = "Y/n" if default else "y/N"
        self.show_hint(step)
        while True:
            raw = TERM.read(t(step.prompt, **self.prompt_args(step)), hint)
            if raw is None:
                return QUIT
            handled, result = self._control(raw, step)
            if handled:
                if result is None:
                    continue
                return result
            if raw == "":
                return default
            if raw.lower() in ("y", "yes"):
                self.explicit.add(step.sid)
                return True
            if raw.lower() in ("n", "no"):
                self.explicit.add(step.sid)
                return False
            TERM.dim(t("err.answer_yn", default="y" if default else "n"))

    def ask_key(self, step):
        default = step.default_for(self)
        if TERM.rich:
            menu = [opt for opt in KEY_MENU if opt[0] in step.options]
            index = [opt[0] for opt in menu].index(default) if default in step.options else 0
            r = ui.select(TERM, self.title(step), [
                (t(name), t(desc), t("recommended") if key == "y" else "")
                for key, name, desc in menu], default=index, hint=self.hint(step),
                help_text=self.help_for(step), keys=self.keys("select"))
            handled, result = self._widget_control(r, step)
            if handled:
                return result
            value = menu[r][0]
            if value != default:
                self.explicit.add(step.sid)
            self.done(step, t(menu[r][1]))
            return value
        self.show_hint(step)
        while True:
            raw = TERM.read(t(step.prompt), default)
            if raw is None:
                return QUIT
            handled, result = self._control(raw, step)
            if handled:
                if result is None:
                    continue
                return result
            if raw == "":
                return default
            if raw in step.options:
                self.explicit.add(step.sid)
                return raw
            TERM.dim(t("err.answer_keys", keys="/".join(step.options)))

    def choice_options(self, step):
        return step.options(self) if callable(step.options) else step.options

    def choice_name(self, step, value):
        for opt in self.choice_options(step):
            if opt[0] == value:
                return opt[1]
        return str(value) if value not in ("", None) else "(blank)"

    def multi_items(self, step):
        """(name, description) for each option of a multichoice step."""
        items = []
        for opt in self.choice_options(step):
            if isinstance(opt, tuple):
                items.append((opt[0], opt[1]))
                continue
            m = re.match(r"^(.*?) \((.*)\)$", opt)
            items.append((m.group(1), m.group(2)) if m else (opt, ""))
        return items

    def ask_choice(self, step):
        """A menu: every option with what it means, the recommended one marked. Typed, it
        accepts the number, the option's name, or its old one-letter key."""
        default = step.default_for(self)
        options = self.choice_options(step)
        if TERM.rich:
            values = [o[0] for o in options]
            if default in values:
                index = values.index(default)
            elif default not in ("", None) and OTHER in values:
                index = values.index(OTHER)
            else:
                index = 0
            r = ui.select(TERM, self.title(step), [
                (name, desc, t("recommended") if rec else "")
                for _, name, desc, rec in options], default=index, hint=self.hint(step),
                help_text=self.help_for(step), keys=self.keys("select"))
            handled, result = self._widget_control(r, step)
            if handled:
                return result
            picked = values[r]
            if picked == OTHER:
                typed = TERM.read("%s %s" % (self._text_prompt(), t("q.other")),
                                  default if default not in values else "blank", lead="")
                if typed is None:
                    return QUIT
                picked = typed.strip() or (default if default not in values else "")
            if r != index or picked != default:
                self.explicit.add(step.sid)
            self.done(step, options[r][1] if picked in values else picked)
            return picked
        width = max(len(o[1]) for o in options)
        for i, (value, name, desc, rec) in enumerate(options):
            mark = ("  " + t("recommended")) if rec else ""
            TERM.say("    %s%d%s  %-*s  %s%s%s%s" % (TERM.D, i + 1, TERM.R, width, name,
                                                   TERM.D, desc, mark, TERM.R))
        hint = None
        for i, opt in enumerate(options):
            if opt[0] == default:
                hint = "%d %s" % (i + 1, opt[1])
        if hint is None and default not in ("", None):
            hint = str(default)
        self.show_hint(step)
        while True:
            raw = TERM.read(t(step.prompt, **self.prompt_args(step)), hint or "blank")
            if raw is None:
                return QUIT
            handled, result = self._control(raw, step)
            if handled:
                if result is None:
                    continue
                return result
            if raw == "":
                return default
            picked = None
            low = raw.strip().lower()
            if low.isdigit() and 1 <= int(low) <= len(options):
                picked = options[int(low) - 1][0]
            else:
                for value, name, _, _ in options:
                    if low in (str(value).lower(), name.lower(), name.split(" ")[0].lower()):
                        picked = value
                        break
            if picked is None:
                TERM.dim(t("err.choice", max=len(options)))
                continue
            if picked == OTHER:
                typed = TERM.read(t("q.other"), "blank")
                if typed is None:
                    return QUIT
                picked = typed.strip()
            self.explicit.add(step.sid)
            return picked

    def ask_multi(self, step):
        default = step.default_for(self)          # list of ints, 1-based
        items = self.multi_items(step)
        if TERM.rich:
            r = ui.multiselect(TERM, self.title(step),
                               [(name, desc, "") for name, desc in items],
                               default=[i - 1 for i in default], hint=self.hint(step),
                               help_text=self.help_for(step), keys=self.keys("multi"),
                               none_ok=step.none_ok, need_one=t("multi.need_one"),
                               filter_label=t("multi.no_match"))
            handled, result = self._widget_control(r, step)
            if handled:
                return result
            picked = [i + 1 for i in r]
            if picked != sorted(default):
                self.explicit.add(step.sid)
            self.done(step, ", ".join(items[i - 1][0] for i in picked) or t("none.word"))
            return picked
        for i, (name, desc) in enumerate(items):
            TERM.say("    %s%2d%s  %s%s" % (TERM.D, i + 1, TERM.R, name,
                                            (" (%s)" % desc) if desc else ""))
        if step.none_ok:
            TERM.say("    %s%2d%s  %s" % (TERM.D, 0, TERM.R, t("none.option")))
        self.show_hint(step)
        while True:
            hint = ",".join(str(x) for x in default)
            if not hint and step.none_ok:
                hint = "0 " + t("none.word")
            raw = TERM.read(t(step.prompt), hint)
            if raw is None:
                return QUIT
            handled, result = self._control(raw, step)
            if handled:
                if result is None:
                    continue
                return result
            if raw == "":
                if not default and not step.none_ok:
                    TERM.dim(t("err.number_range", max=len(items)))
                    continue
                return default
            if step.none_ok and raw.strip().lower() in ("0", "none"):
                self.explicit.add(step.sid)
                return []
            picked, bad = [], False
            for part in re.split(r"[\s,]+", raw.strip()):
                if not part:
                    continue
                if not part.isdigit() or not (1 <= int(part) <= len(items)):
                    bad = True
                    break
                if int(part) not in picked:
                    picked.append(int(part))
            if bad or not picked:
                TERM.dim(t("err.number_range", max=len(items)))
                continue
            self.explicit.add(step.sid)
            return sorted(picked)

    def ask_dest(self, step):
        if self.target:                            # given on the command line
            return str(self.target)
        if TERM.rich:
            TERM.title(t("q.dest"), self.hint(step))
        self.show_hint(step)
        while True:
            if TERM.rich:
                raw = TERM.read(self._text_prompt(), "required", lead="")
            else:
                raw = TERM.read(t("q.dest"), "required")
            if raw is None:
                return QUIT
            if raw in ("q",):
                return QUIT
            if raw == "?":
                (TERM.wrap if TERM.rich else TERM.dim)(t("h.dest"))
                continue
            if raw == "":
                TERM.dim(t("err.required"))
                continue
            path = os.path.expanduser(raw)
            if not os.path.isdir(path):
                if TERM.rich:
                    answer = ui.confirm(TERM, t("q.create", path=path), default=True,
                                        keys=self.keys("confirm"), yes=t("yes"), no=t("no"))
                    if answer == ui.QUIT:
                        return QUIT
                    if answer is not True:
                        continue
                else:
                    answer = TERM.read(t("q.create", path=path), "Y/n")
                    if answer is None:
                        return QUIT
                    if answer.lower() in ("n", "no"):
                        continue
                self.o.create = True
            resolved = resolve_target(path, self.o, TERM)
            if resolved:
                self.target = resolved
                if TERM.rich:
                    TERM.collapse(self.since, t("l.dest"), str(resolved))
                else:
                    TERM.dim("-> %s" % resolved)
                return str(resolved)

    def prompt_args(self, step):
        if step.sid in ("direct", "l.direct"):
            return {"branch": self.a.get("branch", "the default branch")}
        if step.sid == "commands":
            return {"n": len(list((SRC / "optional" / "claude-commands").glob("*.md")))}
        return {}

    # -- the loop --------------------------------------------------------------
    def visible_indexes(self):
        return [i for i, st in enumerate(self.steps) if st.visible(self)]

    def run(self, start=0, single=False):
        idx = start
        while idx < len(self.steps):
            step = self.steps[idx]
            if not step.visible(self):
                idx += 1
                continue
            self.force = step if single else None
            value = self.ask(step)
            self.force = None
            if value == QUIT:
                return False
            if value == BACK:
                self.skip_section, self.skip_all = None, False
                previous = [i for i in self.visible_indexes() if i < idx]
                if not previous:
                    TERM.dim(t("err.at_start"))
                    continue
                idx = previous[-1]
                self.last_section = None
                continue
            self.a[step.sid] = value
            if step.after:
                step.after(self, value)
            if single and not step.cascade:
                return True
            single = False
            idx += 1
        return True

    def display(self, step):
        value = self.a.get(step.sid, "")
        if step.sid == "effort":
            return EFFORT_KEYS.get(value, "Normal")
        if step.sid == "acquisition":
            return ACQUISITION_KEYS.get(value, "Standard")
        if step.sid == "devmethod":
            return DEV_METHOD_KEYS.get(value, "Item")
        if step.sid == "decision":
            return DECISION_KEYS.get(value, "Guide")
        if step.kind == "choice":
            if step.sid in ("access_model", "mfa_policy", "platform"):   # the value is the wording
                return str(value) if value else "(blank)"
            return self.choice_name(step, value)
        if isinstance(value, bool):
            return "yes" if value else "no"
        if step.sid == "skills_pick" and isinstance(value, list):
            return "%d of %d" % (len(value), len(self.multi_items(step)))
        if isinstance(value, list):
            if step.kind == "multichoice":
                if not value:
                    return t("none.word")
                items = self.multi_items(step)
                return ", ".join(items[i - 1][0] for i in value if 1 <= i <= len(items))
            return ", ".join(str(x) for x in value)
        return str(value) if str(value) != "" else "(blank)"

    def review_rows(self):
        """(step index, section, label, value) for every answer the review lists."""
        rows = []
        for i in self.visible_indexes():
            step = self.steps[i]
            if (step.kind in ("key", "show") or step.sid in ("mode", "sections")
                    or step.sid in ("stack_pick", "cmds_pick")
                    or step.sid.startswith("skill:")):
                continue
            rows.append((i, step.section, t(step.label, **self.prompt_args(step)),
                         self.display(step)))
        return rows

    def print_review(self, rows):
        width = max(12, min(self.term_cols() - 46, 60))
        section = None
        for n, (i, sec, label, value) in enumerate(rows, 1):
            if sec != section:
                section = sec
                TERM.say("  %s%s%s" % (TERM.D, t(sec), TERM.R))
            if len(label) > 34:
                label = label[:31] + "..."
            if len(value) > width:
                # A path is recognised by its end; anything else by its start.
                value = ("..." + value[-(width - 3):]) if self.steps[i].kind == "dest" \
                    else (value[:width - 3] + "...")
            TERM.say("   %2d  %-34s %s" % (n, label, value))
        for line in (textwrap.wrap("roles: " + ", ".join(self.active_roles()),
                                   max(40, self.term_cols() - 6), subsequent_indent="  ")
                     + textwrap.wrap("skills: " + (", ".join(self.chosen_skills()) or "none"),
                                     max(40, self.term_cols() - 6), subsequent_indent="  ")):
            TERM.say("  %s%s%s" % (TERM.D, line, TERM.R))
        TERM.say("")
        TERM.dim(t("review.command"))
        TERM.say("    %s" % equivalent_command(self))

    @staticmethod
    def term_cols():
        return shutil.get_terminal_size((80, 24)).columns

    def show_files(self):
        new, kept = preview_files(self)
        TERM.head(t("files.title", path=self.target))
        for line in file_tree(new):
            TERM.say("    " + line)
        if kept:
            TERM.dim(t("files.kept"))
            for line in file_tree(kept)[:8]:
                TERM.say("    %s%s%s" % (TERM.D, line, TERM.R))
        TERM.dim(t("files.summary", new=len(new), kept=len(kept)))
        return new

    def review(self):
        """None = write, QUIT = abandon, int = the step index to revisit."""
        if not self.interactive:
            return None
        while True:
            rows = self.review_rows()
            TERM.head(t("review.rich_title" if TERM.rich else "review.title"))
            self.print_review(rows)
            if TERM.rich:
                choice = self.review_menu(rows)
                if choice == "files":
                    self.show_files()
                    TERM.read(t("files.back"))
                    continue
                return choice
            raw = TERM.read(t("review.prompt"), "write")
            if raw is None:
                TERM.say("")
                TERM.say("  " + t("review.eof"))
                return QUIT
            if raw == "":
                return None
            if raw.lower() in ("q", "quit", "n"):
                return QUIT
            if raw.lower() == "f":
                self.show_files()
                continue
            if raw.isdigit() and 1 <= int(raw) <= len(rows):
                return rows[int(raw) - 1][0]
            TERM.dim(t("review.bad"))

    def review_menu(self, rows):
        """The review's actions as a menu, and "change" as a second menu over the rows."""
        new, _ = preview_files(self)
        actions = [(t("review.write"), t("review.write_desc", new=len(new)), t("recommended")),
                   (t("review.change"), "", ""),
                   (t("review.files"), t("review.files_desc"), ""),
                   (t("review.quit_opt"), t("review.quit_desc"), "")]
        while True:
            TERM.say("")
            r = ui.select(TERM, t("review.rich_title"), actions, default=0,
                          hint=t("review.rich_hint"), keys=self.keys("select"))
            if r == 0:
                return None
            if r == 2:
                return "files"
            if r in (3, ui.QUIT):
                if self.confirm_quit():
                    return QUIT
                continue
            if r == 1:
                pick = ui.select(TERM, t("review.change"), [
                    ("%2d  %s" % (n, label), value, "")
                    for n, (_, _, label, value) in enumerate(rows, 1)], default=0,
                    keys=self.keys("select"))
                if isinstance(pick, int):
                    return rows[pick][0]


# ---------------------------------------------------------------- the steps

STACK_FIELDS = (("s_lang", "q.lang", "lang"), ("s_pm", "q.pm", "pm"),
                ("s_fw", "q.fw", "fw"), ("s_db", "q.db", "db"),
                ("s_auth", "q.auth", "auth"), ("s_host", "q.host", "host"),
                ("s_ci", "q.ci", "ci"), ("s_test", "q.test", "test"))

CMD_FIELDS = (("c_install", "q.c_install", "install"), ("c_run", "q.c_run", "run"),
              ("c_format", "q.c_format", "format"), ("c_lint", "q.c_lint", "lint"),
              ("c_typecheck", "q.c_typecheck", "typecheck"), ("c_unit", "q.c_unit", "unit"),
              ("c_integration", "q.c_integration", "integration"),
              ("c_contract", "q.c_contract", "contract"),
              ("c_build", "q.c_build", "build"), ("c_scan", "q.c_scan", "scan"),
              ("c_a11y", "q.c_a11y", "a11y"),
              ("c_e2e", "q.c_e2e", "e2e"),
              ("c_infra", "q.c_infra", "infra"), ("c_data", "q.c_data", "data"),
              ("c_eval", "q.c_eval", "eval"), ("c_perf", "q.c_perf", "perf"),
              ("c_complexity", "q.c_complexity", "complexity"),
              ("c_mutation", "q.c_mutation", "mutation"))

EFFORT_KEYS = {"l": "Lean", "n": "Normal", "x": "Beast"}
ACQUISITION_KEYS = {"s": "Standard", "a": "Advanced"}
DEV_METHOD_KEYS = {"i": "Item", "e": "Epic"}
DECISION_KEYS = {"a": "Ask", "g": "Guide", "p": "Autopilot"}


# Presets set four charter rows together. An explicit flag always wins over the preset,
# whatever the order on the command line. Presets apply to new installs only: --upgrade
# keeps whatever the project's charter already says.
PRESETS = {
    "solo": {"effort_mode": "lean", "decision_style": "guide", "dev_method": "item",
             "tier_rules": "standard"},
    "team": {"effort_mode": "normal", "decision_style": "guide", "dev_method": "item",
             "tier_rules": "standard"},
    "regulated": {"effort_mode": "normal", "decision_style": "ask", "dev_method": "item",
                  "tier_rules": "strict"},
}
PRESET_HELP = {
    "solo": "one person moving fast: lean effort, the agent recommends and you decide",
    "team": "several people, normal depth -- the kit's own defaults",
    "regulated": "audited or high-stakes work: every material choice asked, strict tiers",
}

# Menus for the guided setup: (stored value, name, what it means, recommended). The stored
# values are the ones the charter writers already read, so a menu changes only the asking.
MODE_OPTIONS = (
    ("quick", "Use these settings", "asks 4 things it cannot detect, then shows every answer for review", True),
    ("custom", "Customise", "pick which sections to go through; the rest keep the settings above", False),
    ("full", "Every question", "all ten sections, about 40 questions, each one explained", False),
)
# The sections a Customise run can pick, in the order they are asked.
SECTION_KEYS = tuple("sec." + sid for sid in SECTION_IDS)
# The confirm-a-table questions as a menu: (stored key, name key, description key).
KEY_MENU = (
    ("y", "k.use", "k.use_desc"),
    ("e", "k.edit", "k.edit_desc"),
    ("n", "k.blank", "k.blank_desc"),
)
PRESET_OPTIONS = tuple((name, name.capitalize(), PRESET_HELP[name], name == "team")
                       for name in ("solo", "team", "regulated"))
EFFORT_OPTIONS = (
    ("l", "Lean", "least optional work: fastest and cheapest", False),
    ("n", "Normal", "balanced investigation and review", True),
    ("x", "Beast", "maximum investigation and verification; slowest", False),
)
DEV_METHOD_OPTIONS = (
    ("i", "Item", "one work item at a time, approvals at each", True),
    ("e", "Epic", "plan several items together, one plan approval, chosen checkpoints", False),
)
DECISION_OPTIONS = (
    ("a", "Ask", "every material choice put to you, with options and trade-offs", False),
    ("g", "Guide", "recommends in plain language, then asks you", True),
    ("p", "Autopilot", "takes the recommended option and logs it for your review", False),
)
TIER_OPTIONS = (
    ("standard", "Standard", "weight by blast radius: small low-risk changes stay light", True),
    ("strict", "Strict", "the 3.x rules: a full record for every tier", False),
)
ACQUISITION_OPTIONS = (
    ("s", "Standard", "ordinary fetching of sources that permit it", True),
    ("a", "Advanced", "browser automation, OCR, session flows -- authorised targets only", False),
)
PROFILE_OPTIONS = (
    ("full", "Full", "every process document (about 22k tokens read per change)", True),
    ("compact", "Compact", "the one-page card instead (about 8k); small context windows", False),
)
ENFORCE_OPTIONS = (
    ("none", "None", "the agent follows the rules by instruction only", True),
    ("claude", "Agent hooks", "Claude Code refuses commits without an ID, credentials, protected edits", False),
    ("git", "Git hooks", "git itself refuses staged credentials and ID-less commits, for every tool", False),
    ("both", "Both", "agent hooks and git hooks", False),
)
GIT_TOOLS_OPTIONS = (
    ("commit", "Commit", ".ai-sdlc/ (manifest, runtime) is versioned with the project", True),
    ("gitignore", "Ignore", "add .ai-sdlc/ to .gitignore -- teammates will not get it", False),
    ("exclude", "Ignore locally", "add it to .git/info/exclude; .gitignore is left alone", False),
)
CI_OPTIONS = (
    ("none", "None", "no CI file is written", True),
    ("github", "GitHub Actions", "a manual-only workflow running the confirmed check commands", False),
    ("gitlab", "GitLab CI", "the same, as .gitlab-ci.yml", False),
)
ACCESS_OPTIONS = (
    ("Role-Based (RBAC)", "Role-Based (RBAC)", "users hold roles; roles grant permissions", False),
    ("Simple Owner/User", "Simple Owner/User", "an owner and ordinary users", False),
    ("Multi-tenant Workspace-Scoped", "Multi-tenant", "every record belongs to a workspace or tenant", False),
    ("ABAC/ReBAC", "ABAC/ReBAC", "attribute- or relationship-based rules", False),
    ("None (Public)", "None (Public)", "no sign-in, nothing private", False),
    (OTHER, "Other", "type your own", False),
)
PLATFORM_OPTIONS = (
    ("none", "None", "a plain repository; only you and your agents change it", True),
    ("Lovable", "Lovable", "AI app builder that edits and syncs this repo", False),
    ("Replit", "Replit", "cloud IDE with its own agent and deploys", False),
    ("Bolt", "Bolt", "AI app builder (.bolt/)", False),
    ("Firebase-Studio", "Firebase Studio", "Google's cloud IDE, formerly IDX (.idx/)", False),
    ("Glitch", "Glitch", "hosted editor that runs the app", False),
    ("CodeSandbox", "CodeSandbox", "cloud sandbox that syncs the repo", False),
    (OTHER, "Other", "type its name", False),
)
MFA_OPTIONS = (
    ("Optional / User-enabled", "Optional", "users may turn it on", False),
    ("Enforced for Admin/Privileged only", "Admins only", "required for privileged accounts", False),
    ("Enforced for all users", "Everyone", "required for every account", False),
    ("Not required", "Not required", "no second factor", False),
    (OTHER, "Other", "type your own", False),
)


def apply_preset(o):
    if not o.preset:
        return
    for field, given in (("effort_mode", "effort_given"), ("decision_style", "decision_given"),
                         ("dev_method", "dev_method_given"), ("tier_rules", "tier_rules_given")):
        if not getattr(o, given):
            setattr(o, field, PRESETS[o.preset][field])
            setattr(o, given, True)


def preset_field(w, field):
    """A flag wins, then the preset chosen in setup, then the kit default."""
    given = {"effort_mode": "effort_given", "decision_style": "decision_given",
             "dev_method": "dev_method_given", "tier_rules": "tier_rules_given"}[field]
    if getattr(w.o, given):
        return getattr(w.o, field)
    if w.a.get("preset") in PRESETS:
        return PRESETS[w.a["preset"]][field]
    return getattr(w.o, field)


def selected_tier_rules(w):
    raw = w.a.get("tier") or w.o.tier_rules
    return {"standard": "Standard", "strict": "Strict"}.get(raw, "Standard")


def selected_independent_review(w):
    raw = w.o.independent_review
    return {"none": "none", "tier1": "Tier 1", "tier1-2": "Tier 1 and 2"}.get(raw, "Tier 1")


def harness_options():
    return [HARNESS_TITLES[n] for n in HARNESS_ORDER] + [
        "Codex, Jules, Zed, Factory, opencode, Antigravity (read AGENTS.md directly)"]


def default_harness(w):
    if not w.interactive or not w.target:
        return [1]
    found = [i + 1 for i, name in enumerate(HARNESS_ORDER)
             if any((w.target / rel).exists() for rel in HARNESS_MARKERS.get(name, ()))]
    return found or [1]


def after_harness(w, picked):
    names = [HARNESS_ORDER[i - 1] for i in picked if 1 <= i <= len(HARNESS_ORDER)]
    w.a["harnesses"] = names
    w.o.native_harnesses = ["codex"] if (len(HARNESS_ORDER) + 1) in picked else []


def after_profile(w, value):
    w.o.profile = value


def after_enforce(w, value):
    w.o.hooks = value in ("claude", "both")
    w.o.git_hooks = "all" if value in ("git", "both") else ""


def after_git_tools(w, value):
    w.o.gitignore_tools = value == "gitignore"
    w.o.git_exclude = value == "exclude"


def after_scaffold_tests(w, value):
    w.o.scaffold_tests = bool(value)


def after_scaffold_ci(w, value):
    w.o.scaffold_ci = "" if value == "none" else value


def preview_files(w):
    """(new, kept): the paths an install with these answers would add, and the ones it
    would leave because they exist -- from the same code path as --dry-run, so the
    preview cannot drift from what is written."""
    import contextlib
    import io
    saved, w.o.dry_run = w.o.dry_run, True
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            inst = Installer(w)
            inst.run()
            inst.scaffold()
            inst.install_hooks()
            inst.install_git_hooks()
    except (IOError, OSError, RuntimeError, ValueError):
        pass
    finally:
        w.o.dry_run = saved
    new, kept = [], []
    for line in out.getvalue().splitlines():
        m = re.match(r"^\s+(would add|skip \(exists\))\s+(\S.*)$", line)
        if m:
            (new if m.group(1) == "would add" else kept).append(m.group(2).strip())
    return new, kept


def file_tree(paths):
    """Paths folded to folders with counts: 'docs/process/  14 files'."""
    groups = []
    counts = {}
    for rel in paths:
        parts = rel.split("/")
        key = rel if len(parts) == 1 else "/".join(parts[:2]) + ("/" if len(parts) > 2 else "")
        if len(parts) == 2:
            key = parts[0] + "/"
        if key not in counts:
            groups.append(key)
            counts[key] = 0
        counts[key] += 1
    width = max([len(k) for k in groups] or [0])
    return ["%-*s  %s" % (width, k, ("%d files" % counts[k]) if counts[k] > 1 else
                          ("1 file" if k.endswith("/") else "")) for k in groups]


def equivalent_command(w):
    """The same install choices as flags, so a setup can be repeated or scripted. -y does
    not carry the charter's free-text answers -- those live in the charter itself."""
    import shlex
    a, o = w.a, w.o
    parts = ["./install.sh", shlex.quote(str(w.target or "<project>")),
             a.get("prefix") or o.prefix or "<PREFIX>", "-y"]
    docs = a.get("docsdir") or o.docs_dir
    if docs != "docs":
        parts += ["--docs-dir", shlex.quote(docs)]
    names = a.get("harnesses")
    if names is None:
        names = ["claude"] if o.harnesses is None else list(o.harnesses)
    names = list(names) + list(o.native_harnesses)
    if names != ["claude"] and names:
        parts += ["--harness", ",".join(names)]
    if w.fact("deploy") or o.deploy is not None:
        parts += ["--deploy", ",".join(selected_platforms(w)) or "none"]
    chosen = {"effort_mode": selected_effort(w).lower(),
              "decision_style": selected_decision(w).lower(),
              "dev_method": selected_dev_method(w).lower(),
              "tier_rules": selected_tier_rules(w).lower()}
    preset = a.get("preset") or o.preset
    if preset in PRESETS and PRESETS[preset] == chosen:
        if preset != "team":
            parts += ["--preset", preset]
    else:
        defaults = {"effort_mode": "normal", "decision_style": "guide",
                    "dev_method": "item", "tier_rules": "standard"}
        for field, flag in (("effort_mode", "--effort-mode"), ("decision_style", "--decision-style"),
                            ("dev_method", "--dev-method"), ("tier_rules", "--tier-rules")):
            if chosen[field] != defaults[field]:
                parts += [flag, chosen[field]]
    if selected_acquisition(w) == "Advanced":
        parts += ["--acquisition-profile", "advanced"]
    if o.profile == "compact":
        parts += ["--profile", "compact"]
    if not o.want_skills or a.get("skills_pick") == []:
        parts.append("--no-skills")
    if o.hooks:
        parts.append("--hooks")
    if o.git_hooks:
        parts += ["--git-hooks"] + (["secrets"] if o.git_hooks == "secrets" else [])
    if o.gitignore_tools:
        parts.append("--gitignore-tools")
    if o.git_exclude:
        parts.append("--git-exclude")
    if o.scaffold_tests:
        parts.append("--scaffold-tests")
    if o.scaffold_ci:
        parts += ["--scaffold-ci", o.scaffold_ci]
    return " ".join(parts)


def selected_effort(w):
    raw = w.a.get("effort") or {"lean": "l", "normal": "n", "beast": "x"}.get(
        w.o.effort_mode, "n")
    return EFFORT_KEYS.get(raw, "Normal")


def selected_dev_method(w):
    raw = w.a.get("devmethod") or {"item": "i", "epic": "e"}.get(w.o.dev_method, "i")
    return DEV_METHOD_KEYS.get(raw, "Item")


def selected_decision(w):
    raw = w.a.get("decision") or {"ask": "a", "guide": "g", "autopilot": "p"}.get(
        w.o.decision_style, "g")
    return DECISION_KEYS.get(raw, "Guide")


def selected_acquisition(w):
    raw = w.a.get("acquisition") or {"standard": "s", "advanced": "a"}.get(
        w.o.acquisition_profile, "s")
    return ACQUISITION_KEYS.get(raw, "Standard")


def seed_from_detection(w):
    """Detected values become answers, so the review screen and the writers read one place."""
    for sid, _, field in STACK_FIELDS:
        if sid not in w.explicit:
            w.a[sid] = w.det.csv(field)
    for sid, _, key in CMD_FIELDS:
        if sid not in w.explicit:
            w.a[sid] = w.det.cmds.get(key, "")


def after_dest(w, value):
    if not w.target:
        return
    w.det = detect(w.target)
    seed_from_detection(w)
    if "types" not in w.explicit:
        w.a["types"] = w.det.types
        after_types(w, w.det.types)


def after_types(w, types):
    for fid in FACT_IDS:
        if fid in w.explicit:
            continue
        w.a[fid] = any(fid in TYPE_FACTS.get(t, ()) for t in types)


def after_stack_ok(w, value):
    if value == "n":
        for sid, _, _ in STACK_FIELDS:
            w.a[sid] = ""
    elif value == "y":
        seed_from_detection(w)


def after_cmds_ok(w, value):
    if value == "n":
        for sid, _, _ in CMD_FIELDS:
            w.a[sid] = ""
    elif value == "y":
        seed_from_detection(w)


def skill_items(w):
    return [(name, why if on else "off: " + why) for name, on, why in w.skills(rules_only=True)]


def default_skills(w):
    return [i for i, (_, on, _) in enumerate(w.skills(rules_only=True), 1) if on]


def after_skills_pick(w, picked):
    """A deliberate pick pins every skill on or off; an untouched one leaves them to the
    rules, so a later change of project type still changes the skills."""
    for i, (name, _, _) in enumerate(w.skills(rules_only=True), 1):
        key = "skill:" + name
        if "skills_pick" in w.explicit:
            w.a[key] = i in picked
        elif key in w.a:
            del w.a[key]


def after_facts_pick(w, picked):
    if "facts_pick" not in w.explicit:
        return
    for i, fid in enumerate(FACT_IDS, 1):
        w.a[fid] = i in picked
        w.explicit.add(fid)


def show_plan(w):
    """The start screen: what detection found and what the recommended settings would
    install, so the first decision is made with the outcome in view."""
    if not w.target:
        return
    a, o, g = w.a, w.o, TERM.g
    dot = " %s " % g["dot"]
    name = a.get("name") or w.target.name
    prefix = o.prefix or w.recovered_prefix() or w.derive_prefix()
    types = [PROJECT_TYPES[i - 1].split(" (")[0] for i in (a.get("types") or w.det.types)]
    if o.harnesses is None:
        tools = [harness_options()[i - 1].split(" (")[0] for i in default_harness(w)]
    else:
        tools = [HARNESS_TITLES.get(n, n) for n in o.harnesses]
    stack = dot.join(a.get(sid) for sid in ("s_lang", "s_pm", "s_fw", "s_db") if a.get(sid))
    found = [key for sid, _, key in CMD_FIELDS if a.get(sid)]
    preset = o.preset or "team"
    on = [s for s in w.skills(rules_only=True) if s[1]]
    docs = default_docsdir(w)
    rows = [
        (t("plan.name"), "%s  (%s-1, %s-2, ...)" % (name, prefix, prefix)),
        (t("plan.types"), ", ".join(types) or t("plan.nothing")),
        (t("plan.tools"), ", ".join(tools)),
        (t("plan.stack"), stack or t("plan.nothing")),
        (t("plan.checks"), t("plan.checks_value", n=len(found), names=", ".join(found))
         if found else t("plan.checks_none")),
    ]
    if w.det.deploy:
        rows.append((t("plan.deploy"), ", ".join(DEPLOY_LABELS.get(p, p) for p in w.det.deploy)))
    if w.det.platforms:
        rows.append((t("plan.platform"), ", ".join(w.det.platforms)))
    rows += [
        (t("plan.style"), "%s: %s" % (preset.capitalize(), PRESET_HELP[preset])),
        (t("plan.roles"), "%d: %s" % (len(w.active_roles()), ", ".join(w.active_roles()))),
        (t("plan.skills"), t("plan.skills_value", n=len(on), total=len(w.skills(rules_only=True)))),
        (t("plan.writes"), "AGENTS.md, %s/, .ai-sdlc/, .claude/commands/, .claude/skills/" % docs),
    ]
    width = max(len(r[0]) for r in rows)
    if TERM.rich:
        TERM.title(t("plan.title"), t("plan.found", path=w.target))
        for label, value in rows:
            TERM.bar("%-*s  %s%s" % (width, label, TERM.B, value), "")
        if w.existing_docs():
            TERM.bar(t("plan.existing"), TERM.Y)
        TERM.bar()
    else:
        TERM.dim(t("plan.title") + " -- " + t("plan.found", path=w.target))
        for label, value in rows:
            TERM.say("    %-*s  %s" % (width, label, value))
        if w.existing_docs():
            TERM.dim(t("plan.existing"))


def show_facts(w):
    TERM.dim(t("hint.facts"))
    for fid in FACT_IDS:
        width = max(len(v) for v in FACT_LABELS.values())
        TERM.say("    %-*s  %s" % (width, FACT_LABELS[fid], "yes" if w.fact(fid) else "no"))


def show_stack(w):
    TERM.dim(t("hint.detected"))
    for sid, key, _ in STACK_FIELDS:
        TERM.say("    %-22s %s" % (t(key), w.a.get(sid) or t("not.detected")))


def show_cmds(w):
    TERM.dim(t("hint.cmds"))
    for sid, key, _ in CMD_FIELDS:
        TERM.say("    %-22s %s" % (t(key), w.a.get(sid) or t("none.found")))


def show_arch(w):
    d = w.det
    if not (d.mono_tool or d.components or d.services or d.integrations):
        return
    TERM.dim(t("hint.arch"))
    if d.mono_tool:
        TERM.say("    %-22s %s" % ("monorepo", d.mono_tool))
    if d.components:
        TERM.say("    %-22s %s" % ("components", ", ".join(n for n, _, _ in d.components)))
    if d.services:
        TERM.say("    %-22s %s" % ("compose services", ", ".join(d.services)))
    if d.integrations:
        TERM.say("    %-22s %s" % ("external services", ", ".join(s for s, _ in d.integrations)))


def show_i18n(w):
    if w.det.locales:
        TERM.dim(t("hint.i18n", locales=", ".join(w.det.locales)))
    elif w.det.i18n_libs:
        TERM.dim(t("hint.i18n", locales=", ".join(w.det.i18n_libs)))


def default_shape(w):
    d = w.det
    if d.services:
        return "several services run together (%s)" % ", ".join(d.services[:4])
    if d.mono_tool and d.components:
        return "%s with %d parts (%s)" % (d.mono_tool, len(d.components),
                                          ", ".join(n for n, _, _ in d.components[:4]))
    if d.host:
        return "one deployable, hosted on %s" % d.csv("host")
    return ""


def default_approval(w):
    parts = []
    if w.fact("deploy"):
        parts.append("production deploys")
    if w.fact("pii"):
        parts.append("anything touching personal data")
    if w.a.get("s_db"):
        parts.append("schema or data migrations")
    parts.append("anything outward-facing (public posts, emails, announcements)")
    return ", ".join(parts)


def default_languages(w):
    if w.det.locales:
        return ", ".join(w.det.locales)
    return "en"


def default_docsdir(w):
    found = w.existing_docs()
    if found:
        return found
    target = w.target
    if target and (target / w.o.docs_dir).is_dir() and any((target / w.o.docs_dir).iterdir()):
        return "sdlc-docs" if not w.o.docs_dir_given else w.o.docs_dir
    return w.o.docs_dir


def normalize_prefix(value):
    """2-4 letters, upper-cased; a trailing '-' or spaces are forgiven, nothing else is.
    The charter, runtime and hooks all read the prefix as exactly that."""
    value = (value or "").strip().rstrip("-").strip()
    return value.upper() if re.fullmatch(r"[A-Za-z]{2,4}", value) else None


def validate_prefix(w, value):
    letters = normalize_prefix(value)
    if letters:
        return True, letters
    return False, t("err.prefix")


def validate_docsdir(w, value):
    value = (value or "").strip()
    if not value or "/" in value or value in (".", ".."):
        return False, t("bad.docs", docs=w.a.get("docsdir") or w.o.docs_dir)
    return True, value


def deploy_options():
    return [label for _, label in DEPLOY_PLATFORMS] + [
        "Other / not listed (describe it in the charter)"]


def default_deploy(w):
    ids = w.o.deploy if w.o.deploy is not None else w.det.deploy
    order = list(DEPLOY_IDS) + [DEPLOY_OTHER]
    return [order.index(pid) + 1 for pid in ids if pid in order]


def selected_platforms(w):
    """Platform ids whose checklists install. An answer or --deploy selects one;
    detection only pre-fills the question, so -y alone installs none."""
    answer = w.a.get("deploy_targets")
    if w.interactive and w.fact("deploy") and answer is not None:
        order = list(DEPLOY_IDS) + [DEPLOY_OTHER]
        return [order[i - 1] for i in answer if 1 <= i <= len(order)]
    return list(w.o.deploy or [])


def installed_platforms(target, docs, extra=()):
    """Platform ids with a checklist on disk, plus any just selected. The profile is
    derived from this rather than from one run's flags, so adding a platform later does
    not erase the ones installed before it."""
    root = Path(target) / docs / "platforms"
    ids = [pid for pid in DEPLOY_IDS if (root / ("%s.md" % pid)).is_file()]
    for pid in extra:
        add(ids, pid)
    return ids


def platform_cell(ids):
    parts = []
    for pid in ids:
        if pid == DEPLOY_OTHER:
            parts.append("other — name it here; no kit checklist covers it")
        else:
            parts.append("%s (`../platforms/%s.md`)" % (DEPLOY_LABELS[pid], pid))
    return ", ".join(parts)


def build_steps(w):
    o = w.o
    # Flags given on the command line answer their question; captured once, because the
    # answers below write into the same options and must not hide their own question.
    hooks_given = bool(o.hooks or o.git_hooks)
    ignore_given = bool(o.gitignore_tools or o.git_exclude)
    tests_given, ci_given = bool(o.scaffold_tests), bool(o.scaffold_ci)
    profile_given, harness_given, preset_given = o.profile_given, o.harnesses is not None, bool(o.preset)
    asking = lambda w: w.interactive
    steps = [
        Step("dest", "sec.dest", "dest", "q.dest", help="h.dest", cascade=True, quick=True,
             default=lambda w: str(w.target or ""), after=after_dest, label="l.dest"),

        Step("plan", "sec.mode", "show", "plan.title", before=show_plan, quick=True,
             when=asking),
        Step("mode", "sec.mode", "choice", "q.mode", help="h.mode", quick=True,
             options=MODE_OPTIONS, default="quick", cascade=True,
             when=lambda w: w.interactive and not w.o.mode),
        Step("sections", "sec.mode", "multichoice", "q.sections", help="h.sections",
             label="l.sections", options=lambda w: [t(k) for k in SECTION_KEYS], default=[],
             cascade=True, when=lambda w: w.interactive and w.mode() == "custom"
             and not w.o.sections),

        Step("name", "sec.project", "text", "q.name", help="h.name", label="l.name",
             default=lambda w: w.a.get("name") or (w.target.name if w.target else "")),
        Step("what", "sec.project", "text", "q.what", help="h.what", label="l.what", quick=True),
        Step("prefix", "sec.project", "text", "q.prefix", help="h.prefix", label="l.prefix",
             validate=validate_prefix, quick=True,
             default=lambda w: (w.o.prefix or w.recovered_prefix() or w.derive_prefix())),
        Step("owner", "sec.project", "text", "q.owner", help="h.owner", label="l.owner",
             default=lambda w: w.git("config", "user.name")),
        Step("repo", "sec.project", "text", "q.repo", help="h.repo", label="l.repo",
             default=lambda w: w.git("remote", "get-url", "origin")),

        Step("types", "sec.build", "multichoice", "q.types", help="h.types", label="l.types",
             options=list(PROJECT_TYPES), default=lambda w: w.det.types,
             after=after_types, cascade=True, quick=True),
        Step("facts_ok", "sec.build", "key", "q.facts", help="h.facts_ok", options="ye",
             default="y", before=show_facts),
        Step("facts_pick", "sec.build", "multichoice", "q.facts_pick", help="h.facts_pick",
             label="l.facts_pick", options=lambda w: [FACT_LABELS[f] for f in FACT_IDS],
             default=lambda w: [i + 1 for i, f in enumerate(FACT_IDS) if w.fact(f)],
             none_ok=True, after=after_facts_pick, when=lambda w: w.a.get("facts_ok") == "e"),
    ]

    steps.append(Step("harness_pick", "sec.tools", "multichoice", "q.harness", help="h.harness",
                      label="l.harness", options=harness_options(), default=default_harness,
                      after=after_harness, quick=True,
                      when=lambda w: w.interactive and not harness_given))

    for section, ok, fields, empty in (("sec.stack", "stack_ok", STACK_FIELDS, "not.detected"),
                                       ("sec.cmds", "cmds_ok", CMD_FIELDS, "none.found")):
        # "Change some" picks the rows first, so correcting one command is one question
        # rather than eighteen.
        steps.append(Step(ok, section, "key", "q." + ok, help="h." + ok, options="yen",
                          default="y", before=show_stack if ok == "stack_ok" else show_cmds,
                          after=after_stack_ok if ok == "stack_ok" else after_cmds_ok))
        pick = ok.replace("_ok", "_pick")
        steps.append(Step(pick, section, "multichoice", "q.pick", help="h.pick",
                          options=(lambda f, e: (lambda w: [(t(key), w.a.get(sid) or t(e))
                                                            for sid, key, _ in f]))(fields, empty),
                          default=[], none_ok=True,
                          when=(lambda k: (lambda w: w.a.get(k) == "e"))(ok)))
        for n, (sid, prompt, _) in enumerate(fields, 1):
            steps.append(Step(sid, section, "text", prompt,
                              default=(lambda s: (lambda w: w.a.get(s, "")))(sid),
                              when=(lambda k, p, n: (lambda w: w.a.get(k) == "e"
                                                     and n in (w.a.get(p) or [])))(ok, pick, n)))

    steps += [
        Step("shape", "sec.arch", "text", "q.shape", help="h.shape", label="l.shape",
             default=default_shape, before=show_arch),
        Step("critical", "sec.arch", "text", "q.critical", help="h.critical", label="l.critical"),
        Step("expensive", "sec.arch", "text", "q.expensive", help="h.expensive", label="l.expensive"),

        Step("multilingual", "sec.lang", "yesno", "q.multilingual", cascade=True, label="l.multilingual",
             help="h.multilingual",
             before=show_i18n,
             when=lambda w: w.fact("ui") or w.fact("public"),
             default=lambda w: len(w.det.locales) > 1 or bool(w.det.i18n_libs)),
        Step("languages", "sec.lang", "text", "q.languages", help="h.languages", label="l.languages",
             default=default_languages, when=lambda w: w.multilingual()),
        Step("catalog", "sec.lang", "text", "q.catalog", help="h.catalog", label="l.catalog",
             default=lambda w: w.det.catalog, when=lambda w: w.multilingual()),
        Step("translation", "sec.lang", "text", "q.translation", help="h.translation", label="l.translation",
             when=lambda w: w.multilingual()),
        Step("glossary", "sec.lang", "text", "q.glossary", help="h.glossary", label="l.glossary",
             when=lambda w: w.multilingual()),

        Step("branch", "sec.process", "text", "q.branch", help="h.branch", label="l.branch",
             default=lambda w: w.git("symbolic-ref", "--short", "HEAD") or "main"),
        Step("direct", "sec.process", "yesno", "q.direct", help="h.direct", default=False,
             label="l.direct"),
        Step("approvers", "sec.process", "text", "q.approvers", help="h.approvers", label="l.approvers",
             default=lambda w: w.a.get("owner", "")),
        Step("staleness", "sec.process", "text", "q.staleness", help="h.staleness",
             default="90 days", label="l.staleness"),
        Step("preset", "sec.process", "choice", "q.preset", help="h.preset", label="l.preset",
             options=PRESET_OPTIONS, default="team",
             when=lambda w: w.interactive and not preset_given),
        Step("effort", "sec.process", "choice", "q.effort", help="h.effort",
             options=EFFORT_OPTIONS, default=lambda w: {"lean": "l", "normal": "n", "beast": "x"}[
                 preset_field(w, "effort_mode")], label="l.effort"),
        Step("devmethod", "sec.process", "choice", "q.devmethod", help="h.devmethod",
             options=DEV_METHOD_OPTIONS, default=lambda w: {"item": "i", "epic": "e"}[
                 preset_field(w, "dev_method")], label="l.devmethod"),
        Step("decision", "sec.process", "choice", "q.decision", help="h.decision",
             options=DECISION_OPTIONS, default=lambda w: {"ask": "a", "guide": "g", "autopilot": "p"}[
                 preset_field(w, "decision_style")], label="l.decision"),
        Step("tier", "sec.process", "choice", "q.tier", help="h.tier", label="l.tier",
             options=TIER_OPTIONS, default=lambda w: preset_field(w, "tier_rules"),
             when=asking),
        Step("acquisition", "sec.process", "choice", "q.acquisition", help="h.acquisition",
             options=ACQUISITION_OPTIONS, default=lambda w: {"standard": "s", "advanced": "a"}[
                 w.o.acquisition_profile], label="l.acquisition", when=lambda w: w.fact("acquire")),
        Step("approval", "sec.process", "text", "q.approval", help="h.approval",
             default=default_approval, label="l.approval"),
        Step("forbidden", "sec.process", "text", "q.forbidden", help="h.forbidden", label="l.forbidden"),
        Step("platform", "sec.process", "choice", "q.platform", help="h.platform", label="l.platform",
             options=PLATFORM_OPTIONS, default=lambda w: ", ".join(w.det.platforms) or "none"),
        Step("deploy_targets", "sec.process", "multichoice", "q.deploy", help="h.deploy",
             label="l.deploy", options=deploy_options(), default=default_deploy,
             when=lambda w: w.fact("deploy"), none_ok=True),

        Step("a11y", "sec.standards", "text", "q.a11y", help="h.a11y", default="WCAG 2.2 AA",
             label="l.a11y",
             when=lambda w: w.fact("ui")),
        Step("outcome", "sec.standards", "text", "q.outcome", help="h.outcome", label="l.outcome",
             when=lambda w: w.fact("conv")),
        Step("access_model", "sec.standards", "choice", "q.access_model", help="h.access_model",
             label="l.access_model", options=ACCESS_OPTIONS,
             default=lambda w: "None (Public)" if not (w.fact("pii") or bool(w.a.get("s_auth"))) else "Role-Based (RBAC)",
             when=lambda w: bool(w.interactive and (w.fact("pii") or bool(w.a.get("s_auth"))))),
        Step("mfa_policy", "sec.standards", "choice", "q.mfa_policy", help="h.mfa_policy",
             label="l.mfa_policy", options=MFA_OPTIONS,
             default=lambda w: "Not required" if not (w.fact("pii") or bool(w.a.get("s_auth"))) else "Optional / User-enabled",
             when=lambda w: bool(w.interactive and (w.fact("pii") or bool(w.a.get("s_auth"))))),

        Step("docsdir", "sec.install", "text", "q.docsdir", help="h.docsdir",
             default=default_docsdir, label="l.docsdir",
             validate=validate_docsdir),
        Step("profile", "sec.install", "choice", "q.profile", help="h.profile", label="l.profile",
             options=PROFILE_OPTIONS, default=lambda w: w.o.profile, after=after_profile,
             when=lambda w: w.interactive and not profile_given),
        Step("commands", "sec.install", "yesno", "q.commands", help="h.commands", default=True,
             label="l.commands"),
        Step("enforce", "sec.install", "choice", "q.enforce", help="h.enforce", label="l.enforce",
             options=ENFORCE_OPTIONS, default="none", after=after_enforce,
             when=lambda w: w.interactive and not hooks_given),
        Step("git_tools", "sec.install", "choice", "q.git_tools", help="h.git_tools",
             label="l.gitignore_tools", options=GIT_TOOLS_OPTIONS, default="commit",
             after=after_git_tools, when=lambda w: w.interactive and not ignore_given),
        Step("scaffold_tests", "sec.install", "yesno", "q.scaffold_tests", help="h.scaffold_tests",
             label="l.scaffold_tests", default=False, after=after_scaffold_tests,
             when=lambda w: w.interactive and not tests_given),
        Step("scaffold_ci", "sec.install", "choice", "q.scaffold_ci", help="h.scaffold_ci",
             label="l.scaffold_ci", options=CI_OPTIONS, default="none", after=after_scaffold_ci,
             when=lambda w: w.interactive and not ci_given),
        Step("skills_pick", "sec.install", "multichoice", "q.skills", help="h.skills_pick",
             label="l.skills", options=skill_items, default=default_skills,
             after=after_skills_pick, none_ok=True, when=lambda w: w.o.want_skills),
    ]
    return steps


# ---------------------------------------------------------------- destination

def resolve_target(path, options, term):
    """A destination, or None with the reason printed. The kit installs into *another*
    project: installing into itself scatters a project's AGENTS.md, docs/ and .claude/
    over the template it was copied from."""
    if not path:
        term.err(t("err.no_target"))
        return None
    p = Path(os.path.expanduser(path))
    if not p.is_dir():
        if options.create:
            # Creation is deferred until after the review screen. This keeps quit and
            # --dry-run genuinely free of filesystem side effects.
            term.say("  would create %s after review" % p)
        else:
            term.err(t("err.no_dir", path=str(p)))
            term.err(t("hint.create"))
            return None
    p = p.resolve()
    if p == SRC:
        term.err(t("err.is_kit", path=str(SRC)))
        term.err(t("err.give_project"))
        return None
    if str(p).startswith(str(SRC) + os.sep):
        term.err(t("err.in_kit", path=str(p), src=str(SRC)))
        term.err(t("err.give_project"))
        return None
    if (p / "install.sh").is_file() and (p / "VERSION").is_file() \
            and (p / "template" / "AGENTS.md").is_file():
        term.err(t("err.kit_copy", path=str(p)))
        return None
    return p


# ---------------------------------------------------------------- text writers

def plain_text(value):
    """Keep user-provided values inside one Markdown/YAML field."""
    value = " ".join(str(value or "").replace("\r", "\n").splitlines())
    return value.replace("{{", "{ {").replace("}}", "} }")


def substitute(text, ctx):
    for key, value in ctx.items():
        text = text.replace("{{%s}}" % key, value)
    return text


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except (IOError, OSError):
        return ""


def ensure_inside(root, path):
    """Reject a destination whose existing symlink chain escapes the selected project."""
    root = Path(root).resolve()
    path = Path(path)
    resolved = path.resolve()
    try:
        inside = os.path.commonpath([str(root), str(resolved)]) == str(root)
    except (AttributeError, ValueError):
        inside = str(resolved).startswith(str(root) + os.sep) or resolved == root
    if not inside:
        raise RuntimeError("destination escapes project through a symlink: %s" % path)
    return path


def atomic_write_bytes(path, data):
    """Write bytes without exposing a partially-written destination."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_text(path, text):
    atomic_write_bytes(path, text.encode("utf-8"))


def installed_profile(target):
    """Which profile this project was installed with. An upgrade must not quietly
    convert a compact install to a full one by restoring documents it deliberately
    does not have."""
    path = Path(target) / PROFILE_REL
    if not path.exists():
        return "full"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (IOError, OSError, ValueError):
        return "full"
    value = data.get("profile") if isinstance(data, dict) else None
    return value if value in ("full", "compact") else "full"


def managed_source_texts(target, docs, ctx, profile="full"):
    """Return portable kit-owned destination paths and their rendered content."""
    planned = {}
    for name in ("README.md", "CARD.md"):
        src = SRC / "template" / "docs" / name
        planned[(Path(docs) / name).as_posix()] = substitute(src.read_text(encoding="utf-8"), ctx)
    for sub in ("process", "roles", "templates"):
        base = SRC / "template" / "docs" / sub
        for src in sorted(base.rglob("*")):
            if not src.is_file():
                continue
            if profile == "compact" and sub == "process" and re.match(r"^[0-9]{2}-", src.name):
                continue
            rel = Path(docs) / sub / src.relative_to(base)
            planned[rel.as_posix()] = substitute(src.read_text(encoding="utf-8"), ctx)
    platforms_root = Path(target) / docs / "platforms"
    if platforms_root.is_dir():
        for src in sorted((SRC / "optional" / "platforms").glob("*.md")):
            if (platforms_root / src.name).is_file():
                planned[(Path(docs) / "platforms" / src.name).as_posix()] = substitute(
                    src.read_text(encoding="utf-8"), ctx)
    commands_root = Path(target) / ".claude" / "commands"
    kit_commands = sorted((SRC / "optional" / "claude-commands").glob("*.md"))
    # Once a project has any kit command, a command the kit gained since (sdlc-build)
    # arrives with the upgrade instead of only on a fresh install.
    has_commands = commands_root.is_dir() and any((commands_root / c.name).is_file()
                                                  for c in kit_commands)
    if has_commands:
        for src in kit_commands:
            planned[(Path(".claude") / "commands" / src.name).as_posix()] = substitute(
                src.read_text(encoding="utf-8"), ctx)
    for skills_rel in (Path(".claude") / "skills", Path(".agents") / "skills"):
        skills_root = Path(target) / skills_rel
        if not skills_root.is_dir():
            continue
        for base in sorted((SRC / "optional" / "skills").iterdir()):
            if not base.is_dir() or not (skills_root / base.name).is_dir():
                continue
            for src in sorted(base.rglob("*")):
                if src.is_file():
                    rel = skills_rel / base.name / src.relative_to(base)
                    planned[rel.as_posix()] = substitute(src.read_text(encoding="utf-8"), ctx)
    shared_root = Path(target) / ".agents" / "skills"
    kit_skill_names = {p.name for p in (SRC / "optional" / "skills").iterdir() if p.is_dir()}
    if shared_root.is_dir() and any((shared_root / n / "SKILL.md").is_file()
                                    for n in kit_skill_names | set(LOOP_SKILLS)):
        for name in LOOP_SKILLS:
            planned[".agents/skills/%s/SKILL.md" % name] = substitute(command_skill_text(name), ctx)
    git_hooks_root = Path(target) / ".ai-sdlc" / "git-hooks"
    if git_hooks_root.is_dir():
        for name in ("pre-commit", "commit-msg"):
            if (git_hooks_root / name).is_file():
                planned[".ai-sdlc/git-hooks/" + name] = substitute(
                    (SRC / "optional" / "git-hooks" / name).read_text(encoding="utf-8"), ctx)
        if (git_hooks_root / "lib.sh").is_file():
            planned[".ai-sdlc/git-hooks/lib.sh"] = substitute(
                (SRC / "optional" / "hooks" / "lib.sh").read_text(encoding="utf-8"), ctx)
    hooks_root = Path(target) / ".claude" / "hooks"
    if hooks_root.is_dir() and any(p.suffix == ".sh" for p in hooks_root.iterdir()):
        # The hooks this project chose, plus the library every current hook sources.
        for src in sorted((SRC / "optional" / "hooks").iterdir()):
            if src.is_file() and ((hooks_root / src.name).is_file() or src.name in ("lib.sh", "adapter.sh")):
                planned[(Path(".claude") / "hooks" / src.name).as_posix()] = substitute(
                    src.read_text(encoding="utf-8"), ctx)
    for name in RUNTIME_FILES:
        planned[".ai-sdlc/bin/" + name] = substitute(
            (SRC / "optional" / "runtime" / name).read_text(encoding="utf-8"), ctx)
    return planned


# The loop's entry points, as skills for tools that list skills where Claude Code lists
# commands (Antigravity's / menu, Codex, Cursor, Gemini CLI, Copilot). Generated from the
# command files so there is one source. sdlc-doctor is not here: optional/skills/ already
# ships a skill by that name.
LOOP_SKILLS = ("sdlc-plan", "sdlc-build", "sdlc-verify", "sdlc-review", "sdlc-log")
LOOP_SKILL_WHEN = {
    "sdlc-plan": "Use when the user invokes /sdlc-plan or asks to plan, frame or scope a "
                 "change, or when a new request needs a tracked work item and a reviewed "
                 "plan before any code is written.",
    "sdlc-build": "Use only when the user invokes /sdlc-build or explicitly asks to build "
                  "or implement a plan that is already approved. Never on your own "
                  "initiative: building without an approved plan is what this loop exists "
                  "to prevent.",
    "sdlc-verify": "Use when the user invokes /sdlc-verify or asks to run the checks, and "
                   "before claiming that anything passes, works or is done.",
    "sdlc-review": "Use when the user invokes /sdlc-review or asks for a review of a plan "
                   "or a change, and when a plan or a diff reaches a review gate.",
    "sdlc-log": "Use when the user invokes /sdlc-log or asks to close, log or wrap up a "
                "work item that is built, verified and reviewed.",
}


def command_skill_text(name):
    """A loop command rewritten as an Agent Skills SKILL.md: name and description in the
    frontmatter, the argument placeholder turned into prose, and references to other
    commands turned into references to their skills. Placeholders are left for
    substitute()."""
    text = (SRC / "optional" / "claude-commands" / (name + ".md")).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    meta, body = {}, text
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    hint = meta.get("argument-hint", "")
    body = body.replace(
        "$ARGUMENTS",
        "the request given with this skill: the text after its name, or the request in the "
        "conversation that called for it" + (" (expected: `%s`)" % hint if hint else "") + ".")
    body = re.sub(r"`/(sdlc-[a-z-]+)`", r"the `\1` skill", body)
    description = "%s. %s" % (meta.get("description", name).rstrip("."), LOOP_SKILL_WHEN[name])
    return ("---\nname: %s\ndescription: %s\n---\n\n"
            "<!-- Generated from the kit's optional/claude-commands/%s.md by install.py. "
            "Kit-managed: change the kit, not this file. -->\n%s"
            % (name, json.dumps(description, ensure_ascii=False), name, body))


def hook_command(name):
    """Anchored on the project root: a relative path fails open the moment the session's
    working directory is a subdirectory."""
    return 'sh "$CLAUDE_PROJECT_DIR"/.claude/hooks/%s' % name


def repair_hook_commands(target):
    """Rewrite hook registrations an older kit wrote as `sh .claude/hooks/x.sh`. Touches
    nothing else in settings.json; returns how many were rewritten."""
    settings = Path(target) / ".claude" / "settings.json"
    if not settings.is_file():
        return 0
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return 0
    legacy = re.compile(r"^sh \.claude/hooks/([A-Za-z0-9_.-]+\.sh)$")
    count = 0
    for entries in hooks.values():
        for entry in entries if isinstance(entries, list) else []:
            for spec in (entry.get("hooks") or []) if isinstance(entry, dict) else []:
                match = legacy.match(str(spec.get("command", ""))) if isinstance(spec, dict) else None
                if match:
                    spec["command"] = hook_command(match.group(1))
                    count += 1
    if count:
        atomic_write_text(settings, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return count


def load_manifest(target):
    path = Path(target) / MANIFEST_REL
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("files"), dict):
            # Installs made on Windows before 3.4.2 recorded backslash paths. Keys are
            # POSIX from then on, so a mixed-OS team upgrades the same manifest.
            for key in ("files", "regions"):
                if isinstance(data.get(key), dict):
                    data[key] = dict((k.replace("\\", "/"), v) for k, v in data[key].items())
            return data
    except (IOError, OSError, ValueError):
        pass
    return None


def write_manifest(target, docs, files, regions=None):
    payload = {
        "schema": 1,
        "kit_version": VERSION,
        "docs_dir": docs,
        "files": dict(sorted((k.replace("\\", "/"), v) for k, v in files.items())),
    }
    if regions:
        payload["regions"] = dict(sorted(regions.items()))
    atomic_write_text(ensure_inside(target, Path(target) / MANIFEST_REL),
                      json.dumps(payload, indent=2, sort_keys=True) + "\n")


def is_managed_rel(rel, docs):
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        return False
    prefixes = ((str(docs), "process"), (str(docs), "roles"), (str(docs), "templates"),
                (str(docs), "platforms"), (".claude", "skills"), (".claude", "commands"),
                (".claude", "hooks"), (".ai-sdlc", "bin"), (".ai-sdlc", "git-hooks"),
                (".agents", "skills"))
    return path.parts in ((str(docs), "README.md"), (str(docs), "CARD.md"),
                          ) + tuple((str(docs), name) for name in RETIRED_DOCS) or any(
        path.parts[:2] == prefix for prefix in prefixes)


AGENTS_BEGIN = "<!-- ai-sdlc:kit-begin"
AGENTS_END = "<!-- ai-sdlc:kit-end -->"
AGENTS_REL = "AGENTS.md"


def agents_split(text):
    """(head, region, tail) around the kit-managed region of AGENTS.md, or None when the
    file has no markers. The region runs from the begin marker's line to the end marker,
    inclusive, so replacing it also refreshes the marker text."""
    start = text.find(AGENTS_BEGIN)
    end = text.find(AGENTS_END)
    if start < 0 or end < start:
        return None
    end += len(AGENTS_END)
    return text[:start], text[start:end], text[end:]


def agents_legacy_split(text):
    """An AGENTS.md from before the markers: the title line, then the portable sections,
    then section 9. None if the file does not have that shape."""
    m = re.search(r"^## 9\. Project overrides", text, re.M)
    if not m or not text.startswith("# "):
        return None
    title_end = text.find("\n") + 1
    return text[:title_end] + "\n", text[title_end:m.start()], text[m.start():]


def charter_row_labels(text):
    return re.findall(r"^\| (\*\*[^*|]+\*\*) \|", text, re.M)


def add_missing_charter_rows(installed, template):
    """Append-only: a bold-labelled row the kit's charter has and this project's lacks is
    inserted, as the kit writes it, next to a neighbour from the same kit table -- after
    the nearest earlier one, else before the nearest later one. Existing rows, the
    project's answers, are never touched. Returns (text, added, unplaced)."""
    row = re.compile(r"^\| (\*\*[^*|]+\*\*) \|")
    tables, current = [], []
    for line in template.split("\n"):
        if line.startswith("|"):
            m = row.match(line)
            if m:
                current.append((m.group(1), line))
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)

    lines = installed.split("\n")

    def index_of(label):
        for i, existing in enumerate(lines):
            if existing.startswith("| %s |" % label):
                return i
        return -1

    added, unplaced = [], []
    for table in tables:
        for pos, (label, text) in enumerate(table):
            if index_of(label) >= 0:
                continue
            placed = False
            for before, _ in reversed(table[:pos]):
                i = index_of(before)
                if i >= 0:
                    lines.insert(i + 1, text)
                    placed = True
                    break
            if not placed:
                for after, _ in table[pos + 1:]:
                    i = index_of(after)
                    if i >= 0:
                        lines.insert(i, text)
                        placed = True
                        break
            (added if placed else unplaced).append(label.strip("*"))
    return "\n".join(lines), added, unplaced


def _cell(value):
    return plain_text(value).replace("|", "\\|")


TIER_RULES_UPGRADE = ("`Strict` _(set by the upgrade from 3.x: the 3.x tier rules still apply. "
                      "Change to `Standard` to tier by blast radius; see `../CARD.md`, "
                      "\"Tiers\")_")


def fill_row(text, label, value):
    """Rewrite the first two-column table row whose first cell is `label`."""
    if not value:
        return text
    out, done = [], False
    head = "| %s |" % label
    for line in text.split("\n"):
        if not done and line.startswith(head):
            out.append("%s %s |" % (head, _cell(value)))
            done = True
        else:
            out.append(line)
    return "\n".join(out)


def fill_line(text, prefix, replacement):
    out, done = [], False
    for line in text.split("\n"):
        if not done and line.startswith(prefix):
            out.append(replacement)
            done = True
        else:
            out.append(line)
    return "\n".join(out)


def fill_field(text, label, value):
    """Replace a bold label and its multi-line _(fill in ...)_ placeholder."""
    if not value:
        return text
    out, done, skipping = [], False, False
    for line in text.split("\n"):
        if skipping:
            if line.strip() == "":
                skipping = False
                out.append(line)
            continue
        if not done and line.startswith(label):
            out.append("%s %s" % (label, plain_text(value)))
            done, skipping = True, True
            continue
        out.append(line)
    return "\n".join(out)


def set_role(text, role, active, reason):
    """Tick or untick a role row, keeping the 'Active if' column and giving every
    unticked row the answer it came from -- a blank reason means nobody decided."""
    out, done = [], False
    for line in text.split("\n"):
        if not done and line.startswith("| %s | " % role):
            cells = line.split("|")
            if len(cells) >= 6:
                cells[2] = " %s " % ("☑" if active else "☐")
                cells[4] = " " if active else " %s " % _cell(reason)
                out.append("|" + "|".join(cells[1:-1]) + "|")
                done = True
                continue
        out.append(line)
    return "\n".join(out)


def tick_artifact(text, name):
    return text.replace("☐ %s" % name, "☑ %s" % name, 1)


def today():
    try:
        return subprocess.check_output(["date", "+%F"]).decode().strip()
    except (OSError, subprocess.CalledProcessError):
        import datetime
        return datetime.date.today().isoformat()


# ---------------------------------------------------------------- installer

class Installer(object):
    def __init__(self, w):
        self.w = w
        self.o = w.o
        self.target = w.target
        self.docs = w.a.get("docsdir") or w.o.docs_dir
        self.added = 0
        self.skipped = 0
        self.updated = 0
        self.fresh = set()
        self.wired = []
        self.harnesses = set()
        self.platforms = selected_platforms(w)
        chosen = w.a.get("harnesses")
        if chosen is None:
            chosen = ["claude"] if w.o.harnesses is None else w.o.harnesses
        for name in chosen:
            self.harnesses.update(HARNESS_ALIASES.get(name, ()))
        # Any tool besides Claude Code reads skills from .agents/skills/ (the Agent
        # Skills cross-client convention), so the chosen skills go there too.
        self.shared_skills = bool([n for n in chosen if n != "claude"]
                                  or getattr(w.o, "native_harnesses", []))
        self.ctx = {
            "PROJECT_NAME": plain_text(w.a.get("name") or
                                       (w.target.name if w.target else "")),
            "PREFIX": w.a.get("prefix") or w.o.prefix or "",
            "DOCS_DIR": self.docs,
            "KIT_VERSION": VERSION,
        }
        if not self.ctx["PREFIX"]:
            del self.ctx["PREFIX"]

    def doc_sources(self):
        """Which of the portable tree this profile installs. compact keeps the card and
        drops the numbered standards it summarises — one source for every rule either
        way, never a second copy written in shorter words."""
        root = SRC / "template" / "docs"
        paths = sorted(p for p in root.rglob("*") if p.is_file())
        if self.o.profile != "compact":
            return paths
        keep = []
        for path in paths:
            parts = path.relative_to(root).parts
            if parts[0] == "process" and re.match(r"^[0-9]{2}-", parts[-1]):
                continue
            keep.append(path)
        return keep

    def platform_sources(self):
        """The checklists for the platforms this project named, plus the index that
        explains them. None at all when it named none: an unused checklist is reading
        that competes with the ones that apply."""
        base = SRC / "optional" / "platforms"
        paths = [base / ("%s.md" % pid) for pid in self.platforms if pid in DEPLOY_IDS]
        return ([base / "README.md"] + paths) if paths else []

    def rel(self, dest):
        try:
            return Path(dest).relative_to(self.target).as_posix()
        except ValueError:
            return str(dest)

    def install_file(self, src, dest):
        dest = ensure_inside(self.target, dest)
        if dest.exists():
            self.skipped += 1
            print("  skip (exists)  %s" % self.rel(dest))
            return False
        if self.o.dry_run:
            self.added += 1
            print("  would add      %s" % self.rel(dest))
            return True
        text = Path(src).read_text(encoding="utf-8")
        atomic_write_text(dest, substitute(text, self.ctx))
        self.added += 1
        self.fresh.add(self.rel(dest))
        print("  add            %s" % self.rel(dest))
        return True

    def install_text(self, dest, content):
        dest = ensure_inside(self.target, dest)
        if dest.exists():
            self.skipped += 1
            print("  skip (exists)  %s" % self.rel(dest))
            return False
        if self.o.dry_run:
            self.added += 1
            print("  would add      %s" % self.rel(dest))
            return True
        atomic_write_text(dest, content)
        self.added += 1
        self.fresh.add(self.rel(dest))
        print("  add            %s" % self.rel(dest))
        return True

    def upgrade_file(self, src, dest):
        dest = ensure_inside(self.target, dest)
        if self.o.dry_run:
            self.updated += 1
            print("  would update   %s" % self.rel(dest))
            return
        atomic_write_text(dest, substitute(Path(src).read_text(encoding="utf-8"), self.ctx))
        self.updated += 1
        print("  update         %s" % self.rel(dest))

    def edit(self, relpath, transform):
        """Only ever applied to a file this run created."""
        path = ensure_inside(self.target, self.target / relpath)
        if self.o.dry_run or not path.exists():
            return False
        text = path.read_text(encoding="utf-8")
        new = transform(text)
        if new != text:
            atomic_write_text(path, new)
            return True
        return False

    # -- the copy --------------------------------------------------------------
    def run(self):
        w = self.w
        print("")
        print("Installing Nuhut kit v%s into %s" % (VERSION, self.target))
        print("")
        candidates = [self.target / "AGENTS.md", self.target / "CLAUDE.md",
                      self.target / MANIFEST_REL]
        candidates.extend(self.target / ".ai-sdlc" / "bin" / name for name in RUNTIME_FILES)
        candidates.extend(self.target / self.docs / path.relative_to(SRC / "template" / "docs")
                          for path in self.doc_sources())
        if w.a.get("commands", True):
            candidates.extend(self.target / ".claude" / "commands" / path.name
                              for path in (SRC / "optional" / "claude-commands").glob("*.md"))
        candidates.extend(self.target / self.docs / "platforms" / path.name
                          for path in self.platform_sources())
        if self.shared_skills and w.a.get("commands", True):
            candidates.extend(self.target / ".agents" / "skills" / name / "SKILL.md"
                              for name in LOOP_SKILLS)
        for name in w.chosen_skills():
            base = SRC / "optional" / "skills" / name
            for root in self.skill_roots():
                candidates.extend(self.target / root / name / path.relative_to(base)
                                  for path in base.rglob("*") if path.is_file())
        if self.o.scaffold_tests:
            candidates.extend((self.target / self.docs / "project" / "test-plan.md",
                               self.target / ".ai-sdlc" / "testing-profile.json"))
        if self.o.scaffold_ci == "github":
            candidates.append(self.target / ".github" / "workflows" / "quality.yml")
        elif self.o.scaffold_ci == "gitlab":
            candidates.append(self.target / ".gitlab-ci.yml")
        if self.o.scaffold_ci and not [key for key in self.selected_commands()
                                       if key not in ("run",)]:
            raise RuntimeError("cannot scaffold CI: no quality commands were detected or confirmed")
        for candidate in candidates:
            ensure_inside(self.target, candidate)
        if not self.o.dry_run:
            self.target.mkdir(parents=True, exist_ok=True)
        self.install_file(SRC / "template" / "AGENTS.md", self.target / "AGENTS.md")
        for name in RUNTIME_FILES:
            self.install_file(SRC / "optional" / "runtime" / name,
                              self.target / ".ai-sdlc" / "bin" / name)
        for path in self.doc_sources():
            self.install_file(path, self.target / self.docs
                              / path.relative_to(SRC / "template" / "docs"))
        for path in self.platform_sources():
            self.install_file(path, self.target / self.docs / "platforms" / path.name)
        if w.a.get("commands", True):
            for path in sorted((SRC / "optional" / "claude-commands").glob("*.md")):
                self.install_file(path, self.target / ".claude" / "commands" / path.name)
        skills = w.chosen_skills()
        for name in skills:
            base = SRC / "optional" / "skills" / name
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    for root in self.skill_roots():
                        self.install_file(path, self.target / root / name
                                          / path.relative_to(base))
        if self.shared_skills and w.a.get("commands", True):
            # The commands, as skills, for tools whose / menu lists skills.
            for name in LOOP_SKILLS:
                self.install_text(self.target / ".agents" / "skills" / name / "SKILL.md",
                                  substitute(command_skill_text(name), self.ctx))
        self.wire_harnesses()
        self.note_profile()
        return skills

    COMPACT_NOTE = (
        "\n---\n\n**This project uses the compact profile.** The numbered documents in\n"
        "`process/` that this card summarises are deliberately not installed, so an\n"
        "escalation named above has nothing to open. That is *Absent*, not missing: the\n"
        "card is the whole standard here. If a Tier 1 change genuinely needs the full\n"
        "text, re-install with `--profile full`, which adds the documents and changes\n"
        "no rule.\n")

    HOOK_SPECS = (
        ("work-item-id.sh", "PreToolUse", "Bash", "Bash(git commit*)",
         "Checking the commit carries a work item ID"),
        ("protected-paths.sh", "PreToolUse", "Write|Edit", None,
         "Checking the path is not single-writer"),
        ("test-lock.sh", "PreToolUse", "Write|Edit", None,
         "Checking the path is not a locked reproducing test"),
        ("secret-guard.sh", "PreToolUse", "Bash", "Bash(git commit*)",
         "Checking the commit adds no credential"),
        ("doc-leak-guard.sh", "PreToolUse", "Write|Edit|MultiEdit", None,
         "Checking the write holds no credential"),
        ("approval-gate.sh", "PreToolUse", "Bash|Write|Edit", None,
         "Checking the command needs no human approval"),
    )

    # Seeded with comments only: until a project adds a line, each hook does nothing.
    HOOK_LISTS = (
        ("protected.txt",
         "# One shell glob per line. An edit to a matching path is denied.\n"
         "# Seeded empty on purpose: only this project knows which files a\n"
         "# managed platform owns, which are generated, and which another\n"
         "# agent holds. Until there is a line here the hook does nothing.\n"
         "#\n"
         "# e.g.  .replit\n"
         "#       replit.nix\n"
         "#       package-lock.json\n"
         "#       **/generated/**\n"),
        ("test-lock.txt",
         "# Reproducing tests locked while a defect is fixed: one shell glob per line.\n"
         "# The agent appends a line from the shell once the failing test is committed\n"
         "# (process/05-change-control.md, \"Fixing a defect\"). Edits to a listed\n"
         "# path, and to this file, are denied; a human removes the line when the fix\n"
         "# is verified.\n"
         "#\n"
         "# e.g.  tests/billing/test_rounding_regression.py\n"),
        ("gates.txt",
         "# Commands that need a named human's approval: one shell glob per line,\n"
         "# matched against the whole command. Mirror AGENTS.md section 9 and the\n"
         "# charter's Environments table. A matching command is denied unless the\n"
         "# session was started with AI_SDLC_APPROVAL=<ticket or ID>.\n"
         "#\n"
         "# e.g.  *deploy*prod*\n"
         "#       *terraform apply*\n"
         "#       *kubectl*--context*prod*\n"
         "#       *db:migrate*production*\n"),
    )

    def install_hooks(self):
        """Merged into whatever settings.json is already there, never written over it:
        the file usually carries permissions somebody tuned by hand."""
        if not self.o.hooks:
            return
        dest_dir = ensure_inside(self.target, self.target / ".claude" / "hooks")
        for name, _, _, _, _ in self.HOOK_SPECS:
            self.install_file(SRC / "optional" / "hooks" / name, dest_dir / name)
        for name in ("lib.sh", "adapter.sh", "README.md"):
            self.install_file(SRC / "optional" / "hooks" / name, dest_dir / name)
        for name, text in self.HOOK_LISTS:
            self.install_text(ensure_inside(self.target, self.target / ".ai-sdlc" / name),
                              text)
        settings = ensure_inside(self.target, self.target / ".claude" / "settings.json")
        if self.o.dry_run:
            print("  would merge    .claude/settings.json (hooks)")
            return
        data = {}
        if settings.exists():
            try:
                data = json.loads(settings.read_text(encoding="utf-8"))
            except ValueError:
                print("  skip           .claude/settings.json is not valid JSON -- hooks "
                      "not merged. Fix it and re-run.")
                return
            if not isinstance(data, dict):
                print("  skip           .claude/settings.json is not an object -- hooks "
                      "not merged.")
                return
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            print("  skip           .claude/settings.json has a non-object 'hooks' -- "
                  "not merged.")
            return
        added = 0
        for name, event, matcher, guard, status in self.HOOK_SPECS:
            command = hook_command(name)
            legacy = "sh .claude/hooks/%s" % name
            entries = hooks.setdefault(event, [])
            if not isinstance(entries, list):
                continue
            found = False
            for entry in entries:
                for spec in (entry.get("hooks") or []) if isinstance(entry, dict) else []:
                    if isinstance(spec, dict) and spec.get("command") in (command, legacy):
                        if spec["command"] == legacy:
                            spec["command"] = command    # an older install, repaired
                            added += 1
                        found = True
            if found:
                continue          # already installed; re-running must not duplicate it
            spec = {"type": "command", "command": command, "statusMessage": status}
            if guard:
                spec["if"] = guard
            entries.append({"matcher": matcher, "hooks": [spec]})
            added += 1
        atomic_write_text(settings, json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("  %s .claude/settings.json (%d hook%s)"
              % ("merge         " if added else "unchanged     ", added,
                 "" if added == 1 else "s"))
        self.install_harness_hooks()

    # Which hooks each other harness can run, and the matcher it uses. Gemini CLI names
    # its tools run_shell_command, write_file and replace, with the same argument names
    # the hooks read. Cursor's beforeShellExecution carries the command only, so the
    # file-write hooks have nothing to look at there and are not registered.
    GEMINI_MATCHERS = {"Bash": "run_shell_command", "Write|Edit": "write_file|replace",
                       "Write|Edit|MultiEdit": "write_file|replace",
                       "Bash|Write|Edit": "run_shell_command|write_file|replace"}

    def merge_json_hooks(self, rel, mutate):
        """Load <rel> as JSON (or start empty), let mutate() add what is missing, write it
        back. Anything already in the file stays: it is somebody's configuration."""
        path = ensure_inside(self.target, self.target / rel)
        if self.o.dry_run:
            print("  would merge    %s (hooks)" % rel)
            return
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                print("  skip           %s is not valid JSON -- hooks not merged. Fix it and re-run." % rel)
                return
            if not isinstance(data, dict):
                print("  skip           %s is not an object -- hooks not merged." % rel)
                return
        added = mutate(data)
        if added is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("  %s %s (%d hook%s)" % ("merge         " if added else "unchanged     ",
                                      rel, added, "" if added == 1 else "s"))

    def install_harness_hooks(self):
        """The same six rules under Gemini CLI and the three shell rules under Cursor,
        through .claude/hooks/adapter.sh. Only for harnesses this install wired."""
        if "GEMINI.md" in self.harnesses:
            def gemini(data):
                hooks = data.setdefault("hooks", {})
                if not isinstance(hooks, dict):
                    print("  skip           .gemini/settings.json has a non-object 'hooks' -- not merged.")
                    return None
                entries = hooks.setdefault("BeforeTool", [])
                if not isinstance(entries, list):
                    return None
                added = 0
                for name, _, matcher, _, status in self.HOOK_SPECS:
                    command = 'sh "$GEMINI_PROJECT_DIR"/.claude/hooks/adapter.sh gemini %s' % name
                    if any(isinstance(e, dict) and any(isinstance(h, dict) and h.get("command") == command
                                                       for h in (e.get("hooks") or []))
                           for e in entries):
                        continue
                    entries.append({"matcher": self.GEMINI_MATCHERS[matcher],
                                    "hooks": [{"type": "command", "command": command,
                                               "name": "ai-sdlc " + name[:-3],
                                               "description": status}]})
                    added += 1
                return added
            self.merge_json_hooks(".gemini/settings.json", gemini)
        if ".cursor/rules/agents.mdc" in self.harnesses:
            def cursor(data):
                data.setdefault("version", 1)
                hooks = data.setdefault("hooks", {})
                if not isinstance(hooks, dict):
                    print("  skip           .cursor/hooks.json has a non-object 'hooks' -- not merged.")
                    return None
                entries = hooks.setdefault("beforeShellExecution", [])
                if not isinstance(entries, list):
                    return None
                added = 0
                for name, _, matcher, _, _ in self.HOOK_SPECS:
                    if "Bash" not in matcher:
                        continue
                    command = 'sh "$CURSOR_PROJECT_DIR"/.claude/hooks/adapter.sh cursor %s' % name
                    if any(isinstance(e, dict) and e.get("command") == command for e in entries):
                        continue
                    entries.append({"command": command, "timeout": 15})
                    added += 1
                return added
            self.merge_json_hooks(".cursor/hooks.json", cursor)

    def apply_git_ignores(self):
        want_gitignore = bool(self.o.gitignore_tools)
        want_exclude = bool(self.o.git_exclude)

        if want_gitignore:
            gi_path = ensure_inside(self.target, self.target / ".gitignore")
            already = False
            content = ""
            if gi_path.exists():
                try:
                    content = gi_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if re.match(r"^\s*(\/)?\.ai-sdlc(\/)?\s*$", line):
                            already = True
                            break
                except (IOError, OSError):
                    pass
            if already:
                self.skipped += 1
                print("  skip (exists)  .ai-sdlc/ already in %s" % self.rel(gi_path))
            elif self.o.dry_run:
                self.added += 1
                print("  would ignore   .ai-sdlc/ in %s" % self.rel(gi_path))
            else:
                entry = ("\n" if content and not content.endswith("\n") else "") + "# Nuhut AI SDLC tools and runtime\n.ai-sdlc/\n"
                atomic_write_text(gi_path, content + entry)
                self.added += 1
                print("  gitignore      .ai-sdlc/ (added to %s)" % self.rel(gi_path))

        if want_exclude:
            git_dir = self.target / ".git"
            ex_path = None
            if git_dir.is_dir():
                ex_path = git_dir / "info" / "exclude"
            elif git_dir.is_file():
                try:
                    txt = git_dir.read_text(encoding="utf-8").strip()
                    if txt.startswith("gitdir:"):
                        gd = Path(txt[7:].strip())
                        if not gd.is_absolute():
                            gd = (self.target / gd).resolve()
                        ex_path = gd / "info" / "exclude"
                except (IOError, OSError):
                    pass
            if ex_path is not None:
                already = False
                content = ""
                if ex_path.exists():
                    try:
                        content = ex_path.read_text(encoding="utf-8")
                        for line in content.splitlines():
                            if re.match(r"^\s*(\/)?\.ai-sdlc(\/)?\s*$", line):
                                already = True
                                break
                    except (IOError, OSError):
                        pass
                if already:
                    self.skipped += 1
                    print("  skip (exists)  .ai-sdlc/ already in %s" % self.rel(ex_path))
                elif self.o.dry_run:
                    self.added += 1
                    print("  would exclude  .ai-sdlc/ in %s" % self.rel(ex_path))
                else:
                    ex_path.parent.mkdir(parents=True, exist_ok=True)
                    entry = ("\n" if content and not content.endswith("\n") else "") + "# Nuhut AI SDLC tools and runtime\n.ai-sdlc/\n"
                    atomic_write_text(ex_path, content + entry)
                    self.added += 1
                    print("  git-exclude    .ai-sdlc/ (added to %s)" % self.rel(ex_path))
            elif not self.o.dry_run:
                sys.stderr.write("warning: --git-exclude requested but %s is not a git repository\n" % self.target)

    def note_profile(self):
        """A reader must be able to tell a deliberate absence from a broken install."""
        if self.o.profile != "compact" or self.o.dry_run:
            return
        rel = "%s/CARD.md" % self.docs
        if rel in self.fresh:
            self.edit(rel, lambda text: text + self.COMPACT_NOTE)

    POINTER = ("Read and follow `AGENTS.md` in this directory. It is the operating "
               "contract for this repository and it takes precedence over habit.")

    def skill_roots(self):
        roots = [Path(".claude") / "skills"]
        if getattr(self, "shared_skills", False):
            roots.append(Path(".agents") / "skills")
        return roots

    GIT_HOOK_CALLS = (
        ("pre-commit", "sh .ai-sdlc/git-hooks/pre-commit"),
        ("commit-msg", 'sh .ai-sdlc/git-hooks/commit-msg "$1"'),
    )

    def install_git_hooks(self):
        """Harness-independent guards git itself runs. The scripts are kit-managed under
        .ai-sdlc/git-hooks/; the project's own hook mechanism gets one line that calls
        them and is otherwise left alone, because that file is somebody's workflow."""
        if not self.o.git_hooks:
            return
        names = ["pre-commit"] if self.o.git_hooks == "secrets" else ["pre-commit", "commit-msg"]
        dest_dir = ensure_inside(self.target, self.target / ".ai-sdlc" / "git-hooks")
        for name in names + ["lib.sh"]:
            src = SRC / "optional" / ("hooks" if name == "lib.sh" else "git-hooks") / name
            if self.install_file(src, dest_dir / name) and not self.o.dry_run and name != "lib.sh":
                os.chmod(dest_dir / name, 0o755)
        calls = [(n, c) for n, c in self.GIT_HOOK_CALLS if n in names]
        root = self.target
        if (root / ".pre-commit-config.yaml").exists() or (root / ".pre-commit-config.yml").exists():
            print("  note           .pre-commit-config.yaml owns the git hooks. Add under `repos:`")
            print("                   - repo: local")
            print("                     hooks:")
            for name, call in calls:
                print("                       - id: nuhut-%s" % name)
                print("                         name: nuhut %s guard" % name)
                print("                         entry: %s" % call.replace(' "$1"', ""))
                print("                         language: system")
                print("                         pass_filenames: %s" % ("true" if name == "commit-msg" else "false"))
                if name == "commit-msg":
                    print("                         stages: [commit-msg]")
            return
        lefthook = [p for p in ("lefthook.yml", "lefthook.yaml", ".lefthook.yml") if (root / p).exists()]
        if lefthook:
            print("  note           %s owns the git hooks. Add:" % lefthook[0])
            for name, call in calls:
                print("                   %s:" % name)
                print("                     commands:")
                print("                       nuhut-%s:" % name)
                print("                         run: %s" % call.replace('"$1"', "{1}"))
            return
        if (root / ".husky").is_dir():
            self.chain_git_hooks(root / ".husky", calls, shebang=False)
            return
        hooks_path = ""
        try:
            hooks_path = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=str(root),
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        universal_newlines=True).stdout.strip()
        except OSError:
            pass
        if hooks_path:
            hooks_dir = Path(hooks_path) if os.path.isabs(hooks_path) else root / hooks_path
            try:
                hooks_dir = ensure_inside(root, hooks_dir)
            except Exception:
                print("  note           core.hooksPath points outside the project (%s). Add to its"
                      % hooks_path)
                for name, call in calls:
                    print("                 %s: %s" % (name, call))
                return
            self.chain_git_hooks(hooks_dir, calls, shebang=True)
            return
        git_dir = root / ".git"
        if git_dir.is_dir():
            self.chain_git_hooks(git_dir / "hooks", calls, shebang=True)
            return
        print("  note           not a git repository yet. After `git init`, re-run with --git-hooks,")
        print("                 or add to .git/hooks/:")
        for name, call in calls:
            print("                 %s: %s" % (name, call))

    def chain_git_hooks(self, hooks_dir, calls, shebang):
        for name, call in calls:
            path = hooks_dir / name
            rel = self.rel(path)
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                if call.split()[1] in text:
                    print("  unchanged      %s (already calls the kit hook)" % rel)
                    continue
                if self.o.dry_run:
                    print("  would append   %s (call to %s)" % (rel, call.split()[1]))
                    continue
                joiner = "" if text.endswith("\n") or not text else "\n"
                atomic_write_text(path, text + joiner + call + "\n")
                print("  append         %s (call to %s)" % (rel, call.split()[1]))
            else:
                if self.o.dry_run:
                    print("  would add      %s" % rel)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(path, ("#!/bin/sh\n" if shebang else "") + call + "\n")
                print("  add            %s" % rel)
            try:
                os.chmod(path, os.stat(path).st_mode | 0o111)
            except OSError:
                pass

    def wire_harnesses(self):
        """Nothing in this kit runs unless the agent is told to read AGENTS.md, and each
        tool looks in a different file. A pointer that is missing fails silently: the
        install looks complete and the contract is never opened."""
        for rel, header in HARNESS_POINTERS:
            path = ensure_inside(self.target, self.target / rel)
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                if "AGENTS.md" in text:
                    continue
                if self.o.dry_run:
                    print("  would append   %s (pointer to AGENTS.md)" % rel)
                    continue
                joiner = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
                atomic_write_text(path, text + joiner + "## Operating contract\n\n"
                                  + self.POINTER + "\n")
                print("  append         %s (pointer to AGENTS.md)" % rel)
                self.wired.append(rel)
                continue
            if rel not in self.harnesses:
                continue
            if self.o.dry_run:
                print("  would add      %s" % rel)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, header + self.POINTER + "\n")
            print("  add            %s (pointer to AGENTS.md)" % rel)
            self.wired.append(rel)

    def selected_commands(self):
        commands = {}
        for sid, _, key in CMD_FIELDS:
            raw = self.w.a[sid] if sid in self.w.a else self.w.det.cmds.get(key, "")
            value = plain_text(raw)
            if value:
                commands[key] = value
        return commands

    def testing_profile(self):
        d = self.w.det
        return {
            "schema": 1,
            "generated_by": "nuhut %s" % VERSION,
            "confirmation_required": True,
            "adapters": d.adapters,
            "languages": d.lang,
            "frameworks": d.fw,
            "databases_and_data_layers": d.db,
            "migration_tools": d.migrations,
            "test_tools": d.test,
            "commands": self.selected_commands(),
        }

    def project_profile(self):
        """The charter is the source of truth and a human reads it. This is the same
        shape in a form a command or a skill can branch on without parsing prose."""
        w, d = self.w, self.w.det
        return {
            "schema": 2,
            "kit_version": VERSION,
            "generated": today(),
            "declared": bool(w.interactive),
            "charter": "%s/project/charter.md" % self.docs,
            "docs_dir": self.docs,
            "prefix": self.ctx.get("PREFIX", ""),
            "facts": dict((fid, bool(w.fact(fid))) for fid in FACT_IDS),
            "multilingual": w.multilingual(),
            "languages": w.languages(),
            "roles": w.active_roles(),
            "skills": w.chosen_skills(),
            "commands": self.selected_commands(),
            "budgets": {},
            "profile": self.o.profile,
            "effort_mode": selected_effort(w).lower(),
            "acquisition_profile": selected_acquisition(w).lower(),
            "dev_method": selected_dev_method(w).lower(),
            "decision_style": selected_decision(w).lower(),
            "independent_review": selected_independent_review(w),
            "harnesses": sorted(self.wired),
            "platform": w.a.get("platform", "") if w.a.get("platform", "none") != "none" else "",
            "deploy_platforms": installed_platforms(self.target, self.docs, self.platforms),
            "gitignore_tools": bool(self.o.gitignore_tools),
            "git_exclude": bool(self.o.git_exclude),
            "detected": {
                "adapters": d.adapters,
                "languages": d.lang,
                "frameworks": d.fw,
                "data_layers": d.db,
                "migration_tools": d.migrations,
                "ml": d.ml,
                "vector_stores": d.vector,
                "data_tooling": d.dataeng,
                "messaging": d.messaging,
                "infrastructure": d.iac,
                "acquisition": d.scrape,
                "deploy_platforms": d.deploy,
                "load_tooling": d.load,
            },
        }

    def write_profile(self):
        """Rewritten on every run, unlike installed documents: it is derived from the
        answers and the repository, so a stale copy is worse than no copy. It never
        contains anything a human wrote — the charter holds that, and wins on conflict."""
        dest = ensure_inside(self.target, self.target / PROFILE_REL)
        existed = dest.exists()
        # A non-interactive re-run (say, adding --hooks later) has only default answers.
        # Rebuilding from those would erase the facts, roles and skills the project was
        # set up with, so an existing profile is only re-stamped.
        keep = existed and not self.w.interactive
        if self.o.dry_run:
            print("  %s %s" % ("would keep    " if keep else "would add     ", PROFILE_REL))
            return
        if keep:
            refresh_profile(self.target)
            try:
                data = json.loads(dest.read_text(encoding="utf-8"))
            except ValueError:
                data = None
            if isinstance(data, dict):
                # Derived from files and flags rather than answers, so safe to refresh.
                merged = list(data.get("deploy_platforms") or [])
                for pid in installed_platforms(self.target, self.docs, self.platforms):
                    add(merged, pid)       # a platform declared without a checklist stays
                data["deploy_platforms"] = merged
                data["harnesses"] = sorted(set(data.get("harnesses") or []) | set(self.wired))
                atomic_write_text(dest, json.dumps(data, indent=2, sort_keys=True) + "\n")
            print("  keep           %s (non-interactive run; answers not re-asked)"
                  % PROFILE_REL)
            return
        atomic_write_text(dest, json.dumps(self.project_profile(), indent=2,
                                           sort_keys=True) + "\n")
        print("  %s         %s" % ("update" if existed else "add   ", PROFILE_REL))

    def scaffold_test_plan(self):
        rel = "%s/project/test-plan.md" % self.docs
        dest = self.target / rel
        source = SRC / "template" / "docs" / "templates" / "test-plan.md"
        text = substitute(source.read_text(encoding="utf-8"), self.ctx)
        text = fill_line(text, "last-reviewed:", "last-reviewed: %s" % today())
        d = self.w.det
        rows = (
            ("Adapters", ", ".join(d.adapters) or "none detected"),
            ("Languages", d.csv("lang") or "unknown"),
            ("Frameworks", d.csv("fw") or "none detected"),
            ("Test tooling", d.csv("test") or "none detected"),
            ("Data stores / layers", d.csv("db") or "none detected"),
            ("Migration tooling", d.csv("migrations") or "none detected"),
        )
        profile = ["## Detected profile", "",
                   "> Generated from repository markers on %s. Confirm every row; detection is"
                   % today(),
                   "> evidence to review, not a dependency installation or a correctness claim.", "",
                   "| Concern | Detected |", "| --- | --- |"]
        profile.extend("| %s | %s |" % (_cell(label), _cell(value)) for label, value in rows)
        if d.db:
            profile.extend(("", "### Database integration baseline", "",
                            "- Run integration tests against the real database engine and supported version, not an in-memory substitute.",
                            "- Start from an empty database, apply every migration forward, and exercise rollback or restore.",
                            "- Cover transactions, constraints, concurrent writes, retry/idempotency, and deletion semantics.",
                            "- Use synthetic data; never copy production data without explicit approval and documented controls."))
        text = text.replace("## Commands\n", "\n".join(profile) + "\n\n## Commands\n", 1)
        added = self.install_text(dest, text)
        if self.w.fact("ai") or d.ml or d.vector:
            self.scaffold_eval_plan()
        profile_dest = self.target / ".ai-sdlc" / "testing-profile.json"
        self.install_text(profile_dest,
                          json.dumps(self.testing_profile(), indent=2, sort_keys=True) + "\n")
        if added:
            charter_rel = "%s/project/charter.md" % self.docs
            if charter_rel in self.fresh:
                self.edit(charter_rel, lambda value: tick_artifact(value, "test-plan"))

    def scaffold_eval_plan(self):
        """A probabilistic surface with no golden set has nothing to be measured
        against, so the plan is the artifact that has to exist first — empty, dated,
        and honest about being empty rather than absent and unnoticed."""
        rel = "%s/project/eval-plan.md" % self.docs
        source = SRC / "template" / "docs" / "templates" / "eval-plan.md"
        text = substitute(source.read_text(encoding="utf-8"), self.ctx)
        text = fill_line(text, "last-reviewed:", "last-reviewed: %s" % today())
        d = self.w.det
        found = ", ".join(d.ml + d.vector) or "none identified"
        note = ("> Created at install on %s because model, retrieval, or evaluation "
                "tooling was\n> detected in this repository (%s). Nothing below is "
                "filled in: a golden set\n> nobody has written is the first task, not a "
                "formality. Until it exists, no\n> claim about this system's quality is "
                "sayable.\n\n" % (today(), found))
        text = text.replace("## What is being evaluated\n", note + "## What is being evaluated\n", 1)
        if self.install_text(self.target / rel, text):
            charter_rel = "%s/project/charter.md" % self.docs
            if charter_rel in self.fresh:
                self.edit(charter_rel, lambda value: tick_artifact(value, "eval-plan"))

    def ci_text(self, provider):
        commands = self.selected_commands()
        ordered = [(key, commands[key]) for _, _, key in CMD_FIELDS
                   if key not in ("run",) and key in commands]
        if provider == "github":
            lines = ["name: Project quality", "", "on:", "  workflow_dispatch:",
                     "", "permissions:", "  contents: read", "",
                     "jobs:", "  quality:", "    runs-on: ubuntu-latest", "    steps:",
                     "      - uses: actions/checkout@v4",
                     "      - name: SDLC records",
                     "        run: python3 .ai-sdlc/bin/sdlc.py doctor --strict"]
            for key, command in ordered:
                lines.extend(("      - name: %s" % key.replace("_", " ").title(),
                              "        run: %s" % json.dumps(command)))
            lines.extend(("", "# Manual-only by default. Confirm commands, runtime, and service versions",
                          "# from the charter before adding push or pull_request triggers.", ""))
            return "\n".join(lines)
        lines = ["stages:", "  - quality", "", "quality:", "  stage: quality",
                 "  when: manual", "  script:",
                 "    - python3 .ai-sdlc/bin/sdlc.py doctor --strict"]
        for _, command in ordered:
            lines.append("    - %s" % json.dumps(command))
        lines.extend(("", "# Manual-only by default. Confirm commands, runtime, and service versions",
                      "# from the charter before making this job automatic or required.", ""))
        return "\n".join(lines)

    def scaffold(self):
        if self.o.scaffold_tests:
            self.scaffold_test_plan()
        if self.o.scaffold_ci:
            dest = (self.target / ".github" / "workflows" / "quality.yml"
                    if self.o.scaffold_ci == "github" else self.target / ".gitlab-ci.yml")
            self.install_text(dest, self.ci_text(self.o.scaffold_ci))

    # -- the answers -----------------------------------------------------------
    def tailor(self):
        """Only for files this run created, and only when a human answered the questions:
        an answer nobody gave must not be written down as a decision."""
        w = self.w
        charter_rel = "%s/project/charter.md" % self.docs
        if not w.interactive:
            # --deploy is an answer given on the command line; nothing else is.
            if charter_rel in self.fresh and self.edit(charter_rel, self.flag_rows):
                return [charter_rel]
            return []
        touched = []
        if charter_rel in self.fresh and self.edit(charter_rel, self.charter):
            touched.append(charter_rel)
        if "AGENTS.md" in self.fresh and self.edit("AGENTS.md", self.agents):
            touched.append("AGENTS.md")
        arch_rel = "%s/project/architecture.md" % self.docs
        if self.seed_architecture(arch_rel):
            touched.append(arch_rel)
            self.edit(charter_rel, lambda text: tick_artifact(text, "architecture"))
        return touched

    def record_manifest(self):
        """Record only portable files that exactly match this kit's rendered source."""
        if self.o.dry_run or (self.target / MANIFEST_REL).exists():
            return
        planned = managed_source_texts(self.target, self.docs, self.ctx, self.o.profile)
        owned = {}
        for rel, expected in planned.items():
            path = self.target / rel
            if path.is_file() and sha256_file(path) == sha256_text(expected):
                owned[rel] = sha256_file(path)
        regions = {}
        agents = self.target / AGENTS_REL
        if agents.is_file():
            parts = agents_split(agents.read_text(encoding="utf-8"))
            if parts:
                regions[AGENTS_REL] = sha256_text(parts[1])
        write_manifest(self.target, self.docs, owned, regions)
        print("  add            %s (%d managed files)" % (MANIFEST_REL, len(owned)))

    def flag_rows(self, text):
        """The rows a command-line flag answered. Anything left at its default stays
        blank: the documented default applies, and nobody is recorded as choosing it."""
        if self.platforms:
            text = self.platform_row(text)
        if self.o.effort_given:
            text = fill_row(text, "**Default effort mode**", selected_effort(self.w))
        if self.o.acquisition_given:
            text = fill_row(text, "**Acquisition profile**", selected_acquisition(self.w))
        if self.o.dev_method_given:
            text = fill_row(text, "**Development method**", selected_dev_method(self.w))
        if self.o.decision_given:
            text = fill_row(text, "**Decision style**", selected_decision(self.w))
        if self.o.tier_rules_given:
            text = fill_row(text, "**Tier rules**", selected_tier_rules(self.w))
        if self.o.independent_review_given:
            text = fill_row(text, "**Independent review required for**",
                            "`%s`" % selected_independent_review(self.w))
        return text

    def platform_row(self, text):
        return fill_row(text, "**Deployment platforms**", platform_cell(self.platforms))

    def charter(self, text):
        w, a = self.w, self.w.a
        text = self.platform_row(text)
        if a.get("owner"):
            text = fill_line(text, "owner:", "owner: %s" % json.dumps(plain_text(a["owner"])))
        text = fill_line(text, "last-reviewed:", "last-reviewed: %s" % today())

        text = fill_row(text, "**What it is**", a.get("what"))
        text = fill_row(text, "**Repository**", a.get("repo"))
        text = fill_row(text, "**Accountable human**", a.get("owner"))
        if a.get("prefix"):
            text = fill_row(text, "**Work item prefix**", "`%s`" % a["prefix"])

        for sid, label in zip([s[0] for s in STACK_FIELDS],
                              ("Language / runtime", "Package manager", "Framework(s)",
                               "Data store(s)", "Auth & Identity", "Hosting & Cloud provider", "CI", "Test tooling")):
            text = fill_row(text, label, a.get(sid))
            # Also fill legacy/alternative labels if present
            if label == "Auth & Identity":
                text = fill_row(text, "Auth", a.get(sid))
            elif label == "Hosting & Cloud provider":
                text = fill_row(text, "Hosting", a.get(sid))
        # Derived from the key rather than zipped against a parallel list: a stage
        # added to one and not the other would silently write into the wrong row.
        for sid, _, key in CMD_FIELDS:
            label = {"install": "Install", "run": "Run locally"}.get(key, "`checks.%s`" % key)
            text = fill_row(text, label, a.get(sid))

        text = fill_row(text, "**Default branch**", a.get("branch"))
        text = fill_row(text, "**Direct commits to it**",
                        "allowed" if a.get("direct") else
                        "not allowed — work goes through a branch and a review")
        text = fill_row(text, "**Platform**", a.get("platform"))
        text = fill_row(text, "**Human approval required for**", a.get("approval"))
        text = fill_row(text, "**Approvers**", a.get("approvers"))
        text = fill_row(text, "**Staleness threshold**", a.get("staleness"))
        text = fill_row(text, "**Default effort mode**", selected_effort(w))
        text = fill_row(text, "**Acquisition profile**", selected_acquisition(w))
        text = fill_row(text, "**Development method**", selected_dev_method(w))
        if self.o.tier_rules_given or a.get("tier"):
            text = fill_row(text, "**Tier rules**", selected_tier_rules(w))
        if self.o.independent_review_given:
            text = fill_row(text, "**Independent review required for**",
                            "`%s`" % selected_independent_review(w))
        text = fill_row(text, "**Decision style**", selected_decision(w))
        if a.get("access_model"):
            text = fill_row(text, "**Access level model**", a.get("access_model"))
        if a.get("mfa_policy"):
            text = fill_row(text, "**MFA / OTP policy**", a.get("mfa_policy"))
        text = fill_row(text, "**Accessibility target**",
                        a.get("a11y") or ("" if w.fact("ui") else
                                          "not applicable — no interface"))
        text = fill_row(text, "**Primary outcome**", a.get("outcome"))
        if not w.fact("pii"):
            text = fill_row(text, "**Data categories held**",
                            "none — declared at install; re-check whenever a feature "
                            "starts collecting anything")

        # languages
        if w.multilingual():
            langs = w.languages()
            rtl = w.rtl_languages()
            text = fill_row(text, "**Ships in**", ", ".join(langs))
            text = fill_row(text, "**Source language**", langs[0] if langs else "")
            if langs:
                ltr = [x for x in langs if x not in rtl]
                if rtl and ltr:
                    direction = ("both — right-to-left for %s, left-to-right for %s"
                                 % (", ".join(rtl), ", ".join(ltr)))
                elif rtl:
                    direction = "right-to-left (%s)" % ", ".join(rtl)
                else:
                    direction = "left-to-right only"
                text = fill_row(text, "**Writing directions**", direction)
            text = fill_row(text, "**Message catalogue**", a.get("catalog"))
            text = fill_row(text, "**Translation workflow**", a.get("translation"))
            text = fill_row(text, "**Terminology / glossary**", a.get("glossary"))
        else:
            text = fill_row(text, "**Ships in**",
                            "one language — declared at install")
            text = fill_row(text, "**Writing directions**", "left-to-right only")

        rules = (
            ("ux-designer", w.fact("ui"), "no interface of any kind in this project"),
            ("brand-designer", w.fact("visual"), "no visual interface"),
            ("copywriter", w.fact("ui") or w.fact("public"), "no user-visible text"),
            ("accessibility", w.fact("ui"), "no interface to make accessible"),
            ("seo", w.fact("public"), "nothing here is publicly discoverable"),
            ("cro-analyst", w.fact("conv"), "no conversion or activation goal"),
            ("devops-sre", w.fact("deploy"), "not deployed or operated by this team"),
            ("privacy-legal", w.fact("pii"),
             "no personal data, tracking, or public claims — declared at install"),
            ("localisation", w.multilingual(),
             "ships in one language — declared at install"),
        )
        for role, active, reason in rules:
            text = set_role(text, role, bool(active), reason)
        return text

    def agents(self, text):
        text = fill_field(text, "**Human approval required for:**", self.w.a.get("approval"))
        text = fill_field(text, "**Forbidden in this project:**", self.w.a.get("forbidden"))
        return text

    def seed_architecture(self, rel):
        """architecture.md is the one artifact the installer instantiates: most of its
        Components and External dependencies are readable straight out of the repo."""
        w, d = self.w, self.w.det
        if self.o.dry_run:
            return False
        dest = ensure_inside(self.target, self.target / rel)
        if dest.exists():
            return False
        if not (d.components or d.services or d.integrations or d.mono_tool
                or w.a.get("shape") or w.a.get("critical") or w.a.get("expensive")):
            return False
        text = substitute((SRC / "template" / "docs" / "templates" / "architecture.md")
                          .read_text(encoding="utf-8"), self.ctx)
        text = fill_line(text, "last-reviewed:", "last-reviewed: %s" % today())
        note = ("> Rows marked _(detected at install)_ were read out of the repository by "
                "the installer\n> on %s. They are a starting point to confirm, not a "
                "description anyone has checked.\n" % today())
        text = text.replace("## Stack\n", note + "\n## Stack\n", 1)

        rows = []
        for name, kind, path in d.components:
            rows.append("| `%s` | _(detected at install: %s — describe it)_ | | |"
                        % (path, kind))
        for service in d.services:
            rows.append("| `%s` | _(detected at install: compose service — describe it)_ | | |"
                        % service)
        if rows:
            text = text.replace("| Component | Responsibility | Owns (data) | Depends on |\n"
                                "| --- | --- | --- | --- |\n| | | | |",
                                "| Component | Responsibility | Owns (data) | Depends on |\n"
                                "| --- | --- | --- | --- |\n" + "\n".join(rows), 1)
        dep_rows = ["| %s | %s | _(unknown — fill in)_ | | |" % (svc, use)
                    for svc, use in d.integrations]
        if dep_rows:
            text = text.replace("| Service | Used for | Failure behaviour | Timeout | Fallback |\n"
                                "| --- | --- | --- | --- | --- |\n| | | | | |",
                                "| Service | Used for | Failure behaviour | Timeout | Fallback |\n"
                                "| --- | --- | --- | --- | --- |\n" + "\n".join(dep_rows), 1)

        sketch = []
        if d.mono_tool:
            sketch.append("%s" % d.mono_tool)
        for name, kind, path in d.components:
            sketch.append("  %-24s %s" % (path, kind))
        for service in d.services:
            sketch.append("  %-24s compose service" % service)
        for svc, use in d.integrations:
            sketch.append("  -> %-21s %s" % (svc, use))
        if sketch:
            text = text.replace("<sketch>", "\n".join(sketch), 1)
        if w.a.get("shape"):
            text = text.replace("```\n" + ("\n".join(sketch) if sketch else "<sketch>") + "\n```",
                                "```\n" + ("\n".join(sketch) if sketch else "<sketch>")
                                + "\n```\n\n" + plain_text(w.a["shape"])
                                + " _(stated at install)_", 1)
        if w.a.get("critical"):
            text = text.replace("## Constraints that shaped this\n",
                                "## Constraints that shaped this\n\n**Must not fail or lose "
                                "data:** %s _(stated at install)_\n"
                                % plain_text(w.a["critical"]), 1)
        if w.a.get("expensive"):
            text = text.replace("## Known limitations\n",
                                "## Known limitations\n\n**Expensive to reverse:** %s "
                                "_(stated at install — worth an ADR)_\n"
                                % plain_text(w.a["expensive"]), 1)
        atomic_write_text(dest, text)
        print("  add            %s" % rel)
        self.added += 1
        return True


# ---------------------------------------------------------------- upgrade mode

def refresh_profile(target):
    """Re-stamp generated metadata and add safe defaults for new profile fields.

    Project-authored values stay in the charter. An upgrade cannot infer whether the old
    Beast label meant implementation effort or acquisition policy, so it deliberately
    uses the safe defaults and lets the doctor flag the legacy charter row.
    """
    path = Path(target) / PROFILE_REL
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (IOError, OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    changed = data.get("kit_version") != VERSION or data.get("schema") != 2
    data["kit_version"] = VERSION
    data["schema"] = 2
    if "effort_mode" not in data:
        data["effort_mode"] = "normal"
        changed = True
    if "acquisition_profile" not in data:
        data["acquisition_profile"] = "standard"
        changed = True
    if "dev_method" not in data:
        data["dev_method"] = "item"
        changed = True
    if "decision_style" not in data:
        data["decision_style"] = "guide"
        changed = True
    if "deploy_platforms" not in data:
        data["deploy_platforms"] = installed_platforms(target, data.get("docs_dir") or "docs")
        changed = True
    if not changed:
        return
    try:
        atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("  update         %s (schema and kit version)" % PROFILE_REL)
    except (IOError, OSError):
        pass


def is_docs_root(path):
    """A compact install has no numbered process documents, so the marker cannot be one
    of them: CARD.md is present in every profile and README.md in every version."""
    return ((path / "process" / "00-operating-model.md").exists()
            or (path / "CARD.md").exists()
            or (path / "roles" / "README.md").exists())


def find_docs(target, preferred):
    names = [preferred]
    manifest = load_manifest(target)
    if manifest and isinstance(manifest.get("docs_dir"), str):
        names.append(manifest["docs_dir"])
    names.extend(("docs", "sdlc-docs"))
    for name in names:
        if is_docs_root(target / name):
            return name
    return ""


def upgrade(target, o):
    if o.preset or o.tier_rules_given:
        print("note: --preset and --tier-rules apply to new installs. An upgrade keeps the "
              "project's charter; edit its rows to change them.")
    docs = find_docs(target, o.docs_dir)
    if not docs:
        sys.stderr.write("error: no installed kit found under %s/%s -- nothing to "
                         "upgrade.\n" % (target, o.docs_dir))
        sys.stderr.write("       Run without --upgrade to install for the first time.\n")
        return 1
    prefix = o.prefix
    charter = target / docs / "project" / "charter.md"
    if charter.exists() and re.search(r"^\| \*\*Operating mode\*\* \|.*Beast",
                                      charter.read_text(encoding="utf-8", errors="replace"), re.M):
        print("  warning        legacy Beast mode is ambiguous; choose Default effort mode "
              "and Acquisition profile in %s" % charter.relative_to(target))
    if not prefix and charter.exists():
        m = re.search(r"^\| \*\*Work item prefix\*\* \| `([A-Z]{2,4})`",
                      charter.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            prefix = m.group(1)
            print("Recovered prefix from charter: %s" % prefix)
    if not prefix and (target / PROFILE_REL).is_file():
        try:
            data = json.loads((target / PROFILE_REL).read_text(encoding="utf-8"))
            value = data.get("prefix") if isinstance(data, dict) else ""
        except (IOError, OSError, ValueError):
            value = ""
        if isinstance(value, str) and normalize_prefix(value):
            prefix = normalize_prefix(value)
            print("Recovered prefix from %s: %s" % (PROFILE_REL.as_posix(), prefix))
    if not prefix:
        sys.stderr.write("error: cannot determine the work item prefix.\n")
        sys.stderr.write("       Pass it explicitly: install.sh %s <PREFIX> --upgrade\n" % target)
        return 1

    class Shim(object):
        pass
    w = Shim()
    w.o, w.target, w.a, w.det = o, target, {"prefix": prefix, "docsdir": docs}, Detected()
    w.interactive = False
    w.chosen_skills = lambda: []
    inst = Installer(w)

    previous = load_manifest(target)
    previous_files = previous.get("files", {}) if previous else {}
    o.profile = installed_profile(target)
    planned = managed_source_texts(target, docs, inst.ctx, o.profile)
    if o.profile == "compact":
        print("Compact profile: the numbered process/ documents stay uninstalled.")
    try:
        for rel in list(planned) + list(previous_files) + [MANIFEST_REL.as_posix()]:
            if rel != MANIFEST_REL.as_posix() and not is_managed_rel(rel, docs):
                raise RuntimeError("manifest contains an unmanaged path: %s" % rel)
            ensure_inside(target, target / rel)
    except RuntimeError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1

    # Commands a pre-3.3 install left unmanaged may carry project edits nobody can tell
    # from an old kit version, so they change only when the project says --adopt.
    unadopted = sorted(rel for rel in planned
                       if rel.startswith((".claude/commands/", ".claude/hooks/", ".agents/skills/"))
                       and (target / rel).is_file()
                       and rel not in previous_files and not o.adopt)
    for rel in unadopted:
        del planned[rel]

    modified, retired_kept, retired_notes = [], [], []
    retired = set((Path(docs) / name).as_posix() for name in RETIRED_DOCS)
    if previous:
        for rel, old_hash in previous_files.items():
            if sha256_file(target / rel) != old_hash:
                if rel in retired:
                    # A retired file someone changed is theirs now: keep it, stop managing it.
                    if (target / rel).is_file():
                        retired_kept.append(rel)
                    continue
                modified.append(rel)
    for rel in retired_kept:
        previous_files = dict(previous_files)
        previous_files.pop(rel, None)
        retired_notes.append("%s is no longer part of the kit (`sdlc.py view --export-html <path>` "
                     "replaces it). It was changed here, so it was left in place; delete it "
                     "when you no longer need it." % rel)
    state_rel = (Path(docs) / RETIRED_STATE).as_posix()
    if (target / state_rel).is_file():
        retired_notes.append("%s fed the retired static status page and is no longer read. It is a "
                     "project record, so the upgrade left it; delete it." % state_rel)

    # Files the kit owns only part of: AGENTS.md sections 1-8, and rows the charter lacks.
    extra, notes, regions = {}, list(retired_notes), {}
    agents_path = target / AGENTS_REL
    kit_agents = substitute((SRC / "template" / "AGENTS.md").read_text(encoding="utf-8"),
                            inst.ctx)
    new_region = agents_split(kit_agents)[1]
    if agents_path.is_file():
        text = agents_path.read_text(encoding="utf-8")
        parts = agents_split(text)
        legacy = None if parts else agents_legacy_split(text)
        if parts:
            recorded = (previous or {}).get("regions", {}).get(AGENTS_REL)
            if recorded and sha256_text(parts[1]) != recorded:
                modified.append("%s (the kit-managed sections 1-8)" % AGENTS_REL)
            else:
                regions[AGENTS_REL] = sha256_text(new_region)
                if parts[0] + new_region + parts[2] != text:
                    extra[AGENTS_REL] = parts[0] + new_region + parts[2]
        elif legacy and o.adopt:
            regions[AGENTS_REL] = sha256_text(new_region)
            extra[AGENTS_REL] = legacy[0] + new_region + "\n\n" + legacy[2]
        elif legacy:
            notes.append("AGENTS.md predates the kit-managed region, so sections 1-8 were "
                         "not updated. Re-run with --upgrade --adopt to replace them (section "
                         "9 is kept, and the old file is backed up).")
        else:
            notes.append("AGENTS.md has no '## 9. Project overrides' heading, so it cannot be "
                         "merged safely. Diff it against %s by hand."
                         % (SRC / "template" / "AGENTS.md"))
    charter_rel = (Path(docs) / "project" / "charter.md").as_posix()
    if (target / charter_rel).is_file():
        kit_charter = substitute((SRC / "template" / "docs" / "project" / "charter.md")
                                 .read_text(encoding="utf-8"), inst.ctx)
        merged, added_rows, unplaced = add_missing_charter_rows(
            (target / charter_rel).read_text(encoding="utf-8"), kit_charter)
        if "Tier rules" in added_rows:
            # A project from before 4.0 worked under the 3.x tier rules. Keep them, and
            # say how to move: an upgrade must not change how a project works silently.
            merged = fill_row(merged, "**Tier rules**", TIER_RULES_UPGRADE)
            added_rows = [r for r in added_rows if r != "Tier rules"]
            extra[charter_rel] = merged
            notes.append("Tier rules set to Strict, which keeps this project's 3.x tiering "
                         "(sensitive topics are Tier 1, every tier writes a worklog line, "
                         "Tier 2 waits for one approver). Set the charter's Tier rules row to "
                         "Standard to tier by blast radius instead (CARD.md, \"Tiers\").")
        if added_rows:
            extra[charter_rel] = merged
            notes.append("The charter gained blank rows for: %s. Fill them in; a blank row "
                         "is Unknown." % ", ".join(added_rows))
        if unplaced:
            notes.append("The kit's charter has rows this one lacks and no neighbour to "
                         "place them by: %s. Copy them from %s." % (", ".join(unplaced),
                         SRC / "template" / "docs" / "project" / "charter.md"))
    stale_commands = [r for r in unadopted if r.startswith(".claude/commands/")]
    stale_hooks = [r for r in unadopted if r.startswith(".claude/hooks/")]
    stale_shared = [r for r in unadopted if r.startswith(".agents/skills/")]
    if stale_shared:
        notes.append("%d files under .agents/skills/ exist but the kit does not own them "
                     "(hand-made, or from before shared skills were managed): %s. They were "
                     "left alone. Re-run with --upgrade --adopt to replace them with the "
                     "kit's versions (backed up first)." % (len(stale_shared), ", ".join(
                         sorted(set(r.split("/")[2] for r in stale_shared)))))
    if stale_commands:
        notes.append("%d /sdlc-* commands predate managed upgrades and were not updated. "
                     "Re-run with --upgrade --adopt to replace them (backed up first)."
                     % len(stale_commands))
    if stale_hooks:
        notes.append("%d hook files predate managed upgrades and were not updated. Older "
                     "hooks fail open when run from a subdirectory, on a `..` path, or on "
                     "a filename containing a quote. Re-run with --upgrade --adopt "
                     "to replace them (backed up first)." % len(stale_hooks))

    if modified:
        sys.stderr.write("error: upgrade stopped; kit-owned files were modified or removed:\n")
        for rel in modified:
            sys.stderr.write("       %s\n" % rel)
        sys.stderr.write("       Move project rules to section 9 of AGENTS.md or the project "
                         "docs, restore these files from the kit, or merge the new kit "
                         "manually.\n")
        return 1

    obsolete = sorted(set(previous_files) - set(planned))
    changed = sorted(rel for rel, content in planned.items()
                     if sha256_file(target / rel) != sha256_text(content))

    if o.dry_run:
        for rel in changed + sorted(extra):
            print("  would update   %s" % rel)
        for rel in obsolete:
            print("  would remove   %s" % rel)
        print("Dry run: %d files would be updated, %d obsolete managed files removed."
              % (len(changed), len(obsolete)))
        return 0

    print("Upgrading Nuhut kit in %s to v%s" % (target, VERSION))
    print("  refreshes the kit's own files: %s/process, roles, templates, platforms, the"
          % docs)
    print("  /sdlc-* commands and the skills already installed. Your charter, backlog,")
    print("  worklog and other project records are never touched.")
    print("")
    if not previous:
        print("  warning        legacy install has no manifest; backing up portable files "
              "before the first managed upgrade")

    affected = changed + obsolete + sorted(extra)
    originals = {}
    for rel in affected:
        path = target / rel
        originals[rel] = path.read_bytes() if path.is_file() else None
    manifest_path = target / MANIFEST_REL
    old_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None

    existing = [rel for rel in affected if originals[rel] is not None]
    if existing:
        stem = "v%s-to-v%s" % ((previous or {}).get("kit_version", "legacy"), VERSION)
        backup_dir = target / ".ai-sdlc" / "backups" / stem
        suffix = 2
        while backup_dir.exists():
            backup_dir = target / ".ai-sdlc" / "backups" / (stem + "-%d" % suffix)
            suffix += 1
        for rel in existing:
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(target / rel), str(dest))
        print("  backup         %s (%d files)" % (backup_dir.relative_to(target), len(existing)))

    try:
        for rel in changed:
            atomic_write_text(target / rel, planned[rel])
            inst.updated += 1
            print("  update         %s" % rel)
        for rel in sorted(extra):
            atomic_write_text(target / rel, extra[rel])
            inst.updated += 1
            print("  update         %s (%s)" % (rel, "kit-managed sections only"
                                               if rel == AGENTS_REL else "rows added"))
        for rel in obsolete:
            path = target / rel
            if path.exists():
                path.unlink()
                print("  remove         %s (obsolete managed file)" % rel)
        hashes = dict((rel, sha256_text(content)) for rel, content in planned.items())
        write_manifest(target, docs, hashes, regions)
        refresh_profile(target)
        repaired = repair_hook_commands(target)
        if repaired:
            print("  update         .claude/settings.json (%d hook command%s anchored on "
                  "$CLAUDE_PROJECT_DIR)" % (repaired, "" if repaired == 1 else "s"))
        inst.apply_git_ignores()
    except Exception as exc:
        for rel, data in originals.items():
            path = target / rel
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write_bytes(path, data)
        if old_manifest is None:
            if manifest_path.exists():
                manifest_path.unlink()
        else:
            atomic_write_bytes(manifest_path, old_manifest)
        sys.stderr.write("error: upgrade failed and managed files were restored: %s\n" % exc)
        return 1
    print("")
    if inst.updated or obsolete:
        print("Done: %d updated, %d obsolete managed files removed." %
              (inst.updated, len(obsolete)))
    else:
        print("Already up to date with v%s: nothing changed." % VERSION)
    print("")
    for note in notes:
        print("note: %s" % note)
        print("")
    have = target / ".claude" / "skills"
    missing = [(name, why) for name, _, why, _ in SKILL_RULES
               if (SRC / "optional" / "skills" / name).is_dir() and not (have / name).is_dir()]
    if missing:
        print("%d kit skills are not installed here (--upgrade never adds one):" % len(missing))
        print("  %s" % ", ".join(name for name, _ in missing))
        print("What each is for: install.sh --list skills. To add the ones that fit, run the")
        print("guided setup again; it only adds files that are missing:")
        print("  %s/install.sh %s --full" % (SRC, target))
    return 0


# ---------------------------------------------------------------- report

def report(w, inst, skills, tailored):
    a = w.a
    docs = inst.docs
    print("")
    if inst.o.dry_run:
        print("Dry run: %d files would be added, %d already exist. Nothing was written."
              % (inst.added, inst.skipped))
        return
    if tailored:
        print("Done: %d added, %d skipped, tailored: %s." % (inst.added, inst.skipped,
                                                             ", ".join(tailored)))
    else:
        print("Done: %d added, %d skipped." % (inst.added, inst.skipped))
    if skills:
        print("Skills installed: %s" % " ".join(skills))
    if inst.fresh:
        print("")
        print("%s:" % t("outro.got"))
        for line in file_tree(sorted(inst.fresh)):
            print("  " + line)
    print("")

    if w.det.platforms:
        print("note: this project appears to live on a managed platform: %s"
              % " ".join(w.det.platforms))
        print("      The platform also edits, syncs, or deploys this repository. The kit must")
        print("      not break it:")
        print("      - Fill in the charter's 'Managed platform' table (sync model, platform-")
        print("        owned files, deploys). Process rules yield to it where they conflict.")
        print("      - Leave the platform's own files alone (e.g. .replit, replit.nix,")
        print("        platform config directories). This installer did not touch them.")
        print("      - Point the platform's instruction file or knowledge base (e.g. replit.md,")
        print("        Lovable project knowledge) at AGENTS.md instead of duplicating it.")
        print("      - See 'Managed platforms' in %s/process/05-change-control.md." % docs)
        print("")
    installed = [pid for pid in inst.platforms if pid in DEPLOY_IDS]
    if installed:
        print("Deployment checklists: %s" % ", ".join(
            "%s/platforms/%s.md" % (docs, pid) for pid in installed))
        if ("%s/project/charter.md" % docs) not in tailored:
            print("      The charter already existed, so it was not edited: add %s to its"
                  % ", ".join(installed))
            print("      'Deployment platforms' row yourself -- the row is authoritative.")
        print("")
    if inst.wired:
        print("Wired to read AGENTS.md: %s" % " ".join(inst.wired))
        print("      Codex, Jules, Zed, Factory and opencode read AGENTS.md directly and")
        print("      needed nothing. Add others later with --harness.")
        print("")
    elif not inst.o.dry_run:
        print("WARNING: nothing in this repository points an agent at AGENTS.md.")
        print("         The kit is installed but will never be read: every agent tool loads")
        print("         its own instruction file, and none of them names AGENTS.md here.")
        print("         Add this line to the one your tool reads (CLAUDE.md, GEMINI.md,")
        print("         AGENT.md, .github/copilot-instructions.md, .cursor/rules/, ...):")
        print("")
        print("           Read and follow `AGENTS.md` in this directory.")
        print("")
        print("         Or re-run with --harness <tool>. Codex, Jules, Zed, Factory and")
        print("         opencode read AGENTS.md directly and need nothing.")
        print("")
    if not inst.ctx.get("PREFIX"):
        print("WARNING: no PREFIX given. {{PREFIX}} is still literal in the installed files.")
        print("         Replace it before use, or re-run against a clean target with a prefix.")
        print("")

    print("Next:")
    if tailored:
        print("  1. Read %s/project/charter.md and correct what setup filled in." % docs)
        print("     Still blank on purpose, because nobody could answer it from here:")
        print("     constraints, environments, sources of truth, and any check command that")
        print("     was not found. A blank cell is read as Unknown, never as 'not applicable'.")
    else:
        print("  1. Fill in %s/project/charter.md -- nothing else is reliable until you do." % docs)
    blanks = charter_blanks(w.target, docs)
    if blanks:
        print("     " + t("outro.later"))
        for line, label in blanks[:6]:
            print("       %s/project/charter.md:%-4d %s" % (docs, line, label))
        if len(blanks) > 6:
            print("       " + t("outro.later_more", n=len(blanks) - 6))
    print("  2. Fill in the Project overrides section at the end of AGENTS.md.")
    if ("%s/project/architecture.md" % docs) in tailored:
        print("  3. Confirm every _(detected at install)_ row in %s/project/architecture.md."
              % docs)
    leftovers = leftover_placeholders(w.target, docs)
    if leftovers:
        print("")
        print("WARNING: unsubstituted {{...}} placeholders remain in:")
        for rel in leftovers[:10]:
            print("           %s" % rel)
        if len(leftovers) > 10:
            print("           ... and %d more" % (len(leftovers) - 10))
    else:
        print("")
        print("Checked: no {{...}} placeholder was left unsubstituted.")

    print("")
    print("Start working:")
    chosen = inst.w.a.get("harnesses")
    if chosen is None:
        chosen = ["claude"] if inst.o.harnesses is None else inst.o.harnesses
    if "claude" in chosen and w.a.get("commands", True):
        print("  Claude Code    open the project and run  /sdlc-plan <what you want to build>")
        print("                 then /sdlc-build, /sdlc-verify, /sdlc-review, /sdlc-log")
    others = [HARNESS_TITLES.get(n, n) for n in chosen if n != "claude"]
    if others or inst.o.native_harnesses:
        names = ", ".join(others + (["Codex and others"] if inst.o.native_harnesses else []))
        print("  %-14s ask it to \"follow AGENTS.md\" and describe the change you want" %
              ("Other tools" if len(others) != 1 else others[0]))
        print("                 (%s)" % names)
    print("  Health check   python3 %s/.ai-sdlc/bin/sdlc.py doctor" % w.target)
    print("  See the state  python3 %s/.ai-sdlc/bin/sdlc.py view --serve" % w.target)

    if w.interactive:
        rec = ["product-brief", "test-plan"]
        if w.fact("ui"):
            rec.append("user-stories")
        if w.fact("visual"):
            rec.append("design-system")
        if w.fact("public"):
            rec.append("content-seo-plan")
        if w.fact("conv"):
            rec.append("measurement-plan")
        if w.fact("pii"):
            rec += ["security-privacy", "threat-model"]
        if w.fact("deploy"):
            rec.append("release-runbook")
        print("")
        print("Artifacts worth writing first for this kind of project:")
        print("  %s" % ", ".join(rec))
        print("  Tick each one in the charter's 'Artifacts in use' list when it exists.")
        if w.multilingual():
            print("")
            print("This project ships in more than one language, so:")
            print("  - %s/process/08-content-and-translation.md is now binding." % docs)
            print("  - the localisation role is active in the charter's roster.")
    if w.interactive:
        print("")
        print(t("review.command"))
        print("  %s" % equivalent_command(w))
    else:
        defaults_taken(w, inst)
    print("")
    print("Later, to pick up a newer version of the portable standards:")
    print("  %s/install.sh %s %s --upgrade" % (SRC, w.target, inst.ctx.get("PREFIX", "<PREFIX>")))


def charter_blanks(target, docs):
    """(line, label) for each charter row still holding only its _(hint)_ or nothing."""
    path = Path(target) / docs / "project" / "charter.md"
    if not path.is_file():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        m = re.match(r"^\| \*\*(.+?)\*\* \|\s*(_\(.*\)_)?\s*\|\s*$", line)
        if m:
            rows.append((n, m.group(1)))
    return rows


def leftover_placeholders(target, docs):
    """Installed files that still hold a {{TOKEN}}: a literal {{PREFIX}} becomes a path
    the agent follows, so this is checked here instead of left to the reader."""
    found = []
    pattern = re.compile(r"\{\{(PROJECT_NAME|PREFIX|DOCS_DIR|KIT_VERSION)\}\}")
    roots = [Path(target) / docs, Path(target) / ".claude", Path(target) / "AGENTS.md"]
    for root in roots:
        files = [root] if root.is_file() else (sorted(root.rglob("*.md")) if root.is_dir() else [])
        for path in files:
            try:
                if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                    found.append(str(path.relative_to(target)))
            except (IOError, OSError):
                continue
    return found


def defaults_taken(w, inst):
    """-y answers nothing, so say what it assumed and which flag changes each."""
    o = inst.o
    rows = []
    if not o.prefix:
        rows.append(("work item prefix", inst.ctx.get("PREFIX", "none"),
                     "give it as the second argument"))
    rows.append(("AI tools", ", ".join((o.harnesses if o.harnesses is not None else ["claude"])
                                       + o.native_harnesses) or "none", "--harness, see --list harnesses"))
    if o.deploy is None:
        found = ", ".join(w.det.deploy) if w.det.deploy else ""
        rows.append(("deploy checklists", "none" + (" (detected: %s)" % found if found else ""),
                     "--deploy %s" % (",".join(w.det.deploy) if found else "<list>")))
    if not o.preset and not (o.effort_given or o.decision_given or o.dev_method_given):
        rows.append(("working style", "charter defaults (team)", "--preset solo|team|regulated"))
    if not (o.hooks or o.git_hooks):
        rows.append(("enforcement", "off", "--hooks and/or --git-hooks"))
    rows.append(("charter", "left blank, nothing declared", "run without -y for guided setup"))
    print("")
    print("Defaults taken (no questions were asked):")
    for what, value, how in rows:
        print("  %-18s %-34s %s" % (what, value, how))


# ---------------------------------------------------------------- main

def main(argv):
    o = parse_args(argv)
    load_locale(o.lang)

    target = None
    if o.target:
        target = resolve_target(o.target, o, TERM)
        if target is None:
            return 1

    interactive = (not o.assume_yes and not o.upgrade and TERM.interactive_in)
    if target is None and not interactive:
        usage()
    if interactive:
        TERM.enable_rich(o.plain)

    if o.upgrade:
        return upgrade(target, o)

    w = Wizard(o)
    w.target = target
    if target is not None:
        after_dest(w, str(target))

    if w.interactive:
        print("")
        print("%s%s%s" % (TERM.B, t("intro.title", version=VERSION), TERM.R))
        TERM.dim(t("intro.what"))
        TERM.say("")
        if TERM.rich:
            TERM.dim(t("intro.rich", **TERM.g))
        else:
            TERM.dim(t("intro.keys1"))
            TERM.dim(t("intro.keys2"))
        TERM.dim(t("intro.keys3"))

    if not w.run(0):
        print("  " + t("review.quit"))
        return 0
    while True:
        choice = w.review()
        if choice is None:
            break
        if choice == QUIT:
            print("  " + t("review.quit"))
            return 0
        if not w.run(choice, single=True):
            print("  " + t("review.quit"))
            return 0

    if not w.interactive:
        # Nobody answered anything, so nothing may be declared on their behalf: the
        # charter keeps its blank cells, and only answer-independent skills install.
        for fid in FACT_IDS:
            w.a[fid] = False
        w.a["multilingual"] = False
        w.a.setdefault("commands", True)
        w.a.setdefault("docsdir", find_docs(w.target, o.docs_dir) or o.docs_dir)

    inst = Installer(w)
    global WRITING
    WRITING = True
    import contextlib
    import io
    # The arrow-key setup already showed every path on request; while copying it prints
    # what needs attention, and the report's "What you got" tree stands in for the list.
    listing = io.StringIO() if TERM.rich else sys.stdout
    try:
        with contextlib.redirect_stdout(listing):
            skills = inst.run()
            tailored = inst.tailor()
            inst.scaffold()
            inst.install_hooks()
            inst.install_git_hooks()
            inst.apply_git_ignores()
            inst.record_manifest()
            inst.write_profile()
    except (IOError, OSError, RuntimeError) as exc:
        sys.stderr.write("error: installation failed: %s\n" % exc)
        return 1
    finally:
        if listing is not sys.stdout:
            for line in listing.getvalue().splitlines():
                if line.strip() and not re.match(r"^\s+(add|skip \(exists\))\s", line):
                    print(line)
    report(w, inst, skills, tailored)
    offer_viewer(w)
    return 0


def offer_viewer(w):
    """The last step of a guided setup: see the project the way agents will record it."""
    script = w.target / RUNTIME_REL
    if not (TERM.rich and w.interactive and script.is_file()):
        return
    print("")
    if ui.confirm(TERM, t("q.viewer"), default=False, help_text=t("h.viewer"),
                  keys=t("keys.confirm", **TERM.g), yes=t("yes"), no=t("no")) is True:
        try:
            subprocess.call([sys.executable, str(script), "view", "--serve"], cwd=str(w.target))
        except KeyboardInterrupt:
            print("")


WRITING = False             # set once files are being copied: Ctrl-C then may leave a partial install


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.stdout.write("\033[?25h" if TERM.tty_out else "")
        print("")
        print("  " + t("cancelled.partial" if WRITING else "cancelled"))
        sys.exit(130)

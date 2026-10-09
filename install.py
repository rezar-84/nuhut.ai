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
from pathlib import Path

SRC = Path(__file__).resolve().parent
VERSION = (SRC / "VERSION").read_text(encoding="utf-8").strip()
MANIFEST_REL = Path(".ai-sdlc") / "manifest.json"
PROFILE_REL = Path(".ai-sdlc") / "profile.json"
STATE_REL = "dashboard-state.js"
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
    "intro.keys1": "Enter = the value in brackets   -  = leave blank   ? = why this is asked",
    "intro.keys2": "b = back one question   s = default the rest of this section   S = default everything",
    "intro.keys3": "Nothing is written until you confirm at the review screen. q quits.",
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
    "q.facts": "Use these? (y = yes, e = edit each)",
    "q.ui": "Is there any interface at all (a CLI counts)?",
    "q.visual": "Is any of it visual (screens, pages, components)?",
    "q.public": "Is any of it publicly discoverable (search, social)?",
    "q.deploy": "Does it deploy to or run somewhere you operate?",
    "q.pii": "Does it hold or process personal data?",
    "q.conv": "Is there a conversion or activation goal to optimise?",
    "q.stack_ok": "Use these? (y = yes, e = edit each, n = leave the table blank)",
    "q.cmds_ok": "Use these? (y = yes, e = edit each, n = leave the table blank)",
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
    "q.effort": "Default effort mode (l = Lean, n = Normal, x = Beast)",
    "h.effort": "Lean minimizes optional work, Normal is balanced, Beast maximizes investigation and verification. Risk-tier requirements never change.",
    "q.acquisition": "Acquisition profile (s = Standard, a = Advanced)",
    "q.devmethod": "Development method (i = Item by item, e = Epic)",
    "h.devmethod": "Item runs one work item at a time and stops at each one's approvals. Epic plans several items together, gets one approval for the plan, and stops at the checkpoints it chooses. Checks, reviews and tier approvals never change.",
    "h.acquisition": "Advanced enables more extraction techniques on authorized targets. It never grants permission to bypass access controls.",
    "q.approval": "Human approval required for",
    "q.forbidden": "Forbidden in this project",
    "h.forbidden": "The specific shortcuts that would be tempting here. Blank = fill in later.",
    "q.deploy": "Where does it deploy? (numbers, comma-separated)",
    "h.deploy": "Each choice installs that platform's checklist into platforms/. Detected ones are pre-selected; pick Other for anything unlisted.",
    "q.platform": "Managed platform co-owning this repo",
    "h.platform": "An AI app builder or cloud IDE that also edits, syncs, or deploys this repo.",
    "q.a11y": "Accessibility target",
    "q.outcome": "Primary outcome success is measured by",
    "h.outcome": "The one user action: sign-up, activation, task completion, purchase.",
    "q.access_model": "Access level model",
    "h.access_model": "Role-Based (RBAC), Simple Owner/User, Multi-tenant Workspace-Scoped, ABAC/ReBAC, or None (Public).",
    "q.mfa_policy": "MFA / OTP policy",
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
    "q.commands": "Install the five /sdlc-* slash commands?",
    "q.skills": "Install the ticked skills? (y = yes, e = choose each, n = none)",

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
    "err.is_kit": "refusing: that is the kit's own directory ({path}).",
    "err.in_kit": "refusing: {path} is inside the kit ({src}).",
    "err.kit_copy": "refusing: {path} is a copy of this kit, not a project to install into.",
    "err.give_project": "Give the project you want to install into: install.sh /path/to/your-project",
    "err.no_target": "a destination is required.",

    "review.title": "Review -- nothing has been written yet",
    "review.prompt": "Enter = write these files, a number = change that answer, q = quit",
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

class Term(object):
    def __init__(self):
        self.interactive_in = sys.stdin.isatty()
        tty_out = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
        self.B = "\033[1m" if tty_out else ""
        self.D = "\033[2m" if tty_out else ""
        self.R = "\033[0m" if tty_out else ""

    def say(self, msg=""):
        print(msg)

    def dim(self, msg):
        print("  %s%s%s" % (self.D, msg, self.R))

    def head(self, msg):
        print("\n%s-- %s %s" % (self.B, msg, self.R))

    def err(self, msg):
        sys.stderr.write("  %s\n" % msg)

    def read(self, prompt, default_hint=""):
        """Returns None at end of input -- callers must treat that as 'no answer given'."""
        if default_hint:
            sys.stdout.write("  %s %s[%s]%s " % (prompt, self.D, default_hint, self.R))
        else:
            sys.stdout.write("  %s " % prompt)
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            return None
        return line.rstrip("\n").rstrip("\r")


TERM = Term()


# ---------------------------------------------------------------- arguments

USAGE = """usage: install.sh <target-project-dir> [PREFIX] [options]

  target dir    the project to install into -- required, and never this directory.
                Omit it only when a terminal is attached, and setup will ask for it.
  PREFIX        2-4 letters for work item IDs, e.g. ACME

  --docs-dir <name>  install the docs under a different directory (default: docs)
  --create           create the target directory if it does not exist
  -y, --yes          no questions: take every default (also implied when stdin is not a
                     terminal, so CI and piped runs never hang)
  --no-skills        do not install anything into .claude/skills/
  --scaffold-tests   create a detected project test plan and machine-readable profile
  --scaffold-ci <provider>
                     create CI for github or gitlab from detected quality commands
  --hooks            install the opt-in Claude Code hooks: deny a commit with no work
                     item ID or with a credential in it, an edit to a path in
                     .ai-sdlc/protected.txt or to a test locked in
                     .ai-sdlc/test-lock.txt, and a command matching
                     .ai-sdlc/gates.txt. Merged into .claude/settings.json without
                     touching anything already there. Needs jq at runtime; without it
                     the hooks allow the call and say so. Never implied by another flag.
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
                     claude, gemini, amp, copilot, cursor, windsurf, cline, aider, or
                     "all". Each gets a pointer file naming AGENTS.md; an instruction
                     file that already exists is appended to, never overwritten. Codex,
                     Jules, Zed, Factory and opencode read AGENTS.md directly and need
                     nothing.
  --adopt            with --upgrade: take over kit files an older version left
                     unmanaged -- sections 1-8 of AGENTS.md and the /sdlc-* commands.
                     The previous copies are backed up first. Needed once per project
                     installed before 3.3; the upgrade says when.
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
        self.harnesses = None   # None: not given; [] : only native harnesses named
        self.profile = "full"
        self.effort_mode = "normal"
        self.acquisition_profile = "standard"
        self.deploy = None          # None: not given; []: explicitly none
        self.adopt = False
        self.effort_given = False
        self.dev_method = "item"
        self.dev_method_given = False
        self.acquisition_given = False
        self.hooks = False
        self.lang = "en"


def usage(code=1):
    sys.stderr.write(USAGE)
    sys.exit(code)


def parse_args(argv):
    o = Options()
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            usage(0)
        elif arg == "--docs-dir":
            if i + 1 >= len(argv):
                usage()
            o.docs_dir, o.docs_dir_given = argv[i + 1], True
            i += 1
        elif arg == "--lang":
            if i + 1 >= len(argv):
                usage()
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
                sys.stderr.write("--scaffold-ci requires github or gitlab\n")
                usage()
            o.scaffold_ci = argv[i + 1]
            i += 1
        elif arg == "--hooks":
            o.hooks = True
        elif arg == "--profile":
            if i + 1 >= len(argv) or argv[i + 1] not in ("full", "compact"):
                sys.stderr.write("--profile requires full or compact\n")
                usage()
            o.profile = argv[i + 1]
            i += 1
        elif arg == "--effort-mode":
            if i + 1 >= len(argv) or argv[i + 1] not in ("lean", "normal", "beast"):
                sys.stderr.write("--effort-mode requires lean, normal, or beast\n")
                usage()
            o.effort_mode, o.effort_given = argv[i + 1], True
            i += 1
        elif arg == "--dev-method":
            if i + 1 >= len(argv) or argv[i + 1] not in ("item", "epic"):
                sys.stderr.write("--dev-method requires item or epic\n")
                usage()
            o.dev_method, o.dev_method_given = argv[i + 1], True
            i += 1
        elif arg == "--acquisition-profile":
            if i + 1 >= len(argv) or argv[i + 1] not in ("standard", "advanced"):
                sys.stderr.write("--acquisition-profile requires standard or advanced\n")
                usage()
            o.acquisition_profile, o.acquisition_given = argv[i + 1], True
            i += 1
        elif arg == "--deploy":
            if i + 1 >= len(argv):
                sys.stderr.write("--deploy requires a comma-separated list\n")
                usage()
            ids, bad = parse_deploy(argv[i + 1])
            if bad is not None:
                sys.stderr.write("unknown deployment platform: %s (known: %s, other, none)\n"
                                 % (bad, ", ".join(DEPLOY_IDS)))
                usage()
            o.deploy = ids
            i += 1
        elif arg == "--harness":
            if i + 1 >= len(argv):
                sys.stderr.write("--harness requires a comma-separated list\n")
                usage()
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
                sys.stderr.write("unknown harness: %s (known: %s)\n"
                                 % (", ".join(unknown), ", ".join(sorted(HARNESS_ALIASES))))
                usage()
            o.harnesses = [x for x in names if x in HARNESS_ALIASES]
            i += 1
        elif arg == "--create":
            o.create = True
        elif arg == "--dry-run":
            o.dry_run = True
        elif arg.startswith("-"):
            sys.stderr.write("unknown option: %s\n" % arg)
            usage()
        else:
            positional.append(arg)
        i += 1
    if len(positional) > 2:
        sys.stderr.write("unexpected argument: %s\n" % positional[2])
        usage()
    if positional:
        o.target = positional[0]
    if len(positional) > 1:
        prefix = normalize_prefix(positional[1])
        if not prefix:
            sys.stderr.write("error: work item prefix %r: %s\n" % (positional[1], t("err.prefix")))
            sys.exit(2)
        o.prefix = prefix
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
                 label=None, cascade=False, secret_default=None):
        self.sid = sid
        self.section = section
        self.kind = kind            # text | yesno | key | multichoice | dest
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

    def skills(self):
        """(name, on, why) for every skill this kit ships, judged by the answers."""
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
            chosen = self.a.get("skill:" + name)
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
    def _control(self, raw, step):
        """Universal keys. Returns (handled, result)."""
        if raw == "b":
            return True, BACK
        if raw == "q":
            return True, QUIT
        if raw == "?":
            if step.help:
                TERM.dim(t(step.help))
            else:
                TERM.dim("no extra detail for this one.")
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

    def _skipping(self, step):
        return (not self.interactive or self.skip_all
                or (self.skip_section and self.skip_section == step.section))

    def ask(self, step):
        if step.kind == "dest" and self.target:      # given on the command line
            return str(self.target)
        if step.section != self.last_section and self.interactive and not self._skipping(step):
            TERM.head(t(step.section))
            self.last_section = step.section
        if step.before and self.interactive and not self._skipping(step):
            step.before(self)
        if self._skipping(step):
            return step.default_for(self)
        handler = {
            "dest": self.ask_dest,
            "text": self.ask_text,
            "yesno": self.ask_yesno,
            "key": self.ask_key,
            "multichoice": self.ask_multi,
        }[step.kind]
        return handler(step)

    def ask_text(self, step):
        default = step.default_for(self)
        while True:
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
                    TERM.dim(out)
                    continue
                value = out
            return value

    def ask_yesno(self, step):
        default = bool(step.default_for(self))
        hint = "Y/n" if default else "y/N"
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

    def ask_multi(self, step):
        default = step.default_for(self)          # list of ints
        for i, label in enumerate(step.options):
            TERM.say("    %s%2d%s  %s" % (TERM.D, i + 1, TERM.R, label))
        while True:
            raw = TERM.read(t(step.prompt), ",".join(str(x) for x in default))
            if raw is None:
                return QUIT
            handled, result = self._control(raw, step)
            if handled:
                if result is None:
                    continue
                return result
            if raw == "":
                return default
            picked, bad = [], False
            for part in re.split(r"[\s,]+", raw.strip()):
                if not part:
                    continue
                if not part.isdigit() or not (1 <= int(part) <= len(step.options)):
                    bad = True
                    break
                if int(part) not in picked:
                    picked.append(int(part))
            if bad or not picked:
                TERM.dim(t("err.number_range", max=len(step.options)))
                continue
            self.explicit.add(step.sid)
            return sorted(picked)

    def ask_dest(self, step):
        if self.target:                            # given on the command line
            return str(self.target)
        while True:
            raw = TERM.read(t("q.dest"), "required")
            if raw is None:
                return QUIT
            if raw in ("q",):
                return QUIT
            if raw == "?":
                TERM.dim(t("h.dest"))
                continue
            if raw == "":
                TERM.dim(t("err.required"))
                continue
            path = os.path.expanduser(raw)
            if not os.path.isdir(path):
                answer = TERM.read(t("q.create", path=path), "Y/n")
                if answer is None:
                    return QUIT
                if answer.lower() in ("n", "no"):
                    continue
                self.o.create = True
            resolved = resolve_target(path, self.o, TERM)
            if resolved:
                self.target = resolved
                TERM.dim("-> %s" % resolved)
                return str(resolved)

    def prompt_args(self, step):
        if step.sid in ("direct", "l.direct"):
            return {"branch": self.a.get("branch", "the default branch")}
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
            value = self.ask(step)
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
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, list):
            if step.kind == "multichoice":
                return ", ".join(step.options[i - 1].split(" (")[0] for i in value)
            return ", ".join(str(x) for x in value)
        return str(value) if str(value) != "" else "(blank)"

    def review(self):
        """None = write, QUIT = abandon, int = the step index to revisit."""
        if not self.interactive:
            return None
        while True:
            TERM.head(t("review.title"))
            numbered = []
            section = None
            for i in self.visible_indexes():
                step = self.steps[i]
                if ((step.kind == "key" and step.sid not in ("effort", "acquisition", "devmethod"))
                        or step.sid.startswith("skill:")):
                    continue
                if step.section != section:
                    section = step.section
                    TERM.say("  %s%s%s" % (TERM.D, t(section), TERM.R))
                numbered.append(i)
                label = t(step.label, **self.prompt_args(step))
                if len(label) > 34:
                    label = label[:31] + "..."
                value = self.display(step)
                if len(value) > 40:
                    value = value[:37] + "..."
                TERM.say("   %2d  %-34s %s" % (len(numbered), label, value))
            TERM.say("  %s%s%s" % (TERM.D, "roles: " + ", ".join(self.active_roles()), TERM.R))
            TERM.say("  %s%s%s" % (TERM.D, "skills: " + (", ".join(self.chosen_skills()) or "none"), TERM.R))
            raw = TERM.read(t("review.prompt"), "write")
            if raw is None:
                TERM.say("")
                TERM.say("  " + t("review.eof"))
                return QUIT
            if raw == "":
                return None
            if raw.lower() in ("q", "quit", "n"):
                return QUIT
            if raw.isdigit() and 1 <= int(raw) <= len(numbered):
                return numbered[int(raw) - 1]
            TERM.dim(t("review.bad"))


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
              ("c_eval", "q.c_eval", "eval"), ("c_perf", "q.c_perf", "perf"))

EFFORT_KEYS = {"l": "Lean", "n": "Normal", "x": "Beast"}
ACQUISITION_KEYS = {"s": "Standard", "a": "Advanced"}
DEV_METHOD_KEYS = {"i": "Item", "e": "Epic"}


def selected_effort(w):
    raw = w.a.get("effort") or {"lean": "l", "normal": "n", "beast": "x"}.get(
        w.o.effort_mode, "n")
    return EFFORT_KEYS.get(raw, "Normal")


def selected_dev_method(w):
    raw = w.a.get("devmethod") or {"item": "i", "epic": "e"}.get(w.o.dev_method, "i")
    return DEV_METHOD_KEYS.get(raw, "Item")


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


def after_skills_ok(w, value):
    for name, _, _, _ in SKILL_RULES:
        key = "skill:" + name
        if value == "n":
            w.a[key] = False
        elif value == "y" and key in w.a:
            del w.a[key]


def show_facts(w):
    TERM.dim(t("hint.facts"))
    for fid in FACT_IDS:
        TERM.say("    %-44s %s" % (FACT_LABELS[fid], "yes" if w.fact(fid) else "no"))


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


def show_skills(w):
    TERM.dim(t("hint.skills"))
    for name, on, why in w.skills():
        TERM.say("    [%s] %-26s %s%s%s" % ("x" if on else " ", name, TERM.D,
                                            why if on else "off: " + why, TERM.R))


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
    steps = [
        Step("dest", "sec.dest", "dest", "q.dest", help="h.dest", cascade=True,
             default=lambda w: str(w.target or ""), after=after_dest, label="l.dest"),

        Step("name", "sec.project", "text", "q.name", label="l.name",
             default=lambda w: w.a.get("name") or (w.target.name if w.target else "")),
        Step("what", "sec.project", "text", "q.what", help="h.what", label="l.what"),
        Step("prefix", "sec.project", "text", "q.prefix", help="h.prefix", label="l.prefix",
             validate=validate_prefix,
             default=lambda w: (w.o.prefix or w.recovered_prefix() or w.derive_prefix())),
        Step("owner", "sec.project", "text", "q.owner", help="h.owner", label="l.owner",
             default=lambda w: w.git("config", "user.name")),
        Step("repo", "sec.project", "text", "q.repo", label="l.repo",
             default=lambda w: w.git("remote", "get-url", "origin")),

        Step("types", "sec.build", "multichoice", "q.types", help="h.types", label="l.types",
             options=list(PROJECT_TYPES), default=lambda w: w.det.types,
             after=after_types, cascade=True),
        Step("facts_ok", "sec.build", "key", "q.facts", options="ye", default="y",
             before=show_facts),
    ]
    for fid, prompt in zip(FACT_IDS, ("q.ui", "q.visual", "q.public", "q.deploy",
                                      "q.pii", "q.conv")):
        steps.append(Step(fid, "sec.build", "yesno", prompt,
                          default=(lambda f: (lambda w: w.fact(f)))(fid),
                          when=lambda w: w.a.get("facts_ok") == "e"))

    steps.append(Step("stack_ok", "sec.stack", "key", "q.stack_ok", options="yen",
                      default="y", before=show_stack, after=after_stack_ok))
    for sid, prompt, _ in STACK_FIELDS:
        steps.append(Step(sid, "sec.stack", "text", prompt,
                          default=(lambda s: (lambda w: w.a.get(s, "")))(sid),
                          when=lambda w: w.a.get("stack_ok") == "e"))

    steps.append(Step("cmds_ok", "sec.cmds", "key", "q.cmds_ok", options="yen",
                      default="y", before=show_cmds, after=after_cmds_ok))
    for sid, prompt, _ in CMD_FIELDS:
        steps.append(Step(sid, "sec.cmds", "text", prompt,
                          default=(lambda s: (lambda w: w.a.get(s, "")))(sid),
                          when=lambda w: w.a.get("cmds_ok") == "e"))

    steps += [
        Step("shape", "sec.arch", "text", "q.shape", help="h.shape", label="l.shape",
             default=default_shape, before=show_arch),
        Step("critical", "sec.arch", "text", "q.critical", help="h.critical", label="l.critical"),
        Step("expensive", "sec.arch", "text", "q.expensive", help="h.expensive", label="l.expensive"),

        Step("multilingual", "sec.lang", "yesno", "q.multilingual", cascade=True, label="l.multilingual",
             before=show_i18n,
             when=lambda w: w.fact("ui") or w.fact("public"),
             default=lambda w: len(w.det.locales) > 1 or bool(w.det.i18n_libs)),
        Step("languages", "sec.lang", "text", "q.languages", help="h.languages", label="l.languages",
             default=default_languages, when=lambda w: w.multilingual()),
        Step("catalog", "sec.lang", "text", "q.catalog", help="h.catalog", label="l.catalog",
             default=lambda w: w.det.catalog, when=lambda w: w.multilingual()),
        Step("translation", "sec.lang", "text", "q.translation", help="h.translation", label="l.translation",
             when=lambda w: w.multilingual()),
        Step("glossary", "sec.lang", "text", "q.glossary", label="l.glossary",
             when=lambda w: w.multilingual()),

        Step("branch", "sec.process", "text", "q.branch", label="l.branch",
             default=lambda w: w.git("symbolic-ref", "--short", "HEAD") or "main"),
        Step("direct", "sec.process", "yesno", "q.direct", default=False, label="l.direct"),
        Step("approvers", "sec.process", "text", "q.approvers", help="h.approvers", label="l.approvers",
             default=lambda w: w.a.get("owner", "")),
        Step("staleness", "sec.process", "text", "q.staleness", default="90 days", label="l.staleness"),
        Step("effort", "sec.process", "key", "q.effort", help="h.effort",
             options="lnx", default=lambda w: {"lean": "l", "normal": "n", "beast": "x"}[
                 w.o.effort_mode], label="l.effort"),
        Step("devmethod", "sec.process", "key", "q.devmethod", help="h.devmethod",
             options="ie", default=lambda w: {"item": "i", "epic": "e"}[w.o.dev_method],
             label="l.devmethod"),
        Step("acquisition", "sec.process", "key", "q.acquisition", help="h.acquisition",
             options="sa", default=lambda w: {"standard": "s", "advanced": "a"}[
                 w.o.acquisition_profile], label="l.acquisition", when=lambda w: w.fact("acquire")),
        Step("approval", "sec.process", "text", "q.approval", default=default_approval, label="l.approval"),
        Step("forbidden", "sec.process", "text", "q.forbidden", help="h.forbidden", label="l.forbidden"),
        Step("platform", "sec.process", "text", "q.platform", help="h.platform", label="l.platform",
             default=lambda w: ", ".join(w.det.platforms) or "none"),
        Step("deploy_targets", "sec.process", "multichoice", "q.deploy", help="h.deploy",
             label="l.deploy", options=deploy_options(), default=default_deploy,
             when=lambda w: w.fact("deploy")),

        Step("a11y", "sec.standards", "text", "q.a11y", default="WCAG 2.2 AA", label="l.a11y",
             when=lambda w: w.fact("ui")),
        Step("outcome", "sec.standards", "text", "q.outcome", help="h.outcome", label="l.outcome",
             when=lambda w: w.fact("conv")),
        Step("access_model", "sec.standards", "text", "q.access_model", help="h.access_model",
             label="l.access_model",
             default=lambda w: "None (Public)" if not (w.fact("pii") or bool(w.a.get("s_auth"))) else "Role-Based (RBAC)",
             when=lambda w: bool(w.interactive and (w.fact("pii") or bool(w.a.get("s_auth"))))),
        Step("mfa_policy", "sec.standards", "text", "q.mfa_policy", help="h.mfa_policy",
             label="l.mfa_policy",
             default=lambda w: "Not required" if not (w.fact("pii") or bool(w.a.get("s_auth"))) else "Optional / User-enabled",
             when=lambda w: bool(w.interactive and (w.fact("pii") or bool(w.a.get("s_auth"))))),

        Step("docsdir", "sec.install", "text", "q.docsdir", default=default_docsdir, label="l.docsdir",
             validate=validate_docsdir),
        Step("commands", "sec.install", "yesno", "q.commands", default=True, label="l.commands"),
        Step("skills_ok", "sec.install", "key", "q.skills", options="yen", default="y",
             before=show_skills, after=after_skills_ok),
    ]
    for name, _, _, _ in SKILL_RULES:
        if not (SRC / "optional" / "skills" / name).is_dir():
            continue
        steps.append(Step("skill:" + name, "sec.install", "yesno", name,
                          label=name,
                          default=(lambda n: (lambda w: dict((s[0], s[1]) for s in w.skills()).get(n, False)))(name),
                          when=lambda w: w.a.get("skills_ok") == "e"))
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
    for name in ("README.md", "CARD.md", "dashboard.html"):
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
    if commands_root.is_dir():
        for src in sorted((SRC / "optional" / "claude-commands").glob("*.md")):
            if (commands_root / src.name).is_file():
                planned[(Path(".claude") / "commands" / src.name).as_posix()] = substitute(
                    src.read_text(encoding="utf-8"), ctx)
    skills_root = Path(target) / ".claude" / "skills"
    if skills_root.is_dir():
        for base in sorted((SRC / "optional" / "skills").iterdir()):
            if not base.is_dir() or not (skills_root / base.name).is_dir():
                continue
            for src in sorted(base.rglob("*")):
                if src.is_file():
                    rel = Path(".claude") / "skills" / base.name / src.relative_to(base)
                    planned[rel.as_posix()] = substitute(src.read_text(encoding="utf-8"), ctx)
    hooks_root = Path(target) / ".claude" / "hooks"
    if hooks_root.is_dir() and any(p.suffix == ".sh" for p in hooks_root.iterdir()):
        # The hooks this project chose, plus the library every current hook sources.
        for src in sorted((SRC / "optional" / "hooks").iterdir()):
            if src.is_file() and ((hooks_root / src.name).is_file() or src.name == "lib.sh"):
                planned[(Path(".claude") / "hooks" / src.name).as_posix()] = substitute(
                    src.read_text(encoding="utf-8"), ctx)
    for name in RUNTIME_FILES:
        planned[".ai-sdlc/bin/" + name] = substitute(
            (SRC / "optional" / "runtime" / name).read_text(encoding="utf-8"), ctx)
    return planned


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
                (".claude", "hooks"), (".ai-sdlc", "bin"))
    return path.parts in ((str(docs), "README.md"), (str(docs), "CARD.md"),
                          (str(docs), "dashboard.html")) or any(
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
        if not chosen:
            chosen = ["claude"] if w.o.harnesses is None else w.o.harnesses
        for name in chosen:
            self.harnesses.update(HARNESS_ALIASES.get(name, ()))
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
        for name in w.chosen_skills():
            base = SRC / "optional" / "skills" / name
            candidates.extend(self.target / ".claude" / "skills" / name / path.relative_to(base)
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
                    self.install_file(path, self.target / ".claude" / "skills" / name
                                      / path.relative_to(base))
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
        for name in ("lib.sh", "README.md"):
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

    # -- the dashboard's state ------------------------------------------------
    def read_installed(self, rel):
        path = self.target / self.docs / rel
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError):
            return ""

    def dashboard_state(self):
        """Read the installed files back and describe them. Deliberately derived from the
        files rather than from the answers: the answers were true at install time, the
        files are true now, and a status page that reports the wrong one is worse than no
        status page."""
        charter = self.read_installed("project/charter.md")
        state = {
            "generated": today(),
            "project": self.ctx.get("PROJECT_NAME", ""),
            "prefix": self.ctx.get("PREFIX", ""),
            "kit_version": VERSION,
            "docs_dir": self.docs,
            "profile": self.o.profile,
            "effort_mode": "Normal",
            "acquisition_profile": "Standard",
            "dev_method": "Item",
            "wired": sorted(self.wired),
            "staleness_days": 90,
            "roles": [], "commands": [], "items": [], "artifacts": [], "budgets": [],
        }

        m = re.search(r"^\| \*\*Staleness threshold\*\* \| ([^|]*)\|", charter, re.M)
        if m:
            n = re.search(r"(\d+)", m.group(1))
            if n:
                state["staleness_days"] = int(n.group(1))

        for field, key, allowed, fallback in (
                ("Default effort mode", "effort_mode", ("Lean", "Normal", "Beast"), "Normal"),
                ("Acquisition profile", "acquisition_profile", ("Standard", "Advanced"), "Standard"),
                ("Development method", "dev_method", ("Item", "Epic"), "Item")):
            m = re.search(r"^\| \*\*%s\*\* \| ([^|]*)\|" % re.escape(field), charter, re.M)
            if m:
                cell = plain_text(m.group(1)).strip()
                matches = [value for value in allowed if value in cell]
                state[key] = matches[0] if len(matches) == 1 else fallback

        for name, tick, active_if, reason in re.findall(
                r"^\| ([a-z][a-z-]+) \| ([\u2611\u2610]) \|([^|]*)\|([^|]*)\|", charter, re.M):
            state["roles"].append({"name": name, "active": tick == "\u2611",
                                   "reason": plain_text(reason).strip()})

        for stage, command in re.findall(r"^\| `(checks\.[a-z0-9]+)` \|([^|]*)\|",
                                         charter, re.M):
            value = plain_text(command).strip()
            if value.startswith("_(") or value.endswith(")_"):
                value = ""
            state["commands"].append({"stage": stage, "command": value})

        for what, budget, method, baseline in re.findall(
                r"^\|([^|]+)\|([^|]*)\|([^|]*)\|([^|]*)\|$", charter, re.M):
            cells = [plain_text(c).strip() for c in (what, budget, method, baseline)]
            if cells[0].startswith("_(e.g.") and any(cells[1:]):
                state["budgets"].append(dict(zip(("what", "budget", "method", "baseline"),
                                                 cells)))

        prefix = self.ctx.get("PREFIX", "")
        row = re.compile(
            r"^\| (%s-\d+|[A-Za-z]\d+(?:\.\d+)*(?:-[a-z0-9]+)?|#?\d+) \|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|"
            % re.escape(prefix)) if prefix else None
        if row:
            for line in self.read_installed("project/backlog.md").splitlines():
                m = row.match(line)
                if not m:
                    continue
                cells = [plain_text(c).strip() for c in m.groups()]
                state["items"].append(dict(zip(
                    ("id", "task", "tier", "owner", "depends", "status"), cells)))

        base = self.target / self.docs / "project"
        if base.is_dir():
            for path in sorted(base.glob("*.md")):
                text = path.read_text(encoding="utf-8", errors="replace")
                if not text.startswith("---"):
                    continue
                head = text.split("---", 2)[1] if text.count("---") >= 2 else ""
                def field(key):
                    m = re.search(r"^%s:\s*(.*)$" % key, head, re.M)
                    return plain_text(m.group(1)).strip().strip('"') if m else ""
                state["artifacts"].append({
                    "file": path.name, "status": field("status"),
                    "owner": field("owner"), "last_reviewed": field("last-reviewed")})
        return state

    def write_dashboard_state(self):
        rel = "%s/%s" % (self.docs, STATE_REL)
        if self.o.dry_run:
            print("  would add      %s" % rel)
            return
        dest = ensure_inside(self.target, self.target / self.docs / STATE_REL)
        if not (self.target / self.docs / "dashboard.html").exists():
            return
        payload = json.dumps(self.dashboard_state(), indent=2, sort_keys=True)
        atomic_write_text(dest,
                          "// Generated from the installed files on %s. Regenerate with the\n"
                          "// installer or /sdlc-doctor -- a stale status page is worse than\n"
                          "// none, and dashboard.html says so when this date is old.\n"
                          "// This is a project record, not a kit file: it is not upgraded.\n"
                          "window.SDLC_STATE = %s;\n" % (today(), payload))
        print("  %s         %s" % ("write ", rel))

    def note_profile(self):
        """A reader must be able to tell a deliberate absence from a broken install."""
        if self.o.profile != "compact" or self.o.dry_run:
            return
        rel = "%s/CARD.md" % self.docs
        if rel in self.fresh:
            self.edit(rel, lambda text: text + self.COMPACT_NOTE)

    POINTER = ("Read and follow `AGENTS.md` in this directory. It is the operating "
               "contract for this repository and it takes precedence over habit.")

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
            "harnesses": sorted(self.wired),
            "platform": w.a.get("platform", "") if w.a.get("platform", "none") != "none" else "",
            "deploy_platforms": installed_platforms(self.target, self.docs, self.platforms),
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
                     "      - uses: actions/checkout@v4"]
            for key, command in ordered:
                lines.extend(("      - name: %s" % key.replace("_", " ").title(),
                              "        run: %s" % json.dumps(command)))
            lines.extend(("", "# Manual-only by default. Confirm commands, runtime, and service versions",
                          "# from the charter before adding push or pull_request triggers.", ""))
            return "\n".join(lines)
        lines = ["stages:", "  - quality", "", "quality:", "  stage: quality",
                 "  when: manual", "  script:"]
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
                       if rel.startswith((".claude/commands/", ".claude/hooks/"))
                       and (target / rel).is_file()
                       and rel not in previous_files and not o.adopt)
    for rel in unadopted:
        del planned[rel]

    modified = []
    if previous:
        for rel, old_hash in previous_files.items():
            if sha256_file(target / rel) != old_hash:
                modified.append(rel)

    # Files the kit owns only part of: AGENTS.md sections 1-8, and rows the charter lacks.
    extra, notes, regions = {}, [], {}
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
    print("  (%s portable docs and already-installed skills -- project records untouched)"
          % docs)
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
    print("Done: %d updated, %d obsolete managed files removed." %
          (inst.updated, len(obsolete)))
    print("")
    for note in notes:
        print("note: %s" % note)
        print("")
    print("New skills shipped by this version are not added by --upgrade. To see them:")
    print("  ls %s" % (SRC / "optional" / "skills"))
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
    elif w.det.deploy and not w.interactive:
        print("note: deployment detected for %s. Detection is not a decision, so no"
              % ", ".join(w.det.deploy))
        print("      platform checklist was installed. Confirm it with --deploy %s"
              % ",".join(w.det.deploy))
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
    print("  2. Fill in the Project overrides section at the end of AGENTS.md.")
    print("  3. Check nothing was left unsubstituted:")
    print("       grep -rn '{{' %s/%s %s/AGENTS.md %s/.claude"
          % (w.target, docs, w.target, w.target))
    if ("%s/project/architecture.md" % docs) in tailored:
        print("  4. Confirm every _(detected at install)_ row in %s/project/architecture.md."
              % docs)

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
    print("")
    print("Later, to pick up a newer version of the portable standards:")
    print("  install.sh %s %s --upgrade" % (w.target, inst.ctx.get("PREFIX", "<PREFIX>")))


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

    if o.upgrade:
        return upgrade(target, o)

    w = Wizard(o)
    w.target = target
    if target is not None:
        after_dest(w, str(target))

    if w.interactive:
        print("")
        print("%s%s%s" % (TERM.B, t("intro.title", version=VERSION), TERM.R))
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
    try:
        skills = inst.run()
        tailored = inst.tailor()
        inst.scaffold()
        inst.install_hooks()
        inst.record_manifest()
        inst.write_dashboard_state()
        inst.write_profile()
    except (IOError, OSError, RuntimeError) as exc:
        sys.stderr.write("error: installation failed: %s\n" % exc)
        return 1
    report(w, inst, skills, tailored)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("")
        print("  interrupted -- review-stage quits write nothing; if copying had started,"
              " the installation may be partial and is safe to re-run.")
        sys.exit(130)

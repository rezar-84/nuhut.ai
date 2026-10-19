#!/usr/bin/env python3
"""The mechanical half of /sdlc-doctor and /sdlc-verify.

Everything this script decides, it decides from files and commands: no model reads a
table and reports what it remembers. The judgment half -- severity, which artifacts a
role needs, behavioural checks, what to fix first -- stays with the agent, in the
markdown commands that call this.

    python3 .ai-sdlc/bin/sdlc.py doctor [--json] [--strict]
    python3 .ai-sdlc/bin/sdlc.py verify [--stage unit,lint] [--timeout 1800]
    python3 .ai-sdlc/bin/sdlc.py plan-check ACME-12 [--base main] [--json] [--strict]
    python3 .ai-sdlc/bin/sdlc.py view [--no-open] [--json] [--serve [--port 8765]]
    python3 .ai-sdlc/bin/sdlc.py metrics [--json]
    python3 .ai-sdlc/bin/sdlc.py log --since main [--write]
    python3 .ai-sdlc/bin/sdlc.py trailers ACME-12 [--agent X --model Y]
    python3 .ai-sdlc/bin/sdlc.py review ACME-12 --role security --by codex|gemini|claude|cmd:<command>
    python3 .ai-sdlc/bin/sdlc.py bite [--base REF] <test command> | --restore

Standard library only. Installed and upgraded by the kit, so a local edit blocks
`--upgrade` rather than being lost; change the kit instead.

This file must never contain two opening braces in a row: the installer substitutes
that pattern in every file it installs. Regexes spell it '[{][{]'.
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

# The order /sdlc-verify runs stages in (04-quality-gates.md), not the installer's
# question order.
STAGES = ("format", "lint", "typecheck", "complexity", "infra", "unit", "mutation",
          "integration", "data", "contract", "eval", "build", "scan", "a11y", "e2e", "perf")
POINTER_FILES = ("CLAUDE.md", "GEMINI.md", "AGENT.md", "CONVENTIONS.md",
                 ".github/copilot-instructions.md", ".cursorrules",
                 ".windsurfrules", ".clinerules", ".roo/rules/agents.md")
EFFORT = ("Lean", "Normal", "Beast")
ACQUISITION = ("Standard", "Advanced")
DEV_METHOD = ("Item", "Epic")
DECISION_STYLE = ("Ask", "Guide", "Autopilot")
TIER_RULES = ("Standard", "Strict")
WORKLOG_ROTATE_LINES = 1000
DEFAULT_STALENESS_DAYS = 90
KNOWN_MISTAKES_LINES = 30
# High-confidence credential shapes, the same set the secret-guard hook denies at commit.
SECRET_PATTERNS = (
    ("private key", r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----[\s\S]*?-----END ([A-Z]+ )?PRIVATE KEY-----"),
    ("AWS access key", r"(AKIA|ASIA)[0-9A-Z]{16}"),
    ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}"),
    ("GitLab token", r"glpat-[A-Za-z0-9_-]{20,}"),
    ("Slack token", r"xox[abposr]-[A-Za-z0-9-]{10,}"),
    ("Stripe live key", r"(sk|rk)_live_[A-Za-z0-9]{20,}"),
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9_-]{20,}"),
    ("OpenAI API key", r"sk-(proj-)?[A-Za-z0-9_-]{40,}"),
    ("Google API key", r"AIza[0-9A-Za-z_-]{35}"),
)
# A URL that embeds a password, with placeholder passwords and example hosts excluded.
URL_PASSWORD = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://([^/\s:@]+):([^/\s@<>{}$]{4,})@([^/\s]*)")
URL_PASSWORD_PLACEHOLDER = re.compile(
    r"^(password|passwd|pass|secret|changeme|x{4,}|\*+)$", re.IGNORECASE)
EXAMPLE_HOST = re.compile(r"(^|\.)(example\.(com|org|net)|invalid)$", re.IGNORECASE)
# Personal-data shapes: lower confidence than credentials, so `doctor` warns.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
CARD_SHAPE = re.compile(r"(?<![0-9])[0-9]{4}(?:[ -][0-9]{4}){3}(?![0-9])")
NATIONAL_ID_SHAPE = re.compile(r"(?<![0-9])[0-9]{3}-[0-9]{2}-[0-9]{4}(?![0-9])")
PLACEHOLDER = re.compile(r"[{][{][A-Z][A-Z0-9_]*[}][}]")
UNFILLED = re.compile(r"_\([^)]*\)_")


# ---------------------------------------------------------------- reading

def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (IOError, OSError, UnicodeDecodeError):
        return ""


def split_row(line):
    """Cells of a markdown table row, honouring escaped pipes."""
    body = line.strip()
    if not (body.startswith("|") and body.endswith("|")):
        return None
    cells = re.split(r"(?<!\\)\|", body[1:-1])
    return [cell.strip().replace("\\|", "|") for cell in cells]


def unfilled(cell):
    """True when a cell holds nothing a human wrote: empty, or only the template's
    italic `_(...)_` hint."""
    return not UNFILLED.sub("", cell).strip()


def labelled(text, label):
    """The value cell of a `| **Label** | value |` row, or None when there is no row."""
    for line in text.splitlines():
        cells = split_row(line)
        if cells and len(cells) >= 2 and cells[0] == "**%s**" % label:
            return cells[1]
    return None


def charter_commands(text):
    """{stage: command} for every `checks.*` row. '' means blank; 'absent' means a
    human wrote that the stage does not exist here."""
    commands = {}
    for line in text.splitlines():
        cells = split_row(line)
        if not cells or len(cells) < 2:
            continue
        match = re.match(r"^`checks\.([a-z0-9]+)`$", cells[0])
        if not match:
            continue
        cell = UNFILLED.sub("", cells[1]).strip()
        spans = re.findall(r"`([^`]+)`", cell)
        if len(spans) == 1 and cell == "`%s`" % spans[0]:
            cell = spans[0]
        else:
            cell = cell.replace("`", "")
        commands[match.group(1)] = "absent" if cell.lower() == "absent" else cell
    return commands


def choice(cell, options):
    """(value, state): state is 'decided', 'undecided' (every option still listed, so
    the documented default applies), 'blank', or 'invalid'."""
    if cell is None:
        return None, "blank"
    found = [option for option in options
             if re.search(r"\b%s\b" % option, UNFILLED.sub("", cell))]
    if len(found) == 1:
        return found[0], "decided"
    if len(found) == len(options):
        return None, "undecided"
    return None, "blank" if unfilled(cell) else "invalid"


def roles(text):
    """[(name, active, reason)] from the Active roles table."""
    found = []
    for line in text.splitlines():
        cells = split_row(line)
        if cells and len(cells) >= 4 and re.match(r"^[a-z][a-z-]+$", cells[0]) \
                and cells[1] in ("☑", "☐"):
            found.append((cells[0], cells[1] == "☑", cells[3]))
    return found


LEGACY_HIERARCHICAL = re.compile(
    r"^[A-Za-z][0-9]+(?:\.[0-9]+)*(?:-[a-z0-9]+)?(?:[–-][A-Za-z]?[0-9]+(?:\.[0-9]+)*)?$"
)
LEGACY_NUMERIC = re.compile(r"^(?:#?[0-9]+|GH-[0-9]+)$")


def is_valid_work_item_id(raw_id, prefix, legacy_prefixes=None):
    if not raw_id or raw_id.startswith("_(") or ("{" + "{") in raw_id:
        return False
    if prefix and re.fullmatch(r"%s-[0-9]+" % re.escape(prefix), raw_id):
        return True
    if legacy_prefixes and any(re.fullmatch(r"%s-[0-9]+" % re.escape(p), raw_id) for p in legacy_prefixes):
        return True
    if LEGACY_HIERARCHICAL.fullmatch(raw_id) or LEGACY_NUMERIC.fullmatch(raw_id):
        return True
    return False


def backlog_rows(text, prefix, legacy_prefixes=None):
    """[(id, status, cells)] for every table row whose first cell is a work item ID."""
    rows = []
    for line in text.splitlines():
        cells = split_row(line)
        if cells and len(cells) >= 6 and is_valid_work_item_id(cells[0], prefix, legacy_prefixes):
            rows.append((cells[0], cells[5].strip("`* "), cells))
    return rows


def ids_in(text, prefix, extra_ids=None):
    patterns = []
    if prefix:
        patterns.append(r"\b%s-[0-9]+\b" % re.escape(prefix))
    if extra_ids:
        patterns.append(r"\b(?:" + "|".join(re.escape(i) for i in sorted(extra_ids, key=len, reverse=True)) + r")\b")
    if not patterns:
        return set()
    found = set(re.findall(r"|".join(patterns), text))
    if extra_ids:
        for m in re.finditer(r"\b([A-Za-z]+)([0-9]+)(?:\.([0-9]+))?\s*[-–—]\s*(?:([A-Za-z]+))?([0-9]+)(?:\.([0-9]+))?\b", text):
            p1, n1, sub1, p2, n2, sub2 = m.groups()
            if sub1 is not None:
                p_letter, major, start_s = p1, int(n1), int(sub1)
                end_s = int(sub2) if sub2 is not None else (int(n2) if p2 is None else None)
                if end_s is not None and start_s <= end_s <= start_s + 100:
                    for s in range(start_s, end_s + 1):
                        cand = "%s%d.%d" % (p_letter, major, s)
                        if cand in extra_ids:
                            found.add(cand)
            elif sub1 is None and sub2 is None and n1 and n2:
                p_letter, start_n, end_n = p1, int(n1), int(n2)
                if start_n <= end_n <= start_n + 100:
                    for n in range(start_n, end_n + 1):
                        cand = "%s%d" % (p_letter, n)
                        if cand in extra_ids:
                            found.add(cand)
    return found


def id_sort_key(i):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"([0-9]+)", i)]


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def age_days(value, today):
    """Days since a YYYY-MM-DD date, or None if it is not one."""
    try:
        return (today - datetime.datetime.strptime(value, "%Y-%m-%d").date()).days
    except ValueError:
        return None


# ---------------------------------------------------------------- project

class Project(object):
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.profile = self.json(".ai-sdlc/profile.json")
        self.manifest = self.json(".ai-sdlc/manifest.json")
        self.docs = self.profile.get("docs_dir") or self.manifest.get("docs_dir") or "docs"
        self.charter_path = os.path.join(self.docs, "project", "charter.md")
        self.charter = read(self.path(self.charter_path))
        prefix_cell = labelled(self.charter, "Work item prefix") or ""
        found = re.search(r"`([A-Z]{2,4})`", UNFILLED.sub("", prefix_cell))
        self.charter_prefix = found.group(1) if found else ""
        self.prefix = self.charter_prefix or self.profile.get("prefix") or ""
        self.legacy_prefixes = set(self.profile.get("legacy_prefixes") or [])
        legacy_cell = labelled(self.charter, "Legacy issue prefix") or \
                      labelled(self.charter, "Legacy prefixes") or ""
        self.legacy_prefixes.update(re.findall(r"`([^`]+)`", legacy_cell))
        m_leg = re.search(r"legacy(?: prefixes?)?:\s*([^\n|]+)", prefix_cell, re.I)
        if m_leg:
            self.legacy_prefixes.update(re.findall(r"`([^`]+)`", m_leg.group(1)))

    def path(self, rel):
        return os.path.join(self.root, rel)

    def json(self, rel):
        try:
            data = json.loads(read(self.path(rel)) or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def records(self, name):
        return read(self.path(os.path.join(self.docs, "project", name)))

    def worklog_texts(self):
        texts = [self.records("worklog.md")]
        archive = self.path(os.path.join(self.docs, "project", "worklog-archive"))
        if os.path.isdir(archive):
            for name in sorted(os.listdir(archive)):
                if name.endswith(".md"):
                    texts.append(read(os.path.join(archive, name)))
        return "\n".join(texts)

    def git(self, *args):
        try:
            proc = subprocess.run(("git",) + args, cwd=self.root, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, universal_newlines=True)
        except OSError:
            return ""
        return proc.stdout if proc.returncode == 0 else ""


# ---------------------------------------------------------------- doctor

class Findings(object):
    def __init__(self):
        self.items = []

    def add(self, level, check, where, message):
        self.items.append({"level": level, "check": check, "where": where,
                           "message": message})


def check_placeholders(project, out):
    # Only what the kit installs: .claude/ also holds worktrees and caches that can be
    # gigabytes of somebody else's files.
    for base in (project.docs, "AGENTS.md", ".claude/commands", ".claude/skills",
                 ".claude/hooks", ".claude/settings.json"):
        top = project.path(base)
        paths = [top] if os.path.isfile(top) else []
        for folder, dirs, names in os.walk(top):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "worktrees")]
            paths.extend(os.path.join(folder, name) for name in sorted(names))
        for path in paths:
            # The worklog is narrative and quotes placeholders when it describes kit work.
            if os.path.basename(path) == "worklog.md" or "worklog-archive" in path:
                continue
            if not path.endswith((".md", ".sh", ".json", ".js", ".html", ".mdc", ".txt")):
                continue
            for number, line in enumerate(read(path).splitlines(), 1):
                for token in PLACEHOLDER.findall(line):
                    out.add("fail", "substitution",
                            "%s:%d" % (os.path.relpath(path, project.root), number),
                            "unsubstituted %s: the install is broken here" % token)


def check_pointer(project, out):
    candidates = list(POINTER_FILES)
    rules = project.path(".cursor/rules")
    if os.path.isdir(rules):
        candidates += [os.path.join(".cursor/rules", name) for name in sorted(os.listdir(rules))
                       if name.endswith(".mdc")]
    pointing = [rel for rel in candidates if "AGENTS.md" in read(project.path(rel))]
    if not pointing:
        out.add("fail", "contract", "(repository)",
                "no instruction file names AGENTS.md, so no agent is told to follow the "
                "process. Codex, Jules, Zed, Factory and opencode read it directly; every "
                "other tool needs a pointer.")
    for rel in project.profile.get("harnesses") or []:
        if isinstance(rel, str) and rel not in pointing and os.path.isfile(project.path(rel)):
            out.add("fail", "contract", rel,
                    "was wired to AGENTS.md at install and no longer mentions it")


def check_charter(project, out):
    text, where = project.charter, project.charter_path
    if not text:
        out.add("fail", "charter", where, "the charter is missing")
        return
    blank = [stage for stage in STAGES if charter_commands(text).get(stage) == ""]
    if blank:
        out.add("warn", "charter", "%s Commands" % where,
                "blank, so Unknown rather than absent: %s. Write each command, or 'absent' "
                "where the stage does not exist here." % ", ".join("checks." + s for s in blank))
    for label in ("Approvers", "Default branch", "Staleness threshold"):
        cell = labelled(text, label)
        if cell is None or unfilled(cell):
            out.add("warn", "charter", "%s %s" % (where, label), "blank")
    if labelled(text, "Operating mode") is not None:
        out.add("fail", "charter", "%s Operating mode" % where,
                "legacy row: whether it meant effort or acquisition needs a human decision")
    for label, options in (("Default effort mode", EFFORT),
                           ("Acquisition profile", ACQUISITION)):
        cell = labelled(text, label)
        if cell is None:
            out.add("warn", "charter", "%s %s" % (where, label),
                    "row missing: the charter predates it. The installer's --upgrade "
                    "reinserts it; the default applies until then.")
            continue
        _, state = choice(cell, options)
        if state == "undecided":
            out.add("warn", "charter", "%s %s" % (where, label),
                    "undecided: the documented default applies until a human picks one")
        elif state in ("invalid", "blank"):
            out.add("fail", "charter", "%s %s" % (where, label),
                    "must be exactly one of %s" % ", ".join(options))
    # Added in 3.5. An older charter without the row simply works item by item, so its
    # absence is not worth a warning; a row that is there must still be readable.
    cell = labelled(text, "Development method")
    if cell is not None and choice(cell, DEV_METHOD)[1] in ("invalid", "blank"):
        out.add("fail", "charter", "%s Development method" % where,
                "must be exactly one of %s" % ", ".join(DEV_METHOD))
    # Added in 3.5 with decision style; same tolerance as the development method.
    cell = labelled(text, "Decision style")
    if cell is not None and choice(cell, DECISION_STYLE)[1] in ("invalid", "blank"):
        out.add("fail", "charter", "%s Decision style" % where,
                "must be exactly one of %s" % ", ".join(DECISION_STYLE))
    # Added in 4.0. Missing, blank or undecided means Standard on a new install; an
    # upgrade from 3.x fills it with Strict. Only a value that is neither is wrong.
    cell = labelled(text, "Tier rules")
    if cell is not None and choice(cell, TIER_RULES)[1] == "invalid":
        out.add("fail", "charter", "%s Tier rules" % where,
                "must be exactly one of %s" % ", ".join(TIER_RULES))
    active = dict((name, on) for name, on, _ in roles(text))
    undecided = [name for name, on, reason in roles(text) if not on and unfilled(reason)]
    if undecided:
        out.add("warn", "roles", "%s Active roles" % where,
                "unticked with no reason, so nobody decided whether they apply: %s"
                % ", ".join(undecided))
    if active.get("ml-engineer"):
        cell = labelled(text, "Providers and pinned versions")
        if cell is not None and unfilled(cell):
            out.add("warn", "charter", "%s Model & data" % where,
                    "ml-engineer is active and no pinned model versions are recorded")
    if active.get("performance-engineer") and not re.search(
            r"^\| (?!_\(e\.g\.)(?!What \|)[^|\s][^|]*\| *[^|\s]", text.split("## Budgets", 1)[-1]
            .split("\n## ", 1)[0], re.M):
        out.add("warn", "charter", "%s Budgets" % where,
                "performance-engineer is active and no budget is recorded")


def check_stack_versions(project, out, today):
    """ADR "Version facts" (process/13-stack-evaluation.md): a version fact is only as
    good as the day it was read, so warn when the verified-on date is missing or older
    than the staleness threshold, and when a recorded support-end date has passed."""
    cell = labelled(project.charter, "Staleness threshold") or ""
    found = re.search(r"[0-9]+", UNFILLED.sub("", cell))
    window = int(found.group(0)) if found else DEFAULT_STALENESS_DAYS
    folder = project.path(os.path.join(project.docs, "project", "adr"))
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name.lower() == "readme.md":
            continue
        text = read(os.path.join(folder, name))
        if "## Version facts" not in text:
            continue
        block = text.split("## Version facts", 1)[1].split("\n## ", 1)[0]
        rel = os.path.join(project.docs, "project", "adr", name)

        def field(label):
            m = re.search(r"\*\*%s:\*\*[ \t]*([^\n]*)" % re.escape(label), block)
            return m.group(1).strip() if m else ""
        verified = age_days(field("Verified on"), today)
        if verified is None:
            out.add("warn", "stack", rel, "Version facts has no verified-on date: the "
                    "versions were recalled, or nobody wrote down when they were read")
        elif verified > window:
            out.add("warn", "stack", rel, "version facts verified %d days ago; the "
                    "window is %d" % (verified, window))
        ends = age_days(field("Support ends"), today)
        if ends is not None and ends > 0:
            out.add("warn", "stack", rel, "the chosen version's support ended %d days ago"
                    % ends)


def check_staleness(project, out, today):
    cell = labelled(project.charter, "Staleness threshold") or ""
    found = re.search(r"[0-9]+", UNFILLED.sub("", cell))
    window = int(found.group(0)) if found else DEFAULT_STALENESS_DAYS
    folder = project.path(os.path.join(project.docs, "project"))
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        rel = os.path.join(project.docs, "project", name)
        value = frontmatter(read(os.path.join(folder, name))).get("last-reviewed")
        if value is None:
            continue
        days = age_days(value, today)
        if days is None:
            out.add("warn", "staleness", rel,
                    "last-reviewed is %r: never reviewed, or not a YYYY-MM-DD date" % value)
        elif days > window:
            out.add("warn", "staleness", rel,
                    "last reviewed %d days ago; the window is %d" % (days, window))


def tier_rules(project):
    """'Strict' or 'Standard' (the default) from the charter's Tier rules row."""
    picked, state = choice(labelled(project.charter, "Tier rules") or "", TIER_RULES)
    return picked if state == "decided" else "Standard"


def check_traceability(project, out):
    prefix = project.prefix
    legacy_prefixes = getattr(project, "legacy_prefixes", None)
    if not prefix and not legacy_prefixes:
        out.add("warn", "traceability", project.charter_path,
                "no work item prefix, so IDs cannot be checked")
        return
    backlog = project.records("backlog.md")
    worklog = project.worklog_texts()
    rows = backlog_rows(backlog, prefix, legacy_prefixes)
    known = set(row[0] for row in rows)
    logged = ids_in(worklog, prefix, known)
    backlog_where = os.path.join(project.docs, "project", "backlog.md")
    for item, status, cells in rows:
        if status == "Done" and item not in logged:
            is_legacy = not (prefix and re.fullmatch(r"%s-[0-9]+" % re.escape(prefix), item))
            if is_legacy:
                out.add("warn", "traceability", "%s %s" % (backlog_where, item),
                        "legacy item Done with no worklog entry naming it")
            else:
                out.add("fail", "traceability", "%s %s" % (backlog_where, item),
                        "Done with no worklog entry naming it")
        if status == "Parked" and (len(cells) < 7 or unfilled(cells[6])):
            out.add("warn", "traceability", "%s %s" % (backlog_where, item),
                    "Parked with no one named in 'Waiting on whom'")
    for item in sorted(logged - known, key=id_sort_key):
        out.add("warn", "traceability", "%s/project/worklog.md %s" % (project.docs, item),
                "in the worklog but not in the backlog")
    # Under Standard tier rules a Tier 3 change's commit message is its whole record, so
    # an ID seen only in a commit is expected. A branch means work worth a record.
    mentioned = ids_in(project.git("branch", "--format=%(refname:short)"), prefix, known)
    if tier_rules(project) == "Strict":
        mentioned |= ids_in(project.git("log", "-50", "--format=%B"), prefix, known)
    for item in sorted(mentioned - known - logged, key=id_sort_key):
        out.add("warn", "traceability", "git",
                "%s is in a recent commit or branch and in neither the backlog nor the "
                "worklog" % item)


def backlog_history(project):
    """What git remembers about each work item: the date a line naming it was last added
    to the backlog, the worklog or a commit subject, and the date each (item, status) row
    was last written to the backlog. Uncommitted edits are not history yet, so a row
    that has never been committed has no dates here."""
    prefix = project.prefix
    legacy = getattr(project, "legacy_prefixes", None)
    docs = os.path.join(project.docs, "project")
    touched, since = {}, {}

    def touch(item, date):
        if item not in touched:
            touched[item] = date

    # git log is newest first, so the first sighting is the latest one.
    date = None
    for line in project.git("log", "-p", "--no-color", "--format=%x01%cs", "--",
                            os.path.join(docs, "backlog.md"),
                            os.path.join(docs, "worklog.md")).splitlines():
        if line.startswith("\x01"):
            date = line[1:]
        elif date and line.startswith("+") and not line.startswith("+++"):
            cells = split_row(line[1:])
            if cells and len(cells) >= 6 and is_valid_work_item_id(cells[0], prefix, legacy):
                since.setdefault((cells[0], cells[5].strip("`* ")), date)
            for item in ids_in(line, prefix):
                touch(item, date)
    for line in project.git("log", "-2000", "--format=%cs%x01%s").splitlines():
        date, _, subject = line.partition("\x01")
        for item in ids_in(subject, prefix):
            touch(item, date)
    return touched, since


def check_backlog_age(project, out, today):
    """A backlog that is never pruned stops being read. In progress or In review with no
    trace of activity for longer than the staleness window is a zombie claim, usually a
    session that died. Blocked, Parked and Ready rows older than the window need a
    decision, not another day in the queue. The window is the charter's staleness
    threshold, the same one the records use."""
    if not project.prefix:
        return
    cell = labelled(project.charter, "Staleness threshold") or ""
    found = re.search(r"[0-9]+", UNFILLED.sub("", cell))
    window = int(found.group(0)) if found else DEFAULT_STALENESS_DAYS
    rows = backlog_rows(project.records("backlog.md"), project.prefix,
                        getattr(project, "legacy_prefixes", None))
    if not rows:
        return
    touched, since = backlog_history(project)
    where = os.path.join(project.docs, "project", "backlog.md")
    for item, status, cells in rows:
        if status in ("In progress", "In review"):
            days = age_days(touched.get(item, ""), today)
            if days is not None and days > window:
                out.add("warn", "backlog", "%s %s" % (where, item),
                        "%s, but nothing has named it for %d days (backlog, worklog or "
                        "commit subject); the window is %d. Finish it, park it with a "
                        "named human, or return it to Ready" % (status, days, window))
            continue
        if status in ("Blocked", "Parked", "Ready"):
            column = {"Blocked": 7, "Parked": 8}.get(status)
            recorded = cells[column] if column and len(cells) > column else ""
            days = age_days(UNFILLED.sub("", recorded).strip(), today)
            if days is None:
                days = age_days(since.get((item, status), ""), today)
            if days is not None and days > window:
                advice = {
                    "Blocked": "name who can unblock it and ask, or defer or drop it",
                    "Parked": "the decision has waited longer than the window; "
                              "chase the named human or drop the item",
                    "Ready": "still the next priority? If not, defer it with a "
                             "condition or drop it with a reason",
                }[status]
                out.add("warn", "backlog", "%s %s" % (where, item),
                        "%s for %d days; the window is %d: %s" % (status, days, window, advice))


def check_known_mistakes(project, out):
    """The lessons list in AGENTS.md section 9 must stay short enough to be read."""
    text = read(project.path("AGENTS.md"))
    at = text.find("**Known agent mistakes:**")
    if at < 0:
        return
    lines = [l for l in text[at:].splitlines()[1:] if l.strip()]
    stop = next((n for n, l in enumerate(lines) if l.startswith(("**", "#", "---"))), len(lines))
    if stop > KNOWN_MISTAKES_LINES:
        out.add("warn", "lessons", "AGENTS.md",
                "%d lines of known agent mistakes; past %d, turn the recurring ones into "
                "checks or hooks" % (stop, KNOWN_MISTAKES_LINES))


def check_rollback(project, out, today):
    """A rollback nobody has run is a theory. Runbooks record when it last ran."""
    cell = labelled(project.charter, "Staleness threshold") or ""
    found = re.search(r"[0-9]+", UNFILLED.sub("", cell))
    window = int(found.group(0)) if found else DEFAULT_STALENESS_DAYS
    folder = project.path(os.path.join(project.docs, "project"))
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        text = read(os.path.join(folder, name)) if name.endswith(".md") else ""
        match = re.search(r"\*\*Last executed:\*\*(.*)", text)
        if not match:
            continue
        rel = os.path.join(project.docs, "project", name)
        date = re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", UNFILLED.sub("", match.group(1)))
        days = age_days(date.group(0), today) if date else None
        if days is None:
            out.add("warn", "rollback", rel, "rollback has no Last executed date: it has "
                    "never been rehearsed, or nobody wrote down when")
        elif days > window:
            out.add("warn", "rollback", rel, "rollback last rehearsed %d days ago; the "
                    "window is %d" % (days, window))


def redact(text):
    """Mask credential shapes in captured output. Returns (text, count)."""
    count = 0
    for kind, pattern in SECRET_PATTERNS:
        text, n = re.subn(pattern, "[redacted: %s]" % kind, text)
        count += n
    return text, count


def sensitive_kinds(line):
    """(credential kinds, personal-data kinds) in one line. Kinds only, never values.
    A line containing EXAMPLE is a deliberate fixture."""
    if "EXAMPLE" in line:
        return [], []
    secrets = [kind for kind, pattern in SECRET_PATTERNS if re.search(pattern, line)]
    for _user, password, host in URL_PASSWORD.findall(line):
        if not URL_PASSWORD_PLACEHOLDER.match(password) and not EXAMPLE_HOST.search(host):
            secrets.append("URL with embedded password")
            break
    personal = []
    for match in EMAIL.finditer(line):
        local, domain = match.group(0).split("@", 1)[0], match.group(1)
        if (EXAMPLE_HOST.search(domain) or domain.lower() == "users.noreply.github.com"
                or local.lower() in ("noreply", "no-reply")):
            continue
        personal.append("email address")
        break
    if CARD_SHAPE.search(line):
        personal.append("card-number shape")
    if NATIONAL_ID_SHAPE.search(line):
        personal.append("national-ID shape")
    return secrets, personal


def check_sensitive(project, out):
    """Credentials and personal data already written into the project's records. The
    records are committed, so a value here is a leak whether or not anything has pushed
    it yet (process/12-sensitive-data-in-records.md). Reports kind and place, never the
    value: a finding that quoted it would be a second copy."""
    top = project.path(os.path.join(project.docs, "project"))
    for folder, dirs, names in os.walk(top):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for name in sorted(names):
            if not name.endswith((".md", ".txt", ".json", ".csv")):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, project.root)
            for number, line in enumerate(read(path).splitlines(), 1):
                secrets, personal = sensitive_kinds(line)
                if secrets:
                    out.add("fail", "sensitive", "%s:%d" % (rel, number),
                            "looks like a credential (%s). Deleting the line does not undo "
                            "it: rotate it, then remove it" % ", ".join(secrets))
                if personal:
                    out.add("warn", "sensitive", "%s:%d" % (rel, number),
                            "looks like personal data (%s). Records hold the decision and "
                            "the reason, not a person's details" % ", ".join(personal))


def check_worklog_size(project, out):
    lines = len(project.records("worklog.md").splitlines())
    if lines > WORKLOG_ROTATE_LINES:
        out.add("warn", "worklog", "%s/project/worklog.md" % project.docs,
                "%d lines; rotate closed entries into worklog-archive/ past %d"
                % (lines, WORKLOG_ROTATE_LINES))


def check_profile(project, out):
    profile = project.profile
    if not profile:
        return
    where = ".ai-sdlc/profile.json"
    charter = charter_commands(project.charter)
    recorded = profile.get("commands") or {}
    differ = [stage for stage in STAGES
              if recorded.get(stage, "") != ("" if charter.get(stage, "") == "absent"
                                             else charter.get(stage, ""))]
    if differ:
        # Warn, not fail: verify always runs the charter's commands, so this misleads
        # only tools that read the profile.
        out.add("warn", "profile", where + " commands",
                "disagrees with the charter for %s. The charter wins; correct the profile."
                % ", ".join(differ))
    if project.charter_prefix and profile.get("prefix") not in (None, "", project.charter_prefix):
        out.add("fail", "profile", where + " prefix",
                "profile says %r, charter says %r" % (profile.get("prefix"),
                                                       project.charter_prefix))
    for key, label, options in (("effort_mode", "Default effort mode", EFFORT),
                                ("acquisition_profile", "Acquisition profile", ACQUISITION),
                                ("dev_method", "Development method", DEV_METHOD),
                                ("decision_style", "Decision style", DECISION_STYLE)):
        value, state = choice(labelled(project.charter, label), options)
        if key in ("dev_method", "decision_style") and key not in profile:
            continue  # a profile written before 3.5; --upgrade adds it
        if state == "decided" and str(profile.get(key, "")).lower() != value.lower():
            out.add("fail", "profile", "%s %s" % (where, key),
                    "profile says %r, charter says %r" % (profile.get(key), value))
    ticked = sorted(name for name, on, _ in roles(project.charter) if on)
    if ticked and "roles" in profile and sorted(profile.get("roles") or []) != ticked:
        out.add("fail", "profile", where + " roles",
                "profile lists %s; charter ticks %s" % (", ".join(sorted(profile["roles"])),
                                                        ", ".join(ticked)))
    have, want = profile.get("kit_version"), project.manifest.get("kit_version")
    if have and want and version_tuple(have) < version_tuple(want):
        out.add("fail", "profile", where + " kit_version",
                "profile is %s, manifest is %s: an incomplete upgrade" % (have, want))


def version_tuple(value):
    return tuple(int(part) for part in re.findall(r"[0-9]+", str(value))[:3])


def check_epics(project, out):
    """Epic rows need their epic file, and an item's '(in ID)' must name a real epic. A
    backlog with no epics, which is every project working item by item, is untouched."""
    prefix = project.prefix
    legacy_prefixes = getattr(project, "legacy_prefixes", None)
    if not prefix and not legacy_prefixes:
        return
    rows = backlog_rows(project.records("backlog.md"), prefix, legacy_prefixes)
    epics = set(item for item, _, cells in rows if cells[1].strip("`* ").startswith("Epic:"))
    backlog_where = os.path.join(project.docs, "project", "backlog.md")
    for item in sorted(epics, key=id_sort_key):
        rel = os.path.join(project.docs, "project", "epics", "%s.md" % item)
        if not os.path.isfile(project.path(rel)):
            out.add("warn", "epics", "%s %s" % (backlog_where, item),
                    "an epic with no %s: its plan and checkpoints have nowhere to live" % rel)
    for item, _, cells in rows:
        for parent in re.findall(r"\(in ([^)\s]+)\)", cells[1]):
            if parent not in epics:
                out.add("warn", "epics", "%s %s" % (backlog_where, item),
                        "says it is in %s, which is not an epic row in the backlog" % parent)


def check_dependencies(project, out):
    """Backlog item dependencies must exist, not be circular, and items must not depend on themselves."""
    prefix = project.prefix
    legacy_prefixes = getattr(project, "legacy_prefixes", None)
    if not prefix and not legacy_prefixes:
        return
    rows = backlog_rows(project.records("backlog.md"), prefix, legacy_prefixes)
    known = set(row[0] for row in rows)
    backlog_where = os.path.join(project.docs, "project", "backlog.md")

    deps_map = {}
    for item, status, cells in rows:
        if len(cells) > 4:
            raw_deps = cells[4]
            dep_ids = set(ids_in(raw_deps, prefix, known))
            for token in re.findall(r"`([^`]+)`", UNFILLED.sub("", raw_deps)):
                token = token.strip()
                if token and token not in ("-", "—", "none", "n/a"):
                    dep_ids.add(token)
            deps_map[item] = []
            for dep in sorted(dep_ids, key=id_sort_key):
                if dep == item:
                    out.add("fail", "dependencies", "%s %s" % (backlog_where, item),
                            "item cannot depend on itself")
                elif dep not in known:
                    out.add("warn", "dependencies", "%s %s" % (backlog_where, item),
                            "depends on %s, which is not in the backlog" % dep)
                else:
                    deps_map[item].append(dep)

    visited = {}
    def dfs(node, path):
        visited[node] = 1
        for neighbor in deps_map.get(node, []):
            if visited.get(neighbor) == 1:
                cycle_slice = path[path.index(neighbor):] + [neighbor]
                out.add("fail", "dependencies", "%s %s" % (backlog_where, neighbor),
                        "circular dependency detected: %s" % " -> ".join(cycle_slice))
            elif visited.get(neighbor, 0) == 0:
                dfs(neighbor, path + [neighbor])
        visited[node] = 2

    for node in sorted(deps_map.keys(), key=id_sort_key):
        if visited.get(node, 0) == 0:
            dfs(node, [node])


def check_hook_dependency(project, out):
    """The hooks stay silent unless they deny, so a missing jq -- which makes every hook
    allow every call -- is reported here instead."""
    hooks = project.path(os.path.join(".claude", "hooks"))
    if os.path.isdir(hooks) and any(n.endswith(".sh") for n in os.listdir(hooks)) \
            and shutil.which("jq") is None:
        out.add("warn", "hooks", ".claude/hooks",
                "installed, but jq is not on PATH, so every hook allows every call")


def check_bite_leftover(project, out):
    if os.path.exists(project.path(os.path.join(BITE_DIR, "active.json"))):
        out.add("fail", "bite", BITE_DIR,
                "an interrupted `sdlc.py bite` left product files reverted; run "
                "`sdlc.py bite --restore`")


def doctor(project, today=None):
    out = Findings()
    today = today or datetime.date.today()
    check_bite_leftover(project, out)
    check_hook_dependency(project, out)
    check_identity(project, out)
    check_verified_claims(project, out)
    check_placeholders(project, out)
    check_pointer(project, out)
    check_charter(project, out)
    check_staleness(project, out, today)
    check_stack_versions(project, out, today)
    check_traceability(project, out)
    check_backlog_age(project, out, today)
    check_epics(project, out)
    check_dependencies(project, out)
    check_worklog_size(project, out)
    check_known_mistakes(project, out)
    check_rollback(project, out, today)
    check_profile(project, out)
    check_sensitive(project, out)
    return out.items


def print_findings(items):
    if not items:
        print("doctor: no mechanical findings. The judgment checks in /sdlc-doctor still "
              "apply.")
        return
    width = max(len(item["where"]) for item in items)
    for item in items:
        print("%-4s  %-12s  %-*s  %s" % (item["level"], item["check"], width, item["where"],
                                          item["message"]))
    fails = sum(1 for item in items if item["level"] == "fail")
    print("\n%d finding(s): %d fail, %d warn" % (len(items), fails, len(items) - fails))


# ---------------------------------------------------------------- verify

def evidence_dir(project, suffix=""):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = project.path(os.path.join(".ai-sdlc", "evidence", stamp + suffix))
    path, n = base, 1
    while os.path.exists(path):
        n += 1
        path = "%s-%d" % (base, n)
    os.makedirs(path)
    ignore = project.path(os.path.join(".ai-sdlc", "evidence", ".gitignore"))
    if not os.path.exists(ignore):
        # Evidence is local proof for the session that ran it, not a project record.
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n!.gitignore\n")
    return path


def verify(project, selected, timeout, parallel=False):
    charter = charter_commands(project.charter)
    recorded = project.profile.get("commands") or {}
    drift = []
    for stage in STAGES:
        want = "" if charter.get(stage, "") == "absent" else charter.get(stage, "")
        if project.profile and recorded.get(stage, "") != want:
            drift.append("%s: profile %r, charter %r (the charter is used)"
                         % (stage, recorded.get(stage, ""), want))
    folder = evidence_dir(project)
    head = project.git("rev-parse", "HEAD").strip()
    dirty = bool(project.git("status", "--porcelain").strip())

    def run_stage(stage, command):
        log = os.path.join(folder, stage + ".log")
        started = time.time()
        with open(log, "wb") as handle:
            try:
                code = subprocess.run(command, shell=True, cwd=project.root,
                                      stdin=subprocess.DEVNULL, stdout=handle,
                                      stderr=subprocess.STDOUT, timeout=timeout).returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                code, timed_out = None, True
        with open(log, "rb") as handle:
            raw = handle.read().decode("utf-8", "replace")
        clean, masked = redact(raw)
        if masked:
            with open(log, "w", encoding="utf-8") as handle:
                handle.write(clean)
        with open(log, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        sec = round(time.time() - started, 1)
        res = ("Verified: fail (timed out after %ds)" % timeout) if timed_out else ("Verified: pass" if code == 0 else "Verified: fail")
        return {
            "exit_code": code, "seconds": sec, "log": os.path.relpath(log, project.root),
            "log_sha256": digest, "redacted": masked, "result": res
        }

    runnable = []
    stage_entries = {}
    for stage in STAGES:
        command = charter.get(stage, "")
        entry = {"stage": stage, "command": command if command != "absent" else ""}
        if selected and stage not in selected:
            entry["result"] = "Not run (not selected)"
            stage_entries[stage] = entry
        elif command == "absent":
            entry["result"] = "Absent (declared)"
            stage_entries[stage] = entry
        elif not command:
            entry["result"] = "Absent (no command in the charter)"
            stage_entries[stage] = entry
        else:
            stage_entries[stage] = entry
            runnable.append((stage, command))

    if parallel and len(runnable) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(runnable), 4)) as executor:
            f_map = {executor.submit(run_stage, s, c): s for s, c in runnable}
            for fut in concurrent.futures.as_completed(f_map):
                s = f_map[fut]
                stage_entries[s].update(fut.result())
    else:
        for s, c in runnable:
            stage_entries[s].update(run_stage(s, c))

    results = [stage_entries[stage] for stage in STAGES]
    summary = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": project.root, "git_head": head, "dirty": dirty,
        "charter": project.charter_path, "drift": drift, "stages": results,
    }
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    ledger_append(project, [{
        "time": summary["generated"], "commit": head, "dirty": dirty, "stage": e["stage"],
        "command": e["command"], "exit_code": e.get("exit_code"), "result": e["result"],
        "output_sha256": e.get("log_sha256", ""), "run": os.path.basename(folder)}
        for e in results if "exit_code" in e])
    text = summary_markdown(summary, os.path.relpath(folder, project.root))
    with open(os.path.join(folder, "summary.md"), "w", encoding="utf-8") as handle:
        handle.write(text)
    return summary, text


def evidence_runs(project):
    """Every verify run on disk, oldest first: (folder name, summary dict)."""
    runs = []
    base = project.path(os.path.join(".ai-sdlc", "evidence"))
    if not os.path.isdir(base):
        return runs
    for name in sorted(os.listdir(base)):
        try:
            with open(os.path.join(base, name, "summary.json"), encoding="utf-8") as handle:
                runs.append((name, json.load(handle)))
        except (IOError, OSError, ValueError):
            continue
    return runs


# ---------------------------------------------------------------- identity

TRAILER = re.compile(r"^([A-Z][A-Za-z-]+):[ \t]*(.+?)[ \t]*$")


def trailers(message):
    """{key: value} from the trailer block, the last paragraph of a commit message."""
    paragraphs = [p for p in re.split(r"\n\s*\n", message.strip()) if p.strip()]
    found = {}
    if len(paragraphs) < 2:
        return found
    for line in paragraphs[-1].splitlines():
        m = TRAILER.match(line.strip())
        if m:
            found[m.group(1)] = m.group(2)
    return found


# Each harness fills Agent and Model differently; `sdlc.py trailers` reads what the
# environment gives and the agent supplies the rest (process/05-change-control.md).
AGENT_ENV = (("CLAUDECODE", "claude-code"), ("GEMINI_CLI", "gemini-cli"),
             ("CODEX_SANDBOX", "codex"), ("CODEX_HOME", "codex"),
             ("CURSOR_TRACE_ID", "cursor"), ("CURSOR_AGENT", "cursor"))
MODEL_ENV = ("AI_SDLC_MODEL", "ANTHROPIC_MODEL", "CLAUDE_CODE_MODEL", "GEMINI_MODEL",
             "OPENAI_MODEL", "CODEX_MODEL")


def identity(agent=None, model=None):
    if not agent:
        agent = os.environ.get("AI_SDLC_AGENT", "")
    if not agent:
        agent = next((name for var, name in AGENT_ENV if os.environ.get(var)), "unknown")
    if not model:
        model = next((os.environ[var] for var in MODEL_ENV if os.environ.get(var)), "unknown")
    return agent, model


def model_family(name):
    """Coarse vendor family, which is what independence is judged on."""
    n = (name or "").lower()
    for family, marks in (("anthropic", ("claude", "anthropic", "opus", "sonnet", "haiku",
                                         "fable", "mythos")),
                          ("openai", ("gpt", "openai", "codex", "o1", "o3", "o4")),
                          ("google", ("gemini", "google", "bard")),
                          ("meta", ("llama",)), ("mistral", ("mistral", "mixtral")),
                          ("deepseek", ("deepseek",)), ("qwen", ("qwen",)),
                          ("human", ("human", "person"))):
        if any(mark in n for mark in marks):
            return family
    return "unknown"


def item_commits(project, item):
    """[(sha, parent, trailers)] for commits naming <item> in a Work-Item trailer or in
    the message, newest first."""
    out = project.git("log", "--all", "--format=%H%x01%P%x01%B%x00")
    found = []
    pattern = re.compile(r"(?<![A-Za-z0-9])%s(?![0-9])" % re.escape(item))
    for record in out.split("\x00"):
        parts = record.strip("\n").split("\x01")
        if len(parts) < 3 or not parts[0].strip():
            continue
        tags = trailers(parts[2])
        if tags.get("Work-Item") == item or pattern.search(parts[2]):
            found.append((parts[0].strip(), (parts[1].split() or [""])[0], tags))
    return found


def item_author(project, item):
    """(agent, model) from the item's commit trailers, or (None, None) when no commit
    carries them -- work from before 4.0, which the identity rules do not judge."""
    for _, _, tags in item_commits(project, item):
        if tags.get("Model") or tags.get("Agent"):
            return tags.get("Agent", "unknown"), tags.get("Model", "unknown")
    return None, None


# ---------------------------------------------------------------- ledger

def ledger_path(project):
    return project.path(os.path.join(project.docs, "project", "evidence-ledger.jsonl"))


def ledger_append(project, entries):
    """The committed evidence ledger: one JSON line per stage run by `sdlc.py verify` (or
    `bite`). Logs stay in the git-ignored evidence folder; the ledger is the part a
    reviewer on another machine, or CI, can check a claim against."""
    path = ledger_path(project)
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        return
    with open(path, "a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def ledger(project):
    rows = []
    try:
        with open(ledger_path(project), encoding="utf-8") as handle:
            for line in handle:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except (IOError, OSError):
        pass
    return rows


def evidence_matches(project, item, rows=None):
    """Ledger rows that verify <item> (the usual order is verify, then commit)."""
    rows = ledger(project) if rows is None else rows
    commits = item_commits(project, item)
    heads = set(sha for sha, _, _ in commits)
    parents = set(parent for _, parent, _ in commits if parent)
    # A clean run on one of the item's commits, or a run on the parent of one with the
    # change still uncommitted. A dirty run on the item's own commit verified whatever
    # came next, not the item.
    return [row for row in rows if (row.get("commit") in heads and not row.get("dirty"))
            or (row.get("dirty") and row.get("commit") in parents)]


# ---------------------------------------------------------------- review

REVIEW_HARNESSES = {
    "claude": (["claude", "-p", "{prompt}", "--output-format", "text"], "--model"),
    "codex": (["codex", "exec", "{prompt}"], "--model"),
    "gemini": (["gemini", "-p", "{prompt}"], "--model"),
}


def item_diff(project, item, base=None):
    commits = item_commits(project, item)
    if not commits and not base:
        return None, "no commit names %s; pass --base to review the working tree" % item
    if base:
        return project.git("diff", base), None
    oldest, newest = commits[-1], commits[0]
    start = oldest[1] or project.git("hash-object", "-t", "tree", "/dev/null").strip()
    return project.git("diff", start, newest[0]), None


def item_tier(project, item):
    for row_id, _, cells in backlog_rows(project.records("backlog.md"), project.prefix,
                                         getattr(project, "legacy_prefixes", None)):
        if row_id == item and len(cells) > 2:
            m = re.search(r"[123]", cells[2])
            return m.group(0) if m else ""
    return ""


def review_prompt(project, item, role, tier, diff):
    playbook = read(project.path(os.path.join(project.docs, "roles", role + ".md")))
    charter = project.charter
    rows = "\n".join(line for line in charter.splitlines()
                     if re.match(r"^\| \*\*(Project|What it is|Work item prefix|Tier rules|"
                                 r"Always Tier 1 here|Never Tier 1 here|Human approval "
                                 r"required for|Data categories held|Access level model|"
                                 r"Accessibility target|Jurisdictions / regimes)\*\*", line))
    return ("You are an independent reviewer. Review the diff below as the %s role, using only "
            "the playbook, the charter rows and the diff given here. Work item %s, Tier %s.\n\n"
            "Answer in this exact shape:\nVerdict: Pass | Pass with conditions | Block\n"
            "Checked: <what you examined>\nNot checked: <what you did not>\nFindings:\n"
            "| # | Sev | Location | Finding | Consequence | Fix |\n\n"
            "## Playbook\n\n%s\n\n## Charter rows\n\n%s\n\n## Diff\n\n```diff\n%s\n```\n"
            % (role, item, tier or "unknown", playbook, rows or "(none filled)", diff))


def review(project, item, role, by, model=None, stage="ship", base=None, timeout=1800):
    """Run one role's review of <item>'s diff in another harness, headless, and save it in
    the review format. Returns (path, record, error)."""
    if not os.path.isfile(project.path(os.path.join(project.docs, "roles", role + ".md"))):
        return None, None, "no playbook %s/roles/%s.md" % (project.docs, role)
    if by.startswith("cmd:"):
        command, harness = by[4:].strip(), "cmd"
        if not command:
            return None, None, "--by cmd: needs a command"
    elif by in REVIEW_HARNESSES:
        command, harness = None, by
        if shutil.which(REVIEW_HARNESSES[by][0][0]) is None:
            return None, None, ("%s is not installed (no `%s` on PATH); install it, or use "
                                "--by cmd:<command> with a reviewer that reads the prompt on "
                                "stdin" % (by, REVIEW_HARNESSES[by][0][0]))
    else:
        return None, None, "--by must be claude, codex, gemini or cmd:<command>"
    diff, error = item_diff(project, item, base)
    if error:
        return None, None, error
    tier = item_tier(project, item)
    prompt = review_prompt(project, item, role, tier, diff)
    try:
        if command:
            proc = subprocess.run(command, shell=True, cwd=project.root, input=prompt,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True, timeout=timeout)
        else:
            args, flag = REVIEW_HARNESSES[by]
            args = [part.replace("{prompt}", prompt) for part in args]
            if model:
                args += [flag, model]
            proc = subprocess.run(args, cwd=project.root, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, None, "the reviewer did not answer within %ds" % timeout
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, None, "the reviewer failed (exit %s): %s" % (
            proc.returncode, (proc.stderr or proc.stdout).strip()[-400:])
    reviewer_model = model or "unknown (the harness default)"
    if harness == "cmd":
        m = re.search(r"^Model:\s*(\S+)", proc.stdout, re.M)
        reviewer_model = model or (m.group(1) if m else "unknown")
    author_agent, author_model = item_author(project, item)
    family_reviewer = model_family(reviewer_model if reviewer_model != "unknown (the harness default)"
                                   else {"claude": "claude", "codex": "openai",
                                         "gemini": "gemini"}.get(harness, ""))
    family_author = model_family(author_model or author_agent or "")
    independent = (family_reviewer not in ("unknown",) and family_author != "unknown"
                   and family_reviewer != family_author)
    verdict = re.search(r"^Verdict:\s*(Pass with conditions|Pass|Block)", proc.stdout, re.M)
    folder = project.path(os.path.join(project.docs, "project", "reviews"))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    name = "%s-%s-%s.md" % (item, stage, role)
    path = os.path.join(folder, name)
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, "%s-%s-%s-%d.md" % (item, stage, role, n))
    record = {
        "item": item, "stage": stage, "role": role, "tier": tier,
        "reviewer_agent": harness if harness != "cmd" else "cmd:" + command.split()[0],
        "reviewer_model": reviewer_model, "reviewer_family": family_reviewer,
        "author_agent": author_agent or "unknown", "author_model": author_model or "unknown",
        "author_family": family_author,
        "independence": "independent" if independent else "self-check",
        "verdict": verdict.group(1) if verdict else "unstated",
    }
    today = datetime.date.today().isoformat()
    text = ("---\nstatus: current\nowner: %s\nlast-reviewed: %s\n---\n\n"
            "# Review — %s\n\n**Stage:** %s **Tier:** %s\n"
            "**Reviewed:** the item's diff (%d lines), by `sdlc.py review`\n"
            "**Reviewer agent:** %s\n**Reviewer model:** %s\n"
            "**Author:** %s / %s\n**Independence:** %s\n\n---\n\n## %s\n\n%s\n"
            % (record["reviewer_agent"], today, item, stage, tier or "unknown",
               len(diff.splitlines()), record["reviewer_agent"], reviewer_model,
               record["author_agent"], record["author_model"],
               record["independence"] + ("" if independent else
                                          " (same model family as the author, or unknown; "
                                          "it cannot clear a gate)"),
               role, proc.stdout.strip()))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return os.path.relpath(path, project.root), record, None


def review_records(project, item):
    """Parsed headers of every review file for <item>."""
    folder = project.path(os.path.join(project.docs, "project", "reviews"))
    found = []
    if not os.path.isdir(folder):
        return found
    for name in sorted(os.listdir(folder)):
        if not (name.startswith(item + "-") and name.endswith(".md")):
            continue
        text = read(os.path.join(folder, name))
        fields = dict(re.findall(r"^\*\*(Reviewer agent|Reviewer model|Independence|Author):\*\*"
                                 r"\s*(.+)$", text, re.M))
        found.append({"file": name, "fields": fields})
    return found


def check_identity(project, out):
    """Tier 1 work (and Tier 2 if the charter says so) needs a review from a different
    model family than the author's. Same-family reviews are recorded as self-checks and
    clear nothing. Only items whose commits carry Agent or Model trailers are judged:
    earlier work has no author identity to compare."""
    cell = UNFILLED.sub("", labelled(project.charter, "Independent review required for") or "")
    # The template lists both options; only a cell that names "Tier 1 and 2" alone decides.
    tiers = {"1", "2"} if "and 2" in cell and cell.count("Tier 1") == 1 else {"1"}
    where = os.path.join(project.docs, "project", "backlog.md")
    for item, status, cells in backlog_rows(project.records("backlog.md"), project.prefix,
                                            getattr(project, "legacy_prefixes", None)):
        tier = re.search(r"[123]", cells[2]).group(0) if len(cells) > 2 and \
            re.search(r"[123]", cells[2]) else ""
        if tier not in tiers or status not in ("In review", "Parked", "Done"):
            continue
        agent, model = item_author(project, item)
        if agent is None:
            continue
        author = model_family(model if model != "unknown" else agent)
        independent = []
        for rec in review_records(project, item):
            reviewer = model_family(rec["fields"].get("Reviewer model", "") or
                                    rec["fields"].get("Reviewer agent", ""))
            if reviewer not in ("unknown",) and author != "unknown" and reviewer != author:
                independent.append(rec["file"])
        if not independent:
            out.add("fail", "independence", "%s %s" % (where, item),
                    "Tier %s, %s: no review from a model family other than the author's "
                    "(%s). Run `sdlc.py review %s --role <role> --by <other harness>`; a "
                    "same-family review is a self-check and cannot clear this gate"
                    % (tier, status, author, item))


def check_verified_claims(project, out):
    """A worklog entry that says Verified for an item must have a ledger row for one of
    that item's commits. Only entries for items that have commits are judged."""
    rows = ledger(project)
    text = project.records("worklog.md")
    prefix = project.prefix
    if not prefix or not text:
        return
    entries = re.split(r"(?m)^(?=## |- [0-9]{4}-[0-9]{2}-[0-9]{2} · )", text)
    where = os.path.join(project.docs, "project", "worklog.md")
    for entry in entries:
        head = re.match(r"^(?:## |- [0-9-]+ · )(%s-[0-9]+)" % re.escape(prefix), entry)
        if not head or not re.search(r"\bVerified\b", entry):
            continue
        item = head.group(1)
        if not item_commits(project, item):
            continue
        if not evidence_matches(project, item, rows):
            out.add("warn", "evidence", "%s %s" % (where, item),
                    "says Verified, but the evidence ledger has no `sdlc.py verify` run on "
                    "this item's commits. Only verify makes a result Verified")


def budgets(project):
    """{tier: {"tokens": n, "minutes": n}} from the charter's Agent budget per tier row."""
    cell = UNFILLED.sub("", labelled(project.charter, "Agent budget per tier") or "")
    found = {}
    for tier, body in re.findall(r"Tier\s*([123])\s*:\s*([^;|]+)", cell):
        entry = {}
        tokens = re.search(r"([0-9.]+)\s*([kKmM]?)\s*tokens", body)
        if tokens:
            scale = {"k": 1e3, "m": 1e6}.get(tokens.group(2).lower(), 1)
            entry["tokens"] = int(float(tokens.group(1)) * scale)
        minutes = re.search(r"([0-9.]+)\s*(min|minutes|h|hours)", body)
        if minutes:
            entry["minutes"] = float(minutes.group(1)) * (60 if minutes.group(2).startswith("h") else 1)
        found[tier] = entry
    return found


def budget_usage(project):
    """Per item with Tokens/Minutes trailers: its tier, its usage, and its tier's budget.
    No harness writes these by itself; an agent adds them where it can read its usage."""
    limits = budgets(project)
    report = []
    for item, _, cells in backlog_rows(project.records("backlog.md"), project.prefix,
                                       getattr(project, "legacy_prefixes", None)):
        tokens = minutes = 0
        seen = False
        for _, _, tags in item_commits(project, item):
            if "Tokens" in tags or "Minutes" in tags:
                seen = True
                tokens += int(re.sub(r"[^0-9]", "", tags.get("Tokens", "0")) or 0)
                minutes += float(re.sub(r"[^0-9.]", "", tags.get("Minutes", "0")) or 0)
        if not seen:
            continue
        tier = item_tier(project, item)
        report.append({"item": item, "tier": tier, "tokens": tokens, "minutes": minutes,
                       "budget": limits.get(tier, {})})
    return report


# ---------------------------------------------------------------- log

def log_entries(project, since):
    """Draft worklog lines from the commits since <since>, one per work item, in the
    worklog's compact form. Verification comes from verify runs recorded on one of the
    item's commits; with none, it says so. Returns (lines, commits without an ID)."""
    prefix = project.prefix
    out = project.git("log", "--reverse", "--format=%H%x01%cs%x01%s%x01%b%x00",
                      "%s..HEAD" % since)
    items, order, orphans = {}, [], []
    for record in out.split("\x00"):
        parts = record.strip("\n").split("\x01")
        if len(parts) < 4 or not parts[0].strip():
            continue
        sha, date, subject, body = parts[0].strip(), parts[1], parts[2], parts[3]
        trailer = re.search(r"^Work-Item:\s*(\S+)", body, re.M)
        found = sorted(ids_in(subject + "\n" + body, prefix)) if prefix else []
        item = trailer.group(1) if trailer else (found[0] if found else None)
        if not item:
            orphans.append("%s %s" % (sha[:7], subject))
            continue
        if item not in items:
            items[item] = {"date": date, "subjects": [], "shas": [], "files": []}
            order.append(item)
        entry = items[item]
        entry["date"] = date
        entry["subjects"].append(subject)
        entry["shas"].append(sha)
        for path in project.git("show", "--name-only", "--format=", sha).splitlines():
            if path.strip() and path not in entry["files"] and not KIT_PATH.match(path) \
                    and not NOISE_PATH.search(path):
                entry["files"].append(path)
    runs = evidence_runs(project)
    lines = []
    for item in order:
        entry = items[item]
        request = re.sub(r"\b%s\b[:\s-]*" % re.escape(item), "", entry["subjects"][0]).strip()
        shown = entry["files"][:3]
        changed = ", ".join(shown) + (" (+%d)" % (len(entry["files"]) - 3)
                                      if len(entry["files"]) > 3 else "")
        verified = "not run"
        for name, summary in reversed(runs):
            if summary.get("git_head") in entry["shas"]:
                ran = [e for e in summary.get("stages", [])
                       if str(e.get("result", "")).startswith("Verified")]
                failed = [e["stage"] for e in ran if "fail" in e["result"]]
                verified = ("%s: %s" % (name, "fail " + ",".join(failed) if failed
                                        else "pass " + ",".join(e["stage"] for e in ran))
                            if ran else "%s: nothing ran" % name)
                break
        lines.append("- %s · %s · %s · changed: %s · verified: %s · commits: %s"
                     % (entry["date"], item, request or entry["subjects"][0], changed or "none",
                        verified, " ".join(sha[:7] for sha in entry["shas"])))
    return lines, orphans


ID_TOKEN = r"[A-Z]+[-0-9.]*[0-9]\b"
NOISE_PATH = re.compile(r"(^|/)__pycache__/|\.py[co]$")


def write_log(project, lines):
    """Insert drafted lines above the newest worklog entry, skipping any item the worklog
    already names. Returns the lines written."""
    path = project.path(os.path.join(project.docs, "project", "worklog.md"))
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (IOError, OSError):
        return []
    new = [line for line in lines if line.split(" · ")[1] not in text]
    if not new:
        return []
    rows = text.split("\n")
    marker = next((i for i, row in enumerate(rows) if "New entries go here" in row), None)
    if marker is not None:
        at = marker + 1
    else:
        at = next((i for i, row in enumerate(rows)
                   if re.match(r"^## %s" % ID_TOKEN, row)
                   or re.match(r"^- [0-9]{4}-[0-9]{2}-[0-9]{2} ·", row)), len(rows))
    # Newest first, like every other entry.
    rows[at:at] = [""] + list(reversed(new))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rows))
    return new


# ---------------------------------------------------------------- bite

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|specs?)/|(^|/)test_[^/]*$|_test\.[A-Za-z]+$|"
                       r"\.(test|spec)\.[A-Za-z]+$|Tests?\.(java|cs|kt)$")
KIT_PATH = re.compile(r"^(\.ai-sdlc/|\.claude/|\.agents/|AGENTS\.md$|CLAUDE\.md$)")
BITE_DIR = os.path.join(".ai-sdlc", "bite")


def bite_files(project, base):
    """Product files that differ between <base> and the working tree."""
    names = set(project.git("diff", "--name-only", base).splitlines())
    names |= set(project.git("ls-files", "--others", "--exclude-standard").splitlines())
    docs = project.docs.rstrip("/") + "/"
    return sorted(n for n in names if n and not TEST_PATH.search(n) and not KIT_PATH.match(n)
                  and not NOISE_PATH.search(n) and not n.startswith(docs))


def bite_restore(project):
    """Put back every file an interrupted bite reverted. Returns the paths restored."""
    marker = project.path(os.path.join(BITE_DIR, "active.json"))
    if not os.path.exists(marker):
        return []
    with open(marker, encoding="utf-8") as handle:
        state = json.load(handle)
    restored = []
    for item in state["files"]:
        target = project.path(item["path"])
        if item["existed"]:
            folder = os.path.dirname(target)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            shutil.copy2(project.path(os.path.join(state["backup"], item["path"])), target)
        elif os.path.exists(target):
            os.remove(target)
        restored.append(item["path"])
    shutil.rmtree(project.path(state["backup"]), ignore_errors=True)
    os.remove(marker)
    return restored


def bite(project, command, base=None, timeout=1800):
    """Does the test command catch the change? Run it on the working tree, then with the
    product files put back to <base> (tests stay as they are), then restore. It bites
    when it passes with the change and fails without it. Returns (result, error)."""
    if os.path.exists(project.path(os.path.join(BITE_DIR, "active.json"))):
        return None, ("an earlier bite was interrupted and left files reverted; run "
                      "`sdlc.py bite --restore` first")
    if not project.git("rev-parse", "HEAD").strip():
        return None, "not a git repository with a commit"
    if base is None:
        base = "HEAD" if bite_files(project, "HEAD") else "HEAD~1"
    if not project.git("rev-parse", "--verify", "--quiet", base + "^{commit}").strip():
        return None, "base %r is not a commit" % base
    files = bite_files(project, base)
    if not files:
        return None, ("no product change between %s and the working tree to revert "
                      "(test files and the kit's own paths are left alone)" % base)

    def run():
        try:
            return subprocess.run(command, shell=True, cwd=project.root, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return None

    with_change = run()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(BITE_DIR, stamp)
    os.makedirs(project.path(backup))
    ignore = project.path(os.path.join(BITE_DIR, ".gitignore"))
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n!.gitignore\n")
    state = {"base": base, "backup": backup, "command": command, "files": []}
    for rel in files:
        existed = os.path.exists(project.path(rel))
        if existed:
            dest = project.path(os.path.join(backup, rel))
            if not os.path.isdir(os.path.dirname(dest)):
                os.makedirs(os.path.dirname(dest))
            shutil.copy2(project.path(rel), dest)
        state["files"].append({"path": rel, "existed": existed})
    with open(project.path(os.path.join(BITE_DIR, "active.json")), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)

    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        for rel in files:
            original = subprocess.run(["git", "show", "%s:%s" % (base, rel)], cwd=project.root,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            target = project.path(rel)
            if original.returncode == 0:
                if not os.path.isdir(os.path.dirname(target) or "."):
                    os.makedirs(os.path.dirname(target))
                with open(target, "wb") as handle:
                    handle.write(original.stdout)
            elif os.path.exists(target):
                os.remove(target)
        without_change = run()
    finally:
        bite_restore(project)
        signal.signal(signal.SIGTERM, previous)

    result = {"command": command, "base": base, "files": files,
              "with_change": with_change, "without_change": without_change,
              "bites": with_change == 0 and without_change not in (0, None),
              "git_head": project.git("rev-parse", "HEAD").strip(),
              "dirty": bool(project.git("status", "--porcelain").strip()),
              "generated": datetime.datetime.now(datetime.timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ")}
    folder = evidence_dir(project, "-bite")
    with open(os.path.join(folder, "bite.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    ledger_append(project, [{"time": result["generated"], "commit": result["git_head"],
                             "dirty": result["dirty"], "stage": "bite", "command": command,
                             "exit_code": 0 if result["bites"] else 1,
                             "result": "Verified: %s" % ("pass" if result["bites"] else "fail"),
                             "output_sha256": "", "run": os.path.basename(folder)}])
    result["evidence"] = os.path.relpath(folder, project.root)
    return result, None


def print_bite(result):
    verdict = ("bites: the tests pass with the change and fail without it"
               if result["bites"] else
               "does not bite: " + ("the tests fail with the change too; fix them first"
                                    if result["with_change"] != 0 else
                                    "the tests still pass without the change, so they do not "
                                    "test it"))
    print("bite %s" % ("PASS" if result["bites"] else "FAIL"))
    print("  command         %s" % result["command"])
    print("  reverted to     %s: %s" % (result["base"], ", ".join(result["files"])))
    print("  with change     exit %s" % result["with_change"])
    print("  without change  exit %s" % result["without_change"])
    print("  %s" % verdict)
    print("  evidence        %s" % result["evidence"])


def summary_markdown(summary, folder):
    lines = ["# Verification evidence", "",
             "Generated %s by `.ai-sdlc/bin/sdlc.py verify` at %s%s."
             % (summary["generated"], summary["git_head"][:12] or "(no git HEAD)",
                " with uncommitted changes" if summary["dirty"] else ""), "",
             "| Stage | Result | Exit | Seconds | Command | Log |",
             "| --- | --- | --- | --- | --- | --- |"]
    for entry in summary["stages"]:
        lines.append("| `checks.%s` | %s | %s | %s | %s | %s |" % (
            entry["stage"], entry["result"],
            "" if entry.get("exit_code") is None else entry["exit_code"],
            entry.get("seconds", ""),
            ("`%s`" % entry["command"].replace("|", "\\|")) if entry["command"] else "",
            entry.get("log", "")))
    masked = sum(e.get("redacted", 0) for e in summary["stages"])
    if masked:
        lines += ["", "**%d credential-shaped string(s) were masked in the logs.** Something "
                  "printed a secret; find out what, and rotate it if it was real." % masked]
    if summary["drift"]:
        lines += ["", "**Profile drift** (the charter was used):", ""]
        lines += ["- " + item for item in summary["drift"]]
    lines += ["", "Evidence: `%s/`. Quote this table; do not restate results from memory."
              % folder, ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- plan-check

PLAN_PLACEHOLDERS = ("path/or/glob",)


def plan_section(text, heading):
    """The lines under `## heading`, up to the next `## `."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == heading.lower()
            continue
        if inside:
            lines.append(line)
    return lines


def expand_braces(token):
    """`a/{b,c}.ts` -> a/b.ts, a/c.ts. One level, which is what plans use."""
    match = re.search(r"[{]([^{}]*,[^{}]*)[}]", token)
    if not match:
        return [token]
    out = []
    for part in match.group(1).split(","):
        out.extend(expand_braces(token[:match.start()] + part.strip() + token[match.end():]))
    return out


def code_bullet(text):
    """Plans written before "Files that change" existed name their files in the
    **Code:** bullet of "Affected surfaces", inline or as nested items."""
    lines, inside = [], False
    for line in plan_section(text, "Affected surfaces"):
        stripped = line.lstrip()
        top = stripped.startswith(("- **", "* **")) and len(line) - len(stripped) < 2
        if top:
            inside = stripped[2:].startswith("**Code:**")
            if inside:
                lines.append("- " + stripped[2:])
        elif inside and stripped:
            lines.append(line)
    return lines


def planned_paths(text):
    """Backticked paths or globs in the plan's "Files that change" list items, else in the
    Affected surfaces **Code:** bullet. The template's hint and example are not plans."""
    found = []
    for source in (plan_section(text, "Files that change"), code_bullet(text)):
        for line in source:
            if not line.lstrip().startswith(("-", "*")):
                continue
            for token in re.findall(r"`([^`]+)`", UNFILLED.sub("", line)):
                for path in expand_braces(token.strip()):
                    while path.startswith("./"):
                        path = path[2:]
                    if " " in path or path in PLAN_PLACEHOLDERS or path in found:
                        continue
                    if path:
                        found.append(path)
        if found:
            break
    return found


def glob_regex(pattern):
    """`**` spans directories, `*` and `?` do not; a bare directory matches its contents."""
    if not re.search(r"[*?\[]", pattern):
        pattern = pattern.rstrip("/")
        return re.compile(re.escape(pattern) + r"(/.*)?$")
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + "$")


def default_branch(project):
    cell = labelled(project.charter, "Default branch") or ""
    cell = UNFILLED.sub("", cell).strip().strip("`").strip()
    return cell or project.profile.get("default_branch") or ""


def changed_files(project, base):
    """Committed on the branch since it left base, plus anything not yet committed."""
    names = set()
    merge_base = project.git("merge-base", base, "HEAD").strip()
    if merge_base:
        names.update(project.git("diff", "--name-only", merge_base, "HEAD").split("\n"))
    names.update(project.git("diff", "--name-only", "HEAD").split("\n"))
    names.update(project.git("ls-files", "--others", "--exclude-standard").split("\n"))
    records = project.docs.rstrip("/") + "/project/"
    return sorted(n for n in names if n and not n.startswith(records)
                  and not n.startswith(".ai-sdlc/"))


def plan_check(project, item, base=None):
    """Returns (result, error). The records under project/ are bookkeeping every change
    touches, so they are never "unplanned"."""
    folder = os.path.join(project.docs, "project", "plans")
    rel = os.path.join(folder, item + ".md")
    if not os.path.isfile(project.path(rel)) and os.path.isdir(project.path(folder)):
        # Plans are often named <ID>-<slug>.md.
        named = sorted(n for n in os.listdir(project.path(folder))
                       if n.startswith(item + "-") and n.endswith(".md"))
        if named:
            rel = os.path.join(folder, named[0])
    text = read(project.path(rel))
    if not text:
        spec_candidates = [
            os.path.join(".sdlc", "specs", item, "spec.md"),
            os.path.join(".sdlc", "specs", item, "walkthrough.md"),
            os.path.join(project.docs, "plans", item + ".md"),
        ]
        specs_dir = project.path(os.path.join(".sdlc", "specs"))
        if os.path.isdir(specs_dir):
            for d in sorted(os.listdir(specs_dir)):
                if d.startswith(item + "-"):
                    spec_candidates.append(os.path.join(".sdlc", "specs", d, "spec.md"))
        for cand in spec_candidates:
            if os.path.isfile(project.path(cand)):
                cand_text = read(project.path(cand))
                if cand_text:
                    rel = cand
                    text = cand_text
                    break
    if not text:
        return None, ("no plan at %s. Tier 1 items have one; a Tier 2 or 3 plan lives in "
                      "the response and cannot be checked mechanically." % rel)
    planned = planned_paths(text)
    if not planned:
        return None, ("%s has no backticked paths under \"## Files that change\", so "
                      "there is nothing to compare the diff with." % rel)
    base = base or default_branch(project) or "main"
    if not project.git("rev-parse", "--verify", "--quiet", base).strip():
        return None, ("base %r is not a git ref here. Pass --base, or fill the charter's "
                      "Default branch row." % base)
    changed = changed_files(project, base)
    regexes = [(p, glob_regex(p)) for p in planned]
    unplanned = [f for f in changed if not any(r.match(f) for _, r in regexes)]
    untouched = [p for p, r in regexes if not any(r.match(f) for f in changed)]
    return {"item": item, "plan": rel, "base": base, "planned": planned,
            "changed": changed, "unplanned": unplanned, "untouched": untouched}, None


def print_plan_check(result):
    use_color = sys.stdout.isatty()
    c_red = "\033[31m" if use_color else ""
    c_yellow = "\033[33m" if use_color else ""
    c_green = "\033[32m" if use_color else ""
    c_reset = "\033[0m" if use_color else ""

    print("plan-check %s: %d planned, %d changed since %s"
          % (result["item"], len(result["planned"]), len(result["changed"]),
             result["base"]))
    if not result["changed"]:
        print("Nothing has changed since %s, so there is no diff to compare. Run this on the "
              "item's branch, before it merges." % result["base"])
        return
    for f in result["unplanned"]:
        print("%swarn  unplanned   %s  (changed, but not in the plan's Files that change)%s"
              % (c_red, f, c_reset))
    for p in result["untouched"]:
        print("%swarn  untouched   %s  (in the plan, but nothing matching it changed)%s"
              % (c_yellow, p, c_reset))
    if not result["unplanned"] and not result["untouched"]:
        print("%sThe diff matches the plan's file list. Whether it matches the plan's intent "
              "is the review's conformance pass.%s" % (c_green, c_reset))
    else:
        print("\nEach gap is either a plan to update (in the same commit) or a change to "
              "question. Neither is decided here.")


# ---------------------------------------------------------------- self-test

def selftest():
    charter = "\n".join([
        "| **Work item prefix** | `ACME` _(2–4 uppercase letters, e.g. `ACME`)_ |",
        "| `checks.unit` | `python3 -m unittest` |",
        "| `checks.lint` | |",
        "| `checks.eval` | _(if any output is probabilistic)_ |",
        "| `checks.build` | absent |",
        "| `checks.scan` | `a \\| b` |",
        "| **Default effort mode** | `Lean` · `Normal` · `Beast` _(default: Normal)_ |",
        "| **Acquisition profile** | `Advanced` |",
        "| **Approvers** | _(names)_ |",
        "| qa | ☑ | always | |",
        "| seo | ☐ | content is public | |",
        "| cro-analyst | ☐ | a goal | no funnel |",
    ])
    commands = charter_commands(charter)
    assert commands == {"unit": "python3 -m unittest", "lint": "", "eval": "",
                        "build": "absent", "scan": "a | b"}, commands
    assert choice(labelled(charter, "Default effort mode"), EFFORT) == (None, "undecided")
    assert choice(labelled(charter, "Acquisition profile"), ACQUISITION) == \
        ("Advanced", "decided")
    assert choice("`Fast`", EFFORT) == (None, "invalid")
    assert unfilled(labelled(charter, "Approvers"))
    assert roles(charter) == [("qa", True, ""), ("seo", False, ""),
                              ("cro-analyst", False, "no funnel")]
    backlog = ("| ACME-2 | Ship it | 2 | qa | | `Done` | 2026-01-01 |\n"
               "| ACME-10 | x | 3 | qa | | Parked | | why | |\n"
               "| S61.5 | Legacy story | 2 | qa | | Ready |")
    rows = backlog_rows(backlog, "ACME")
    assert [(r[0], r[1]) for r in rows] == [("ACME-2", "Done"), ("ACME-10", "Parked"), ("S61.5", "Ready")]
    assert ids_in("ACME-3 and ACME-12, not ACME-### or XACME-4", "ACME") == {"ACME-3", "ACME-12"}
    assert ids_in("Working on S61.5 and ACME-3", "ACME", {"S61.5"}) == {"ACME-3", "S61.5"}
    assert ids_in("Delivered S61.1–S61.3 and E0-E2", "ACME", {"S61.1", "S61.2", "S61.3", "E0", "E1", "E2"}) == \
        {"S61.1", "S61.2", "S61.3", "E0", "E1", "E2"}
    assert frontmatter("---\nstatus: draft\nlast-reviewed: 2026-01-01\n---\n# x") == \
        {"status": "draft", "last-reviewed": "2026-01-01"}
    today = datetime.date(2026, 4, 1)
    assert age_days("2026-01-01", today) == 90 and age_days("YYYY-MM-DD", today) is None
    assert PLACEHOLDER.findall("a " + "{" * 2 + "PREFIX" + "}" * 2) == ["{" * 2 + "PREFIX" + "}" * 2]
    assert version_tuple("3.10.0") > version_tuple("3.9.9")
    fake = "token=AKIA" + "ABCDEFGHIJKLMNOP and " + "ghp_" + "a" * 36
    clean, n = redact(fake)
    assert n == 2 and "ABCDEFGHIJKLMNOP" not in clean and "[redacted: AWS access key]" in clean, clean
    dep_backlog = (
        "| ID | Task | Tier | Owner role | Depends on | Status |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| ACME-1 | First task | 2 | qa | | Done |\n"
        "| ACME-2 | Second task | 2 | qa | `ACME-1` | Now |\n"
        "| ACME-3 | Broken dep | 2 | qa | `ACME-99` | Blocked |\n"
        "| ACME-4 | Self loop | 2 | qa | `ACME-4` | Blocked |\n"
        "| ACME-5 | Cycle A | 2 | qa | `ACME-6` | Blocked |\n"
        "| ACME-6 | Cycle B | 2 | qa | `ACME-5` | Blocked |\n"
    )
    class FakeProj(object):
        prefix = "ACME"
        legacy_prefixes = set()
        docs = "docs"
        def records(self, name):
            return dep_backlog if name == "backlog.md" else ""
    df = Findings()
    check_dependencies(FakeProj(), df)
    d_items = [(f["check"], f["level"], f["message"]) for f in df.items]
    assert any("depends on ACME-99" in m for c, l, m in d_items)
    assert any("cannot depend on itself" in m for c, l, m in d_items)
    assert any("circular dependency" in m for c, l, m in d_items)
    plan = ("# Plan\n## Files that change\n\n_(hint with `x/y`)_\n\n- `path/or/glob`\n"
            "- `src/billing/**` and `./db/0042_*.sql`\n- `README.md`, `.github/ci.yml`\n"
            "## Order of work\n"
            "- `not/this.py`\n")
    assert planned_paths(plan) == ["src/billing/**", "db/0042_*.sql", "README.md",
                                   ".github/ci.yml"], planned_paths(plan)
    old_plan = ("## Affected surfaces\n\n- **Code:**\n  - `apps/a.ts`\n  - `lib/*`\n"
                "- **Data:** `not/this.sql`\n")
    assert planned_paths(old_plan) == ["apps/a.ts", "lib/*"], planned_paths(old_plan)
    inline = "## Affected surfaces\n- **Code:** `api/{a,b}`, `web/x.ts`\n- **Data:** none\n"
    assert planned_paths(inline) == ["api/a", "api/b", "web/x.ts"], planned_paths(inline)
    assert glob_regex("src/billing/**").match("src/billing/a/b.py")
    assert not glob_regex("db/0042_*.sql").match("db/sub/0042_x.sql")
    assert glob_regex("src/api").match("src/api/x.py")
    assert not glob_regex("src/api").match("src/apiary.py")
    assert glob_regex("**/test_*.py").match("test_a.py")
    aws = "AKIA" + "ABCDEFGHIJKLMNOP"
    assert sensitive_kinds("key " + aws) == (["AWS access key"], [])
    assert sensitive_kinds("key AKIAIOSFODNN7EXAMPLE") == ([], [])
    assert sensitive_kinds("db postgres://app:" + "s3cretPw" + "@prod.db.internal/app")[0] == \
        ["URL with embedded password"]
    assert sensitive_kinds("db postgres://user:PASSWORD@db.example.com/app") == ([], [])
    assert sensitive_kinds("ask jane.doe@acme-corp.io") == ([], ["email address"])
    assert sensitive_kinds("ask me@eu.example.org or noreply@acme.io") == ([], [])
    assert sensitive_kinds("card 4111 1111 1111 1111")[1] == ["card-number shape"]
    assert sensitive_kinds("plain prose, ACME-12, 2026-01-01") == ([], [])
    print("sdlc runtime self-test passed")


# ---------------------------------------------------------------- entry

def default_root():
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.dirname(os.path.dirname(here))
    if os.path.basename(here) == "bin" and os.path.basename(os.path.dirname(here)) == ".ai-sdlc":
        return candidate
    return os.getcwd()


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    parser = argparse.ArgumentParser(prog="sdlc.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", help="project root (default: the project this file is "
                        "installed in)")
    sub = parser.add_subparsers(dest="command")
    doc = sub.add_parser("doctor", help="mechanical checks of the SDLC records")
    doc.add_argument("--json", action="store_true", help="print findings as JSON")
    doc.add_argument("--strict", action="store_true",
                     help="exit 1 if any finding is at level fail (for CI)")
    ver = sub.add_parser("verify", help="run the charter's check commands and record "
                         "the evidence")
    ver.add_argument("--stage", help="comma-separated stages to run, e.g. unit,lint")
    ver.add_argument("--timeout", type=int, default=1800, help="seconds per stage")
    ver.add_argument("--parallel", "-j", action="store_true",
                     help="run independent verification stages concurrently")
    chk = sub.add_parser("plan-check", help="compare a Tier 1 plan's file list with the "
                         "branch's diff")
    chk.add_argument("item", help="work item ID, e.g. ACME-12")
    chk.add_argument("--base", help="branch the work left (default: the charter's Default "
                     "branch, else main)")
    chk.add_argument("--json", action="store_true", help="print the result as JSON")
    chk.add_argument("--strict", action="store_true",
                     help="exit 1 if any file is unplanned or any planned path untouched")
    vw = sub.add_parser("view", help="draw the records as an interactive page "
                        "(.ai-sdlc/view/index.html, git-ignored)")
    vw.add_argument("--no-open", action="store_true", help="write the page, do not open it")
    vw.add_argument("--json", action="store_true", help="print the model instead")
    vw.add_argument("--serve", action="store_true", help="live mode: serve the page on "
                     "127.0.0.1 and update it as the records change")
    vw.add_argument("--port", type=int, default=8765, help="live mode port (default 8765; "
                     "0 picks a free one)")
    vw.add_argument("--interval", type=int, default=2, help="live mode: seconds between "
                     "checks for changes (default 2)")
    vw.add_argument("--svg", nargs="?", const="", default=None,
                    help="export the mind map as a formatted SVG file (.ai-sdlc/view/map.svg by default)")
    vw.add_argument("--export-html", nargs="?", const="dashboard.html", default=None,
                    help="export the standalone dashboard HTML file (default: dashboard.html)")
    met = sub.add_parser("metrics", help="process measures from the records and git")
    met.add_argument("--json", action="store_true", help="print as JSON")
    lg = sub.add_parser("log", help="draft worklog lines from commits and verify runs")
    lg.add_argument("--since", required=True, help="git ref to start after, e.g. main or HEAD~5")
    lg.add_argument("--write", action="store_true", help="insert the drafts into the worklog "
                    "(items it already names are skipped)")
    tr = sub.add_parser("trailers", help="print the commit trailers for a work item")
    tr.add_argument("item", help="work item ID")
    tr.add_argument("--agent", help="the harness making the commit (default: from the "
                    "environment, else unknown)")
    tr.add_argument("--model", help="the model id (default: from the environment, else "
                    "unknown)")
    rv = sub.add_parser("review", help="run one role's review of an item's diff in another "
                        "harness and save it")
    rv.add_argument("item", help="work item ID")
    rv.add_argument("--role", required=True, help="role playbook, e.g. security")
    rv.add_argument("--by", required=True, help="claude, codex, gemini, or cmd:<command> "
                    "(reads the prompt on stdin, prints the review)")
    rv.add_argument("--model", help="model to ask the harness for; recorded")
    rv.add_argument("--stage", default="ship", choices=("design", "ship"))
    rv.add_argument("--base", help="review the diff from this ref to the working tree "
                    "instead of the item's commits")
    rv.add_argument("--timeout", type=int, default=1800)
    bt = sub.add_parser("bite", help="check that a test command fails without the change "
                        "and passes with it")
    bt.add_argument("test_command", nargs=argparse.REMAINDER,
                    help="the test command, e.g. python3 -m unittest discover -s tests")
    bt.add_argument("--base", help="ref to revert product files to (default: HEAD when "
                    "there are uncommitted product changes, else HEAD~1)")
    bt.add_argument("--timeout", type=int, default=1800, help="seconds per test run")
    bt.add_argument("--restore", action="store_true",
                    help="put back files an interrupted bite left reverted")
    bt.add_argument("--json", action="store_true", help="print the result as JSON")
    opts = parser.parse_args(argv)
    if not opts.command:
        parser.print_help()
        return 2
    project = Project(opts.root or default_root())
    if opts.command == "doctor":
        items = doctor(project)
        if opts.json:
            print(json.dumps(items, indent=2))
        else:
            print_findings(items)
        return 1 if opts.strict and any(i["level"] == "fail" for i in items) else 0
    if opts.command in ("view", "metrics"):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        sys.dont_write_bytecode = True  # no __pycache__ next to kit files in a project
        import view
        if opts.command == "metrics":
            return view.print_metrics(sys.modules[__name__], project, opts)
        return view.run(sys.modules[__name__], project, opts)
    if opts.command == "log":
        if not project.git("rev-parse", "--verify", "--quiet", opts.since + "^{commit}").strip():
            sys.stderr.write("log: %r is not a commit\n" % opts.since)
            return 2
        lines, orphans = log_entries(project, opts.since)
        if opts.write:
            written = write_log(project, lines)
            print("wrote %d line(s) to %s/project/worklog.md" % (len(written), project.docs))
            lines = written
        for line in lines:
            print(line)
        for orphan in orphans:
            print("no work item ID: %s" % orphan, file=sys.stderr)
        return 0
    if opts.command == "trailers":
        agent, model = identity(opts.agent, opts.model)
        print("Work-Item: %s\nAgent: %s\nModel: %s" % (opts.item, agent, model))
        return 0
    if opts.command == "review":
        path, record, error = review(project, opts.item, opts.role, opts.by, opts.model,
                                     opts.stage, opts.base, opts.timeout)
        if error:
            sys.stderr.write("review: %s\n" % error)
            return 2
        print("review saved: %s" % path)
        print("  reviewer  %s / %s" % (record["reviewer_agent"], record["reviewer_model"]))
        print("  author    %s / %s" % (record["author_agent"], record["author_model"]))
        print("  %s; verdict: %s" % (record["independence"], record["verdict"]))
        return 0
    if opts.command == "bite":
        if opts.restore:
            restored = bite_restore(project)
            print("restored %d file(s)%s" % (len(restored), (": " + ", ".join(restored))
                                             if restored else ""))
            return 0
        command = " ".join(opts.test_command).strip()
        if command.startswith("-- "):
            command = command[3:]
        if not command:
            parser.error("bite needs a test command")
        result, error = bite(project, command, opts.base, opts.timeout)
        if error:
            sys.stderr.write("bite: %s\n" % error)
            return 2
        if opts.json:
            print(json.dumps(result, indent=2))
        else:
            print_bite(result)
        return 0 if result["bites"] else 1
    if opts.command == "plan-check":
        result, error = plan_check(project, opts.item, opts.base)
        if error:
            sys.stderr.write("plan-check: %s\n" % error)
            return 2
        if opts.json:
            print(json.dumps(result, indent=2))
        else:
            print_plan_check(result)
        gaps = result["unplanned"] or result["untouched"]
        return 1 if opts.strict and gaps else 0
    selected = None
    if opts.stage:
        selected = set(s.strip().replace("checks.", "") for s in opts.stage.split(","))
        unknown = sorted(selected - set(STAGES))
        if unknown:
            parser.error("unknown stage: %s (stages: %s)" % (", ".join(unknown),
                                                              ", ".join(STAGES)))
    if not project.charter:
        sys.stderr.write("no charter at %s: nothing says which commands to run\n"
                         % project.charter_path)
        return 2
    summary, text = verify(project, selected, opts.timeout, parallel=getattr(opts, "parallel", False))
    print(text)
    failed = [e for e in summary["stages"] if e["result"].startswith("Verified: fail")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

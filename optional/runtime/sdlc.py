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

Standard library only. Installed and upgraded by the kit, so a local edit blocks
`--upgrade` rather than being lost; change the kit instead.

This file must never contain two opening braces in a row: the installer substitutes
that pattern in every file it installs. Regexes spell it '[{][{]'.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

# The order /sdlc-verify runs stages in (04-quality-gates.md), not the installer's
# question order.
STAGES = ("format", "lint", "typecheck", "infra", "unit", "integration", "data", "contract",
          "eval", "build", "scan", "a11y", "e2e", "perf")
POINTER_FILES = ("CLAUDE.md", "GEMINI.md", "AGENT.md", "CONVENTIONS.md",
                 ".github/copilot-instructions.md", ".windsurfrules", ".clinerules")
EFFORT = ("Lean", "Normal", "Beast")
ACQUISITION = ("Standard", "Advanced")
DEV_METHOD = ("Item", "Epic")
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
    mentioned = ids_in(project.git("log", "-50", "--format=%B"), prefix, known) | \
        ids_in(project.git("branch", "--format=%(refname:short)"), prefix, known)
    for item in sorted(mentioned - known - logged, key=id_sort_key):
        out.add("warn", "traceability", "git",
                "%s is in a recent commit or branch and in neither the backlog nor the "
                "worklog" % item)


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
                                ("dev_method", "Development method", DEV_METHOD)):
        value, state = choice(labelled(project.charter, label), options)
        if key == "dev_method" and key not in profile:
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


def doctor(project, today=None):
    out = Findings()
    today = today or datetime.date.today()
    check_placeholders(project, out)
    check_pointer(project, out)
    check_charter(project, out)
    check_staleness(project, out, today)
    check_traceability(project, out)
    check_epics(project, out)
    check_worklog_size(project, out)
    check_known_mistakes(project, out)
    check_rollback(project, out, today)
    check_profile(project, out)
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

def evidence_dir(project):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = project.path(os.path.join(".ai-sdlc", "evidence", stamp))
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


def verify(project, selected, timeout):
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
    results = []
    for stage in STAGES:
        command = charter.get(stage, "")
        entry = {"stage": stage, "command": command if command != "absent" else ""}
        if selected and stage not in selected:
            entry["result"] = "Not run (not selected)"
        elif command == "absent":
            entry["result"] = "Absent (declared)"
        elif not command:
            entry["result"] = "Absent (no command in the charter)"
        else:
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
            # A test that prints a token must not leave it on disk in the evidence.
            with open(log, "rb") as handle:
                raw = handle.read().decode("utf-8", "replace")
            clean, masked = redact(raw)
            if masked:
                with open(log, "w", encoding="utf-8") as handle:
                    handle.write(clean)
            with open(log, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            entry.update({"exit_code": code, "seconds": round(time.time() - started, 1),
                          "log": os.path.relpath(log, project.root), "log_sha256": digest,
                          "redacted": masked})
            if timed_out:
                entry["result"] = "Verified: fail (timed out after %ds)" % timeout
            else:
                entry["result"] = "Verified: pass" if code == 0 else "Verified: fail"
        results.append(entry)
    summary = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": project.root, "git_head": head, "dirty": dirty,
        "charter": project.charter_path, "drift": drift, "stages": results,
    }
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    text = summary_markdown(summary, os.path.relpath(folder, project.root))
    with open(os.path.join(folder, "summary.md"), "w", encoding="utf-8") as handle:
        handle.write(text)
    return summary, text


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
    print("plan-check %s: %d planned, %d changed since %s"
          % (result["item"], len(result["planned"]), len(result["changed"]),
             result["base"]))
    if not result["changed"]:
        print("Nothing has changed since %s, so there is no diff to compare. Run this on the "
              "item's branch, before it merges." % result["base"])
        return
    for f in result["unplanned"]:
        print("warn  unplanned   %s  (changed, but not in the plan's Files that change)" % f)
    for p in result["untouched"]:
        print("warn  untouched   %s  (in the plan, but nothing matching it changed)" % p)
    if not result["unplanned"] and not result["untouched"]:
        print("The diff matches the plan's file list. Whether it matches the plan's intent "
              "is the review's conformance pass.")
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
    met = sub.add_parser("metrics", help="process measures from the records and git")
    met.add_argument("--json", action="store_true", help="print as JSON")
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
    summary, text = verify(project, selected, opts.timeout)
    print(text)
    failed = [e for e in summary["stages"] if e["result"].startswith("Verified: fail")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

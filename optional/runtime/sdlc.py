#!/usr/bin/env python3
"""The mechanical half of /sdlc-doctor and /sdlc-verify.

Everything this script decides, it decides from files and commands: no model reads a
table and reports what it remembers. The judgment half -- severity, which artifacts a
role needs, behavioural checks, what to fix first -- stays with the agent, in the
markdown commands that call this.

    python3 .ai-sdlc/bin/sdlc.py doctor [--json] [--strict]
    python3 .ai-sdlc/bin/sdlc.py verify [--stage unit,lint] [--timeout 1800]
    python3 .ai-sdlc/bin/sdlc.py plan-check ACME-12 [--base main] [--json] [--strict]
    python3 .ai-sdlc/bin/sdlc.py approvals ACME-12 [--json]
    python3 .ai-sdlc/bin/sdlc.py ci-check [--base main] [--head REF|event] [--charter-ref REF] [--json]
    python3 .ai-sdlc/bin/sdlc.py view [--no-open] [--json] [--serve [--port 8765]
                                       [--host 127.0.0.1|tailscale|<ip>] [--allow-actions]]
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
import shlex
import shutil
import signal
import subprocess
import sys
import time

# The order /sdlc-verify runs stages in (04-quality-gates.md), not the installer's
# question order.
STAGES = ("format", "lint", "typecheck", "complexity", "infra", "unit", "mutation",
          "integration", "data", "contract", "eval", "build", "scan", "a11y", "e2e", "perf")
EFFORT = ("Lean", "Normal", "Beast")
ACQUISITION = ("Standard", "Advanced")
DEV_METHOD = ("Item", "Epic")
DECISION_STYLE = ("Ask", "Guide", "Autopilot")
TIER_RULES = ("Standard", "Strict")
DISCOVERED_DEFECTS = ("Parked", "Auto-Ready (bite)")
WORKLOG_ROTATE_LINES = 1000
DEFAULT_STALENESS_DAYS = 90
KNOWN_MISTAKES_LINES = 30
sys.dont_write_bytecode = True
_RUNTIME_DIR = os.path.dirname(os.path.abspath(__file__))
if _RUNTIME_DIR not in sys.path:
    sys.path.insert(0, _RUNTIME_DIR)
import hooks as _hooks_mod  # noqa: E402
import shards as _shards_mod  # noqa: E402
from skillgen import LOOP_SKILLS, LOOP_SKILL_WHEN, command_to_skill_text  # noqa: E402,F401

SECRET_PATTERNS = _hooks_mod.SECRET_PATTERNS
URL_PASSWORD = _hooks_mod.URL_PASSWORD
URL_PASSWORD_PLACEHOLDER = _hooks_mod.URL_PASSWORD_PLACEHOLDER
EXAMPLE_HOST = _hooks_mod.EXAMPLE_HOST
EMAIL = _hooks_mod.EMAIL
CARD_SHAPE = _hooks_mod.CARD_SHAPE
NATIONAL_ID_SHAPE = _hooks_mod.NATIONAL_ID_SHAPE
PLACEHOLDER = re.compile(r"[{][{][A-Z][A-Z0-9_]*[}][}]")
UNFILLED = re.compile(r"_\([^)]*\)_")

AGENT_SESSION_ENVS = (
    "CLAUDECODE",
    "CLAUDE_PROJECT_DIR",
    "GEMINI_CLI",
    "GEMINI_PROJECT_DIR",
    "CURSOR_PROJECT_DIR",
    "CODEX_SANDBOX",
    "ANTIGRAVITY_AGENT",
    "NUHUT_DISPATCH_WORKER",
)


def _run_isolated(cmd_or_args, cwd, timeout, shell=False, input_text=None, stdout=None, stderr=None, env=None):
    """Run a child command in its own POSIX process group so timeouts kill grandchildren too."""
    kwargs = dict(
        cwd=cwd,
        shell=shell,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE if stdout is None else stdout,
        stderr=subprocess.PIPE if stderr is None else stderr,
    )
    if env is not None:
        kwargs["env"] = env
    if os.name == "posix":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd_or_args, **kwargs)
    try:
        in_bytes = input_text.encode("utf-8") if isinstance(input_text, str) else input_text
        out_b, err_b = proc.communicate(input=in_bytes, timeout=timeout)
        return proc.returncode, out_b or b"", err_b or b"", False
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        return None, b"", b"", True


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
        is_absent = bool(re.match(r"^absent(?:\s*$|\s+[-—:]|\s*[:(\[])", cell.strip(), re.I))
        commands[match.group(1)] = "absent" if is_absent else cell
    return commands


def choice(cell, options):
    """(value, state): state is 'decided', 'undecided' (every option still listed, so
    the documented default applies), 'blank', or 'invalid'."""
    if cell is None:
        return None, "blank"
    found = [option for option in options
             if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(option),
                          UNFILLED.sub("", cell))]
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


def id_ranges(text, prefix):
    """IDs a range names: ACME-4..7 or ACME-4–7 (en dash, no spaces, either end may repeat
    the prefix) or ACME-4 to ACME-7, so one commit or entry that closes several items counts
    for each. The em dash is the worklog's title separator, never a range. Zero padding
    follows the first ID; spans over 100 are taken as a typo and ignored."""
    if not prefix:
        return set()
    found = set()
    p = re.escape(prefix)
    pattern = (r"\b%s-([0-9]+)(?:(?:\.\.|–)(?:%s-)?([0-9]+)|\s+to\s+%s-([0-9]+))\b"
               % (p, p, p))
    for a, b, c in re.findall(pattern, text or ""):
        lo, hi = int(a), int(b or c)
        width = len(a) if a.startswith("0") else 0
        if lo < hi <= lo + 100:
            found.update("%s-%0*d" % (prefix, width, n) for n in range(lo, hi + 1))
    return found


def ids_in(text, prefix, extra_ids=None):
    patterns = []
    if prefix:
        patterns.append(r"\b%s-[0-9]+\b" % re.escape(prefix))
    if extra_ids:
        patterns.append(r"\b(?:" + "|".join(re.escape(i) for i in sorted(extra_ids, key=len, reverse=True)) + r")\b")
    if not patterns:
        return set()
    found = set(re.findall(r"|".join(patterns), text)) | id_ranges(text, prefix)
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
        self.root = os.path.realpath(root)
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
        self._build_cache = None

    def path(self, rel):
        return os.path.join(self.root, rel)

    def json(self, rel):
        try:
            data = json.loads(read(self.path(rel)) or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def records(self, name):
        raw = read(self.path(os.path.join(self.docs, "project", name)))
        if name == "backlog.md":
            return _shards_mod.overlay_backlog(self, raw)
        return raw

    def worklog_texts(self):
        texts = [body for _, _, body in _shards_mod.load_worklog_shards(self)]
        texts.append(self.records("worklog.md"))
        archive = self.path(os.path.join(self.docs, "project", "worklog-archive"))
        if os.path.isdir(archive):
            for name in sorted(os.listdir(archive)):
                if name.endswith(".md"):
                    texts.append(read(os.path.join(archive, name)))
        return "\n".join(texts)

    def git(self, *args):
        try:
            # quotePath=false: non-ASCII names come back as text, not "caf\303\251.py".
            proc = subprocess.run(("git", "-c", "core.quotePath=false") + args, cwd=self.root,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, universal_newlines=True)
        except OSError:
            return ""
        return proc.stdout if proc.returncode == 0 else ""


# ---------------------------------------------------------------- doctor

# What to do about a finding, and who can do it: `tool` (a runtime command repairs it),
# `agent` (the agent edits a record) or `owner` (a human decides). Matched in order on
# (check, message); {item} is the work item ID at the end of `where`, {where} the place.
SDLC = "python3 .ai-sdlc/bin/sdlc.py"
FIX_HINTS = (
    ("substitution", r"", "tool", "Re-run install.sh <this project> --upgrade, or replace the "
     "placeholder with the project's value by hand"),
    ("contract", r"", "tool", SDLC + " fix wire-pointer"),
    ("charter", r"charter is missing", "tool", "Re-run install.sh <this project> --upgrade; it "
     "recreates the charter without touching other records"),
    ("charter", r"^blank, so Unknown", "agent", "Write each blank command in the charter's "
     "Commands table, or 'absent' where the stage does not exist: " + SDLC +
     " config --set STAGE=COMMAND"),
    ("charter", r"^blank$", "owner", "Fill the row in {where}"),
    ("charter", r"legacy row", "owner", "Decide what Operating mode meant here, then replace the "
     "row with Default effort mode"),
    ("charter", r"row missing", "tool", "install.sh <this project> --upgrade reinserts the row"),
    ("charter", r"undecided", "owner", "Pick one value in {where} (or " + SDLC + " config)"),
    ("charter", r"must be exactly one of", "agent", "Set the row in {where} to exactly one of "
     "the listed values"),
    ("charter", r"", "agent", "Record what the message names in {where}"),
    ("roles", r"", "owner", "Tick each role in the charter's Active roles, or write why it does "
     "not apply"),
    ("stack", r"support ended", "owner", "Open a backlog item to upgrade off the unsupported "
     "version"),
    ("stack", r"", "agent", "Re-read the versions from their registry or vendor page and set "
     "**Verified on:** to today in the ADR's Version facts"),
    ("staleness", r"", "agent", "Check the document against how things are now, correct what "
     "changed, and set last-reviewed to today"),
    ("traceability", r"no work item prefix", "owner", "Set the work item prefix in the charter"),
    ("traceability", r"Done with no worklog entry", "agent", "Record the work: " + SDLC +
     " finish {item} drafts the entry from its commits and the ledger; fill its TODO(finish) "
     "parts. If nothing was built, set the row to Dropped"),
    ("traceability", r"Parked with no one", "owner", "Name the person {item} waits on in "
     "'Waiting on whom'"),
    ("traceability", r"in the worklog but not in the backlog", "agent", "Add a backlog row for "
     "{item} with its tier and status, or correct the ID in the worklog"),
    ("traceability", r"recent commit or branch", "agent", "Add a backlog row for the ID (a "
     "retroactive ID, CARD.md), or fix the commit's Work-Item trailer"),
    ("backlog", r"", "owner", "Decide: finish it, park it with a named human, return it to "
     "Ready, defer it or drop it, and update {where}"),
    ("lessons", r"", "agent", "Turn the recurring lessons into checks or hooks and remove them "
     "from AGENTS.md section 9"),
    ("rollback", r"", "owner", "Rehearse the rollback and record its Last executed date"),
    ("sensitive", r"credential", "owner", "Rotate the credential first, then remove the line; "
     "deleting it alone does not undo the leak"),
    ("sensitive", r"", "agent", "Replace the personal detail with a role (\"the owner\", "
     "\"a client\")"),
    ("worklog", r"", "tool", SDLC + " fix rotate-worklog --apply (preview without --apply)"),
    ("profile", r"kit_version", "tool", "Finish the upgrade: install.sh <this project> --upgrade"),
    ("profile", r"", "tool", SDLC + " fix sync-profile"),
    ("epics", r"an epic with no", "agent", "Create the epic file from templates/epic.md"),
    ("epics", r"", "agent", "Correct the Epic cell of {item}, or add the epic's row"),
    ("dependencies", r"", "agent", "Correct the Depends on cell of {item}"),
    ("hooks", r"", "owner", "Install jq, or remove the hooks"),
    ("bite", r"", "tool", SDLC + " bite --restore"),
    ("escalation", r"", "owner", "Decide the finding, write the decision and your name in the "
     "review's Responses row; the agent then applies it"),
    ("contest", r"", "agent", "Cite a file:line or a recorded decision the reviewer could read, "
     "or change the response to Fix or Escalate"),
    ("independence", r"", "tool", SDLC + " review {item} --role <role> --by <other harness>"),
    ("evidence", r"", "agent", "Run " + SDLC + " verify --item {item} and cite the run. Runs "
     "kept on disk but missing from the ledger: " + SDLC + " fix link-evidence. For past work "
     "that cannot be re-run, change the worklog's Verified line to 'Not run: <reason>', or "
     "accept the history once with doctor --baseline"),
    ("claims", r"still claimed", "tool", SDLC + " unclaim {item}"),
    ("claims", r"", "owner", "Decide which agent keeps {item}; the other unclaims it"),
    ("specs", r"not applied", "tool", SDLC + " spec apply {item} --write"),
    ("harnesses", r"git-ignored", "owner", "Remove {where} from .gitignore or your global "
     "gitignore so commands and skills travel to other devices on git pull"),
    ("harnesses", r"", "tool", SDLC + " fix shared-skills"),
    ("hotfix", r"", "agent", SDLC + " review {item} --role <role> --by <harness> --stage retro"),
    ("postmortem", r"not a work item", "agent", "Add the follow-up with " + SDLC + " item add, "
     "or correct the ID in {where}"),
    ("postmortem", r"", "agent", "Name each follow-up item ID and the test that reproduces the "
     "failure in {where}"),
)


def fix_hint(check, where, message):
    """(fix, who) for a finding, from FIX_HINTS; ("", "") when none applies."""
    found = re.search(r"([A-Za-z][A-Za-z0-9]*-[0-9]+)\s*$", where or "")
    for name, pattern, who, fix in FIX_HINTS:
        if name == check and re.search(pattern, message or ""):
            return fix.replace("{item}", found.group(1) if found else "the item") \
                      .replace("{where}", where or "the record"), who
    return "", ""


class Findings(object):
    def __init__(self):
        self.items = []

    def add(self, level, check, where, message, fix=None, who=None):
        hint, hint_who = fix_hint(check, where, message)
        self.items.append({"level": level, "check": check, "where": where,
                           "message": message, "fix": fix or hint,
                           "who": who or hint_who})


def check_placeholders(project, out):
    # Only what the kit installs: .claude/ also holds worktrees and caches that can be
    # gigabytes of somebody else's files.
    for base in (project.docs, "AGENTS.md", ".claude/commands", ".claude/skills",
                 ".claude/hooks", ".claude/settings.json", ".agents/skills"):
        top = project.path(base)
        paths = [top] if os.path.isfile(top) else []
        for folder, dirs, names in os.walk(top):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "worktrees")]
            paths.extend(os.path.join(folder, name) for name in sorted(names))
        for path in paths:
            # The worklog is narrative and quotes placeholders when it describes kit work.
            if (os.path.basename(path) == "worklog.md" or "worklog-archive" in path
                    or (os.sep + "worklog" + os.sep) in path):
                continue
            if not path.endswith((".md", ".sh", ".json", ".js", ".html", ".mdc", ".txt")):
                continue
            for number, line in enumerate(read(path).splitlines(), 1):
                for token in PLACEHOLDER.findall(line):
                    out.add("fail", "substitution",
                            "%s:%d" % (os.path.relpath(path, project.root), number),
                            "unsubstituted %s: the install is broken here" % token)


def check_pointer(project, out):
    candidates = list(pointer_files(project))
    rules = project.path(".cursor/rules")
    if os.path.isdir(rules):
        candidates += [os.path.join(".cursor/rules", name) for name in sorted(os.listdir(rules))
                       if name.endswith(".mdc")
                       and os.path.join(".cursor/rules", name) not in candidates]
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


def check_harness_parity(project, out):
    """Warn when .agents/skills/ is missing loop skills or kit skills for a project that
    wired non-Claude harnesses, or when .claude/commands, .claude/skills or .agents/skills
    is git-ignored in a repository where AGENTS.md is tracked."""
    non_claude_pointers = [rel for rel in pointer_files(project) if rel != "CLAUDE.md"
                           and not rel.startswith(".cursor/rules/")
                           and os.path.isfile(project.path(rel))
                           and "AGENTS.md" in read(project.path(rel))]
    rules_dir = project.path(".cursor/rules")
    if os.path.isdir(rules_dir):
        for name in sorted(os.listdir(rules_dir)):
            if name.endswith(".mdc") and "AGENTS.md" in read(os.path.join(rules_dir, name)):
                non_claude_pointers.append(os.path.join(".cursor/rules", name))
    shared_dir = project.path(".agents/skills")
    cmds_dir = project.path(".claude/commands")
    has_commands = os.path.isdir(cmds_dir) and any(
        os.path.isfile(os.path.join(cmds_dir, n + ".md")) for n in LOOP_SKILLS
    )
    if (os.path.isdir(shared_dir) or non_claude_pointers) and has_commands:
        missing_loop = [n for n in LOOP_SKILLS
                        if os.path.isfile(os.path.join(cmds_dir, n + ".md"))
                        and not os.path.isfile(os.path.join(shared_dir, n, "SKILL.md"))]
        if missing_loop:
            out.add("warn", "harnesses", ".agents/skills",
                    "missing loop skill(s) for non-Claude tools: %s" % ", ".join(missing_loop))
        claude_skills = project.path(".claude/skills")
        if os.path.isdir(claude_skills):
            missing_kit = [n for n in sorted(os.listdir(claude_skills))
                           if n.startswith("sdlc-")
                           and os.path.isfile(os.path.join(claude_skills, n, "SKILL.md"))
                           and not os.path.isfile(os.path.join(shared_dir, n, "SKILL.md"))]
            if missing_kit:
                out.add("warn", "harnesses", ".agents/skills",
                        "kit skill(s) in .claude/skills/ not mirrored to .agents/skills/: %s"
                        % ", ".join(missing_kit))

    if os.path.exists(project.path(".git")) and project.git("ls-files", "--error-unmatch", "AGENTS.md"):
        check_paths = [rel for rel in (".claude/commands", ".claude/skills", ".agents/skills")
                       if os.path.isdir(project.path(rel))]
        if check_paths:
            try:
                proc = subprocess.run(("git", "check-ignore") + tuple(check_paths),
                                      cwd=project.root, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, universal_newlines=True)
                ignored = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            except OSError:
                ignored = []
            for rel in ignored:
                if not project.git("ls-files", rel).strip():
                    out.add("warn", "harnesses", rel,
                            "%s is git-ignored while AGENTS.md is tracked, so /sdlc-* commands "
                            "and skills will be missing on other devices after git pull" % rel)


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
    cell = labelled(text, "Discovered defects")
    if cell is not None and choice(cell, DISCOVERED_DEFECTS)[1] == "invalid":
        out.add("fail", "charter", "%s Discovered defects" % where,
                "must be exactly one of %s" % ", ".join(DISCOVERED_DEFECTS))
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


def tier_of(cell):
    """'1', '2' or '3' from a Tier cell ("1", "**Tier 2**", "3 (auto)"); '' when unreadable."""
    found = re.search(r"[123]", re.sub(r"_\([^)]*\)_", "", cell or ""))
    return found.group(0) if found else ""


def status_column(status):
    """The board column a backlog status belongs to, read the way the viewer reads it, so
    "Done on epic branch" or "Completed" is Done for doctor too."""
    try:
        return runtime_module("view").column_of(status)
    except ImportError:
        return status if status in ("Done", "Parked", "Dropped") else "Other"


def required_steps(tier, rules, started, done):
    """Which lifecycle steps an item owes, from its tier, whether work has started or is
    Done, and the charter's Tier rules (AGENTS.md section 2, CARD.md). The one table doctor
    and the viewer both read, so they never disagree. An unreadable tier counts as Tier 2.
    Tier 3: the commit is the record, plus a worklog line under Strict."""
    tier = tier if tier in ("1", "2", "3") else "2"
    return {
        "Frame": True,
        "Plan": tier == "1" and started,
        "Design review": tier == "1" and started,
        "Build": done,
        "Verify": done and tier != "3",
        "Ship review": tier == "1" and done,
        "Log": done and (tier != "3" or rules == "Strict"),
        "Close": False,
    }


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
    rules = tier_rules(project)
    for item, status, cells in rows:
        owes_log = required_steps(tier_of(cells[2]), rules, True, True)["Log"]
        if status_column(status) == "Done" and owes_log and item not in logged:
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

    for item_id, sh in _shards_mod.load_items(project).items():
        dt = sh.get("updated") or sh.get("created") or ""
        if dt:
            touch(item_id, dt)
            since.setdefault((item_id, sh.get("status", "")), dt)

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


redact = _hooks_mod.redact
sensitive_kinds = _hooks_mod.sensitive_kinds


def check_sensitive(project, out):
    """Credentials and personal data already written into the project's records. The
    records are committed, so a value here is a leak whether or not anything has pushed
    it yet (process/12-sensitive-data-in-records.md). Reports kind and place, never the
    value: a finding that quoted it would be a second copy."""
    top = project.path(os.path.join(project.docs, "project"))
    # Values the owner marked safe in the charter (their own work address, a company
    # phone) are not personal-data findings. Credentials are never allowlisted.
    allowed = re.findall(r"`([^`]+)`", UNFILLED.sub("", labelled(project.charter,
                                                                 "Allowed in records") or ""))
    for folder, dirs, names in os.walk(top):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
        for name in sorted(names):
            if not name.endswith((".md", ".txt", ".json", ".jsonl", ".csv")):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, project.root)
            for number, line in enumerate(read(path).splitlines(), 1):
                secrets, personal = sensitive_kinds(line)
                if personal and allowed:
                    for value in allowed:
                        line = line.replace(value, "")
                    personal = sensitive_kinds(line)[1]
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
    """Check that installed hooks have their runtime engine (or legacy jq when un-upgraded)."""
    hooks = project.path(os.path.join(".claude", "hooks"))
    if not os.path.isdir(hooks) or not any(n.endswith(".sh") for n in os.listdir(hooks)):
        return
    lib_text = read(os.path.join(hooks, "lib.sh"))
    if "command -v jq" in lib_text and shutil.which("jq") is None:
        out.add("warn", "hooks", ".claude/hooks",
                "legacy shell hooks installed without jq on PATH; run install.py --upgrade to switch to stdlib hooks.py")
    elif "hooks.py" in lib_text and not os.path.isfile(project.path(".ai-sdlc/bin/hooks.py")):
        out.add("fail", "hooks", ".ai-sdlc/bin/hooks.py",
                "hooks delegate to .ai-sdlc/bin/hooks.py, which is missing; run install.py --upgrade")


def check_bite_leftover(project, out):
    if os.path.exists(project.path(os.path.join(BITE_DIR, "active.json"))):
        out.add("fail", "bite", BITE_DIR,
                "an interrupted `sdlc.py bite` left product files reverted; run "
                "`sdlc.py bite --restore`")


DOCTOR_CACHE_VERSION = 5


def _doctor_input_digest(project, today):
    """Content-addressed SHA-256 over every file and git ref doctor inspects."""
    h = hashlib.sha256()
    h.update(("v%d|%s|%s\0" % (
        DOCTOR_CACHE_VERSION, today.isoformat(), bool(shutil.which("jq"))
    )).encode("utf-8"))
    h.update((project.charter or "").encode("utf-8", "replace") + b"\0")
    h.update(json.dumps(project.profile or {}, sort_keys=True).encode("utf-8") + b"\0")
    h.update(json.dumps(project.manifest or {}, sort_keys=True).encode("utf-8") + b"\0")

    head_refs = project.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/remotes", "refs/nuhut")
    head_sha = project.git("rev-parse", "HEAD").strip()
    h.update(("HEAD:%s\n%s\0" % (head_sha, head_refs)).encode("utf-8"))

    single_files = [
        "AGENTS.md", ".gitignore", ".git/info/exclude",
        ".ai-sdlc/profile.json", ".ai-sdlc/manifest.json",
        ".ai-sdlc/bite/active.json", ".ai-sdlc/bin/hooks.py", ".ai-sdlc/bin/registry.py",
        ".claude/settings.json",
    ] + list(pointer_files(project))
    for rel in single_files:
        p = project.path(rel)
        if os.path.isfile(p):
            h.update(("F:" + rel + "\0").encode("utf-8"))
            try:
                with open(p, "rb") as fh:
                    h.update(hashlib.sha256(fh.read()).digest())
            except OSError:
                h.update(b"err")
        else:
            h.update(("M:" + rel + "\0").encode("utf-8"))

    scan_dirs = [
        project.docs, ".cursor/rules", ".claude/hooks",
        ".claude/commands", ".claude/skills", ".agents/skills",
        ".ai-sdlc/extensions", ".ai-sdlc/local/extensions",
    ]
    for rel_dir in scan_dirs:
        top = project.path(rel_dir)
        if not os.path.isdir(top):
            h.update(("MD:" + rel_dir + "\0").encode("utf-8"))
            continue
        for folder, dirs, names in os.walk(top):
            dirs[:] = sorted(d for d in dirs if d not in ("node_modules", ".git", "worktrees"))
            for name in sorted(names):
                full = os.path.join(folder, name)
                rpath = os.path.relpath(full, project.root)
                h.update(("D:" + rpath + "\0").encode("utf-8"))
                try:
                    with open(full, "rb") as fh:
                        h.update(hashlib.sha256(fh.read()).digest())
                except OSError:
                    h.update(b"err")

    try:
        reg_dir = runtime_module("claims").registry(project)
    except Exception:
        reg_dir = ""
    if reg_dir and os.path.isdir(reg_dir):
        for name in sorted(os.listdir(reg_dir)):
            if name.endswith(".json"):
                full = os.path.join(reg_dir, name)
                h.update(("C:" + name + "\0").encode("utf-8"))
                try:
                    with open(full, "rb") as fh:
                        h.update(hashlib.sha256(fh.read()).digest())
                except OSError:
                    h.update(b"err")
    return h.hexdigest()


def doctor(project, today=None, use_cache=True):
    today = today or datetime.date.today()
    can_cache = bool(
        use_cache
        and getattr(project, "root", "")
        and os.path.isdir(project.path(".ai-sdlc"))
    )
    digest = ""
    cache_file = ""
    if can_cache:
        cache_dir = project.path(os.path.join(".ai-sdlc", "cache"))
        cache_file = os.path.join(cache_dir, "doctor.json")
        try:
            digest = _doctor_input_digest(project, today)
            if os.path.isfile(cache_file):
                with open(cache_file, encoding="utf-8") as ch:
                    cached = json.load(ch)
                if (isinstance(cached, dict)
                        and cached.get("version") == DOCTOR_CACHE_VERSION
                        and cached.get("digest") == digest
                        and isinstance(cached.get("raw_items"), list)):
                    return apply_baseline(project, [dict(x) for x in cached["raw_items"]])
        except Exception:
            digest = ""

    out = Findings()
    own_cache = getattr(project, "_build_cache", None) is None
    if own_cache:
        project._build_cache = {}
    try:
        check_bite_leftover(project, out)
        check_hook_dependency(project, out)
        check_identity(project, out)
        check_responses(project, out)
        check_verified_claims(project, out)
        check_attribution(project, out)
        check_people(project, out)
        check_placeholders(project, out)
        check_pointer(project, out)
        check_harness_parity(project, out)
        check_extensions(project, out)
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
        check_claims(project, out, today)
        check_specs(project, out, today)
        check_hotfix(project, out, today)
        check_postmortems(project, out)
        if can_cache and digest and cache_file:
            try:
                cache_dir = os.path.dirname(cache_file)
                os.makedirs(cache_dir, exist_ok=True)
                gi = os.path.join(cache_dir, ".gitignore")
                if not os.path.isfile(gi):
                    with open(gi, "w", encoding="utf-8") as gh:
                        gh.write("*\n")
                _shards_mod._atomic_write_text(
                    cache_file,
                    json.dumps({
                        "version": DOCTOR_CACHE_VERSION,
                        "digest": digest,
                        "raw_items": out.items,
                    }) + "\n",
                )
            except Exception:
                pass
        return apply_baseline(project, [dict(x) for x in out.items])
    finally:
        if own_cache:
            project._build_cache = None


BASELINE = os.path.join("project", "doctor-baseline.json")


def finding_key(item):
    """A finding's identity across runs: line numbers and counts in it change as the
    records grow, the finding does not."""
    where = re.sub(r":[0-9]+$", "", item["where"])
    return "|".join((item["check"], where, re.sub(r"[0-9]+", "#", item["message"])))


def acceptable(item):
    """A leaked credential is never accepted: it is rotated."""
    return not (item["check"] == "sensitive" and item["level"] == "fail")


def apply_baseline(project, items):
    """Mark the findings `doctor --baseline` accepted with "accepted": <date>. Each key is
    accepted as many times as it was recorded, so a second copy of an old problem shows."""
    data = project.json(os.path.join(project.docs, BASELINE))
    left = dict(data.get("accepted") or {})
    for item in items:
        key = finding_key(item)
        if left.get(key, 0) > 0 and acceptable(item):
            left[key] -= 1
            item["accepted"] = data.get("date", "")
    return items


def write_baseline(project, items, today=None):
    """Record today's findings as accepted. It is a ratchet: once the file exists, a
    rewrite only drops what is fixed and never adds a new finding. Returns (kept, dropped,
    refused): refused are findings that are new since the baseline."""
    rel = os.path.join(project.docs, BASELINE)
    old = project.json(rel)
    current = {}
    for item in items:
        if acceptable(item):
            current[finding_key(item)] = current.get(finding_key(item), 0) + 1
    if old.get("accepted") is None:
        accepted, date = current, (today or datetime.date.today()).isoformat()
    else:
        accepted = dict((k, min(v, current.get(k, 0))) for k, v in old["accepted"].items()
                        if current.get(k))
        date = old.get("date", "")
    refused = sum(max(0, v - accepted.get(k, 0)) for k, v in current.items())
    dropped = sum((old.get("accepted") or {}).values()) - sum(accepted.values()) \
        if old.get("accepted") is not None else 0
    with open(project.path(rel), "w", encoding="utf-8") as handle:
        json.dump({"date": date, "note": "Findings accepted by `sdlc.py doctor --baseline`. "
                   "doctor hides them and shows how many; a rewrite only removes fixed ones. "
                   "Delete this file to start again.", "accepted": accepted},
                  handle, indent=2, sort_keys=True)
        handle.write("\n")
    return sum(accepted.values()), dropped, refused


def merge_driver_command():
    """The driver line for this checkout: absolute interpreter and script, so a merge run
    from any shell or GUI client finds the same Python and the same runtime."""
    py = os.path.abspath(sys.executable or "python3")
    script = os.path.realpath(os.path.abspath(__file__))
    return "%s %s merge-shard %%O %%A %%B --marker-size %%L" % (shlex.quote(py), shlex.quote(script))


def fix_merge_driver(project, as_json=False):
    """Set merge.nuhut-shard.driver in this clone's local git config. The line is printed
    before it is written, so the person sees exactly what git will run on a merge."""
    driver = merge_driver_command()
    name = _shards_mod.MERGE_DRIVER_NAME
    label = "Nuhut item shard merge"
    shown = ["git config merge.%s.name %s" % (name, shlex.quote(label)),
             "git config merge.%s.driver %s" % (name, shlex.quote(driver))]
    if not as_json:
        print("fix merge-driver: setting the local git config in %s" % project.root)
        for line in shown:
            print("  " + line)
        sys.stdout.flush()
    failed = []
    for key, value in (("merge.%s.name" % name, label), ("merge.%s.driver" % name, driver)):
        try:
            proc = subprocess.run(["git", "config", "--local", key, value], cwd=project.root,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True)
            if proc.returncode != 0:
                failed.append("%s: %s" % (key, proc.stderr.strip() or "git config failed"))
        except OSError as exc:
            failed.append("%s: %s" % (key, exc))
    attrs = read(project.path(".gitattributes"))
    pattern = "%s/project/items/*.json merge=%s" % (project.docs, name)
    if as_json:
        print(json.dumps({"action": "merge-driver", "commands": shown, "driver": driver,
                          "errors": failed, "gitattributes": pattern in attrs}, indent=2))
    elif failed:
        for line in failed:
            sys.stderr.write("fix merge-driver: %s\n" % line)
    else:
        print("fixed: merge.%s.driver set in .git/config (this clone only)" % name)
        if pattern not in attrs:
            print("note: .gitattributes has no '%s' line; add it (install.py --upgrade "
                  "writes it) or git never calls the driver" % pattern)
    return 1 if failed else 0


def runtime_module(name):
    """A sibling module of this file (view, lens, claims), imported on demand."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    sys.dont_write_bytecode = True
    return __import__(name)


def check_claims(project, out, today):
    """Stale claims, claims on finished items, and two branches for one claimed item."""
    try:
        claims_mod, view_mod = runtime_module("claims"), runtime_module("view")
    except ImportError:
        return
    cell = labelled(project.charter, "Staleness threshold") or ""
    found = re.search(r"[0-9]+", UNFILLED.sub("", cell))
    claims_mod.check(project, out, view_mod, int(found.group(0)) if found else DEFAULT_STALENESS_DAYS, today)


def check_specs(project, out, today):
    """Only when the charter's Specs row is on: spec validation, and Done items whose spec
    change was never applied."""
    try:
        specs_mod, claims_mod, view_mod = runtime_module("specs"), runtime_module("claims"), runtime_module("view")
    except ImportError:
        return
    done = set(i for i, it in claims_mod.items(project, view_mod).items() if it["column"] == "Done")
    specs_mod.check(project, out, labelled, done, today)


def print_findings(items, show_accepted=False):
    accepted = [item for item in items if item.get("accepted")]
    if not show_accepted:
        items = [item for item in items if not item.get("accepted")]
    if accepted and not show_accepted:
        print("doctor: %d finding(s) accepted on %s (doctor-baseline.json); "
              "doctor --all shows them" % (len(accepted), accepted[0]["accepted"]))
    if not items:
        print("doctor: no mechanical findings. The judgment checks in /sdlc-doctor still "
              "apply.")
        return
    width = max(len(item["where"]) for item in items)
    for item in items:
        print("%-4s  %-12s  %-*s  %s" % (item["level"], item["check"], width, item["where"],
                                          item["message"]))
        if item.get("fix"):
            print("%-4s  %-12s  %-*s  fix (%s): %s" % ("", "", width, "", item.get("who") or "agent",
                                                      item["fix"]))
    fails = sum(1 for item in items if item["level"] == "fail")
    infos = sum(1 for item in items if item["level"] == "info")
    print("\n%d finding(s): %d fail, %d warn%s" % (len(items), fails, len(items) - fails - infos,
                                                  ", %d info" % infos if infos else ""))


# ---------------------------------------------------------------- verify

def evidence_dir(project, suffix=""):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parent = project.path(os.path.join(".ai-sdlc", "evidence"))
    os.makedirs(parent, exist_ok=True)
    base = os.path.join(parent, stamp + suffix)
    path, n = base, 1
    while True:
        try:
            os.makedirs(path, exist_ok=False)
            break
        except FileExistsError:
            n += 1
            path = "%s-%d" % (base, n)
    ignore = os.path.join(parent, ".gitignore")
    if not os.path.exists(ignore):
        # Evidence is local proof for the session that ran it, not a project record.
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n!.gitignore\n")
    return path


def verify(project, selected, timeout, parallel=False, item=None):
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
    dirty = tree_dirty(project)

    def run_stage(stage, command):
        log = os.path.join(folder, stage + ".log")
        started = time.time()
        with open(log, "wb") as handle:
            code, _, _, timed_out = _run_isolated(
                command, cwd=project.root, timeout=timeout, shell=True,
                stdout=handle, stderr=subprocess.STDOUT,
            )
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
    passed = not any(e["result"].startswith("Verified: fail") for e in results)
    summary = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": project.root, "git_head": head, "dirty": dirty,
        "charter": project.charter_path, "drift": drift,
        "run": os.path.basename(folder),
        "evidence_dir": os.path.relpath(folder, project.root),
        "passed": passed,
        "stages": results,
    }
    if item:
        summary["item"] = item
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    ledger_append(project, [{
        "time": summary["generated"], "commit": head, "dirty": dirty, "stage": e["stage"],
        "command": e["command"], "exit_code": e.get("exit_code"), "result": e["result"],
        "output_sha256": e.get("log_sha256", ""), "run": os.path.basename(folder),
        **({"item": item} if item else {}),
        **({"selected": sorted(selected)} if selected else {})}
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


IDENTITY_TRAILERS = ("Work-Item", "Agent", "Model")


def trailers(message):
    """{key: value} from the trailer block: the last paragraph of a commit message. When
    that paragraph names none of Work-Item, Agent and Model (a harness often appends
    `Co-Authored-By:` as a paragraph of its own after `Work-Item:`), the paragraphs just
    before it that hold nothing but trailer lines count too. A body paragraph that only
    looks like trailers never adds to a last paragraph that already has them."""
    paragraphs = [p for p in re.split(r"\n\s*\n", message.strip()) if p.strip()]
    found = {}
    if len(paragraphs) < 2:
        return found
    blocks = [paragraphs[-1]]
    last_keys = set(m.group(1) for m in (TRAILER.match(line.strip())
                                         for line in paragraphs[-1].splitlines()) if m)
    earlier = [] if last_keys & set(IDENTITY_TRAILERS) else paragraphs[1:-1]
    for para in reversed(earlier):
        lines = [line for line in para.splitlines() if line.strip()]
        if not lines or not all(TRAILER.match(line.strip()) for line in lines):
            break
        blocks.insert(0, para)
    for block in blocks:
        for line in block.splitlines():
            m = TRAILER.match(line.strip())
            if m:
                found[m.group(1)] = m.group(2)
    return found


# Each harness fills Agent and Model differently; `sdlc.py trailers` reads what the
# environment gives and the agent supplies the rest (process/05-change-control.md). The
# variables each tool sets are in its agents record (`identity`).
def identity(agent=None, model=None, project=None):
    agent_env, model_env = identity_env(project)
    if not agent:
        agent = os.environ.get("AI_SDLC_AGENT", "")
    if not agent:
        agent = next((name for var, name in agent_env if os.environ.get(var)), "unknown")
    if not model:
        model = next((os.environ[var] for var in model_env if os.environ.get(var)), "unknown")
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


def _parsed_commits(project):
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "commits" in cache:
        return cache["commits"]
    out = project.git("log", "--all", "--format=%H%x01%P%x01%B%x00")
    records = []
    for record in out.split("\x00"):
        parts = record.strip("\n").split("\x01")
        if len(parts) < 3 or not parts[0].strip():
            continue
        sha = parts[0].strip()
        parent = (parts[1].split() or [""])[0]
        body = parts[2]
        tags = trailers(body)
        records.append((sha, parent, body, tags))
    if cache is not None:
        cache["commits"] = records
    return records


def commit_index(project, known=None):
    """{item: [(sha, parent, trailers)]} for every commit, from one `git log` -- the same
    matching as item_commits, for callers that need every item at once."""
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "commit_index" in cache:
        return cache["commit_index"]
    if known is None:
        known = getattr(project, "legacy_prefixes", None)
    # Only the Work-Item trailer attributes a commit. A message that merely mentions an
    # ID ("follows up ACME-12") is not that item's work. `known` stays for callers.
    index = {}
    for sha, parent, body, tags in _parsed_commits(project):
        if tags.get("Work-Item"):
            index.setdefault(tags["Work-Item"], []).append((sha, parent, tags))
    if cache is not None:
        cache["commit_index"] = index
    return index


def item_commits(project, item):
    """[(sha, parent, trailers)] for commits whose Work-Item trailer names <item>, newest
    first. A mention in the subject or body does not attribute a commit."""
    cache = getattr(project, "_build_cache", None)
    if cache is not None:
        return list(commit_index(project).get(item, ()))
    return [(sha, parent, tags) for sha, parent, body, tags in _parsed_commits(project)
            if tags.get("Work-Item") == item]


def mentioned_only(project):
    """Item IDs that commit messages mention but no Work-Item trailer names: work that
    lost its commit attribution when matching became trailer-only (6.0)."""
    if not project.prefix:
        return []
    named, mentioned = set(), set()
    shape = re.compile(r"(?i)^%s-([0-9]+)$" % re.escape(project.prefix))
    for _, _, body, tags in _parsed_commits(project):
        tag = tags.get("Work-Item")
        if tag:
            named.add(tag)
            m = shape.match(tag.strip())
            if m and tag.strip() != "%s-%s" % (project.prefix, m.group(1)):
                # `Work-Item: acme-1` attributes nothing: the match is exact-case.
                mentioned.add("%s-%s" % (project.prefix, m.group(1)))
        else:
            mentioned.update(ids_in(body, project.prefix))
    return sorted(mentioned - named, key=id_sort_key)


def records_path(project, path):
    """True for a path under <docs>/project/ (ledger, worklog, backlog, reviews) other
    than the charter, which holds the check commands."""
    records = project.docs.rstrip("/") + "/project/"
    return path.startswith(records) and path != project.charter_path.replace(os.sep, "/")


def tree_dirty(project):
    """True when the working tree has uncommitted changes the checks could see.
    Uncommitted records (ledger, worklog, backlog) and the kit's generated state
    (evidence, cache) do not count; the charter does, because it holds the commands."""
    counted = (".ai-sdlc/bin/", ".ai-sdlc/profile.json", ".ai-sdlc/manifest.json")
    for line in project.git("status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        if not path or records_path(project, path) or \
                (path.startswith(".ai-sdlc/") and not path.startswith(counted)):
            continue
        return True
    return False


def commit_paths(project, sha):
    """Paths a commit changes, against its first parent (a merge counts what it brought
    in to the branch it landed on)."""
    out = project.git("diff-tree", "--no-commit-id", "--name-only", "-r", "-m",
                      "--first-parent", "--root", sha)
    return [line.strip() for line in out.splitlines() if line.strip()]


def newest_code_commit(project, item, commits=None):
    """(sha, parent) of the item's newest commit that changes a path outside
    <docs>/project/** -- the commit a verify run must cover. Records-only commits
    (ledger, worklog, status) are skipped; when every commit is records-only, the newest
    commit is used. (None, None) when the item has no commits."""
    commits = item_commits(project, item) if commits is None else commits
    if not commits:
        return None, None
    for sha, parent, _ in commits:
        if any(not records_path(project, path) for path in commit_paths(project, sha)):
            return sha, parent
    return commits[0][0], commits[0][1]


def is_ancestor(project, older, newer):
    """True when <older> is <newer> or one of its ancestors. Fails closed."""
    if not older or not newer:
        return False
    if older == newer:
        return True
    if str(older).startswith("-") or str(newer).startswith("-"):
        return False
    try:
        proc = subprocess.run(("git", "merge-base", "--is-ancestor", older, newer),
                              cwd=project.root, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return proc.returncode == 0


# ---------------------------------------------------------------- trusted records

def trusted_ref(project):
    """The ref security-bearing records are read from, or None: registry.trusted_ref,
    which prefers origin/HEAD so that a branch cannot name itself the default branch."""
    try:
        return runtime_module("registry").trusted_ref(project.root, project.charter_path)
    except Exception:  # no registry: the same order, inline
        head = project.git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").strip()
        if head.startswith("refs/remotes/origin/"):
            return head
        branch = default_branch(project)
        if not branch or branch.startswith("-"):
            return None
        for ref in ("refs/remotes/origin/" + branch, "refs/heads/" + branch):
            if project.git("rev-parse", "--verify", "--quiet", ref + "^{commit}").strip():
                return ref
        return None


def show_at(project, ref, rel):
    """<rel>'s text at <ref>, or None when it is not there. `ref:./rel` resolves against
    the project root, which may be a subdirectory of the repository."""
    rel = rel.replace(os.sep, "/").lstrip("/")
    if not ref or not project.git("ls-tree", "--name-only", ref, "--", rel).strip():
        return None
    return project.git("show", "%s:./%s" % (ref, rel))


def trusted_text(project, rel, ref=None):
    """(text, source) for a security-bearing record (the charter's Approvers row,
    people.json, ...), read as it stands on the default branch so a branch that edits it
    has no effect until it merges. source names the ref. Falls back to the working tree,
    with source "working-tree", only when there is no git, no default-branch ref, or the
    file does not exist on that ref yet. ADR 0003 decision 8. <ref> (ci-check's
    --charter-ref) names the ref to read instead of the default branch."""
    rel = rel.replace(os.sep, "/")
    if ref is not None:
        ref = ref if ref and not str(ref).startswith("-") and \
            project.git("rev-parse", "--verify", "--quiet", ref + "^{commit}").strip() else None
        text = show_at(project, ref, rel)
        if text is not None:
            return text, ref
        return read(project.path(rel)), "working-tree"
    ref = trusted_ref(project)
    text = show_at(project, ref, rel)
    if text is not None:
        source = ref[len("refs/remotes/"):] if ref.startswith("refs/remotes/") else \
            ref[len("refs/heads/"):]
        return text, source
    return read(project.path(rel)), "working-tree"


def person_key(name):
    """A name as compared: no `@`, backticks or surrounding space, lowercase."""
    return re.sub(r"[`@]", "", str(name or "")).strip().lower()


PEOPLE_REL = os.path.join("project", "people.json")


def people_entries(project):
    """{handle: {"handle", "name", "roles", "github", ...}} from <docs>/project/people.json
    (NUHT-023), read from the default branch (`trusted_text`). {} when there is no
    registry or it lists nobody. Accepts {"people": [...]}, a bare list, or
    {handle: {...}}."""
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "people" in cache:
        return cache["people"]
    text, _ = trusted_text(project, os.path.join(project.docs, PEOPLE_REL))
    try:
        data = json.loads(text) if (text or "").strip() else None
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("people"), list):
        data = data["people"]
    if isinstance(data, dict):
        data = [dict(v, handle=k) if isinstance(v, dict) else {"handle": k}
                for k, v in data.items() if k not in ("note", "people")]
    found = {}
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict) or not person_key(entry.get("handle")):
            continue
        roles_v = entry.get("roles")
        found[person_key(entry["handle"])] = dict(
            entry, handle=person_key(entry["handle"]), name=str(entry.get("name") or ""),
            roles=[str(r) for r in roles_v] if isinstance(roles_v, list) else [],
            github=person_key(entry.get("github")))
    if cache is not None:
        cache["people"] = found
    return found


def people(project):
    """{handle: set of lowercase names it answers to}: the handle, name, github login and
    any aliases, git_names, emails or names. {} when there is no registry."""
    found = {}
    for handle, entry in people_entries(project).items():
        names = set([handle])
        for key in ("name", "git_name", "email", "github"):
            if entry.get(key):
                names.add(person_key(entry[key]))
        for key in ("aliases", "git_names", "emails", "names"):
            if isinstance(entry.get(key), list):
                names.update(person_key(v) for v in entry[key] if v)
        found[handle] = names
    return found


def handle_for_github(project, login):
    """The people.json handle whose `github` field is <login> (case and a leading @
    ignored), or None. Only the github field counts: a display name is not a login."""
    key = person_key(login)
    if not key:
        return None
    for handle, entry in people_entries(project).items():
        if entry.get("github") == key:
            return handle
    return None


def role_slugs(project):
    """Role slugs an Owner cell may hold: the role playbooks, the charter's Active roles,
    and software-engineer (the default owner, which has no playbook)."""
    slugs = set(["software-engineer"])
    folder = project.path(os.path.join(project.docs, "roles"))
    try:
        slugs.update(n[:-3] for n in os.listdir(folder) if n.endswith(".md") and n != "README.md")
    except OSError:
        pass
    slugs.update(name for name, _, _ in roles(project.charter or ""))
    return slugs


def resolve_owner(project, value):
    """(owner to store, error). A role slug stays as written; with a people.json registry
    a person is stored as their handle and anything else is refused. Without a registry
    the value is kept: there is nothing to check it against."""
    value = (value or "").strip()
    if not value or value in role_slugs(project):
        return value, None
    registry = people(project)
    if not registry:
        return value, None
    handle = resolve_person(registry, value)
    if handle:
        return handle, None
    return None, ("%r is neither a role nor a handle in %s/%s; use a role slug (e.g. "
                  "software-engineer) or add the person to people.json"
                  % (value, project.docs, PEOPLE_REL.replace(os.sep, "/")))


PERSON_WARNING = ("no person identity: set NUHUT_USER=<handle> or map git user.name in "
                  "%s")
_person_warned = []


def person_identity(project, read_only=False, warn=True):
    """{"person", "raw", "source", "warning"} for the human behind this command.
    NUHUT_USER is taken as written when there is no registry (it is a deliberate
    statement) and must resolve when there is one; git user.name counts only when
    people.json maps it. Anything else gives person None, never a guess. The warning goes
    to stderr at most once per process, and not at all under CI=true for a read-only
    command; warn=False leaves printing to the caller (a --json result)."""
    registry = people(project)
    raw = (os.environ.get("NUHUT_USER") or "").strip()
    source = "NUHUT_USER" if raw else ""
    if not raw:
        raw = project.git("config", "user.name").strip()
        source = "git user.name" if raw else ""
    person = None
    if raw and registry:
        person = resolve_person(registry, raw)
    elif raw and source == "NUHUT_USER":
        person = person_key(raw) or None
    warning = None if person else PERSON_WARNING % os.path.join(project.docs, PEOPLE_REL).replace(
        os.sep, "/")
    quiet = read_only and (os.environ.get("CI") or "").strip().lower() == "true"
    if warning and warn and not quiet and not _person_warned:
        _person_warned.append(True)
        sys.stderr.write("warning: %s\n" % warning)
    return {"person": person, "raw": raw, "source": source, "warning": warning}


def resolve_person(registry, name):
    """The people.json handle <name> answers to; without a registry, the name itself (as
    compared). None when a registry exists and does not know the name."""
    key = person_key(name)
    if not registry:
        return key or None
    for handle, names in registry.items():
        if key in names:
            return handle
    return None


def approver_names(project):
    """(names as written, source) from the charter's Approvers row on the default
    branch. A placeholder cell gives []."""
    text, source = trusted_text(project, project.charter_path)
    cell = labelled(text or "", "Approvers") or ""
    if unfilled(cell):
        return [], source
    cell = UNFILLED.sub("", cell)
    names = [re.sub(r"[`@*]", "", n).strip() for n in re.split(r",|;|\band\b", cell)]
    return [n for n in names if n], source


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
    `bite`). Sharded projects and linked worktrees write immutable per-run files under
    <docs>/project/ledger/<run>.jsonl; single-worktree 4.x projects append to
    evidence-ledger.jsonl."""
    if not entries:
        return
    if _shards_mod.is_sharded(project, for_write=True):
        _shards_mod.append_ledger_shards(project, entries)
        return
    path = ledger_path(project)
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        return
    with open(path, "a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


def ledger(project):
    rows = []
    seen = set()
    try:
        with open(ledger_path(project), encoding="utf-8") as handle:
            for line in handle:
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        k = _shards_mod.ledger_row_key(obj)
                        if k not in seen:
                            seen.add(k)
                            rows.append(obj)
                except ValueError:
                    continue
    except (IOError, OSError):
        pass
    for obj in _shards_mod.read_ledger_shards(project):
        k = _shards_mod.ledger_row_key(obj)
        if k not in seen:
            seen.add(k)
            rows.append(obj)
    return rows


def evidence_matches(project, item, rows=None, commits=None):
    """Ledger rows that verify <item> (the usual order is verify, then commit)."""
    rows = ledger(project) if rows is None else rows
    commits = item_commits(project, item) if commits is None else commits
    heads = set(sha for sha, _, _ in commits)
    parents = set(parent for _, parent, _ in commits if parent)
    ancestry = {}

    def descends(commit):
        # The answer depends on the commit graph only, never on HEAD or the clock, so
        # doctor and the viewer agree whenever they run. Freshness is finish's job.
        if commit not in ancestry:
            ancestry[commit] = any(is_ancestor(project, sha, commit) for sha in heads)
        return ancestry[commit]

    # A clean run on one of the item's commits, a run on the parent of one with the change
    # still uncommitted, or a clean run tagged with the item (verify --item) that has one
    # of the item's commits in its history. A dirty run on the item's own commit verified
    # whatever came next, not the item. A waiver (finish --waive) is a recorded Not run,
    # never evidence.
    return [row for row in rows if not row.get("waived_by") and (
        (row.get("commit") in heads and not row.get("dirty"))
        or (row.get("dirty") and row.get("commit") in parents)
        or (row.get("item") == item and not row.get("dirty")
            and str(row.get("result", "")).startswith("Verified")
            and descends(row.get("commit"))))]


# ---------------------------------------------------------------- extensions

def allowed_extensions(project):
    """The extension ids the charter's Extensions allowed row names, read from the
    default branch (a branch that adds an id has no effect until it merges)."""
    text, _ = trusted_text(project, project.charter_path)
    try:
        return runtime_module("registry").parse_allowed(labelled(text or "", "Extensions allowed"))
    except Exception:  # no registry: nothing is allowed
        return frozenset()


def notify_event(project, event, item="", title="", tier="", status=""):
    """Send one webhook event (NUHT-034) when the charter's Notify webhook row is on.
    Returns (state, message); never raises and never blocks the caller."""
    try:
        return runtime_module("notify").send(sys.modules[__name__], project, event, item,
                                             title, tier, status)
    except Exception as exc:  # noqa: BLE001 -- a missing notify.py is "off"
        return "off", exc.__class__.__name__


def notify_if_parked(project, before, saved):
    """The parked event, once, when <saved> is Parked and <before> was not."""
    if (saved or {}).get("status") == "Parked" and (before or {}).get("status") != "Parked":
        notify_event(project, "parked", saved.get("id", ""), saved.get("title", ""),
                     saved.get("tier", ""), "Parked")


def extension_lifecycle(project, event, *args):
    """[(extension id, message)] from the built-in and allowed extensions' <event> hooks;
    [] when the registry is missing."""
    reg, _ = load_registry(project)
    if reg is None:
        return []
    return runtime_module("registry").run_lifecycle(reg, event, *args)


def load_registry(project):
    """(registry, None), or (None, reason) when the v5 tables apply: no built-in
    extension directory exists, or registry.py cannot be imported."""
    try:
        reg_mod = runtime_module("registry")
    except Exception as exc:  # a broken or missing registry.py must not break the CLI
        return None, "registry.py cannot be imported (%s)" % exc.__class__.__name__
    try:
        reg = reg_mod.load(project.root, version=(project.manifest or {}).get("kit_version"),
                           allowed=allowed_extensions(project))
    except Exception as exc:
        return None, "the registry failed to load (%s)" % exc.__class__.__name__
    if reg.missing:
        return None, "no .ai-sdlc/extensions/ directory"
    return reg, None


# The v5 tables, one record per tool, for when the registry is missing (an install made
# before 6.0, or a registry.py that cannot be imported). The built-in extensions in
# .ai-sdlc/extensions/ are the source; tests/smoke.py checks that the two agree.
V5_AGENTS = {
    "claude": {"id": "claude", "family": "claude",
               "review": ["claude", "-p", "{prompt}", "--output-format", "text"],
               "build": ["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits",
                         "--output-format", "text"],
               "model_flag": "--model",
               "identity": {"agent": "claude-code", "env": ["CLAUDECODE"],
                            "model_env": ["ANTHROPIC_MODEL", "CLAUDE_CODE_MODEL"]}},
    "gemini": {"id": "gemini", "family": "gemini",
               "review": ["gemini", "-p", "{prompt}"],
               "build": ["gemini", "-p", "{prompt}", "-y"],
               "model_flag": "--model",
               "identity": {"agent": "gemini-cli", "env": ["GEMINI_CLI"],
                            "model_env": ["GEMINI_MODEL"]}},
    "codex": {"id": "codex", "family": "openai",
              "review": ["codex", "exec", "{prompt}"],
              "build": ["codex", "exec", "--full-auto", "{prompt}"],
              "model_flag": "--model",
              "identity": {"agent": "codex", "env": ["CODEX_SANDBOX", "CODEX_HOME"],
                           "model_env": ["OPENAI_MODEL", "CODEX_MODEL"]}},
    "cursor": {"id": "cursor", "family": "", "review": None, "build": None,
               "model_flag": None,
               "identity": {"agent": "cursor", "env": ["CURSOR_TRACE_ID", "CURSOR_AGENT"],
                            "model_env": []}},
}
V5_POINTER_FILES = ("CLAUDE.md", ".cursor/rules/agents.mdc", ".cursorrules",
                    ".github/copilot-instructions.md", "GEMINI.md", ".windsurfrules",
                    ".clinerules", ".roo/rules/agents.md", "AGENT.md", "CONVENTIONS.md")
# The --reviewer choices when even the fallback cannot be built.
STATIC_REVIEWERS = ("claude", "codex", "gemini")


def v5_agent_table(kind):
    """{id: (argv, model_flag)} for kind "review" or "build", from V5_AGENTS."""
    return dict((aid, (list(rec[kind]), rec.get("model_flag") or "--model"))
                for aid, rec in V5_AGENTS.items() if rec.get(kind))


def v5_identity_env():
    agent_env, model_env = [], ["AI_SDLC_MODEL"]
    for rec in V5_AGENTS.values():
        ident = rec.get("identity") or {}
        agent_env.extend((var, ident["agent"]) for var in ident.get("env") or ())
        model_env.extend(v for v in ident.get("model_env") or () if v not in model_env)
    return tuple(agent_env), tuple(model_env)


def _registry_or_none(project=None):
    """The registry for <project>, or for the project this file is installed in; None when
    the v5 tables apply. Never raises."""
    if project is not None:
        return load_registry(project)[0]
    try:
        reg = runtime_module("registry").load(default_root(), warn=False)
    except Exception:  # a broken registry.py must not break the CLI
        return None
    return None if reg.missing else reg


def agent_table(project, kind):
    """{id: (argv, model_flag)} for kind "review" or "build", from the registry, or the
    v5 table when the registry is missing. Both kinds come from one agents record."""
    reg, _ = load_registry(project)
    if reg is None:
        return v5_agent_table(kind)
    return runtime_module("registry").agent_table(reg, kind)


def identity_env(project=None):
    """(AGENT_ENV, MODEL_ENV) from the agents records, or the v5 tables."""
    reg = _registry_or_none(project)
    if reg is not None:
        try:
            return runtime_module("registry").identity_env(reg)
        except Exception:
            pass
    return v5_identity_env()


def pointer_files(project=None, builtin_only=False):
    """Every pointer file a harness record names, or the v5 list."""
    reg = _registry_or_none(project)
    if reg is not None:
        try:
            return runtime_module("registry").pointer_files(reg, builtin_only=builtin_only)
        except Exception:
            pass
    return V5_POINTER_FILES


def reviewer_choices():
    """The --reviewer choices: every agent with a review argv. Built from the registry
    inside a try, so a bad manifest or registry.py falls back to a static list."""
    try:
        reg = _registry_or_none()
        table = (runtime_module("registry").agent_table(reg, "review") if reg is not None
                 else v5_agent_table("review"))
        return tuple(sorted(table)) or STATIC_REVIEWERS
    except Exception:
        return STATIC_REVIEWERS


def agent_family(project, harness):
    """The model family an agent CLI runs by default, for the independence label."""
    reg, _ = load_registry(project)
    rec = (reg.agents() if reg is not None else V5_AGENTS).get(harness)
    return (rec or {}).get("family") or ""


def broken_agent(project, by):
    """The error for agent <by> when the extension that would provide it failed to load."""
    reg, _ = load_registry(project)
    err = reg.broken.get(by) if reg is not None else None
    if not err:
        return None
    return ("the %s extension is invalid and was skipped: %s: %s: %s. Run `sdlc.py doctor`, "
            "then restore it with `install.sh <this project> --upgrade` or fix the file"
            % (by, err["path"], err["field"], err["message"]))


def check_extensions(project, out):
    reg, why = load_registry(project)
    if reg is None:
        out.add("warn", "extensions", ".ai-sdlc/extensions",
                "registry missing, using v5 tables: %s" % why,
                fix="Restore the built-in extensions: install.sh <this project> --upgrade")
        return
    for err in reg.errors:
        out.add("fail", "extensions", err["path"],
                "%s: %s; the extension is skipped" % (err["field"], err["message"]))
    for item in reg.warnings:
        out.add("warn", "extensions", item["path"], "%s: %s" % (item["field"], item["message"]))
    for note in reg.notes:
        out.add("warn", "extensions", note["path"], note["message"],
                fix="Allow it with `sdlc.py config --allow-extension %s` (it takes effect once "
                    "merged to the default branch), or `sdlc.py ext remove %s`"
                    % (note["id"], note["id"]) if note.get("blocked") else None,
                who="human" if note.get("blocked") else None)
    reg_mod = runtime_module("registry")
    for ext_id in sorted(reg.extensions):
        ext = reg.extensions[ext_id]
        if ext["source"] == reg_mod.BUILTIN or reg.status(ext_id) != "code-enabled":
            continue
        for field, what in reg_mod.executable_entries(ext["manifest"]):
            out.add("info", "extensions", ext["rel"], "%s %s %s" % (ext_id, field, what))
    for item in reg_mod.run_doctor(reg, project.root):
        out.add(item["level"], "extensions", item["where"], item["message"])


# ---------------------------------------------------------------- review

def item_diff(project, item, base=None):
    if base and str(base).startswith("-"):
        return None, "base %r is not a valid git ref" % base
    commits = item_commits(project, item)
    if not commits and not base:
        return None, ("no commit carries a `Work-Item: %s` trailer; pass --base to review "
                      "the working tree" % item)
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
            "Paraphrase: <two to five sentences of your own: what this change does and how the "
            "code it touches works. A part you cannot paraphrase is a finding>\n"
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
    elif broken_agent(project, by):
        return None, None, broken_agent(project, by)
    elif by in agent_table(project, "review"):
        command, harness = None, by
        exe = agent_table(project, "review")[by][0][0]
        if shutil.which(exe) is None:
            return None, None, ("%s is not installed (no `%s` on PATH); install it, or use "
                                "--by cmd:<command> with a reviewer that reads the prompt on "
                                "stdin" % (by, exe))
    else:
        return None, None, "--by must be %s or cmd:<command>" % ", ".join(
            sorted(agent_table(project, "review")))
    diff, error = item_diff(project, item, base)
    if error:
        return None, None, error
    tier = item_tier(project, item)
    prompt = review_prompt(project, item, role, tier, diff)
    if command:
        rc, out_b, err_b, timed_out = _run_isolated(
            command, cwd=project.root, timeout=timeout, shell=True, input_text=prompt
        )
    else:
        args, flag = agent_table(project, "review")[by]
        args = [part.replace("{prompt}", prompt) for part in args]
        if model:
            args += [flag, model]
        rc, out_b, err_b, timed_out = _run_isolated(
            args, cwd=project.root, timeout=timeout, shell=False
        )
    if timed_out:
        return None, None, "the reviewer did not answer within %ds" % timeout
    stdout_str = out_b.decode("utf-8", "replace")
    stderr_str = err_b.decode("utf-8", "replace")
    if rc != 0 or not stdout_str.strip():
        return None, None, "the reviewer failed (exit %s): %s" % (
            rc, (stderr_str or stdout_str).strip()[-400:])
    reviewer_model = model or "unknown (the harness default)"
    if harness == "cmd":
        m = re.search(r"^Model:\s*(\S+)", stdout_str, re.M)
        reviewer_model = model or (m.group(1) if m else "unknown")
    author_agent, author_model = item_author(project, item)
    family_reviewer = model_family(reviewer_model if reviewer_model != "unknown (the harness default)"
                                   else agent_family(project, harness))
    family_author = model_family(author_model or author_agent or "")
    independent = (family_reviewer not in ("unknown",) and family_author != "unknown"
                   and family_reviewer != family_author)
    verdict = re.search(r"^Verdict:\s*(Pass with conditions|Pass|Block)", stdout_str, re.M)
    folder = project.path(os.path.join(project.docs, "project", "reviews"))
    os.makedirs(folder, exist_ok=True)
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
               role, stdout_str.strip()))
    path = os.path.join(folder, "%s-%s-%s.md" % (item, stage, role))
    n = 1
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            n += 1
            path = os.path.join(folder, "%s-%s-%s-%d.md" % (item, stage, role, n))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    return os.path.relpath(path, project.root), record, None


RESPONSES = ("fix", "contest", "escalate", "decline")


NOT_DECIDED = re.compile(r"^(tbd|pending|owner|the owner|n/?a|none|todo|unknown|\?+)$", re.I)


def _response_sections(text):
    """Lines under every `## Responses...` or `### Responses...` heading, each up to the
    next heading of the same or a higher level."""
    lines, level = [], 0
    for line in text.splitlines():
        m = re.match(r"^(#{2,6})\s+(.*)$", line)
        if m:
            depth = len(m.group(1))
            if level and depth <= level:
                level = 0
            if m.group(2).strip().lower().startswith("responses"):
                level = depth
            continue
        if level:
            lines.append(line)
    return lines


def _plain(cell):
    return re.sub(r"[*_`]", "", UNFILLED.sub("", cell)).strip()


def review_responses(text):
    """Rows of a review's Responses table(s): the author's answer to each finding
    (02-role-reviews.md, "Answering findings"). Columns are found by their header names.
    Template placeholder rows are skipped. Fails closed: a cell that only defers the
    decision ("pending", "TBD", "owner") is not a decision."""
    rows, cols = [], None
    for line in _response_sections(text):
        cells = split_row(line)
        if cells is None:
            cols = None if not line.strip() else cols
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if cols is None:
            names = [_plain(c).lower() for c in cells]
            pick = lambda *keys: next((i for i, n in enumerate(names)
                                       if any(n.startswith(k) for k in keys)), None)
            cols = {"n": pick("#", "finding", "no"), "response": pick("response"),
                    "evidence": pick("evidence"), "decided_by": pick("decided")}
            if cols["response"] is None:
                cols = {"n": 0, "response": 1, "evidence": 2, "decided_by": 3}
            else:
                continue
        get = lambda k: cells[cols[k]] if cols.get(k) is not None and cols[k] < len(cells) else ""
        word = _plain(get("response")).lower()
        if not word:
            continue
        m = re.match(r"(fix|contest|escalat|declin)", word)
        response = {"fix": "fix", "contest": "contest", "escalat": "escalate",
                    "declin": "decline"}[m.group(1)] if m else \
            ("escalate" if "escalat" in word else word)
        decided = _plain(get("decided_by")).strip("—-– ").strip()
        evidence = UNFILLED.sub("", get("evidence")).strip().strip("—-– ").strip()
        rows.append({"n": _plain(get("n")), "response": response, "evidence": evidence,
                     "decided_by": "" if not decided or NOT_DECIDED.match(decided) else decided})
    return rows


def open_escalations(project, item):
    """(file, finding #) for each of <item>'s findings escalated to a person and not decided."""
    folder = project.path(os.path.join(project.docs, "project", "reviews"))
    found = []
    for rec in review_records(project, item):
        for row in review_responses(read(os.path.join(folder, rec["file"]))):
            if row["response"] == "escalate" and not row["decided_by"]:
                found.append((rec["file"], row["n"]))
    return found


def check_responses(project, out):
    """An escalated finding waits on a person: it is the owner's decision. A contest must
    cite evidence the reviewer could read, or it is only the author disagreeing."""
    rel = os.path.join(project.docs, "project", "reviews")
    folder = project.path(rel)
    if not os.path.isdir(folder):
        return
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name == "README.md":
            continue
        for row in review_responses(read(os.path.join(folder, name))):
            where = "%s/%s #%s" % (rel, name, row["n"])
            if row["response"] == "escalate" and not row["decided_by"]:
                out.add("warn", "escalation", where,
                        "finding %s is escalated to a person and has no decision: %s"
                        % (row["n"], row["evidence"] or "no reason given"))
            elif row["response"] == "contest" and not row["evidence"]:
                out.add("warn", "contest", where,
                        "finding %s is contested with no evidence the reviewer could read"
                        % row["n"])
            elif row["response"] not in RESPONSES:
                out.add("warn", "contest", where,
                        "finding %s has response %r; use Fix, Contest, Escalate or Decline"
                        % (row["n"], row["response"]),
                        fix="Change the response to Fix, Contest, Escalate or Decline")


def review_records(project, item):
    """Parsed headers of every review file for <item>."""
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "reviews" in cache:
        all_recs = cache["reviews"]
    else:
        folder = project.path(os.path.join(project.docs, "project", "reviews"))
        all_recs = []
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".md"):
                    continue
                text = read(os.path.join(folder, name))
                fields = dict(re.findall(r"^\*\*(Reviewer agent|Reviewer model|Independence|Author):\*\*"
                                         r"\s*(.+)$", text, re.M))
                all_recs.append({"file": name, "fields": fields})
        if cache is not None:
            cache["reviews"] = all_recs
    prefix = item + "-"
    return [r for r in all_recs if r["file"].startswith(prefix)]


def independent_review_policy(charter, profile=None):
    """(policy, tiers, state): policy is 'none' (default), 'Tier 1', or 'Tier 1 and 2'.
    Off ('none') by default unless explicitly enabled in the charter or profile."""
    raw = labelled(charter, "Independent review required for")
    if raw is not None:
        cell = UNFILLED.sub("", raw).strip()
        has_none = bool(re.search(r"\b(none|off)\b", cell, re.I))
        has_t12 = "and 2" in cell
        t1_count = cell.count("Tier 1")
        if has_none and t1_count == 0:
            return "none", set(), "decided"
        if has_t12 and t1_count == 1 and not has_none:
            return "Tier 1 and 2", set(["1", "2"]), "decided"
        if t1_count == 1 and not has_t12 and not has_none:
            return "Tier 1", set(["1"]), "decided"
        state = "blank" if not cell else "undecided"
    else:
        state = "blank"
    if isinstance(profile, dict) and profile.get("independent_review"):
        p_raw = str(profile.get("independent_review")).strip().lower()
        if p_raw in ("tier 1 and 2", "tier1-2"):
            return "Tier 1 and 2", set(["1", "2"]), "decided"
        if p_raw in ("tier 1", "tier1"):
            return "Tier 1", set(["1"]), "decided"
        if p_raw in ("none", "off"):
            return "none", set(), "decided"
    return "none", set(), state


def discovered_defects_policy(charter, profile=None):
    """(policy, state): policy is 'Parked' (default) or 'Auto-Ready (bite)'."""
    raw = labelled(charter, "Discovered defects")
    if raw is not None:
        val, state = choice(raw, DISCOVERED_DEFECTS)
        if state == "decided" and val:
            return val, "decided"
    else:
        state = "blank"
    if isinstance(profile, dict) and profile.get("discovered_defects"):
        p_raw = str(profile.get("discovered_defects")).strip().lower()
        if p_raw in ("auto-ready (bite)", "auto-ready-bite", "auto"):
            return "Auto-Ready (bite)", "decided"
        if p_raw == "parked":
            return "Parked", "decided"
    return "Parked", state


def resolve_discovered_status(project, item_id, item_type, tier):
    """Return ('Ready' | 'Parked', reason) for a newly discovered or triaged item."""
    policy, _ = discovered_defects_policy(project.charter, project.profile)
    itype = str(item_type or "feat").strip().lower()
    if itype == "bug":
        itype = "defect"
    t = str(tier or "2").strip()
    if policy == "Auto-Ready (bite)" and itype == "defect" and t in ("2", "3"):
        has_bite = any(
            r.get("item") == item_id and r.get("stage") == "bite" and r.get("result") == "Verified: pass"
            for r in ledger(project)
        )
        if has_bite:
            return "Ready", "Auto-Ready (bite): Tier %s defect has a passing bite run" % t
        return "Parked", "Auto-Ready (bite) requires a passing `sdlc.py bite --item %s` run first" % item_id
    if policy == "Auto-Ready (bite)":
        return "Parked", "Auto-Ready (bite) applies only to Tier 2 or 3 defects (got Tier %s %s)" % (t, itype)
    return "Parked", "charter Discovered defects policy is Parked (human triage required)"


DEFAULT_RETRO_REVIEW_DAYS = 2


def retro_review_window(charter):
    """Days a hotfix has for its retroactive review: the charter's Retroactive review within
    row, or DEFAULT_RETRO_REVIEW_DAYS when the row is absent or blank."""
    cell = UNFILLED.sub("", labelled(charter or "", "Retroactive review within") or "")
    found = re.search(r"[0-9]+", cell)
    return int(found.group(0)) if found else DEFAULT_RETRO_REVIEW_DAYS


def retro_reviews(project, item):
    """The retroactive review files for <item>: <docs>/project/reviews/<ID>-retro*.md."""
    return [r for r in review_records(project, item) if r["file"].startswith(item + "-retro")]


def mark_hotfix(project, item_id, today=None):
    """Mark <item_id> as a hotfix: hotfix true and the UTC time, the tier unchanged. The one
    path behind `item set <ID> --hotfix` and `hotfix <ID>`. Returns (shard, error, exit code)."""
    today = today or datetime.date.today().isoformat()
    cur = _shards_mod.merged_items(project).get(item_id)
    if not cur:
        return None, _shards_mod.not_found(project, item_id), 2
    updated = dict(cur)
    if not _shards_mod.is_hotfix(cur) or not cur.get("hotfix_at"):
        updated["hotfix"] = True
        updated["hotfix_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    updated["updated"] = today
    try:
        return _shards_mod.save_item(project, updated, today=today), None, 0
    except ValueError as exc:
        return None, str(exc), 2


def check_hotfix(project, out, today):
    """A hotfix skips the pre-merge review and owes a retroactive one within the charter's
    window. Past the window with no <ID>-retro*.md review file, doctor fails it."""
    window = retro_review_window(project.charter)
    for iid, it in sorted(_shards_mod.merged_items(project).items(), key=lambda kv: id_sort_key(kv[0])):
        if not _shards_mod.is_hotfix(it) or it.get("status") == "Dropped":
            continue
        marked = str(it.get("hotfix_at") or "")[:10]
        days = age_days(marked, today)
        if days is None:
            out.add("warn", "hotfix", "hotfix %s" % iid, "hotfix %s has no hotfix_at date, so "
                    "its retroactive review window cannot be checked" % iid)
        elif days > window and not retro_reviews(project, iid):
            out.add("fail", "hotfix", "hotfix %s" % iid,
                    "hotfix %s was marked %s and has no retroactive review after %d day(s); "
                    "the charter's Retroactive review within is %d: write %s/project/reviews/"
                    "%s-retro-<role>.md" % (iid, marked, days, window, project.docs, iid))


FOLLOW_UP_ID = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9]+\b")


def check_postmortems(project, out):
    """Each postmortem names its follow-up items, and they exist; and names the regression
    test that reproduces the failure."""
    folder = project.path(os.path.join(project.docs, "project", "postmortems"))
    if not os.path.isdir(folder):
        return
    known = set(_shards_mod.merged_items(project))
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name.lower() == "readme.md":
            continue
        rel = os.path.join(project.docs, "project", "postmortems", name)
        text = read(os.path.join(folder, name))
        follow = re.search(r"^\*\*Follow-up items:\*\*(.*)$", text, re.M)
        ids = FOLLOW_UP_ID.findall(UNFILLED.sub("", follow.group(1))) if follow else []
        if not ids:
            out.add("warn", "postmortem", rel, "postmortem names no follow-up item IDs on its "
                    "**Follow-up items:** line")
        missing = [i for i in ids if i not in known]
        if missing:
            out.add("fail", "postmortem", rel, "postmortem follow-up %s is not a work item in "
                    "the backlog" % ", ".join(missing))
        test = re.search(r"^\*\*Regression test:\*\*(.*)$", text, re.M)
        if not test or not UNFILLED.sub("", test.group(1)).strip():
            out.add("warn", "postmortem", rel, "postmortem names no regression test on its "
                    "**Regression test:** line")


def check_identity(project, out):
    """When independent review is enabled in the charter, Tier 1 work (and Tier 2 if the
    charter says so) needs a review from a different model family than the author's.
    Same-family reviews are recorded as self-checks and clear nothing. Only items whose
    commits carry Agent or Model trailers are judged: earlier work has no author identity
    to compare."""
    _, tiers, _ = independent_review_policy(project.charter, project.profile)
    if not tiers:
        return
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


def claims_verified(entry):
    """Whether a worklog entry claims a Verified result. The template's `### Verified`
    heading is a section name, not a claim, and "Not run" or "Absent" under it claim
    nothing; a compact line's `verified: <run>: pass` does claim it."""
    body = re.sub(r"(?m)^#+ .*$", "", entry)
    return bool(re.search(r"\bVerified\b", body) or
                re.search(r"(?i)\bverified:\s*(?!not run|absent|none\b|-|n/a)\S", body))


UNATTRIBUTED_VERIFIED = (
    "says Verified, but the evidence ledger has no `sdlc.py verify` run for this item: its "
    "commits mention it without a `Work-Item:` trailer, so none is attributed to it. Commit "
    "with the trailer (`sdlc.py trailers <ID>`) and run verify")


def check_verified_claims(project, out):
    """A worklog entry that says Verified for an item must have a ledger row for one of
    that item's commits. Entries for items with no commits are judged only when commit
    messages mention the item without a Work-Item trailer naming it: that work exists
    but nothing attributes it, so no ledger run can be matched to it."""
    prefix = project.prefix
    if not prefix:
        return
    rows = ledger(project)
    unattributed = set(mentioned_only(project))
    checked_ids = set()
    for wl_id, wl_rel, wl_body in _shards_mod.load_worklog_shards(project):
        checked_ids.add(wl_id)
        if not re.fullmatch(r"%s-[0-9]+" % re.escape(prefix), wl_id):
            continue
        if not claims_verified(wl_body):
            continue
        if not item_commits(project, wl_id):
            if wl_id in unattributed:
                out.add("warn", "evidence", "%s %s" % (wl_rel, wl_id), UNATTRIBUTED_VERIFIED)
            continue
        if not evidence_matches(project, wl_id, rows):
            out.add("warn", "evidence", "%s %s" % (wl_rel, wl_id),
                    "says Verified, but the evidence ledger has no `sdlc.py verify` run on "
                    "this item's commits. Only verify makes a result Verified")

    text = project.records("worklog.md")
    if not text:
        return
    entries = re.split(r"(?m)^(?=## |- [0-9]{4}-[0-9]{2}-[0-9]{2} · )", text)
    where = os.path.join(project.docs, "project", "worklog.md")
    for entry in entries:
        head = re.match(r"^(?:## |- [0-9-]+ · )(%s-[0-9]+)" % re.escape(prefix), entry)
        if not head or not claims_verified(entry):
            continue
        item = head.group(1)
        if item in checked_ids:
            continue
        if not item_commits(project, item):
            if item in unattributed:
                out.add("warn", "evidence", "%s %s" % (where, item), UNATTRIBUTED_VERIFIED)
            continue
        if not evidence_matches(project, item, rows):
            out.add("warn", "evidence", "%s %s" % (where, item),
                    "says Verified, but the evidence ledger has no `sdlc.py verify` run on "
                    "this item's commits. Only verify makes a result Verified")


def check_people(project, out):
    """With a people.json registry: open items whose owner is neither a role nor a
    handle (one line per owner), and how many claims record no person (one line)."""
    registry = people(project)
    rel = os.path.join(project.docs, PEOPLE_REL)
    if registry:
        slugs = role_slugs(project)
        stray = {}
        try:
            merged = _shards_mod.merged_items(project)
        except Exception:
            merged = {}
        for iid in sorted(merged, key=id_sort_key):
            it = merged[iid]
            owner = str(it.get("owner") or "").strip()
            if not owner or it.get("status") in ("Done", "Dropped") or owner in slugs:
                continue
            if person_key(owner) in registry:
                continue
            stray.setdefault(owner, []).append(iid)
        for owner, ids in sorted(stray.items()):
            out.add("warn", "people", rel,
                    "owner %r on %s is neither a role nor a handle in people.json"
                    % (owner, ", ".join(ids[:8]) + (" ..." if len(ids) > 8 else "")),
                    fix="%s item set <ID> --owner <handle or role>, or add the person to %s"
                        % (SDLC, rel), who="owner")
    try:
        held = runtime_module("claims").list_claims(project)
    except Exception:
        held = []
    missing = [c for c in held if not c.get("person")]
    if missing:
        out.add("warn" if registry else "info", "people", "claims",
                "%d claim%s record%s no person (%s)" % (
                    len(missing), "" if len(missing) == 1 else "s",
                    "s" if len(missing) == 1 else "",
                    ", ".join(c.get("id", "?") for c in missing[:8])
                    + (" ..." if len(missing) > 8 else "")),
                fix="Claim with NUHUT_USER=<handle> set, or map git user.name in %s; "
                    "re-claim to record the person" % rel, who="owner")


def check_attribution(project, out):
    """Since 6.0 only a Work-Item trailer attributes a commit. Items that commit messages
    mention but no trailer names lost their commits; approver names that people.json
    does not know cannot waive."""
    lost = [item for item in mentioned_only(project)
            if item in set(row_id for row_id, _, _ in backlog_rows(
                project.records("backlog.md"), project.prefix,
                getattr(project, "legacy_prefixes", None)))]
    if lost:
        out.add("info", "attribution", "git log",
                "%d item%s lost commit attribution (no Work-Item trailer); see `sdlc.py "
                "trailers`: %s" % (len(lost), "" if len(lost) == 1 else "s",
                                   ", ".join(lost[:8]) + (" ..." if len(lost) > 8 else "")),
                fix="Commit further work on these items with a `Work-Item: <ID>` trailer "
                    "(`%s trailers <ID>`); old commits stay unattributed" % SDLC, who="agent")
    registry = people(project)
    if registry:
        names, source = approver_names(project)
        for name in names:
            handle = resolve_person(registry, name)
            if handle is None:
                out.add("warn", "approvers", "%s Approvers" % project.charter_path,
                        "%r is not a handle in people.json (read from %s), so it cannot "
                        "waive verify" % (name, source),
                        fix="Use the person's people.json handle in the Approvers row, or "
                            "add them to people.json", who="owner")
            elif person_key(name) != handle:
                out.add("warn", "approvers", "%s Approvers" % project.charter_path,
                        "%r is a name, not a handle; write %s, the people.json handle it "
                        "resolves to (read from %s)" % (name, handle, source),
                        fix="Replace %r with %s in the Approvers row" % (name, handle),
                        who="owner")


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
    own_cache = getattr(project, "_build_cache", None) is None
    if own_cache:
        project._build_cache = {}
    try:
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
            tier = (re.search(r"[123]", cells[2]).group(0)
                    if len(cells) > 2 and re.search(r"[123]", cells[2]) else "")
            report.append({"item": item, "tier": tier, "tokens": tokens, "minutes": minutes,
                           "budget": limits.get(tier, {})})
        return report
    finally:
        if own_cache:
            project._build_cache = None


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
    """Insert drafted lines above the newest worklog entry (or write per-item worklog shards
    when sharded), skipping any item the worklog already names. Returns the lines written."""
    if _shards_mod.is_sharded(project, for_write=True):
        existing_text = project.worklog_texts()
        written = []
        for line in lines:
            parts = line.split(" · ")
            if len(parts) < 2:
                continue
            item_id = parts[1].strip()
            if _shards_mod.load_worklog_shard(project, item_id) or item_id in existing_text:
                continue
            _shards_mod.save_worklog_shard(project, item_id, line)
            written.append(line)
        return written
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
    if not base or str(base).startswith("-"):
        return []
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
            if folder:
                os.makedirs(folder, exist_ok=True)
            if os.path.lexists(target) and os.path.islink(target):
                os.remove(target)
            shutil.copy2(project.path(os.path.join(state["backup"], item["path"])), target,
                         follow_symlinks=False)
        elif os.path.lexists(target):
            os.remove(target)
        restored.append(item["path"])
    shutil.rmtree(project.path(state["backup"]), ignore_errors=True)
    os.remove(marker)
    return restored


def bite(project, command, base=None, timeout=1800, item=None):
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
    if str(base).startswith("-") or not project.git("rev-parse", "--verify", "--quiet", base + "^{commit}").strip():
        return None, "base %r is not a commit" % base
    files = bite_files(project, base)
    if not files:
        return None, ("no product change between %s and the working tree to revert "
                      "(test files and the kit's own paths are left alone)" % base)

    bite_env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def run():
        rc, _, _, timed_out = _run_isolated(
            command, cwd=project.root, timeout=timeout, shell=True,
            stderr=subprocess.STDOUT, env=bite_env
        )
        return None if timed_out else rc

    with_change = run()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(BITE_DIR, stamp)
    os.makedirs(project.path(backup), exist_ok=True)
    ignore = project.path(os.path.join(BITE_DIR, ".gitignore"))
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n!.gitignore\n")
    state = {"base": base, "backup": backup, "command": command, "files": []}
    for rel in files:
        existed = os.path.lexists(project.path(rel))
        if existed:
            dest = project.path(os.path.join(backup, rel))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(project.path(rel), dest, follow_symlinks=False)
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
                if os.path.dirname(target):
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                if os.path.islink(target):
                    os.remove(target)
                with open(target, "wb") as handle:
                    handle.write(original.stdout)
                ls_tree = project.git("ls-tree", base, "--", rel).strip()
                if ls_tree.startswith("100755"):
                    try:
                        os.chmod(target, 0o755)
                    except OSError:
                        pass
            elif os.path.lexists(target):
                os.remove(target)
        without_change = run()
    finally:
        bite_restore(project)
        signal.signal(signal.SIGTERM, previous)

    result = {"command": command, "base": base, "files": files,
              "with_change": with_change, "without_change": without_change,
              "bites": with_change == 0 and without_change not in (0, None),
              "git_head": project.git("rev-parse", "HEAD").strip(),
              "dirty": tree_dirty(project),
              "generated": datetime.datetime.now(datetime.timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ")}
    folder = evidence_dir(project, "-bite")
    with open(os.path.join(folder, "bite.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    row = {"time": result["generated"], "commit": result["git_head"],
           "dirty": result["dirty"], "stage": "bite", "command": command,
           "exit_code": 0 if result["bites"] else 1,
           "result": "Verified: %s" % ("pass" if result["bites"] else "fail"),
           "output_sha256": "", "run": os.path.basename(folder)}
    if item:
        row["item"] = item
    ledger_append(project, [row])
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
                token = NEW_MARK.sub("", token)
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
    cache = getattr(project, "_build_cache", None)
    key = ("changed", base)
    if cache is not None and key in cache:
        return cache[key]
    names = set()
    merge_base = project.git("merge-base", base, "HEAD").strip()
    if merge_base:
        names.update(project.git("diff", "--name-only", merge_base, "HEAD").split("\n"))
    names.update(project.git("diff", "--name-only", "HEAD").split("\n"))
    names.update(project.git("ls-files", "--others", "--exclude-standard").split("\n"))
    records = project.docs.rstrip("/") + "/project/"
    # .ai-sdlc/ holds generated state (ledger, cache, dispatch logs, backups), which every
    # change touches. Its runtime, profile and manifest are real changes and are counted.
    counted = (".ai-sdlc/bin/", ".ai-sdlc/profile.json", ".ai-sdlc/manifest.json")
    res = sorted(n for n in names if n and not n.startswith(records)
                 and (not n.startswith(".ai-sdlc/") or n.startswith(counted)))
    if cache is not None:
        cache[key] = res
    return res


def find_plan(project, item):
    """(rel, text) of the item's plan or spec; text is "" when there is none."""
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
    return rel, text


NEW_MARK = re.compile(r"\s*\(new\)\s*$", re.I)


def planned_new(text):
    """Planned paths whose list line says (new): the build creates them."""
    found = []
    for line in plan_section(text, "Files that change"):
        if re.search(r"\(new\)", line, re.I):
            for token in re.findall(r"`([^`]+)`", line):
                for path in expand_braces(NEW_MARK.sub("", token).strip()):
                    while path.startswith("./"):
                        path = path[2:]
                    found.append(path)
    return found


def _too_broad(project, regexes):
    """The planned paths that make a plan match over half the tracked files, or []."""
    tracked = [t for t in project.git("ls-files").split("\n") if t]
    if len(tracked) < 20:
        return []
    matched = sum(1 for t in tracked if any(r.match(t) for _, r in regexes))
    if matched * 2 <= len(tracked):
        return []
    broad = [p for p, r in regexes if sum(1 for t in tracked if r.match(t)) * 10 > len(tracked)]
    return broad or [p for p, _ in regexes]


def _plan_or_error(project, item):
    rel, text = find_plan(project, item)
    if not text:
        return None, None, ("no plan at %s. Tier 1 items have one; a Tier 2 or 3 plan lives in "
                            "the response and cannot be checked mechanically." % rel)
    planned = planned_paths(text)
    if not planned:
        return None, None, ("%s has no backticked paths under \"## Files that change\", so "
                            "there is nothing to compare the diff with." % rel)
    return rel, text, None


def plan_precheck(project, item):
    """Before the build: every planned path matches a file here or is marked (new), and the
    list is narrow enough for plan-check to fail. Returns (result, error)."""
    rel, text, error = _plan_or_error(project, item)
    if error:
        return None, error
    planned = planned_paths(text)
    new = [p for p in planned_new(text) if p in planned]
    on_disk = set(t for t in project.git("ls-files", "--cached", "--others",
                                         "--exclude-standard").split("\n") if t)
    regexes = [(p, glob_regex(p)) for p in planned]
    missing = [p for p, r in regexes if p not in new
               and not any(r.match(f) for f in on_disk)
               and not os.path.exists(project.path(p))]
    return {"item": item, "plan": rel, "planned": planned, "new": new, "missing": missing,
            "broad": _too_broad(project, regexes)}, None


def print_plan_precheck(result):
    print("plan-check %s --pre: %d planned, %d marked new, in %s"
          % (result["item"], len(result["planned"]), len(result["new"]), result["plan"]))
    for p in result["missing"]:
        print("fail  missing     %s  (no file matches it; fix the path, or add (new) after it "
              "if the build creates it)" % p)
    if result["broad"]:
        print("fail  too broad   the plan's paths match over half the repository, so "
              "plan-check cannot fail after the build. Narrow: %s" % ", ".join(result["broad"]))
    if not result["missing"] and not result["broad"]:
        print("Every planned path exists or is marked (new).")


def plan_check(project, item, base=None):
    """Returns (result, error). The records under project/ are bookkeeping every change
    touches, so they are never "unplanned"."""
    rel, text, error = _plan_or_error(project, item)
    if error:
        return None, error
    planned = planned_paths(text)
    base = base or default_branch(project) or "main"
    if str(base).startswith("-"):
        return None, ("base %r is not a git ref here. Pass --base, or fill the charter's "
                      "Default branch row." % base)
    cache = getattr(project, "_build_cache", None)
    ref_key = ("ref", base)
    if cache is not None and ref_key in cache:
        ref_ok = cache[ref_key]
    else:
        ref_ok = bool(project.git("rev-parse", "--verify", "--quiet", base).strip())
        if cache is not None:
            cache[ref_key] = ref_ok
    if not ref_ok:
        return None, ("base %r is not a git ref here. Pass --base, or fill the charter's "
                      "Default branch row." % base)
    changed = changed_files(project, base)
    regexes = [(p, glob_regex(p)) for p in planned]
    unplanned = [f for f in changed if not any(r.match(f) for _, r in regexes)]
    untouched = [p for p, r in regexes if not any(r.match(f) for f in changed)]
    # A plan whose globs match most of the repository cannot fail this check.
    broad = _too_broad(project, regexes)
    return {"item": item, "plan": rel, "base": base, "planned": planned,
            "changed": changed, "unplanned": unplanned, "untouched": untouched,
            "broad": broad}, None


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
    if result.get("broad"):
        print("%swarn  too broad   the plan's paths match over half the repository, so this "
              "check cannot find gaps. Narrow: %s%s"
              % (c_red, ", ".join(result["broad"]), c_reset))
    if not result["unplanned"] and not result["untouched"] and not result.get("broad"):
        print("%sThe diff matches the plan's file list. Whether it matches the plan's intent "
              "is the review's conformance pass.%s" % (c_green, c_reset))
    else:
        print("\nEach gap is either a plan to update (in the same commit) or a change to "
              "question. Neither is decided here.")


# ---------------------------------------------------------------- ci-check

# Bot authors whose commits carry no trailers. They skip the trailer check only: their
# paths still meet the tier floor, unattributed, so a bot commit on a Tier 1 path fails.
CI_BOTS = ("dependabot[bot]", "github-actions[bot]")
# Used when the charter's Always Tier 1 here row names no backticked glob; any depth.
CI_DEFAULT_TIER1 = ("**/auth/**", "**/migrations/**", "**/infra/**")
# The charter rows whose change is itself a Tier 1 change (ADR 0003 decision 8).
CI_SECURITY_ROWS = ("Approvers", "Always Tier 1 here", "Extensions allowed", "Notify webhook",
                    "Tier rules", "Independent review required for")
# Under .ai-sdlc/ but not enforcement surfaces: the test-first locks routine Tier 2 work
# keeps, and the folders of generated state (each holds a committed .gitignore).
CI_NOT_TIER1 = (".ai-sdlc/test-lock.txt",) + tuple(
    ".ai-sdlc/%s/" % name for name in ("backups", "bite", "cache", "dispatch", "evidence",
                                       "guard", "runs", "session", "view"))
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _printable(text):
    """Commit text as safe to print in a CI log: no terminal escapes."""
    return _CONTROL.sub("?", str(text or ""))


def ci_tier1_globs(project, charter_ref=None):
    """(globs, source): the Tier 1 path globs ci-check enforces. The backticked globs in
    the charter's Always Tier 1 here row, read at <charter_ref> through trusted_text, else
    auth/, migrations/ and infra/ at any depth; always the kit's own enforcement surfaces."""
    text, source = trusted_text(project, project.charter_path, charter_ref)
    cell = UNFILLED.sub("", labelled(text, "Always Tier 1 here") or "")
    globs = [g.strip() for g in re.findall(r"`([^`\n]+)`", cell)
             if g.strip() and not re.search(r"\s", g.strip()) and not g.strip().startswith("-")]
    if not globs:
        globs = list(CI_DEFAULT_TIER1)
    always = [".ai-sdlc/**", ".github/workflows/**",
              project.docs.rstrip("/") + "/project/people.json"]
    return globs + [g for g in always if g not in globs], source


def _ci_tier_at(project, ref, item):
    """The item's tier on <ref>: its shard file, else its backlog row; '' when unknown."""
    folder = project.docs.rstrip("/") + "/project/"
    raw = project.git("show", "%s:%sitems/%s.json" % (ref, folder, item))
    if raw.strip():
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        if isinstance(data, dict) and tier_of(str(data.get("tier", ""))):
            return tier_of(str(data.get("tier", "")))
    text = project.git("show", "%s:%sbacklog.md" % (ref, folder))
    for row_id, _, cells in backlog_rows(text, project.prefix,
                                         getattr(project, "legacy_prefixes", None)):
        if row_id == item and len(cells) > 2:
            return tier_of(cells[2])
    return ""


def _ci_charter_rows(project, ref):
    text = show_at(project, ref, project.charter_path) or ""
    return dict((label, labelled(text, label)) for label in CI_SECURITY_ROWS)


def _ci_paths(project, sha, parents, merge_base):
    """Paths a commit changes. A merge is judged on what it changes against its first
    parent (`git diff --name-only <first-parent> <merge>`), less what one of its other
    parents or the base branch already had: those paths were judged on the commits that
    wrote them, so what is left is the content the merge itself added."""
    if len(parents) > 1:
        out = project.git("diff", "--name-only", parents[0], sha)
        keep = None
        for other in list(parents[1:]) + [merge_base]:
            changed = set(project.git("diff", "--name-only", other, sha).splitlines())
            keep = changed if keep is None else keep & changed
        return [p for p in out.splitlines() if p.strip() and p in keep]
    return commit_paths(project, sha)


def ci_event_head(path):
    """(sha, error): pull_request.head.sha from the GitHub event file at <path>."""
    if not path:
        return None, "--head event needs $GITHUB_EVENT_PATH (set by GitHub Actions)"
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        sha = data["pull_request"]["head"]["sha"]
    except (IOError, OSError, ValueError, KeyError, TypeError):
        return None, "no pull_request.head.sha in the event file $GITHUB_EVENT_PATH"
    if not isinstance(sha, str) or not _SHA.match(sha):
        return None, "pull_request.head.sha in $GITHUB_EVENT_PATH is not a commit id"
    return sha, None


def ci_check(project, base=None, head=None, charter_ref=None):
    """Returns (result, error). Judges the commits in merge_base(base, head)..head, merge
    commits included: trailers, the ledger record behind each item, a review file for
    each Tier 1 item, the tier floor its changed paths imply, and tier lowering."""
    base = base or default_branch(project) or "main"
    head = head or "HEAD"
    for name, ref in (("base", base), ("head", head), ("charter-ref", charter_ref)):
        if ref is None:
            continue
        if not ref or str(ref).startswith("-") or \
                not project.git("rev-parse", "--verify", "--quiet", ref + "^{commit}").strip():
            return None, ("%s %r is not a commit here. Fetch it (actions/checkout with "
                          "fetch-depth: 0), or pass --%s" % (name, ref, name))
    head_sha = project.git("rev-parse", "--verify", "--quiet", head + "^{commit}").strip()
    merge_base = project.git("merge-base", base, head_sha).strip()
    if not merge_base:
        return None, ("no merge base between %s and %s: the clone is shallow or the histories "
                      "are unrelated. Check out with fetch-depth: 0" % (base, head))
    log = project.git("log", "--format=%H%x01%P%x01%an%x01%B%x00",
                      "%s..%s" % (merge_base, head_sha))
    commits = []
    for record in log.split("\x00"):
        parts = record.strip("\n").split("\x01")
        if len(parts) < 4 or not parts[0].strip():
            continue
        commits.append({"sha": parts[0].strip(), "parents": parts[1].split(),
                        "author": parts[2], "subject": (parts[3].strip().splitlines() or [""])[0],
                        "trailers": trailers(parts[3])})
    findings = []

    def find(check, item, sha, detail, fix):
        findings.append({"check": check, "item": item or "", "sha": sha or "",
                         "detail": _printable(detail), "fix": fix})

    globs, glob_source = ci_tier1_globs(project, charter_ref)
    regexes = [(g, glob_regex(g)) for g in globs]
    charter_rel = project.charter_path.replace(os.sep, "/")
    items, tiers = [], {}
    for c in commits:
        tags, short = c["trailers"], c["sha"][:7]
        label = '%s "%s"' % (short, c["subject"][:60])
        item = (tags.get("Work-Item") or "").strip()
        if item and item not in items:
            items.append(item)
        if c["author"] not in CI_BOTS:
            agent = (tags.get("Agent") or "").strip()
            model = (tags.get("Model") or "").strip()
            missing = [k for k, v in (("Work-Item", item), ("Agent", agent)) if not v]
            if agent.lower() != "human" and not model:
                missing.append("Model")
            fix = "%s trailers %s" % (SDLC, item or "<ID>")
            if missing:
                find("trailers", item, c["sha"], "%s  missing %s" % (label, ", ".join(missing)),
                     "end the commit message with the lines `%s` prints" % fix)
            if agent.lower() == "unknown" or model.lower() == "unknown":
                find("trailers", item, c["sha"], "%s  Agent or Model is `unknown`" % label,
                     "set AI_SDLC_AGENT or use Agent: human (then no Model line)")
        if item and item not in tiers:
            tiers[item] = item_tier(project, item)
        tier = tiers.get(item, "") if item else ""
        if tier == "1":
            continue
        paths = _ci_paths(project, c["sha"], c["parents"], merge_base)
        hits = []
        for path in paths:
            if path in CI_NOT_TIER1 or path.startswith(CI_NOT_TIER1):
                continue
            glob = next((g for g, rx in regexes if rx.match(path)), None)
            if glob:
                hits.append((path, "matches `%s`" % glob))
            elif path == charter_rel and c["parents"]:
                before = _ci_charter_rows(project, c["parents"][0])
                after = _ci_charter_rows(project, c["sha"])
                changed = [k for k in CI_SECURITY_ROWS if before.get(k) != after.get(k)]
                if changed:
                    hits.append((path, "changes the security-bearing row(s) " +
                                 ", ".join(changed)))
        if hits:
            shown = "; ".join("%s %s" % pair for pair in hits[:3])
            if len(hits) > 3:
                shown += "; and %d more Tier 1 path(s)" % (len(hits) - 3)
            find("tier", item, c["sha"],
                 "%s  %s: Tier 1, but %s" % (
                     label, shown, ("%s is Tier %s" % (item, tier)) if item and tier
                     else "the commit names no Tier 1 item"),
                 "raise the item to Tier 1 (plan, review, approvals), or move the change "
                 "to a Tier 1 item")

    rules = tier_rules(project)
    for item in items:
        tier = tiers.get(item) or item_tier(project, item)
        if not tier:
            find("item", item, "", "%s is not in the backlog, so its tier cannot be judged"
                 % item, "add its backlog row, or correct the commit's Work-Item trailer")
            continue
        was = _ci_tier_at(project, base, item)
        if was and int(tier) > int(was):
            find("tier", item, "", "%s lowered from Tier %s to Tier %s against %s"
                 % (item, was, tier, base),
                 "restore Tier %s; lowering a tier needs its own reviewed change on %s"
                 % (was, base))
        if required_steps(tier, rules, True, True)["Verify"]:
            state = runtime_module("finish").verify_state(sys.modules[__name__], project, item,
                                                          item_commits(project, item))
            if state[0] != "pass":
                why = state[3] or ("the latest run (%s) failed" % state[1] if state[0] == "fail"
                                   else "no run names it")
                find("ledger", item, "", "no committed verify record for %s on its newest "
                     "code commit (this checks the record, not the result): %s" % (item, why),
                     "%s verify --item %s, then commit the ledger" % (SDLC, item))
        if tier == "1" and not review_records(project, item):
            find("review", item, "", "%s is Tier 1 and has no review file in %s/project/reviews/"
                 % (item, project.docs),
                 "/sdlc-review %s, or %s review %s --role <role> --by <tool>" % (item, SDLC, item))
    return {"base": base, "head": head_sha, "merge_base": merge_base,
            "charter_source": glob_source, "tier1_globs": globs,
            "commits": [c["sha"] for c in commits], "items": items,
            "findings": findings}, None


def print_ci_check(result):
    print("ci-check: %d commit(s), %d item(s) since %s (%s); Tier 1 paths from %s"
          % (len(result["commits"]), len(result["items"]), result["merge_base"][:7],
             result["base"], result["charter_source"]))
    if not result["commits"]:
        print("no commits since %s" % result["base"])
        return
    for f in result["findings"]:
        print("fail  %-8s  %s" % (f["check"], f["detail"]))
        print("      fix: %s" % f["fix"])
    if result["findings"]:
        print("%d finding(s)." % len(result["findings"]))
    else:
        print("Every commit is attributed, every item has its record, and no path is above "
              "its item's tier.")

# ---------------------------------------------------------------- kit control & repair

def _word_count(path):
    return len(read(path).split())


def _active_lines(path):
    return [line.strip() for line in read(path).splitlines()
            if line.strip() and not line.strip().startswith("#")]


def detect_candidate_commands(project):
    """Inspect repo files to suggest candidate commands for blank checks.* stages without
    fabricating or writing them automatically."""
    candidates = {}
    pkg_text = read(project.path("package.json"))
    if pkg_text:
        try:
            pkg = json.loads(pkg_text)
        except ValueError:
            pkg = {}
        scripts = pkg.get("scripts") if isinstance(pkg, dict) else {}
        if isinstance(scripts, dict):
            if "test" in scripts and "no test specified" not in str(scripts.get("test", "")):
                candidates.setdefault("unit", "npm test")
            if "lint" in scripts:
                candidates.setdefault("lint", "npm run lint")
            if "format" in scripts or "fmt" in scripts:
                candidates.setdefault("format", "npm run " + ("format" if "format" in scripts else "fmt"))
            if "typecheck" in scripts or "check-types" in scripts:
                candidates.setdefault("typecheck", "npm run " + ("typecheck" if "typecheck" in scripts else "check-types"))
            if "build" in scripts:
                candidates.setdefault("build", "npm run build")
            if "e2e" in scripts or "test:e2e" in scripts:
                candidates.setdefault("e2e", "npm run " + ("e2e" if "e2e" in scripts else "test:e2e"))
    pyproj = read(project.path("pyproject.toml"))
    reqs = read(project.path("requirements.txt"))
    has_py = bool(pyproj or reqs or os.path.isdir(project.path("tests"))
                  or os.path.isfile(project.path("setup.py")))
    if has_py:
        if "pytest" in pyproj or "pytest" in reqs:
            candidates.setdefault("unit", "pytest")
        elif os.path.isdir(project.path("tests")):
            candidates.setdefault("unit", "python3 -m unittest discover -s tests")
        if "ruff" in pyproj or "ruff" in reqs:
            candidates.setdefault("lint", "ruff check .")
            candidates.setdefault("format", "ruff format --check .")
        if "mypy" in pyproj or "mypy" in reqs:
            candidates.setdefault("typecheck", "mypy .")
    if os.path.isfile(project.path("Cargo.toml")):
        candidates.setdefault("unit", "cargo test")
        candidates.setdefault("lint", "cargo clippy -- -D warnings")
        candidates.setdefault("format", "cargo fmt --check")
        candidates.setdefault("build", "cargo build")
    if os.path.isfile(project.path("go.mod")):
        candidates.setdefault("unit", "go test ./...")
        candidates.setdefault("build", "go build ./...")
    return candidates


def kit_status(project):
    """Structured inventory of the kit installation, active constraints, token reading
    budget, wired harnesses/hooks, and safe mechanical repairs."""
    charter = project.charter
    prof = project.profile or {}
    effort_val, effort_state = choice(labelled(charter, "Default effort mode"), EFFORT)
    if not effort_val and prof.get("effort_mode"):
        effort_val = next((o for o in EFFORT if o.lower() == str(prof["effort_mode"]).lower()), None)
    effort_resolved = effort_val or "Normal"
    ind_policy, ind_tiers, ind_state = independent_review_policy(charter, prof)
    tier_val, tier_state = choice(labelled(charter, "Tier rules"), TIER_RULES)
    if not tier_val and prof.get("tier_rules"):
        tier_val = next((o for o in TIER_RULES if o.lower() == str(prof["tier_rules"]).lower()), None)
    tier_resolved = tier_val or "Standard"
    dec_val, dec_state = choice(labelled(charter, "Decision style"), DECISION_STYLE)
    if not dec_val and prof.get("decision_style"):
        dec_val = next((o for o in DECISION_STYLE if o.lower() == str(prof["decision_style"]).lower()), None)
    dec_resolved = dec_val or "Guide"
    dev_val, dev_state = choice(labelled(charter, "Development method"), DEV_METHOD)
    if not dev_val and prof.get("dev_method"):
        dev_val = next((o for o in DEV_METHOD if o.lower() == str(prof["dev_method"]).lower()), None)
    dev_resolved = dev_val or "Item"
    acq_val, acq_state = choice(labelled(charter, "Acquisition profile"), ACQUISITION)
    if not acq_val and prof.get("acquisition_profile"):
        acq_val = next((o for o in ACQUISITION if o.lower() == str(prof["acquisition_profile"]).lower()), None)
    acq_resolved = acq_val or "Standard"
    disc_policy, disc_state = discovered_defects_policy(charter, prof)
    budget_cell = UNFILLED.sub("", labelled(charter, "Agent budget per tier") or "").strip()
    staleness_cell = labelled(charter, "Staleness threshold") or ""
    staleness_match = re.search(r"[0-9]+", UNFILLED.sub("", staleness_cell))
    staleness_days = int(staleness_match.group(0)) if staleness_match else DEFAULT_STALENESS_DAYS

    has_process_docs = os.path.isfile(
        project.path(os.path.join(project.docs, "process", "00-operating-model.md"))
    )
    doc_profile = project.profile.get("profile") or ("full" if has_process_docs else "compact")
    token_saving = bool(
        project.profile.get("token_saving")
        or (effort_resolved == "Lean" and ind_policy == "none")
    )

    cli_tools = dict((name, bool(shutil.which(name)))
                     for name in ("claude", "codex", "gemini", "jq", "git", "python3"))
    preferred_rev = project.profile.get("preferred_reviewer")
    if preferred_rev not in ("codex", "claude", "gemini"):
        preferred_rev = ("codex" if cli_tools.get("codex") else
                         ("gemini" if cli_tools.get("gemini") else "claude"))

    # Reading budget estimation (words and tokens ~= words * 1.3)
    base_words = (
        _word_count(project.path("AGENTS.md"))
        + _word_count(project.path(os.path.join(project.docs, "CARD.md")))
        + _word_count(project.path(project.charter_path))
    )
    backlog_words = _word_count(project.path(os.path.join(project.docs, "project", "backlog.md")))
    roles_dir = project.path(os.path.join(project.docs, "roles"))
    active_roles = [name for name, on, _ in roles(charter) if on]
    role_words = [
        _word_count(os.path.join(roles_dir, r + ".md"))
        for r in active_roles
        if os.path.isfile(os.path.join(roles_dir, r + ".md"))
    ]
    avg_role_words = int(sum(role_words) / len(role_words)) if role_words else 450
    proc_dir = project.path(os.path.join(project.docs, "process"))
    proc_words = 0
    if os.path.isdir(proc_dir):
        for fname in os.listdir(proc_dir):
            if fname[:2].isdigit() and fname.endswith(".md"):
                proc_words += _word_count(os.path.join(proc_dir, fname))
    if proc_words == 0:
        proc_words = 6200  # standard full process docs baseline for comparison

    t3_words = base_words + backlog_words
    # In Lean or Token-Saving mode, agents stay in CARD.md and use minimum roles (1 pass)
    if effort_resolved == "Lean" or token_saving or doc_profile == "compact":
        t2_words = t3_words + avg_role_words
        t1_words = t3_words + (avg_role_words * 2)
    elif effort_resolved == "Beast":
        t2_words = t3_words + (avg_role_words * 3) + int(proc_words * 0.45)
        t1_words = t3_words + sum(role_words or [avg_role_words * 4]) + proc_words
    else:
        t2_words = t3_words + (avg_role_words * 2) + int(proc_words * 0.25)
        t1_words = t3_words + (avg_role_words * 3) + int(proc_words * 0.6)

    if "2" in ind_tiers:
        t2_words += base_words + avg_role_words
    if "1" in ind_tiers:
        t1_words += base_words + (avg_role_words * 2)

    baseline_t1_words = t3_words + (avg_role_words * 3) + int(proc_words * 0.6) + base_words + (avg_role_words * 2)
    saved_pct = max(0, int(round((1.0 - (float(t1_words) / max(1, baseline_t1_words))) * 100)))

    # Harnesses and pointer files
    pointer_candidates = list(pointer_files(project))
    cursor_rules_dir = project.path(".cursor/rules")
    if os.path.isdir(cursor_rules_dir):
        for name in sorted(os.listdir(cursor_rules_dir)):
            if name.endswith(".mdc"):
                rel = os.path.join(".cursor/rules", name)
                if rel not in pointer_candidates:
                    pointer_candidates.append(rel)
    elif ".cursor/rules/agents.mdc" not in pointer_candidates:
        pointer_candidates.insert(2, ".cursor/rules/agents.mdc")

    harnesses = [{
        "file": "AGENTS.md",
        "exists": os.path.isfile(project.path("AGENTS.md")),
        "wired": os.path.isfile(project.path("AGENTS.md")),
        "role": "contract",
    }]
    for rel in pointer_candidates:
        fpath = project.path(rel)
        exists = os.path.isfile(fpath)
        wired = exists and ("AGENTS.md" in read(fpath))
        if exists or rel in ("CLAUDE.md", "GEMINI.md", ".cursor/rules/agents.mdc", ".github/copilot-instructions.md"):
            harnesses.append({"file": rel, "exists": exists, "wired": wired, "role": "pointer"})

    # Hooks & guards
    claude_hooks_dir = project.path(".claude/hooks")
    claude_hooks = sorted(n for n in os.listdir(claude_hooks_dir) if n.endswith(".sh")) \
        if os.path.isdir(claude_hooks_dir) else []
    pre_commit_path = project.path(".git/hooks/pre-commit")
    commit_msg_path = project.path(".git/hooks/commit-msg")
    hooks_info = {
        "claude_hooks": claude_hooks,
        "claude_settings": os.path.isfile(project.path(".claude/settings.json")),
        "gemini_settings": os.path.isfile(project.path(".gemini/settings.json")),
        "cursor_hooks": os.path.isfile(project.path(".cursor/hooks.json")),
        "git_pre_commit": os.path.isfile(pre_commit_path) and "git-hooks/pre-commit" in read(pre_commit_path),
        "git_commit_msg": os.path.isfile(commit_msg_path) and "git-hooks/commit-msg" in read(commit_msg_path),
    }

    protected_rules = _active_lines(project.path(".ai-sdlc/protected.txt"))
    locked_tests = _active_lines(project.path(".ai-sdlc/test-lock.txt"))
    gate_rules = _active_lines(project.path(".ai-sdlc/gates.txt"))
    bite_active = os.path.isfile(project.path(os.path.join(BITE_DIR, "active.json")))

    # Skills
    skills = set()
    for sdir in (".claude/skills", ".agents/skills"):
        full_sdir = project.path(sdir)
        if os.path.isdir(full_sdir):
            for name in os.listdir(full_sdir):
                if os.path.isdir(os.path.join(full_sdir, name)):
                    skills.add(name)

    cmds = charter_commands(charter)
    blank_stages = [s for s in STAGES if cmds.get(s, "") == ""]
    detected_cmds = detect_candidate_commands(project)

    # Check safe mechanical fixables
    prof_findings = Findings()
    check_profile(project, prof_findings)
    ptr_findings = Findings()
    check_pointer(project, ptr_findings)
    hrn_findings = Findings()
    check_harness_parity(project, hrn_findings)
    shared_skill_findings = [f for f in hrn_findings.items if f["where"] == ".agents/skills"]

    fixable = []
    if prof_findings.items:
        fixable.append({
            "id": "sync-profile",
            "title": "Sync .ai-sdlc/profile.json with charter.md",
            "detail": "; ".join(f["message"] for f in prof_findings.items),
            "level": "fail" if any(f["level"] == "fail" for f in prof_findings.items) else "warn",
        })
    if ptr_findings.items:
        fixable.append({
            "id": "wire-pointer",
            "title": "Wire CLAUDE.md pointer to AGENTS.md",
            "detail": ptr_findings.items[0]["message"],
            "level": "fail",
        })
    if shared_skill_findings:
        fixable.append({
            "id": "shared-skills",
            "title": "Materialise / sync cross-tool skills (.agents/skills/)",
            "detail": "; ".join(f["message"] for f in shared_skill_findings),
            "level": "warn",
        })
    if bite_active:
        fixable.append({
            "id": "restore-bite",
            "title": "Restore interrupted bite backup",
            "detail": "An interrupted `sdlc.py bite` left product files reverted in .ai-sdlc/bite/active.json.",
            "level": "fail",
        })
    if locked_tests:
        fixable.append({
            "id": "unlock-tests",
            "title": "Unlock reproducing test locks (%d locked)" % len(locked_tests),
            "detail": "Locked in .ai-sdlc/test-lock.txt: " + ", ".join(locked_tests[:5]),
            "level": "info",
        })

    available_agent_clis = [k for k in ("claude", "codex", "gemini") if cli_tools.get(k)]
    reviewer_warning = ""
    if ind_tiers and len(available_agent_clis) < 2:
        reviewer_warning = (
            "Independent review is required for Tier %s, but only %d agent CLI (%s) is on PATH. "
            "Install a second CLI (codex/claude/gemini) or set Independent Review to 'none' for single-agent work."
            % (", ".join(sorted(ind_tiers)), len(available_agent_clis),
               ", ".join(available_agent_clis) or "none")
        )

    return {
        "kit_version": project.manifest.get("kit_version") or project.profile.get("kit_version") or "unknown",
        "docs_dir": project.docs,
        "prefix": project.prefix,
        "profile": doc_profile,
        "has_process_docs": has_process_docs,
        "token_saving": token_saving,
        "constraints": {
            "effort_mode": effort_resolved,
            "effort_state": effort_state,
            "independent_review": ind_policy,
            "independent_review_state": ind_state,
            "preferred_reviewer": preferred_rev,
            "tier_rules": tier_resolved,
            "tier_rules_state": tier_state,
            "decision_style": dec_resolved,
            "decision_style_state": dec_state,
            "dev_method": dev_resolved,
            "dev_method_state": dev_state,
            "acquisition_profile": acq_resolved,
            "acquisition_state": acq_state,
            "discovered_defects": disc_policy,
            "discovered_defects_state": disc_state,
            "agent_budget": budget_cell,
            "staleness_days": staleness_days,
        },
        "reading_tokens": {
            "tier3_words": t3_words,
            "tier3_tokens": int(t3_words * 1.3),
            "tier2_words": t2_words,
            "tier2_tokens": int(t2_words * 1.3),
            "tier1_words": t1_words,
            "tier1_tokens": int(t1_words * 1.3),
            "baseline_tier1_tokens": int(baseline_t1_words * 1.3),
            "saved_pct": saved_pct,
        },
        "installed": {
            "harnesses": harnesses,
            "cli_tools": cli_tools,
            "hooks": hooks_info,
            "guards": {
                "protected": protected_rules,
                "test_locks": locked_tests,
                "gates": gate_rules,
                "bite_active": bite_active,
            },
            "skills": sorted(skills),
            "roles": [{"name": n, "active": on, "reason": UNFILLED.sub("", r).strip()}
                      for n, on, r in roles(charter)],
            "commands": cmds,
            "blank_stages": blank_stages,
            "detected_commands": detected_cmds,
        },
        "fixable": fixable,
        "reviewer_warning": reviewer_warning,
    }


def _set_charter_row(text, label, formatted_value, section="## Risk defaults"):
    """Replace or insert a `| **Label** | value |` row in charter.md (a new row goes at the
    end of the first table under `section`, or at the top of Risk defaults)."""
    lines = text.splitlines()
    target_cell = "**%s**" % label
    replaced = False
    for idx, line in enumerate(lines):
        cells = split_row(line)
        if cells and len(cells) >= 2 and cells[0] == target_cell:
            lines[idx] = "| **%s** | %s |" % (label, formatted_value)
            replaced = True
            break
    if not replaced and section != "## Risk defaults":
        for idx, line in enumerate(lines):
            if line.strip() == section:
                j = idx + 1
                while j < len(lines) and not lines[j].strip().startswith("|"):
                    if lines[j].startswith("## "):
                        break
                    j += 1
                if j < len(lines) and lines[j].strip().startswith("|"):
                    while j < len(lines) and lines[j].strip().startswith("|"):
                        j += 1
                    lines.insert(j, "| **%s** | %s |" % (label, formatted_value))
                    replaced = True
                break
    if not replaced:
        # Insert at top of Risk defaults table if present
        for idx, line in enumerate(lines):
            if line.strip() == "## Risk defaults":
                for j in range(idx + 1, min(idx + 6, len(lines))):
                    if lines[j].strip().startswith("| ---"):
                        lines.insert(j + 1, "| **%s** | %s |" % (label, formatted_value))
                        replaced = True
                        break
                break
        if not replaced:
            lines.append("| **%s** | %s |" % (label, formatted_value))
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _set_check_row(text, stage, command):
    """Update a `| `checks.<stage>` | ... |` row in charter.md."""
    lines = text.splitlines()
    target = "`checks.%s`" % stage
    clean_cmd = re.sub(r"[\r\n]+", " ", str(command or "").strip()).replace("`", "")
    val_str = "absent" if clean_cmd.lower() == "absent" else (
        "`%s`" % clean_cmd.replace("|", "\\|") if clean_cmd else ""
    )
    for idx, line in enumerate(lines):
        cells = split_row(line)
        if cells and len(cells) >= 2 and cells[0] == target:
            lines[idx] = "| `checks.%s` | %s |" % (stage, val_str)
            break
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def sync_profile(project, extra=None):
    """Synchronise .ai-sdlc/profile.json with charter.md and manifest.json."""
    profile_path = project.path(".ai-sdlc/profile.json")
    data = dict(project.profile) if project.profile else {}
    data["schema"] = 2
    if project.manifest.get("kit_version"):
        data["kit_version"] = project.manifest["kit_version"]
    elif "kit_version" not in data:
        data["kit_version"] = "4.0.0"
    data["docs_dir"] = project.docs
    if project.charter_prefix:
        data["prefix"] = project.charter_prefix
    cmds = charter_commands(project.charter)
    data["commands"] = dict((s, "" if cmds.get(s, "") == "absent" else cmds.get(s, ""))
                            for s in STAGES if s in cmds or s in (data.get("commands") or {}))
    for key, label, options, fallback in (
        ("effort_mode", "Default effort mode", EFFORT, "normal"),
        ("acquisition_profile", "Acquisition profile", ACQUISITION, "standard"),
        ("dev_method", "Development method", DEV_METHOD, "item"),
        ("decision_style", "Decision style", DECISION_STYLE, "guide"),
    ):
        val, state = choice(labelled(project.charter, label), options)
        if state == "decided" and val:
            data[key] = val.lower()
        elif key not in data:
            data[key] = fallback
    ticked = sorted(name for name, on, _ in roles(project.charter) if on)
    if ticked:
        data["roles"] = ticked
    if extra:
        for k, v in extra.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
    folder = os.path.dirname(profile_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(profile_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    project.__init__(project.root)
    return data


def configure_kit(project, changes):
    """Apply user-selected constraint changes to charter.md and .ai-sdlc/profile.json.
    Never modifies kit-owned files tracked in manifest.json."""
    text = project.charter or ""
    extra_profile = {}
    applied = []

    if "token_saving" in changes and changes["token_saving"] is not None:
        ts = changes["token_saving"]
        on = ts in (True, "on", "true", "1", 1)
        if on:
            prev_effort, _ = choice(labelled(text, "Default effort mode"), EFFORT)
            prev_ind, _, _ = independent_review_policy(text, project.profile or {})
            prev_tier, _ = choice(labelled(text, "Tier rules"), TIER_RULES)
            prev_budget = UNFILLED.sub("", labelled(text, "Agent budget per tier") or "").strip()
            existing_prev = (project.profile or {}).get("pre_token_saving") or {}
            if not (project.profile or {}).get("token_saving"):
                extra_profile["pre_token_saving"] = {
                    "effort_mode": prev_effort or existing_prev.get("effort_mode") or "Normal",
                    "independent_review": prev_ind or existing_prev.get("independent_review") or "none",
                    "tier_rules": prev_tier or existing_prev.get("tier_rules") or "Standard",
                    "agent_budget": prev_budget or existing_prev.get("agent_budget") or (
                        "Tier 3: 50k tokens, 10 min; Tier 2: 300k tokens, 45 min; Tier 1: 1.5M tokens, 3 h"
                    ),
                }
            text = _set_charter_row(text, "Default effort mode", "`Lean`")
            text = _set_charter_row(text, "Independent review required for", "`none`")
            text = _set_charter_row(text, "Tier rules", "`Standard`")
            text = _set_charter_row(
                text, "Agent budget per tier",
                "Tier 3: 5k tokens, 5 min; Tier 2: 15k tokens, 15 min; Tier 1: 40k tokens, 45 min"
            )
            extra_profile["token_saving"] = True
            extra_profile["effort_mode"] = "lean"
            extra_profile["independent_review"] = "none"
            extra_profile["tier_rules"] = "standard"
            extra_profile["profile"] = "compact"
            applied.append("token_saving=on (Lean, single-agent review, Standard tier rules, compact budget)")
        else:
            prev = (project.profile or {}).get("pre_token_saving") or {}
            restored_effort = prev.get("effort_mode") or "Normal"
            if restored_effort == "Lean":
                restored_effort = "Normal"
            restored_ind = prev.get("independent_review") or "none"
            restored_tier = prev.get("tier_rules") or "Standard"
            restored_budget = prev.get("agent_budget") or (
                "Tier 3: 50k tokens, 10 min; Tier 2: 300k tokens, 45 min; Tier 1: 1.5M tokens, 3 h"
            )
            text = _set_charter_row(text, "Default effort mode", "`%s`" % restored_effort)
            text = _set_charter_row(text, "Independent review required for", "`%s`" % restored_ind)
            text = _set_charter_row(text, "Tier rules", "`%s`" % restored_tier)
            text = _set_charter_row(text, "Agent budget per tier", restored_budget)
            has_proc = os.path.isfile(
                project.path(os.path.join(project.docs, "process", "00-operating-model.md"))
            )
            extra_profile["token_saving"] = False
            extra_profile["effort_mode"] = restored_effort.lower()
            extra_profile["independent_review"] = restored_ind
            extra_profile["tier_rules"] = restored_tier.lower()
            extra_profile["profile"] = "full" if has_proc else "compact"
            extra_profile["pre_token_saving"] = None
            applied.append("token_saving=off (%s effort restored)" % restored_effort)

    if changes.get("effort"):
        val = next((o for o in EFFORT if o.lower() == str(changes["effort"]).strip().lower()), None)
        if not val:
            return None, "effort must be one of: %s" % ", ".join(EFFORT)
        text = _set_charter_row(text, "Default effort mode", "`%s`" % val)
        extra_profile["effort_mode"] = val.lower()
        if val != "Lean":
            extra_profile["token_saving"] = False
        applied.append("Default effort mode=%s" % val)

    if changes.get("independent_review"):
        raw = str(changes["independent_review"]).strip().lower()
        mapping = {
            "none": ("none", "`none`"),
            "off": ("none", "`none`"),
            "tier1": ("Tier 1", "`Tier 1`"),
            "tier 1": ("Tier 1", "`Tier 1`"),
            "tier1-2": ("Tier 1 and 2", "`Tier 1 and 2`"),
            "tier 1 and 2": ("Tier 1 and 2", "`Tier 1 and 2`"),
        }
        if raw not in mapping:
            return None, "independent_review must be none, Tier 1, or Tier 1 and 2"
        label_val, cell_val = mapping[raw]
        text = _set_charter_row(text, "Independent review required for", cell_val)
        extra_profile["independent_review"] = label_val
        if label_val != "none":
            extra_profile["token_saving"] = False
        applied.append("Independent review required for=%s" % label_val)

    if changes.get("tier_rules"):
        val = next((o for o in TIER_RULES if o.lower() == str(changes["tier_rules"]).strip().lower()), None)
        if not val:
            return None, "tier_rules must be one of: %s" % ", ".join(TIER_RULES)
        text = _set_charter_row(text, "Tier rules", "`%s`" % val)
        extra_profile["tier_rules"] = val.lower()
        applied.append("Tier rules=%s" % val)

    if changes.get("decision_style"):
        val = next((o for o in DECISION_STYLE if o.lower() == str(changes["decision_style"]).strip().lower()), None)
        if not val:
            return None, "decision_style must be one of: %s" % ", ".join(DECISION_STYLE)
        text = _set_charter_row(text, "Decision style", "`%s`" % val)
        extra_profile["decision_style"] = val.lower()
        applied.append("Decision style=%s" % val)

    if changes.get("slop_filter") in ("off", "on", "strict"):
        text = _set_charter_row(text, "Slop filter", "`%s`" % changes["slop_filter"])
        applied.append("Slop filter=%s" % changes["slop_filter"])

    if changes.get("specs") in ("on", "off"):
        text = _set_charter_row(text, "Specs", "`%s`" % changes["specs"])
        if changes["specs"] == "on":
            os.makedirs(project.path(os.path.join(project.docs, "project", "specs", "changes")), exist_ok=True)
        applied.append("Specs=%s" % changes["specs"])

    if changes.get("dev_method"):
        val = next((o for o in DEV_METHOD if o.lower() == str(changes["dev_method"]).strip().lower()), None)
        if not val:
            return None, "dev_method must be one of: %s" % ", ".join(DEV_METHOD)
        text = _set_charter_row(text, "Development method", "`%s`" % val)
        extra_profile["dev_method"] = val.lower()
        applied.append("Development method=%s" % val)

    if changes.get("acquisition_profile"):
        val = next((o for o in ACQUISITION if o.lower() == str(changes["acquisition_profile"]).strip().lower()), None)
        if not val:
            return None, "acquisition_profile must be one of: %s" % ", ".join(ACQUISITION)
        text = _set_charter_row(text, "Acquisition profile", "`%s`" % val)
        extra_profile["acquisition_profile"] = val.lower()
        applied.append("Acquisition profile=%s" % val)

    if changes.get("discovered_defects"):
        raw_dd = str(changes["discovered_defects"]).strip().lower()
        dd_map = {
            "parked": "Parked",
            "auto-ready-bite": "Auto-Ready (bite)",
            "auto-ready (bite)": "Auto-Ready (bite)",
            "auto": "Auto-Ready (bite)",
        }
        if raw_dd not in dd_map:
            return None, "discovered_defects must be Parked or Auto-Ready (bite)"
        dd_val = dd_map[raw_dd]
        text = _set_charter_row(text, "Discovered defects", "`%s`" % dd_val)
        extra_profile["discovered_defects"] = dd_val
        applied.append("Discovered defects=%s" % dd_val)

    if changes.get("worktree_scripts") is not None:
        claims_mod = runtime_module("claims")
        raw_ws = re.sub(r"[\r\n]+", " ", str(changes["worktree_scripts"])).strip()
        conf = claims_mod.parse_worktree_scripts(raw_ws)
        if conf["error"]:
            return None, conf["error"]
        if not (conf["setup"] or conf["teardown"]):
            cell_ws = "none"
        else:
            parts = [k + ": " + conf[k] for k in ("setup", "teardown") if conf[k]]
            if conf["port_base"] != claims_mod.DEFAULT_PORT_BASE:
                parts.append("port: %d" % conf["port_base"])
            cell_ws = "; ".join(parts).replace("|", "\\|")
        text = _set_charter_row(text, claims_mod.WORKTREE_SCRIPTS_LABEL, cell_ws, section="## Concurrency")
        applied.append("Worktree scripts=%s" % cell_ws.replace("\\|", "|"))

    if changes.get("preferred_reviewer"):
        rev = str(changes["preferred_reviewer"]).strip().lower()
        if rev not in ("codex", "claude", "gemini"):
            return None, "preferred_reviewer must be codex, claude, or gemini"
        extra_profile["preferred_reviewer"] = rev
        applied.append("preferred_reviewer=%s" % rev)

    if changes.get("checks") and isinstance(changes["checks"], dict):
        for stage, cmd in sorted(changes["checks"].items()):
            stage_clean = stage.replace("checks.", "").strip()
            if stage_clean not in STAGES:
                return None, "unknown check stage: %s" % stage
            text = _set_check_row(text, stage_clean, str(cmd))
            applied.append("checks.%s=%s" % (stage_clean, cmd))

    if changes.get("allow_extension"):
        reg_mod = runtime_module("registry")
        cell = labelled(text, "Extensions allowed") or ""
        have = sorted(reg_mod.parse_allowed(cell))
        for ext_id in changes["allow_extension"]:
            if not reg_mod.ID_RE.match(str(ext_id)):
                return None, "--allow-extension %r is not an extension id" % ext_id
            if ext_id not in have:
                have.append(ext_id)
        text = _set_charter_row(text, "Extensions allowed",
                                ", ".join("`%s`" % i for i in have))
        applied.append("Extensions allowed=%s (takes effect once this charter change is on "
                       "the default branch)" % ", ".join(have))

    if changes.get("notify_webhook"):
        name = str(changes["notify_webhook"]).strip()
        if name.lower() == "off":
            text = _set_charter_row(text, "Notify webhook", "off")
            applied.append("Notify webhook=off")
        else:
            env_re = runtime_module("notify").ENV_RE
            if not env_re.match(name):
                return None, ("--notify-webhook takes the name of an environment variable "
                              "matching ^NUHUT_[A-Z0-9_]{1,40}$ (e.g. NUHUT_WEBHOOK_URL), "
                              "never the URL itself")
            text = _set_charter_row(text, "Notify webhook", "`%s`" % name)
            applied.append("Notify webhook=%s (takes effect once this charter change is on the "
                           "default branch; set %s where the commands run)" % (name, name))

    charter_full = project.path(project.charter_path)
    charter_dir = os.path.dirname(charter_full)
    if charter_dir:
        os.makedirs(charter_dir, exist_ok=True)
    if text:
        with open(charter_full, "w", encoding="utf-8") as handle:
            handle.write(text)
        project.charter = text
    sync_profile(project, extra_profile)
    return {"applied": applied, "kit": kit_status(project)}, None


def sync_shared_skills(project):
    """Materialise or sync .agents/skills/ from .claude/commands/ and .claude/skills/,
    updating .ai-sdlc/manifest.json without overwriting user-modified files."""
    manifest_path = project.path(".ai-sdlc/manifest.json")
    manifest = dict(project.manifest) if project.manifest else {}
    managed = dict(manifest.get("files") or {})
    written = []

    def can_write(rel, dest):
        if not os.path.isfile(dest):
            return True
        if rel not in managed:
            return False
        try:
            with open(dest, "rb") as handle:
                return hashlib.sha256(handle.read()).hexdigest() == managed[rel]
        except (IOError, OSError):
            return False

    def write_managed(rel, dest, content_bytes):
        digest = hashlib.sha256(content_bytes).hexdigest()
        if os.path.isfile(dest):
            try:
                with open(dest, "rb") as handle:
                    if handle.read() == content_bytes:
                        if managed.get(rel) != digest:
                            managed[rel] = digest
                            written.append(rel)
                        return
            except (IOError, OSError):
                pass
        if not can_write(rel, dest):
            return
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(dest, "wb") as handle:
            handle.write(content_bytes)
        managed[rel] = digest
        written.append(rel)

    cmds_dir = project.path(".claude/commands")
    if os.path.isdir(cmds_dir):
        for name in LOOP_SKILLS:
            src_cmd = os.path.join(cmds_dir, name + ".md")
            if not os.path.isfile(src_cmd):
                continue
            skill_text = command_to_skill_text(name, read(src_cmd))
            rel = ".agents/skills/%s/SKILL.md" % name
            write_managed(rel, project.path(rel), skill_text.encode("utf-8"))

    claude_skills = project.path(".claude/skills")
    if os.path.isdir(claude_skills):
        for name in sorted(os.listdir(claude_skills)):
            src_skill_dir = os.path.join(claude_skills, name)
            if not name.startswith("sdlc-") or not os.path.isdir(src_skill_dir):
                continue
            for folder, _, files in os.walk(src_skill_dir):
                for fname in sorted(files):
                    src_file = os.path.join(folder, fname)
                    sub_rel = os.path.relpath(src_file, src_skill_dir).replace(os.sep, "/")
                    claude_rel = ".claude/skills/%s/%s" % (name, sub_rel)
                    if managed and claude_rel not in managed:
                        continue
                    rel = ".agents/skills/%s/%s" % (name, sub_rel)
                    try:
                        with open(src_file, "rb") as handle:
                            raw = handle.read()
                    except (IOError, OSError):
                        continue
                    write_managed(rel, project.path(rel), raw)

    if written and os.path.isfile(manifest_path):
        manifest["files"] = dict(sorted(managed.items()))
        with open(manifest_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return written


def fix_kit(project, action="all", opts=None):
    """Run safe, non-fabricating mechanical repairs on the kit setup."""
    opts = opts or {}
    repaired = []

    if action in ("all", "sync-profile"):
        sync_profile(project)
        repaired.append("synced .ai-sdlc/profile.json with charter.md")

    if action in ("all", "wire-pointer"):
        ptr_findings = Findings()
        check_pointer(project, ptr_findings)
        target_rel = opts.get("file") or "CLAUDE.md"
        if ptr_findings.items or action == "wire-pointer":
            allowed_pointers = set(pointer_files(project, builtin_only=True)) | set(
                r for r in (project.profile.get("harnesses") or []) if isinstance(r, str)
            )
            root_real = os.path.realpath(project.root)
            targets = [target_rel]
            for rel in project.profile.get("harnesses") or []:
                if isinstance(rel, str) and rel not in targets:
                    targets.append(rel)
            for rel in targets:
                if not isinstance(rel, str) or rel.startswith(("/", "\\")) or ".." in rel.split("/"):
                    continue
                if rel not in allowed_pointers and not (rel.startswith(".cursor/rules/") and rel.endswith(".mdc")):
                    continue
                fpath = project.path(rel)
                if not (os.path.realpath(fpath) == root_real
                        or os.path.realpath(fpath).startswith(root_real + os.sep)):
                    continue
                existing = read(fpath)
                if "AGENTS.md" not in existing:
                    parent = os.path.dirname(fpath)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    pointer_line = "\nRead and follow [AGENTS.md](AGENTS.md).\n" if existing else \
                        "Read and follow [AGENTS.md](AGENTS.md).\n"
                    with open(fpath, "w", encoding="utf-8") as handle:
                        handle.write(existing + pointer_line)
                    repaired.append("wired %s -> AGENTS.md" % rel)

    if action in ("all", "restore-bite"):
        if os.path.isfile(project.path(os.path.join(BITE_DIR, "active.json"))):
            restored = bite_restore(project)
            repaired.append("restored bite backup (%d file(s))" % len(restored))

    if action == "shared-skills" or action == "all":
        hrn_findings = Findings()
        check_harness_parity(project, hrn_findings)
        need_shared = any(f["where"] == ".agents/skills" for f in hrn_findings.items)
        if action == "shared-skills" or need_shared:
            synced = sync_shared_skills(project)
            if synced:
                repaired.append("synced %d cross-tool skill file(s) in .agents/skills/" % len(synced))

    if action == "unlock-tests" or (action == "all" and opts.get("unlock_tests")):
        lock_path = project.path(".ai-sdlc/test-lock.txt")
        if os.path.isfile(lock_path):
            target_test = opts.get("test")
            kept = []
            removed = 0
            for line in read(lock_path).splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    kept.append(line)
                elif target_test and stripped != target_test:
                    kept.append(line)
                else:
                    removed += 1
            with open(lock_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(kept) + "\n")
            repaired.append("unlocked %d test lock(s) in .ai-sdlc/test-lock.txt" % removed)

    project.__init__(project.root)
    return {"repaired": repaired, "kit": kit_status(project), "findings": doctor(project)}


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
    assert independent_review_policy("") == ("none", set(), "blank")
    assert independent_review_policy("| **Independent review required for** | `none` · `Tier 1` · `Tier 1 and 2` |") == \
        ("none", set(), "undecided")
    assert independent_review_policy("| **Independent review required for** | `none` |") == \
        ("none", set(), "decided")
    assert independent_review_policy("| **Independent review required for** | `Tier 1` |") == \
        ("Tier 1", set(["1"]), "decided")
    assert independent_review_policy("| **Independent review required for** | `Tier 1 and 2` |") == \
        ("Tier 1 and 2", set(["1", "2"]), "decided")
    updated_c = _set_charter_row(charter, "Default effort mode", "`Lean`")
    assert choice(labelled(updated_c, "Default effort mode"), EFFORT) == ("Lean", "decided")
    updated_chk = _set_check_row(charter, "lint", "ruff check .")
    assert charter_commands(updated_chk)["lint"] == "ruff check ."
    norm_it = _shards_mod.normalize_item({
        "id": "ACME-007", "title": "Fix parser", "type": "bug", "tier": "2",
        "effort": "beast", "status": "next", "touch": "./src/a.py, tests/t.py",
        "depends": "ACME-001, ACME-002",
    }, today="2026-04-01")
    assert norm_it["type"] == "defect" and norm_it["effort"] == "Beast"
    assert norm_it["status"] == "Ready" and norm_it["touch"] == ["src/a.py", "tests/t.py"]
    assert norm_it["depends"] == ["ACME-001", "ACME-002"]
    assert discovered_defects_policy("") == ("Parked", "blank")
    assert discovered_defects_policy("| **Discovered defects** | `Parked` · `Auto-Ready (bite)` |") == ("Parked", "undecided")
    assert discovered_defects_policy("| **Discovered defects** | `Auto-Ready (bite)` |") == ("Auto-Ready (bite)", "decided")
    print("sdlc runtime self-test passed")


# ---------------------------------------------------------------- entry

def default_root():
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.dirname(os.path.dirname(here))
    if os.path.basename(here) == "bin" and os.path.basename(os.path.dirname(here)) == ".ai-sdlc":
        return candidate
    return os.getcwd()


def run_audit(project, lens_mod, opts):
    """Run the charter's scan command in its JSON form, keep the raw output and the parsed
    vulnerabilities under .ai-sdlc/evidence/<stamp>-audit/. The kit never fetches advisory
    data itself; the project's own scanner does."""
    scan = charter_commands(project.charter).get("scan", "")
    cmd, parser = lens_mod.audit_command(scan)
    if not cmd:
        sys.stderr.write("audit: the charter's scan stage (%r) is not a scanner this command can read "
                         "(npm/pnpm/yarn audit, pip-audit, osv-scanner, cargo audit, govulncheck)\n" % scan)
        return 2
    folder = evidence_dir(project, "-audit")
    started = time.time()
    code, out_b, err_b, timed_out = _run_isolated(
        cmd, cwd=project.root, timeout=opts.timeout, shell=True
    )
    if timed_out:
        out, err, code = "", "timed out after %ds" % opts.timeout, None
    else:
        out = out_b.decode("utf-8", "replace")
        err = err_b.decode("utf-8", "replace")
    vulns = lens_mod.parse_audit(parser, out) if out else None
    clean, _ = redact(out + ("\n" + err if err else ""))
    with open(os.path.join(folder, "audit.log"), "w", encoding="utf-8") as handle:
        handle.write(clean)
    record = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "command": cmd, "tool": parser, "exit_code": code, "seconds": round(time.time() - started, 2),
              "git_head": project.git("rev-parse", "--short", "HEAD").strip(),
              "vulns": vulns or [], "error": "" if vulns is not None else "could not read the scanner's JSON output"}
    with open(os.path.join(folder, "audit.json"), "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    if opts.json:
        print(json.dumps(record, indent=2))
    else:
        by = {}
        for v in record["vulns"]:
            by[v["severity"]] = by.get(v["severity"], 0) + 1
        parts = ", ".join("%d %s" % (n, k) for k, n in sorted(by.items(), key=lambda x: lens_mod.SEVERITY_RANK.get(x[0], 5)))
        print("audit: %s -> %d vulnerable package(s)%s" % (cmd, len(record["vulns"]), " (" + parts + ")" if parts else ""))
        if record["error"]:
            print("audit: " + record["error"] + "; raw output kept in " + os.path.relpath(folder, project.root))
    worst = any(v["severity"] in ("critical", "high") for v in record["vulns"])
    return 1 if (opts.strict and worst) else 0


def run_standards(project, lens_mod, opts):
    """`lens --area standards`: report the conventions; --write drafts the page once."""
    std = lens_mod.standards(project)
    rel = os.path.join(project.docs, "project", "standards.md").replace(os.sep, "/")
    if opts.write:
        target = project.path(rel)
        if os.path.exists(target):
            print("standards: %s exists; not overwriting it. Compare by hand with "
                  "`sdlc.py lens --area standards`." % rel)
            return 1
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(lens_mod.standards_markdown(std))
        print("standards: drafted %s; review it before anyone relies on it" % rel)
        return 0
    if opts.json:
        print(json.dumps(std, indent=2))
        return 0
    print("Standards (%d source file(s) sampled)" % std["files_scanned"])
    print("  tooling      %s" % (", ".join("%s (%s)" % (t["tool"], t["path"]) for t in std["tooling"]) or "none found"))
    for n in std["naming"]:
        print("  naming       %-22s functions %s, types %s%s" % (
            n["language"], n["functions"] or "unclear", n["classes"] or "unclear",
            (", files " + n["files"]) if n["files"] else ""))
    t = std["tests"]
    print("  tests        %s, %d file(s)%s" % (t["layout"], t["count"],
                                               (" · " + ", ".join(t["patterns"])) if t["patterns"] else ""))
    for i in std["imports"]:
        print("  imports      %-22s %s (%d absolute, %d relative, %d alias)" % (
            i["language"], i["style"], i["absolute"], i["relative"], i["alias"]))
    c = std["commits"]
    print("  commits      %s (%d of %d conventional)" % (c["convention"], c["conventional"], c["sampled"]))
    print("Read-only. Draft %s with: python3 .ai-sdlc/bin/sdlc.py lens --area standards --write" % rel)
    return 0


def print_lens(data, area=None):
    s = data["summary"]

    def show(a):
        return area in (None, a)
    if show("stack"):
        print("Stack")
        for g in data["stack"]["groups"]:
            print("  %-16s %s" % (g["label"], ", ".join(g["values"])))
    if show("deps"):
        print("Dependencies: %d across %d manifest(s)" % (s["stack"]["dependencies"], s["stack"]["manifests"]))
        for m in data["dependencies"]["manifests"]:
            print("  %-40s %-7s %4d  lockfile: %s" % (m["path"], m["kind"], m["count"], m["lockfile"] or "none"))
    if show("build"):
        b = data["build"]
        failing = s["build"]["failing"]
        print("Build (verify run %s): %s" % (b["run"] or "none", ", ".join(failing) + " failing" if failing else "nothing failing"))
        for st in b["stages"]:
            for e in st["errors"][:10]:
                print("  %-10s %s%s  %s" % (st["stage"], e["file"], ":%d" % e["line"] if e["line"] else "", e["message"]))
    if show("security"):
        print("Security: %d fail, %d warn%s" % (s["security"]["fail"], s["security"]["warn"],
              "" if s["security"]["audited"] else " (no audit yet: python3 .ai-sdlc/bin/sdlc.py audit)"))
        for x in data["security"][:30]:
            print("  %-4s %-10s %s  %s" % (x["level"], x["area"], x["title"], x["detail"]))
    if show("deploy"):
        d = s["deploy"]
        print("Deploy: %s · %d workflow(s), %d deploying · %d Dockerfile(s) · %d compose service(s)" % (
            ", ".join(d["platforms"]) or "no platform evidence", d["workflows"], d["deploying_workflows"],
            d["dockerfiles"], d["compose_services"]))
    if show("env"):
        e = data["env"]
        print("Env: %d variable(s), %d used but not in a template" % (len(e["variables"]), len(e["missing_from_template"])))
        for n in e["missing_from_template"][:20]:
            print("  missing from template: %s" % n)
    if show("agents"):
        a = data["agents"]
        print("Agents: %s" % ", ".join("%d %s" % (sum(v.values()), k) for k, v in sorted(a["counts"].items())))
        print("  always-loaded skill descriptions: ~%d tokens; kit files: %d managed, %d modified, %d missing" % (
            a["always_loaded_tokens"], a["kit_files"]["managed"], a["kit_files"]["modified"], a["kit_files"]["missing"]))
        for o in a["other_kits"]:
            print("  other kit: %s (%s)" % (o["name"], o["path"]))
        for i in a["issues"]:
            print("  %s  %s  %s" % (i["level"], i["title"], i["detail"]))


MAIN_HELP = """usage: python3 .ai-sdlc/bin/sdlc.py <command> [options]     (every command: <command> -h)

The mechanical half of the Nuhut process: checks, evidence, the viewer, claims and specs.

Start here
  status              missing setup, your items' next step, Parked on you, Ready     status --json

Records and checks
  doctor              audit the records: stale rows, unproven Verified claims, gaps   doctor --strict
  verify              run the charter's checks in order and keep the evidence        verify --item ACME-12
  finish <ID>         close an item: evidence, review, worklog draft, status          finish ACME-12
  approvals <ID>      merge approvals from the item branch's GitHub PR reviews       approvals ACME-12
  bite <test cmd>     do the tests fail without the change and pass with it?          bite npm test
  plan-check <ID>     does the branch's diff match the plan's Files that change?     plan-check ACME-12
  ci-check            PR range: trailers, ledger record, Tier 1 review, tier floor    ci-check --base main

Viewer and reports
  view                the project as an interactive page; --serve keeps it live      view --serve
  lens                stack, deps, build, security, deploy, env, agents, standards   lens --area security
  audit               run the dependency scanner and keep the vulnerable packages    audit
  metrics             process measures from the records and git                       metrics

Work items and agents
  item                manage sharded items: add, set, show, list                      item add --title "Fix auth"
  hotfix <ID>         mark an item a hotfix (same as item set <ID> --hotfix)          hotfix ACME-12
  bug "<title>"       report a defect with its severity; agents see S0-S2 at start   bug "Login 500s" --severity S1
  next-id             allocate the next work item or ADR ID (--sync-refs for CAS)     next-id --sync-refs
  render              materialize backlog.md and worklog.md from shards (--check)     render --check
  merge-shard         git merge driver for items/*.json (fix merge-driver sets it)    fix merge-driver
  claim <ID>          take an item: atomic claim, its branch and its own worktree     claim ACME-12
  unclaim <ID>        free it (--remove-worktree to clean up; release is the old name) unclaim ACME-12
  claims / parallel   who holds what / which Ready items can run side by side        parallel
  dispatch            execute conflict-free waves of Ready items across workers       dispatch --workers 2 --by claude
  trailers <ID>       the Work-Item, Agent and Model commit trailers                   trailers ACME-12
  sync                behind the remote or the default branch? conflicts? next command  sync --fetch
  review <ID>         one role's review of the diff, by another model family          review ACME-12 --role security --by codex
  log                 draft worklog lines from commits and verify runs                log --since main --write
  mcp                 the records as read-only MCP tools over stdio                   mcp --allow-verify

Releases and deploys
  deploy record       write releases/<version>.json and a deploys.jsonl line          deploy record --version 1.4.0 --env prod
  deploy list         which version runs in each environment                          deploy list

Specs (when the charter's Specs row is on)
  spec                list, show, validate, apply <ID> [--write]                       spec apply ACME-12 --write

Writing (the charter's Slop filter row: off, on, strict)
  slop [paths]        phrasings that read as machine-written, by line, with a fix      slop --strict docs/

Setup
  config              see or change the charter's constraints                          config --specs on
  notify              the Notify webhook: its setup; --test sends a test event         notify --test
  fix                 repair setup drift; preview record repairs (--apply writes)      fix rotate-worklog
  ext                 extensions: list, add, update, remove, search, validate, package ext search lint
"""
MAIN_HELP_FOOTER = """
Options: --root <dir> runs against another project; --selftest checks the runtime itself.
Guides: docs/cli.md, docs/viewer.md, docs/multi-agent.md, docs/specs.md and docs/extensions.md
in the kit repository.
"""


EXAMPLES = {
    "status": ["status                   # what to do next on this branch", "status --json"],
    "doctor": ["doctor", "doctor --strict          # exit 1 on a fail-level finding (CI)", "doctor --json",
               "doctor --baseline        # accept today's findings once; only new ones show",
               "doctor --all             # include the accepted ones"],
    "verify": ["verify --item ACME-12     # the ledger rows name the item", "verify --parallel",
               "verify --stage lint,unit", "verify --timeout 900"],
    "finish": ["finish ACME-12", "finish ACME-12 --dry-run",
               "finish ACME-12 --waive verify --by Sam --reason \"no staging DB here\""],
    "approvals": ["approvals ACME-12        # exit 0 when the tier's approvals are on the PR head",
                  "approvals ACME-12 --json"],
    "guard": ["guard start              # SessionStart hook (reads the hook JSON on stdin)",
              "guard stop               # Stop hook"],
    "plan-check": ["plan-check ACME-12", "plan-check ACME-12 --base main --strict",
                   "plan-check ACME-12 --pre"],
    "ci-check": ["ci-check --base main", "ci-check --base origin/main --head event --charter-ref origin/main",
                 "ci-check --json"],
    "view": ["view                     # write .ai-sdlc/view/index.html and open it",
             "view --serve             # live page on 127.0.0.1",
             "view --serve --github    # also open GitHub issues and PRs",
             "view --serve --host tailscale  # reach it from your tailnet, read-only, key in the link", "view --export-html report.html"],
    "metrics": ["metrics", "metrics --json", "metrics --env staging   # DORA measures for another environment"],
    "log": ["log --since main", "log --since main --id ACME-12 --write"],
    "trailers": ["trailers ACME-12 --agent claude"],
    "review": ["review ACME-12 --role security --by codex",
               "review ACME-12 --role architect --by gemini --stage design"],
    "bite": ["bite npm test", "bite --restore"],
    "config": ["config                   # show the constraints", "config --effort Lean --independent-review tier1",
               "config --specs on", "config --slop-filter strict", "config --set-check unit='npm test'",
               "config --allow-extension lint-pack   # let an extension's code run once merged",
               "config --worktree-scripts 'setup: npm ci; teardown: docker compose down'"],
    "ext": ["ext list", "ext add https://github.com/<owner>/<repo>.git --ref v1.0.0",
            "ext add ../my-extension      # a local directory", "ext update lint-pack --dry-run",
            "ext remove lint-pack", "ext search lint", "ext validate ../my-extension",
            "ext package lint-pack --for gemini  # writes dist/extensions/lint-pack/gemini/"],
    "fix": ["fix all", "fix shared-skills", "fix wire-pointer", "fix migrate-shards --apply",
            "fix rotate-worklog          # preview", "fix normalise-status --apply",
            "fix link-evidence --apply"],
    "item": ["item add --title \"Fix empty input\" --type defect --tier 2 --touch src/parser.py",
             "item set ACME-12 --status Ready --effort Lean",
             "item set ACME-12 --hotfix  # finish skips the pre-merge review; a retro review is owed",
             "item list --status Ready --json", "item show ACME-12 --json"],
    "bug": ['bug "Login returns 500 on a long password" --severity S1 --touch "src/auth/**"',
            'bug "Typo on the pricing page" --severity S4 --found-by "user report"'],
    "hotfix": ["hotfix ACME-12           # the same as item set ACME-12 --hotfix",
               "review ACME-12 --role qa --by codex --stage retro  # the retroactive review"],
    "next-id": ["next-id", "next-id --sync-refs --json", "next-id --kind adr"],
    "render": ["render", "render --check"],
    "merge-shard": ["merge-shard BASE OURS THEIRS   # what git runs; set it up with: fix merge-driver"],
    "lens": ["lens", "lens --area build", "lens --area standards --write", "lens --user --json"],
    "audit": ["audit", "audit --strict           # exit 1 on a critical or high vulnerability"],
    "notify": ["notify                   # is the webhook on, which variable, is it set here",
               "notify --test            # send a test event (exit 1 when nothing was sent)",
               "notify --test --ids-only # the same, without the title"],
    "sync": ["sync                     # as of the last fetch", "sync --fetch             # fetch first",
             "sync --fetch --strict    # exit 1 when behind the default branch too (CI, before finish)"],
    "slop": ["slop                     # prose files changed against HEAD",
             "slop README.md docs/", "slop --strict content/   # exit 1 when a file fails (CI)",
             "slop --guide             # the rules", "slop - < draft.md"],
    "spec": ["spec list", "spec validate --strict", "spec apply ACME-12          # dry run",
             "spec apply ACME-12 --write"],
    "claim": ["claim ACME-12", "claim ACME-12 --no-worktree --mark",
              "claim ACME-12 --agent codex --worktree ../acme-12"],
    "unclaim": ["unclaim ACME-12", "unclaim ACME-12 --remove-worktree"],
    "release": ["unclaim ACME-12          # release is deprecated; it still works until 7.0"],
    "deploy": ["deploy record --version 1.4.0 --env staging",
               "deploy record --version 1.4.0 --env prod --by Sam   # promote the same commit",
               "deploy record --version 1.4.1 --env staging --from v1.4.0 --dry-run",
               "deploy list", "deploy list --json"],
    "claims": ["claims", "claims --json"],
    "parallel": ["parallel", "parallel --json"],
    "dispatch": ["dispatch --dry-run", "dispatch --workers 2 --by claude",
                 "dispatch --workers 3 --by codex --reviewer claude --pr"],
    "mcp": ["mcp                      # read-only tools: item_list, item_show, doctor, finish_status, status",
            "mcp --allow-verify       # also the verify tool, which writes evidence"],
}


class _Main(argparse.ArgumentParser):
    """The top-level help, grouped by what you are doing, with an example per command."""

    def format_help(self):
        extra = ["  %-19s %s" % (c.name, c.help) for c in COMMANDS.values() if not c.core]
        if not extra:
            return MAIN_HELP + MAIN_HELP_FOOTER
        # Extension commands are commands like the rest: listed before the footer.
        return MAIN_HELP + "\nExtension commands\n" + "\n".join(extra) + "\n" + MAIN_HELP_FOOTER




def _cmd_merge_shard(project, opts, parser):
    """merge-shard: the nuhut-shard git merge driver (needs no project)."""
    code, message = _shards_mod.merge_shard_files(
        opts.base, opts.ours, opts.theirs, marker_size=max(3, min(opts.marker_size, 64)))
    sys.stderr.write(message + "\n")
    return code


def _cmd_status(project, opts, parser):
    """status: one screen of next actions."""
    status_mod = runtime_module("status")
    data = status_mod.report(sys.modules[__name__], project)
    print(json.dumps(data, indent=2) if opts.json else status_mod.format_report(data))
    return 0


def _cmd_doctor(project, opts, parser):
    """doctor: mechanical checks of the SDLC records."""
    items = doctor(project, use_cache=not getattr(opts, "no_cache", False))
    if opts.baseline:
        kept, dropped, refused = write_baseline(project, items)
        if not opts.json:
            print("doctor-baseline.json: %d finding(s) accepted%s%s" % (
                kept, ", %d fixed one(s) removed" % dropped if dropped else "",
                ". %d finding(s) are new since the baseline and stay visible" % refused
                if refused else ""))
        items = apply_baseline(project, [dict(i, accepted="") for i in items])
    if opts.json:
        print(json.dumps(items, indent=2))
    else:
        print_findings(items, opts.all)
    return 1 if opts.strict and any(i["level"] == "fail" and not i.get("accepted")
                                    for i in items) else 0


def _cmd_approvals(project, opts, parser):
    """approvals: who approved an item's merge, from its PR reviews or the charter."""
    res = runtime_module("finish").approvals(sys.modules[__name__], project, opts.item)
    if res is None:
        sys.stderr.write("approvals: %s is not in the backlog\n" % opts.item)
        return 2
    if opts.json:
        print(json.dumps(res, indent=2))
    else:
        print("%s · Tier %s" % (opts.item, res["tier"] or "?"))
        print("\n".join(runtime_module("finish").approval_lines(res)))
    return 0 if res["met"] else 1


def _cmd_finish(project, opts, parser):
    """finish and guard: close a work item, or run the finish guard from a hook."""
    finish_mod = runtime_module("finish")
    if opts.command == "guard":
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
        code, message = finish_mod.guard(sys.modules[__name__], project, opts.event,
                                         payload if isinstance(payload, dict) else {})
        if message and opts.event == "start" and code == 0:
            # SessionStart: stdout is what the agent reads as context.
            print(message)
        elif message:
            sys.stderr.write(message + "\n")
        return code
    if opts.waive and not (opts.by and opts.reason):
        parser.error("--waive verify needs --by <name> and --reason \"...\"")
    notes = {}
    if getattr(opts, "from_json", None):
        try:
            raw_j = sys.stdin.read() if opts.from_json == "-" else read(opts.from_json)
            parsed_j = json.loads(raw_j or "{}")
            if not isinstance(parsed_j, dict):
                parser.error("--from-json must contain a JSON object")
            for nk in ("why", "not_done", "discovered", "decisions", "assumptions", "plan", "reviews"):
                if parsed_j.get(nk) is not None:
                    notes[nk] = str(parsed_j[nk])
        except ValueError as exc:
            parser.error("invalid --from-json payload: %s" % exc)
    for nk in ("why", "not_done", "discovered", "decisions", "assumptions", "plan", "reviews"):
        cli_v = getattr(opts, nk, None)
        if cli_v is not None:
            notes[nk] = cli_v
    lines, code = finish_mod.finish(sys.modules[__name__], project, opts.item,
                                    opts.by if opts.waive else None, opts.reason,
                                    opts.dry_run, notes=notes or None)
    if getattr(opts, "json", False):
        owed_list = [ln[5:].strip() for ln in lines if ln.startswith("OWED ")]
        cur_item = _shards_mod.merged_items(project).get(opts.item) or {}
        print(json.dumps({
            "item": opts.item,
            "exit_code": code,
            "finished": code == 0,
            "status": cur_item.get("status", ""),
            "owed": owed_list,
            "lines": lines,
        }, indent=2))
    else:
        print("\n".join(lines))
    return code


def _cmd_notify(project, opts, parser):
    """notify: the Notify webhook's setup, or a test event."""
    notify_mod = runtime_module("notify")
    if not opts.test:
        cfg = notify_mod.config(sys.modules[__name__], project)
        if opts.json:
            print(json.dumps(dict(cfg, set=bool(cfg["env"] and os.environ.get(cfg["env"], "").strip())),
                             indent=2))
        else:
            print("\n".join(notify_mod.status_lines(sys.modules[__name__], project)))
        return 0
    state, message = notify_mod.send(sys.modules[__name__], project, "test",
                                     title="Nuhut webhook test", ids_only=opts.ids_only,
                                     warn=lambda m: None)
    if opts.json:
        print(json.dumps({"state": state, "message": message}, indent=2))
    else:
        print("notify: " + message)
    return 0 if state == "sent" else 1


def _cmd_sync(project, opts, parser):
    """sync: where this checkout stands against its remote."""
    sync_mod = runtime_module("sync")
    how = sync_mod.strategy(labelled(project.charter, "Updating a branch"))
    state = sync_mod.state(project, default_branch(project), opts.fetch)
    if state is None:
        sys.stderr.write("sync: not a git repository here\n")
        return 2
    found = sync_mod.findings(state, how)
    code = sync_mod.exit_code(found, opts.strict)
    if opts.json:
        print(json.dumps({"state": state, "strategy": how, "exit": code, "findings": [
            {"level": level, "text": text, "command": command}
            for level, text, command in found]}, indent=2, sort_keys=True))
    else:
        print("\n".join(sync_mod.report(state, found, how)))
    return code


def _cmd_slop(project, opts, parser):
    """slop: the slop filter."""
    slop_mod = runtime_module("slop")
    if opts.guide:
        print("\n".join(slop_mod.guide()))
        return 0
    charter_mode = slop_mod.mode(project, labelled)
    strict = opts.strict or charter_mode == "strict"
    if opts.paths == ["-"]:
        found, count = slop_mod.scan_text(sys.stdin.read(), "<stdin>")
        results, unread = [("<stdin>", found, count)], []
    else:
        if opts.paths:
            cwd_real = os.path.realpath(os.getcwd())
            base_dir = project.root if opts.root else cwd_real
            files = slop_mod.collect(opts.paths, base_dir)
        else:
            files = slop_mod.changed_prose(project.root)
            if files is None:
                sys.stderr.write("slop: not a git repository here; name the files or "
                                 "directories to scan\n")
                return 2
        results, unread = slop_mod.scan_paths(files, project.root)
    for rel in unread:
        sys.stderr.write("slop: cannot read %s\n" % rel)
    failed = sum(1 for _, found, count in results if slop_mod.verdict(found, count)[0])
    if opts.json:
        print(json.dumps({"mode": charter_mode, "strict": strict, "files": [
            {"file": rel, "words": count, "fails": slop_mod.verdict(found, count)[0],
             "findings": found} for rel, found, count in results]}, indent=2))
    else:
        lines = slop_mod.report(results, strict)[0]
        if not results:
            lines = ["slop: no prose files to scan" + ("" if opts.paths else
                     " (nothing changed; name a file or directory)")]
        print("\n".join(lines))
        if charter_mode == "off" and not opts.strict:
            print("The charter's Slop filter row is off, so this run is advisory. "
                  "Turn it on with: config --slop-filter on|strict")
    if unread and not results:
        return 2
    return 1 if strict and failed else 0


def _cmd_spec(project, opts, parser):
    """spec: living specs."""
    specs_mod = runtime_module("specs")
    if opts.action == "apply":
        if not opts.target:
            sys.stderr.write("spec apply: give the work item ID\n")
            return 2
        steps, error = specs_mod.apply_change(project, opts.target, write=opts.write)
        if error:
            sys.stderr.write("spec apply: %s\n" % error)
            return 1
        if opts.json:
            print(json.dumps({"item": opts.target, "applied": bool(opts.write), "steps": steps}, indent=2))
        else:
            print(("applied:" if opts.write else "would (dry run; add --write):"))
            for s in steps:
                print("  " + s)
        return 0
    data = specs_mod.load(project)
    if opts.action == "validate":
        problems = specs_mod.validate(project, data)
        if opts.json:
            print(json.dumps(problems, indent=2))
        for p in [] if opts.json else problems:
            print("%-4s  %s  %s" % (p["level"], p["where"], p["message"]))
        if not problems and not opts.json:
            print("specs: no problems in %d capability spec(s) and %d change(s)" % (len(data["capabilities"]), len(data["changes"])))
        return 1 if (opts.strict and problems) else 0
    if opts.action == "show":
        spec = next((c for c in data["capabilities"] + data["imported"] if c["capability"] == opts.target), None)
        if not spec:
            sys.stderr.write("spec show: no capability %r\n" % opts.target)
            return 2
        if opts.json:
            print(json.dumps(spec, indent=2))
            return 0
        print("%s (%s) — %s" % (spec["capability"], spec["source"], spec["path"]))
        for r in spec["requirements"]:
            print("  Requirement: %s  (%d scenario%s)" % (r["name"], len(r["scenarios"]), "" if len(r["scenarios"]) == 1 else "s"))
        return 0
    if opts.json:
        print(json.dumps(data, indent=2))
        return 0
    print("specs %s in the charter" % ("on" if specs_mod.enabled(project, labelled) else "off"))
    for c in data["capabilities"] + data["imported"]:
        print("  %-28s %-9s %3d requirement(s)  %s" % (c["capability"], c["source"], len(c["requirements"]), c["path"]))
    for ch in data["changes"]:
        n = dict((k, len(v)) for k, v in ch["sections"].items() if v)
        print("  change %-21s %-9s %s" % (ch["item"], ch["source"], ", ".join("%d %s" % (v, k) for k, v in n.items())))
    return 0


def _cmd_next_id(project, opts, parser):
    """next-id: allocate the next work item or ADR ID."""
    claims_mod = runtime_module("claims")
    res, error = claims_mod.next_id(project, kind=opts.kind, sync_refs=opts.sync_refs)
    if error:
        sys.stderr.write("next-id: %s\n" % error)
        return 1
    if opts.json:
        print(json.dumps(res, indent=2))
    else:
        print(res["id"])
    return 0


def _cmd_render(project, opts, parser):
    """render: backlog.md and worklog.md from the shards."""
    res = _shards_mod.render(project, check_only=opts.check)
    if opts.json:
        print(json.dumps(res, indent=2))
    elif opts.check:
        if res["in_sync"]:
            print("render: backlog.md and worklog.md match shards")
        else:
            print("render: out of sync (%s); run `sdlc.py render`" % ", ".join(res["drift"]))
    else:
        changed = [f["path"] for f in res["files"] if f["changed"]]
        print("render: updated %s" % (", ".join(changed) if changed else "nothing (already in sync)"))
    return 0 if (not opts.check or res["in_sync"]) else 1


def _cmd_item(project, opts, parser):
    """item: manage sharded work items."""
    today_iso = datetime.date.today().isoformat()
    if getattr(opts, "item_id_flag", None) and not opts.target:
        opts.target = opts.item_id_flag
    if opts.action == "list":
        all_items = _shards_mod.merged_items(project)
        tier_filter = set(s.strip() for s in (opts.tier or "").split(",") if s.strip())
        status_filter = _shards_mod.normalize_status(opts.status) if opts.status else ""
        rows_out = []
        for iid in sorted(all_items.keys(), key=id_sort_key):
            it = all_items[iid]
            if status_filter and it["status"] != status_filter:
                continue
            if tier_filter and it["tier"] not in tier_filter:
                continue
            rows_out.append(it)
        if opts.json:
            print(json.dumps(rows_out, indent=2))
        elif not rows_out:
            print("no matching items")
        else:
            for it in rows_out:
                t_str = (" touch=" + ",".join(it["touch"])) if it.get("touch") else ""
                print("%-10s Tier %-2s %-12s %-18s %s%s" % (
                    it["id"], it["tier"], it["status"], it["owner"], it["title"], t_str
                ))
        return 0
    if opts.action == "show":
        if not opts.target:
            sys.stderr.write("item show: give a work item ID\n")
            return 2
        it = _shards_mod.merged_items(project).get(opts.target)
        if not it:
            sys.stderr.write("item show: %s not found\n" % opts.target)
            return 2
        if opts.json:
            print(json.dumps(it, indent=2))
        else:
            print("%s · Tier %s · %s · %s" % (it["id"], it["tier"], it["status"], it["title"]))
            print("  type: %s · owner: %s · effort: %s" % (
                it["type"], it["owner"], it.get("effort") or "(charter default)"
            ))
            if it.get("depends"):
                print("  depends: %s" % ", ".join(it["depends"]))
            if it.get("touch"):
                print("  touch: %s" % ", ".join(it["touch"]))
            if _shards_mod.is_hotfix(it):
                print("  hotfix: since %s · retroactive review: %s" % (
                    it.get("hotfix_at") or "unknown",
                    "on file" if retro_reviews(project, it["id"]) else (it.get("retro_review") or "owed once merged")))
        return 0
    if opts.action == "add":
        if not opts.title:
            sys.stderr.write("item add: --title is required\n")
            return 2
        if opts.owner:
            opts.owner, err_o = resolve_owner(project, opts.owner)
            if err_o:
                sys.stderr.write("item add: --owner %s\n" % err_o)
                return 2
        item_id = opts.target
        if not item_id:
            claims_mod = runtime_module("claims")
            alloc, err_a = claims_mod.next_id(project, kind="item", sync_refs=opts.sync_refs)
            if err_a:
                sys.stderr.write("item add: %s\n" % err_a)
                return 1
            item_id = alloc["id"]
        existing = _shards_mod.merged_items(project)
        if item_id in existing:
            sys.stderr.write("item add: %s already exists (use `item set %s`)\n" % (item_id, item_id))
            return 1
        itype_val = opts.item_type or ("defect" if getattr(opts, "discovered", False) else "feat")
        tier_val = opts.tier or "2"
        status_val = opts.status or "Ready"
        wait_val = opts.waiting_on or ""
        reason_val = opts.park_reason or ""
        triage_note = ""
        if getattr(opts, "discovered", False):
            status_val, triage_note = resolve_discovered_status(project, item_id, itype_val, tier_val)
            if status_val == "Parked":
                wait_val = wait_val or "backlog owner"
                reason_val = reason_val or ("Discovered item triage: accept into Ready, defer, or drop (%s)" % triage_note)
        data = {
            "id": item_id,
            "title": opts.title,
            "type": itype_val,
            "tier": tier_val,
            "effort": opts.effort or "",
            "owner": opts.owner or ("qa" if itype_val == "defect" else "software-engineer"),
            "status": status_val,
            "depends": opts.depends or "",
            "touch": opts.touch or "",
            "created": today_iso,
            "updated": today_iso,
            "waiting_on": wait_val,
            "park_reason": reason_val,
            "unblock_by": opts.unblock_by or "",
            "later_when": opts.later_when or "",
            "dropped_reason": opts.dropped_reason or "",
            "summary": opts.summary or "",
            "severity": getattr(opts, "severity", None) or "",
            "found_by": getattr(opts, "found_by", None) or "",
        }
        if data["severity"] and not _shards_mod.severity_of(data["severity"]):
            sys.stderr.write("item add: --severity must be S0 to S4\n")
            return 2
        try:
            saved = _shards_mod.save_item(project, data, today=today_iso)
        except ValueError as exc:
            sys.stderr.write("item add: %s\n" % exc)
            return 2
        notify_if_parked(project, None, saved)
        if opts.json:
            out_saved = dict(saved)
            if triage_note:
                out_saved["triage_reason"] = triage_note
            print(json.dumps(out_saved, indent=2))
        else:
            print("added %s (%s, Tier %s) -> %s/project/items/%s.json" % (
                saved["id"], saved["status"], saved["tier"], project.docs, saved["id"]
            ))
        return 0
    if opts.action == "triage":
        if not opts.target:
            sys.stderr.write("item triage: give a work item ID\n")
            return 2
        cur = _shards_mod.merged_items(project).get(opts.target)
        if not cur:
            sys.stderr.write("item triage: %s not found\n" % opts.target)
            return 2
        new_status, triage_reason = resolve_discovered_status(
            project, opts.target, cur.get("type") or "feat", cur.get("tier") or "2"
        )
        updated = dict(cur)
        updated["status"] = new_status
        updated["updated"] = today_iso
        if new_status == "Ready":
            updated["waiting_on"] = ""
            updated["park_reason"] = ""
        else:
            updated["waiting_on"] = updated.get("waiting_on") or "backlog owner"
            updated["park_reason"] = updated.get("park_reason") or ("Discovered item triage: %s" % triage_reason)
        saved = _shards_mod.save_item(project, updated, today=today_iso)
        notify_if_parked(project, cur, saved)
        if opts.json:
            out_saved = dict(saved, promoted=(saved["status"] == "Ready"), triage_reason=triage_reason)
            print(json.dumps(out_saved, indent=2))
        else:
            print("triaged %s -> %s (%s)" % (saved["id"], saved["status"], triage_reason))
        return 0
    if opts.action == "set":
        if not opts.target:
            sys.stderr.write("item set: give a work item ID\n")
            return 2
        cur = _shards_mod.merged_items(project).get(opts.target)
        if not cur:
            sys.stderr.write("item set: %s not found\n" % opts.target)
            return 2
        updated = dict(cur)
        if opts.title is not None:
            updated["title"] = opts.title
        if opts.item_type is not None:
            updated["type"] = opts.item_type
        if opts.tier is not None:
            updated["tier"] = opts.tier
        if opts.effort is not None:
            updated["effort"] = opts.effort
        if opts.owner is not None:
            owner_v, err_o = resolve_owner(project, opts.owner)
            if err_o:
                sys.stderr.write("item set: --owner %s\n" % err_o)
                return 2
            updated["owner"] = owner_v
        if opts.status is not None:
            updated["status"] = opts.status
        if opts.depends is not None:
            updated["depends"] = opts.depends
        if opts.touch is not None:
            updated["touch"] = opts.touch
        if opts.waiting_on is not None:
            updated["waiting_on"] = opts.waiting_on
        if opts.park_reason is not None:
            updated["park_reason"] = opts.park_reason
        if opts.unblock_by is not None:
            updated["unblock_by"] = opts.unblock_by
        if opts.later_when is not None:
            updated["later_when"] = opts.later_when
        if opts.dropped_reason is not None:
            updated["dropped_reason"] = opts.dropped_reason
        if opts.summary is not None:
            updated["summary"] = opts.summary
        if getattr(opts, "severity", None) is not None:
            if opts.severity and not _shards_mod.severity_of(opts.severity):
                sys.stderr.write("item set: --severity must be S0 to S4\n")
                return 2
            updated["severity"] = opts.severity
        if getattr(opts, "found_by", None) is not None:
            updated["found_by"] = opts.found_by
        updated["updated"] = today_iso
        try:
            saved = _shards_mod.save_item(project, updated, today=today_iso)
        except ValueError as exc:
            sys.stderr.write("item set: %s\n" % exc)
            return 2
        notify_if_parked(project, cur, saved)
        if getattr(opts, "hotfix", False):
            saved, err_h, code_h = mark_hotfix(project, opts.target, today=today_iso)
            if err_h:
                sys.stderr.write("item set: %s\n" % err_h)
                return code_h
        if opts.json:
            print(json.dumps(saved, indent=2))
        else:
            print("updated %s (%s, Tier %s)" % (saved["id"], saved["status"], saved["tier"]))
        return 0


def defect_report_text(project, item, repro="", today=None):
    """A defect report for item from the project's defect-report template, with the header
    filled in; a short stand-in when the template is missing."""
    today = today or datetime.date.today().isoformat()
    path = os.path.join(project.root, project.docs, "templates", "defect-report.md")
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (IOError, OSError):
        text = ("# Defect report \u2014 %s %s\n\n**Severity:** %s\n\n## Steps to reproduce\n\n"
                % (item["id"], item["title"], item.get("severity", "")))
        return text + (repro or "_(steps)_") + "\n"
    text = re.sub(r"(?m)^status: \S+", "status: current", text, count=1)
    text = re.sub(r"(?m)^last-reviewed: \S+", "last-reviewed: " + today, text, count=1)
    text = re.sub(r"(?m)^# Defect report \u2014 .*$",
                  lambda m: "# Defect report \u2014 %s %s" % (item["id"], item["title"]), text, count=1)
    text = re.sub(r"(?m)^\*\*Severity:\*\* S0 \| S1 \| S2 \| S3 \| S4",
                  "**Severity:** " + item.get("severity", ""), text, count=1)
    if item.get("found_by"):
        text = text.replace("**Found by:** _(tester / tool / user)_",
                            "**Found by:** " + item["found_by"], 1)
    text = re.sub(r"(?m)^\*\*Environment:\*\* (.*)\*\*Date:\*\* YYYY-MM-DD",
                  lambda m: "**Environment:** %s**Date:** %s" % (m.group(1), today), text, count=1)
    if repro:
        text = re.sub(r"(?s)(## Steps to reproduce\n\n).*?(?=\n\*\*Inputs|\n## )",
                      lambda m: m.group(1) + repro.strip() + "\n", text, count=1)
    return text


def _cmd_bug(project, opts, parser):
    """bug: report a defect as a defect item plus a defect report (NUHT-040)."""
    severity = _shards_mod.severity_of(opts.severity)
    if not severity:
        sys.stderr.write("bug: --severity must be S0 to S4 (see the severity ladder in CARD.md)\n")
        return 2
    claims_mod = runtime_module("claims")
    alloc, err_a = claims_mod.next_id(project, kind="item")
    if err_a:
        sys.stderr.write("bug: %s\n" % err_a)
        return 1
    item_id = alloc["id"]
    today_iso = datetime.date.today().isoformat()
    status, note = opts.status, ""
    wait, reason = "", ""
    if not status:
        status, note = resolve_discovered_status(project, item_id, "defect", opts.tier)
        if status == "Parked":
            wait, reason = "backlog owner", "Defect triage: accept into Ready, defer, or drop (%s)" % note
    data = {"id": item_id, "title": opts.title, "type": "defect", "tier": opts.tier,
            "owner": "qa", "status": status, "touch": opts.touch or "",
            "created": today_iso, "updated": today_iso, "waiting_on": wait,
            "park_reason": reason, "severity": severity, "found_by": opts.found_by or ""}
    try:
        saved = _shards_mod.save_item(project, data, today=today_iso)
    except ValueError as exc:
        sys.stderr.write("bug: %s\n" % exc)
        return 2
    rel = os.path.join(project.docs, "project", "defects", item_id + ".md")
    full = os.path.join(project.root, rel)
    if not os.path.exists(full):
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(defect_report_text(project, saved, opts.repro or "", today_iso))
    _shards_mod.render(project)
    notify_if_parked(project, None, saved)
    if opts.json:
        print(json.dumps(dict(saved, report=rel, triage_reason=note), indent=2))
        return 0
    print("added %s (%s, %s, Tier %s) -> %s" % (item_id, severity, saved["status"], saved["tier"], rel))
    if severity == "S0":
        print("S0: stop and start the incident process (CARD.md); a postmortem is owed.")
    elif severity == "S1":
        print("S1: a release blocker until it is Done.")
    if note:
        print("status: %s (%s)" % (saved["status"], note))
    return 0


def _cmd_hotfix(project, opts, parser):
    """hotfix: mark a work item a hotfix."""
    saved, err_h, code_h = mark_hotfix(project, opts.item)
    if err_h:
        sys.stderr.write("hotfix: %s\n" % err_h)
        return code_h
    if opts.json:
        print(json.dumps(saved, indent=2))
    else:
        print("%s marked hotfix at %s (Tier %s stays). finish skips the pre-merge review; a "
              "retroactive review is owed within %d day(s)" % (
                  saved["id"], saved["hotfix_at"], saved["tier"],
                  retro_review_window(project.charter)))
    return 0


def _cmd_dispatch(project, opts, parser):
    """dispatch: run waves of Ready items in worker worktrees."""
    dispatch_mod = runtime_module("dispatch")
    report, rc = dispatch_mod.run_dispatch(sys.modules[__name__], project, opts)
    if report.get("error"):
        if opts.json:
            print(json.dumps(report, indent=2))
        else:
            sys.stderr.write("dispatch: %s\n" % report["error"])
        return rc
    if opts.json:
        print(json.dumps(report, indent=2))
    else:
        print(dispatch_mod.format_dispatch_report(report))
    return rc


def _cmd_deploy(project, opts, parser):
    """deploy record|list: release records and the deploy ledger."""
    releases_mod = runtime_module("releases")
    if opts.deploy_action == "list":
        state = releases_mod.deployed(project)
        print(json.dumps(state, indent=2, sort_keys=True) if opts.json
              else releases_mod.format_list(state))
        return 0
    try:
        accept = [a.strip() for a in (opts.accept_defects or "").split(",") if a.strip()]
        result = releases_mod.record(project, sys.modules[__name__], opts.version, opts.env,
                                     opts.from_ref, opts.to_ref, opts.by, opts.dry_run,
                                     accept=accept, reason=opts.reason)
    except (releases_mod.DeployError, OSError) as exc:
        sys.stderr.write("deploy record: %s\n" % exc)
        return 1
    if opts.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    rec = result["record"]
    verb = "would record" if result["dry_run"] else "recorded"
    if result["action"] == "promotion":
        print("%s %s in %s (promotion of %s; record unchanged except envs)" % (
            verb, opts.version, opts.env, rec.get("to", "")[:12]))
    else:
        print("%s %s in %s: %d commit(s), %d item(s)%s" % (
            verb, opts.version, opts.env, rec.get("commits", 0), len(rec.get("items") or []),
            ": " + ", ".join(rec["items"]) if rec.get("items") else ""))
    print("  %s%s" % (result["path"], "" if result["dry_run"] else
                      " and one line in %s/project/deploys.jsonl" % project.docs))
    return 0


def _cmd_claims(project, opts, parser):
    """claim, unclaim, release, claims and parallel: the shared claim store."""
    claims_mod, view_mod = runtime_module("claims"), runtime_module("view")
    if opts.command == "claim":
        agent = opts.agent or identity(None, None, project)[0]
        # Never a silent stand-in: an unknown agent or person is recorded as such and
        # said out loud (on stderr, or inside the --json result).
        notes = []
        if agent == "unknown":
            notes.append("no agent identity: pass --agent <name> or set AI_SDLC_AGENT")
            if not opts.json:
                sys.stderr.write("warning: %s\n" % notes[-1])
        who = person_identity(project, warn=not opts.json)
        if who["warning"]:
            notes.append(who["warning"])
        record, error = claims_mod.claim(
            project, view_mod, opts.item, agent, opts.worktree,
            opts.no_worktree, opts.mark, opts.base,
            sync_refs=getattr(opts, "sync_refs", False),
            person=who["person"],
        )
        if error:
            sys.stderr.write("claim: %s\n" % error)
            return 1
        setup = record.pop("setup_result", None)
        if opts.json:
            shown = dict(record, setup_result=setup) if setup else record
            print(json.dumps(dict(shown, warnings=notes) if notes else shown, indent=2))
        else:
            print("claimed %s for %s (%s) on branch %s" % (
                record["id"], record["agent"], record.get("person") or "unknown person",
                record["branch"]))
            if record["worktree"]:
                print("worktree: %s\n  cd %s" % (record["worktree"], record["worktree"]))
            if setup and setup["ok"]:
                print("setup: `%s` passed (NUHUT_PORT=%s)" % (setup["command"], record.get("port") or ""))
            print("free it when the item is Done, Parked or Deferred: "
                  "python3 .ai-sdlc/bin/sdlc.py unclaim %s" % record["id"])
        claimed_item = _shards_mod.merged_items(project).get(record["id"]) or {}
        for dft, hit in _shards_mod.defects_touching(_shards_mod.merged_items(project),
                                                      claimed_item.get("touch") or []):
            if dft["id"] != record["id"]:
                sys.stderr.write("claim: open defect %s (%s) touches %s: %s\n" % (
                    dft["id"], dft.get("severity") or "unrated", ", ".join(hit), dft.get("title", "")))
        if setup and not setup["ok"]:
            tail = (setup.get("output") or "").strip()
            sys.stderr.write("claim: %s. The claim and its worktree are kept: fix the cause and run "
                             "the setup again by hand, or free it with `sdlc.py unclaim %s "
                             "--remove-worktree`%s\n" % (setup["error"], record["id"],
                                                          ("\n" + tail) if tail else ""))
            return 1
        return 0
    deprecated = None
    if opts.command == "release":
        # The claim command's old name. Same stdout and exit codes; one note that repeats
        # the caller's own arguments under the new name: on stderr, or with --json as a
        # "deprecated" field, so a caller that merges the streams still parses the JSON.
        rest = list(getattr(opts, "_argv", None) or [])
        if "release" in rest:
            rest = rest[rest.index("release") + 1:]
        deprecated = "use: sdlc.py unclaim %s" % " ".join(rest)
        if not getattr(opts, "json", False):
            sys.stderr.write("release: deprecated, %s\n" % deprecated)
    if opts.command in ("release", "unclaim"):
        record, error = claims_mod.release(
            project, opts.item, opts.remove_worktree,
            agent=getattr(opts, "agent", None) or identity(None, None, project)[0],
            force=getattr(opts, "force", False),
            sync_refs=getattr(opts, "sync_refs", False),
        )
        if error:
            sys.stderr.write("%s: %s\n" % (opts.command, error))
            return 1
        down = record.pop("teardown_result", None)
        if getattr(opts, "json", False):
            doc = {"released": record["id"], "record": record, "teardown": down}
            if deprecated:
                doc["deprecated"] = deprecated
            print(json.dumps(doc, indent=2))
        else:
            print("released %s (was %s)" % (record["id"], record.get("agent", "?")))
            if down and down["ok"]:
                print("teardown: `%s` passed" % down["command"])
        if down and not down["ok"]:
            tail = (down.get("output") or "").strip()
            sys.stderr.write("%s: warning: %s; the worktree was removed anyway (--force)%s\n" % (
                opts.command, down["error"], ("\n" + tail) if tail else ""))
        return 0
    if opts.command == "claims":
        held = claims_mod.list_claims(project, sync_refs=getattr(opts, "sync_refs", False))
        if opts.json:
            print(json.dumps(held, indent=2))
        elif not held:
            print("no active claims")
        for c in [] if opts.json else held:
            print("%-10s %-16s %-16s %-36s since %s  last commit %s" % (
                c["id"], c.get("agent", "?"), c.get("person") or "unknown person", c.get("branch", ""),
                c.get("since", "")[:10], c.get("last_commit", "")[:10] or "none"))
        return 0
    result = claims_mod.parallel(
        project, sys.modules[__name__], view_mod,
        sync_refs=getattr(opts, "sync_refs", False),
    )
    if opts.json:
        print(json.dumps(result, indent=2))
        return 0
    for n, group in enumerate(result["groups"], 1):
        print("group %d (can run together): %s" % (n, ", ".join(group)))
    for c in result["conflicts"]:
        print("conflict %s × %s: %s" % (c["a"], c["b"], ", ".join(c["files"] + c["single_writer"])))
    if result["plan_first"]:
        print("plan first (no Files that change): %s" % ", ".join(x["id"] for x in result["plan_first"]))
    if not (result["groups"] or result["plan_first"]):
        print("no unclaimed Ready items with finished dependencies")
    return 0


def _cmd_lens(project, opts, parser):
    """lens and audit: the project lens and the dependency scanner."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.dont_write_bytecode = True
    import lens as lens_mod
    if opts.command == "audit":
        return run_audit(project, lens_mod, opts)
    if opts.write and opts.area != "standards":
        print("lens: --write needs --area standards", file=sys.stderr)
        return 2
    if opts.area == "standards":
        return run_standards(project, lens_mod, opts)
    import view
    model = {"kit": kit_status(project), "alerts": doctor(project), "evidence": view.evidence_runs(project)}
    data = lens_mod.lens(sys.modules[__name__], project, model, include_user=opts.user)
    if opts.json:
        key = {"deps": "dependencies", "deploy": "workflows"}.get(opts.area, opts.area)
        print(json.dumps(data if not opts.area else data.get(key), indent=2))
        return 0
    print_lens(data, opts.area)
    return 0


def _cmd_view(project, opts, parser):
    """view and metrics: the interactive page and the process measures."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.dont_write_bytecode = True  # no __pycache__ next to kit files in a project
    import view
    if opts.command == "metrics":
        return view.print_metrics(sys.modules[__name__], project, opts)
    if not opts.serve and (opts.allow_actions or opts.host not in (None, "127.0.0.1")):
        parser.error("view: --host and --allow-actions only apply with --serve")
    return view.run(sys.modules[__name__], project, opts)


def _cmd_log(project, opts, parser):
    """log: draft worklog lines."""
    since = opts.since
    if not since and opts.id:
        found = item_commits(project, opts.id)
        if not found:
            sys.stderr.write("log: no commit carries a `Work-Item: %s` trailer\n" % opts.id)
            return 2
        since = found[-1][1].split(" ")[0]
        if not since:
            sys.stderr.write("log: %s starts at the root commit; pass --since\n" % opts.id)
            return 2
    if not since:
        sys.stderr.write("log: give --since <ref>, or --id <item>\n")
        return 2
    if str(since).startswith("-") or not project.git("rev-parse", "--verify", "--quiet", since + "^{commit}").strip():
        sys.stderr.write("log: %r is not a commit\n" % since)
        return 2
    lines, orphans = log_entries(project, since)
    if opts.id:
        lines = [line for line in lines if line.split(" · ")[1] == opts.id]
        orphans = []
    if opts.write:
        written = write_log(project, lines)
        if not getattr(opts, "json", False):
            dest = ("%s/project/worklog/" % project.docs) if _shards_mod.is_sharded(project, for_write=True) else ("%s/project/worklog.md" % project.docs)
            print("wrote %d line(s) to %s" % (len(written), dest))
        lines = written
    if getattr(opts, "json", False):
        print(json.dumps({
            "since": since,
            "id": opts.id,
            "wrote": bool(opts.write),
            "entries": lines,
            "orphans": orphans,
        }, indent=2))
        return 0
    for line in lines:
        print(line)
    for orphan in orphans:
        print("no work item ID: %s" % orphan, file=sys.stderr)
    return 0


def _cmd_trailers(project, opts, parser):
    """trailers: print the commit trailers for a work item."""
    agent, model = identity(opts.agent, opts.model, project)
    # No agent detected: a person is committing, and a person has no Model trailer
    # (process/05-change-control.md). `unknown` would fail ci-check.
    tags = [("Work-Item", opts.item)] + ([("Agent", "human")] if agent == "unknown" else
                                         [("Agent", agent), ("Model", model)])
    if getattr(opts, "json", False):
        print(json.dumps(dict(tags), indent=2))
    else:
        print("\n".join("%s: %s" % pair for pair in tags))
    if agent != "unknown" and model == "unknown":
        sys.stderr.write("trailers: %s was detected but not its model, and ci-check rejects "
                         "`Model: unknown`: pass --model <model id> or set AI_SDLC_MODEL\n" % agent)
    return 0


def _cmd_review(project, opts, parser):
    """review: one role's review in another agent tool."""
    path, record, error = review(project, opts.item, opts.role, opts.by, opts.model,
                                 opts.stage, opts.base, opts.timeout)
    if error:
        sys.stderr.write("review: %s\n" % error)
        return 2
    if getattr(opts, "json", False):
        out_rec = dict(record, path=path)
        print(json.dumps(out_rec, indent=2))
    else:
        print("review saved: %s" % path)
        print("  reviewer  %s / %s" % (record["reviewer_agent"], record["reviewer_model"]))
        print("  author    %s / %s" % (record["author_agent"], record["author_model"]))
        print("  %s; verdict: %s" % (record["independence"], record["verdict"]))
    return 0


def _cmd_bite(project, opts, parser):
    """bite: check that a test fails without the change."""
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
    result, error = bite(project, command, opts.base, opts.timeout, item=opts.item)
    if error:
        sys.stderr.write("bite: %s\n" % error)
        return 2
    if opts.json:
        print(json.dumps(result, indent=2))
    else:
        print_bite(result)
    return 0 if result["bites"] else 1


def _cmd_plan_check(project, opts, parser):
    """plan-check: compare a plan's file list with the diff."""
    if opts.pre:
        result, error = plan_precheck(project, opts.item)
    else:
        result, error = plan_check(project, opts.item, opts.base)
    if error:
        sys.stderr.write("plan-check: %s\n" % error)
        return 2
    if opts.json:
        print(json.dumps(result, indent=2))
    elif opts.pre:
        print_plan_precheck(result)
    else:
        print_plan_check(result)
    if opts.pre:
        return 1 if result["missing"] or result["broad"] else 0
    gaps = result["unplanned"] or result["untouched"] or result["broad"]
    return 1 if opts.strict and gaps else 0


def _cmd_ext(project, opts, parser):
    """ext: project extensions."""
    return runtime_module("ext").main(sys.modules[__name__], project, opts)


def _cmd_ci_check(project, opts, parser):
    """ci-check: judge a pull request's commits."""
    head = opts.head
    if head == "event":
        head, error = ci_event_head(os.environ.get("GITHUB_EVENT_PATH", ""))
        if error:
            sys.stderr.write("ci-check: %s\n" % error)
            return 2
    result, error = ci_check(project, opts.base, head, opts.charter_ref)
    if error:
        sys.stderr.write("ci-check: %s\n" % error)
        return 2
    if opts.json:
        print(json.dumps(result, indent=2))
    else:
        print_ci_check(result)
    return 1 if result["findings"] else 0


def _cmd_config(project, opts, parser):
    """config: inspect or update kit constraints."""
    changes = {}
    if opts.effort:
        changes["effort"] = opts.effort
    if opts.independent_review:
        changes["independent_review"] = opts.independent_review
    if opts.tier_rules:
        changes["tier_rules"] = opts.tier_rules
    if opts.decision_style:
        changes["decision_style"] = opts.decision_style
    if opts.dev_method:
        changes["dev_method"] = opts.dev_method
    if getattr(opts, "specs", None):
        changes["specs"] = opts.specs
    if getattr(opts, "slop_filter", None):
        changes["slop_filter"] = opts.slop_filter
    if getattr(opts, "discovered_defects", None):
        changes["discovered_defects"] = opts.discovered_defects
    if getattr(opts, "worktree_scripts", None) is not None:
        changes["worktree_scripts"] = opts.worktree_scripts
    if opts.reviewer:
        changes["preferred_reviewer"] = opts.reviewer
    if opts.token_saving:
        changes["token_saving"] = opts.token_saving
    if opts.set_check:
        chk_map = {}
        for item_kv in opts.set_check:
            if "=" not in item_kv:
                parser.error("--set-check must be STAGE=COMMAND")
            k, v = item_kv.split("=", 1)
            chk_map[k.strip()] = v.strip()
        changes["checks"] = chk_map
    if opts.allow_extension:
        changes["allow_extension"] = opts.allow_extension
    if opts.notify_webhook:
        changes["notify_webhook"] = opts.notify_webhook
    if changes:
        res, err = configure_kit(project, changes)
        if err:
            sys.stderr.write("config: %s\n" % err)
            return 2
        if opts.json:
            print(json.dumps(res, indent=2))
        else:
            for line in res["applied"]:
                print("updated: %s" % line)
        return 0
    status = kit_status(project)
    if opts.json:
        print(json.dumps(status, indent=2))
    else:
        c = status["constraints"]
        print("kit v%s (%s profile) · token-saving: %s" % (
            status["kit_version"], status["profile"],
            "on" if status["token_saving"] else "off"))
        print("  effort: %s · independent review: %s · reviewer: %s" % (
            c["effort_mode"], c["independent_review"], c["preferred_reviewer"]))
        print("  tier rules: %s · decision style: %s · dev method: %s" % (
            c["tier_rules"], c["decision_style"], c["dev_method"]))
    return 0


def _cmd_verify(project, opts, parser):
    """verify: run the charter's check commands."""
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
    summary, text = verify(project, selected, opts.timeout, parallel=getattr(opts, "parallel", False),
                           item=opts.item)
    if getattr(opts, "json", False):
        print(json.dumps(summary, indent=2))
    else:
        print(text)
    failed = [e for e in summary["stages"] if e["result"].startswith("Verified: fail")]
    return 1 if failed else 0


def _cmd_fix(project, opts, parser):
    """fix: safe mechanical repairs."""
    if opts.action in ("rotate-worklog", "normalise-status",
                       "link-evidence", "migrate-shards"):
        finish_mod = runtime_module("finish")
        report = getattr(finish_mod, opts.action.replace("-", "_"))(
            sys.modules[__name__], project, opts.apply)
        if opts.json:
            print(json.dumps({"action": opts.action, "applied": bool(opts.apply), "report": report}, indent=2))
        else:
            print("\n".join(report))
            if not opts.apply and not report[0].startswith(("worklog.md is", "every")):
                print("(preview: add --apply to write it)")
        return 0
    if opts.action == "merge-driver":
        return fix_merge_driver(project, opts.json)
    if (opts.action == "unlock-tests" or opts.unlock_tests) and not os.environ.get("AI_SDLC_APPROVAL"):
        if any(os.environ.get(k) for k in AGENT_SESSION_ENVS):
            sys.stderr.write(
                "fix: unlocking reproducing tests from an agent session requires human approval "
                "(AI_SDLC_APPROVAL=<ticket>) or verified completion via `sdlc.py finish <ID>`\n"
            )
            return 1
    res = fix_kit(project, opts.action, {"unlock_tests": opts.unlock_tests})
    if opts.json:
        print(json.dumps(res, indent=2))
    else:
        if res["repaired"]:
            for line in res["repaired"]:
                print("fixed: %s" % line)
        else:
            print("nothing needed repair")
    return 0


class Command(object):
    """One entry in COMMANDS. A plain command has a handler; a noun-verb group (rollout
    start|list) has verbs, a name -> Command map, and no handler of its own. A handler is
    called as handler(project, opts, parser) and returns the exit code; configure(subparser)
    adds the command's flags. A command with needs_project False (the merge driver) is
    called with project None, since git may run it where no project can be read."""

    __slots__ = ("name", "handler", "help", "configure", "verbs", "core", "needs_project")

    def __init__(self, name, handler=None, help="", configure=None, verbs=None, core=False,
                 needs_project=True):
        self.name, self.handler, self.help = name, handler, help
        self.configure, self.verbs, self.core = configure, verbs, core
        self.needs_project = needs_project


def _cmd_mcp(project, opts, parser):
    return runtime_module("mcp_server").serve(
        project.root, os.path.abspath(__file__), allow_verify=opts.allow_verify,
        version=str(project.manifest.get("kit_version") or ""))


COMMANDS = {}
_VERB_DEST = "_verb"
_COMMAND_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def register_command(name, handler, help="", configure=None, verb=None, core=False):
    """Add a subcommand to COMMANDS, or a verb to a noun-verb group when verb is given.

    Refuses (ValueError) a malformed name, any name a core command already uses, a name
    an extension already took, a verb already in its group, and mixing a plain command with
    a group of the same name. Core argparse flags stay in build_parser; an extension
    command's flags come from configure(subparser)."""
    if not callable(handler):
        raise ValueError("command %r: handler is not callable" % (name,))
    for part in (name, verb) if verb is not None else (name,):
        if not isinstance(part, str) or not _COMMAND_NAME.match(part):
            raise ValueError("command name %r: use lowercase letters, digits and single "
                             "hyphens" % (part,))
    have = COMMANDS.get(name)
    if have is not None and have.core:
        raise ValueError("command %r is a core sdlc.py command; pick another name" % name)
    if core and verb is not None:
        raise ValueError("core command %r: core commands take no registered verbs" % name)
    if verb is None:
        if have is not None:
            raise ValueError("command %r is already registered" % name)
        COMMANDS[name] = Command(name, handler, help, configure, core=core)
        return COMMANDS[name]
    if have is None:
        have = COMMANDS[name] = Command(name, verbs={})
    elif have.verbs is None:
        raise ValueError("command %r is a plain command, not a verb group" % name)
    if verb in have.verbs:
        raise ValueError("command %r %r is already registered" % (name, verb))
    have.verbs[verb] = Command(verb, handler, help, configure)
    have.help = "%s %s" % (name, "|".join(have.verbs))
    return have.verbs[verb]


for _name, _handler in (
        ("status", _cmd_status), ("doctor", _cmd_doctor), ("approvals", _cmd_approvals),
        ("finish", _cmd_finish), ("guard", _cmd_finish),
        ("notify", _cmd_notify), ("sync", _cmd_sync), ("slop", _cmd_slop), ("spec", _cmd_spec),
        ("next-id", _cmd_next_id), ("render", _cmd_render), ("item", _cmd_item),
        ("hotfix", _cmd_hotfix), ("bug", _cmd_bug), ("dispatch", _cmd_dispatch), ("deploy", _cmd_deploy),
        ("claim", _cmd_claims), ("release", _cmd_claims), ("unclaim", _cmd_claims),
        ("claims", _cmd_claims), ("parallel", _cmd_claims), ("lens", _cmd_lens),
        ("audit", _cmd_lens), ("view", _cmd_view), ("metrics", _cmd_view),
        ("log", _cmd_log), ("trailers", _cmd_trailers), ("review", _cmd_review),
        ("bite", _cmd_bite), ("plan-check", _cmd_plan_check), ("ext", _cmd_ext),
        ("ci-check", _cmd_ci_check), ("config", _cmd_config), ("verify", _cmd_verify),
        ("fix", _cmd_fix), ("mcp", _cmd_mcp)):
    register_command(_name, _handler, core=True)
del _name, _handler
register_command("merge-shard", _cmd_merge_shard, core=True).needs_project = False

_EXT_COMMANDS_DONE = set()   # (extension id, command name) already registered in this process


def register_extension_commands(reg):
    """Register the `commands` entry points of <reg>'s extensions in COMMANDS; returns
    the names registered. A record {"id": "<name>", "file": "<file>.py"} gives the one
    command name the extension may use. The file defines register(add, runtime) and calls
    add(handler, help="", configure=None, verb=None) for a plain command or for each verb
    of a group; runtime is this module. Code loads through reg.load_code, so a project
    extension's commands stay off until Extensions allowed lists it and its pinned hashes
    match. A name a core command uses, or one another extension took, is refused with a
    stderr warning; nothing here can stop a core command from running."""
    names = []
    for ext_id, rec in reg.code_records("commands"):
        name = rec.get("id")
        key = (ext_id, name)
        if key in _EXT_COMMANDS_DONE:
            continue
        have = COMMANDS.get(name)
        if have is not None and have.core:
            sys.stderr.write("extension %s: command %r is a core sdlc.py command; the "
                             "extension's command is ignored\n" % (ext_id, name))
            continue
        module, why = reg.load_code(ext_id, rec.get("file") or "")
        if module is None:
            continue           # blocked or broken: ext list and doctor report it
        hook = getattr(module, "register", None)
        if not callable(hook):
            sys.stderr.write("extension %s: %s defines no register(add, runtime); command %r "
                             "is ignored\n" % (ext_id, rec.get("file"), name))
            continue

        def add(handler, help="", configure=None, verb=None, _name=name):
            return register_command(_name, handler, help=help, configure=configure, verb=verb)

        try:
            hook(add, sys.modules[__name__])
        except Exception as exc:  # an extension's own bug must not break the CLI
            if have is None:
                COMMANDS.pop(name, None)
            else:
                COMMANDS[name] = have
            sys.stderr.write("extension %s: command %r is ignored (%s: %s)\n"
                             % (ext_id, name, exc.__class__.__name__, exc))
            continue
        _EXT_COMMANDS_DONE.add(key)
        if name in COMMANDS:
            names.append(name)
    return names


def _peek_command(argv):
    """(the subcommand argv names or None, the --root value or None), without argparse."""
    root, i = None, 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--root" and i + 1 < len(argv):
            root, i = argv[i + 1], i + 2
            continue
        if arg.startswith("--root="):
            root = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            return arg, root
        i += 1
    return None, root


def _load_extension_commands(argv):
    """Register extension commands unless argv names a core command, so core commands
    (and git's merge driver) never import extension code. Never raises."""
    name, root = _peek_command(argv)
    have = COMMANDS.get(name) if name else None
    if have is not None and have.core:
        return
    try:
        project = Project(root or default_root())
        reg, _ = load_registry(project)
        if reg is not None:
            register_extension_commands(reg)
    except Exception as exc:  # a missing project or a broken registry leaves core commands
        if name:
            sys.stderr.write("extension commands are not available (%s)\n"
                             % exc.__class__.__name__)


def build_parser():
    """The argparse tree: every core subcommand, then each registered extension command."""
    parser = _Main(prog="sdlc.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", help="project root (default: the project this file is "
                        "installed in)")
    sub = parser.add_subparsers(dest="command", parser_class=argparse.ArgumentParser)
    stp = sub.add_parser("status", help="one screen of next actions: missing setup, your items "
                                        "and the step each owes, Parked on you, Ready to take")
    stp.add_argument("--json", action="store_true", help="print the status as JSON")
    doc = sub.add_parser("doctor", help="mechanical checks of the SDLC records")
    doc.add_argument("--json", action="store_true", help="print findings as JSON")
    doc.add_argument("--strict", action="store_true",
                     help="exit 1 if any finding is at level fail (for CI); accepted ones "
                     "do not count")
    doc.add_argument("--baseline", action="store_true",
                     help="accept the current findings in docs/project/doctor-baseline.json; "
                     "once it exists a rewrite only removes fixed ones")
    doc.add_argument("--all", action="store_true", help="also show accepted findings")
    doc.add_argument("--no-cache", dest="no_cache", action="store_true",
                     help="bypass .ai-sdlc/cache/doctor.json")
    ver = sub.add_parser("verify", help="run the charter's check commands and record "
                         "the evidence")
    ver.add_argument("--stage", help="comma-separated stages to run, e.g. unit,lint")
    ver.add_argument("--timeout", type=int, default=1800, help="seconds per stage")
    ver.add_argument("--parallel", "-j", action="store_true",
                     help="run independent verification stages concurrently")
    ver.add_argument("--item", help="the work item this run verifies; the ledger rows name it")
    ver.add_argument("--json", action="store_true", help="print verification summary as JSON")
    fin = sub.add_parser("finish", help="close a work item: check its evidence and reviews, "
                         "draft the worklog entry, set Done (Tier 1 / Strict Tier 2: Parked)")
    fin.add_argument("item", help="work item ID")
    fin.add_argument("--waive", choices=("verify",), help="record that the checks could not "
                     "run (not at Tier 1); needs --by and --reason")
    fin.add_argument("--by", help="who decided the waiver")
    fin.add_argument("--reason", help="why the checks cannot run")
    fin.add_argument("--why", help="single-shot worklog reasoning and rejected alternatives")
    fin.add_argument("--not-done", dest="not_done", help="deferred work with follow-up IDs, or 'nothing deferred'")
    fin.add_argument("--discovered", help="discovered bugs, stale docs, or 'nothing'")
    fin.add_argument("--decisions", help="durable decisions and ADRs, or 'none'")
    fin.add_argument("--assumptions", help="assumptions relied upon, or 'none'")
    fin.add_argument("--plan", help="Tier 2 plan summary when not in plans/<ID>.md")
    fin.add_argument("--reviews", help="reviews summary when not in reviews/<ID>*.md")
    fin.add_argument("--from-json", dest="from_json", help="JSON file (or '-' for stdin) supplying worklog fields")
    fin.add_argument("--dry-run", action="store_true", help="say what it would do; write nothing")
    fin.add_argument("--json", action="store_true", help="print result as JSON")
    apr = sub.add_parser("approvals", help="who approved an item's merge: the item branch's "
                         "GitHub PR reviews on its head (gh), else the charter's Approvers")
    apr.add_argument("item", help="work item ID")
    apr.add_argument("--json", action="store_true", help="print the result as JSON")
    gd = sub.add_parser("guard", help="the finish guard, run by the agent tool's session hooks")
    gd.add_argument("event", choices=("start", "stop"))
    chk = sub.add_parser("plan-check", help="compare a Tier 1 plan's file list with the "
                         "branch's diff")
    chk.add_argument("item", help="work item ID, e.g. ACME-12")
    chk.add_argument("--base", help="branch the work left (default: the charter's Default "
                     "branch, else main)")
    chk.add_argument("--json", action="store_true", help="print the result as JSON")
    chk.add_argument("--strict", action="store_true",
                     help="exit 1 if any file is unplanned, any planned path untouched, or "
                     "the plan is too broad to check")
    chk.add_argument("--pre", action="store_true",
                     help="before the build: exit 1 if a planned path matches no file and is "
                     "not marked (new), or the plan is too broad (ignores --base and --strict)")
    cic = sub.add_parser("ci-check", help="judge a pull request's commits: trailers, the "
                         "ledger record behind each item, Tier 1 reviews and the tier floor")
    cic.add_argument("--base", help="branch the PR targets (default: the charter's Default "
                     "branch, else main)")
    cic.add_argument("--head", help="the PR's last commit (default: HEAD); `event` reads "
                     "pull_request.head.sha from $GITHUB_EVENT_PATH")
    cic.add_argument("--charter-ref", dest="charter_ref", help="read the Always Tier 1 here "
                     "globs from the charter on this ref (CI: the base branch), so the PR "
                     "cannot weaken them")
    cic.add_argument("--json", action="store_true", help="print the result as JSON")
    vw = sub.add_parser("view", help="draw the records as an interactive page "
                        "(.ai-sdlc/view/index.html, git-ignored)")
    vw.add_argument("--no-open", action="store_true", help="write the page, do not open it")
    vw.add_argument("--json", action="store_true", help="print the model instead")
    vw.add_argument("--github", action="store_true", help="live mode: also show open GitHub issues "
                    "and pull requests (needs the gh CLI, signed in); never written to a static page")
    vw.add_argument("--no-user", action="store_true", help="live mode: leave user-level skills, "
                    "commands and MCP servers (~/.claude) out of the Project lens")
    vw.add_argument("--serve", action="store_true", help="live mode: serve the page on "
                     "127.0.0.1 (or --host) and update it as the records change")
    vw.add_argument("--port", type=int, default=8765, help="live mode port (default 8765; "
                     "0 picks a free one)")
    vw.add_argument("--host", default=None, help="live mode: where to listen. 127.0.0.1 "
                    "(default, this machine only), tailscale (this machine's Tailscale IPv4), "
                    "0.0.0.0 or an IP address. Anything but loopback needs the access key "
                    "printed in the link and is read-only")
    vw.add_argument("--allow-actions", action="store_true", help="live mode with --host: let "
                    "the page run kit commands and change settings, as it does locally")
    vw.add_argument("--interval", type=int, default=2, help="live mode: seconds between "
                     "checks for changes (default 2)")
    vw.add_argument("--svg", nargs="?", const="", default=None,
                    help="export the mind map as a formatted SVG file (.ai-sdlc/view/map.svg by default)")
    vw.add_argument("--export-html", nargs="?", const="dashboard.html", default=None,
                    help="export the standalone dashboard HTML file (default: dashboard.html)")
    met = sub.add_parser("metrics", help="process measures from the records and git")
    met.add_argument("--json", action="store_true", help="print as JSON")
    met.add_argument("--env", help="the deploy environment the DORA measures read (default: "
                     "production, prod, prd or live, else the only one in the ledger)")
    lg = sub.add_parser("log", help="draft worklog lines from commits and verify runs")
    lg.add_argument("--since", help="git ref to start after, e.g. main or HEAD~5 (default with "
                    "--id: just before the item's first commit)")
    lg.add_argument("--id", help="draft only this work item's line")
    lg.add_argument("--write", action="store_true", help="insert the drafts into the worklog "
                    "(items it already names are skipped)")
    lg.add_argument("--json", action="store_true", help="print drafted entries as JSON")
    tr = sub.add_parser("trailers", help="print the commit trailers for a work item")
    tr.add_argument("item", help="work item ID")
    tr.add_argument("--agent", help="the harness making the commit (default: from the "
                    "environment, else human, with no Model line)")
    tr.add_argument("--model", help="the model id (default: from the environment, else "
                    "unknown)")
    tr.add_argument("--json", action="store_true", help="print trailers as JSON")
    rv = sub.add_parser("review", help="run one role's review of an item's diff in another "
                        "harness and save it")
    rv.add_argument("item", help="work item ID")
    rv.add_argument("--role", required=True, help="role playbook, e.g. security")
    rv.add_argument("--by", required=True, help="an agent record in the registry (claude, "
                    "codex, gemini, opencode, kiro, ...) or cmd:<command> (reads the prompt on "
                    "stdin, prints the review)")
    rv.add_argument("--model", help="model to ask the harness for; recorded")
    rv.add_argument("--stage", default="ship", choices=("design", "ship", "retro"),
                    help="design, ship, or retro (the retroactive review a hotfix owes)")
    rv.add_argument("--base", help="review the diff from this ref to the working tree "
                    "instead of the item's commits")
    rv.add_argument("--timeout", type=int, default=1800)
    rv.add_argument("--json", action="store_true", help="print review record as JSON")
    bt = sub.add_parser("bite", help="check that a test command fails without the change "
                        "and passes with it")
    bt.add_argument("--item", help="the work item this bite verifies; the ledger row names it")
    bt.add_argument("test_command", nargs=argparse.REMAINDER,
                    help="the test command, e.g. python3 -m unittest discover -s tests")
    bt.add_argument("--base", help="ref to revert product files to (default: HEAD when "
                    "there are uncommitted product changes, else HEAD~1)")
    bt.add_argument("--timeout", type=int, default=1800, help="seconds per test run")
    bt.add_argument("--restore", action="store_true",
                    help="put back files an interrupted bite left reverted")
    bt.add_argument("--json", action="store_true", help="print the result as JSON")
    cfg = sub.add_parser("config", help="inspect or update kit constraints in charter.md "
                         "and .ai-sdlc/profile.json")
    cfg.add_argument("--effort", choices=("Lean", "Normal", "Beast", "lean", "normal", "beast"),
                     help="set Default effort mode")
    cfg.add_argument("--independent-review",
                     choices=("none", "off", "tier1", "tier1-2", "Tier 1", "Tier 1 and 2"),
                     help="set Independent review required for")
    cfg.add_argument("--tier-rules", choices=("Standard", "Strict", "standard", "strict"),
                     help="set Tier rules")
    cfg.add_argument("--decision-style",
                     choices=("Ask", "Guide", "Autopilot", "ask", "guide", "autopilot"),
                     help="set Decision style")
    cfg.add_argument("--dev-method", choices=("Item", "Epic", "item", "epic"),
                     help="set Development method")
    cfg.add_argument("--reviewer", choices=reviewer_choices(),
                     help="set preferred second reviewer CLI")
    cfg.add_argument("--token-saving", choices=("on", "off"),
                     help="toggle token-saving mode (Lean effort, single-agent review, "
                          "Standard tier rules, compact budget)")
    cfg.add_argument("--set-check", action="append", default=[],
                     help="set a check command: STAGE=COMMAND or STAGE=absent")
    cfg.add_argument("--specs", choices=("on", "off"), help="turn living specs on or off (docs/project/specs/)")
    cfg.add_argument("--slop-filter", choices=("off", "on", "strict"),
                     help="set the Slop filter: off, on (public copy, advisory) or strict "
                          "(all prose; `slop` exits 1 on a failing file)")
    cfg.add_argument("--discovered-defects", dest="discovered_defects",
                     choices=("Parked", "Auto-Ready (bite)", "parked", "auto-ready-bite", "auto"),
                     help="set Discovered defects triage policy: Parked or Auto-Ready (bite)")
    cfg.add_argument("--allow-extension", dest="allow_extension", action="append", default=[],
                     metavar="ID", help="add an extension id to the charter's Extensions allowed "
                     "row, so its code runs once the change is on the default branch")
    cfg.add_argument("--notify-webhook", dest="notify_webhook", metavar="NUHUT_VAR|off",
                     help="set the charter's Notify webhook row to the environment variable "
                     "that holds the webhook URL (never the URL), or off")
    cfg.add_argument("--worktree-scripts", dest="worktree_scripts", metavar="SCRIPTS",
                     help="set the charter's Worktree scripts row: 'setup: <cmd>; teardown: <cmd>' "
                          "(optional '; port: <base>'), or none")
    cfg.add_argument("--json", action="store_true", help="print kit status as JSON")
    ex = sub.add_parser("ext", help="project extensions: list, add, update, remove, search the "
                                    "catalog, validate a manifest, package a plugin wrapper")
    ex.add_argument("action", choices=("list", "add", "update", "remove", "search", "validate",
                                       "package"))
    ex.add_argument("target", nargs="?", help="add: a git URL or local directory; update, "
                    "remove and package: an extension id; search: a term; validate: a "
                    "directory")
    ex.add_argument("--for", dest="for_tool", choices=("claude", "gemini", "codex", "kiro"),
                    help="package: the tool whose plugin wrapper to write")
    ex.add_argument("--out", help="package: the directory to write into (default: "
                    "dist/extensions/<id>/<tool>/)")
    ex.add_argument("--ref", help="add or update: the branch, tag or commit to install")
    ex.add_argument("--dry-run", action="store_true", help="update: print what would change")
    ex.add_argument("--yes", action="store_true", help="update: re-pin changed executable code "
                    "of an allowed extension without asking (needed without a terminal)")
    ex.add_argument("--json", action="store_true", help="list: print JSON")
    fx = sub.add_parser("fix", help="run safe mechanical repairs on kit setup")
    fx.add_argument("action", nargs="?", default="all",
                    choices=("all", "sync-profile", "wire-pointer", "shared-skills", "restore-bite",
                             "unlock-tests", "rotate-worklog", "normalise-status", "link-evidence",
                             "migrate-shards", "merge-driver"),
                    help="repair action to run (default: all, the setup repairs). The record "
                    "repairs preview unless --apply")
    fx.add_argument("--apply", action="store_true", help="record repairs: write the change")
    fx.add_argument("--unlock-tests", action="store_true",
                    help="also unlock tests in .ai-sdlc/test-lock.txt when running 'all'")
    fx.add_argument("--json", action="store_true", help="print repair result as JSON")
    ln = sub.add_parser("lens", help="the project lens: stack, dependencies, build errors, "
                                     "security, deploy, containers, env names and the agentic stack")
    ln.add_argument("--area", choices=("stack", "deps", "build", "security", "deploy", "env", "agents", "standards"),
                    help="print one area only; standards reads the coding conventions the code follows")
    ln.add_argument("--write", action="store_true",
                    help="with --area standards: draft <docs>/project/standards.md (never overwrites)")
    ln.add_argument("--user", action="store_true",
                    help="also list user-level skills, commands, subagents, MCP servers and plugins (~/.claude)")
    ln.add_argument("--json", action="store_true", help="print the lens as JSON")
    sl = sub.add_parser("slop", help="the slop filter: list the phrasings that make prose read "
                        "as machine-written, by line, with a fix for each")
    sl.add_argument("paths", nargs="*", help="files or directories (default: prose files "
                    "changed against HEAD or untracked); - reads standard input")
    sl.add_argument("--strict", action="store_true",
                    help="exit 1 when a file fails, whatever the charter's Slop filter row says")
    sl.add_argument("--guide", action="store_true", help="print the rules and what each one wants")
    sl.add_argument("--json", action="store_true")
    sy = sub.add_parser("sync", help="where this checkout stands against its remote and the "
                        "default branch; reports and names the next command, changes nothing")
    sy.add_argument("--fetch", action="store_true",
                    help="run `git fetch --prune` first, so the figures are current")
    sy.add_argument("--strict", action="store_true",
                    help="also exit 1 when the branch is behind the default branch")
    sy.add_argument("--json", action="store_true")
    sp = sub.add_parser("spec", help="living specs: list, show, validate, apply an item's change")
    sp.add_argument("action", choices=("list", "show", "validate", "apply"))
    sp.add_argument("target", nargs="?", help="capability (show) or work item ID (apply)")
    sp.add_argument("--write", action="store_true", help="apply: write the merge and archive the change")
    sp.add_argument("--strict", action="store_true", help="validate: exit 1 on any problem")
    sp.add_argument("--json", action="store_true")
    cl = sub.add_parser("claim", help="take a work item: an atomic claim shared by every worktree, "
                                      "plus its branch and (by default) its own worktree")
    cl.add_argument("item")
    cl.add_argument("--agent", help="who holds it (default: the identity trailers would use)")
    cl.add_argument("--worktree", help="where to create the worktree (default: ../<repo>-<ID>)")
    cl.add_argument("--no-worktree", action="store_true", help="create the branch only")
    cl.add_argument("--base", help="start the branch from this ref (default: HEAD)")
    cl.add_argument("--mark", action="store_true", help="also set the backlog row to In progress "
                    "(main worktree or item shard)")
    cl.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                    help="coordinate atomically across clones via refs/nuhut/claims/<ID> on origin")
    cl.add_argument("--json", action="store_true")
    for rl in (sub.add_parser("unclaim", help="free a claimed item"),
               sub.add_parser("release", help="deprecated: use unclaim (removed in 7.0)")):
        rl.add_argument("item")
        rl.add_argument("--agent", help="who is releasing (default: the identity trailers would use)")
        rl.add_argument("--force", action="store_true", help="override agent/host ownership check")
        rl.add_argument("--remove-worktree", action="store_true",
                        help="also remove its worktree (refused when dirty)")
        rl.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                        help="also delete refs/nuhut/claims/<ID> on origin")
        rl.add_argument("--json", action="store_true")
    dep = sub.add_parser("deploy", help="release records and the deploy ledger: record which "
                                        "version runs in which environment, and list them")
    dverbs = dep.add_subparsers(dest="deploy_action", metavar="{record,list}")
    dverbs.required = True
    drec = dverbs.add_parser("record", help="write <docs>/project/releases/<version>.json and "
                                            "append a line to <docs>/project/deploys.jsonl")
    drec.add_argument("--version", required=True, help="the version label, e.g. 1.4.0")
    drec.add_argument("--env", required=True, help="the environment, e.g. staging or prod")
    drec.add_argument("--from", dest="from_ref", help="the range starts after this ref "
                      "(default: the env's last deploy, else the newest record, else the "
                      "whole history)")
    drec.add_argument("--to", dest="to_ref", default="HEAD", help="the commit deployed "
                      "(default: HEAD)")
    drec.add_argument("--by", help="who deployed (default: git user.name); never an email")
    drec.add_argument("--accept-defects", dest="accept_defects", help="comma-separated open S2 "
                      "defect IDs an approver accepts for this release (S0 and S1 cannot be "
                      "accepted); needs --by <approver> and --reason")
    drec.add_argument("--reason", help="why the accepted defects may ship")
    drec.add_argument("--dry-run", action="store_true", help="say what it would write; write nothing")
    drec.add_argument("--json", action="store_true")
    dlist = dverbs.add_parser("list", help="which version runs in each environment")
    dlist.add_argument("--json", action="store_true")
    for verb, sp_ in (("record", drec), ("list", dlist)):
        sp_.formatter_class = argparse.RawDescriptionHelpFormatter
        sp_.epilog = "examples:\n" + "\n".join("  python3 .ai-sdlc/bin/sdlc.py " + e for e in EXAMPLES["deploy"]
                                               if e.startswith("deploy " + verb))
    cs = sub.add_parser("claims", help="list active claims")
    cs.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                    help="fetch refs/nuhut/claims/* from origin first")
    cs.add_argument("--json", action="store_true")
    pa = sub.add_parser("parallel", help="Ready items nobody holds, grouped so no two in a group "
                                         "touch the same files")
    pa.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                    help="include remote claims from refs/nuhut/claims/* on origin")
    pa.add_argument("--json", action="store_true")
    it_p = sub.add_parser("item", help="manage sharded work items under <docs>/project/items/<ID>.json")
    it_p.add_argument("action", choices=("add", "set", "show", "list", "triage"))
    it_p.add_argument("target", nargs="?", help="work item ID (auto-allocated on `add` when omitted)")
    it_p.add_argument("--id", dest="item_id_flag", help="optional explicit work item ID alias")
    it_p.add_argument("--title", help="item title")
    it_p.add_argument("--type", dest="item_type", choices=_shards_mod.ITEM_TYPES,
                      help="work item type (feat, fix, defect, chore, docs, refactor, test)")
    it_p.add_argument("--tier", choices=("1", "2", "3"), help="risk tier (1, 2, or 3)")
    it_p.add_argument("--effort", choices=("Lean", "Normal", "Beast", "lean", "normal", "beast", ""),
                      help="per-item effort override")
    it_p.add_argument("--owner", help="owner: a role slug (e.g. software-engineer) or a people.json handle")
    it_p.add_argument("--status", help="status, e.g. Ready, In progress, Parked, Done")
    it_p.add_argument("--depends", help="comma-separated dependency IDs")
    it_p.add_argument("--touch", help="comma-separated file or glob patterns for parallel scheduling")
    it_p.add_argument("--discovered", action="store_true",
                      help="apply charter Discovered defects triage policy (Parked, or Ready with passing bite)")
    it_p.add_argument("--waiting-on", dest="waiting_on", help="who Parked waits on")
    it_p.add_argument("--park-reason", dest="park_reason", help="decision Parked waits for")
    it_p.add_argument("--unblock-by", dest="unblock_by", help="who can unblock a Blocked item")
    it_p.add_argument("--later-when", dest="later_when", help="when a Deferred item becomes relevant")
    it_p.add_argument("--dropped-reason", dest="dropped_reason", help="reason an item was Dropped")
    it_p.add_argument("--summary", help="optional short summary")
    it_p.add_argument("--severity", help="defect severity S0 to S4 (CARD.md ladder); "
                      "S0 to S2 are shown at session start and in status")
    it_p.add_argument("--found-by", dest="found_by", help="who or what found a defect: a "
                      "person, a tool, a user report (never an email)")
    it_p.add_argument("--hotfix", action="store_true",
                      help="on `set`: mark the item a hotfix (records hotfix:true and the time; the "
                           "tier stays). finish then skips the pre-merge review and records a "
                           "retroactive review owed within the charter's Retroactive review within")
    it_p.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                      help="when auto-allocating ID on `add`, coordinate via refs/nuhut/seq on origin")
    it_p.add_argument("--json", action="store_true", help="print result as JSON")
    bug_p = sub.add_parser("bug", help="report a defect: a defect item with its severity, "
                           "and a defect report under <docs>/project/defects/")
    bug_p.add_argument("title", help="what is wrong, in one line")
    bug_p.add_argument("--severity", required=True, help="S0 to S4, by consequence (CARD.md)")
    bug_p.add_argument("--touch", help="comma-separated files or globs the defect lives in; "
                       "claim warns an agent whose item touches them")
    bug_p.add_argument("--repro", help="steps to reproduce, for the report")
    bug_p.add_argument("--found-by", dest="found_by", help="person, tool or user report (never an email)")
    bug_p.add_argument("--tier", choices=("1", "2", "3"), default="2", help="risk tier of the fix (default 2)")
    bug_p.add_argument("--status", help="status; default follows the charter's Discovered defects row")
    bug_p.add_argument("--json", action="store_true", help="print the item as JSON")
    hf_p = sub.add_parser("hotfix", help="mark a work item a hotfix: the same as `item set <ID> --hotfix`")
    hf_p.add_argument("item", help="work item ID")
    hf_p.add_argument("--json", action="store_true", help="print the item as JSON")
    dsp = sub.add_parser("dispatch", help="execute conflict-free waves of Ready items across isolated worker worktrees")
    dsp.add_argument("--workers", type=int, default=1, help="max parallel workers per wave (default: 1)")
    dsp.add_argument("--by", help="builder CLI: an agent record with build argv (claude, "
                     "codex, gemini, opencode, kiro, ...) or cmd:<command>")
    dsp.add_argument("--model", help="model override passed to the builder CLI and trailers")
    dsp.add_argument("--reviewer", help="optional independent reviewer CLI: claude, codex, gemini, or cmd:<command>")
    dsp.add_argument("--reviewer-model", dest="reviewer_model", help="model override for reviewer CLI")
    dsp.add_argument("--max-items", dest="max_items", type=int, default=0,
                     help="cap total dispatched items across waves (0 = all eligible)")
    dsp.add_argument("--tier", default="2,3", help="comma-separated allowed tiers (default: 2,3)")
    dsp.add_argument("--max-retries", dest="max_retries", type=int, default=1,
                     help="repair retries on failed verify/slop checks (default: 1)")
    dsp.add_argument("--timeout", type=int, default=1800, help="per-turn timeout in seconds (default: 1800)")
    dsp.add_argument("--worktree-root", dest="worktree_root", help="directory for worker worktrees")
    dsp.add_argument("--pr", action="store_true", help="push each finished branch and open a PR/MR instead of merging")
    dsp.add_argument("--no-merge", dest="no_merge", action="store_true",
                     help="keep finished branches unmerged instead of merging Done Tier 2/3 items")
    dsp.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                     help="coordinate claims and IDs across clones via refs/nuhut/* on origin")
    dsp.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="preview conflict-free waves without claiming or executing")
    dsp.add_argument("--json", action="store_true", help="print dispatch report as JSON")
    nid_p = sub.add_parser("next-id", help="atomically allocate the next work item or ADR ID")
    nid_p.add_argument("--kind", default="item", choices=("item", "adr"),
                       help="sequence kind: item (default) or adr")
    nid_p.add_argument("--sync-refs", dest="sync_refs", action="store_true",
                       help="coordinate atomically via refs/nuhut/seq CAS push on origin")
    nid_p.add_argument("--json", action="store_true", help="print allocated ID as JSON")
    rnd_p = sub.add_parser("render", help="materialize backlog.md and worklog.md summary views from shards")
    rnd_p.add_argument("--check", action="store_true",
                       help="exit 1 if backlog.md or worklog.md differs from rendered shards")
    rnd_p.add_argument("--json", action="store_true", help="print render report as JSON")
    ms_p = sub.add_parser("merge-shard", help="git merge driver: field-level 3-way merge of one "
                                              "items/<ID>.json shard (writes the result to OURS)")
    ms_p.add_argument("base", help="the common ancestor (%%O); an empty file means none")
    ms_p.add_argument("ours", help="our version (%%A); the merge result is written here")
    ms_p.add_argument("theirs", help="their version (%%B)")
    ms_p.add_argument("--marker-size", dest="marker_size", type=int, default=7,
                      help="length of the conflict markers (git's %%L)")
    nt = sub.add_parser("notify", help="the webhook named by the charter's Notify webhook row: "
                                       "show how it is set up, or send a test event")
    nt.add_argument("--test", action="store_true", help="send a test event and report the result")
    nt.add_argument("--ids-only", dest="ids_only", action="store_true",
                    help="leave the title out of the test payload")
    nt.add_argument("--json", action="store_true", help="print the result as JSON")
    au = sub.add_parser("audit", help="run the charter's dependency scanner in JSON mode and keep "
                                      "the vulnerable packages it reports")
    au.add_argument("--timeout", type=int, default=600, help="seconds before the scanner is stopped")
    au.add_argument("--strict", action="store_true", help="exit 1 on a critical or high vulnerability")
    au.add_argument("--json", action="store_true", help="print the stored result as JSON")
    mc = sub.add_parser("mcp", help="serve the records as read-only MCP tools over stdio "
                                    "(JSON-RPC 2.0), for Claude Code and other MCP clients")
    mc.add_argument("--allow-verify", dest="allow_verify", action="store_true",
                    help="also offer the verify tool, which runs the charter's checks and "
                    "writes evidence")
    for name, sp_ in sub.choices.items():
        if name in EXAMPLES:
            sp_.formatter_class = argparse.RawDescriptionHelpFormatter
            sp_.epilog = "examples:\n" + "\n".join("  python3 .ai-sdlc/bin/sdlc.py " + e for e in EXAMPLES[name])
    for cmd in COMMANDS.values():
        if cmd.core:
            continue
        ext = sub.add_parser(cmd.name, help=cmd.help)
        if cmd.verbs is None:
            if cmd.configure:
                cmd.configure(ext)
            continue
        verbs = ext.add_subparsers(dest=_VERB_DEST, parser_class=argparse.ArgumentParser)
        for verb, entry in cmd.verbs.items():
            vp = verbs.add_parser(verb, help=entry.help)
            if entry.configure:
                entry.configure(vp)
    return parser


def dispatch_command(project, opts, parser):
    """Run the handler COMMANDS holds for opts.command (and its verb, for a group)."""
    cmd = COMMANDS.get(opts.command)
    if cmd is None:
        parser.error("unknown command: %s" % opts.command)
    if cmd.verbs is None:
        return cmd.handler(project, opts, parser)
    verb = getattr(opts, _VERB_DEST, None)
    entry = cmd.verbs.get(verb) if verb else None
    if entry is None:
        sys.stderr.write("%s: give one of: %s\n" % (cmd.name, ", ".join(cmd.verbs)))
        return 2
    return entry.handler(project, opts, parser)


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    _load_extension_commands(argv)
    parser = build_parser()
    opts = parser.parse_args(argv)
    if not opts.command:
        parser.print_help()
        return 2
    opts._argv = list(argv)  # the deprecated `release` repeats the caller's arguments
    cmd = COMMANDS.get(opts.command)
    needs = cmd is None or cmd.needs_project
    project = Project(opts.root or default_root()) if needs else None
    return dispatch_command(project, opts, parser)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

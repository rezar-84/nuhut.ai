"""Living specs: what the system does now, as requirements with scenarios, and the
changes each work item makes to them.

Opt-in per project: the charter's **Specs** row says `on` or `off` (default off). When on,
docs/project/specs/<capability>.md describes current behaviour, and a work item that
changes behaviour carries docs/project/specs/changes/<ID>.md with ADDED, MODIFIED and
REMOVED requirements. `spec apply <ID> --write` merges the change into the living specs on
close and archives it. The headings are the ones OpenSpec uses, so one parser reads both:

    ### Requirement: <name>
    The system SHALL ...
    #### Scenario: <name>
    - **WHEN** ...
    - **THEN** ...

Existing openspec/ and Spec Kit specs are read too, read-only and labelled with their
source. Spec Kit's are free-form templates, so they are read best-effort (FR-### lines
and Given/When/Then scenarios) and never fail a check.

Called by sdlc.py (spec, doctor) and view.py. Standard library only.
This file must never contain two opening braces in a row (see sdlc.py).
"""

import datetime
import glob
import os
import re

REQ_RE = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$", re.M)
SCEN_RE = re.compile(r"^####\s+Scenario:\s*(.+?)\s*$", re.M)
DELTA_RE = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$", re.M | re.I)
CAP_LINE = re.compile(r"^\s*(?:\*\*)?Capability(?:\*\*)?:\s*`?([\w./\-]+)`?\s*$", re.M | re.I)


def enabled(project, labelled):
    cell = (labelled(project.charter or "", "Specs") or "").lower()
    return bool(re.search(r"`?\bon\b`?", cell)) and "`on` ·" not in cell


def specs_dir(project):
    return project.path(os.path.join(project.docs, "project", "specs"))


def _read(path):
    try:
        with open(path, encoding="utf-8") as h:
            return h.read()
    except (IOError, OSError):
        return ""


def parse_requirements(text):
    """[{name, body, scenarios[{name, body, when, then}], line}] in file order."""
    out = []
    marks = list(REQ_RE.finditer(text))
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(text)
        nxt = re.search(r"^##\s", text[m.end():end], re.M)
        if nxt:
            end = m.end() + nxt.start()
        block = text[m.end():end]
        scen_marks = list(SCEN_RE.finditer(block))
        body = block[:scen_marks[0].start()] if scen_marks else block
        scenarios = []
        for k, s in enumerate(scen_marks):
            s_end = scen_marks[k + 1].start() if k + 1 < len(scen_marks) else len(block)
            sbody = block[s.end():s_end].strip()
            scenarios.append({"name": s.group(1), "body": sbody,
                              "when": bool(re.search(r"\bWHEN\b", sbody)), "then": bool(re.search(r"\bTHEN\b", sbody))})
        cap = CAP_LINE.search(body)
        out.append({"name": m.group(1), "body": CAP_LINE.sub("", body).strip(), "capability": cap.group(1) if cap else "",
                    "scenarios": scenarios, "line": text[:m.start()].count("\n") + 1,
                    "text": text[m.start():end].rstrip() + "\n"})
    return out


def parse_spec(path, source="nuhut", capability=None):
    text = _read(path)
    title = re.search(r"^#\s+(.+)$", text, re.M)
    purpose = re.search(r"^##\s+Purpose\s*\n([\s\S]*?)(?=^##\s|\Z)", text, re.M)
    return {"capability": capability or os.path.splitext(os.path.basename(path))[0],
            "title": title.group(1).strip() if title else "", "purpose": purpose.group(1).strip() if purpose else "",
            "path": path, "source": source, "requirements": parse_requirements(text)}


def parse_change(path, item=None, source="nuhut"):
    """{item, path, sections{ADDED: [req], MODIFIED: [...], REMOVED: [...]}}."""
    text = _read(path)
    sections = {"ADDED": [], "MODIFIED": [], "REMOVED": [], "RENAMED": []}
    marks = list(DELTA_RE.finditer(text))
    default_cap = CAP_LINE.search(text[:marks[0].start()] if marks else text)
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(text)
        reqs = parse_requirements(text[m.start():end])
        for r in reqs:
            if not r["capability"] and default_cap:
                r["capability"] = default_cap.group(1)
        sections[m.group(1).upper()] += reqs
    return {"item": item or os.path.splitext(os.path.basename(path))[0], "path": path, "source": source, "sections": sections}


def load(project):
    """Living specs, pending changes, and imported (read-only) specs."""
    base = specs_dir(project)
    caps, changes = [], []
    if os.path.isdir(base):
        for path in sorted(glob.glob(os.path.join(base, "*.md"))):
            if os.path.basename(path).lower() == "readme.md":
                continue
            caps.append(parse_spec(path))
        for path in sorted(glob.glob(os.path.join(base, "changes", "*.md"))):
            changes.append(parse_change(path))
    imported = []
    # OpenSpec: openspec/specs/<capability>/spec.md and openspec/changes/<name>/specs/<capability>/spec.md
    for path in sorted(glob.glob(project.path(os.path.join("openspec", "specs", "**", "spec.md")), recursive=True)):
        cap = os.path.basename(os.path.dirname(path))
        imported.append(parse_spec(path, "openspec", cap))
    for path in sorted(glob.glob(project.path(os.path.join("openspec", "changes", "*", "specs", "**", "spec.md")), recursive=True)):
        if os.sep + "archive" + os.sep in path:
            continue
        ch = parse_change(path, item=path.split(os.sep + "changes" + os.sep)[1].split(os.sep)[0], source="openspec")
        cap = os.path.basename(os.path.dirname(path))
        for sect in ch["sections"].values():
            for r in sect:
                r["capability"] = r["capability"] or cap
        changes.append(ch)
    # Spec Kit: specs/<feature>/spec.md (and .specify/specs/), best-effort.
    if os.path.isdir(project.path(".specify")):
        for pattern in (os.path.join("specs", "*", "spec.md"), os.path.join(".specify", "specs", "*", "spec.md")):
            for path in sorted(glob.glob(project.path(pattern))):
                imported.append(parse_speckit(path))
    for spec in caps + imported:
        spec["path"] = os.path.relpath(spec["path"], project.root).replace(os.sep, "/")
    for ch in changes:
        ch["path"] = os.path.relpath(ch["path"], project.root).replace(os.sep, "/")
    return {"capabilities": caps, "changes": changes, "imported": imported}


def parse_speckit(path):
    """Spec Kit feature spec: FR-### requirements and Given/When/Then acceptance scenarios."""
    text = _read(path)
    title = re.search(r"^#\s+(?:Feature Specification:\s*)?(.+)$", text, re.M)
    reqs = []
    for m in re.finditer(r"^\s*[-*]\s*\*\*(FR-\d+)\*\*:?\s*(.+)$", text, re.M):
        reqs.append({"name": m.group(1), "body": m.group(2).strip(), "capability": "", "scenarios": [], "line": text[:m.start()].count("\n") + 1, "text": ""})
    scen = []
    for m in re.finditer(r"^\s*\d+\.\s*\*\*Given\*\*\s*(.+?),?\s*\*\*When\*\*\s*(.+?),?\s*\*\*Then\*\*\s*(.+)$", text, re.M):
        scen.append({"name": m.group(2)[:60], "body": "GIVEN %s WHEN %s THEN %s" % m.groups(), "when": True, "then": True})
    if scen:
        reqs.append({"name": "Acceptance scenarios", "body": "", "capability": "", "scenarios": scen, "line": 0, "text": ""})
    return {"capability": os.path.basename(os.path.dirname(path)), "title": title.group(1).strip() if title else "",
            "purpose": "", "path": path, "source": "spec-kit", "requirements": reqs, "best_effort": True}


def validate(project, data=None):
    """Problems with the native specs and changes: [{level, where, message}]. Imported specs
    are never judged."""
    data = data or load(project)
    out = []
    names = {}
    for cap in data["capabilities"]:
        for r in cap["requirements"]:
            names.setdefault(cap["capability"], set()).add(r["name"])
            where = "%s:%d" % (cap["path"], r["line"])
            if not re.search(r"\b(SHALL|MUST)\b", r["body"]):
                out.append({"level": "warn", "where": where, "message": "requirement %r does not say SHALL or MUST" % r["name"]})
            if not r["scenarios"]:
                out.append({"level": "warn", "where": where, "message": "requirement %r has no scenario" % r["name"]})
            for s in r["scenarios"]:
                if not (s["when"] and s["then"]):
                    out.append({"level": "warn", "where": where, "message": "scenario %r needs both WHEN and THEN" % s["name"]})
    for ch in data["changes"]:
        if ch["source"] != "nuhut":
            continue
        for kind, reqs in ch["sections"].items():
            for r in reqs:
                where = "%s:%d" % (ch["path"], r["line"])
                cap = r["capability"]
                if not cap:
                    out.append({"level": "warn", "where": where, "message": "%s requirement %r names no Capability" % (kind, r["name"])})
                    continue
                exists = r["name"] in names.get(cap, set())
                if kind == "ADDED" and exists:
                    out.append({"level": "warn", "where": where, "message": "ADDED %r already exists in %s" % (r["name"], cap)})
                if kind in ("MODIFIED", "REMOVED") and not exists:
                    out.append({"level": "warn", "where": where, "message": "%s %r is not in %s" % (kind, r["name"], cap)})
                if kind in ("ADDED", "MODIFIED") and not r["scenarios"]:
                    out.append({"level": "warn", "where": where, "message": "%s %r has no scenario" % (kind, r["name"])})
    return out


def apply_change(project, item, write=False, today=None):
    """Merge specs/changes/<item>.md into the living specs. Returns (plan, error): plan is a
    list of human-readable steps; nothing is written unless write=True. MODIFIED and REMOVED
    match by exact requirement name and refuse when the name is missing or repeated."""
    base = specs_dir(project)
    path = os.path.join(base, "changes", item + ".md")
    if not os.path.isfile(path):
        return None, "no spec change for %s (%s)" % (item, os.path.relpath(path, project.root))
    ch = parse_change(path, item)
    files, steps = {}, []

    def spec_text(cap):
        if cap not in files:
            p = os.path.join(base, cap + ".md")
            files[cap] = _read(p) or "# %s\n\n## Purpose\n\n_(what this capability is for)_\n\n## Requirements\n" % cap.replace("-", " ").title()
        return files[cap]

    for kind in ("REMOVED", "MODIFIED", "ADDED"):
        for r in ch["sections"][kind]:
            cap = r["capability"]
            if not cap:
                return None, "%s requirement %r names no Capability" % (kind, r["name"])
            text = spec_text(cap)
            current = [x for x in parse_requirements(text) if x["name"] == r["name"]]
            if kind == "ADDED":
                if current:
                    return None, "ADDED %r already exists in %s" % (r["name"], cap)
                files[cap] = text.rstrip("\n") + "\n\n" + CAP_LINE.sub("", r["text"])
                steps.append("add %r to %s" % (r["name"], cap))
            elif len(current) != 1:
                return None, "%s %r: %s in %s" % (kind, r["name"], "not found" if not current else "found %d times" % len(current), cap)
            elif kind == "MODIFIED":
                files[cap] = text.replace(current[0]["text"], CAP_LINE.sub("", r["text"]), 1)
                steps.append("replace %r in %s" % (r["name"], cap))
            else:
                files[cap] = text.replace(current[0]["text"], "", 1)
                steps.append("remove %r from %s" % (r["name"], cap))
    if write:
        for cap, text in files.items():
            with open(os.path.join(base, cap + ".md"), "w", encoding="utf-8") as h:
                h.write(re.sub(r"\n{3,}", "\n\n", text))
        archive = os.path.join(base, "changes", "archive")
        if not os.path.isdir(archive):
            os.makedirs(archive)
        stamp = (today or datetime.date.today()).isoformat()
        os.rename(path, os.path.join(archive, "%s-%s.md" % (stamp, item)))
        steps.append("archive the change to specs/changes/archive/%s-%s.md" % (stamp, item))
    return steps, None


def check(project, out, labelled, done_ids, today=None):
    """Doctor's view, only when the charter turns Specs on."""
    if not enabled(project, labelled):
        return
    data = load(project)
    for p in validate(project, data):
        out.add(p["level"], "specs", p["where"], p["message"])
    for ch in data["changes"]:
        if ch["source"] == "nuhut" and ch["item"] in done_ids:
            out.add("warn", "specs", ch["path"], "%s is Done but its spec change is not applied: "
                    "python3 .ai-sdlc/bin/sdlc.py spec apply %s --write" % (ch["item"], ch["item"]))

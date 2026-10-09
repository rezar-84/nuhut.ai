"""The model behind `sdlc.py view`: the project's records, read now, joined by work item ID.

Read-only. It parses the formats the kit's own templates define -- backlog tables by
header name, worklog entries by `## ID — title` heading or the compact Tier 3 line,
plans, reviews, defects and postmortems by file name -- and writes one self-contained page
to .ai-sdlc/view/index.html, which git ignores. Nothing it cannot read is dropped: it is
listed under "unread" so the page can say so.

Called by sdlc.py, which passes itself in as `rt` so the two share one set of parsers.
This file must never contain two opening braces in a row (see sdlc.py).
"""

import datetime
import hashlib
import json
import os
import re
import sys
import threading
import time
import webbrowser

# Backlog statuses, in the order the board shows them, and the column each belongs to.
COLUMNS = (("Now", ("In progress", "In review")), ("Next", ("Ready",)),
           ("Blocked", ("Blocked",)), ("Parked", ("Parked",)), ("Later", ("Deferred",)),
           ("Done", ("Done",)), ("Dropped", ("Dropped",)))
STEPS = ("Frame", "Plan", "Design review", "Build", "Verify", "Ship review", "Log", "Close")
RECORD_DIRS = ("plans", "reviews", "defects", "postmortems", "adr")
MAX_DOC_CHARS = 400000
MAX_COMMITS = 3000


def plain(cell):
    """A table cell without the markdown a human reads past."""
    cell = re.sub(r"_\([^)]*\)_", "", cell or "")
    cell = re.sub(r"\*\*|__|`|~~", "", cell)
    return cell.strip()


def column_of(status):
    for name, statuses in COLUMNS:
        if status in statuses:
            return name
    return "Other"


def headings(text):
    out, fence = [], False
    for n, line in enumerate(text.splitlines()):
        if line.startswith("```"):
            fence = not fence
        if fence:
            continue
        m = re.match(r"^(#{1,4})\s+(.*\S)\s*$", line)
        if m:
            out.append({"level": len(m.group(1)), "text": m.group(2), "line": n})
    return out


# ---------------------------------------------------------------- backlog

def backlog_tables(text):
    """Every table under a `## ` section whose header has ID and Status columns."""
    rows, section, header = [], "", None
    for n, line in enumerate(text.splitlines()):
        if line.startswith("## "):
            section, header = line[3:].strip(), None
            continue
        cells = None
        body = line.strip()
        if body.startswith("|") and body.endswith("|"):
            cells = [c.strip().replace("\\|", "|")
                     for c in re.split(r"(?<!\\)\|", body[1:-1])]
        if cells is None:
            header = None
            continue
        if header is None:
            names = [plain(c) for c in cells]
            header = names if "ID" in names and "Status" in names else False
            continue
        if header is False or set("".join(cells)) <= set("-: "):
            continue
        rows.append((section, n + 1, dict(zip(header, cells))))
    return rows


def epics(text, ids):
    """An optional `| Epic | Items | ... |` table. The kit does not require one."""
    out, header = [], None
    for line in text.splitlines():
        body = line.strip()
        if not (body.startswith("|") and body.endswith("|")):
            header = None
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", body[1:-1])]
        if header is None:
            names = [plain(c) for c in cells]
            header = names if "Epic" in names and "Items" in names else False
            continue
        if header is False or set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        members = [i for i in ids.findall(row.get("Items", ""))]
        extra = dict((k, plain(v)) for k, v in row.items() if k not in ("Epic", "Items"))
        out.append({"name": plain(row.get("Epic", "")), "items": members, "extra": extra})
    return out


# ---------------------------------------------------------------- worklog

def worklog_entries(text, source, id_re):
    """Full entries (`## ID — title` with `### ` subsections) and compact Tier 3 lines
    (`- YYYY-MM-DD · ID · request · ...`)."""
    entries, current, sub = [], None, None
    for n, line in enumerate(text.splitlines()):
        if line.startswith("## "):
            m = re.match(r"^##\s+(%s)(?:\s+\([^)]*\))?\s+[—-]+\s*(.*)$" % id_re.pattern, line)
            current = None
            if m:
                current = {"id": m.group(1), "title": m.group(2).strip(), "source": source,
                           "line": n + 1, "date": "", "status": "", "sections": {},
                           "compact": False}
                entries.append(current)
                sub = "_head"
            continue
        compact = re.match(r"^- (\d{4}-\d{2}-\d{2})\s+·\s+(%s)\s+·\s*(.*)$" % id_re.pattern, line)
        if compact:
            current, sub = None, None
            parts = [p.strip() for p in compact.group(3).split(" · ")]
            entries.append({"id": compact.group(2), "title": parts[0], "source": source,
                            "line": n + 1, "date": compact.group(1), "status": "Done",
                            "sections": {"Summary": " · ".join(parts[1:])},
                            "compact": True})
            continue
        if current is None:
            continue
        if line.startswith("### "):
            sub = line[4:].strip()
            current["sections"][sub] = ""
            continue
        if sub == "_head":
            m = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", line)
            if m:
                current["date"] = m.group(1)
            m = re.search(r"\*\*Status:\*\*\s*([A-Za-z]+)", line)
            if m:
                current["status"] = m.group(1)
            continue
        if sub:
            current["sections"][sub] += line + "\n"
    for entry in entries:
        entry["sections"] = dict((k, v.strip()) for k, v in entry["sections"].items())
    return entries


# ---------------------------------------------------------------- model

LEGACY_HIERARCHICAL = re.compile(
    r"^[A-Za-z][0-9]+(?:\.[0-9]+)*(?:-[a-z0-9]+)?(?:[–-][A-Za-z]?[0-9]+(?:\.[0-9]+)*)?$"
)
LEGACY_NUMERIC = re.compile(r"^(?:#?[0-9]+|GH-[0-9]+)$")


def is_valid_work_item_id(raw_id, prefix, legacy_prefixes=None):
    if not raw_id or raw_id.startswith("_(") or ("{" + "{") in raw_id:
        return False, "placeholder"
    if prefix and re.fullmatch(r"%s-[0-9]+" % re.escape(prefix), raw_id):
        return True, "standard"
    if legacy_prefixes and any(re.fullmatch(r"%s-[0-9]+" % re.escape(p), raw_id) for p in legacy_prefixes):
        return True, "legacy_prefix"
    if LEGACY_HIERARCHICAL.fullmatch(raw_id) or LEGACY_NUMERIC.fullmatch(raw_id):
        return True, "legacy"
    if re.fullmatch(r"^[A-Z]{2,4}-[0-9]+$", raw_id):
        return False, "wrong_prefix"
    return False, "invalid"


def build(rt, project):
    prefix = project.prefix
    legacy_prefixes = set(getattr(project, "legacy_prefixes", []))
    if not legacy_prefixes and project.charter:
        cell = rt.labelled(project.charter, "Legacy issue prefix") or \
               rt.labelled(project.charter, "Legacy prefixes") or ""
        legacy_prefixes.update(re.findall(r"`([^`]+)`", cell))
        prefix_cell = rt.labelled(project.charter, "Work item prefix") or ""
        m_leg = re.search(r"legacy(?: prefixes?)?:\s*([^\n|]+)", prefix_cell, re.I)
        if m_leg:
            legacy_prefixes.update(re.findall(r"`([^`]+)`", m_leg.group(1)))

    docs_root = os.path.join(project.docs, "project")
    backlog_rel = os.path.join(docs_root, "backlog.md")
    backlog = rt.read(project.path(backlog_rel))
    rows = backlog_tables(backlog)

    known_ids = set()
    for section, line, row in rows:
        raw_id = plain(row.get("ID", ""))
        ok, _ = is_valid_work_item_id(raw_id, prefix, legacy_prefixes)
        if ok:
            known_ids.add(raw_id)
    known_ids.update(re.findall(r"\b[E][0-9]+\b", backlog))

    worklog_text = project.worklog_texts() if hasattr(project, "worklog_texts") else ""
    if worklog_text:
        wl_headings = re.findall(r"^##\s+([A-Za-z0-9#][A-Za-z0-9_#.–-]*)(?:\s+\([^)]*\))?\s+[—-]", worklog_text, re.M)
        for hid in wl_headings:
            ok, _ = is_valid_work_item_id(hid, prefix, legacy_prefixes)
            if ok:
                known_ids.add(hid)
        wl_compact = re.findall(r"^- \d{4}-\d{2}-\d{2}\s+·\s+([A-Za-z0-9#][A-Za-z0-9_#.–-]*)\s+·", worklog_text, re.M)
        for cid in wl_compact:
            ok, _ = is_valid_work_item_id(cid, prefix, legacy_prefixes)
            if ok:
                known_ids.add(cid)

    patterns = []
    if prefix:
        patterns.append(r"%s-[0-9]+" % re.escape(prefix))
    if legacy_prefixes:
        for lp in sorted(legacy_prefixes):
            patterns.append(r"%s-[0-9]+" % re.escape(lp))
    patterns.append(r"[A-Za-z][0-9]+(?:\.[0-9]+)+(?:-[a-z0-9]+)?")
    extra_known = [i for i in known_ids if not (prefix and re.fullmatch(r"%s-[0-9]+" % re.escape(prefix), i))
                   and not re.fullmatch(r"[A-Za-z][0-9]+(?:\.[0-9]+)+(?:-[a-z0-9]+)?", i)]
    if extra_known:
        patterns.append("|".join(re.escape(i) for i in sorted(extra_known, key=len, reverse=True)))
    id_re = re.compile(r"\b(?:" + "|".join(patterns) + r")\b") if patterns else re.compile(r"(?!x)x")

    model = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "project": plain(rt.labelled(project.charter, "Project") or "") or
                   os.path.basename(project.root),
        "prefix": prefix, "docs_dir": project.docs,
        "git_head": project.git("rev-parse", "--short", "HEAD").strip(),
        "git_branch": project.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "columns": [c for c, _ in COLUMNS] + ["Other"], "steps": list(STEPS),
        "items": {}, "order": [], "epics": [], "worklog": [], "docs": [], "unread": [],
        "alerts": [], "id_pattern": id_re.pattern,
    }
    if not prefix and not legacy_prefixes and not known_ids:
        model["unread"].append({"path": project.charter_path,
                                "reason": "no work item prefix in the charter, so no ID "
                                          "can be recognised"})

    # Backlog rows.
    for section, line, row in rows:
        raw_id = plain(row.get("ID", ""))
        ok, kind = is_valid_work_item_id(raw_id, prefix, legacy_prefixes)
        if not ok:
            if kind == "wrong_prefix":
                model["unread"].append({"path": "%s:%d" % (backlog_rel, line),
                                        "reason": "ID %r is not %s-###" % (raw_id, prefix)})
            elif kind == "invalid":
                model["unread"].append({"path": "%s:%d" % (backlog_rel, line),
                                        "reason": "ID %r is not a recognised work item ID" % raw_id})
            continue
        status = plain(row.get("Status", ""))
        known = ("ID", "Task", "Tier", "Owner role", "Depends on", "Status")
        item = model["items"].setdefault(raw_id, {"id": raw_id})
        item.update({
            "title": plain(row.get("Task", "")), "tier": plain(row.get("Tier", "")),
            "owner": plain(row.get("Owner role", "")),
            "depends": id_re.findall(row.get("Depends on", "")),
            "depends_text": plain(row.get("Depends on", "")),
            "status": status, "column": column_of(status), "section": section,
            "row": "%s:%d" % (backlog_rel, line),
            "extra": dict((k, plain(v)) for k, v in row.items() if k not in known and v),
        })
        if raw_id not in model["order"]:
            model["order"].append(raw_id)
    model["epics"] = epics(backlog, id_re)

    # Worklog, active then archive.
    sources = [os.path.join(docs_root, "worklog.md")]
    archive = project.path(os.path.join(docs_root, "worklog-archive"))
    if os.path.isdir(archive):
        sources += [os.path.join(docs_root, "worklog-archive", n)
                    for n in sorted(os.listdir(archive)) if n.endswith(".md")]
    for rel in sources:
        model["worklog"].extend(worklog_entries(rt.read(project.path(rel)), rel, id_re))

    # Every markdown record under project/, plus the contract and the card.
    doc_paths = ["AGENTS.md", os.path.join(project.docs, "CARD.md")]
    for base, _, files in sorted(os.walk(project.path(docs_root))):
        for name in sorted(files):
            if name.endswith(".md"):
                doc_paths.append(os.path.relpath(os.path.join(base, name), project.root))
    for rel in doc_paths:
        text = rt.read(project.path(rel))
        if not text:
            continue
        kind = "record"
        parts = rel.replace(os.sep, "/").split("/")
        for d in RECORD_DIRS:
            if d in parts[:-1]:
                kind = d
        if parts[-1] == "README.md" and kind in RECORD_DIRS:
            kind = "index"
        if "worklog-archive" in parts:
            kind = "archive"
        truncated = len(text) > MAX_DOC_CHARS
        meta = rt.frontmatter(text)
        doc = {"path": rel.replace(os.sep, "/"), "kind": kind,
               "title": next((h["text"] for h in headings(text) if h["level"] == 1),
                             parts[-1]),
               "meta": meta, "headings": headings(text),
               "mentions": sorted(set(id_re.findall(text))),
               "text": text[:MAX_DOC_CHARS], "truncated": truncated}
        stem = parts[-1][:-3] if parts[-1].endswith(".md") else parts[-1]
        m = re.match(r"^(%s)(?:-(design|ship))?$" % id_re.pattern, stem)
        if not m:
            m = re.match(r"^(%s)(?:-(design|ship))?" % id_re.pattern, parts[-1])
        doc["owner_id"] = m.group(1) if m and kind in RECORD_DIRS else ""
        doc["stage"] = (m.group(2) or "") if m else ""
        model["docs"].append(doc)

    # Commits that name an ID, plus full git traceability metadata.
    log = project.git("log", "-n", str(MAX_COMMITS), "--date=short",
                      "--format=%h%x1f%an%x1f%ad%x1f%s")
    commits = {}
    all_commits = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            sha, author, date, subject = parts
        elif len(parts) == 3:
            sha, author, date, subject = parts[0], "", parts[1], parts[2]
        else:
            continue
        found = sorted(set(id_re.findall(subject)))
        all_commits.append({"sha": sha, "author": author, "date": date,
                            "subject": subject, "items": found})
        for fid in found:
            commits.setdefault(fid, []).append({"sha": sha, "author": author,
                                                "date": date, "subject": subject})

    curr_branch = model.get("git_branch") or project.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    status_raw = project.git("status", "--porcelain")
    modified_files = []
    for s_line in status_raw.splitlines():
        if s_line.strip():
            modified_files.append({"status": s_line[:2].strip(), "path": s_line[3:].strip()})
    clean = len(modified_files) == 0

    branch_log = project.git("branch", "--format=%(refname:short)%09%(committerdate:short)%09%(subject)")
    branches = []
    for b_line in branch_log.splitlines():
        bparts = b_line.split("\t")
        if not bparts or not bparts[0].strip():
            continue
        bname = bparts[0].strip()
        bdate = bparts[1].strip() if len(bparts) > 1 else ""
        bsubj = bparts[2].strip() if len(bparts) > 2 else ""
        bitems = sorted(set(id_re.findall(bname) + id_re.findall(bsubj)))
        branches.append({
            "name": bname, "current": bname == curr_branch,
            "date": bdate, "subject": bsubj, "items": bitems,
        })

    total_commits = len(all_commits)
    linked_commits = sum(1 for c in all_commits if c["items"])
    untracked_commits = total_commits - linked_commits
    rate = round((linked_commits / total_commits * 100), 1) if total_commits else 0.0

    model["git"] = {
        "branch": curr_branch,
        "clean": clean,
        "modified_count": len(modified_files),
        "modified_files": modified_files[:100],
        "branches": branches,
        "commits": all_commits[:1000],
        "stats": {
            "total": total_commits,
            "linked": linked_commits,
            "untracked": untracked_commits,
            "rate": rate,
        },
    }

    # Join everything onto the items. An ID seen only in the records still gets a node.
    def item(i):
        if i not in model["items"]:
            model["items"][i] = {"id": i, "title": "", "status": "", "column": "Other",
                                 "orphan": True, "depends": [], "extra": {}}
            model["order"].append(i)
        return model["items"][i]
    for n, entry in enumerate(model["worklog"]):
        it = item(entry["id"])
        it.setdefault("worklog", []).append(n)
        if not it.get("title"):
            it["title"] = entry["title"]
    for n, doc in enumerate(model["docs"]):
        if doc["owner_id"]:
            item(doc["owner_id"]).setdefault("records", []).append(n)
        for mention in doc["mentions"]:
            if mention in model["items"] and mention != doc["owner_id"]:
                model["items"][mention].setdefault("mentioned_in", []).append(n)
    for i, found in commits.items():
        if i in model["items"]:
            model["items"][i]["commits"] = found[:50]
    for it in model["items"].values():
        for dep in it.get("depends", []):
            if dep in model["items"]:
                model["items"][dep].setdefault("dependents", []).append(it["id"])
        it["steps"] = lifecycle(it, model)

    model["metrics"] = metrics(rt, project, model)

    # The mechanical doctor findings are the home page's alerts.
    try:
        model["alerts"] = rt.doctor(project)
    except Exception as exc:  # the view must open even when a check breaks
        model["alerts"] = [{"level": "warn", "check": "view", "where": "",
                            "message": "doctor could not run: %s" % exc}]
    return model


def lifecycle(it, model):
    """Frame -> Close, each step done / missing / n/a, from which records exist."""
    records = [model["docs"][n] for n in it.get("records", [])]
    kinds = set((d["kind"], d["stage"]) for d in records)
    entries = [model["worklog"][n] for n in it.get("worklog", [])]
    tier = it.get("tier", "")
    verified = any(any(re.search(r"verif", name, re.I) for name in e["sections"])
                   or "verified:" in e["sections"].get("Summary", "") for e in entries)
    done = it.get("column") == "Done"
    started = it.get("column") in ("Now", "Done")  # before work starts, nothing is owed yet

    def need(present, required=True):
        return "done" if present else ("missing" if required else "n/a")
    return {
        "Frame": need(bool(it.get("row"))),
        "Plan": need(("plans", "") in kinds, tier == "1" and started),
        "Design review": need(("reviews", "design") in kinds, tier == "1" and started),
        "Build": need(bool(it.get("commits")), done),
        "Verify": need(verified, done),
        "Ship review": need(("reviews", "ship") in kinds, tier == "1" and done),
        "Log": need(bool(entries), done),
        "Close": need(done, False) if not done else "done",
    }


# ---------------------------------------------------------------- metrics

def _date(value):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2.0


def metrics(rt, project, model, today=None):
    """Process measures computed only from what the records and git already hold. Each is
    labelled leading (moves early) or lagging (confirms later), and says what it is from."""
    today = today or datetime.date.today()
    items = model["items"].values()
    out = []

    def add(name, kind, value, basis):
        out.append({"name": name, "kind": kind, "value": value, "basis": basis})

    def first_commit(it):
        dates = [_date(c["date"]) for c in it.get("commits", [])]
        dates = [d for d in dates if d]
        return min(dates) if dates else None

    now = [it for it in items if it.get("column") == "Now"]
    ages = [(today - first_commit(it)).days for it in now if first_commit(it)]
    add("Work in progress", "leading", "%d items, oldest %s" % (
        len(now), "%d days" % max(ages) if ages else "unknown"),
        "Now rows; age from each item's first commit")

    waiting = [it for it in items if it.get("column") in ("Blocked", "Parked")]
    waits = [(today - _date(it["extra"].get("Since"))).days for it in waiting
             if _date(it.get("extra", {}).get("Since"))]
    add("Waiting on a human", "leading", "%d items, oldest %s" % (
        len(waiting), "%d days" % max(waits) if waits else "unknown"),
        "Blocked and Parked rows, their Since cell")

    runs = []
    folder = project.path(os.path.join(".ai-sdlc", "evidence"))
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            try:
                with open(os.path.join(folder, name, "summary.json"), encoding="utf-8") as h:
                    runs.append(json.load(h))
            except (IOError, OSError, ValueError):
                continue
    ran = [r for r in runs if any(e["result"].startswith("Verified") for e in r["stages"])]
    passed = [r for r in ran if not any(e["result"].startswith("Verified: fail")
                                        for e in r["stages"])]
    add("Verify pass rate", "leading",
        "%d of %d runs (%d%%)" % (len(passed), len(ran), 100 * len(passed) // len(ran))
        if ran else "no runs recorded", "sdlc.py verify evidence under .ai-sdlc/evidence/")

    done = [it for it in items if it.get("column") == "Done"]
    recent = [it for it in done if _date(it.get("extra", {}).get("Completed"))
              and (today - _date(it["extra"]["Completed"])).days <= 28]
    add("Throughput", "lagging", "%d items in the last 4 weeks" % len(recent),
        "Done rows, their Completed cell")

    leads = []
    for it in done:
        start, end = first_commit(it), _date(it.get("extra", {}).get("Completed"))
        if start and end and end >= start:
            leads.append((end - start).days)
    lead = _median(leads)
    add("Lead time", "lagging", "median %s days over %d items" % (lead, len(leads))
        if lead is not None else "unknown", "first commit naming the item to its Completed date")

    gaps = [it["id"] for it in done
            if any(v == "missing" for v in it.get("steps", {}).values())]
    add("Done with a lifecycle gap", "lagging", "%d of %d" % (len(gaps), len(done)) +
        (": " + ", ".join(gaps[:8]) + (" …" if len(gaps) > 8 else "") if gaps else ""),
        "Done items missing a plan, review, commit or worklog entry their tier requires")

    revised = 0
    for it in items:
        plan = next((model["docs"][n] for n in it.get("records", [])
                     if model["docs"][n]["kind"] == "plans"), None)
        start = first_commit(it)
        if not plan or not start:
            continue
        log = project.git("log", "--date=short", "--format=%ad", "--", plan["path"])
        if any(_date(d) and _date(d) > start for d in log.split()):
            revised += 1
    add("Plans updated after build started", "lagging", str(revised),
        "plan files changed after the item's first commit: deviations that were recorded")
    return out


# ---------------------------------------------------------------- page

def render(model, template):
    data = json.dumps(model, ensure_ascii=False, separators=(",", ":"))
    # Safe inside <script>: nothing can close the tag or start a comment.
    data = (data.replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return template.replace("/*NUHUT_MODEL*/null", data, 1)


def print_metrics(rt, project, opts):
    model = build(rt, project)
    if getattr(opts, "json", False):
        print(json.dumps(model["metrics"], indent=2))
        return 0
    width = max(len(m["name"]) for m in model["metrics"])
    for m in model["metrics"]:
        print("%-7s  %-*s  %s" % (m["kind"], width, m["name"], m["value"]))
        print("         %-*s  from: %s" % (width, "", m["basis"]))
    return 0


# ---------------------------------------------------------------- live mode

def watched_paths(project):
    """Every file the model is read from. A change to any of them, or a new commit,
    changes the fingerprint."""
    paths = [project.path("AGENTS.md"), project.path(os.path.join(project.docs, "CARD.md"))]
    for base, _, files in os.walk(project.path(os.path.join(project.docs, "project"))):
        paths.extend(os.path.join(base, n) for n in files if n.endswith(".md"))
    evidence = project.path(os.path.join(".ai-sdlc", "evidence"))
    if os.path.isdir(evidence):
        paths.extend(os.path.join(evidence, n, "summary.json") for n in os.listdir(evidence))
    return sorted(paths)


def fingerprint(project):
    digest = hashlib.sha256()
    for path in watched_paths(project):
        try:
            st = os.stat(path)
        except OSError:
            continue
        digest.update(("%s %d %d\n" % (path, st.st_mtime_ns, st.st_size)).encode("utf-8"))
    digest.update(project.git("rev-parse", "HEAD").encode("utf-8"))
    return digest.hexdigest()[:16]


class Live(object):
    """The current model, rebuilt only when the fingerprint moves, and at most once per
    interval however many tabs are polling."""

    def __init__(self, rt, project, template, interval):
        self.rt, self.project, self.template, self.interval = rt, project, template, interval
        self.lock = threading.Lock()
        self.checked = 0.0
        self.version = None
        self.model_json = b""
        self.page = b""
        self.refresh(force=True)

    def refresh(self, force=False):
        with self.lock:
            now = time.time()
            if not force and now - self.checked < self.interval:
                return self.version
            self.checked = now
            version = fingerprint(self.project)
            if version == self.version and not force:
                return self.version
            try:
                model = build(self.rt, self.project)
            except Exception as exc:  # a record caught half-written; keep the last good one
                sys.stderr.write("view: rebuild failed, keeping the last model: %s\n" % exc)
                return self.version
            model["version"] = version
            model["live_interval"] = self.interval
            self.version = version
            self.model_json = json.dumps(model, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")
            self.page = render(model, self.template).encode("utf-8")
            if not force:
                sys.stderr.write("view: records changed, model rebuilt (%s)\n"
                                 % time.strftime("%H:%M:%S"))
            return self.version


def serve(rt, project, template, opts):
    try:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    except ImportError:  # Python < 3.7
        raise SystemExit("--serve needs Python 3.7 or newer")
    interval = max(1, int(getattr(opts, "interval", 2) or 2))
    live = Live(rt, project, template, interval)

    class Handler(BaseHTTPRequestHandler):
        server_version = "nuhut-view"

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            # The page carries the records' contents. Refuse any Host but this machine,
            # so a web page cannot reach it through DNS rebinding.
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
            if host not in ("127.0.0.1", "localhost", "::1"):
                return self._send(403, b"forbidden\n", "text/plain; charset=utf-8")
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                live.refresh()
                return self._send(200, live.page, "text/html; charset=utf-8")
            if path == "/version":
                return self._send(200, (live.refresh() or "").encode("utf-8"),
                                  "text/plain; charset=utf-8")
            if path == "/model.json":
                live.refresh()
                return self._send(200, live.model_json, "application/json; charset=utf-8")
            return self._send(404, b"not found\n", "text/plain; charset=utf-8")

        do_HEAD = do_GET

        def log_message(self, *args):  # the terminal shows rebuilds, not every poll
            pass

    port = int(getattr(opts, "port", 8765))
    server = None
    for candidate in ([port] if port == 0 else range(port, port + 10)):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit("view: ports %d-%d are all in use; pass --port" % (port, port + 9))
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("view: live at %s (local only). The page follows the records as they change; "
          "Ctrl+C stops it." % url)
    sys.stdout.flush()
    if not getattr(opts, "no_open", False):
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nview: stopped")
    finally:
        server.server_close()
def build_map_svg(model, interactive=True):
    """Build a standalone, formatted SVG mind map of the project records."""
    ids = model.get("order", [])
    items = model.get("items", {})

    def clip(text, n):
        return text if len(text) <= n else text[:n - 1] + "…"

    def esc(text):
        return (str(text or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

    def item_node(iid):
        it = items.get(iid, {})
        title = it.get("title", "")
        return {
            "key": "i:" + iid,
            "label": iid + "  " + clip(title, 42),
            "full": iid + " " + title,
            "col": it.get("column", "Other"),
            "route": "item/" + iid,
        }

    by_col = []
    for c in model.get("columns", {}):
        kids = [item_node(i) for i in ids if items.get(i, {}).get("column") == c]
        if kids:
            by_col.append({"key": "c:" + c, "label": c, "col": c, "children": kids})

    owners = {}
    for i in ids:
        it = items.get(i, {})
        o = it.get("owner")
        if o and it.get("column") not in ("Done", "Dropped"):
            owners.setdefault(o, []).append(i)
    by_owner = [{"key": "o:" + o, "label": o, "children": [item_node(i) for i in owners[o]]}
                for o in sorted(owners)]

    kinds = {}
    for d in model.get("docs", []):
        if d.get("kind") != "index":
            kinds.setdefault(d.get("kind"), []).append(d)

    kind_names = {
        "record": "Records", "plans": "Plans", "reviews": "Reviews", "defects": "Defects",
        "postmortems": "Postmortems", "adr": "ADRs", "archive": "Worklog archive"
    }
    by_doc = []
    for k in sorted(kinds):
        children = []
        for d in kinds[k]:
            path = d.get("path", "")
            name = path.split("/")[-1]
            children.append({"key": "d:" + path, "label": clip(name, 40), "full": path})
        by_doc.append({"key": "k:" + k, "label": kind_names.get(k, k), "children": children})

    root = {
        "key": "root",
        "label": model.get("project") or "Project",
        "children": [
            {"key": "g:status", "label": "Work by status", "children": by_col},
            {"key": "g:owner", "label": "Open work by owner role", "children": by_owner},
            {"key": "g:docs", "label": "Documents", "children": by_doc},
        ]
    }
    epics = model.get("epics", [])
    if epics:
        epic_kids = []
        for e in epics:
            e_items = [item_node(i) for i in e.get("items", []) if i in items]
            epic_kids.append({"key": "e:" + e.get("name", ""), "label": e.get("name", ""), "children": e_items})
        root["children"].insert(1, {"key": "g:epics", "label": "Epics", "children": epic_kids})

    ROW = 24
    COLW = 230
    rows = [0]
    max_depth = [0]
    nodes = []
    links = []

    def place(n, depth):
        max_depth[0] = max(max_depth[0], depth)
        kids = n.get("children", [])
        if kids and depth < 2:
            for k in kids:
                place(k, depth + 1)
                links.append((n, k))
            n["y"] = (kids[0]["y"] + kids[-1]["y"]) / 2
        else:
            n["y"] = rows[0] * ROW + 24
            rows[0] += 1
        n["x"] = depth * COLW + 24
        nodes.append(n)

    place(root, 0)
    width = max(760, (max_depth[0] + 1) * COLW + 300)
    height = max(360, rows[0] * ROW + 48)
    proj_name = esc(model.get("project") or "Project")

    COL_HEX = {
        "Now": "#0969da", "Next": "#8250df", "Blocked": "#cf222e", "Parked": "#bf8700",
        "Later": "#6e7781", "Done": "#2f8f5b", "Dropped": "#afb8c1", "Other": "#6e7781"
    }

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s Mind Map">'
        % (width, height, width, height, proj_name),
        '  <title>%s Mind Map</title>' % proj_name,
        '  <defs>',
        '    <style type="text/css"><![CDATA[',
        '      :root {',
        '        --bg: #ffffff; --panel: #f6f8fa; --line: #d0d7de; --text: #1f2328; --muted: #57606a;',
        '        --link: #0969da; --accent: #2f8f5b; --c-Now: #0969da; --c-Next: #8250df;',
        '        --c-Blocked: #cf222e; --c-Parked: #bf8700; --c-Later: #6e7781; --c-Done: #2f8f5b;',
        '        --c-Dropped: #afb8c1; --c-Other: #6e7781;',
        '      }',
        '      @media (prefers-color-scheme: dark) {',
        '        :root {',
        '          --bg: #0d1117; --panel: #161b22; --line: #30363d; --text: #e6edf3; --muted: #9da7b3;',
        '          --link: #4493f8; --accent: #3fb950; --c-Now: #4493f8; --c-Next: #a371f7;',
        '          --c-Blocked: #f85149; --c-Parked: #d29922; --c-Later: #8b949e; --c-Done: #3fb950;',
        '          --c-Dropped: #484f58; --c-Other: #8b949e;',
        '        }',
        '      }',
        '      text { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }',
        '      .bg-canvas { fill: var(--bg, #ffffff); }',
        '      .map-link { fill: none; stroke: var(--line, #d0d7de); stroke-width: 1.5; stroke-linecap: round; transition: stroke .15s ease, stroke-width .15s ease; }',
        '      .map-link:hover { stroke: var(--link, #0969da); stroke-width: 2.2; }',
        '      .node-dot { stroke-width: 2; cursor: pointer; transition: r .15s ease; }',
        '      .node-dot:hover { r: 7.5; }',
        '      .node-label { font-size: 13px; fill: var(--text, #1f2328); cursor: pointer; user-select: none; }',
        '      .node-label.nav { fill: var(--link, #0969da); font-weight: 500; }',
        '      .node-label.nav:hover { text-decoration: underline; }',
        '      .node-count { font-size: 11px; fill: var(--muted, #57606a); user-select: none; }',
        '      .svg-btn { cursor: pointer; user-select: none; }',
        '      .svg-btn rect { fill: var(--panel, #f6f8fa); stroke: var(--line, #d0d7de); stroke-width: 1; rx: 4; ry: 4; }',
        '      .svg-btn:hover rect { fill: var(--line, #d0d7de); }',
        '      .svg-btn text { font-size: 11px; font-weight: 600; fill: var(--text, #1f2328); text-anchor: middle; dominant-baseline: central; }',
        '    ]]></style>',
        '  </defs>',
        '',
        '  <!-- Background -->',
        '  <rect width="100%" height="100%" fill="var(--bg, #ffffff)" class="bg-canvas" />',
        '',
        '  <g id="viewport">',
        '    <!-- Connectors -->',
        '    <g id="links">',
    ]

    for a, b in links:
        mx = (a["x"] + b["x"]) / 2
        d = "M%d %d C%d %d %d %d %d %d" % (
            a["x"] + 6, a["y"], mx, a["y"], mx, b["y"], b["x"] - 6, b["y"]
        )
        lines.append('      <path class="map-link" d="%s" fill="none" stroke="var(--line, #d0d7de)" stroke-width="1.5" />' % d)

    lines.append('    </g>')
    lines.append('')
    lines.append('    <!-- Nodes -->')
    lines.append('    <g id="nodes">')

    for n in nodes:
        kids = n.get("children", [])
        is_open = bool(kids and n.get("depth", 0) < 2)
        stroke_hex = COL_HEX.get(n.get("col", ""), "#2f8f5b")
        stroke_val = "var(--c-%s, %s)" % (n["col"], stroke_hex) if n.get("col") else "var(--accent, #2f8f5b)"
        fill_hex = stroke_hex if (kids and not is_open) else "#ffffff"
        fill_val = stroke_val if (kids and not is_open) else "var(--bg, #ffffff)"
        r = 6 if kids else 4
        label_cls = "node-label" + (" nav" if n.get("route") else "")
        full_text = esc(n.get("full") or n.get("label", ""))
        label_text = esc(n.get("label", ""))

        lines.append('      <g class="map-node" data-key="%s">' % esc(n.get("key", "")))
        lines.append('        <circle class="node-dot" cx="%d" cy="%d" r="%d" fill="%s" stroke="%s" stroke-width="2">'
                     % (n["x"], n["y"], r, fill_val, stroke_val))
        lines.append('          <title>%s</title>' % full_text)
        lines.append('        </circle>')
        lines.append('        <text class="%s" x="%d" y="%d" font-family="system-ui, sans-serif" font-size="13px" fill="var(--text, #1f2328)">'
                     '%s<title>%s</title></text>' % (label_cls, n["x"] + 10, n["y"] + 4, label_text, full_text))
        if kids and not is_open:
            cx = n["x"] + 14 + len(n.get("label", "")) * 7.2
            lines.append('        <text class="node-count" x="%.1f" y="%d" font-family="system-ui, sans-serif" font-size="11px" fill="var(--muted, #57606a)">(%d)</text>'
                         % (cx, n["y"] + 4, len(kids)))
        lines.append('      </g>')

    lines.append('    </g>')
    lines.append('  </g>')

    if interactive:
        lines.extend([
            '',
            '  <!-- Interactive Navigation Controls -->',
            '  <g id="controls" transform="translate(%d, 14)">' % (width - 156),
            '    <rect width="142" height="30" rx="6" ry="6" fill="var(--panel, #f6f8fa)" stroke="var(--line, #d0d7de)" stroke-width="1" />',
            '    <g class="svg-btn" id="btn-zoom-in" transform="translate(5, 3)">',
            '      <rect width="24" height="24" /><text x="12" y="12">+</text>',
            '      <title>Zoom in</title>',
            '    </g>',
            '    <g class="svg-btn" id="btn-zoom-out" transform="translate(33, 3)">',
            '      <rect width="24" height="24" /><text x="12" y="12">−</text>',
            '      <title>Zoom out</title>',
            '    </g>',
            '    <g class="svg-btn" id="btn-reset" transform="translate(61, 3)">',
            '      <rect width="42" height="24" /><text x="21" y="12">100%</text>',
            '      <title>Reset view</title>',
            '    </g>',
            '    <g class="svg-btn" id="btn-theme" transform="translate(107, 3)">',
            '      <rect width="26" height="24" /><text x="13" y="12">◐</text>',
            '      <title>Toggle theme</title>',
            '    </g>',
            '  </g>',
            '',
            '  <!-- Interactive Pan & Zoom Script -->',
            '  <script type="text/javascript"><![CDATA[',
            '    (function () {',
            '      var svg = document.documentElement;',
            '      var vp = document.getElementById("viewport");',
            '      if (!vp) return;',
            '      var scale = 1, panX = 0, panY = 0;',
            '      var dragging = false, startX = 0, startY = 0;',
            '      function update() {',
            '        vp.setAttribute("transform", "translate(" + panX.toFixed(2) + "," + panY.toFixed(2) + ") scale(" + scale.toFixed(3) + ")");',
            '      }',
            '      svg.addEventListener("mousedown", function (e) {',
            '        if (e.target.closest && e.target.closest("#controls")) return;',
            '        dragging = true;',
            '        startX = e.clientX - panX;',
            '        startY = e.clientY - panY;',
            '        svg.style.cursor = "grabbing";',
            '      });',
            '      window.addEventListener("mousemove", function (e) {',
            '        if (!dragging) return;',
            '        panX = e.clientX - startX;',
            '        panY = e.clientY - startY;',
            '        update();',
            '      });',
            '      window.addEventListener("mouseup", function () {',
            '        if (dragging) { dragging = false; svg.style.cursor = "default"; }',
            '      });',
            '      svg.addEventListener("wheel", function (e) {',
            '        e.preventDefault();',
            '        var delta = e.deltaY < 0 ? 1.15 : 0.87;',
            '        var next = Math.max(0.15, Math.min(6, scale * delta));',
            '        var r = svg.getBoundingClientRect();',
            '        var mx = e.clientX - r.left, my = e.clientY - r.top;',
            '        panX = mx - (mx - panX) * (next / scale);',
            '        panY = my - (my - panY) * (next / scale);',
            '        scale = next;',
            '        update();',
            '      }, { passive: false });',
            '      var bIn = document.getElementById("btn-zoom-in");',
            '      if (bIn) bIn.addEventListener("click", function () { scale = Math.min(6, scale * 1.25); update(); });',
            '      var bOut = document.getElementById("btn-zoom-out");',
            '      if (bOut) bOut.addEventListener("click", function () { scale = Math.max(0.15, scale * 0.8); update(); });',
            '      var bRes = document.getElementById("btn-reset");',
            '      if (bRes) bRes.addEventListener("click", function () { scale = 1; panX = 0; panY = 0; update(); });',
            '      var bTh = document.getElementById("btn-theme");',
            '      if (bTh) bTh.addEventListener("click", function () {',
            '        var curr = svg.getAttribute("data-theme");',
            '        var isDark = curr === "dark" || (!curr && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);',
            '        var next = isDark ? "light" : "dark";',
            '        svg.setAttribute("data-theme", next);',
            '        if (next === "dark") {',
            '          svg.style.setProperty("--bg", "#0d1117"); svg.style.setProperty("--text", "#e6edf3");',
            '          svg.style.setProperty("--line", "#30363d"); svg.style.setProperty("--panel", "#161b22");',
            '        } else {',
            '          svg.style.setProperty("--bg", "#ffffff"); svg.style.setProperty("--text", "#1f2328");',
            '          svg.style.setProperty("--line", "#d0d7de"); svg.style.setProperty("--panel", "#f6f8fa");',
            '        }',
            '      });',
            '    })();',
            '  ]]></script>',
        ])

    lines.append('</svg>')
    lines.append('')
    return '\n'.join(lines)


def run(rt, project, opts):
    here = os.path.dirname(os.path.abspath(__file__))
    template = rt.read(os.path.join(here, "view.html"))
    if not template:
        raise SystemExit("view.html is missing next to view.py; re-run the installer "
                         "with --upgrade")
    if getattr(opts, "serve", False):
        return serve(rt, project, template, opts)
    model = build(rt, project)
    out_dir = project.path(os.path.join(".ai-sdlc", "view"))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    ignore = os.path.join(out_dir, ".gitignore")
    if not os.path.exists(ignore):
        # The page copies the records' contents; it is a view, not a record.
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n")
    out = os.path.join(out_dir, "index.html")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(render(model, template))

    svg_content = build_map_svg(model)
    svg_out = os.path.join(out_dir, "map.svg")
    with open(svg_out, "w", encoding="utf-8") as handle:
        handle.write(svg_content)

    custom_svg = getattr(opts, "svg", None)
    if custom_svg:
        target_svg = project.path(custom_svg) if not os.path.isabs(custom_svg) else custom_svg
        os.makedirs(os.path.dirname(target_svg), exist_ok=True)
        with open(target_svg, "w", encoding="utf-8") as handle:
            handle.write(svg_content)
        print("wrote %s" % os.path.relpath(target_svg, project.root))

    if getattr(opts, "json", False):
        print(json.dumps(model, indent=2, ensure_ascii=False))
        return 0
    counts = {}
    for it in model["items"].values():
        counts[it["column"]] = counts.get(it["column"], 0) + 1
    print("view: %d items (%s), %d worklog entries, %d documents%s"
          % (len(model["items"]),
             ", ".join("%s %d" % (c, counts[c]) for c in model["columns"] if c in counts),
             len(model["worklog"]), len(model["docs"]),
             ", %d unread" % len(model["unread"]) if model["unread"] else ""))
    print("wrote %s and %s" % (os.path.relpath(out, project.root), os.path.relpath(svg_out, project.root)))
    if not getattr(opts, "no_open", False):
        webbrowser.open("file://" + out)
    return 0

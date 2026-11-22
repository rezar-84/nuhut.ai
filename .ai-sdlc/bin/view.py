"""The model behind `sdlc.py view`: the project's records, read now, joined by work item ID.

Read-only. It parses the formats the kit's own templates define -- backlog tables by
header name, worklog entries by `## ID — title` heading or the compact Tier 3 line,
plans, reviews, defects and postmortems by file name -- and writes one self-contained page
to .ai-sdlc/view/index.html, which git ignores. Nothing it cannot read is dropped: it is
listed under "unread" so the page can say so.

Also from git and the evidence folder: `flow`, the backlog's column counts at each
committed day (one `git show` per day, capped), and `evidence`, the last verify runs
reduced to stage results. Both feed charts; neither is a reason for the page not to open.

Called by sdlc.py, which passes itself in as `rt` so the two share one set of parsers.
This file must never contain two opening braces in a row (see sdlc.py).
"""

import datetime
import errno
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser

# Backlog statuses, in the order the board shows them, and the column each belongs to.
COLUMNS = (("Now", ("In progress", "In review")), ("Next", ("Ready",)),
           ("Blocked", ("Blocked",)), ("Parked", ("Parked",)), ("Later", ("Deferred",)),
           ("Done", ("Done",)), ("Dropped", ("Dropped",)))
STEPS = ("Frame", "Plan", "Design review", "Build", "Verify", "Ship review", "Log", "Close")
RECORD_DIRS = ("plans", "reviews", "defects", "postmortems", "adr", "epics")
MAX_DOC_CHARS = 400000
MAX_COMMITS = 3000


def plain(cell):
    """A table cell without the markdown a human reads past."""
    cell = re.sub(r"_\([^)]*\)_", "", cell or "")
    cell = re.sub(r"\*\*|__|`|~~", "", cell)
    return cell.strip()


# Statuses projects write that mean one of the kit's columns. Matched without case; the
# item keeps the status text it was written with.
STATUS_SYNONYMS = {
    "doing": "Now", "wip": "Now", "in development": "Now", "in-progress": "Now", "active": "Now",
    "planned": "Next", "pending": "Next", "to do": "Next", "todo": "Next", "backlog": "Next",
    "proposed": "Next", "open": "Next", "queued": "Next",
    "on hold": "Parked", "on-hold": "Parked", "waiting": "Parked",
    "completed": "Done", "complete": "Done", "closed": "Done", "shipped": "Done",
    "merged": "Done", "released": "Done", "verified": "Done",
    "cancelled": "Dropped", "canceled": "Dropped", "won't do": "Dropped", "wont do": "Dropped",
    "rejected": "Dropped", "abandoned": "Dropped",
}


def column_of(status):
    for name, statuses in COLUMNS:
        if status in statuses:
            return name
    key = re.sub(r"\s+", " ", plain(status or "")).strip().lower()
    for name, statuses in COLUMNS:
        if key in (s.lower() for s in statuses):
            return name
    if key in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[key]
    # "Completed (merged 8acbc4a)", "Shipped — v2.1": a synonym with a note.
    head = re.split(r"\s*[(\[—–:]", key, 1)[0].strip()
    if head != key and head in STATUS_SYNONYMS:
        return STATUS_SYNONYMS[head]
    # "Done on epic branch", "Done (owner sign-off pending)": done, with a note.
    if re.match(r"^done\b", key):
        return "Done"
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
            # One entry may close several items: `## ACME-1, ACME-2 — title` (or `/`, `&`).
            m = re.match(r"^##\s+((?:%s)(?:\s*[,&/]\s*(?:%s))*)(?:\s+\([^)]*\))?\s+[—-]+\s*(.*)$"
                         % (id_re.pattern, id_re.pattern), line)
            current = None
            if m:
                ids = re.findall(id_re.pattern, m.group(1))
                current = {"id": ids[0], "ids": ids, "title": m.group(m.lastindex).strip(),
                           "source": source, "line": n + 1, "date": "", "status": "",
                           "sections": {}, "compact": False}
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
    own_cache = getattr(project, "_build_cache", None) is None
    if own_cache:
        project._build_cache = {}
    try:
        return _build_inner(rt, project)
    finally:
        if own_cache:
            project._build_cache = None


def _build_inner(rt, project):
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
    backlog = project.records("backlog.md") if hasattr(project, "records") else rt.read(project.path(backlog_rel))
    rows = backlog_tables(backlog)
    try:
        shards_mod = rt.runtime_module("shards")
        shard_items = shards_mod.load_items(project)
        wl_shards = shards_mod.load_worklog_shards(project)
        sharded_mode = shards_mod.has_shards(project)
    except Exception:
        shard_items, wl_shards, sharded_mode = {}, [], False

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
        sh = shard_items.get(raw_id) or {}
        item.update({
            "title": sh.get("title") or plain(row.get("Task", "")),
            "tier": plain(row.get("Tier", "")),
            "owner": plain(row.get("Owner role", "")),
            "depends": id_re.findall(row.get("Depends on", "")),
            "depends_text": plain(row.get("Depends on", "")),
            "status": status, "column": column_of(status), "section": section,
            "row": ("%s/project/items/%s.json" % (project.docs, raw_id)) if sh else ("%s:%d" % (backlog_rel, line)),
            "extra": dict((k, plain(v)) for k, v in row.items() if k not in known and v),
        })
        if sh:
            item["type"] = sh.get("type", "feat")
            item["touch"] = sh.get("touch", [])
            item["effort"] = sh.get("effort", "")
        if raw_id not in model["order"]:
            model["order"].append(raw_id)
    model["epics"] = epics(backlog, id_re)
    model["shards"] = {"enabled": sharded_mode, "items": len(shard_items), "worklogs": len(wl_shards)}

    # Worklog: per-item shards first (deduplicated against rendered worklog.md), then active and archive.
    seen_wl_ids = set()
    for wl_id, wl_rel, wl_body in wl_shards:
        for entry in worklog_entries(wl_body, wl_rel, id_re):
            model["worklog"].append(entry)
        seen_wl_ids.add(wl_id)
    sources = [os.path.join(docs_root, "worklog.md")]
    archive = project.path(os.path.join(docs_root, "worklog-archive"))
    if os.path.isdir(archive):
        sources += [os.path.join(docs_root, "worklog-archive", n)
                    for n in sorted(os.listdir(archive)) if n.endswith(".md")]
    for rel in sources:
        for entry in worklog_entries(rt.read(project.path(rel)), rel, id_re):
            if entry.get("id") and entry["id"] in seen_wl_ids:
                continue
            model["worklog"].append(entry)

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

    # Commits that name an ID, plus full git traceability metadata and graph linkages.
    log = project.git("log", "--all", "-n", str(MAX_COMMITS), "--date=short",
                      "--format=%h%x1f%p%x1f%d%x1f%an%x1f%ad%x1f%s")
    commits = {}
    all_commits = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) >= 6:
            sha, parents_raw, refs_raw, author, date = parts[0], parts[1], parts[2], parts[3], parts[4]
            subject = "\x1f".join(parts[5:])
            parents = [p for p in parents_raw.split() if p]
            refs = [r.strip() for r in refs_raw.strip(" ()").split(",") if r.strip()]
        elif len(parts) == 4:
            sha, author, date, subject = parts
            parents = []
            refs = []
        elif len(parts) == 3:
            sha, author, date, subject = parts[0], "", parts[1], parts[2]
            parents = []
            refs = []
        else:
            continue
        found = sorted(set(id_re.findall(subject)) | rt.id_ranges(subject, prefix))
        all_commits.append({"sha": sha, "parents": parents, "refs": refs,
                            "author": author, "date": date,
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

    remote_raw = project.git("remote", "get-url", "origin").strip()
    remote_web = ""
    if remote_raw:
        if remote_raw.startswith("git@") and ":" in remote_raw:
            host, rpath = remote_raw[4:].split(":", 1)
            rpath = rpath.rstrip("/")
            if rpath.endswith(".git"):
                rpath = rpath[:-4]
            remote_web = "https://%s/%s" % (host, rpath)
        elif remote_raw.startswith("http://") or remote_raw.startswith("https://"):
            rpath = remote_raw.rstrip("/")
            if rpath.endswith(".git"):
                rpath = rpath[:-4]
            remote_web = rpath

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
        "remote_url": remote_web,
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
        for entry_id in entry.get("ids") or [entry["id"]]:
            it = item(entry_id)
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
    # Who reviewed each item, and what the evidence ledger holds for it.
    try:
        ledger_rows = rt.ledger(project)
        index = rt.commit_index(project, set(model["items"]))
    except Exception:
        ledger_rows, index = [], {}
    for item_id, it in model["items"].items():
        reviews = []
        for rec in rt.review_records(project, item_id):
            f = rec["fields"]
            if not f:
                continue
            reviews.append({"file": rec["file"],
                            "stage": "design" if "-design-" in rec["file"] or rec["file"].endswith("-design.md") else "ship",
                            "reviewer": "%s / %s" % (f.get("Reviewer agent", "?"), f.get("Reviewer model", "?")),
                            "author": f.get("Author", ""),
                            "independent": f.get("Independence", "").startswith("independent")})
        if reviews:
            it["reviews"] = reviews
        commits = index.get(item_id)
        if commits:
            trailer_by_sha = {}
            for full_sha, _, tags in commits:
                trailer_by_sha[full_sha] = tags
                trailer_by_sha[full_sha[:7]] = tags
            for c_obj in it.get("commits", []):
                ctags = trailer_by_sha.get(c_obj.get("sha", ""), {})
                if ctags.get("Agent"):
                    c_obj["agent"] = ctags["Agent"]
                if ctags.get("Model"):
                    c_obj["model"] = ctags["Model"]
                if ctags.get("Tokens"):
                    c_obj["tokens"] = ctags["Tokens"]
                if ctags.get("Minutes"):
                    c_obj["minutes"] = ctags["Minutes"]
        waived = [r for r in ledger_rows if r.get("waived_by") and r.get("item") == item_id]
        if waived:
            it["waived"] = {"by": waived[-1]["waived_by"], "reason": waived[-1].get("reason", ""),
                            "time": waived[-1].get("time", "")}
        if commits and ledger_rows:
            rows = rt.evidence_matches(project, item_id, ledger_rows, commits)
            if rows:
                it["evidence"] = [{"stage": r.get("stage"), "result": r.get("result"),
                                   "commit": (r.get("commit") or "")[:7], "time": r.get("time"),
                                   "dirty": bool(r.get("dirty"))} for r in rows[-20:]]
        author = next((tags for _, _, tags in (commits or []) if tags.get("Model") or tags.get("Agent")), None)
        if author:
            it["author"] = "%s / %s" % (author.get("Agent", "?"), author.get("Model", "?"))
    rules = rt.tier_rules(project)
    for it in model["items"].values():
        for dep in it.get("depends", []):
            if dep in model["items"]:
                model["items"][dep].setdefault("dependents", []).append(it["id"])
        it["steps"] = lifecycle(it, model, rt, rules)
        has_plan = any(model["docs"][n]["kind"] == "plans" for n in it.get("records", []))
        if has_plan and hasattr(rt, "plan_check") and it.get("column") == "Now":
            try:
                pc_res, _ = rt.plan_check(project, it["id"])
                if pc_res:
                    it["plan_check"] = pc_res
            except Exception:
                pass
        it["thread"] = build_item_thread(it, model)

    model["evidence"] = evidence_runs(project)
    model["runs"] = run_records(project)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import specs as specs_mod
        spec_data = specs_mod.load(project)
        spec_data["enabled"] = specs_mod.enabled(project, rt.labelled) if hasattr(rt, "labelled") else False
        spec_data["problems"] = specs_mod.validate(project, spec_data) if spec_data["enabled"] else []
        archived = {}
        arch_dir = os.path.join(specs_mod.specs_dir(project), "changes", "archive")
        if os.path.isdir(arch_dir):
            for name in sorted(os.listdir(arch_dir)):
                m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", name)
                if m:
                    archived[m.group(2)] = m.group(1)
        spec_data["archived"] = archived
        model["specs"] = spec_data
        # Each item's spec change joins its thread, pending or applied.
        for ch in spec_data["changes"]:
            it = model["items"].get(ch["item"])
            if it is not None:
                counts = dict((k, len(v)) for k, v in ch["sections"].items() if v)
                it.setdefault("thread", []).append({"kind": "spec_change", "order": 25, "date": "", "path": ch["path"],
                                                    "title": "Spec change", "counts": counts, "source": ch["source"], "applied": False})
        for item, day in archived.items():
            it = model["items"].get(item)
            if it is not None:
                it.setdefault("thread", []).append({"kind": "spec_change", "order": 25, "date": day, "title": "Spec change applied",
                                                    "counts": {}, "source": "nuhut", "applied": True,
                                                    "path": os.path.join(project.docs, "project", "specs", "changes", "archive", "%s-%s.md" % (day, item))})
        for it in model["items"].values():
            it.get("thread", []).sort(key=lambda e: (e.get("order", 50), e.get("date") or ""))
    except Exception as exc:
        model["specs"] = {"capabilities": [], "changes": [], "imported": [], "enabled": False, "error": str(exc)}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import claims as claims_mod
        model["claims"] = claims_mod.list_claims(project)
        model["parallel"] = claims_mod.parallel(project, rt, sys.modules[__name__])
    except Exception as exc:  # claims are a convenience; the page opens without them
        model["claims"], model["parallel"] = [], {"groups": [], "conflicts": [], "plan_first": [], "candidates": [],
                                                  "error": str(exc)}
    try:
        # people.json (default branch): a claim's person and a handle owner show by name.
        model["people"] = dict((h, {"name": e.get("name", ""), "github": e.get("github", ""),
                                    "roles": e.get("roles", [])})
                               for h, e in rt.people_entries(project).items())
    except Exception:
        model["people"] = {}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import releases as releases_mod
        model["deploys"] = releases_mod.view_model(project)
    except Exception as exc:  # a broken ledger never stops the page opening
        model["deploys"] = {"envs": {}, "skipped": 0, "records": {}, "error": str(exc)}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import shards as shards_mod
        import dispatch as dispatch_mod
        items_d = shards_mod.items_dir(project)
        wl_d = shards_mod.worklog_dir(project)
        ldg_d = shards_mod.ledger_dir(project)
        model["factory"] = {
            "sharded": shards_mod.has_shards(project),
            "item_shards": len([n for n in os.listdir(items_d) if n.endswith(".json")]) if os.path.isdir(items_d) else 0,
            "worklog_shards": len([n for n in os.listdir(wl_d) if n.endswith(".md")]) if os.path.isdir(wl_d) else 0,
            "ledger_shards": len([n for n in os.listdir(ldg_d) if n.endswith(".jsonl")]) if os.path.isdir(ldg_d) else 0,
            "dispatch_runs": dispatch_mod.load_dispatch_runs(project, limit=20),
        }
    except Exception as exc:
        model["factory"] = {"sharded": False, "item_shards": 0, "worklog_shards": 0, "ledger_shards": 0,
                            "dispatch_runs": [], "error": str(exc)}
    model["metrics"] = metrics(rt, project, model)
    try:
        model["flow"] = flow(rt, project, model)
    except Exception as exc:  # a chart is never a reason for the view not to open
        model["flow"] = {"dates": [], "series": {}, "error": str(exc)}

    try:
        model["kit"] = rt.kit_status(project) if hasattr(rt, "kit_status") else {}
    except Exception as exc:
        model["kit"] = {"error": str(exc)}

    # The mechanical doctor findings are the home page's alerts.
    try:
        found = rt.doctor(project)
        # Findings accepted by `doctor --baseline` leave the alerts; their count stays
        # on the page so the history is never hidden.
        model["alerts"] = [f for f in found if not f.get("accepted")]
        accepted = [f for f in found if f.get("accepted")]
        model["accepted"] = {"count": len(accepted),
                             "date": accepted[0]["accepted"] if accepted else ""}
    except Exception as exc:  # the view must open even when a check breaks
        model["alerts"] = [{"level": "warn", "check": "view", "where": "",
                            "message": "doctor could not run: %s" % exc}]
    return model


def build_item_thread(it, model):
    """Build a causally and chronologically ordered list of action/thread events for an item."""
    events = []
    # 1. Frame event
    events.append({
        "kind": "frame",
        "order": 10,
        "date": (it.get("extra") or {}).get("Since") or "",
        "title": it.get("title") or it["id"],
        "status": it.get("status") or it.get("column") or "Unknown",
        "tier": it.get("tier") or "",
        "owner": it.get("owner") or "",
        "depends": it.get("depends") or [],
        "dependents": it.get("dependents") or [],
    })
    # 2. Plan & Design Review & ADR/Defect records
    for doc_idx in it.get("records", []):
        doc = model["docs"][doc_idx]
        dkind = doc.get("kind", "record")
        dstage = doc.get("stage", "")
        ddate = (doc.get("meta") or {}).get("last-reviewed", "")
        if dkind in ("plans", "epics"):
            events.append({
                "kind": "plan",
                "order": 20,
                "date": ddate,
                "path": doc["path"],
                "title": doc["title"],
                "doc_index": doc_idx,
            })
        elif dkind == "reviews" and dstage == "design":
            events.append({
                "kind": "design_review",
                "order": 30,
                "date": ddate,
                "path": doc["path"],
                "title": doc["title"],
                "doc_index": doc_idx,
            })
        elif dkind == "reviews":
            events.append({
                "kind": "ship_review",
                "order": 60,
                "date": ddate,
                "path": doc["path"],
                "title": doc["title"],
                "doc_index": doc_idx,
            })
        else:
            events.append({
                "kind": dkind,
                "order": 35,
                "date": ddate,
                "path": doc["path"],
                "title": doc["title"],
                "doc_index": doc_idx,
            })
    # 3. Commits (oldest first in thread feed)
    for c in reversed(it.get("commits", [])):
        events.append({
            "kind": "commit",
            "order": 40,
            "date": c.get("date", ""),
            "sha": c.get("sha", ""),
            "author": c.get("author", ""),
            "agent": c.get("agent", ""),
            "model": c.get("model", ""),
            "tokens": c.get("tokens", ""),
            "minutes": c.get("minutes", ""),
            "subject": c.get("subject", ""),
        })
    # 4. Evidence / Verify runs
    if it.get("evidence"):
        by_commit = {}
        for ev in it["evidence"]:
            key = (ev.get("time") or "")[:10] + "@" + (ev.get("commit") or "")
            by_commit.setdefault(key, {
                "kind": "verify",
                "order": 50,
                "date": (ev.get("time") or "")[:10],
                "time": ev.get("time") or "",
                "commit": ev.get("commit") or "",
                "dirty": bool(ev.get("dirty")),
                "stages": [],
            })["stages"].append({"stage": ev.get("stage"), "result": ev.get("result")})
        events.extend(by_commit.values())
    # 5. Human gate / blockage alert if Parked or Blocked
    if it.get("column") in ("Blocked", "Parked"):
        extra = it.get("extra") or {}
        events.append({
            "kind": "gate",
            "order": 55,
            "date": extra.get("Since") or "",
            "column": it.get("column"),
            "waiting_on": extra.get("Waiting on whom") or extra.get("Who can unblock") or extra.get("Unblocked by") or "",
            "decision": extra.get("Decision needed") or extra.get("Blocked on") or "",
        })
    # 6. Worklog entries
    for w_idx in it.get("worklog", []):
        w = model["worklog"][w_idx]
        events.append({
            "kind": "worklog",
            "order": 70,
            "date": w.get("date") or "",
            "title": w.get("title") or "",
            "compact": bool(w.get("compact")),
            "sections": w.get("sections") or {},
            "worklog_index": w_idx,
        })
    events.sort(key=lambda e: (e.get("order", 50), e.get("date") or ""))
    return events


def section_text(text, heading):
    """The body under a `## heading` (any level), without the fill-in markers."""
    m = re.search(r"(?m)^#+ +%s\b[^\n]*\n(.*?)(?=^#+ |\Z)" % re.escape(heading), text or "", re.S)
    return re.sub(r"_\([^)]*\)_", "", m.group(1)).strip() if m else ""


def lifecycle(it, model, rt, rules="Standard"):
    """Frame -> Close, each step done / unproven / skipped / missing / n/a, from which
    records exist and what the item's tier owes (rt.required_steps). An epic file is the
    epic's plan, and its filled Design review section is the design review
    (process/11-epics.md). A worklog that says a check was Not run, with the reason, is an
    honest skip; one that reports results no verify run backs is unproven. Neither is a gap."""
    records = [model["docs"][n] for n in it.get("records", [])]
    kinds = set((d["kind"], d["stage"]) for d in records)
    epic_docs = [d for d in records if d["kind"] == "epics"]
    entries = [model["worklog"][n] for n in it.get("worklog", [])]
    done = it.get("column") == "Done"
    started = it.get("column") in ("Now", "Done")  # before work starts, nothing is owed yet
    owed = rt.required_steps(rt.tier_of(it.get("tier", "")), rules, started, done)

    verified = any(str(e.get("result", "")).startswith("Verified: pass")
                   for e in it.get("evidence", []))
    # What the worklog says about checks: its Verified section (or one named like it,
    # "Verification", "Quality gates verified"), or a compact line's `verified:` field.
    reports = [body.strip() for e in entries for name, body in e["sections"].items()
               if re.search(r"(?i)verif|quality gate", name)]
    summaries = [e["sections"].get("Summary", "") for e in entries]
    not_run = bool(it.get("waived")) or \
        any(re.match(r"(?i)[-*\s]*not run\b", r) for r in reports) or \
        any(re.search(r"(?i)\bverified:\s*not run", s) for s in summaries)
    # Results reported with no verify run behind them: recorded, not proven. doctor's
    # evidence check names each one; the step is not a gap.
    claimed = any(r and not re.match(r"(?i)[-*\s]*(not run|absent|none|n/a)\b", r)
                  for r in reports) or any(rt.claims_verified(s) for s in summaries)
    stages = set(r["stage"] for r in it.get("reviews", []))
    # An epic's plan and design review cover the items its Items section lists; a Tier 1
    # member still writes its own plan (CARD.md, Development method).
    member_of = [d for d in model["docs"] if d["kind"] == "epics" and d not in epic_docs
                 and it["id"] in re.findall(r"[A-Za-z][A-Za-z0-9]*-[0-9]+",
                                            section_text(d["text"], "Items"))]
    has_plan = ("plans", "") in kinds or bool(epic_docs) or \
        (bool(member_of) and rt.tier_of(it.get("tier", "")) != "1")
    has_design = (("reviews", "design") in kinds or "design" in stages or
                  any(section_text(d["text"], "Design review") for d in epic_docs + member_of))

    def need(step, present, skipped=False, unproven=False):
        if present:
            return "done"
        if unproven:
            return "unproven"
        if skipped:
            return "skipped"
        return "missing" if owed[step] else "n/a"
    return {
        "Frame": need("Frame", bool(it.get("row"))),
        "Plan": need("Plan", has_plan),
        "Design review": need("Design review", has_design),
        "Build": need("Build", bool(it.get("commits"))),
        "Verify": need("Verify", verified, not_run, claimed and not not_run),
        "Ship review": need("Ship review", ("reviews", "ship") in kinds or "ship" in stages),
        "Log": need("Log", bool(entries)),
        "Close": "done" if done else "n/a",
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


MAX_FLOW_POINTS = 180
MAX_EVIDENCE_RUNS = 30


_FLOW_BLOB_CACHE = {}


def flow(rt, project, model, today=None):
    """Backlog column counts at each committed day the backlog changed, oldest first,
    plus today's working tree. Each point is a snapshot of that commit's backlog, so a
    row that moved sections counts once, in its new column. Dropped is left out: it is a
    record, not flow."""
    today = today or datetime.date.today()
    names = [name for name, _ in COLUMNS if name != "Dropped"]
    backlog_rel = os.path.join(project.docs, "project", "backlog.md")
    backlog_git_path = backlog_rel.replace(os.sep, "/")
    legacy = set(getattr(project, "legacy_prefixes", []) or [])
    picked, seen = [], set()
    for line in project.git("log", "--format=%H %cs", "--", backlog_rel).splitlines():
        sha, _, date = line.partition(" ")
        if date and date not in seen:  # newest first: the first sighting is the last of its day
            seen.add(date)
            picked.append((date, sha))
        if len(picked) >= MAX_FLOW_POINTS:
            break
    picked.reverse()
    dates, series = [], dict((name, []) for name in names)
    for date, sha in picked:
        cache_key = (project.root, sha, backlog_git_path)
        if cache_key in _FLOW_BLOB_CACHE:
            text = _FLOW_BLOB_CACHE[cache_key]
        else:
            text = project.git("show", "%s:%s" % (sha, backlog_git_path))
            if len(_FLOW_BLOB_CACHE) > 512:
                _FLOW_BLOB_CACHE.clear()
            _FLOW_BLOB_CACHE[cache_key] = text
        if not text:
            continue
        counts = dict((name, 0) for name in names)
        for _, status, _ in rt.backlog_rows(text, project.prefix, legacy or None):
            col = column_of(status)
            if col in counts:
                counts[col] += 1
        dates.append(date)
        for name in names:
            series[name].append(counts[name])
    counts = dict((name, 0) for name in names)
    for it in model["items"].values():
        if it.get("column") in counts:
            counts[it["column"]] += 1
    label = today.isoformat()
    if dates and dates[-1] == label:
        dates.pop()
        for name in names:
            series[name].pop()
    dates.append(label)
    for name in names:
        series[name].append(counts[name])
    return {"dates": dates, "series": series}


def evidence_runs(project):
    """The last verify runs under .ai-sdlc/evidence/, oldest first, reduced to what a
    trend needs: when, on what commit, and each stage's result."""
    runs = []
    folder = project.path(os.path.join(".ai-sdlc", "evidence"))
    if not os.path.isdir(folder):
        return runs
    for name in sorted(os.listdir(folder))[-MAX_EVIDENCE_RUNS:]:
        try:
            with open(os.path.join(folder, name, "summary.json"), encoding="utf-8") as h:
                data = json.load(h)
        except (IOError, OSError, ValueError):
            continue
        runs.append({
            "folder": name,
            "generated": data.get("generated", ""),
            "git_head": data.get("git_head", ""),
            "dirty": bool(data.get("dirty")),
            "stages": [{"stage": e.get("stage", ""), "result": e.get("result", ""),
                        "seconds": e.get("seconds")} for e in data.get("stages", [])],
        })
    return runs


MAX_RUNS = 50
MAX_LOG_BYTES = 200000
RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z[A-Za-z0-9-]*$")


def runs_folder(project):
    return project.path(os.path.join(".ai-sdlc", "runs"))


def save_run(rt, project, record):
    """Keep one command the live page ran, redacted, under the git-ignored runs folder,
    so the cockpit can show it after the response is gone. Only the newest MAX_RUNS stay."""
    folder = runs_folder(project)
    os.makedirs(folder, exist_ok=True)
    ignore = os.path.join(folder, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n!.gitignore\n")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = "%s-%s" % (stamp, re.sub(r"[^a-z-]", "", record.get("sub", "run")))
    name, n = base, 1
    while os.path.exists(os.path.join(folder, name + ".json")):
        n += 1
        name = "%s-%d" % (base, n)
    if hasattr(rt, "redact"):
        record["output"], _ = rt.redact(record.get("output", ""))
    record["output"] = record.get("output", "")[-MAX_LOG_BYTES:]
    with open(os.path.join(folder, name + ".json"), "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
    kept = sorted(f for f in os.listdir(folder) if f.endswith(".json"))
    for old in kept[:-MAX_RUNS]:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    return name


def run_records(project):
    """The saved runs, oldest first, without their output (the page asks for a log)."""
    out = []
    folder = runs_folder(project)
    if not os.path.isdir(folder):
        return out
    for name in sorted(f for f in os.listdir(folder) if f.endswith(".json"))[-MAX_RUNS:]:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as h:
                data = json.load(h)
        except (IOError, OSError, ValueError):
            continue
        out.append({"id": name[:-5], "sub": data.get("sub", ""), "args": data.get("args", []),
                    "exit_code": data.get("exit_code"), "seconds": data.get("seconds"),
                    "generated": data.get("generated", ""), "git_head": data.get("git_head", ""),
                    "doctor": data.get("doctor")})
    return out


def read_log(rt, project, kind, run_id, stage):
    """The text of one evidence stage log or one saved run, or None. Names are checked
    against a strict shape and the resolved path must stay inside its folder."""
    if not RUN_ID.match(run_id or ""):
        return None
    if kind == "evidence":
        stages = getattr(rt, "STAGES", ())
        if stage not in stages:
            return None
        root = project.path(os.path.join(".ai-sdlc", "evidence"))
        path = os.path.join(root, run_id, stage + ".log")
    elif kind == "run":
        root = runs_folder(project)
        path = os.path.join(root, run_id + ".json")
    else:
        return None
    real_root = os.path.realpath(root)
    real = os.path.realpath(path)
    if not real.startswith(real_root + os.sep) or not os.path.isfile(real):
        return None
    try:
        with open(real, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - MAX_LOG_BYTES))
            text = handle.read().decode("utf-8", "replace")
    except (IOError, OSError):
        return None
    if kind == "run":
        try:
            text = json.loads(text).get("output", "")
        except ValueError:
            return None
    elif size > MAX_LOG_BYTES:
        text = "[... first %d bytes cut ...]\n" % (size - MAX_LOG_BYTES) + text
    return text


# ---------------------------------------------------------------- DORA

DORA_WINDOW_DAYS = 90       # every DORA measure looks back this far
DORA_FAILURE_DAYS = 7       # a hotfix or defect opened this soon after a deploy marks it failed
DORA_MAX_COMMITS = 2000     # commits read per deploy range, so one huge range cannot stall a page
PRODUCTION_ENVS = ("production", "prod", "prd", "live")
DORA_SHA = re.compile(r"^[0-9a-f]{40,64}$")


def _when(value):
    """A UTC datetime from an ISO date or timestamp, or None. A bare date is midnight."""
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?", str(value or ""))
    if not m:
        return None
    try:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                 int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
    except ValueError:
        return None


def _days(value):
    text = "%.1f days" % value
    return "%.1f hours" % (value * 24) if value < 1 else text


def _n(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def _failure_item(it):
    """A hotfix (NUHT-028) or a defect item: the records that say a change went wrong."""
    try:
        import shards as shards_mod
        if shards_mod.is_hotfix(it):
            return True
    except Exception:
        if it.get("hotfix") is True:
            return True
    return str(it.get("type") or "").strip().lower() in ("defect", "bug", "incident", "hotfix")


def dora(rt, project, now=None, env=None):
    """The four DORA delivery measures, from the deploy ledger (sdlc.py deploy record),
    commit dates and hotfix/defect items. Each says "not enough data" rather than guess.
    Ledger lines are hand-editable, so a commit is passed to git only when it is a full SHA."""
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)
    since = now - datetime.timedelta(days=DORA_WINDOW_DAYS)
    out = {"env": None, "envs": [], "window_days": DORA_WINDOW_DAYS,
           "failure_days": DORA_FAILURE_DAYS, "measures": []}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import releases as releases_mod
        lines, _ = releases_mod.ledger_lines(project)
    except Exception:
        lines = []
    dated = []
    for line in lines:
        at = _when(line.get("date"))
        if at is not None and at <= now + datetime.timedelta(minutes=5):
            dated.append((at, line))
    envs = sorted(set(line["env"] for _, line in dated))
    out["envs"] = envs
    if env is None:
        env = next((e for e in PRODUCTION_ENVS if e in envs), None)
        if env is None and len(envs) == 1:
            env = envs[0]
    out["env"] = env
    window = "the last %d days" % DORA_WINDOW_DAYS

    def add(name, value, basis, data=None):
        out["measures"].append({"name": name, "kind": "lagging", "group": "dora", "value": value,
                                "basis": basis, "data": data or {}})

    if not envs:
        why = "not enough data: no deploys recorded (sdlc.py deploy record --version <v> --env <env>)"
    elif env is None:
        why = ("not enough data: no production environment in the ledger (envs: %s); "
               "run sdlc.py metrics --env <env>" % ", ".join(envs))
    else:
        why = None
    deploys = sorted([(at, line) for at, line in dated if line["env"] == env], key=lambda p: p[0])
    recent = [(at, line) for at, line in deploys if at >= since]
    if why is None and not recent:
        why = "not enough data: no deploys to %s in %s" % (env, window)

    # Deploy frequency
    if why:
        add("Deploy frequency", why, "deploys.jsonl lines for the production environment")
    else:
        per_week = round(len(recent) * 7.0 / DORA_WINDOW_DAYS, 2)
        add("Deploy frequency", "%s to %s in %s (%s per week)" % (
            _n(len(recent), "deploy"), env, window, per_week),
            "deploys.jsonl lines for %s; other environments are left out" % env,
            {"env": env, "deploys": len(recent), "per_week": per_week})

    # Lead time for changes: each commit's date to the first deploy whose range holds it.
    leads, seen, ranged = [], set(), 0
    for at, line in recent:
        frm, to = str(line.get("from") or ""), str(line.get("to") or "")
        if not (DORA_SHA.match(frm) and DORA_SHA.match(to)):
            continue
        ranged += 1
        log = project.git("log", "--format=%H %ct", "-n", str(DORA_MAX_COMMITS), "%s..%s" % (frm, to))
        for row in log.splitlines():
            sha, _, stamp = row.partition(" ")
            if sha in seen or not stamp.strip().isdigit():
                continue
            seen.add(sha)
            committed = datetime.datetime.fromtimestamp(int(stamp), datetime.timezone.utc).replace(tzinfo=None)
            if committed <= at:
                leads.append((at - committed).total_seconds() / 86400.0)
    lead = _median(leads)
    basis = ("each commit's date to the %s deploy that shipped it; a deploy with no starting "
             "commit (the first one) is left out" % (env or "production"))
    if why:
        add("Lead time for changes", why, basis)
    elif lead is None:
        add("Lead time for changes", "not enough data: no deploy to %s in %s names a commit range"
            % (env, window), basis)
    else:
        add("Lead time for changes", "median %s over %s in %s" % (
            _days(lead), _n(len(leads), "commit"), _n(ranged, "deploy")), basis,
            {"env": env, "commits": len(leads), "deploys": ranged, "median_days": round(lead, 2)})

    # Change failure rate: a failure item is laid at the newest deploy before it opened.
    try:
        import shards as shards_mod
        items = shards_mod.merged_items(project)
    except Exception:
        items = {}
    failures = []
    for iid, it in items.items():
        if not _failure_item(it) or it.get("status") == "Dropped":
            continue
        opened = _when(it.get("hotfix_at")) or _when(it.get("created"))
        if opened is not None:
            failures.append((iid, it, opened))
    failed, culprits = {}, []
    for iid, _, opened in sorted(failures, key=lambda f: f[2]):
        before = [p for p in deploys if p[0] <= opened]
        if not before:
            continue
        at, line = before[-1]
        if at < since or (opened - at).days >= DORA_FAILURE_DAYS:
            continue
        failed.setdefault(id(line), []).append(iid)
        culprits.append(iid)
    basis = ("deploys to %s followed within %d days by a hotfix or defect item (laid at the "
             "newest deploy before it opened)" % (env or "production", DORA_FAILURE_DAYS))
    if why:
        add("Change failure rate", why, basis)
    else:
        rate = 100 * len(failed) // len(recent)
        add("Change failure rate", "%d of %d deploys (%d%%)%s" % (
            len(failed), len(recent), rate, (": " + ", ".join(sorted(culprits)[:8])) if culprits else ""),
            basis, {"env": env, "deploys": len(recent), "failed": len(failed), "rate": rate,
                    "items": sorted(culprits)})

    # Time to restore: a hotfix or defect item from open to Done.
    restores, restored = [], []
    for iid, it, opened in failures:
        done = _when(it.get("completed"))
        if it.get("status") != "Done" or done is None or done < since or done.date() < opened.date():
            continue
        restores.append(float((done.date() - opened.date()).days))
        restored.append(iid)
    ttr = _median(restores)
    basis = "hotfix and defect items, hotfix time (else created date) to their Completed date"
    if ttr is None:
        add("Time to restore", "not enough data: no hotfix or defect item done in %s" % window, basis)
    else:
        add("Time to restore", "median %.1f days over %s" % (ttr, _n(len(restores), "item")), basis,
            {"items": sorted(restored), "median_days": round(ttr, 2)})
    return out


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

    runs = model.get("evidence")
    if runs is None:
        runs = model["evidence"] = evidence_runs(project)
    ran = [r for r in runs if any(e["result"].startswith("Verified") for e in r["stages"])]
    passed = [r for r in ran if not any(e["result"].startswith("Verified: fail")
                                        for e in r["stages"])]
    add("Verify pass rate", "leading",
        "%d of %d runs (%d%%)" % (len(passed), len(ran), 100 * len(passed) // len(ran))
        if ran else "no runs recorded", "sdlc.py verify evidence under .ai-sdlc/evidence/")

    try:
        usage = rt.budget_usage(project)
    except Exception:
        usage = []
    if usage:
        over = [u for u in usage if (u["budget"].get("tokens") and u["tokens"] > u["budget"]["tokens"])
                or (u["budget"].get("minutes") and u["minutes"] > u["budget"]["minutes"])]
        add("Agent budget", "leading",
            "%d of %d items with usage recorded are over their tier's budget%s"
            % (len(over), len(usage), (": " + ", ".join(u["item"] for u in over)) if over else ""),
            "Tokens and Minutes commit trailers against the charter's Agent budget per tier")
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
    skips = [it["id"] for it in done if it["id"] not in gaps
             and any(v == "skipped" for v in it.get("steps", {}).values())]
    unproven = [it["id"] for it in done if it.get("steps", {}).get("Verify") == "unproven"]
    add("Done with a lifecycle gap", "lagging", "%d of %d" % (len(gaps), len(done)) +
        (": " + ", ".join(gaps[:8]) + (" …" if len(gaps) > 8 else "") if gaps else "") +
        ("; %d more skipped a check on record" % len(skips) if skips else ""),
        "Done items missing a plan, review, commit, verification or worklog entry their tier "
        "requires; a check the worklog says was Not run, with its reason, is a skip, not a gap")
    if unproven:
        add("Verified by word only", "lagging", "%d of %d Done items" % (len(unproven), len(done)),
            "worklog reports check results with no sdlc.py verify run on the item's commits")
    waived = [it["id"] for it in done if it.get("waived")]
    if waived:
        add("Verify waived", "lagging", "%d of %d Done items: %s" % (len(waived), len(done),
                                                                     ", ".join(waived[:8])),
            "finish --waive verify: the checks did not run, a named person said why")

    plan_dates = {}
    plans_dir = os.path.join(project.docs, "project", "plans")
    if os.path.isdir(project.path(plans_dir)):
        cur_date = None
        for line in project.git("log", "--date=short", "--format=%x01%ad",
                                "--name-only", "--", plans_dir).splitlines():
            if line.startswith("\x01"):
                cur_date = _date(line[1:].strip())
            elif cur_date and line.strip():
                plan_dates.setdefault(line.strip().replace(os.sep, "/"), []).append(cur_date)
    revised = 0
    for it in items:
        plan = next((model["docs"][n] for n in it.get("records", [])
                     if model["docs"][n]["kind"] == "plans"), None)
        start = first_commit(it)
        if not plan or not start:
            continue
        dates = plan_dates.get(plan["path"])
        if dates is None:
            log = project.git("log", "--date=short", "--format=%ad", "--", plan["path"])
            dates = [_date(d) for d in log.split() if _date(d)]
        if any(d > start for d in dates):
            revised += 1
    add("Plans updated after build started", "lagging", str(revised),
        "plan files changed after the item's first commit: deviations that were recorded")
    try:
        model["dora"] = dora(rt, project)
    except Exception as exc:  # a broken ledger never stops the page or the report
        model["dora"] = {"env": None, "envs": [], "measures": [], "error": str(exc)}
    out.extend(model["dora"]["measures"])
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
    env = getattr(opts, "env", None)
    if env:
        if not re.match(r"^[a-z0-9][a-z0-9_-]{0,31}$", env):
            sys.stderr.write("metrics: invalid --env %r: lower-case letters, digits, _ and -\n" % (env,))
            return 2
        model["dora"] = dora(rt, project, env=env)
        model["metrics"] = [m for m in model["metrics"] if m.get("group") != "dora"] + model["dora"]["measures"]
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
    paths = [
        project.path("AGENTS.md"),
        project.path("CLAUDE.md"),
        project.path("GEMINI.md"),
        project.path(os.path.join(project.docs, "CARD.md")),
        project.path(".ai-sdlc/profile.json"),
        project.path(".ai-sdlc/manifest.json"),
        project.path(".ai-sdlc/test-lock.txt"),
        project.path(".ai-sdlc/protected.txt"),
        project.path(".ai-sdlc/gates.txt"),
        project.path(".ai-sdlc/bite/active.json"),
    ]
    for base, _, files in os.walk(project.path(os.path.join(project.docs, "project"))):
        paths.extend(os.path.join(base, n) for n in files if n.endswith((".md", ".json", ".jsonl")))
    evidence = project.path(os.path.join(".ai-sdlc", "evidence"))
    if os.path.isdir(evidence):
        paths.extend(os.path.join(evidence, n, "summary.json") for n in os.listdir(evidence))
    try:
        import claims as claims_mod
        reg = claims_mod.registry(project)
        if reg and os.path.isdir(reg):
            paths.extend(os.path.join(reg, n) for n in os.listdir(reg))
    except Exception:
        pass
    runs = runs_folder(project)
    if os.path.isdir(runs):
        paths.extend(os.path.join(runs, n) for n in os.listdir(runs) if n.endswith(".json"))
    disp = project.path(os.path.join(".ai-sdlc", "dispatch"))
    if os.path.isdir(disp):
        paths.extend(os.path.join(disp, n) for n in os.listdir(disp) if n.endswith(".json"))
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

    def __init__(self, rt, project, template, interval, actions=True):
        self.rt, self.project, self.template, self.interval = rt, project, template, interval
        self.actions = actions
        self.lock = threading.RLock()
        self.refreshing = False
        self.token = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
        self.checked = 0.0
        self.version = None
        self.model = None
        self.model_json = b""
        self.page = b""
        self.lens_full = None
        self.lens_print = None
        self.include_user = True
        self.github = False
        self.github_cache = (0.0, None)
        self.refresh(force=True)

    def lens(self):
        """The full lens, rebuilt only when a file it reads (or HEAD) has changed."""
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import lens as lens_mod
            digest = hashlib.sha256()
            for path in lens_mod.watched(self.project):
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                digest.update(("%s %d %d\n" % (path, st.st_mtime_ns, st.st_size)).encode("utf-8"))
            digest.update(self.project.git("rev-parse", "HEAD").encode("utf-8"))
            print_ = digest.hexdigest()
        except Exception:
            print_ = None
        with self.lock:
            if self.lens_full is not None and print_ and print_ == self.lens_print:
                return self.lens_full
            model = self.model or {}
        full = lens_report(self.rt, self.project, model, include_user=self.include_user)
        with self.lock:
            self.lens_full, self.lens_print = full, print_
        return full

    def github_work(self):
        """Open issues and pull requests through the gh CLI, cached for five minutes. Only
        when the server was started with --github; a failure is reported, never raised."""
        if not self.github:
            return None
        at, cached = self.github_cache
        if cached is not None and time.time() - at < 300:
            return cached
        out = {"issues": [], "pulls": [], "error": ""}
        for key, args in (("issues", ["issue", "list"]), ("pulls", ["pr", "list"])):
            try:
                proc = subprocess.run(["gh"] + args + ["--state", "open", "--limit", "50", "--json",
                                      "number,title,labels,updatedAt,url,author"],
                                      cwd=self.project.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
                if proc.returncode:
                    out["error"] = proc.stderr.decode("utf-8", "replace").strip()[:200]
                    continue
                out[key] = [{"number": x.get("number"), "title": x.get("title", ""), "url": x.get("url", ""),
                             "updated": x.get("updatedAt", ""), "labels": [l.get("name", "") for l in x.get("labels", [])],
                             "author": (x.get("author") or {}).get("login", "")}
                            for x in json.loads(proc.stdout.decode("utf-8", "replace") or "[]")]
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                out["error"] = str(exc)[:200]
        self.github_cache = (time.time(), out)
        return out

    def update_kit(self, kit_data, alerts=None):
        """Fast in-memory update for /api/config and /api/fix without full git rebuild."""
        with self.lock:
            if not self.model:
                self.refresh(force=True)
                return self.version
            self.model["kit"] = kit_data
            if alerts is not None:
                self.model["alerts"] = alerts
            version = fingerprint(self.project)
            self.model["version"] = version
            self.version = version
            self.model_json = json.dumps(self.model, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")
            self.page = render(self.model, self.template).encode("utf-8")
            self.checked = time.time()
            return self.version

    def refresh(self, force=False):
        with self.lock:
            now = time.time()
            if not force:
                if self.refreshing or now - self.checked < self.interval:
                    return self.version
                self.checked = now
                self.refreshing = True
        try:
            version = fingerprint(self.project)
            if version == self.version and not force:
                return self.version
            try:
                fresh_project = self.rt.Project(self.project.root)
                model = build(self.rt, fresh_project)
            except Exception as exc:  # a record caught half-written; keep the last good one
                sys.stderr.write("view: rebuild failed, keeping the last model: %s\n" % exc)
                return self.version
            model["version"] = version
            if self.lens_full is not None:
                model["lens"] = lens_summary(self.lens_full)
            model["live_interval"] = self.interval
            model["live_actions"] = self.actions
            new_json = json.dumps(model, ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8")
            new_page = render(model, self.template).encode("utf-8")
            with self.lock:
                self.project = fresh_project
                self.model = model
                self.version = version
                self.model_json = new_json
                self.page = new_page
                self.checked = time.time()
            if not force:
                sys.stderr.write("view: records changed, model rebuilt (%s)\n"
                                 % time.strftime("%H:%M:%S"))
            return self.version
        finally:
            if not force:
                with self.lock:
                    self.refreshing = False


def _parse_host(raw_host):
    raw = (raw_host or "").strip().lower()
    if raw.startswith("["):
        return raw.split("]", 1)[0].lstrip("[")
    return raw.split(":", 1)[0]


def _session_cookie(raw_cookie, name="nuhut_session"):
    for part in (raw_cookie or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() == name:
                return v.strip()
    return ""


def _valid_origin(raw_origin, port, own_host=None):
    """The Origin of a POST must be this server. Local mode knows its own addresses; remote
    mode (own_host given) has no fixed name behind a proxy, so it compares the Origin with
    the request's own Host header."""
    origin = (raw_origin or "").strip().lower().rstrip("/")
    if not origin:
        return False
    if own_host is not None:
        host = own_host.strip().lower()
        return bool(host) and origin in ("http://" + host, "https://" + host)
    allowed = (
        "http://127.0.0.1:%d" % port,
        "http://localhost:%d" % port,
        "http://[::1]:%d" % port,
    )
    return origin in allowed


def _query(path):
    query = {}
    for pair in (path.split("?", 1) + [""])[1].split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            query[k] = v
    return query


TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


def _tailscale_ip():
    """This machine's Tailscale IPv4 address from `tailscale ip -4`."""
    candidates = ["tailscale"]
    if sys.platform == "darwin":  # the Mac app ships its CLI inside the bundle
        candidates.append("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
    missing = True
    for exe in candidates:
        try:
            proc = subprocess.run([exe, "ip", "-4"], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        missing = False
        for line in proc.stdout.decode("utf-8", "replace").split():
            try:
                return str(ipaddress.IPv4Address(line.strip()))
            except ValueError:
                continue
    if missing:
        raise SystemExit("view: --host tailscale needs the tailscale command; install "
                         "Tailscale, or pass the address with --host <ip>")
    raise SystemExit("view: tailscale reports no IPv4 address for this machine; run "
                     "`tailscale up`, or pass the address with --host <ip>")


def bind_address(spec):
    """--host as (address, is loopback). Raises SystemExit on a value that is not one."""
    spec = (spec or "127.0.0.1").strip()
    if spec.lower() == "localhost":
        spec = "127.0.0.1"
    if spec.lower() == "tailscale":
        spec = _tailscale_ip()
    try:
        addr = ipaddress.ip_address(spec.strip("[]"))
    except ValueError:
        raise SystemExit("view: --host takes 127.0.0.1, tailscale, 0.0.0.0 or an IP address "
                         "of this machine, not %r" % spec)
    return str(addr), addr.is_loopback


def _reachable_names():
    """What another machine might use to reach a server bound to every interface: the host
    name and the address of the default route, found without sending a packet."""
    names = []
    try:
        names.append(socket.gethostname())
    except OSError:
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # TEST-NET-1: a UDP connect only picks a route
        names.append(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    return [n for i, n in enumerate(names) if n and n not in names[:i]]


def _url_host(addr):
    return "[%s]" % addr if ":" in addr else addr


def _kill_proc_tree(proc):
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


def serve(rt, project, template, opts):
    try:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    except ImportError:  # Python < 3.7
        raise SystemExit("--serve needs Python 3.7 or newer")
    interval = max(1, int(getattr(opts, "interval", 2) or 2))
    addr, loopback = bind_address(getattr(opts, "host", None))
    # Remote mode: any bind another machine can reach. NUHUT_VIEW_REMOTE_TEST turns it on
    # for a loopback bind too, so the smoke tests can drive it on any OS; it only adds checks.
    remote = not loopback or os.environ.get("NUHUT_VIEW_REMOTE_TEST") == "1"
    allow_actions = bool(getattr(opts, "allow_actions", False))
    # The key is printed once and kept in memory only: never in a file, a log or the page.
    access_key = secrets.token_urlsafe(32) if remote else ""
    live = Live(rt, project, template, interval, actions=allow_actions or not remote)
    live.github = bool(getattr(opts, "github", False))
    live.include_user = not getattr(opts, "no_user", False)

    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        server_version = "nuhut-view"

        def _send(self, code, body, ctype, extra_headers=()):
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                for hk, hv in extra_headers:
                    self.send_header(hk, hv)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _gate(self):
            """None when the request may go on, else the reason it may not. Local mode
            refuses any Host but this machine, so a web page cannot reach it through DNS
            rebinding. Remote mode takes any Host (a proxy, a tailnet name) and asks for the
            access key instead: ?k= in the address or the cookie a valid ?k= sets."""
            if not remote:
                host = _parse_host(self.headers.get("Host"))
                return None if host in ("127.0.0.1", "localhost", "::1") else "forbidden"
            given = _query(self.path).get("k", "") or _session_cookie(
                self.headers.get("Cookie"), "nuhut_key")
            if given and hmac.compare_digest(given.encode("utf-8", "replace"),
                                             access_key.encode("ascii")):
                return None
            return "the access key is missing or wrong; open the link view --serve printed"

        def do_GET(self):
            refused = self._gate()
            if refused:
                return self._send(403, (refused + "\n").encode("utf-8"), "text/plain; charset=utf-8")
            path = self.path.split("?", 1)[0]
            if remote and path in ("/", "/index.html") and "k" in _query(self.path):
                # Trade the key in the address for a cookie, and take it out of the address bar.
                cookie = "nuhut_key=%s; HttpOnly; SameSite=Strict; Path=/" % access_key
                return self._send(303, b"", "text/plain; charset=utf-8",
                                  extra_headers=(("Set-Cookie", cookie), ("Location", "./")))
            if path in ("/", "/index.html"):
                live.refresh()
                cookie = "nuhut_session=%s; HttpOnly; SameSite=Strict; Path=/" % live.token
                return self._send(200, live.page, "text/html; charset=utf-8",
                                  extra_headers=(("Set-Cookie", cookie),))
            if path == "/version":
                return self._send(200, (live.refresh() or "").encode("utf-8"),
                                  "text/plain; charset=utf-8")
            if path == "/model.json":
                live.refresh()
                return self._send(200, live.model_json, "application/json; charset=utf-8")
            if path == "/api/lens":
                data = dict(live.lens())
                gh = live.github_work()
                if gh is not None:
                    data["github"] = gh
                body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8")
            if path == "/api/log":
                query = _query(self.path)
                text = read_log(rt, live.project, query.get("kind", ""), query.get("id", ""),
                                query.get("stage", ""))
                if text is None:
                    return self._send(404, b"not found\n", "text/plain; charset=utf-8")
                return self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
            return self._send(404, b"not found\n", "text/plain; charset=utf-8")

        do_HEAD = do_GET

        def do_POST(self):
            refused = self._gate()
            if refused:
                body = json.dumps({"ok": False, "error": refused}).encode("utf-8")
                return self._send(403, body, "application/json; charset=utf-8")
            if not live.actions:
                return self._send(
                    403,
                    b'{"ok":false,"error":"this server is read-only; start it with view --serve --allow-actions to run commands or change settings from the page"}\n',
                    "application/json; charset=utf-8",
                )
            port = self.server.server_address[1]
            own_host = (self.headers.get("Host") or "") if remote else None
            if not _valid_origin(self.headers.get("Origin"), port, own_host):
                return self._send(403, b'{"ok":false,"error":"invalid or missing Origin"}\n',
                                  "application/json; charset=utf-8")
            cookie_tok = _session_cookie(self.headers.get("Cookie"))
            if not cookie_tok or not hmac.compare_digest(cookie_tok, live.token):
                return self._send(403, b'{"ok":false,"error":"invalid or missing session cookie"}\n',
                                  "application/json; charset=utf-8")
            path = self.path.split("?", 1)[0]
            if path not in ("/api/config", "/api/fix", "/api/run"):
                return self._send(404, b"not found\n", "text/plain; charset=utf-8")
            try:
                length = min(65536, max(0, int(self.headers.get("Content-Length") or "0")))
                raw = self.rfile.read(length).decode("utf-8", "replace") if length else "{}"
                payload = json.loads(raw or "{}")
            except ValueError:
                return self._send(400, b'{"ok":false,"error":"invalid json"}\n',
                                  "application/json; charset=utf-8")
            if not isinstance(payload, dict):
                return self._send(400, b'{"ok":false,"error":"json payload must be an object"}\n',
                                  "application/json; charset=utf-8")
            if path == "/api/config":
                if "checks" in payload and payload["checks"] is not None:
                    return self._send(
                        403,
                        b'{"ok":false,"error":"checks commands cannot be modified over HTTP; run sdlc.py config --set-check in a terminal"}\n',
                        "application/json; charset=utf-8",
                    )
                with live.lock:
                    res, err = rt.configure_kit(live.project, payload)
                    if err:
                        body = json.dumps({"ok": False, "error": err}).encode("utf-8")
                        return self._send(400, body, "application/json; charset=utf-8")
                    live.update_kit(res["kit"])
                    body = json.dumps({
                        "ok": True,
                        "applied": res["applied"],
                        "kit": res["kit"],
                        "version": live.version,
                    }).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8")
            if path == "/api/fix":
                action = payload.get("action") or "all"
                with live.lock:
                    res = rt.fix_kit(live.project, action, payload)
                    live.update_kit(res["kit"], res.get("findings"))
                    body = json.dumps({
                        "ok": True,
                        "repaired": res["repaired"],
                        "kit": res["kit"],
                        "alerts": res.get("findings"),
                        "version": live.version,
                    }).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8")
            if path == "/api/run":
                sub = str(payload.get("subcommand") or "").strip()
                allowed = ("verify", "plan-check", "doctor", "log", "trailers", "metrics", "audit")
                if sub not in allowed:
                    body = json.dumps({"ok": False, "error": "unsupported command: %s" % sub}).encode("utf-8")
                    return self._send(400, body, "application/json; charset=utf-8")
                allowed_flags = {
                    "verify": ("--parallel", "--stage"),
                    "plan-check": ("--strict", "--base"),
                    "doctor": ("--strict", "--all"),
                    "log": ("--since", "--id", "--write"),
                    "trailers": ("--agent", "--model"),
                    "metrics": (),
                    "audit": ("--strict",),
                }
                safe_re = re.compile(r"^[A-Za-z0-9_./:-]+$")
                cmd_args = [sub]
                raw_args = payload.get("args")
                if isinstance(raw_args, list) and raw_args:
                    sub_flags = allowed_flags.get(sub, ())
                    for a in raw_args[:12]:
                        sa = str(a).strip()
                        if not sa or not safe_re.match(sa):
                            return self._send(400, b'{"ok":false,"error":"invalid argument"}\n',
                                              "application/json; charset=utf-8")
                        if sa.startswith("-") and sa not in sub_flags:
                            return self._send(400, b'{"ok":false,"error":"invalid flag"}\n',
                                              "application/json; charset=utf-8")
                        cmd_args.append(sa)
                elif sub == "verify":
                    if payload.get("parallel", True):
                        cmd_args.append("--parallel")
                    st = str(payload.get("stage") or "").strip()
                    if st and safe_re.match(st):
                        cmd_args.extend(["--stage", st])
                elif sub == "plan-check":
                    iid = str(payload.get("item_id") or "").strip()
                    if not iid or not safe_re.match(iid):
                        return self._send(400, b'{"ok":false,"error":"missing or invalid item_id"}\n',
                                          "application/json; charset=utf-8")
                    cmd_args.append(iid)
                    if payload.get("strict"):
                        cmd_args.append("--strict")
                elif sub == "doctor":
                    if payload.get("strict"):
                        cmd_args.append("--strict")
                elif sub == "log":
                    since = str(payload.get("since") or "").strip()
                    if not since and not payload.get("item_id"):
                        since = "main"
                    if since and safe_re.match(since):
                        cmd_args.extend(["--since", since])
                    iid = str(payload.get("item_id") or "").strip()
                    if iid and safe_re.match(iid):
                        cmd_args.extend(["--id", iid])
                    if payload.get("write", True):
                        cmd_args.append("--write")
                elif sub == "trailers":
                    iid = str(payload.get("item_id") or "").strip()
                    if not iid or not safe_re.match(iid):
                        return self._send(400, b'{"ok":false,"error":"missing or invalid item_id"}\n',
                                          "application/json; charset=utf-8")
                    cmd_args.append(iid)
                    ag = str(payload.get("agent") or "").strip()
                    if ag and safe_re.match(ag):
                        cmd_args.extend(["--agent", ag])
                sdlc_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdlc.py")
                t0 = time.time()
                proc = None
                try:
                    popen_kw = dict(
                        cwd=live.project.root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    )
                    if os.name == "posix":
                        popen_kw["start_new_session"] = True
                    proc = subprocess.Popen(
                        [sys.executable, sdlc_bin] + cmd_args,
                        **popen_kw
                    )
                    out_bytes, _ = proc.communicate(timeout=120)
                    exit_code = proc.returncode
                    output_text = out_bytes.decode("utf-8", "replace")
                except subprocess.TimeoutExpired:
                    if proc is not None:
                        _kill_proc_tree(proc)
                    exit_code = 124
                    output_text = "Command timed out after 120s.\n"
                except Exception as exc:
                    exit_code = 1
                    output_text = "Failed to execute command: %s\n" % exc
                elapsed = round(time.time() - t0, 2)
                record = {"sub": sub, "args": cmd_args[1:], "exit_code": exit_code,
                          "seconds": elapsed, "output": output_text,
                          "generated": datetime.datetime.now(datetime.timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "git_head": live.project.git("rev-parse", "HEAD").strip()}
                if sub == "doctor":
                    try:
                        found = [f for f in rt.doctor(live.project) if not f.get("accepted")]
                        record["doctor"] = dict((lvl, sum(1 for f in found
                                                          if f.get("level") == lvl))
                                                for lvl in ("fail", "warn", "ok"))
                    except Exception:
                        pass
                try:
                    run_id = save_run(rt, live.project, record)
                except (IOError, OSError) as exc:
                    run_id = ""
                    sys.stderr.write("view: could not keep the run: %s\n" % exc)
                live.refresh(force=True)
                with live.lock:
                    body = json.dumps({
                        "ok": True,
                        "exit_code": exit_code,
                        "command": "python3 .ai-sdlc/bin/sdlc.py " + " ".join(cmd_args),
                        "output": output_text,
                        "seconds": elapsed,
                        "run_id": run_id,
                        "model": live.model,
                        "version": live.version,
                    }, ensure_ascii=False).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8")

        def log_message(self, *args):  # the terminal shows rebuilds, not every poll
            pass

    if ":" in addr:
        LocalServer.address_family = socket.AF_INET6
    port = int(getattr(opts, "port", 8765))
    server = None
    for candidate in ([port] if port == 0 else range(port, port + 10)):
        try:
            server = LocalServer((addr, candidate), Handler)
            break
        except OSError as exc:
            if exc.errno == errno.EADDRNOTAVAIL:
                raise SystemExit("view: cannot listen on %s: it is not an address of this "
                                 "machine" % addr)
            continue
    if server is None:
        raise SystemExit("view: ports %d-%d are all in use; pass --port" % (port, port + 9))
    bound = server.server_address[1]
    if not remote:
        url = "http://127.0.0.1:%d/" % bound
        print("view: live at %s (local only). The page follows the records as they change; "
              "Ctrl+C stops it." % url)
    else:
        ip = ipaddress.ip_address(addr)
        hosts = _reachable_names() if ip.is_unspecified else [_url_host(addr)]
        urls = ["http://%s:%d/?k=%s" % (h, bound, access_key) for h in hosts]
        mode = ("actions allowed: the page can run kit commands" if allow_actions else
                "read-only; start with --allow-actions to run commands from the page")
        print("view: live at %s (remote, %s). Anyone with this link can read the records; "
              "Ctrl+C stops it." % (urls[0] if urls else "port %d" % bound, mode))
        for other in urls[1:]:
            print("      also %s" % other)
        if not loopback and (ip.is_unspecified or not any(ip in net for net in TAILNET
                                                          if net.version == ip.version)):
            sys.stderr.write("view: warning: traffic is plain HTTP; anyone on the network path "
                             "can read the page and the key. Prefer --host tailscale.\n")
        url = "http://%s:%d/?k=%s" % ("127.0.0.1" if ip.is_unspecified else _url_host(addr),
                                      bound, access_key)
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
        "postmortems": "Postmortems", "adr": "ADRs", "epics": "Epics",
        "archive": "Worklog archive"
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

        count_span = ('<tspan class="node-count" dx="6" font-size="11px" fill="var(--muted, #57606a)">(%d)</tspan>'
                      % len(kids)) if (kids and not is_open) else ""
        lines.append('      <g class="map-node" data-key="%s">' % esc(n.get("key", "")))
        lines.append('        <circle class="node-dot" cx="%d" cy="%d" r="%d" fill="%s" stroke="%s" stroke-width="2">'
                     % (n["x"], n["y"], r, fill_val, stroke_val))
        lines.append('          <title>%s</title>' % full_text)
        lines.append('        </circle>')
        lines.append('        <text class="%s" x="%d" y="%d" font-family="system-ui, sans-serif" font-size="13px" fill="var(--text, #1f2328)">'
                     '%s%s<title>%s</title></text>' % (label_cls, n["x"] + 10, n["y"] + 4, label_text, count_span, full_text))
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


def lens_report(rt, project, model, include_user):
    """The Project lens (lens.py), or a note saying why it could not be built; never a
    reason for the page not to open."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import lens
        return lens.lens(rt, project, model, include_user=include_user)
    except Exception as exc:
        return {"error": "the project lens could not be built: %s" % exc}


def lens_summary(full):
    if "error" in full:
        return full
    import lens
    return lens.lens_summary(full)


def run(rt, project, opts):
    here = os.path.dirname(os.path.abspath(__file__))
    template = rt.read(os.path.join(here, "view.html"))
    if not template:
        raise SystemExit("view.html is missing next to view.py; re-run the installer "
                         "with --upgrade")
    if getattr(opts, "serve", False):
        return serve(rt, project, template, opts)
    model = build(rt, project)
    # A static page carries the lens's counts and worst findings only, never user-level items.
    model["lens"] = lens_summary(lens_report(rt, project, model, include_user=False))
    out_dir = project.path(os.path.join(".ai-sdlc", "view"))
    os.makedirs(out_dir, exist_ok=True)
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

    custom_html = getattr(opts, "export_html", None)
    if custom_html:
        target_html = project.path(custom_html) if not os.path.isabs(custom_html) else custom_html
        os.makedirs(os.path.dirname(target_html), exist_ok=True)
        with open(target_html, "w", encoding="utf-8") as handle:
            handle.write(render(model, template))
        print("wrote %s" % os.path.relpath(target_html, project.root))

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
    if not getattr(opts, "no_open", False) and not custom_html and not custom_svg:
        webbrowser.open("file://" + out)
    return 0

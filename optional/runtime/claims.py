"""Who is working on what, and what can safely run side by side.

A claim is a file in the repository's shared git directory (<git-common-dir>/nuhut/
claims/<ID>.json). Every worktree of a clone shares that directory, so agents working in
parallel on one machine see each other's claims, and the file is created atomically:
two agents cannot both take the same item. Across machines the claim's branch
(<ID>-<slug>, pushed) is what others see.

The backlog is not the source of truth for claims: every worktree has its own copy of
backlog.md, and two agents marking rows in two worktrees produce conflicting edits at
merge time -- the very collision claims exist to prevent. `claim --mark` edits the row
only from the main worktree.

`parallel` lists the Ready items nobody holds, grouped so that no two in a group touch
the same files (from each plan's "Files that change"); single-writer files -- the
charter, migrations, lockfiles -- always conflict.

Called by sdlc.py (claim, release, claims, parallel), doctor and view.py. Standard
library only. This file must never contain two opening braces in a row (see sdlc.py).
"""

import datetime
import json
import os
import re
import socket
import subprocess

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9]+\b")
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "poetry.lock",
             "uv.lock", "Pipfile.lock", "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock")


def _git(project, *args):
    try:
        return subprocess.run(["git"] + list(args), cwd=project.root, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True).stdout
    except OSError:
        return ""


def _git_ok(cwd, *args):
    p = subprocess.run(["git"] + list(args), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def common_dir(project):
    raw = _git(project, "rev-parse", "--git-common-dir").strip()
    if not raw:
        return ""
    return raw if os.path.isabs(raw) else os.path.normpath(os.path.join(project.root, raw))


def registry(project):
    base = common_dir(project)
    return os.path.join(base, "nuhut", "claims") if base else ""


def main_worktree(project):
    """The checkout that owns the shared git directory (where --mark may edit)."""
    base = common_dir(project)
    return os.path.dirname(base) if base.endswith(os.sep + ".git") or base.endswith("/.git") else ""


def is_main_worktree(project):
    main = main_worktree(project)
    return bool(main) and os.path.realpath(main) == os.path.realpath(project.root)


def items(project, view_mod):
    """{id: {title, status, column, depends, line, section}} from the backlog tables."""
    text = project.records("backlog.md")
    out = {}
    for section, line, row in view_mod.backlog_tables(text):
        rid = (row.get("ID") or "").strip()
        m = ID_RE.search(rid)
        if not m:
            continue
        status = view_mod.plain(row.get("Status", ""))
        out[m.group(0)] = {"title": view_mod.plain(row.get("Task", row.get("Title", ""))), "status": status,
                           "column": view_mod.column_of(status), "line": line, "section": section,
                           "depends": [d for d in ID_RE.findall(row.get("Depends on", "")) if d != m.group(0)]}
    return out


def list_claims(project):
    folder = registry(project)
    out = []
    if not folder or not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as h:
                data = json.load(h)
        except (IOError, OSError, ValueError):
            continue
        branch = data.get("branch", "")
        last = _git(project, "log", "-1", "--format=%cI", branch, "--").strip() if branch else ""
        data["last_commit"] = last
        data["worktree_exists"] = bool(data.get("worktree")) and os.path.isdir(data["worktree"])
        out.append(data)
    return out


def slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return "-".join(s.split("-")[:6])[:40].strip("-") or "work"


def claim(project, view_mod, item, agent, worktree=None, no_worktree=False, mark=False, base=None):
    """Returns (record, error)."""
    backlog = items(project, view_mod)
    it = backlog.get(item)
    if not it:
        return None, "%s is not in the backlog" % item
    if it["column"] in ("Done", "Dropped"):
        return None, "%s is %s" % (item, it["status"])
    open_deps = [d for d in it["depends"] if d in backlog and backlog[d]["column"] != "Done"]
    if open_deps:
        return None, "%s depends on unfinished %s" % (item, ", ".join(open_deps))
    folder = registry(project)
    if not folder:
        return None, "not a git repository"
    if not os.path.isdir(folder):
        os.makedirs(folder)
    if mark and not is_main_worktree(project):
        return None, "--mark edits backlog.md, which only the main worktree (%s) may do" % (main_worktree(project) or "?")
    branch = "%s-%s" % (item, slug(it["title"]))
    path = None if no_worktree else (worktree or os.path.join(os.path.dirname(main_worktree(project) or project.root),
                                                              "%s-%s" % (os.path.basename(main_worktree(project) or project.root), item)))
    record = {"id": item, "agent": agent, "branch": branch, "worktree": path or "",
              "since": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "host": socket.gethostname(), "title": it["title"]}
    target = os.path.join(folder, item + ".json")
    try:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        try:
            with open(target, encoding="utf-8") as h:
                held = json.load(h)
        except (IOError, OSError, ValueError):
            held = {}
        return None, "%s is already claimed by %s since %s (branch %s)" % (
            item, held.get("agent", "?"), held.get("since", "?"), held.get("branch", "?"))
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(record, h, indent=2)
    exists = bool(_git(project, "rev-parse", "--verify", "--quiet", branch).strip())
    if path:
        args = ["worktree", "add", path, branch] if exists else ["worktree", "add", "-b", branch, path] + ([base] if base else [])
        ok, msg = _git_ok(project.root, *args)
        if not ok:
            os.remove(target)
            return None, "git worktree add failed: %s" % msg
    elif not exists:
        ok, msg = _git_ok(project.root, "branch", branch, *([base] if base else []))
        if not ok:
            os.remove(target)
            return None, "git branch failed: %s" % msg
    if mark:
        mark_status(project, item, it, "In progress")
    return record, None


def mark_status(project, item, it, status):
    """Rewrite the Status cell of the item's backlog row, nothing else."""
    rel = os.path.join(project.docs, "project", "backlog.md")
    path = project.path(rel)
    with open(path, encoding="utf-8") as h:
        lines = h.read().split("\n")
    idx = it["line"] - 1 if it["line"] else -1
    if not (0 <= idx < len(lines)) or item not in lines[idx]:
        idx = next((n for n, l in enumerate(lines) if l.strip().startswith("|") and re.search(r"\|\s*%s\s*\|" % re.escape(item), l)), -1)
    if idx < 0:
        return False
    header = next((lines[n] for n in range(idx - 1, -1, -1) if re.search(r"\|\s*Status\s*\|", lines[n])), "")
    cols = [c.strip() for c in header.strip().strip("|").split("|")]
    if "Status" not in cols:
        return False
    cells = lines[idx].strip().strip("|").split("|")
    pos = cols.index("Status")
    if pos >= len(cells):
        return False
    width = len(cells[pos])
    cells[pos] = (" " + status).ljust(max(width, len(status) + 2))
    lines[idx] = "|" + "|".join(cells) + "|"
    with open(path, "w", encoding="utf-8") as h:
        h.write("\n".join(lines))
    return True


def release(project, item, remove_worktree=False):
    target = os.path.join(registry(project), item + ".json")
    if not os.path.exists(target):
        return None, "%s is not claimed" % item
    with open(target, encoding="utf-8") as h:
        record = json.load(h)
    wt = record.get("worktree") or ""
    if remove_worktree and wt and os.path.isdir(wt):
        ok, status = _git_ok(wt, "status", "--porcelain")
        if status:
            return None, "the worktree %s has uncommitted changes; commit or stash them first" % wt
        ok, msg = _git_ok(project.root, "worktree", "remove", wt)
        if not ok:
            return None, "git worktree remove failed: %s" % msg
    os.remove(target)
    return record, None


# ---------------------------------------------------------------- parallel

def plan_text(project, item, rt):
    folder = os.path.join(project.docs, "project", "plans")
    rel = os.path.join(folder, item + ".md")
    if not os.path.isfile(project.path(rel)) and os.path.isdir(project.path(folder)):
        named = sorted(n for n in os.listdir(project.path(folder)) if n.startswith(item + "-") and n.endswith(".md"))
        if named:
            rel = os.path.join(folder, named[0])
    return rt.read(project.path(rel))


def single_writer(path, project):
    """A shared resource the path belongs to, if it is one only one agent may change."""
    p = path.lower()
    if os.path.basename(p) in LOCKFILES:
        return "lockfile"
    if "migration" in p or "/migrate/" in p or p.startswith("migrate/"):
        return "migrations"
    if p.endswith("charter.md") and "project" in p:
        return "charter"
    return ""


def overlaps(a, b, rt):
    a_re, b_re = rt.glob_regex(a), rt.glob_regex(b)
    if a_re.match(b) or b_re.match(a):
        return True
    a_dir, b_dir = re.split(r"[*?\[]", a)[0], re.split(r"[*?\[]", b)[0]
    return bool(a_dir and b_dir and (a_dir.startswith(b_dir) or b_dir.startswith(a_dir)) and (a_dir != a or b_dir != b))


def parallel(project, rt, view_mod):
    backlog = items(project, view_mod)
    held = set(c["id"] for c in list_claims(project))
    candidates, no_plan = [], []
    for item, it in backlog.items():
        if it["column"] != "Next" or item in held:
            continue
        if any(d in backlog and backlog[d]["column"] != "Done" for d in it["depends"]):
            continue
        paths = rt.planned_paths(plan_text(project, item, rt) or "")
        if not paths:
            no_plan.append({"id": item, "title": it["title"]})
            continue
        candidates.append({"id": item, "title": it["title"], "files": paths,
                           "writers": sorted(set(w for w in (single_writer(p, project) for p in paths) if w))})
    conflicts = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            shared = [x for x in a["files"] if any(overlaps(x, y, rt) for y in b["files"])]
            writers = sorted(set(a["writers"]) & set(b["writers"]))
            if shared or writers:
                conflicts.append({"a": a["id"], "b": b["id"], "files": shared[:6], "single_writer": writers})
    clash = {}
    for c in conflicts:
        clash.setdefault(c["a"], set()).add(c["b"])
        clash.setdefault(c["b"], set()).add(c["a"])
    groups = []
    for cand in sorted(candidates, key=lambda c: (-len(clash.get(c["id"], ())), c["id"])):
        for g in groups:
            if not any(other in clash.get(cand["id"], ()) for other in g):
                g.append(cand["id"])
                break
        else:
            groups.append([cand["id"]])
    groups.sort(key=lambda g: -len(g))
    return {"groups": groups, "candidates": candidates, "conflicts": conflicts,
            "plan_first": sorted(no_plan, key=lambda x: x["id"]), "claimed": sorted(held)}


# ---------------------------------------------------------------- doctor

def check(project, out, view_mod, window_days, today=None):
    claims = list_claims(project)
    if not claims:
        return
    backlog = items(project, view_mod)
    today = today or datetime.date.today()
    for c in claims:
        where = "claim %s" % c["id"]
        it = backlog.get(c["id"])
        if it and it["column"] in ("Done", "Dropped"):
            out.add("warn", "claims", where, "%s is %s but still claimed by %s; release it: "
                    "python3 .ai-sdlc/bin/sdlc.py release %s" % (c["id"], it["status"], c.get("agent", "?"), c["id"]))
            continue
        try:
            since = datetime.datetime.strptime(c["since"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        last = c.get("last_commit", "")[:10]
        recent = last and last >= c["since"][:10]
        if (today - since).days > window_days and not recent:
            out.add("warn", "claims", where, "claimed by %s %d days ago with no commit on %s since; "
                    "re-claim it deliberately or release it" % (c.get("agent", "?"), (today - since).days, c.get("branch", "?")))
    branches = _git(project, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
    per_id = {}
    for b in branches:
        m = re.match(r"^(?:[\w.-]+/)?([A-Z][A-Z0-9]*-[0-9]+)(?:-|$)", b)
        if m:
            per_id.setdefault(m.group(1), []).append(b)
    for item, names in sorted(per_id.items()):
        if len(names) > 1 and any(c["id"] == item for c in claims):
            out.add("warn", "claims", "claim %s" % item, "%d branches for one item (%s); two agents may be on it"
                    % (len(names), ", ".join(names[:4])))

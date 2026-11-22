"""`sdlc.py status`: one screen of what to do next on this branch, for this person.

Read-only. It reports and names commands; it changes no record, claim or git state. The
order is the order of what blocks work: setup this clone is missing, then the items you
hold and the next step each one owes (the same rules `finish` applies, run as a dry run),
then items Parked on you, then Ready items you could take, then the doctor finding count.
"""
import json
import os
import re
import shutil
import subprocess

SDLC = "python3 .ai-sdlc/bin/sdlc.py"
BUILTIN_MERGE = ("text", "binary", "union")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
STEP_ORDER = ("sync", "verify", "review", "log")


def clean(text):
    """Record text printed to a terminal: no escape sequences from a crafted title."""
    return CONTROL.sub("", str(text or ""))


# ---------------------------------------------------------------- identity

def people_path(project):
    return project.path(os.path.join(project.docs, "project", "people.json"))


def load_people(project):
    """[(handle, {lowercased names})] from <docs>/project/people.json, or None when the
    file is absent. Accepts a {"people": [...]} list, a bare list, or a {handle: {...}}
    map; each person may give name, names, aliases, git, github and email."""
    path = people_path(project)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, OSError, ValueError):
        return []
    if isinstance(data, dict) and isinstance(data.get("people"), list):
        entries = data["people"]
    elif isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = [dict(v, handle=k) if isinstance(v, dict) else {"handle": k, "name": v}
                   for k, v in data.items()]
    else:
        entries = []
    out = []
    for entry in entries:
        if not isinstance(entry, dict) or not str(entry.get("handle") or "").strip():
            continue
        handle = str(entry["handle"]).strip()
        names = set([handle.lower()])
        for key in ("name", "names", "aliases", "git", "github", "email"):
            value = entry.get(key)
            for v in (value if isinstance(value, list) else [value]):
                if isinstance(v, str) and v.strip():
                    names.add(v.strip().lstrip("@").lower())
        out.append((handle, names))
    # The installed template lists nobody: that is no registry yet, not an empty one.
    return out or None


def whoami(project):
    """{name, source, handle, names, people}: NUHUT_USER, else git config user.name,
    resolved through people.json when it exists."""
    name = os.environ.get("NUHUT_USER", "").strip()
    source = "NUHUT_USER" if name else ""
    if not name:
        name = project.git("config", "user.name").strip()
        source = "git user.name" if name else ""
    people = load_people(project)
    handle, names = "", set([name.lower()]) if name else set()
    for h, known in people or []:
        if name and name.lstrip("@").lower() in known:
            handle, names = h, names | known
            break
    return {"name": name, "source": source, "handle": handle, "names": sorted(names),
            "people": people is not None}


def names_match(cell, names):
    """True when a Waiting on whom / Who can unblock cell names one of <names>."""
    if not names:
        return False
    for token in re.split(r"[,;/&+]|\band\b|\bor\b", (cell or "").lower()):
        token = token.strip().strip("`*_").lstrip("@").strip()
        if token and token in names:
            return True
    return False


# ---------------------------------------------------------------- setup

def gitattribute_drivers(project):
    """Custom merge driver names .gitattributes asks for (merge=<name>)."""
    try:
        with open(project.path(".gitattributes"), encoding="utf-8") as handle:
            text = handle.read()
    except (IOError, OSError):
        return []
    found = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        for name in re.findall(r"(?:^|\s)merge=([A-Za-z0-9_.-]+)", line):
            if name not in BUILTIN_MERGE and name not in found:
                found.append(name)
    return found


def gh_state():
    """'ok', 'missing' or 'unauthenticated'. Runs `gh auth status` only; never prints its
    output, which can name the account."""
    exe = shutil.which("gh")
    if not exe:
        return "missing"
    try:
        proc = subprocess.run([exe, "auth", "status"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=15, env=dict(os.environ, GH_PROMPT_DISABLED="1"))
    except (OSError, subprocess.SubprocessError):
        return "unauthenticated"
    return "ok" if proc.returncode == 0 else "unauthenticated"


def setup_gaps(project, me, open_tier1):
    """[{check, text, fix}] for what this clone is missing, in the order to fix them."""
    gaps = []
    for name in gitattribute_drivers(project):
        if not project.git("config", "--get", "merge.%s.driver" % name).strip():
            gaps.append({"check": "merge-driver",
                         "text": "merge driver %s is not configured in this clone "
                                 "(.gitattributes asks for it)" % name,
                         "fix": "%s fix merge-driver" % SDLC})
    rel = os.path.join(project.docs, "project", "people.json")
    if not me["name"]:
        gaps.append({"check": "identity",
                     "text": "no identity: neither NUHUT_USER nor git user.name is set",
                     "fix": "git config user.name \"<your name>\", or export NUHUT_USER=<handle>"})
    elif not me["people"] and me["source"] == "git user.name":
        # The rule claim applies (sdlc.person_identity): git user.name names a person
        # only through people.json, so with no one listed every claim records none.
        gaps.append({"check": "identity",
                     "text": "%s (git user.name) names no one: %s lists no people, so your "
                             "claims record no person" % (me["name"], rel),
                     "fix": "add yourself to %s, or export NUHUT_USER=<handle>" % rel})
    elif me["people"] and not me["handle"]:
        gaps.append({"check": "identity",
                     "text": "%s (%s) is not in %s" % (me["name"], me["source"], rel),
                     "fix": "export NUHUT_USER=<your handle in people.json>, or add "
                            "\"%s\" to your entry's names in %s" % (me["name"], rel)})
    if open_tier1:
        state = gh_state()
        if state != "ok":
            gaps.append({"check": "gh",
                         "text": "gh is %s; %d open Tier 1 item(s) need GitHub for approval"
                                 % ("not installed" if state == "missing" else "not logged in",
                                    open_tier1),
                         "fix": ("install the GitHub CLI (https://cli.github.com), then "
                                 if state == "missing" else "") + "gh auth login"})
    return gaps


# ---------------------------------------------------------------- items

def next_step(rt, project, item, tier, column, claims_mod, finish_mod):
    """(step, detail): the next thing <item> owes. plan, build, sync, verify, review,
    log, finish (nothing owed: run it), release (the item is finished but still claimed)
    or unknown."""
    if column in ("Done", "Dropped"):
        return "release", "%s is %s: %s release %s" % (item, column, SDLC, item)
    if tier == "1" and not rt.planned_paths(claims_mod.plan_text(project, item, rt) or ""):
        return "plan", "Tier 1 needs a plan with Files that change: /sdlc-plan %s" % item
    try:
        lines, code = finish_mod.finish(rt, project, item, dry_run=True)
    except Exception as exc:              # status reports; it never fails on one item
        return "unknown", "finish --dry-run could not run: %s" % exc
    if code == 2:
        return "unknown", lines[0] if lines else "%s is not in the backlog" % item
    if any(ln.startswith("build ") for ln in lines) and code == 1 and \
            not any(ln.startswith("OWED ") for ln in lines):
        return "build", "no commit carries a Work-Item: %s trailer yet: build it, commit with the trailer" % item
    owed = [ln[5:].strip() for ln in lines if ln.startswith("OWED ")]
    if owed:
        steps = [o.split(None, 1) for o in owed]
        steps.sort(key=lambda s: STEP_ORDER.index(s[0]) if s[0] in STEP_ORDER else 99)
        step = steps[0][0] if steps[0][0] in STEP_ORDER else "finish"
        return step, (steps[0][1] if len(steps[0]) > 1 else "").strip()
    return "finish", "nothing owed: %s finish %s" % (SDLC, item)


def report(rt, project):
    """The status model, also what --json prints."""
    claims_mod = rt.runtime_module("claims")
    view_mod = rt.runtime_module("view")
    finish_mod = rt.runtime_module("finish")
    shards_mod = rt.runtime_module("shards")
    branch = project.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    unborn = False
    if not branch:
        # No commits yet: rev-parse fails, but HEAD already names a branch.
        branch = project.git("symbolic-ref", "--quiet", "--short", "HEAD").strip()
        unborn = bool(branch)
    me = whoami(project)
    names = set(me["names"])
    agent = rt.identity(None, None)[0]
    backlog = claims_mod.items(project, view_mod)
    merged = shards_mod.merged_items(project)
    root = os.path.realpath(project.root)

    held = claims_mod.list_claims(project)
    mine, others = [], 0
    for c in held:
        wt = c.get("worktree") or ""
        if (branch and c.get("branch") == branch) or (wt and os.path.realpath(wt) == root) \
                or (c.get("agent") and (c["agent"].lower() in names
                                        or (agent != "unknown" and c["agent"] == agent))):
            mine.append(c)
        else:
            others += 1
    ids = [c["id"] for c in mine]
    for found in re.findall(r"[A-Z][A-Z0-9]*-\d+", branch or ""):
        if found in backlog and found not in ids and \
                backlog[found]["column"] not in ("Done", "Dropped"):
            ids.append(found)
            mine.append({"id": found, "branch": branch, "agent": "", "claimed": False})
    items = []
    for c in mine:
        it = backlog.get(c["id"]) or {}
        step, detail = next_step(rt, project, c["id"], it.get("tier", ""),
                                 it.get("column", ""), claims_mod, finish_mod)
        items.append({"id": c["id"], "title": it.get("title") or c.get("title", ""),
                      "tier": it.get("tier", ""), "status": it.get("status", ""),
                      "claimed": c.get("claimed", True), "branch": c.get("branch", ""),
                      "worktree": c.get("worktree", ""), "next": step, "detail": detail})

    parked = []
    for item_id in sorted(merged, key=lambda k: shards_mod._id_sort_key(k)):
        it = merged[item_id]
        column = view_mod.column_of(it.get("status", ""))
        cell = it.get("waiting_on") if column == "Parked" else \
            it.get("unblock_by") if column == "Blocked" else None
        if cell and names_match(cell, names):
            parked.append({"id": item_id, "title": it.get("title", ""), "status": column,
                           "for": it.get("park_reason", "") if column == "Parked" else "",
                           "waiting_on": cell})

    par = claims_mod.parallel(project, rt, view_mod)
    ready = [{"id": c["id"], "title": c["title"], "tier": c["tier"]}
             for c in sorted(par["candidates"], key=lambda c: shards_mod._id_sort_key(c["id"]))
             if c["id"] not in ids]
    plan_first = [dict(p) for p in par["plan_first"] if p["id"] not in ids]

    open_tier1 = sum(1 for it in backlog.values()
                     if it.get("tier") == "1" and it["column"] not in ("Done", "Dropped"))
    setup = setup_gaps(project, me, open_tier1)
    if unborn:
        setup.insert(0, {"check": "commits",
                         "text": "no commits yet on %s, so claim cannot make a worktree" % branch,
                         "fix": "commit the kit first: git add -A && git commit"})

    findings = rt.apply_baseline(project, rt.doctor(project))
    counts = {"fail": 0, "warn": 0, "info": 0}
    for f in findings:
        if not f.get("accepted") and f.get("level") in counts:
            counts[f["level"]] += 1
    return {"branch": branch,
            "user": {"name": me["name"], "source": me["source"], "handle": me["handle"]},
            "setup": setup, "items": items, "other_claims": others, "parked": parked,
            "ready": ready, "plan_first": plan_first, "doctor": counts}


def format_report(data, limit=8):
    out = ["status · branch %s · you: %s" % (
        clean(data["branch"]) or "(no git)",
        clean(data["user"]["handle"] or data["user"]["name"]) or "unknown")]
    if data["setup"]:
        out.append("")
        out.append("Setup missing")
        for g in data["setup"]:
            out.append("  %s" % clean(g["text"]))
            out.append("    fix: %s" % clean(g["fix"]))
    out.append("")
    out.append("Your items")
    if not data["items"]:
        out.append("  none on this branch or claimed by you. Take one: %s claim <ID>" % SDLC)
    for it in data["items"]:
        out.append("  %-10s %-12s T%-2s next: %-7s %s" % (
            clean(it["id"]), clean(it["status"]), clean(it["tier"]) or "?", it["next"],
            clean(it["title"])[:48]))
        if it["detail"]:
            out.append("  %10s %s" % ("", clean(it["detail"])))
    if data["other_claims"]:
        out.append("  %d other claim(s): %s claims" % (data["other_claims"], SDLC))
    if data["parked"]:
        out.append("")
        out.append("Waiting on you")
        for p in data["parked"]:
            out.append("  %-10s %-8s %s%s" % (clean(p["id"]), p["status"], clean(p["title"])[:48],
                                              " (%s)" % clean(p["for"]) if p["for"] else ""))
    out.append("")
    out.append("Ready to take")
    if not (data["ready"] or data["plan_first"]):
        out.append("  no unclaimed Ready item with finished dependencies")
    for r in data["ready"][:limit]:
        out.append("  %-10s T%-2s %s" % (clean(r["id"]), clean(r["tier"]), clean(r["title"])[:56]))
    if len(data["ready"]) > limit:
        out.append("  ... %d more: %s parallel" % (len(data["ready"]) - limit, SDLC))
    if data["plan_first"]:
        out.append("  plan first (no Files that change): %s" % ", ".join(
            clean(p["id"]) for p in data["plan_first"][:limit]))
    if data["ready"]:
        out.append("  take one: %s claim %s" % (SDLC, clean(data["ready"][0]["id"])))
    d = data["doctor"]
    out.append("")
    out.append("Doctor: %d fail, %d warn%s" % (
        d["fail"], d["warn"], " (%s doctor)" % SDLC if d["fail"] or d["warn"] else ""))
    return "\n".join(out)

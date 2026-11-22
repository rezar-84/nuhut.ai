"""Release records and the deploy ledger: what shipped, and which version runs where.

`sdlc.py deploy record --version X --env E` writes <docs>/project/releases/<X>.json (the
version, the commit range, the work items named in that range's Work-Item trailers, the
date, who deployed it and with which tool) and appends one line to
<docs>/project/deploys.jsonl. `sdlc.py deploy list` reads the ledger back: the newest
line per environment is the version running there.

A version is never rewritten: recording it again at the same commit is a promotion (one
more ledger line, one more env on the record); at a different commit it is refused.

The version becomes a file name and the refs reach git, so both are checked before any
path is built or any git command runs. Email addresses are never stored.

Called by sdlc.py (deploy record, deploy list) and view.py.
Standard library only. This file must never contain two opening braces in a row.
"""

import datetime
import json
import os
import re

import shards

SCHEMA = 1
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")
ENV_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
LEDGER = "deploys.jsonl"


class DeployError(Exception):
    """A refusal: the message says what was wrong; nothing was written."""


def validate_version(value):
    return bool(isinstance(value, str) and VERSION_RE.match(value) and ".." not in value)


def validate_env(value):
    return bool(isinstance(value, str) and ENV_RE.match(value))


def releases_dir(project):
    return project.path(os.path.join(project.docs, "project", "releases"))


def ledger_path(project):
    return project.path(os.path.join(project.docs, "project", LEDGER))


def record_path(project, version):
    """The record's path, or DeployError when the version could leave releases/."""
    if not validate_version(version):
        raise DeployError("invalid version %r: use letters, digits and . _ + - (up to 64, "
                          "starting with a letter or digit, no '..')" % (version,))
    base = os.path.realpath(releases_dir(project))
    path = os.path.realpath(os.path.join(base, version + ".json"))
    if os.path.dirname(path) != base:
        raise DeployError("invalid version %r: the record would leave releases/" % (version,))
    return path


def resolve_ref(project, ref):
    """The full commit SHA <ref> names. A ref that looks like an option, or names no
    commit, is an error -- never an empty range."""
    if not isinstance(ref, str) or not ref.strip():
        raise DeployError("empty git ref")
    if ref.startswith("-"):
        raise DeployError("refusing git ref %r: it starts with '-'" % ref)
    if any(c in ref for c in "\0\n\r"):
        raise DeployError("refusing git ref %r: control characters" % ref)
    sha = project.git("rev-parse", "--verify", "--quiet", "--end-of-options",
                      ref + "^{commit}").strip()
    if not SHA_RE.match(sha):
        # --end-of-options needs git 2.24; the leading '-' check above already guards
        # older ones, so try again without it before giving up.
        sha = project.git("rev-parse", "--verify", "--quiet", ref + "^{commit}").strip()
    if not SHA_RE.match(sha):
        raise DeployError("unknown git ref %r: it names no commit" % ref)
    return sha


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_record(project, version):
    try:
        return _read_json(record_path(project, version))
    except DeployError:
        return None


def ledger_lines(project):
    """([line dict], skipped count) in file order. A malformed or hand-broken line is
    skipped and counted, never fatal."""
    lines, skipped = [], 0
    try:
        with open(ledger_path(project), encoding="utf-8", errors="replace") as handle:
            raw = handle.read().splitlines()
    except (IOError, OSError):
        return lines, skipped
    for text in raw:
        if not text.strip():
            continue
        try:
            line = json.loads(text)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(line, dict) or not validate_version(line.get("version")) \
                or not validate_env(line.get("env")):
            skipped += 1
            continue
        lines.append(line)
    return lines, skipped


def deployed(project):
    """{"envs": {env: newest ledger line}, "skipped": n}. The last line per env wins."""
    lines, skipped = ledger_lines(project)
    envs = {}
    for line in lines:
        envs[line["env"]] = line
    return {"envs": envs, "skipped": skipped}


def view_model(project):
    """What the viewer shows: deployed() plus the record behind each env's version."""
    model = deployed(project)
    records = {}
    for line in model["envs"].values():
        rec = load_record(project, line["version"])
        if rec is not None:
            records[line["version"]] = rec
    model["records"] = records
    return model


def default_from(project, env):
    """Where a new record's range starts: the env's last deployed commit, else the newest
    release record of any env, else None (the whole history)."""
    line = deployed(project)["envs"].get(env)
    if line and SHA_RE.match(str(line.get("to") or "")):
        return line["to"]
    newest = None
    folder = releases_dir(project)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    for name in names:
        if not name.endswith(".json") or not validate_version(name[:-5]):
            continue
        rec = _read_json(os.path.join(folder, name))
        if not rec or not SHA_RE.match(str(rec.get("to") or "")):
            continue
        if newest is None or str(rec.get("date") or "") > str(newest.get("date") or ""):
            newest = rec
    return newest["to"] if newest else None


def collect(project, rt, from_sha, to_sha):
    """{"commits": n, "items": [IDs]} for from_sha..to_sha. Only the Work-Item trailer
    counts: an ID mentioned in prose is not a shipped item."""
    span = "%s..%s" % (from_sha, to_sha) if from_sha else to_sha
    out = project.git("log", "--format=%H%x00%B%x1e", span)
    commits, items = 0, set()
    for chunk in out.split("\x1e"):
        sha, sep, body = chunk.strip("\n").partition("\x00")
        if not sep or not SHA_RE.match(sha.strip()):
            continue
        commits += 1
        item = work_item(rt, body)
        if item:
            items.add(item)
    return {"commits": commits, "items": sorted(items)}


def work_item(rt, body):
    """The Work-Item trailer. rt.trailers reads only the last paragraph, and a harness
    often adds its Co-Authored-By line as a paragraph of its own, so earlier paragraphs
    made only of trailer lines are read too, newest paragraph first."""
    found = rt.trailers(body).get("Work-Item", "").strip()
    if found:
        return found
    paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    for para in reversed(paragraphs[1:]):
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        if not lines or not all(rt.TRAILER.match(l) for l in lines):
            break
        for l in lines:
            m = rt.TRAILER.match(l)
            if m.group(1) == "Work-Item":
                return m.group(2).strip()
    return ""


def _clean_person(name):
    """A display name, or None. Never an email address."""
    if not isinstance(name, str):
        return None
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:100]
    if not name or EMAIL_RE.search(name):
        return None
    return name


def person(project, rt, by=None):
    """Who deployed: --by, else the project's person lookup when the runtime has one,
    else git user.name, else None."""
    if by is not None:
        if EMAIL_RE.search(by):
            raise DeployError("--by looks like an email address; give a name or handle "
                              "(email addresses are never stored)")
        cleaned = _clean_person(by)
        if not cleaned:
            raise DeployError("--by is empty")
        return cleaned
    lookup = getattr(rt, "person", None)
    if callable(lookup):
        try:
            found = _clean_person(lookup(project))
        except Exception:
            found = None
        if found:
            return found
    return _clean_person(project.git("config", "user.name").strip())


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_ledger(project, line):
    """One JSON line, in a single write on an O_APPEND descriptor, so two writers never
    interleave within a line."""
    path = ledger_path(project)
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    data = (json.dumps(line, sort_keys=True) + "\n").encode("utf-8")
    # O_NOFOLLOW: a ledger planted as a symlink must not redirect the write elsewhere.
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


# The severity ladder (CARD.md): S0 and S1 block a release outright; S2 blocks unless a named
# approver accepts it in writing (NUHT-041).
HARD_BLOCKERS = ("S0", "S1")
ACCEPTABLE = ("S2",)


def fix_shipped(project, item_id, to_sha):
    """True when the history of to_sha has a commit whose Work-Item trailer is item_id: the
    deployed code carries its fix, in this range or an earlier one."""
    if not to_sha or not SHA_RE.match(to_sha):
        return False
    pattern = "^Work-Item:[[:space:]]*%s[[:space:]]*$" % re.escape(item_id)
    return bool(project.git("log", "-1", "--format=%H", "--extended-regexp",
                            "--grep=" + pattern, to_sha).strip())


def release_blockers(project, shipped, to_sha=None):
    """Open S0-S2 defects the deployed code carries no fix for. A defect whose ID is a
    Work-Item trailer in the range, or anywhere in to_sha's history, does not block."""
    items = shards.merged_items(project)
    return [it for it in shards.open_defects(items, HARD_BLOCKERS + ACCEPTABLE)
            if it["id"] not in shipped and not fix_shipped(project, it["id"], to_sha)]


def check_defects(project, rt, shipped, accept, by, reason, to_sha=None):
    """[{id, severity, by, reason}] for the accepted S2 defects; raises DeployError when an
    open defect blocks this release."""
    blockers = release_blockers(project, set(shipped or ()), to_sha)
    by_id = dict((b["id"], b) for b in blockers)
    accept = [a for a in (accept or []) if a]
    for a in accept:
        if a in by_id and by_id[a]["severity"] in HARD_BLOCKERS:
            raise DeployError("%s is an open %s defect, which cannot be accepted: fix it in this "
                              "deploy (a Work-Item: %s commit), or change its severity or status "
                              "with `item set`, which the item's history keeps" % (
                                  a, by_id[a]["severity"], a))
        if a not in by_id:
            raise DeployError("--accept-defects %s: not an open S2 defect this deploy leaves "
                              "unfixed" % a)
    hard = [b for b in blockers if b["severity"] in HARD_BLOCKERS]
    soft = [b for b in blockers if b["severity"] in ACCEPTABLE and b["id"] not in accept]
    if hard or soft:
        lines = ["%s %s: %s" % (b["severity"], b["id"], b.get("title", "")) for b in hard + soft]
        how = []
        if hard:
            how.append("S0 and S1 block a release until fixed: ship a commit with their "
                       "Work-Item: trailer, or change the item with `item set`")
        if soft:
            how.append("an approver may accept an S2: --accept-defects <ID> --by <approver> "
                       "--reason \"...\"")
        raise DeployError("open defects block this release (CARD.md severity ladder):\n  %s\n%s"
                          % ("\n  ".join(lines), "; ".join(how)))
    if not accept:
        return []
    if not by or not (reason or "").strip():
        raise DeployError("--accept-defects needs --by <approver> and --reason \"...\"")
    finish_mod = rt.runtime_module("finish")
    approvers, source, registry = finish_mod.waiver_approvers(rt, project)
    refused = finish_mod.check_waiver(rt, project, by, approvers, source, registry,
                                      finish_mod._interactive())
    if refused:
        raise DeployError("the acceptance is refused: %s" % refused)
    return [{"id": a, "severity": by_id[a]["severity"], "by": by, "reason": reason.strip()}
            for a in accept]


def record(project, rt, version, env, from_ref=None, to_ref="HEAD", by=None, dry_run=False,
           accept=None, reason=None):
    """Record that <version> runs in <env>. Returns {"action", "record", "ledger",
    "path", "dry_run"}; raises DeployError on a refusal, with nothing written."""
    path = record_path(project, version)
    if not validate_env(env):
        raise DeployError("invalid env %r: lower-case letters, digits, _ and - (up to 32, "
                          "starting with a letter or digit)" % (env,))
    if not project.git("rev-parse", "--git-dir").strip():
        raise DeployError("not a git repository: %s" % project.root)
    if not SHA_RE.match(project.git("rev-parse", "--verify", "--quiet", "HEAD^{commit}").strip()):
        raise DeployError("this repository has no commits yet; commit first, then record")
    to_sha = resolve_ref(project, to_ref or "HEAD")
    from_sha = resolve_ref(project, from_ref) if from_ref else None
    who = person(project, rt, by)
    agent = rt.identity(None, None)[0]
    date = _now()
    existing = _read_json(path) if os.path.exists(path) else None
    if os.path.exists(path) and existing is None:
        raise DeployError("%s exists but is not a JSON record; fix or remove it by hand"
                          % os.path.relpath(path, project.root))
    if existing is not None:
        if existing.get("to") != to_sha:
            raise DeployError("version %s was recorded at %s; this is %s. A version is never "
                              "rewritten: record a new version" % (
                                  version, str(existing.get("to"))[:12], to_sha[:12]))
        action = "promotion"
        rec = dict(existing)
        envs = list(rec.get("envs") or ([rec["env"]] if rec.get("env") else []))
        if env not in envs:
            envs.append(env)
        rec["envs"] = envs
        from_used = rec.get("from")
    else:
        action = "new"
        if from_sha is None:
            from_sha = default_from(project, env)
        found = collect(project, rt, from_sha, to_sha)
        rec = {"schema": SCHEMA, "version": version, "env": env, "envs": [env],
               "from": from_sha, "to": to_sha, "commits": found["commits"],
               "items": found["items"], "date": date, "by": who, "agent": agent}
        from_used = from_sha
    accepted = check_defects(project, rt, rec.get("items") or [], accept, by, reason, to_sha)
    if accepted:
        kept = [a for a in rec.get("accepted_defects") or []
                if a.get("id") not in set(x["id"] for x in accepted)]
        rec["accepted_defects"] = kept + accepted
    line = {"schema": SCHEMA, "version": version, "env": env, "from": from_used,
            "to": to_sha, "date": date, "by": who, "agent": agent}
    result = {"action": action, "record": rec, "ledger": line,
              "path": os.path.relpath(path, project.root), "dry_run": bool(dry_run)}
    if dry_run:
        return result
    if action == "new" or rec != existing:
        shards._atomic_write_text(path, json.dumps(rec, indent=2, sort_keys=True) + "\n")
    append_ledger(project, line)
    return result


def format_list(state):
    envs = state.get("envs") or {}
    lines = []
    if not envs:
        lines.append("nothing recorded yet: python3 .ai-sdlc/bin/sdlc.py deploy record "
                     "--version <v> --env <env>")
    else:
        lines.append("%-12s %-20s %-20s %-12s %s" % ("ENV", "VERSION", "DATE", "COMMIT", "BY"))
        for env in sorted(envs):
            line = envs[env]
            lines.append("%-12s %-20s %-20s %-12s %s" % (
                env, line.get("version", ""), str(line.get("date") or "")[:19],
                str(line.get("to") or "")[:12], line.get("by") or "-"))
    if state.get("skipped"):
        lines.append("skipped %d malformed ledger line(s) in deploys.jsonl" % state["skipped"])
    return "\n".join(lines)

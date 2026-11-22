"""Who is working on what, and what can safely run side by side.

A claim is a file in the repository's shared git directory (<git-common-dir>/nuhut/
claims/<ID>.json). Every worktree of a clone shares that directory, so agents working in
parallel on one machine see each other's claims, and the file is created atomically:
two agents cannot both take the same item.

Across machines or CI workers (`--sync-refs`), claims and ID sequences coordinate via
atomic Git fast-forward / ref-creation compare-and-swap (CAS) pushes on:
  - refs/nuhut/claims/<ID>  (parentless commit -> only one creator can win non-force push)
  - refs/nuhut/seq          (linear commit chain -> non-force push retries on race)

`parallel` lists Ready items nobody holds, grouped so that no two in a group touch the
same files (from item `touch` globs, plan "Files that change", or spec deltas). Tier 1
items still require a written plan file before scheduling; single-writer files -- the
charter, migrations, lockfiles, and charter Single-writer globs -- always conflict.

Called by sdlc.py (claim, release, claims, parallel, next-id), doctor and view.py.
Standard library only. This file must never contain two opening braces in a row.
"""

import datetime
import json
import os
import re
import socket
import subprocess
import time

import shards

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9]+\b")
LOCKFILES = (
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
    "poetry.lock", "uv.lock", "Pipfile.lock", "Cargo.lock", "go.sum",
    "Gemfile.lock", "composer.lock",
)


def _git_env():
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "nuhut")
    env.setdefault("GIT_AUTHOR_EMAIL", "nuhut@local")
    env.setdefault("GIT_COMMITTER_NAME", "nuhut")
    env.setdefault("GIT_COMMITTER_EMAIL", "nuhut@local")
    return env


def _git(project, *args):
    try:
        return subprocess.run(
            ["git"] + list(args),
            cwd=project.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ).stdout
    except OSError:
        return ""


def _git_ok(cwd, *args, input_text=None):
    p = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=_git_env(),
    )
    return p.returncode == 0, p.stdout.strip(), p.stderr.strip()


def common_dir(project):
    raw = _git(project, "rev-parse", "--git-common-dir").strip()
    if not raw:
        return ""
    return raw if os.path.isabs(raw) else os.path.normpath(os.path.join(project.root, raw))


def nuhut_git_dir(project):
    base = common_dir(project)
    return os.path.join(base, "nuhut") if base else ""


def registry(project):
    base = nuhut_git_dir(project)
    return os.path.join(base, "claims") if base else ""


def main_worktree(project):
    """The checkout that owns the shared git directory (where --mark may edit backlog.md)."""
    base = common_dir(project)
    return os.path.dirname(base) if base.endswith(os.sep + ".git") or base.endswith("/.git") else ""


def is_main_worktree(project):
    main = main_worktree(project)
    return bool(main) and os.path.realpath(main) == os.path.realpath(project.root)


# ---------------------------------------------------------------- git CAS helpers

def _commit_json_blob(project, filename, data, parent_sha="", message="nuhut"):
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    ok, blob_sha, err = _git_ok(project.root, "hash-object", "-w", "--stdin", input_text=payload)
    if not ok or not blob_sha:
        return "", "git hash-object failed: %s" % err
    tree_line = "100644 blob %s\t%s\n" % (blob_sha, filename)
    ok, tree_sha, err = _git_ok(project.root, "mktree", input_text=tree_line)
    if not ok or not tree_sha:
        return "", "git mktree failed: %s" % err
    cmd = ["commit-tree", tree_sha]
    if parent_sha:
        cmd += ["-p", parent_sha]
    cmd += ["-m", message]
    ok, commit_sha, err = _git_ok(project.root, *cmd)
    if not ok or not commit_sha:
        return "", "git commit-tree failed: %s" % err
    return commit_sha, ""


def _read_ref_json(project, ref, filename):
    raw = _git(project, "show", "%s:%s" % (ref, filename))
    if not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def _has_remote(project, remote="origin"):
    ok, _, _ = _git_ok(project.root, "remote", "get-url", remote)
    return ok


def sync_remote_claims(project, remote="origin"):
    if not _has_remote(project, remote):
        return False, "git remote %r is not configured" % remote
    # Prune local remote-claims tracking refs first, then fetch all live remote claims.
    existing = _git(
        project, "for-each-ref", "--format=%(refname)", "refs/nuhut/remote-claims"
    ).splitlines()
    ok, _, err = _git_ok(
        project.root,
        "fetch",
        "--prune",
        "--quiet",
        remote,
        "+refs/nuhut/claims/*:refs/nuhut/remote-claims/*",
    )
    if not ok:
        # When a bare remote has zero refs/nuhut/claims/* yet, git fetch exits 0 on modern git,
        # or warns couldn't find remote ref on very old git. Treat missing refspec as empty.
        if "couldn't find remote ref" in err.lower() or "no_match" in err.lower():
            for ref in existing:
                if ref.strip():
                    _git_ok(project.root, "update-ref", "-d", ref.strip())
            return True, ""
        return False, "git fetch %s refs/nuhut/claims/* failed: %s" % (remote, err)
    return True, ""


def _delete_remote_claim(project, remote, item, expected_sha):
    """Delete refs/nuhut/claims/<item> on remote only if it still points at expected_sha."""
    ref = "refs/nuhut/claims/%s" % item
    ok, _, err = _git_ok(project.root, "push", "--force-with-lease=%s:%s" % (ref, expected_sha),
                         remote, ":" + ref)
    if ok or "remote ref does not exist" in err.lower() or "unable to delete" in err.lower():
        _git_ok(project.root, "update-ref", "-d", "refs/nuhut/remote-claims/%s" % item)
        return True, ""
    return False, err


def _remote_claim_records(project):
    out = {}
    refs = _git(
        project, "for-each-ref", "--format=%(refname)", "refs/nuhut/remote-claims"
    ).splitlines()
    for ref in refs:
        ref = ref.strip()
        if not ref:
            continue
        item_id = ref.rsplit("/", 1)[-1]
        data = _read_ref_json(project, ref, "claim.json")
        if data.get("id"):
            data = dict(data, remote=True)
            out[data["id"]] = data
        elif item_id:
            out[item_id] = {"id": item_id, "remote": True}
    return out


# ---------------------------------------------------------------- atomic sequence (next-id)

def _acquire_lock(lock_path, timeout=5.0):
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("%d %f\n" % (os.getpid(), time.time()))
            return True
        except FileExistsError:
            try:
                st = os.stat(lock_path)
                if time.time() - st.st_mtime > 15.0:
                    os.unlink(lock_path)
                    continue
            except OSError:
                pass
            if time.time() >= deadline:
                return False
            time.sleep(0.02)


def _scan_repo_max(project, kind):
    if kind == "adr":
        adr_dir = project.path(os.path.join(project.docs, "project", "adr"))
        best = 0
        if os.path.isdir(adr_dir):
            for name in os.listdir(adr_dir):
                m = re.match(r"^([0-9]{1,6})-", name)
                if m:
                    best = max(best, int(m.group(1)))
        return best

    prefix = project.prefix
    if not prefix:
        return 0
    pat = re.compile(r"\b%s-([0-9]+)\b" % re.escape(prefix))
    unfilled_re = re.compile(r"_\([^)]*\)_")
    best = 0
    sources = [
        unfilled_re.sub("", project.records("backlog.md") or ""),
        unfilled_re.sub("", project.worklog_texts() or ""),
        _git(project, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes", "refs/nuhut"),
    ]
    for src in sources:
        for m in pat.finditer(src or ""):
            best = max(best, int(m.group(1)))
    for it_id in shards.load_items(project):
        m = pat.match(it_id)
        if m:
            best = max(best, int(m.group(1)))
    return best


def _format_seq_id(prefix, kind, number):
    if kind == "adr":
        return "%04d" % number if number < 10000 else "%d" % number
    return ("%s-%03d" % (prefix, number)) if number < 1000 else ("%s-%d" % (prefix, number))


def next_id(project, kind="item", sync_refs=False, remote="origin"):
    """Atomically allocate the next work-item or ADR ID, optionally CAS-synced to origin."""
    if kind not in ("item", "adr"):
        return None, "unknown sequence kind %r (expected item or adr)" % kind
    if kind == "item" and not project.prefix:
        return None, "no work item prefix configured in %s" % project.charter_path
    base = nuhut_git_dir(project)
    if not base:
        return None, "not a git repository"
    os.makedirs(base, exist_ok=True)
    lock_path = os.path.join(base, "seq.lock")
    seq_path = os.path.join(base, "seq.json")
    if not _acquire_lock(lock_path):
        return None, "timed out waiting for sequence lock %s" % lock_path

    try:
        try:
            with open(seq_path, encoding="utf-8") as handle:
                local_seq = json.load(handle)
            if not isinstance(local_seq, dict):
                local_seq = {}
        except (IOError, OSError, ValueError):
            local_seq = {}

        repo_max = _scan_repo_max(project, kind)

        if sync_refs:
            if not _has_remote(project, remote):
                return None, "git remote %r is not configured" % remote
            last_err = ""
            for _ in range(10):
                ok_f, _, err_f = _git_ok(
                    project.root, "fetch", "--quiet", remote, "+refs/nuhut/seq:refs/nuhut/seq"
                )
                if not ok_f and "couldn't find remote ref" not in err_f.lower():
                    # Check whether refs/nuhut/seq simply does not exist on remote yet.
                    ok_ls, ls_out, ls_err = _git_ok(project.root, "ls-remote", remote, "refs/nuhut/seq")
                    if not ok_ls:
                        return None, "git ls-remote %s failed: %s" % (remote, ls_err)
                    if not ls_out.strip():
                        _git_ok(project.root, "update-ref", "-d", "refs/nuhut/seq")
                remote_sha = _git(project, "rev-parse", "--verify", "--quiet", "refs/nuhut/seq").strip()
                remote_seq = _read_ref_json(project, "refs/nuhut/seq", "seq.json") if remote_sha else {}
                cur_max = max(
                    repo_max,
                    int(local_seq.get(kind) or 0),
                    int(remote_seq.get(kind) or 0),
                )
                allocated = cur_max + 1
                merged_seq = dict(local_seq)
                merged_seq.update(remote_seq)
                merged_seq[kind] = allocated
                formatted = _format_seq_id(project.prefix, kind, allocated)
                commit_sha, c_err = _commit_json_blob(
                    project, "seq.json", merged_seq, parent_sha=remote_sha,
                    message="seq: %s" % formatted,
                )
                if c_err:
                    return None, c_err
                ok_p, _, err_p = _git_ok(
                    project.root, "push", remote, "%s:refs/nuhut/seq" % commit_sha
                )
                if ok_p:
                    _git_ok(project.root, "update-ref", "refs/nuhut/seq", commit_sha)
                    shards._atomic_write_text(seq_path, json.dumps(merged_seq, indent=2, sort_keys=True) + "\n")
                    return {
                        "id": formatted,
                        "kind": kind,
                        "number": allocated,
                        "synced": True,
                    }, None
                last_err = err_p
                time.sleep(0.02)
            return None, "failed to allocate %s ID via %s after CAS retries: %s" % (kind, remote, last_err)

        allocated = max(repo_max, int(local_seq.get(kind) or 0)) + 1
        local_seq[kind] = allocated
        shards._atomic_write_text(seq_path, json.dumps(local_seq, indent=2, sort_keys=True) + "\n")
        formatted = _format_seq_id(project.prefix, kind, allocated)
        return {
            "id": formatted,
            "kind": kind,
            "number": allocated,
            "synced": False,
        }, None
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


# ---------------------------------------------------------------- items & claims

def items(project, view_mod):
    """{id: {title, type, tier, status, column, depends, touch, line, section}} from backlog + shards."""
    text = project.records("backlog.md")
    shard_map = shards.load_items(project)
    out = {}
    for section, line, row in view_mod.backlog_tables(text):
        rid = (row.get("ID") or "").strip()
        m = ID_RE.search(rid)
        if not m:
            continue
        item_id = m.group(0)
        raw_task = row.get("Task", row.get("Title", ""))
        status = view_mod.plain(row.get("Status", ""))
        itype = view_mod.plain(row.get("Type", "")).lower()
        raw_tier = view_mod.plain(row.get("Tier", ""))
        m_tier = re.search(r"[123]", raw_tier)
        tier = m_tier.group(0) if m_tier else "2"
        touch = shards.extract_inline_touch(raw_task)
        sh = shard_map.get(item_id)
        if sh:
            itype = sh.get("type") or itype
            tier = sh.get("tier") or tier
            if sh.get("touch"):
                touch = list(sh["touch"])
        out[item_id] = {
            "title": sh["title"] if sh else view_mod.plain(shards._strip_inline_tags(raw_task)),
            "type": itype,
            "tier": tier,
            "status": status,
            "column": view_mod.column_of(status),
            "line": line,
            "section": section,
            "depends": [d for d in ID_RE.findall(row.get("Depends on", "")) if d != item_id],
            "touch": touch,
        }
    return out


def list_claims(project, sync_refs=False, remote="origin"):
    if sync_refs:
        sync_remote_claims(project, remote)
    folder = registry(project)
    by_id = {}
    if folder and os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(folder, name), encoding="utf-8") as h:
                    data = json.load(h)
            except (IOError, OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("id"):
                by_id[data["id"]] = data
    for rem_id, rem_data in sorted(_remote_claim_records(project).items()):
        if rem_id not in by_id:
            by_id[rem_id] = rem_data
        else:
            by_id[rem_id]["synced"] = True

    out = []
    for cid in sorted(by_id.keys(), key=shards._id_sort_key):
        data = by_id[cid]
        branch = data.get("branch", "")
        last = _git(project, "log", "-1", "--format=%cI", branch, "--").strip() if branch else ""
        data["last_commit"] = last
        data["worktree_exists"] = bool(data.get("worktree")) and os.path.isdir(data["worktree"])
        out.append(data)
    return out


def slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return "-".join(s.split("-")[:6])[:40].strip("-") or "work"


def _branch_prefix(it):
    itype = (it.get("type") or "").lower()
    title = (it.get("title") or "").lower()
    if itype in ("defect", "bug", "fix", "hotfix") or re.match(r"^(?:fix|bug|defect)\b", title):
        return "fix"
    if itype in ("chore", "docs", "refactor", "test"):
        return itype
    return "feat"


def _existing_item_branch(project, item):
    refs = _git(project, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
    for b in refs:
        m = re.match(r"^(?:[\w.-]+/)?([A-Z][A-Z0-9]*-[0-9]+)(?:-|$)", b)
        if m and m.group(1) == item:
            return b
    return ""


def claim(project, view_mod, item, agent, worktree=None, no_worktree=False, mark=False,
          base=None, sync_refs=False, remote="origin", person=None):
    """Returns (record, error). <person> is the people.json handle of the human behind
    the agent (sdlc.person_identity), or None when it is not known: recorded as null,
    never guessed."""
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
    os.makedirs(folder, exist_ok=True)
    has_item_shard = shards.load_item(project, item) is not None
    if mark and not is_main_worktree(project) and not has_item_shard:
        return None, "--mark edits backlog.md, which only the main worktree (%s) may do" % (main_worktree(project) or "?")

    if sync_refs:
        ok_sync, err_sync = sync_remote_claims(project, remote)
        if not ok_sync:
            return None, err_sync
        rem = _remote_claim_records(project).get(item)
        if rem:
            return None, "%s is already claimed on %s by %s since %s (host %s)" % (
                item, remote, rem.get("agent", "?"), rem.get("since", "?"), rem.get("host", "?")
            )

    existing_br = _existing_item_branch(project, item)
    branch = existing_br or ("%s/%s-%s" % (_branch_prefix(it), item, slug(it["title"])))
    main_wt = main_worktree(project) or project.root
    path = None if no_worktree else (
        worktree or os.path.join(os.path.dirname(main_wt), "%s-%s" % (os.path.basename(main_wt), item))
    )
    record = {
        "id": item,
        "agent": agent,
        "person": person or None,
        "branch": branch,
        "worktree": path or "",
        "since": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": socket.gethostname(),
        "title": it["title"],
    }
    if sync_refs:
        record["synced"] = True

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
            item, held.get("agent", "?"), held.get("since", "?"), held.get("branch", "?")
        )
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(record, h, indent=2)

    if sync_refs:
        commit_sha, c_err = _commit_json_blob(
            project, "claim.json", record, parent_sha="", message="claim: %s" % item
        )
        if c_err:
            os.remove(target)
            return None, c_err
        ok_p, _, err_p = _git_ok(
            project.root, "push", remote, "%s:refs/nuhut/claims/%s" % (commit_sha, item)
        )
        if not ok_p:
            os.remove(target)
            sync_remote_claims(project, remote)
            rem = _remote_claim_records(project).get(item) or {}
            holder = rem.get("agent")
            if holder:
                return None, "%s is already claimed on %s by %s since %s (host %s)" % (
                    item, remote, holder, rem.get("since", "?"), rem.get("host", "?")
                )
            return None, "remote claim push failed for %s: %s" % (item, err_p)
        _git_ok(project.root, "update-ref", "refs/nuhut/remote-claims/%s" % item, commit_sha)
        # Remember which remote lease is ours, so release can delete it compare-and-swap.
        record["ref_sha"] = commit_sha
        with open(target, "w", encoding="utf-8") as h:
            json.dump(record, h, indent=2)

    def _rollback_claim():
        try:
            os.remove(target)
        except OSError:
            pass
        if sync_refs:
            _delete_remote_claim(project, remote, item, commit_sha)

    exists = bool(_git(project, "rev-parse", "--verify", "--quiet", branch).strip())
    if path:
        args = (
            ["worktree", "add", path, branch]
            if exists
            else ["worktree", "add", "-b", branch, path] + ([base] if base else [])
        )
        ok, out_s, err_s = _git_ok(project.root, *args)
        if not ok:
            _rollback_claim()
            return None, "git worktree add failed: %s" % (err_s or out_s)
    elif not exists:
        ok, out_s, err_s = _git_ok(project.root, "branch", branch, *([base] if base else []))
        if not ok:
            _rollback_claim()
            return None, "git branch failed: %s" % (err_s or out_s)
    if mark:
        mark_status(project, item, it, "In progress")
    return record, None


def mark_status(project, item, it, status):
    """Update item shard if present, else rewrite the Status cell of backlog.md."""
    sh = shards.load_item(project, item)
    if sh is not None:
        sh["status"] = status
        sh["updated"] = datetime.date.today().isoformat()
        shards.save_item(project, sh)
        return True
    rel = os.path.join(project.docs, "project", "backlog.md")
    path = project.path(rel)
    try:
        with open(path, encoding="utf-8") as h:
            lines = h.read().split("\n")
    except (IOError, OSError):
        return False
    idx = it["line"] - 1 if it["line"] else -1
    if not (0 <= idx < len(lines)) or item not in lines[idx]:
        idx = next(
            (n for n, l in enumerate(lines) if l.strip().startswith("|") and re.search(r"\|\s*%s\s*\|" % re.escape(item), l)),
            -1,
        )
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


def release(project, item, remove_worktree=False, agent=None, force=False,
            sync_refs=False, remote="origin"):
    reg = registry(project)
    if not reg:
        return None, "not a git repository"
    if sync_refs:
        ok_sync, err_sync = sync_remote_claims(project, remote)
        if not ok_sync:
            return None, err_sync

    target = os.path.join(reg, item + ".json")
    record = None
    if os.path.exists(target):
        with open(target, encoding="utf-8") as h:
            record = json.load(h)
    remote_sha = ""
    if sync_refs:
        # The remote lease is the truth; a local record may be stale.
        remote_sha = _git(project, "rev-parse", "--verify", "--quiet",
                          "refs/nuhut/remote-claims/%s" % item).strip()
        remote_rec = _remote_claim_records(project).get(item) if remote_sha else None
        if record and record.get("synced"):
            ours = record.get("ref_sha") or ""
            if remote_sha and ours != remote_sha:
                if not force:
                    try:
                        os.remove(target)
                    except OSError:
                        pass
                    return None, ("%s was taken over on %s by %s since %s; dropped the stale "
                                  "local claim record and left the remote lease alone" % (
                                      item, remote, (remote_rec or {}).get("agent", "?"),
                                      (remote_rec or {}).get("since", "?")))
                record = remote_rec or record
        elif remote_rec:
            record = remote_rec

    if not record:
        return None, "%s is not claimed" % item

    if not force:
        held_agent = record.get("agent") or ""
        held_host = record.get("host") or ""
        if agent and held_agent and agent != held_agent:
            return None, "%s is claimed by %s, not %s (pass --force to override)" % (item, held_agent, agent)
        if held_host and held_host != socket.gethostname():
            return None, "%s is claimed on host %s (pass --force to override)" % (item, held_host)

    wt = record.get("worktree") or ""
    if remove_worktree and wt and os.path.isdir(wt) and record.get("host", socket.gethostname()) == socket.gethostname():
        ok, status_out, _ = _git_ok(wt, "status", "--porcelain")
        if status_out:
            return None, "the worktree %s has uncommitted changes; commit or stash them first" % wt
        ok, out_s, err_s = _git_ok(project.root, "worktree", "remove", wt)
        if not ok:
            return None, "git worktree remove failed: %s" % (err_s or out_s)

    if sync_refs and remote_sha:
        ok_p, err_p = _delete_remote_claim(project, remote, item, remote_sha)
        if not ok_p:
            return None, ("remote claim %s on %s changed since it was checked; nothing was "
                          "released: %s" % (item, remote, err_p))

    try:
        os.remove(target)
    except FileNotFoundError:
        pass
    return record, None


# ---------------------------------------------------------------- parallel

def plan_text(project, item, rt):
    folder = os.path.join(project.docs, "project", "plans")
    rel = os.path.join(folder, item + ".md")
    if not os.path.isfile(project.path(rel)) and os.path.isdir(project.path(folder)):
        named = sorted(
            n for n in os.listdir(project.path(folder)) if n.startswith(item + "-") and n.endswith(".md")
        )
        if named:
            rel = os.path.join(folder, named[0])
    return rt.read(project.path(rel))


def _spec_change_paths(project, item, rt):
    """Paths declared in <docs>/project/specs/changes/<ID>.md when living specs are used."""
    rel = os.path.join(project.docs, "project", "specs", "changes", item + ".md")
    text = rt.read(project.path(rel))
    if not text:
        return []
    paths = list(rt.planned_paths(text))
    for cap in re.findall(r"(?m)^#\s+Capability:\s*([A-Za-z0-9._-]+)\s*$", text):
        spec_rel = os.path.join(project.docs, "project", "specs", cap, "spec.md")
        if spec_rel not in paths:
            paths.append(spec_rel)
    return paths


def _charter_single_writers(project, rt):
    if not rt or not getattr(project, "charter", ""):
        return []
    raw = rt.labelled(project.charter, "Single-writer files") or ""
    cleaned = rt.UNFILLED.sub("", raw)
    globs = []
    for tok in re.findall(r"`([^`]+)`", cleaned):
        tok = tok.strip()
        if tok:
            globs.append((tok, rt.glob_regex(tok)))
    return globs


def single_writer(path, project, rt=None, custom_globs=None):
    """A shared resource the path belongs to, if it is one only one agent may change."""
    p = path.lower()
    if os.path.basename(p) in LOCKFILES:
        return "lockfile"
    if "migration" in p or "/migrate/" in p or p.startswith("migrate/"):
        return "migrations"
    if p.endswith("charter.md") and "project" in p:
        return "charter"
    for pat, rx in (custom_globs or ()):
        if rx.match(path):
            return "charter:%s" % pat
    return ""


def overlaps(a, b, rt):
    a_re, b_re = rt.glob_regex(a), rt.glob_regex(b)
    if a_re.match(b) or b_re.match(a):
        return True
    a_dir, b_dir = re.split(r"[*?\[]", a)[0], re.split(r"[*?\[]", b)[0]
    return bool(
        a_dir
        and b_dir
        and (a_dir.startswith(b_dir) or b_dir.startswith(a_dir))
        and (a_dir != a or b_dir != b)
    )


def _expand_touch_globs(touch_list, rt):
    out = []
    for raw in (touch_list or ()):
        for expanded in rt.expand_braces(raw.strip()):
            while expanded.startswith("./"):
                expanded = expanded[2:]
            if expanded and expanded not in out:
                out.append(expanded)
    return out


def parallel(project, rt, view_mod, sync_refs=False, remote="origin"):
    backlog = items(project, view_mod)
    held = set(c["id"] for c in list_claims(project, sync_refs=sync_refs, remote=remote))
    custom_sw = _charter_single_writers(project, rt)
    candidates, no_plan = [], []
    for item, it in backlog.items():
        if it["column"] != "Next" or item in held:
            continue
        if any(d in backlog and backlog[d]["column"] != "Done" for d in it["depends"]):
            continue
        plan_paths = rt.planned_paths(plan_text(project, item, rt) or "")
        # Tier 1 items always owe a written plan before scheduling, even if touch globs exist.
        if it.get("tier") == "1" and not plan_paths:
            no_plan.append({"id": item, "title": it["title"], "tier": "1"})
            continue
        touch_paths = _expand_touch_globs(it.get("touch"), rt)
        spec_paths = _spec_change_paths(project, item, rt)
        paths = []
        for p in touch_paths + plan_paths + spec_paths:
            if p not in paths:
                paths.append(p)
        if not paths:
            no_plan.append({"id": item, "title": it["title"], "tier": it.get("tier") or "2"})
            continue
        candidates.append(
            {
                "id": item,
                "title": it["title"],
                "tier": it.get("tier") or "2",
                "type": it.get("type") or "feat",
                "files": paths,
                "writers": sorted(
                    set(w for w in (single_writer(p, project, rt, custom_sw) for p in paths) if w)
                ),
            }
        )
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
    return {
        "groups": groups,
        "candidates": candidates,
        "conflicts": conflicts,
        "plan_first": sorted(no_plan, key=lambda x: x["id"]),
        "claimed": sorted(held),
    }


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
            out.add(
                "warn",
                "claims",
                where,
                "%s is %s but still claimed by %s; release it: "
                "python3 .ai-sdlc/bin/sdlc.py release %s"
                % (c["id"], it["status"], c.get("agent", "?"), c["id"]),
            )
            continue
        try:
            since = datetime.datetime.strptime(c["since"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        last = c.get("last_commit", "")[:10]
        recent = last and last >= c["since"][:10]
        if (today - since).days > window_days and not recent:
            out.add(
                "warn",
                "claims",
                where,
                "claimed by %s %d days ago with no commit on %s since; "
                "re-claim it deliberately or release it"
                % (c.get("agent", "?"), (today - since).days, c.get("branch", "?")),
            )
    branches = _git(project, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
    per_id = {}
    for b in branches:
        m = re.match(r"^(?:[\w.-]+/)?([A-Z][A-Z0-9]*-[0-9]+)(?:-|$)", b)
        if m:
            per_id.setdefault(m.group(1), []).append(b)
    for item, names in sorted(per_id.items()):
        if len(names) > 1 and any(c["id"] == item for c in claims):
            out.add(
                "warn",
                "claims",
                "claim %s" % item,
                "%d branches for one item (%s); two agents may be on it"
                % (len(names), ", ".join(names[:4])),
            )

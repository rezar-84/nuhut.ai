"""`sdlc.py sync`: where this checkout stands against its remote and the default branch.

Read-only. It reports and names the next command; it never merges, rebases, pulls or
pushes, because changing the working tree is a decision the rules in
process/05-change-control.md ("Staying in step with the remote") leave to whoever is
doing the work. `--fetch` is the one thing it runs against the network, and a fetch only
moves remote-tracking refs.
"""
import os
import subprocess
import time

STRATEGIES = ("merge", "rebase")
STALE_FETCH_HOURS = 24
IN_PROGRESS = (("MERGE_HEAD", "merge"), ("rebase-merge", "rebase"), ("rebase-apply", "rebase"),
               ("CHERRY_PICK_HEAD", "cherry-pick"), ("REVERT_HEAD", "revert"))


def strategy(cell):
    """The charter's Updating a branch row. Blank, or anything else, is merge: it is the
    one that cannot lose a commit somebody else already has."""
    cell = (cell or "").strip().strip("`").strip().lower()
    for name in STRATEGIES:
        if cell.startswith(name):
            return name
    return "merge"


def fetch(root, timeout=60):
    """'' when the fetch worked, otherwise why it did not. Never raises: an agent with no
    network still gets a report, marked as of the last fetch."""
    try:
        proc = subprocess.run(("git", "fetch", "--prune", "--quiet"), cwd=root, timeout=timeout,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, universal_newlines=True)
    except subprocess.TimeoutExpired:
        return "timed out after %d seconds" % timeout
    except OSError as exc:
        return str(exc)
    if proc.returncode == 0:
        return ""
    lines = [line.strip() for line in proc.stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "git fetch exited %d" % proc.returncode


def _counts(git, left, right):
    """(only in left, only in right), or None when either side does not exist."""
    out = git("rev-list", "--left-right", "--count", "%s...%s" % (left, right)).split()
    return (int(out[0]), int(out[1])) if len(out) == 2 else None


def state(project, default, do_fetch=False):
    """Everything the report needs, as a dict; None outside a git repository."""
    git = project.git
    git_dir = git("rev-parse", "--absolute-git-dir").strip()
    if not git_dir:
        return None
    s = {"branch": git("rev-parse", "--abbrev-ref", "HEAD").strip(), "default": default,
         "remotes": git("remote").split(), "fetch_error": "", "fetched": False}
    if s["branch"] == "HEAD":
        s["branch"] = ""                                # detached
    if do_fetch and s["remotes"]:
        s["fetch_error"] = fetch(project.root)
        s["fetched"] = not s["fetch_error"]
    # A linked worktree keeps its own HEAD but shares FETCH_HEAD with the main checkout.
    common = git("rev-parse", "--git-common-dir").strip() or git_dir
    if not os.path.isabs(common):
        common = os.path.join(project.root, common)
    try:
        s["fetch_age_hours"] = (time.time() - os.path.getmtime(os.path.join(common, "FETCH_HEAD"))) / 3600.0
    except OSError:
        s["fetch_age_hours"] = None
    s["upstream"] = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    counts = _counts(git, "HEAD", s["upstream"]) if s["upstream"] else None
    s["ahead"], s["behind"] = counts if counts else (None, None)
    s["default_ref"] = ""
    if default:
        for remote in (["origin"] if "origin" in s["remotes"] else []) + s["remotes"]:
            ref = "%s/%s" % (remote, default)
            if git("rev-parse", "--verify", "--quiet", "refs/remotes/" + ref).strip():
                s["default_ref"] = ref
                break
        if not s["default_ref"] and git("rev-parse", "--verify", "--quiet",
                                        "refs/heads/" + default).strip():
            s["default_ref"] = default
    counts = _counts(git, "HEAD", s["default_ref"]) if s["default_ref"] else None
    s["ahead_default"], s["behind_default"] = counts if counts else (None, None)
    s["dirty"] = len([l for l in git("status", "--porcelain").splitlines() if l.strip()])
    s["conflicted"] = [l for l in git("diff", "--name-only", "--diff-filter=U").splitlines() if l]
    s["operation"] = ""
    for name, label in IN_PROGRESS:
        if os.path.exists(os.path.join(git_dir, name)):
            s["operation"] = label
            break
    return s


def findings(s, how):
    """[(level, text, command)]: 'stop' must be dealt with before more work, 'update' before
    the item is finished, 'note' is context. The command is the next step, or ''."""
    out = []
    on_default = bool(s["branch"]) and s["branch"] == s["default"]
    if s["operation"] or s["conflicted"]:
        what = "A %s is in progress" % s["operation"] if s["operation"] else "There are conflicts"
        if s["conflicted"]:
            what += " with %d unresolved file%s: %s" % (
                len(s["conflicted"]), "" if len(s["conflicted"]) == 1 else "s",
                ", ".join(s["conflicted"][:6]) + (" ..." if len(s["conflicted"]) > 6 else ""))
        out.append(("stop", what + ". Resolve it as 05-change-control.md says, or back out.",
                    "git %s --abort" % s["operation"] if s["operation"] else ""))
    if not s["branch"]:
        out.append(("stop", "HEAD is detached: commits made here belong to no branch.",
                    "git switch <branch>"))
    if s["behind"]:
        if s["ahead"]:
            out.append(("stop", "%s and %s have diverged: %d commit%s here, %d there that "
                        "you do not have." % (s["branch"], s["upstream"], s["ahead"],
                                              "" if s["ahead"] == 1 else "s", s["behind"]),
                        "git %s %s" % (how, s["upstream"])))
        else:
            out.append(("stop", "%s is %d commit%s behind %s." % (
                s["branch"], s["behind"], "" if s["behind"] == 1 else "s", s["upstream"]),
                "git merge --ff-only %s" % s["upstream"]))
    if s["behind_default"] and not on_default:
        out.append(("update", "%s is %d commit%s behind %s. Bring it up to date before the "
                    "item is finished, and run verify again afterwards." % (
                        s["branch"] or "HEAD", s["behind_default"],
                        "" if s["behind_default"] == 1 else "s", s["default_ref"]),
                    "git %s %s" % (how, s["default_ref"])))
    if not s["remotes"]:
        out.append(("note", "No remote is configured, so there is nothing to compare with.", ""))
    elif s["branch"] and not s["upstream"]:
        out.append(("note", "%s has no upstream: its commits exist only on this machine."
                    % s["branch"], "git push -u %s %s" % (
                        "origin" if "origin" in s["remotes"] else s["remotes"][0], s["branch"])))
    elif s["ahead"] and not s["behind"]:
        out.append(("note", "%d commit%s not pushed to %s." % (
            s["ahead"], "" if s["ahead"] == 1 else "s", s["upstream"]), "git push"))
    if s["default"] and not s["default_ref"]:
        out.append(("note", "The charter's default branch, %s, is not a branch here." % s["default"], ""))
    if not s["default"]:
        out.append(("note", "The charter's Default branch row is blank, so the branch was "
                    "compared with its own upstream only.", ""))
    if s["dirty"]:
        out.append(("note", "%d uncommitted change%s. Commit or stash before you merge or rebase."
                    % (s["dirty"], "" if s["dirty"] == 1 else "s"), ""))
    if s["fetch_error"]:
        out.append(("note", "Could not fetch (%s). The figures are as of the last fetch."
                    % s["fetch_error"], ""))
    elif s["remotes"] and not s["fetched"]:
        age = s["fetch_age_hours"]
        if age is None:
            out.append(("note", "This checkout has never fetched; the figures may be old.",
                        "python3 .ai-sdlc/bin/sdlc.py sync --fetch"))
        elif age > STALE_FETCH_HOURS:
            out.append(("note", "Last fetch was %d hours ago; the figures may be old."
                        % int(age), "python3 .ai-sdlc/bin/sdlc.py sync --fetch"))
    return out


def exit_code(found, strict=False):
    levels = set(level for level, _, _ in found)
    return 1 if "stop" in levels or (strict and "update" in levels) else 0


def report(s, found, how):
    lines = ["Branch %s%s" % (s["branch"] or "(detached)",
                              "  ->  " + s["upstream"] if s["upstream"] else "")]
    if s["upstream"] and s["ahead"] is not None:
        lines.append("  against %s: %d ahead, %d behind" % (s["upstream"], s["ahead"], s["behind"]))
    if s["default_ref"] and s["ahead_default"] is not None and s["branch"] != s["default"]:
        lines.append("  against %s: %d ahead, %d behind" % (s["default_ref"], s["ahead_default"],
                                                            s["behind_default"]))
    lines.append("  updating a branch here: %s (the charter's Updating a branch row)" % how)
    lines.append("")
    labels = {"stop": "STOP  ", "update": "UPDATE", "note": "note  "}
    for level in ("stop", "update", "note"):
        for found_level, text, command in found:
            if found_level != level:
                continue
            lines.append("%s %s" % (labels[level], text))
            if command:
                lines.append("         %s" % command)
    if not any(level in ("stop", "update") for level, _, _ in found):
        lines.append("In step: nothing to bring in.")
    return lines

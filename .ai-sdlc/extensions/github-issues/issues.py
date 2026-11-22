"""GitHub Issues sync for Nuhut work items (NUHT-030), through the gh CLI.

    sdlc.py issues pull [--state open] [--label L] [--limit N] [--repo OWNER/NAME] [--dry-run]
    sdlc.py issues push ID [ID ...] | --all [--repo OWNER/NAME] [--dry-run]

pull parks each issue no item maps to as a new Parked item, with the issue number on its
shard ("issue"). An issue whose title starts with an item ID ("ACME-12: ...") links that
item instead. Only the number, title, labels and URL are read; the issue body never enters
the backlog, since it is text anyone can write. push opens an issue for each item you name
(or every open item without one, with --all) and stores its number.

Stdlib only, Python 3.8+. gh does the network calls and holds the credentials; nothing
here reads a token.
"""

import datetime
import json
import re
import shutil
import subprocess
import sys
import unicodedata

GH_TIMEOUT = 60
TITLE_MAX = 120
LIST_FIELDS = "number,title,labels,url"
CLOSED = ("Done", "Dropped")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)?|\x1b.")
_ISSUE_URL = re.compile(r"/issues/(\d+)\s*$")


def register(add, runtime):
    """Called by sdlc.py: add the `issues pull` and `issues push` verbs."""
    def pull(project, opts, parser):
        return cmd_pull(runtime, project, opts)

    def push(project, opts, parser):
        return cmd_push(runtime, project, opts)

    add(pull, help="park GitHub issues that no item maps to as new Parked items",
        configure=_configure_pull, verb="pull")
    add(push, help="open a GitHub issue for each named item (or --all) that has none",
        configure=_configure_push, verb="push")


def _common(parser):
    parser.add_argument("--repo", help="OWNER/NAME (default: the repository gh finds here)")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="show what would change and write nothing")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")


def _configure_pull(parser):
    parser.add_argument("--state", choices=("open", "closed", "all"), default="open",
                        help="which issues to read (default: open)")
    parser.add_argument("--label", action="append", default=[],
                        help="only issues with this label (repeatable)")
    parser.add_argument("--limit", type=int, default=100,
                        help="read at most this many issues, 1 to 1000 (default: 100)")
    _common(parser)


def _configure_push(parser):
    parser.add_argument("ids", nargs="*", metavar="ID", help="the items to open issues for")
    parser.add_argument("--all", action="store_true",
                        help="every item that is not Done or Dropped and has no issue")
    _common(parser)


def clean_title(text):
    """One plain line: no escape sequences, control or format characters, no `|` (the
    backlog is a markdown table), whitespace collapsed, at most TITLE_MAX characters."""
    text = _ANSI.sub("", str(text or ""))
    text = "".join(" " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") else
                   "" if unicodedata.category(ch) == "Cf" else ch for ch in text)
    text = re.sub(r"\s+", " ", text.replace("|", "/")).strip()
    if len(text) > TITLE_MAX:
        text = text[:TITLE_MAX - 3].rstrip() + "..."
    return text


class GhError(Exception):
    pass


def gh(args, repo=None):
    """Run gh with <args> (argv, no shell) and return its stdout."""
    exe = shutil.which("gh")
    if not exe:
        raise GhError("gh is not installed or not on PATH: install it from https://cli.github.com "
                      "and run `gh auth login`")
    argv = [exe] + list(args) + (["--repo", repo] if repo else [])
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise GhError("gh %s timed out after %d s" % (" ".join(args[:2]), GH_TIMEOUT))
    except OSError as exc:
        raise GhError("gh could not run (%s)" % exc.__class__.__name__)
    if proc.returncode != 0:
        lines = [l for l in (proc.stderr or "").splitlines() if l.strip()]
        raise GhError("gh %s failed (exit %d)%s" % (" ".join(args[:2]), proc.returncode,
                                                    (": " + lines[0][:300]) if lines else ""))
    return proc.stdout


def _is_defect(issue):
    for label in issue.get("labels") or []:
        name = label.get("name") if isinstance(label, dict) else label
        if isinstance(name, str) and "bug" in name.lower():
            return True
    return False


def _report(opts, result, lines):
    if getattr(opts, "json", False):
        print(json.dumps(result, indent=2))
    else:
        for line in lines:
            print(line)


def _render_hint(runtime, project, changed, dry_run):
    if changed and not dry_run:
        print("run `python3 .ai-sdlc/bin/sdlc.py render` to refresh %s/project/backlog.md"
              % project.docs)


def cmd_pull(runtime, project, opts):
    shards = runtime.runtime_module("shards")
    if not 1 <= opts.limit <= 1000:
        sys.stderr.write("issues pull: --limit must be 1 to 1000\n")
        return 2
    args = ["issue", "list", "--state", opts.state, "--limit", str(opts.limit),
            "--json", LIST_FIELDS]
    for label in opts.label:
        args += ["--label", label]
    try:
        raw = json.loads(gh(args, opts.repo) or "[]")
    except GhError as exc:
        sys.stderr.write("issues pull: %s\n" % exc)
        return 1
    except ValueError:
        sys.stderr.write("issues pull: gh issue list did not return JSON\n")
        return 1
    if not isinstance(raw, list):
        sys.stderr.write("issues pull: gh issue list did not return a list\n")
        return 1
    items = shards.merged_items(project)
    mapped = dict((it["issue"], iid) for iid, it in items.items() if it.get("issue"))
    id_at_start = re.compile(r"^\s*(%s-\d+)\s*[:\-]" % re.escape(project.prefix)) \
        if project.prefix else None
    today = datetime.date.today().isoformat()
    result = {"created": [], "linked": [], "skipped": [], "dry_run": bool(opts.dry_run)}
    lines = []
    for issue in raw:
        number = shards.issue_number(issue.get("number")) if isinstance(issue, dict) else None
        if not number:
            continue
        if number in mapped:
            continue
        title = clean_title(issue.get("title")) or "GitHub issue #%d" % number
        named = id_at_start.match(title) if id_at_start else None
        if named and named.group(1) in items:
            target = items[named.group(1)]
            if target.get("issue"):
                result["skipped"].append({"issue": number, "item": target["id"],
                                          "why": "already linked to #%d" % target["issue"]})
                lines.append("skipped #%d: its title names %s, which is linked to #%d"
                             % (number, target["id"], target["issue"]))
                continue
            if not opts.dry_run:
                saved = shards.save_item(project, dict(target, issue=number, updated=today),
                                         today=today)
                items[saved["id"]] = saved
            mapped[number] = target["id"]
            result["linked"].append({"issue": number, "item": target["id"]})
            lines.append("%s #%d -> %s (named in its title)"
                         % ("would link" if opts.dry_run else "linked", number, target["id"]))
            continue
        itype = "defect" if _is_defect(issue) else "feat"
        entry = {"issue": number, "title": title, "type": itype}
        if opts.dry_run:
            result["created"].append(entry)
            lines.append("would park #%d as a new %s item: %s" % (number, itype, title))
            continue
        alloc, err = runtime.runtime_module("claims").next_id(project, kind="item")
        if err:
            sys.stderr.write("issues pull: %s\n" % err)
            return 1
        data = {"id": alloc["id"], "title": title, "type": itype, "tier": "2",
                "owner": "qa" if itype == "defect" else "software-engineer",
                "status": "Parked", "created": today, "updated": today,
                "waiting_on": "backlog owner",
                "park_reason": "Imported from GitHub issue #%d: triage into Ready, defer or "
                               "drop" % number,
                "summary": "GitHub issue #%d" % number, "issue": number}
        try:
            saved = shards.save_item(project, data, today=today)
        except ValueError as exc:
            sys.stderr.write("issues pull: %s\n" % exc)
            return 1
        runtime.notify_if_parked(project, None, saved)
        items[saved["id"]] = saved
        mapped[number] = saved["id"]
        entry["item"] = saved["id"]
        result["created"].append(entry)
        lines.append("parked #%d as %s (%s): %s" % (number, saved["id"], itype, title))
    if not lines:
        lines.append("nothing to do: every issue read maps to an item")
    _report(opts, result, lines)
    if not opts.json:
        _render_hint(runtime, project, result["created"] or result["linked"], opts.dry_run)
    return 0


def cmd_push(runtime, project, opts):
    shards = runtime.runtime_module("shards")
    items = shards.merged_items(project)
    candidates = [iid for iid in sorted(items, key=runtime.id_sort_key)
                  if not items[iid].get("issue") and items[iid]["status"] not in CLOSED]
    if not opts.ids and not opts.all:
        sys.stderr.write("issues push: name the items, or pass --all for every open item "
                         "without an issue%s\n" % (":" if candidates else " (there are none)"))
        for iid in candidates:
            sys.stderr.write("  %-10s %-12s %s\n" % (iid, items[iid]["status"], items[iid]["title"]))
        return 2
    unknown = [iid for iid in opts.ids if iid not in items]
    if unknown:
        sys.stderr.write("issues push: no such item: %s\n" % ", ".join(unknown))
        return 2
    targets = list(opts.ids) if opts.ids else candidates
    today = datetime.date.today().isoformat()
    result = {"created": [], "skipped": [], "dry_run": bool(opts.dry_run)}
    lines = []
    for iid in targets:
        it = items[iid]
        if it.get("issue"):
            result["skipped"].append({"item": iid, "issue": it["issue"]})
            lines.append("skipped %s: already linked to #%d" % (iid, it["issue"]))
            continue
        title = clean_title("%s: %s" % (iid, it["title"]))
        body = ("Tracked as %s (%s, Tier %s, %s) in this repository's Nuhut backlog."
                % (iid, it["type"], it["tier"], it["status"]))
        if opts.dry_run:
            result["created"].append({"item": iid, "title": title})
            lines.append("would open an issue for %s: %s" % (iid, title))
            continue
        try:
            out = gh(["issue", "create", "--title=" + title, "--body=" + body], opts.repo)
        except GhError as exc:
            sys.stderr.write("issues push: %s: %s\n" % (iid, exc))
            _report(opts, result, lines)
            return 1
        found = [m for m in (_ISSUE_URL.search(l) for l in out.splitlines()) if m]
        if not found:
            sys.stderr.write("issues push: %s: gh did not print an issue URL; if the issue was "
                             "made, `issues pull` links it by its title\n" % iid)
            _report(opts, result, lines)
            return 1
        number = int(found[-1].group(1))
        shards.save_item(project, dict(it, issue=number, updated=today), today=today)
        result["created"].append({"item": iid, "title": title, "issue": number})
        lines.append("opened #%d for %s" % (number, iid))
    if not lines:
        lines.append("nothing to do: no open item lacks an issue")
    _report(opts, result, lines)
    return 0

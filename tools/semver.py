#!/usr/bin/env python3
"""The kit's next semantic version, worked out from the commits since VERSION last changed.

Commit subjects follow Conventional Commits, as the kit's history already does:
`feat(...)` is a minor bump, a `!` after the type or a `BREAKING CHANGE:` footer is a
major one, and anything else (fix, docs, chore, refactor, ...) is a patch. A subject may
carry several types (`docs,feat(kit): ...`); the largest wins. The release commit this
script writes (`chore(release): vX.Y.Z`) is never counted.

    python3 tools/semver.py next [--json]          the version a merge to main would get
    python3 tools/semver.py next --prerelease      X.Y.Z-dev.N+sha, for a branch build
    python3 tools/semver.py bump [--dry-run]       write VERSION, plugin.json, CHANGELOG.md

Standard library only; runs on Python 3.8.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = ("none", "patch", "minor", "major")
HEADER = re.compile(r"^(?P<types>[a-z]+(?:\s*,\s*[a-z]+)*)(?:\([^)]*\))?(?P<bang>!)?:\s*(?P<desc>.+)$")
RELEASE_SUBJECT = re.compile(r"^chore\(release\):\s*v?[0-9]+\.[0-9]+\.[0-9]+")
VERSION_RE = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)$")


def git(root, *args):
    return subprocess.run(["git"] + list(args), cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout


def current_version(root):
    with open(os.path.join(root, "VERSION"), encoding="utf-8") as h:
        text = h.read().strip()
    if not VERSION_RE.match(text):
        raise SystemExit("VERSION is not major.minor.patch: %r" % text)
    return text


def base_commit(root):
    """The last commit that changed VERSION: everything after it is unreleased."""
    sha = git(root, "log", "-1", "--format=%H", "--", "VERSION").strip()
    if not sha:
        raise SystemExit("VERSION has no git history; commit it first")
    return sha


def commits_since(root, base):
    raw = git(root, "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", base + "..HEAD")
    out = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, subject, body = (rec.split("\x1f") + ["", ""])[:3]
        if RELEASE_SUBJECT.match(subject):
            continue
        out.append({"sha": sha, "subject": subject, "body": body, "level": level_of(subject, body)})
    return out


def level_of(subject, body):
    if re.search(r"^BREAKING[ -]CHANGE:", body or "", re.M):
        return "major"
    m = HEADER.match(subject)
    if not m:
        return "patch"
    if m.group("bang"):
        return "major"
    types = [t.strip() for t in m.group("types").split(",")]
    return "minor" if "feat" in types else "patch"


def bump(version, level):
    major, minor, patch = (int(x) for x in VERSION_RE.match(version).groups())
    if level == "major":
        return "%d.0.0" % (major + 1)
    if level == "minor":
        return "%d.%d.0" % (major, minor + 1)
    if level == "patch":
        return "%d.%d.%d" % (major, minor, patch + 1)
    return version


def plan(root):
    version = current_version(root)
    commits = commits_since(root, base_commit(root))
    level = max((c["level"] for c in commits), key=LEVELS.index, default="none")
    return {"current": version, "level": level, "next": bump(version, level),
            "commits": len(commits), "subjects": [c["subject"] for c in commits]}


def prerelease(root, info):
    sha = git(root, "rev-parse", "--short", "HEAD").strip()
    nxt = info["next"] if info["level"] != "none" else bump(info["current"], "patch")
    return "%s-dev.%d+%s" % (nxt, info["commits"], sha)


def write_changelog(path, version, subjects, today):
    """Turn the Unreleased section into this version's section and open a new one. An
    empty Unreleased section is filled from the commit subjects, so no release is blank."""
    with open(path, encoding="utf-8") as h:
        text = h.read()
    m = re.search(r"^## Unreleased[ \t]*\n", text, re.M)
    heading = "## %s — %s\n" % (version, today)
    if not m:
        first = re.search(r"^## ", text, re.M)
        at = first.start() if first else len(text)
        body = "".join("- %s\n" % s for s in subjects) + "\n"
        text = text[:at] + "## Unreleased\n\n" + heading + "\n" + body + text[at:]
    else:
        nxt = re.search(r"^## ", text[m.end():], re.M)
        end = m.end() + nxt.start() if nxt else len(text)
        section = text[m.end():end]
        if not section.strip():
            section = "\n" + "".join("- %s\n" % s for s in subjects) + "\n"
        text = text[:m.start()] + "## Unreleased\n\n" + heading + section + text[end:]
    with open(path, "w", encoding="utf-8") as h:
        h.write(text)


def write_release(root, info, today=None):
    version = info["next"]
    today = today or datetime.date.today().isoformat()
    with open(os.path.join(root, "VERSION"), "w", encoding="utf-8") as h:
        h.write(version + "\n")
    manifest = os.path.join(root, ".claude-plugin", "plugin.json")
    if os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as h:
            raw = h.read()
        # Replace only the version value, so the file's own formatting survives.
        new, n = re.subn(r'("version"\s*:\s*")[^"]*(")', r"\g<1>%s\g<2>" % version, raw, count=1)
        if n:
            with open(manifest, "w", encoding="utf-8") as h:
                h.write(new)
    changelog = os.path.join(root, "CHANGELOG.md")
    if os.path.isfile(changelog):
        write_changelog(changelog, version, info["subjects"], today)
    return version


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("next", "bump"))
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--prerelease", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    info = plan(args.root)
    if args.command == "next":
        if args.prerelease:
            info["prerelease"] = prerelease(args.root, info)
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(info.get("prerelease") or info["next"])
        return 0
    if info["level"] == "none":
        print("nothing to release: no commits since VERSION last changed (%s)" % info["current"])
        return 0
    if args.dry_run:
        print("would bump %s -> %s (%s, %d commits)" % (info["current"], info["next"], info["level"], info["commits"]))
        return 0
    print(write_release(args.root, info))
    return 0


if __name__ == "__main__":
    sys.exit(main())

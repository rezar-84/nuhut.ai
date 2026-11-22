"""`sdlc.py ext`: install, list, update and remove project extensions (ADR 0003 decision 5).

Project extensions live in `.ai-sdlc/local/extensions/<id>/`. Each install is recorded in
`.ai-sdlc/manifest.json` under its own key, outside the kit's `files`:

    "extensions": {"<id>": {"source", "ref", "commit", "version", "files": {rel: sha256}}}

`install.py --upgrade` copies that key through unchanged and never deletes those files.
Only `ext update` and `ext remove` change them, backing up a file edited by hand first,
and `ext update` is the only path that re-pins the hashes.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

LOCAL_REL = os.path.join(".ai-sdlc", "local", "extensions")
MANIFEST_REL = os.path.join(".ai-sdlc", "manifest.json")
DEFAULT_CATALOG = "https://raw.githubusercontent.com/rezar-84/nuhut.ai/main/catalog.json"
GIT = ["git", "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=user"]
GIT_URL_RES = (
    re.compile(r"^https://[A-Za-z0-9.-]+(:[0-9]+)?/[^\s]+$"),
    re.compile(r"^ssh://([A-Za-z0-9._-]+@)?[A-Za-z0-9.-]+(:[0-9]+)?/[^\s]+$"),
    re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[A-Za-z0-9._~/][^\s]*$"),
)
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
SOURCE_RULE = ("give an https://, ssh:// or git@host:path git URL, or a local directory "
               "(never file://)")


def parse_source(text):
    """("git", url) or ("path", realpath). Raises ValueError for anything else: a leading
    '-', a file:// or other URL scheme, a git transport such as ext::, or a missing
    directory."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("no source: " + SOURCE_RULE)
    if text.startswith("-"):
        raise ValueError("a source may not start with '-': " + SOURCE_RULE)
    if any(rx.match(text) for rx in GIT_URL_RES):
        return "git", text
    if "://" in text or "::" in text or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text):
        raise ValueError("refused %r: %s" % (text.split(":", 1)[0] + ":", SOURCE_RULE))
    path = os.path.realpath(os.path.expanduser(text))
    if not os.path.isdir(path):
        raise ValueError("%s is not a directory: %s" % (text, SOURCE_RULE))
    return "path", path


def _run(argv, cwd=None, timeout=300):
    try:
        proc = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", "%s: %s" % (argv[0], exc.__class__.__name__)
    return (proc.returncode, proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def fetch(kind, where, ref):
    """(ext_dir, commit, cleanup_dir). Raises ValueError with a message for the user."""
    if kind == "path":
        if ref:
            raise ValueError("--ref needs a git URL; a local directory is used as it stands")
        code, top, _ = _run(["git", "-C", where, "rev-parse", "--show-toplevel"])
        commit = None
        if code == 0 and os.path.realpath(top.strip()) == where:
            code, out, _ = _run(["git", "-C", where, "rev-parse", "HEAD"])
            commit = out.strip() if code == 0 else None
        return where, commit, None
    if ref is not None and not REF_RE.match(ref):
        raise ValueError("--ref %r is not a branch, tag or commit name" % ref)
    tmp = tempfile.mkdtemp(prefix="nuhut-ext-")
    dest = os.path.join(tmp, "src")
    code, _, err = _run(GIT + ["clone", "--depth", "1", "--no-recurse-submodules", "--",
                               where, dest])
    if code != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise ValueError("git clone failed: %s" % (err.strip().splitlines() or ["?"])[-1])
    if ref:
        code, _, err = _run(GIT + ["-C", dest, "fetch", "--depth", "1", "origin", ref])
        if code == 0:
            code, _, err = _run(GIT + ["-C", dest, "checkout", "-q", "--detach", "FETCH_HEAD"])
        if code != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ValueError("cannot check out --ref %s: %s"
                             % (ref, (err.strip().splitlines() or ["?"])[-1]))
    _, out, _ = _run(["git", "-C", dest, "rev-parse", "HEAD"])
    return dest, out.strip() or None, tmp


def inspect(reg_mod, ext_dir, version):
    """(manifest or None, [(field, message)] errors, warnings) for an extension on disk."""
    path = os.path.join(ext_dir, reg_mod.MANIFEST)
    if not os.path.isfile(path):
        return None, [("(file)", "missing %s" % reg_mod.MANIFEST)], []
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (ValueError, UnicodeDecodeError) as exc:
        return None, [("(file)", "not valid JSON: %s" % exc)], []
    errors, warnings = reg_mod.validate(manifest)
    if errors:
        return manifest, errors, warnings
    errors = reg_mod.check_tree(ext_dir, manifest)
    if manifest.get("nuhut") == "builtin":
        errors.append(("nuhut", "\"builtin\" is reserved for the kit's own extensions; "
                       "give a version range"))
    elif version:
        try:
            if not reg_mod.version_ok(manifest.get("nuhut"), version):
                errors.append(("nuhut", "needs Nuhut %s; this is %s"
                               % (manifest.get("nuhut"), version)))
        except ValueError as exc:
            errors.append(("nuhut", str(exc)))
    return manifest, errors, warnings


def collect(ext_dir):
    """{rel: bytes} for every file in the extension, .git left out. Call after inspect():
    check_tree has already refused anything that resolves outside <ext_dir>."""
    out = {}
    for folder, dirs, names in os.walk(ext_dir):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(names):
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, ext_dir).replace(os.sep, "/")
            with open(full, "rb") as handle:
                out[rel] = handle.read()
    return out


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def read_manifest(root):
    try:
        with open(os.path.join(root, MANIFEST_REL), encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_manifest(root, data):
    path = os.path.join(root, MANIFEST_REL)
    fd, tmp = tempfile.mkstemp(prefix=".manifest-", dir=os.path.dirname(path))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def summary(reg_mod, manifest, allowed):
    """Lines describing what an extension brings, executable entry points first."""
    ext_id = manifest["id"]
    provides = manifest.get("provides") or {}
    lines = ["%s %s  %s" % (ext_id, manifest.get("version"), manifest.get("description") or "")]
    data = []
    for kind in ("harnesses", "presets", "overlays"):
        if provides.get(kind):
            data.append("%d %s" % (len(provides[kind]), kind))
    for kind in reg_mod.DIR_PROVIDES:
        if provides.get(kind):
            data.append("%s %s/" % (kind, provides[kind].rstrip("/")))
    lines.append("  data:        %s" % (", ".join(data) or "none"))
    if manifest.get("overrides"):
        lines.append("  overrides:   built-in %s (needs Extensions allowed)" % manifest["overrides"])
    entries = reg_mod.executable_entries(manifest)
    if not entries:
        lines.append("  executable:  none")
        return lines
    lines.append("  executable:")
    for field, what in entries:
        lines.append("    %-34s %s" % (field, what))
    if ext_id in allowed:
        lines.append("code is enabled: the charter row Extensions allowed lists `%s`" % ext_id)
    else:
        lines.append("code is disabled until the charter row Extensions allowed lists `%s`: "
                     "run `sdlc.py config --allow-extension %s`" % (ext_id, ext_id))
    return lines


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def edited_files(root, ext_id, pinned):
    """Files of an installed extension that differ from their pinned hash or are gone,
    plus files nobody pinned."""
    base = os.path.join(root, LOCAL_REL, ext_id)
    out = []
    for rel, digest in sorted(pinned.items()):
        try:
            with open(os.path.join(base, rel), "rb") as handle:
                if _sha(handle.read()) != digest:
                    out.append(rel)
        except (IOError, OSError):
            out.append(rel)
    if os.path.isdir(base):
        for rel in sorted(collect(base)):
            if rel not in pinned:
                out.append(rel)
    return out


def back_up(root, ext_id, rels):
    """Copy <rels> of an installed extension to .ai-sdlc/backups/; return the backup dir."""
    base = os.path.join(root, LOCAL_REL, ext_id)
    present = [r for r in rels if os.path.isfile(os.path.join(base, r))]
    if not present:
        return None
    dest = os.path.join(root, ".ai-sdlc", "backups", "extensions", "%s-%s" % (ext_id, _stamp()))
    for rel in present:
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(base, rel), target)
    return os.path.relpath(dest, root)


def place(root, ext_id, files):
    """Write <files> as .ai-sdlc/local/extensions/<ext_id>/, replacing what is there."""
    parent = os.path.join(root, LOCAL_REL)
    os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".%s-new-" % ext_id, dir=parent)
    for rel, data in files.items():
        target = os.path.join(stage, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
    dest = os.path.join(parent, ext_id)
    old = None
    if os.path.exists(dest):
        old = tempfile.mkdtemp(prefix=".%s-old-" % ext_id, dir=parent)
        os.rmdir(old)
        os.rename(dest, old)
    os.rename(stage, dest)
    if old:
        shutil.rmtree(old, ignore_errors=True)


def _overlay_note(project, manifest):
    if (manifest.get("provides") or {}).get("overlays"):
        return ("note: template overlays apply to %s/templates/ at the next "
                "`install.sh <this project> --upgrade`" % project.docs)
    return None


def _fetch_checked(rt, reg_mod, project, source, ref):
    """(manifest, files, commit) for <source>, or raises ValueError with the problems."""
    kind, where = parse_source(source)
    ext_dir, commit, cleanup = fetch(kind, where, ref)
    try:
        manifest, errors, _ = inspect(reg_mod, ext_dir, (project.manifest or {}).get("kit_version"))
        if errors:
            raise ValueError("refused:\n" + "\n".join("  %s: %s" % e for e in errors))
        return manifest, collect(ext_dir), commit
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)


def cmd_add(rt, reg_mod, project, opts):
    data = read_manifest(project.root)
    if data is None:
        return _fail("ext add: %s is missing; install the kit here first" % MANIFEST_REL)
    try:
        manifest, files, commit = _fetch_checked(rt, reg_mod, project, opts.target, opts.ref)
    except ValueError as exc:
        return _fail("ext add: %s" % exc)
    ext_id = manifest["id"]
    reg, _ = rt.load_registry(project)
    builtin_ids = set(i for i, e in (reg.extensions if reg else {}).items()
                      if e["source"] == reg_mod.BUILTIN)
    if ext_id in builtin_ids:
        return _fail("ext add: %r is a built-in extension id; give yours another id and "
                     "\"overrides\": \"%s\"" % (ext_id, ext_id))
    pins = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
    if ext_id in pins or os.path.exists(os.path.join(project.root, LOCAL_REL, ext_id)):
        return _fail("ext add: %s is already installed; use `sdlc.py ext update %s` or "
                     "`ext remove %s`" % (ext_id, ext_id, ext_id))
    allowed = rt.allowed_extensions(project)
    print("\n".join(summary(reg_mod, manifest, allowed)))
    place(project.root, ext_id, files)
    pins = dict(pins)
    pins[ext_id] = {"source": parse_source(opts.target)[1], "ref": opts.ref, "commit": commit, "version": manifest.get("version"),
                    "files": dict((rel, _sha(b)) for rel, b in sorted(files.items()))}
    data["extensions"] = pins
    write_manifest(project.root, data)
    print("installed %s %s in %s/%s/ (%d files%s)" % (
        ext_id, manifest.get("version"), LOCAL_REL.replace(os.sep, "/"), ext_id, len(files),
        ", commit %s" % commit[:12] if commit else ""))
    note = _overlay_note(project, manifest)
    if note:
        print(note)
    return 0


def cmd_update(rt, reg_mod, project, opts):
    data = read_manifest(project.root) or {}
    pins = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
    ext_id = opts.target
    rec = pins.get(ext_id)
    if not rec:
        return _fail("ext update: %s was not installed with `sdlc.py ext add`" % ext_id)
    ref = opts.ref if opts.ref is not None else rec.get("ref")
    try:
        manifest, files, commit = _fetch_checked(rt, reg_mod, project, rec.get("source"), ref)
    except ValueError as exc:
        return _fail("ext update: %s" % exc)
    if manifest["id"] != ext_id:
        return _fail("ext update: the source now holds extension %r, not %r"
                     % (manifest["id"], ext_id))
    old = rec.get("files") or {}
    new = dict((rel, _sha(b)) for rel, b in sorted(files.items()))
    changed = sorted(r for r in set(old) | set(new) if old.get(r) != new.get(r))
    edited = edited_files(project.root, ext_id, old)
    print("%s: commit %s -> %s, version %s -> %s" % (
        ext_id, (rec.get("commit") or "none")[:12], (commit or "none")[:12],
        rec.get("version"), manifest.get("version")))
    for rel in changed:
        print("  %-8s %s" % ("added" if rel not in old else "removed" if rel not in new
                             else "changed", rel))
    if not changed and not edited:
        print("already up to date")
        return 0
    print("\n".join(summary(reg_mod, manifest, rt.allowed_extensions(project))))
    if opts.dry_run:
        print("dry run: nothing written")
        return 0
    backup = back_up(project.root, ext_id, edited)
    if backup:
        print("backup   %s (%d file(s) edited here: %s)" % (backup, len(edited), ", ".join(edited)))
    place(project.root, ext_id, files)
    pins = dict(pins)
    pins[ext_id] = dict(rec, ref=ref, commit=commit, version=manifest.get("version"), files=new)
    data["extensions"] = pins
    write_manifest(project.root, data)
    print("updated %s and re-pinned %d file hash(es)" % (ext_id, len(new)))
    note = _overlay_note(project, manifest)
    if note:
        print(note)
    return 0


def cmd_remove(rt, reg_mod, project, opts):
    data = read_manifest(project.root) or {}
    pins = data.get("extensions") if isinstance(data.get("extensions"), dict) else {}
    ext_id = opts.target
    base = os.path.join(project.root, LOCAL_REL, ext_id)
    if ext_id not in pins:
        if os.path.isdir(base):
            return _fail("ext remove: %s/%s was not installed with `ext add`; it is yours, "
                         "so delete it by hand" % (LOCAL_REL.replace(os.sep, "/"), ext_id))
        return _fail("ext remove: %s is not installed" % ext_id)
    edited = edited_files(project.root, ext_id, pins[ext_id].get("files") or {})
    backup = back_up(project.root, ext_id, edited)
    if backup:
        print("backup   %s (%d file(s) edited here: %s)" % (backup, len(edited), ", ".join(edited)))
    if os.path.isdir(base):
        shutil.rmtree(base)
    pins = dict(pins)
    pins.pop(ext_id)
    data["extensions"] = pins
    write_manifest(project.root, data)
    print("removed %s" % ext_id)
    if ext_id in rt.allowed_extensions(project):
        print("note: the charter row Extensions allowed still lists `%s`; remove it there" % ext_id)
    return 0


def cmd_list(rt, reg_mod, project, opts):
    reg, why = rt.load_registry(project)
    if reg is None:
        return _fail("ext list: %s" % why)
    rows = []
    for ext_id in sorted(set(reg.extensions) | set(reg.broken)):
        ext = reg.extensions.get(ext_id)
        pin = reg.pins.get(ext_id) or {}
        rows.append({
            "id": ext_id,
            "version": ext["manifest"].get("version") if ext else pin.get("version") or "?",
            "source": ext["source"] if ext else "project",
            "status": reg.status(ext_id),
            "commit": pin.get("commit") or "",
            "origin": pin.get("source") or "",
            "error": None if ext else "%s: %s" % (reg.broken[ext_id]["field"],
                                                   reg.broken[ext_id]["message"]),
        })
    labels, execs = [], []
    for ext_id in sorted(reg.extensions):
        ext = reg.extensions[ext_id]
        provides = ext["manifest"].get("provides") or {}
        for kind in ("skills", "roles"):
            if provides.get(kind):
                labels.append({"kind": kind, "path": provides[kind], "extension": ext_id,
                               "source": ext["source"]})
        if ext["source"] != reg_mod.BUILTIN:
            for field, what in reg_mod.executable_entries(ext["manifest"]):
                execs.append({"extension": ext_id, "field": field, "what": what,
                              "status": reg.status(ext_id)})
    if getattr(opts, "json", False):
        print(json.dumps({"extensions": rows, "prompt_content": labels,
                          "executables": execs}, indent=2))
        return 0
    print("%-18s %-9s %-9s %-15s %s" % ("ID", "VERSION", "SOURCE", "STATUS", "COMMIT"))
    for r in rows:
        print("%-18s %-9s %-9s %-15s %s" % (r["id"], r["version"], r["source"], r["status"],
                                            r["commit"][:12] or "-"))
        if r["error"]:
            print("  %s" % r["error"])
    if labels:
        print("")
        print("Skills and roles reach agent context; each is labelled with its extension:")
        for lab in labels:
            print("  %-7s %s  (from %s, %s)" % (lab["kind"], lab["path"], lab["extension"],
                                               lab["source"]))
    if execs:
        print("")
        print("Executable contributions from non-built-in extensions:")
        for x in execs:
            print("  %-16s %-34s %s  [%s]" % (x["extension"], x["field"], x["what"], x["status"]))
    return 0


def load_catalog(source):
    """The catalog entries from <source>: an https URL (through net.py) or a file path."""
    if source.startswith("https://"):
        net = _sibling("net")
        body = net.fetch(source).decode("utf-8", "replace")
    elif "://" in source:
        raise ValueError("a catalog is an https:// URL or a file path")
    else:
        with open(os.path.expanduser(source), encoding="utf-8") as handle:
            body = handle.read()
    data = json.loads(body)
    if isinstance(data, dict):
        data = data.get("extensions")
    if not isinstance(data, list):
        raise ValueError("expected a JSON list of {id, url, ref, description}")
    return data


def check_entry(reg_mod, entry, version):
    """None when a catalog entry is usable, else why not."""
    if not isinstance(entry, dict) or not reg_mod.ID_RE.match(str(entry.get("id") or "")):
        return "expected {id, url, ref, description} with a valid id"
    try:
        if parse_source(entry.get("url"))[0] != "git":
            return "the url is not a git URL"
    except ValueError as exc:
        return str(exc)
    ref = entry.get("ref")
    if ref is not None and not REF_RE.match(str(ref)):
        return "ref %r is not a branch, tag or commit name" % ref
    spec = entry.get("nuhut")
    if spec and spec != "builtin" and version:
        try:
            if not reg_mod.version_ok(spec, version):
                return "needs Nuhut %s; this is %s" % (spec, version)
        except ValueError as exc:
            return "nuhut: %s" % exc
    return None


def catalog_source():
    env = os.environ.get("NUHUT_CATALOG_URL", "").strip()
    if env:
        return env
    kit = _sibling("registry").default_kit()
    if kit and os.path.isfile(os.path.join(kit, "catalog.json")):
        return os.path.join(kit, "catalog.json")
    return DEFAULT_CATALOG


def cmd_search(rt, reg_mod, project, opts):
    source = catalog_source()
    try:
        entries = load_catalog(source)
    except (ValueError, IOError, OSError) as exc:
        return _fail("ext search: %s" % exc)
    term = (opts.target or "").lower()
    version = (project.manifest or {}).get("kit_version")
    shown = 0
    for entry in entries:
        text = " ".join(str(entry.get(k) or "") for k in ("id", "description")).lower() \
            if isinstance(entry, dict) else ""
        if term and term not in text:
            continue
        problem = check_entry(reg_mod, entry, version)
        shown += 1
        if problem:
            print("%-20s refused: %s" % (str(entry.get("id") if isinstance(entry, dict)
                                             else entry)[:20], problem))
            continue
        print("%-20s %-12s %s" % (entry["id"], entry.get("ref") or "-",
                                  entry.get("description") or ""))
        print("  sdlc.py ext add %s%s" % (entry["url"], " --ref %s" % entry["ref"]
                                          if entry.get("ref") else ""))
    if not shown:
        print("no catalog entry matches%s" % (" %r" % opts.target if opts.target else ""))
    return 0


def cmd_validate(rt, reg_mod, project, opts):
    path = os.path.realpath(opts.target or ".")
    if os.path.isfile(path):
        path = os.path.dirname(path)
    manifest, errors, warnings = inspect(reg_mod, path, (project.manifest or {}).get("kit_version"))
    for field, message in errors:
        print("error  %s: %s" % (field, message))
    for field, message in warnings:
        print("warn   %s: %s" % (field, message))
    if errors:
        return 1
    print("ok     %s %s is a valid extension" % (manifest["id"], manifest.get("version")))
    print("\n".join(summary(reg_mod, manifest, rt.allowed_extensions(project))))
    return 0


def _sibling(name):
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return __import__(name)


def _fail(message):
    sys.stderr.write(message + "\n")
    return 1


ACTIONS = {"list": cmd_list, "add": cmd_add, "update": cmd_update, "remove": cmd_remove,
           "search": cmd_search, "validate": cmd_validate}
NEEDS_TARGET = ("add", "update", "remove", "validate")


def main(rt, project, opts):
    if opts.action in NEEDS_TARGET and not opts.target:
        return _fail("ext %s: give %s" % (opts.action, "a source" if opts.action == "add"
                                          else "a path" if opts.action == "validate"
                                          else "an extension id"))
    return ACTIONS[opts.action](rt, _sibling("registry"), project, opts)

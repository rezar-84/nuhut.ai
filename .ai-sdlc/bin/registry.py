"""Extension registry: agent tools, agent CLIs, check stages and presets as data.

An extension is a directory holding `nuhut-extension.json` (ADR 0003). The registry looks
for them, highest priority first, in:

    <root>/.ai-sdlc/local/extensions/<id>/   project and third-party extensions
    <root>/.ai-sdlc/extensions/<id>/         the installed built-ins (kit-managed)
    <kit>/optional/extensions/<id>/          only when running from the kit checkout

Built-in status comes from the location, never from the manifest. A project extension
may add harness and preset records; it replaces a built-in record only when its manifest
says `"overrides": "<built-in id>"`, and then only records of that built-in, by id.
Executable contributions (agent argv, check commands) from project extensions are
refused until NUHT-018 adds the Extensions allowed gate.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import json
import os
import re
import sys

SCHEMA = 1
MANIFEST = "nuhut-extension.json"
BUILTIN = "built-in"
PROJECT = "project"
OVERRIDE = "override"

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,2}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.+-]+)?$")
CLAUSE_RE = re.compile(r"^(>=|<|==)\s*([0-9]+(?:\.[0-9]+){0,2})$")
TOP_KEYS = ("schema", "id", "version", "nuhut", "description", "overrides", "provides")
LIST_PROVIDES = ("harnesses", "agents", "checks", "presets", "hook_rules", "doctor",
                 "overlays", "commands")
DIR_PROVIDES = ("skills", "roles", "templates")
DIALECTS = ("claude", "gemini", "cursor")
# Executable contributions: these reach a subprocess or the interpreter.
EXECUTABLE = ("agents", "checks", "hook_rules", "doctor", "commands", "lifecycle")

_HERE = os.path.dirname(os.path.abspath(__file__))
_WARNED = set()
_CACHE = {}


def default_kit():
    """The kit checkout this file runs from, or None in an installed project."""
    parent = os.path.dirname(_HERE)
    if (os.path.basename(_HERE) == "runtime" and os.path.basename(parent) == "optional"
            and os.path.isdir(os.path.join(parent, "extensions"))):
        return os.path.dirname(parent)
    return None


def parse_version(text):
    m = re.match(r"^([0-9]+(?:\.[0-9]+){0,2})", str(text or "").strip())
    if not m:
        return None
    parts = [int(p) for p in m.group(1).split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def version_ok(spec, version):
    """True when <version> satisfies <spec>: a comma-separated list of `>=`, `<` and
    `==` clauses, or the literal "builtin", which always matches. Raises ValueError on a
    malformed spec or an unknown running version."""
    if spec == "builtin":
        return True
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("expected a version range such as \">=6.0.0,<7.0.0\"")
    have = parse_version(version)
    if have is None:
        raise ValueError("the running Nuhut version is unknown")
    for clause in spec.split(","):
        m = CLAUSE_RE.match(clause.strip())
        if not m:
            raise ValueError("bad clause %r: use >=, < or == and a version" % clause.strip())
        want = parse_version(m.group(2))
        op = m.group(1)
        if (op == ">=" and have < want) or (op == "<" and have >= want) or (
                op == "==" and have != want):
            return False
    return True


def _is_str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _safe_rel(value):
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        return False
    parts = value.replace("\\", "/").split("/")
    return ".." not in parts and not re.match(r"^[A-Za-z]:", value)


def _check_id(errors, field, value):
    if not isinstance(value, str) or not ID_RE.match(value):
        errors.append((field, "expected an id of lowercase letters, digits and '-'"))
        return False
    return True


def _check_paths(errors, field, value, allow_null=False):
    if value is None and allow_null:
        return
    if not _is_str_list(value):
        errors.append((field, "expected list of strings"))
        return
    for n, rel in enumerate(value):
        if not _safe_rel(rel):
            errors.append(("%s[%d]" % (field, n), "expected a relative path with no '..'"))


def _check_harness(errors, field, rec):
    title = rec.get("title")
    if not isinstance(title, str) or not title:
        errors.append((field + ".title", "expected a non-empty string"))
    pointer = rec.get("pointer")
    if pointer is not None:
        if not isinstance(pointer, list):
            errors.append((field + ".pointer", "expected null or a list of {path, header}"))
        else:
            for n, ptr in enumerate(pointer):
                where = "%s.pointer[%d]" % (field, n)
                if not isinstance(ptr, dict) or not _safe_rel(ptr.get("path")):
                    errors.append((where + ".path", "expected a relative path with no '..'"))
                elif not isinstance(ptr.get("header", ""), str):
                    errors.append((where + ".header", "expected a string"))
    if not isinstance(rec.get("native", False), bool):
        errors.append((field + ".native", "expected true or false"))
    _check_paths(errors, field + ".markers", rec.get("markers", []))
    skills_dir = rec.get("skills_dir")
    if skills_dir is not None and not _safe_rel(skills_dir):
        errors.append((field + ".skills_dir", "expected null or a relative path"))
    order = rec.get("order")
    if order is not None and (isinstance(order, bool) or not isinstance(order, int)):
        errors.append((field + ".order", "expected an integer"))
    hooks = rec.get("hooks", {})
    if not isinstance(hooks, dict):
        errors.append((field + ".hooks", "expected an object"))
    else:
        if hooks.get("dialect") is not None and hooks.get("dialect") not in DIALECTS:
            errors.append((field + ".hooks.dialect", "expected null or one of %s"
                           % ", ".join(DIALECTS)))
        settings = hooks.get("settings")
        if settings is not None and not _safe_rel(settings):
            errors.append((field + ".hooks.settings", "expected null or a relative path"))
        events = hooks.get("events", {})
        if not isinstance(events, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in events.items()):
            errors.append((field + ".hooks.events", "expected an object of strings"))
    lens = rec.get("lens", {})
    if not isinstance(lens, dict):
        errors.append((field + ".lens", "expected an object"))
    else:
        _check_paths(errors, field + ".lens.dirs", lens.get("dirs", []))
        _check_paths(errors, field + ".lens.mcp", lens.get("mcp", []))


def _check_agent(errors, field, rec):
    if not isinstance(rec.get("family", ""), str):
        errors.append((field + ".family", "expected a string"))
    for key in ("review", "build"):
        argv = rec.get(key)
        if argv is not None and (not _is_str_list(argv) or not argv
                                 or not argv[0] or argv[0].startswith("-")):
            errors.append(("%s.%s" % (field, key), "expected list of strings"))
    flag = rec.get("model_flag")
    if flag is not None and not isinstance(flag, str):
        errors.append((field + ".model_flag", "expected null or a string"))


def _check_preset(errors, field, rec):
    if not isinstance(rec.get("help", ""), str):
        errors.append((field + ".help", "expected a string"))
    settings = rec.get("settings")
    if not isinstance(settings, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in settings.items()):
        errors.append((field + ".settings", "expected an object of strings"))


def _check_check(errors, field, rec):
    command = rec.get("command")
    if command is not None and not isinstance(command, str):
        errors.append((field + ".command", "expected a string"))


RECORD_CHECKS = {"harnesses": _check_harness, "agents": _check_agent,
                 "presets": _check_preset, "checks": _check_check}


def validate(manifest):
    """Check a manifest against schema 1. Returns (errors, warnings), each a list of
    (field, message). An unknown key under `provides` is a warning, never an error."""
    errors, warnings = [], []
    if not isinstance(manifest, dict):
        return [("(manifest)", "expected a JSON object")], warnings
    schema = manifest.get("schema")
    if isinstance(schema, bool) or not isinstance(schema, int):
        errors.append(("schema", "expected an integer"))
    elif schema > SCHEMA:
        errors.append(("schema", "schema %d: this extension needs a newer Nuhut: upgrade "
                       "Nuhut" % schema))
        return errors, warnings
    elif schema < 1:
        errors.append(("schema", "expected 1"))
    _check_id(errors, "id", manifest.get("id"))
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        errors.append(("version", "expected a version such as \"1.0.0\""))
    nuhut = manifest.get("nuhut")
    if nuhut != "builtin":
        try:
            version_ok(nuhut, "0.0.0")
        except ValueError as exc:
            errors.append(("nuhut", str(exc)))
    if not isinstance(manifest.get("description", ""), str):
        errors.append(("description", "expected a string"))
    overrides = manifest.get("overrides")
    if overrides is not None:
        _check_id(errors, "overrides", overrides)
    for key in sorted(manifest):
        if key not in TOP_KEYS:
            warnings.append((key, "unknown key, ignored"))
    provides = manifest.get("provides", {})
    if not isinstance(provides, dict):
        errors.append(("provides", "expected an object"))
        return errors, warnings
    for key in sorted(provides):
        value = provides[key]
        field = "provides." + key
        if key in LIST_PROVIDES:
            if not isinstance(value, list):
                errors.append((field, "expected a list"))
                continue
            seen = set()
            for n, rec in enumerate(value):
                where = "%s[%d]" % (field, n)
                if not isinstance(rec, dict):
                    errors.append((where, "expected an object"))
                    continue
                if key in RECORD_CHECKS:
                    if _check_id(errors, where + ".id", rec.get("id")):
                        if rec["id"] in seen:
                            errors.append((where + ".id", "duplicate id %r" % rec["id"]))
                        seen.add(rec["id"])
                    RECORD_CHECKS[key](errors, where, rec)
        elif key in DIR_PROVIDES:
            if value is not None and not _safe_rel(value):
                errors.append((field, "expected a relative path with no '..'"))
        elif key == "lifecycle":
            if not isinstance(value, dict) or not all(_safe_rel(v) for v in value.values()):
                errors.append((field, "expected an object of relative paths"))
        else:
            warnings.append((field, "unknown key, ignored"))
    return errors, warnings


class Registry(object):
    """The loaded extensions. `missing` is True when no built-in location exists at all,
    in which case callers use their v5 tables."""

    def __init__(self, root, kit):
        self.root = root
        self.kit = kit
        self.missing = False
        self.extensions = {}     # id -> {"id", "path", "source", "manifest"}
        self.errors = []         # {"id", "path", "field", "message"}
        self.warnings = []
        self.notes = []          # {"id", "path", "message"}
        self.broken = {}         # id -> first error
        self._records = {}

    def _rel(self, path):
        for base in (self.root, self.kit):
            if base:
                try:
                    rel = os.path.relpath(path, base)
                except ValueError:
                    continue
                if not rel.startswith(".."):
                    return rel
        return path

    def _merge(self):
        kinds = ("harnesses", "agents", "checks", "presets")
        merged = dict((k, {}) for k in kinds)
        owner = dict((k, {}) for k in kinds)
        builtins = [self.extensions[i] for i in sorted(self.extensions)
                    if self.extensions[i]["source"] == BUILTIN]
        projects = [self.extensions[i] for i in sorted(self.extensions)
                    if self.extensions[i]["source"] != BUILTIN]
        for ext in builtins:
            for kind in kinds:
                for rec in ext["manifest"].get("provides", {}).get(kind, []) or []:
                    if rec["id"] in merged[kind]:
                        self.notes.append({"id": ext["id"], "path": ext["rel"], "message":
                                           "%s record %r is already provided by built-in %s; "
                                           "ignored" % (kind, rec["id"], owner[kind][rec["id"]])})
                        continue
                    merged[kind][rec["id"]] = dict(rec, source=BUILTIN, extension=ext["id"])
                    owner[kind][rec["id"]] = ext["id"]
        for ext in projects:
            target = ext["manifest"].get("overrides")
            if target and (target not in self.extensions
                           or self.extensions[target]["source"] != BUILTIN):
                self.notes.append({"id": ext["id"], "path": ext["rel"], "message":
                                   "overrides %r, which is not a loaded built-in extension; "
                                   "its overriding records are ignored" % target})
                target = None
            for kind in kinds:
                for rec in ext["manifest"].get("provides", {}).get(kind, []) or []:
                    if kind in EXECUTABLE:
                        self.notes.append({"id": ext["id"], "path": ext["rel"], "message":
                                           "%s record %r refused: executable contributions "
                                           "from project extensions need NUHT-018"
                                           % (kind, rec["id"])})
                        continue
                    if rec["id"] in merged[kind]:
                        if target and owner[kind][rec["id"]] == target:
                            merged[kind][rec["id"]] = dict(rec, source=OVERRIDE,
                                                           extension=ext["id"])
                            owner[kind][rec["id"]] = ext["id"]
                        else:
                            self.notes.append({"id": ext["id"], "path": ext["rel"], "message":
                                               "%s record %r is already provided by %s; ignored "
                                               "(a project extension replaces a built-in record "
                                               "only with \"overrides\": \"%s\")"
                                               % (kind, rec["id"], owner[kind][rec["id"]],
                                                  owner[kind][rec["id"]])})
                        continue
                    merged[kind][rec["id"]] = dict(rec, source=PROJECT, extension=ext["id"])
                    owner[kind][rec["id"]] = ext["id"]
            for kind in EXECUTABLE:
                if kind not in kinds and ext["manifest"].get("provides", {}).get(kind):
                    self.notes.append({"id": ext["id"], "path": ext["rel"], "message":
                                       "%s refused: executable contributions from project "
                                       "extensions need NUHT-018" % kind})
        self._records = merged

    def _sorted(self, kind):
        recs = self._records.get(kind, {})
        return dict((k, recs[k]) for k in sorted(
            recs, key=lambda k: (recs[k].get("order", 1000000), k)))

    def harnesses(self):
        return self._sorted("harnesses")

    def agents(self):
        return self._sorted("agents")

    def checks(self):
        return self._sorted("checks")

    def presets(self):
        return self._sorted("presets")


def _read_manifest(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), None
    except ValueError as exc:
        return None, ("(file)", "not valid JSON: %s" % exc)
    except (IOError, OSError) as exc:
        return None, ("(file)", "unreadable: %s" % exc.__class__.__name__)


def load(root=None, kit=True, version=None, warn=True, use_cache=True):
    """Load every extension for project <root>. kit=True finds the kit checkout this file
    runs from; pass a path or None to choose. <version> is the running Nuhut version,
    used only for non-built-in ranges."""
    if kit is True:
        kit = default_kit()
    root = os.path.realpath(root) if root else None
    kit = os.path.realpath(kit) if kit else None
    key = (root, kit, version)
    if use_cache and key in _CACHE:
        return _CACHE[key]
    if version is None and kit and os.path.isfile(os.path.join(kit, "VERSION")):
        try:
            with open(os.path.join(kit, "VERSION"), encoding="utf-8") as handle:
                version = handle.read().strip()
        except (IOError, OSError):
            version = None
    reg = Registry(root, kit)
    locations = []
    if root:
        locations.append((os.path.join(root, ".ai-sdlc", "local", "extensions"), PROJECT))
        locations.append((os.path.join(root, ".ai-sdlc", "extensions"), BUILTIN))
    if kit:
        locations.append((os.path.join(kit, "optional", "extensions"), BUILTIN))
    reg.missing = not any(os.path.isdir(d) for d, src in locations if src == BUILTIN)
    seen = set()
    for folder, source in locations:
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            ext_dir = os.path.join(folder, name)
            path = os.path.join(ext_dir, MANIFEST)
            if not os.path.isdir(ext_dir) or name.startswith("."):
                continue
            if name in seen:
                continue           # a higher-priority location already has this id
            seen.add(name)
            rel = reg._rel(path)

            def fail(field, message, name=name, rel=rel):
                err = {"id": name, "path": rel, "field": field, "message": message}
                reg.errors.append(err)
                reg.broken.setdefault(name, err)
                if warn and (rel, field) not in _WARNED:
                    _WARNED.add((rel, field))
                    sys.stderr.write("nuhut: extension %s: %s: %s\n" % (rel, field, message))

            if not os.path.isfile(path):
                fail("(file)", "missing %s" % MANIFEST)
                continue
            manifest, read_error = _read_manifest(path)
            if read_error:
                fail(*read_error)
                continue
            errors, warnings = validate(manifest)
            for field, message in warnings:
                reg.warnings.append({"id": name, "path": rel, "field": field,
                                     "message": message})
                if warn and (rel, field) not in _WARNED:
                    _WARNED.add((rel, field))
                    sys.stderr.write("nuhut: extension %s: %s: %s\n" % (rel, field, message))
            if not errors and manifest.get("id") != name:
                errors.append(("id", "%r does not match its directory name %r"
                               % (manifest.get("id"), name)))
            if not errors and source != BUILTIN and manifest.get("nuhut") == "builtin":
                errors.append(("nuhut", "\"builtin\" is reserved for the kit's own "
                               "extensions; give a version range"))
            if not errors and source != BUILTIN:
                try:
                    if not version_ok(manifest.get("nuhut"), version):
                        errors.append(("nuhut", "needs Nuhut %s; this is %s"
                                       % (manifest.get("nuhut"), version)))
                except ValueError as exc:
                    errors.append(("nuhut", str(exc)))
            if errors:
                for field, message in errors:
                    fail(field, message)
                continue
            reg.extensions[name] = {"id": name, "path": path, "rel": rel,
                                    "source": source, "manifest": manifest}
    reg._merge()
    if use_cache:
        _CACHE[key] = reg
    return reg


def install_tables(reg):
    """The installer's v5 HARNESS_* and PRESET* tables, built from the registry."""
    harnesses = reg.harnesses()
    pointers, aliases, titles, order, markers, native = [], {}, {}, [], {}, []
    for hid, rec in harnesses.items():
        if rec.get("native"):
            native.append(hid)
            continue
        ptrs = rec.get("pointer") or []
        aliases[hid] = tuple(p["path"] for p in ptrs)
        pointers.extend((p["path"], p.get("header", "")) for p in ptrs)
        titles[hid] = rec["title"]
        order.append(hid)
        if rec.get("markers"):
            markers[hid] = tuple(rec["markers"])
    presets = reg.presets()
    return {
        "HARNESS_POINTERS": tuple(pointers),
        "HARNESS_NATIVE": tuple(native),
        "HARNESS_ALIASES": aliases,
        "HARNESS_TITLES": titles,
        "HARNESS_ORDER": tuple(order),
        "HARNESS_MARKERS": markers,
        "PRESETS": dict((k, dict(v["settings"])) for k, v in presets.items()),
        "PRESET_HELP": dict((k, v.get("help", "")) for k, v in presets.items()),
    }


def agent_table(reg, kind):
    """{id: (argv, model_flag)} for kind "review" or "build", the shape of the v5
    REVIEW_HARNESSES and BUILD_HARNESSES tables."""
    out = {}
    for aid, rec in reg.agents().items():
        if rec.get(kind):
            out[aid] = (list(rec[kind]), rec.get("model_flag") or "--model")
    return out

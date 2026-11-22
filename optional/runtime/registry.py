"""Extension registry: agent tools, agent CLIs, check stages and presets as data.

An extension is a directory holding `nuhut-extension.json` (ADR 0003). The registry looks
for them, highest priority first, in:

    <root>/.ai-sdlc/local/extensions/<id>/   project and third-party extensions
    <root>/.ai-sdlc/extensions/<id>/         the installed built-ins (kit-managed)
    <kit>/optional/extensions/<id>/          only when running from the kit checkout

Built-in status comes from the location, never from the manifest. A project extension
may add harness and preset records. It replaces a built-in record only when its manifest
says `"overrides": "<built-in id>"` and the charter's Extensions allowed row lists it, and
then only records of that built-in, by id. Executable contributions (agent argv, check
commands, hook rules, doctor checks, commands, lifecycle hooks) from a project extension
load only when Extensions allowed lists its id, as that row stands on the default branch,
and only while its files match the sha256 pinned by `sdlc.py ext add` (NUHT-018).

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
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
TOP_KEYS = ("schema", "id", "version", "nuhut", "description", "overrides", "package",
            "provides")
# `sdlc.py ext package --for <tool>` (NUHT-019): the plugin wrappers each tool expects.
PACKAGE_TOOLS = ("claude", "gemini", "codex", "kiro")
PACKAGE_TEXT = ("title", "description", "license")
PACKAGE_PATHS = ("commands", "context_file")
URL_RE = re.compile(r"^https?://[^\s]+$")
LIST_PROVIDES = ("harnesses", "agents", "checks", "presets", "hook_rules", "doctor",
                 "overlays", "commands")
DIR_PROVIDES = ("skills", "roles", "templates")
DIALECTS = ("claude", "gemini", "cursor")
# Executable contributions: these reach a subprocess or the interpreter.
EXECUTABLE = ("agents", "checks", "hook_rules", "doctor", "commands", "lifecycle")
# Code entry points: Python files loaded with importlib.
CODE_KINDS = ("hook_rules", "doctor", "commands")
OVERLAY_MODES = ("prepend", "wrap", "append")
OVERLAY_TARGET_RE = re.compile(r"^templates/[A-Za-z0-9][A-Za-z0-9._-]*\.md$")
# In a `wrap` overlay this line is replaced by the template's text.
WRAP_MARKER = "<!-- nuhut:content -->"
ALLOWED_LABEL = "Extensions allowed"

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
    order = rec.get("order")
    if order is not None and (isinstance(order, bool) or not isinstance(order, int)):
        errors.append((field + ".order", "expected an integer"))
    ident = rec.get("identity")
    if ident is not None:
        if not isinstance(ident, dict):
            errors.append((field + ".identity", "expected an object"))
        else:
            if not isinstance(ident.get("agent", ""), str):
                errors.append((field + ".identity.agent", "expected a string"))
            for key in ("env", "model_env"):
                if not _is_str_list(ident.get(key, [])):
                    errors.append(("%s.identity.%s" % (field, key), "expected list of strings"))


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


def _check_code(errors, field, rec):
    if not _safe_rel(rec.get("file")):
        errors.append((field + ".file", "expected a relative path with no '..'"))
    elif not rec["file"].endswith(".py"):
        errors.append((field + ".file", "expected a .py file"))
    tools = rec.get("tools")
    if tools is not None and not _is_str_list(tools):
        errors.append((field + ".tools", "expected list of strings"))


def _check_overlay(errors, field, rec):
    target = rec.get("target")
    if not isinstance(target, str) or not OVERLAY_TARGET_RE.match(target):
        errors.append((field + ".target", "expected a kit template such as "
                       "\"templates/plan.md\""))
    if rec.get("mode") not in OVERLAY_MODES:
        errors.append((field + ".mode", "expected one of %s" % ", ".join(OVERLAY_MODES)))
    if not _safe_rel(rec.get("file")):
        errors.append((field + ".file", "expected a relative path with no '..'"))


def _check_package(errors, warnings, pkg):
    """The optional top-level `package` block: metadata for the plugin wrappers."""
    if not isinstance(pkg, dict):
        errors.append(("package", "expected an object"))
        return
    for key in sorted(pkg):
        value, field = pkg[key], "package." + key
        if key == "name":
            _check_id(errors, field, value)
        elif key == "version":
            if value != "kit" and not (isinstance(value, str) and SEMVER_RE.match(value)):
                errors.append((field, "expected \"kit\" or a version such as \"1.0.0\""))
        elif key in PACKAGE_TEXT:
            if not isinstance(value, str):
                errors.append((field, "expected a string"))
        elif key == "homepage":
            if not isinstance(value, str) or not URL_RE.match(value):
                errors.append((field, "expected an http:// or https:// URL"))
        elif key == "keywords":
            if not _is_str_list(value):
                errors.append((field, "expected list of strings"))
        elif key == "author":
            if not isinstance(value, dict) or not isinstance(value.get("name"), str):
                errors.append((field, "expected an object with a string name"))
            else:
                for sub in sorted(value):
                    if sub not in ("name", "url", "email"):
                        warnings.append(("%s.%s" % (field, sub), "unknown key, ignored"))
                    elif not isinstance(value[sub], str) or (
                            sub == "url" and not URL_RE.match(value[sub])):
                        errors.append(("%s.%s" % (field, sub), "expected a string" if
                                       sub != "url" else "expected an http(s) URL"))
        elif key in PACKAGE_PATHS:
            if not _safe_rel(value):
                errors.append((field, "expected a relative path with no '..'"))
        else:
            warnings.append((field, "unknown key, ignored"))


RECORD_CHECKS = {"harnesses": _check_harness, "agents": _check_agent,
                 "presets": _check_preset, "checks": _check_check,
                 "hook_rules": _check_code, "doctor": _check_code, "commands": _check_code}


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
    if "package" in manifest:
        _check_package(errors, warnings, manifest["package"])
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
                if key == "overlays":
                    _check_overlay(errors, where, rec)
                elif key in RECORD_CHECKS:
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

    def __init__(self, root, kit, allowed=(), pins=None):
        self.root = root
        self.kit = kit
        self.allowed = frozenset(allowed or ())
        self.pins = pins or {}   # id -> the manifest.json "extensions" record
        self.missing = False
        self._code = {}          # (id, rel) -> (module, None) or (None, error)
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
            code_ok, why = self.code_allowed(ext["id"])
            if target and ext["id"] not in self.allowed:
                self.notes.append({"id": ext["id"], "path": ext["rel"], "message":
                                   "the override of built-in %r is ignored: the charter row "
                                   "%s does not list %r (run `sdlc.py config "
                                   "--allow-extension %s`)" % (target, ALLOWED_LABEL,
                                                               ext["id"], ext["id"])})
                target = None
            for kind in kinds:
                for rec in ext["manifest"].get("provides", {}).get(kind, []) or []:
                    if kind in EXECUTABLE and not code_ok:
                        continue       # reported once per extension by blocked_notes()
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
            if executable_entries(ext["manifest"]) and not code_ok:
                self.notes.append({"id": ext["id"], "path": ext["rel"], "blocked": True,
                                   "message": "extension %s: executable contributions are "
                                   "blocked: %s" % (ext["id"], why)})
        self._records = merged

    def code_allowed(self, ext_id):
        """(True, None) when <ext_id>'s executable contributions may load: built-in, or
        listed in Extensions allowed with its manifest unchanged since `ext add` pinned
        it. Otherwise (False, why)."""
        ext = self.extensions.get(ext_id)
        if ext is None:
            return False, "not installed"
        if ext["source"] == BUILTIN:
            return True, None
        if ext_id not in self.allowed:
            return False, ("code is disabled until the charter row %s lists `%s` on the "
                           "default branch: run `sdlc.py config --allow-extension %s`"
                           % (ALLOWED_LABEL, ext_id, ext_id))
        pinned = (self.pins.get(ext_id) or {}).get("files") or {}
        if MANIFEST not in pinned:
            return False, ("it was not installed with `sdlc.py ext add`, so nothing pins "
                           "its files; reinstall it with `sdlc.py ext add <source>`")
        if sha256_file(ext["path"]) != pinned[MANIFEST]:
            return False, ("%s changed since it was pinned: run `sdlc.py ext update %s`"
                           % (MANIFEST, ext_id))
        return True, None

    def status(self, ext_id):
        """data, code-enabled, code-blocked, version-refused or invalid."""
        if ext_id not in self.extensions:
            err = self.broken.get(ext_id) or {}
            return "version-refused" if err.get("field") in ("nuhut", "schema") else "invalid"
        if not executable_entries(self.extensions[ext_id]["manifest"]):
            return "data"
        return "code-enabled" if self.code_allowed(ext_id)[0] else "code-blocked"

    def load_code(self, ext_id, rel):
        """(module, None) for code file <rel> of extension <ext_id>, or (None, why). A
        non-built-in file loads only when the extension is allowed and the file's sha256
        equals the hash pinned at `ext add`; the realpath must stay inside its directory."""
        key = (ext_id, rel)
        if key in self._code:
            return self._code[key]
        ok, why = self.code_allowed(ext_id)
        ext = self.extensions.get(ext_id)
        path = None
        if ok:
            base = os.path.dirname(ext["path"])
            path = os.path.join(base, rel)
            if not _safe_rel(rel) or not _inside(path, base):
                ok, why = False, "%s escapes the extension directory" % rel
            elif not os.path.isfile(path):
                ok, why = False, "%s is missing" % rel
        if ok and ext["source"] != BUILTIN:
            pinned = ((self.pins.get(ext_id) or {}).get("files") or {}).get(rel)
            if pinned is None or sha256_file(path) != pinned:
                ok, why = False, ("%s does not match the sha256 pinned at `ext add`: run "
                                  "`sdlc.py ext update %s` or restore the file"
                                  % (rel, ext_id))
        result = (None, why)
        if ok:
            name = "nuhut_ext_%s_%s" % (re.sub(r"[^A-Za-z0-9]", "_", ext_id),
                                        re.sub(r"[^A-Za-z0-9]", "_", rel))
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                result = (module, None)
            except Exception as exc:  # an extension's own bug must not crash the caller
                result = (None, "%s failed to load (%s: %s)"
                          % (rel, exc.__class__.__name__, exc))
        self._code[key] = result
        return result

    def code_records(self, kind):
        """[(extension id, record)] for code kind <kind> across every loaded extension,
        built-ins first, then by id. Records of blocked extensions are included: callers
        decide, through load_code, whether they run."""
        out = []
        for ext_id in sorted(self.extensions, key=lambda i: (
                self.extensions[i]["source"] != BUILTIN, i)):
            for rec in self.extensions[ext_id]["manifest"].get("provides", {}).get(kind) or []:
                out.append((ext_id, rec))
        return out

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


def load(root=None, kit=True, version=None, warn=True, use_cache=True, allowed=None,
         pins=None):
    """Load every extension for project <root>. kit=True finds the kit checkout this file
    runs from; pass a path or None to choose. <version> is the running Nuhut version,
    used only for non-built-in ranges. <allowed> is the set of extension ids the charter's
    Extensions allowed row names (default: none, so project code stays off). <pins> is
    the manifest.json "extensions" record (default: read from <root>)."""
    if kit is True:
        kit = default_kit()
    root = os.path.realpath(root) if root else None
    kit = os.path.realpath(kit) if kit else None
    allowed = frozenset(allowed or ())
    if pins is None:
        pins = read_pins(root)
    key = (root, kit, version, allowed, json.dumps(pins, sort_keys=True))
    if use_cache and key in _CACHE:
        return _CACHE[key]
    if version is None and kit and os.path.isfile(os.path.join(kit, "VERSION")):
        try:
            with open(os.path.join(kit, "VERSION"), encoding="utf-8") as handle:
                version = handle.read().strip()
        except (IOError, OSError):
            version = None
    reg = Registry(root, kit, allowed, pins)
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


def sha256_file(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (IOError, OSError):
        return None


def _inside(path, base):
    real, top = os.path.realpath(path), os.path.realpath(base)
    return real == top or real.startswith(top.rstrip(os.sep) + os.sep)


def read_pins(root):
    """The manifest.json "extensions" record: {id: {source, ref, commit, version, files}}."""
    if not root:
        return {}
    try:
        with open(os.path.join(root, ".ai-sdlc", "manifest.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, OSError, ValueError):
        return {}
    pins = data.get("extensions") if isinstance(data, dict) else None
    return pins if isinstance(pins, dict) else {}


def executable_entries(manifest):
    """[(field, what)] for every executable contribution in <manifest>: agent argv,
    check commands and code entry points, each with its path or argv[0]."""
    provides = manifest.get("provides") or {}
    out = []
    for n, rec in enumerate(provides.get("agents") or []):
        for key in ("review", "build"):
            if isinstance(rec, dict) and rec.get(key):
                out.append(("provides.agents[%d].%s" % (n, key),
                            "runs `%s`" % " ".join(str(a) for a in rec[key])))
    for n, rec in enumerate(provides.get("checks") or []):
        if isinstance(rec, dict) and rec.get("command"):
            out.append(("provides.checks[%d].command" % n, "runs `%s`" % rec["command"]))
    for kind in CODE_KINDS:
        for n, rec in enumerate(provides.get(kind) or []):
            if isinstance(rec, dict):
                out.append(("provides.%s[%d]" % (kind, n), "loads %s" % rec.get("file")))
    lifecycle = provides.get("lifecycle")
    if isinstance(lifecycle, dict):
        for event in sorted(lifecycle):
            out.append(("provides.lifecycle.%s" % event, "loads %s" % lifecycle[event]))
    return out


def referenced_paths(manifest):
    """[(field, rel, is_dir)] for every path a manifest names."""
    provides = manifest.get("provides") or {}
    out = []
    for kind in CODE_KINDS:
        for n, rec in enumerate(provides.get(kind) or []):
            if isinstance(rec, dict) and isinstance(rec.get("file"), str):
                out.append(("provides.%s[%d].file" % (kind, n), rec["file"], False))
    for n, rec in enumerate(provides.get("overlays") or []):
        if isinstance(rec, dict) and isinstance(rec.get("file"), str):
            out.append(("provides.overlays[%d].file" % n, rec["file"], False))
    lifecycle = provides.get("lifecycle")
    if isinstance(lifecycle, dict):
        for event in sorted(lifecycle):
            if isinstance(lifecycle[event], str):
                out.append(("provides.lifecycle.%s" % event, lifecycle[event], False))
    for key in DIR_PROVIDES:
        if isinstance(provides.get(key), str):
            out.append(("provides." + key, provides[key], True))
    pkg = manifest.get("package")
    if isinstance(pkg, dict):
        for key in PACKAGE_PATHS:
            if isinstance(pkg.get(key), str):
                out.append(("package." + key, pkg[key], key == "commands"))
    return out


def _json_text(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def package_meta(manifest, version):
    """The wrapper metadata of <manifest>: its `package` block with defaults filled in
    from the manifest. A package version of "kit" means <version>, the running Nuhut."""
    pkg = manifest.get("package") if isinstance(manifest.get("package"), dict) else {}
    ver = pkg.get("version") or manifest.get("version")
    if ver == "kit":
        ver = version
    meta = {"name": pkg.get("name") or manifest.get("id"),
            "title": pkg.get("title") or manifest.get("id"),
            "description": pkg.get("description", manifest.get("description") or ""),
            "version": ver}
    for key in ("author", "homepage", "license", "keywords", "commands", "context_file"):
        if pkg.get(key):
            meta[key] = pkg[key]
    return meta


def _common(meta, keys):
    return [(k, meta[k]) for k in keys if k in meta]


def package_files(manifest, tool, version):
    """[(rel, text)] of the wrapper files <tool> expects for <manifest>. Pure: nothing is
    read or written. No wrapper lists skills: they are model-invoked and cost context
    every turn, so the installer chooses them per project."""
    if tool not in PACKAGE_TOOLS:
        raise ValueError("unknown tool %r: use one of %s" % (tool, ", ".join(PACKAGE_TOOLS)))
    meta = package_meta(manifest, version)
    base = [("name", meta["name"]), ("description", meta["description"]),
            ("version", meta["version"])]
    if tool == "claude":
        obj = dict(base + _common(meta, ("author", "homepage", "license", "keywords",
                                         "commands")))
        return [(".claude-plugin/plugin.json", _json_text(obj))]
    if tool == "gemini":
        obj = dict([("name", meta["name"]), ("version", meta["version"]),
                    ("description", meta["description"])])
        if "context_file" in meta:
            obj["contextFileName"] = meta["context_file"]
        return [("gemini-extension.json", _json_text(obj))]
    if tool == "codex":
        obj = dict(base + _common(meta, ("author", "homepage", "license", "keywords")))
        first = (meta["description"].strip().splitlines() or [""])[0]
        obj["interface"] = {"displayName": meta["title"], "shortDescription": first}
        return [(".codex-plugin/plugin.json", _json_text(obj))]
    obj = dict([("name", meta["name"]), ("displayName", meta["title"]),
                ("version", meta["version"]), ("description", meta["description"])]
               + _common(meta, ("keywords", "author", "homepage", "license")))
    # JSON strings are valid YAML double-quoted scalars, so no value can add a key.
    front = ["---"] + ["%s: %s" % (k, json.dumps(obj[k], ensure_ascii=False))
                       for k in ("name", "displayName", "description", "keywords")
                       if k in obj] + ["---", ""]
    body = "# %s\n\n%s\n" % (meta["title"], meta["description"].strip())
    return [("plugin.json", _json_text(obj)), ("POWER.md", "\n".join(front) + "\n" + body)]


def package_copies(manifest, tool):
    """[(field, rel, is_dir)]: the extension files the <tool> wrapper refers to, which
    `ext package` copies beside it."""
    pkg = manifest.get("package") if isinstance(manifest.get("package"), dict) else {}
    key = {"claude": "commands", "gemini": "context_file"}.get(tool)
    if key and isinstance(pkg.get(key), str):
        return [("package." + key, pkg[key], key == "commands")]
    return []


def check_tree(ext_dir, manifest):
    """[(field, message)] for an extension directory on disk: every path the manifest
    names exists, and no file or symlink resolves outside <ext_dir>."""
    errors = []
    top = os.path.realpath(ext_dir)
    for folder, dirs, names in os.walk(ext_dir):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(dirs + names):
            full = os.path.join(folder, name)
            if not _inside(full, top):
                errors.append(("(files)", "%s escapes the extension directory (it resolves "
                               "outside it)" % os.path.relpath(full, ext_dir)))
    for field, rel, is_dir in referenced_paths(manifest):
        if not _safe_rel(rel):
            continue           # validate() reports it
        full = os.path.join(ext_dir, rel)
        if not _inside(full, top):
            errors.append((field, "%s escapes the extension directory" % rel))
        elif not (os.path.isdir(full) if is_dir else os.path.isfile(full)):
            errors.append((field, "%s does not exist" % rel))
    for n, rec in enumerate((manifest.get("provides") or {}).get("overlays") or []):
        if isinstance(rec, dict) and rec.get("mode") == "wrap" and _safe_rel(rec.get("file")):
            try:
                with open(os.path.join(ext_dir, rec["file"]), encoding="utf-8") as handle:
                    body = handle.read()
            except (IOError, OSError, UnicodeDecodeError):
                continue
            if WRAP_MARKER not in body:
                errors.append(("provides.overlays[%d].file" % n, "a wrap overlay needs a "
                               "line %s where the template goes" % WRAP_MARKER))
    return errors


def parse_allowed(cell):
    """The extension ids an Extensions allowed cell names. A placeholder, `none` or a
    blank cell names none."""
    text = re.sub(r"_\([^)]*\)_", "", cell or "").replace("`", " ")
    return frozenset(w for w in re.split(r"[\s,;]+", text) if ID_RE.match(w) and w != "none")


def _row(text, label):
    for line in (text or "").splitlines():
        m = re.match(r"^\|\s*\*\*%s\*\*\s*\|(.*?)\|\s*$" % re.escape(label), line.strip())
        if m:
            return m.group(1).strip()
    return None


def _git(root, *args):
    try:
        proc = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else ""


def trusted_allowed(root):
    """The Extensions allowed ids as the charter stands on the default branch, the same
    rule as sdlc.py's trusted_text (ADR 0003 decision 8), for callers that do not load
    sdlc.py (the hooks). Falls back to the working tree only when there is no default
    branch or the charter is not on it yet."""
    docs, default = "docs", ""
    try:
        with open(os.path.join(root, ".ai-sdlc", "profile.json"), encoding="utf-8") as handle:
            prof = json.load(handle)
        if isinstance(prof, dict):
            docs = str(prof.get("docs_dir") or docs)
            default = str(prof.get("default_branch") or "")
    except (IOError, OSError, ValueError):
        pass
    rel = docs.strip("/") + "/project/charter.md"
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as handle:
            work = handle.read()
    except (IOError, OSError, UnicodeDecodeError):
        work = ""
    cell = re.sub(r"_\([^)]*\)_", "", _row(work, "Default branch") or "").strip().strip("`")
    branch = cell.strip() or default
    if not branch:
        head = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").strip()
        if head.startswith("refs/remotes/origin/"):
            branch = head[len("refs/remotes/origin/"):]
    text = work
    if branch and not branch.startswith("-"):
        for ref in ("refs/remotes/origin/" + branch, "refs/heads/" + branch):
            if _git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}").strip():
                if _git(root, "ls-tree", "--name-only", ref, "--", rel).strip():
                    text = _git(root, "show", "%s:%s" % (ref, rel))
                break
    return parse_allowed(_row(text, ALLOWED_LABEL))


_HOOK_WARNED = set()


def run_hook_rules(reg, payload, cwd, root, warn=True):
    """The deny reason from the first extension hook rule that denies this tool call, or
    None. A blocked extension's rules do not run (doctor reports them). An allowed one
    whose code cannot load fails closed: one stderr warning per process names it, and
    only the calls its rules would judge are denied."""
    tool = str(payload.get("tool_name") or "")
    for ext_id, rec in reg.code_records("hook_rules"):
        ext = reg.extensions[ext_id]
        if ext["source"] != BUILTIN and ext_id not in reg.allowed:
            continue
        tools = rec.get("tools")
        if tools and tool not in tools and "*" not in tools:
            continue
        module, why = reg.load_code(ext_id, rec.get("file") or "")
        evaluate = getattr(module, "evaluate", None) if module else None
        if module is not None and not callable(evaluate):
            why = "%s has no evaluate(payload, cwd, root)" % rec.get("file")
        if why:
            if warn and ext_id not in _HOOK_WARNED:
                _HOOK_WARNED.add(ext_id)
                sys.stderr.write("nuhut: extension %s: hook rules skipped: %s\n" % (ext_id, why))
            return ("extension %s hook rule %s failed closed, so this %s call is denied: %s"
                    % (ext_id, rec.get("id"), tool or "tool", why))
        try:
            reason = evaluate(payload, cwd, root)
        except Exception as exc:
            return ("extension %s hook rule %s failed closed (%s)"
                    % (ext_id, rec.get("id"), exc.__class__.__name__))
        if reason:
            return "%s [extension %s, rule %s]" % (reason, ext_id, rec.get("id"))
    return None


def run_doctor(reg, root):
    """Findings {level, where, message} from the doctor checks of built-in and allowed
    extensions. A check returns a list of (level, where, message) tuples or dicts."""
    out = []
    for ext_id, rec in reg.code_records("doctor"):
        if reg.extensions[ext_id]["source"] != BUILTIN and ext_id not in reg.allowed:
            continue           # blocked: check_extensions warns once instead
        where = "%s:%s" % (ext_id, rec.get("file"))
        module, why = reg.load_code(ext_id, rec.get("file") or "")
        fn = getattr(module, "check", None) if module else None
        if module is not None and not callable(fn):
            why = "%s has no check(root)" % rec.get("file")
        if why:
            out.append({"level": "fail", "where": where, "message": "skipped: %s" % why})
            continue
        try:
            found = list(fn(root) or [])
        except Exception as exc:
            out.append({"level": "fail", "where": where, "message": "the check raised %s"
                        % exc.__class__.__name__})
            continue
        for item in found:
            if isinstance(item, dict):
                level, at, msg = item.get("level"), item.get("where"), item.get("message")
            elif isinstance(item, (list, tuple)) and len(item) == 3:
                level, at, msg = item
            else:
                continue
            out.append({"level": level if level in ("fail", "warn", "info") else "warn",
                        "where": str(at or where), "message": "[%s] %s" % (ext_id, msg)})
    return out


def run_lifecycle(reg, event, *args):
    """[(extension id, message)] from every built-in or allowed extension's <event> hook:
    the function named <event> in the file `provides.lifecycle.<event>` names. A hook
    returns None to pass or a message to stop; one that cannot load or raises stops too."""
    out = []
    for ext_id in sorted(reg.extensions):
        ext = reg.extensions[ext_id]
        rel = ((ext["manifest"].get("provides") or {}).get("lifecycle") or {}).get(event)
        if not rel or (ext["source"] != BUILTIN and ext_id not in reg.allowed):
            continue
        module, why = reg.load_code(ext_id, rel)
        fn = getattr(module, event, None) if module else None
        if module is not None and not callable(fn):
            why = "%s has no %s()" % (rel, event)
        if why:
            out.append((ext_id, "failed closed: %s" % why))
            continue
        try:
            message = fn(*args)
        except Exception as exc:
            message = "failed closed (%s)" % exc.__class__.__name__
        if message:
            out.append((ext_id, str(message)))
    return out


def template_overlays(reg):
    """({target: [overlay]}, notes) for every loaded extension's overlays, each overlay a
    dict of ext, version, mode and content. A non-built-in overlay file applies only
    while it matches the sha256 pinned at `ext add`."""
    found, notes = {}, []
    for ext_id in sorted(reg.extensions):
        ext = reg.extensions[ext_id]
        base = os.path.dirname(ext["path"])
        pinned = (reg.pins.get(ext_id) or {}).get("files") or {}
        for rec in (ext["manifest"].get("provides") or {}).get("overlays") or []:
            rel = rec["file"]
            path = os.path.join(base, rel)
            if not _inside(path, base) or not os.path.isfile(path):
                notes.append("extension %s: overlay %s is missing or escapes its directory; "
                             "skipped" % (ext_id, rel))
                continue
            if ext["source"] != BUILTIN and sha256_file(path) != pinned.get(rel):
                notes.append("extension %s: overlay %s does not match the hash pinned at "
                             "`ext add`; skipped (run `sdlc.py ext update %s`)"
                             % (ext_id, rel, ext_id))
                continue
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            found.setdefault(rec["target"], []).append({
                "ext": ext_id, "version": ext["manifest"].get("version"),
                "mode": rec["mode"], "content": content})
    return found, notes


def apply_overlays(text, overlays):
    """<text> with <overlays> applied: prepend, then wrap, then append, and by extension
    id within each mode (ADR 0003 decision 7)."""
    for ov in sorted(overlays, key=lambda o: (OVERLAY_MODES.index(o["mode"]), o["ext"])):
        content = ov["content"]
        if ov["mode"] == "prepend":
            text = content + ("" if content.endswith("\n") else "\n") + text
        elif ov["mode"] == "wrap":
            text = content.replace(WRAP_MARKER, text.rstrip("\n"), 1)
        else:
            text = text + ("" if text.endswith("\n") else "\n") + content
    return text


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
    """{id: (argv, model_flag)} for kind "review" or "build". Both kinds come from the
    same agents record, so the reviewer and builder tables cannot disagree on a tool."""
    return agent_table_of(reg.agents(), kind)


def agent_table_of(agents, kind):
    """agent_table() over a plain {id: record} mapping (the runtime's v5 fallback)."""
    out = {}
    for aid, rec in agents.items():
        if rec.get(kind):
            out[aid] = (list(rec[kind]), rec.get("model_flag") or "--model")
    return out


# The model variable any tool may set; the agents records add their own after it.
MODEL_ENV_FIRST = ("AI_SDLC_MODEL",)


def identity_env_of(agents):
    """(agent_env, model_env) over a plain {id: record} mapping in priority order:
    agent_env is ((variable, trailer agent name), ...), the first variable set wins;
    model_env is the variables read for the model, in order."""
    agent_env, model_env = [], list(MODEL_ENV_FIRST)
    for rec in agents.values():
        ident = rec.get("identity") or {}
        for var in ident.get("env") or ():
            agent_env.append((var, ident.get("agent") or rec["id"]))
        for var in ident.get("model_env") or ():
            if var not in model_env:
                model_env.append(var)
    return tuple(agent_env), tuple(model_env)


def identity_env(reg):
    """The v5 AGENT_ENV and MODEL_ENV, built from the agents records' `identity`."""
    return identity_env_of(reg.agents())


def pointer_files(reg, builtin_only=False):
    """Every pointer file a harness record names, in harness order. builtin_only leaves out
    records from project extensions, for callers that write to the files."""
    out = []
    for rec in reg.harnesses().values():
        if builtin_only and rec.get("source") != BUILTIN:
            continue
        for ptr in rec.get("pointer") or ():
            if ptr.get("path") and ptr["path"] not in out:
                out.append(ptr["path"])
    return tuple(out)


def builtin_record(reg, kind, rec_id):
    """The record <rec_id> of <kind> as a built-in extension declares it, ignoring any
    override; None when no built-in declares it."""
    for ext_id in sorted(reg.extensions):
        ext = reg.extensions[ext_id]
        if ext["source"] != BUILTIN:
            continue
        for rec in ext["manifest"].get("provides", {}).get(kind, []) or []:
            if rec.get("id") == rec_id:
                return rec
    return None


def hook_dialect(reg, harness):
    """The hook dialect ("claude", "gemini", "cursor" or None) for tool <harness>. A
    built-in tool keeps its built-in dialect even when a project extension overrides its
    record: answering a tool in the wrong shape would let it ignore a deny. A tool only a
    project extension adds uses that extension's dialect."""
    rec = builtin_record(reg, "harnesses", harness) or reg.harnesses().get(harness)
    if not rec:
        return None
    dialect = (rec.get("hooks") or {}).get("dialect")
    return dialect if dialect in DIALECTS else None


def lens_files(reg):
    """(dirs, mcp): [(path, harness id, dialect, title)] for every tool directory and MCP
    config file the harness records name, in harness order, each path once."""
    dirs, mcp, seen_d, seen_m = [], [], set(), set()
    for hid, rec in reg.harnesses().items():
        lens = rec.get("lens") or {}
        dialect = hook_dialect(reg, hid)
        for rel in lens.get("dirs") or ():
            if rel not in seen_d:
                seen_d.add(rel)
                dirs.append((rel, hid, dialect, rec.get("title") or hid))
        for rel in lens.get("mcp") or ():
            if rel not in seen_m:
                seen_m.add(rel)
                mcp.append((rel, hid, dialect, rec.get("title") or hid))
    return dirs, mcp

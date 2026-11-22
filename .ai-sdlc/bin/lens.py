"""The Project lens: everything a repository is made of, in one read-only report.

Stack and dependencies, build errors from the last verify run, vulnerable packages from
the last `sdlc.py audit`, deployment and CI, containers, environment variable names, the
agentic stack (skills, commands, subagents, hooks, MCP servers, plugins, harness files,
other kits) and the security findings across all of them. Asked for
(`--area standards`), it also reads the coding conventions the code already follows.

It never runs a tool (beyond a read-only `git log` for the commit convention) and
never touches the network: build errors come from logs `verify`
kept, vulnerabilities from the result `audit` kept. It never reads a secret: environment
files are read for variable *names* only (and only templates; a real .env is checked for
existence and whether git ignores it), MCP servers are reported by name and transport,
never their command arguments, environment or headers. User-level items (~/.claude) are
included only when asked, for the live page; a static export never carries them.

Called by sdlc.py (`lens`, `audit`) and view.py (`/api/lens`). Standard library only.
This file must never contain two opening braces in a row (see sdlc.py).
"""

import datetime
import glob
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", "out", "coverage", ".venv", "venv",
             "__pycache__", ".turbo", ".cache", "vendor", "target", ".ai-sdlc", ".idea", ".vscode"}
MAX_SCAN_FILES = 4000
MAX_DEPS = 400
MAX_ERRORS = 60
CODE_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro",
            ".py", ".rb", ".go", ".rs", ".php", ".java", ".kt", ".cs", ".ex", ".exs")
ENV_TEMPLATES = (".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults",
                 "example.env", ".env.local.example", ".env.development.example",
                 ".env.production.example")
ENV_REF = re.compile(
    r"process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[['\"]([A-Z][A-Z0-9_]+)['\"]\]"
    r"|import\.meta\.env\.([A-Z][A-Z0-9_]+)"
    r"|os\.environ(?:\.get)?\(?\[?['\"]([A-Z][A-Z0-9_]+)['\"]|os\.getenv\(['\"]([A-Z][A-Z0-9_]+)['\"]"
    r"|ENV\[['\"]([A-Z][A-Z0-9_]+)['\"]\]|ENV\.fetch\(['\"]([A-Z][A-Z0-9_]+)['\"]"
    r"|os\.Getenv\(\"([A-Z][A-Z0-9_]+)\"\)|env::var\(\"([A-Z][A-Z0-9_]+)\"\)|getenv\(['\"]([A-Z][A-Z0-9_]+)['\"]\)")
# Built into runtimes or set by the platform; never expected in a template.
ENV_BUILTIN = {"NODE_ENV", "PORT", "HOME", "PATH", "PWD", "CI", "TZ", "LANG", "HOSTNAME", "VERCEL",
               "VERCEL_ENV", "VERCEL_URL", "GITHUB_ACTIONS", "NEXT_RUNTIME", "DEV", "PROD", "MODE",
               "SSR", "BASE_URL", "DEBUG", "USER", "SHELL", "TERM", "TMPDIR"}
SECRETISH = re.compile(r"(SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVATE|CREDENTIAL|AUTH)", re.I)
SEVERITY_RANK = {"critical": 0, "high": 1, "moderate": 2, "medium": 2, "low": 3, "info": 4, "unknown": 5}

# Error lines worth lifting out of a build, typecheck or lint log.
ERROR_PATTERNS = (
    ("tsc", re.compile(r"^(?P<file>[^\s:()]+\.(?:tsx?|jsx?|mts|cts|vue))[(:](?P<line>\d+)[,:](?P<col>\d+)\)?:?\s*-?\s*error\s+(?P<msg>TS\d+:.*)$")),
    ("eslint", re.compile(r"^\s*(?P<line>\d+):(?P<col>\d+)\s+error\s+(?P<msg>.+)$")),
    ("python", re.compile(r"^(?P<file>[^\s:]+\.py):(?P<line>\d+):(?:(?P<col>\d+):)?\s*(?:error:)?\s*(?P<msg>.+)$")),
    ("pytest", re.compile(r"^(?:FAILED|ERROR)\s+(?P<file>[^\s:]+\.py)(?:::(?P<msg>\S.*))?$")),
    ("go", re.compile(r"^(?P<file>[^\s:]+\.go):(?P<line>\d+):(?P<col>\d+):\s*(?P<msg>.+)$")),
    ("rust", re.compile(r"^\s*-->\s*(?P<file>[^\s:]+\.rs):(?P<line>\d+):(?P<col>\d+)$")),
    ("generic", re.compile(r"^(?P<file>[\w./@-]+\.\w{1,5}):(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?P<msg>(?:error|Error|ERROR)\b.*)$")),
    ("message", re.compile(r"^(?:Error|ERROR|error)(?:\[[^\]]*\])?:\s*(?P<msg>.{4,})$")),
)


def _rel(project, path):
    return os.path.relpath(path, project.root).replace(os.sep, "/")


def _read(path, limit=2000000):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except (IOError, OSError):
        return ""


def _json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, OSError, ValueError):
        return None


def _walk(root, max_depth=4):
    """Files under root, skipping vendored and generated trees, capped."""
    count = 0
    base_depth = root.rstrip(os.sep).count(os.sep)
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") or d in (".github", ".devcontainer", ".claude", ".agents")]
        if base.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
        for name in files:
            count += 1
            if count > MAX_SCAN_FILES:
                return
            yield os.path.join(base, name)


def _frontmatter(text):
    """key: value pairs from a leading --- block; enough for SKILL.md and agent files."""
    out = {}
    if not text.startswith("---"):
        return out
    end = text.find("\n---", 3)
    if end < 0:
        return out
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip("\"'")
    return out


def _tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home) else path


# ---------------------------------------------------------------- stack & dependencies

def stack(project, detect_mod):
    d = detect_mod.detect(project.root)
    fields = (("languages", "lang"), ("package managers", "pm"), ("frameworks", "fw"), ("data", "db"),
              ("auth", "auth"), ("hosting", "host"), ("CI", "ci"), ("tests", "test"),
              ("migrations", "migrations"), ("ML", "ml"), ("vector stores", "vector"),
              ("data tooling", "dataeng"), ("messaging", "messaging"), ("infrastructure", "iac"),
              ("i18n", "i18n_libs"), ("load testing", "load"))
    out = []
    for label, attr in fields:
        values = list(getattr(d, attr, []) or [])
        if values:
            out.append({"label": label, "values": values})
    return {
        "groups": out,
        "monorepo": getattr(d, "mono_tool", "") or "",
        "components": [{"name": c[0], "kind": c[1], "path": c[2]} for c in getattr(d, "components", [])],
        "integrations": [{"service": s, "use": u} for s, u in getattr(d, "integrations", [])],
        "deploy": list(getattr(d, "deploy", []) or []),
        "deploy_labels": [detect_mod.DEPLOY_LABELS.get(p, p) for p in getattr(d, "deploy", []) or []],
        "commands": dict(getattr(d, "cmds", {}) or {}),
    }


def _req_lines(text):
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*(.*)$", line)
        if m:
            yield m.group(1), m.group(2).strip()


LOCKFILES = {
    "npm": ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb", "bun.lock"),
    "python": ("uv.lock", "poetry.lock", "Pipfile.lock", "pdm.lock"),
    "go": ("go.sum",), "cargo": ("Cargo.lock",), "ruby": ("Gemfile.lock",), "php": ("composer.lock",),
}


def dependencies(project):
    """Direct dependencies per manifest. Versions are what the manifest asks for, not
    what is installed; nothing is resolved and nothing is fetched."""
    manifests = []
    for path in _walk(project.root, max_depth=3):
        name = os.path.basename(path)
        rel = _rel(project, path)
        deps = []
        kind = ""
        if name == "package.json":
            data = _json(path) or {}
            kind = "npm"
            for section, scope in (("dependencies", "prod"), ("devDependencies", "dev"),
                                   ("peerDependencies", "peer"), ("optionalDependencies", "optional")):
                for dep, ver in sorted((data.get(section) or {}).items()):
                    deps.append({"name": dep, "version": str(ver), "scope": scope})
        elif name == "pyproject.toml":
            text = _read(path)
            kind = "python"
            block = re.search(r"^\[project\][\s\S]*?^dependencies\s*=\s*\[([\s\S]*?)\]", text, re.M)
            for raw in re.findall(r"['\"]([^'\"]+)['\"]", block.group(1) if block else ""):
                m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*(.*)$", raw)
                if m:
                    deps.append({"name": m.group(1), "version": m.group(2), "scope": "prod"})
            poetry = re.search(r"^\[tool\.poetry\.dependencies\]([\s\S]*?)(?=^\[|\Z)", text, re.M)
            for m in re.finditer(r"^([A-Za-z0-9_.\-]+)\s*=\s*(.+)$", poetry.group(1) if poetry else "", re.M):
                if m.group(1).lower() != "python":
                    deps.append({"name": m.group(1), "version": m.group(2).strip().strip("\"'"), "scope": "prod"})
        elif re.match(r"^requirements(-[\w.]+)?\.txt$", name):
            kind = "python"
            scope = "dev" if re.search(r"dev|test", name) else "prod"
            deps = [{"name": n, "version": v, "scope": scope} for n, v in _req_lines(_read(path))]
        elif name == "go.mod":
            kind = "go"
            for m in re.finditer(r"^\s*([\w./\-]+)\s+(v[\w.\-+]+)(\s*//\s*indirect)?", _read(path), re.M):
                if not m.group(3):
                    deps.append({"name": m.group(1), "version": m.group(2), "scope": "prod"})
        elif name == "Cargo.toml":
            kind = "cargo"
            text = _read(path)
            for section, scope in (("dependencies", "prod"), ("dev-dependencies", "dev")):
                block = re.search(r"^\[%s\]([\s\S]*?)(?=^\[|\Z)" % re.escape(section), text, re.M)
                for m in re.finditer(r"^([\w\-]+)\s*=\s*(.+)$", block.group(1) if block else "", re.M):
                    ver = re.search(r"version\s*=\s*\"([^\"]+)\"", m.group(2))
                    deps.append({"name": m.group(1), "version": ver.group(1) if ver else m.group(2).strip().strip("\""), "scope": scope})
        elif name == "Gemfile":
            kind = "ruby"
            for m in re.finditer(r"^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", _read(path), re.M):
                deps.append({"name": m.group(1), "version": m.group(2) or "", "scope": "prod"})
        elif name == "composer.json":
            data = _json(path) or {}
            kind = "php"
            for section, scope in (("require", "prod"), ("require-dev", "dev")):
                for dep, ver in sorted((data.get(section) or {}).items()):
                    deps.append({"name": dep, "version": str(ver), "scope": scope})
        else:
            continue
        # A workspace package shares the lockfile of the nearest ancestor that has one.
        lock, here = [], os.path.realpath(os.path.dirname(path))
        root_real = os.path.realpath(project.root)
        while not lock:
            lock = [os.path.relpath(os.path.join(here, f), root_real).replace(os.sep, "/")
                    for f in LOCKFILES.get(kind, ())
                    if os.path.exists(os.path.join(here, f))]
            if here == root_real or not here.startswith(root_real + os.sep):
                break
            here = os.path.dirname(here)
        manifests.append({"path": rel, "kind": kind, "count": len(deps), "lockfile": lock[0] if lock else "",
                          "deps": deps[:MAX_DEPS], "truncated": len(deps) > MAX_DEPS})
    manifests.sort(key=lambda m: (m["path"].count("/"), m["path"]))
    return {"manifests": manifests, "total": sum(m["count"] for m in manifests)}


# ---------------------------------------------------------------- build errors

def extract_errors(text, limit=MAX_ERRORS):
    """`file:line: message` lines from a tool's output, deduplicated, in log order."""
    out, seen, last_file = [], set(), ""
    for raw in text.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", raw).rstrip()
        if not line:
            continue
        if re.match(r"^\S.*\.(?:tsx?|jsx?|vue|svelte|astro)$", line.strip()):
            last_file = line.strip()        # eslint prints the file, then indented problems
        for tool, pattern in ERROR_PATTERNS:
            m = pattern.match(line)
            if not m:
                continue
            g = m.groupdict()
            item = {"tool": tool, "file": g.get("file") or (last_file if tool == "eslint" else ""),
                    "line": int(g["line"]) if g.get("line") else None, "message": (g.get("msg") or line).strip()[:300]}
            key = (item["file"], item["line"], item["message"])
            if key not in seen:
                seen.add(key)
                out.append(item)
            break
        if len(out) >= limit:
            break
    return out


def build_errors(project, evidence):
    """For each stage of the latest verify run that failed, the error lines from its log."""
    if not evidence:
        return {"run": "", "stages": []}
    run = evidence[-1]
    folder = project.path(os.path.join(".ai-sdlc", "evidence", run["folder"]))
    stages = []
    for st in run.get("stages", []):
        result = st.get("result") or ""
        if not result.startswith("Verified"):
            continue
        failed = "fail" in result
        errors = extract_errors(_read(os.path.join(folder, st["stage"] + ".log"))) if failed else []
        stages.append({"stage": st["stage"], "result": result, "failed": failed, "seconds": st.get("seconds"),
                       "errors": errors})
    stages.sort(key=lambda s: (not s["failed"], s["stage"]))
    return {"run": run["folder"], "generated": run.get("generated", ""), "dirty": run.get("dirty", False), "stages": stages}


# ---------------------------------------------------------------- audit

AUDIT_TOOLS = (
    # (substring of the charter's scan command, JSON command, parser name)
    ("pnpm audit", "pnpm audit --json", "npm"),
    ("npm audit", "npm audit --json", "npm"),
    ("yarn npm audit", "yarn npm audit --json --recursive", "yarn"),
    ("pip-audit", "pip-audit -f json", "pip"),
    ("osv-scanner", "osv-scanner --format json -r .", "osv"),
    ("cargo audit", "cargo audit --json", "cargo"),
    ("govulncheck", "govulncheck -json ./...", "govuln"),
)


def audit_command(scan_command):
    """The JSON form of the project's own dependency scanner, or None when the charter's
    scan stage runs a tool this module cannot read."""
    for needle, cmd, parser in AUDIT_TOOLS:
        if needle in (scan_command or ""):
            return cmd, parser
    return None, None


def parse_audit(parser, text):
    vulns = []
    try:
        if parser == "govuln":
            data = [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
        elif parser == "yarn":
            data = [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
        else:
            data = json.loads(text[text.find("{"):] if "{" in text else "{}")
    except ValueError:
        return None
    if parser == "npm":
        for name, v in sorted((data.get("vulnerabilities") or {}).items()):
            via = [x for x in v.get("via", []) if isinstance(x, dict)]
            vulns.append({"package": name, "version": v.get("range", ""), "severity": v.get("severity", "unknown"),
                          "id": (via[0].get("url", "") or str(via[0].get("source", ""))) if via else "",
                          "title": via[0].get("title", "") if via else "via " + ", ".join(str(x) for x in v.get("via", [])),
                          "fix": "yes" if v.get("fixAvailable") else "no", "direct": bool(v.get("isDirect"))})
        for adv in (data.get("advisories") or {}).values():   # npm 6 / pnpm
            vulns.append({"package": adv.get("module_name", ""), "version": adv.get("vulnerable_versions", ""),
                          "severity": adv.get("severity", "unknown"), "id": adv.get("url", ""),
                          "title": adv.get("title", ""), "fix": adv.get("patched_versions", ""), "direct": False})
    elif parser == "yarn":
        for rec in data:
            adv = (rec.get("children") or {})
            vulns.append({"package": rec.get("value", ""), "version": adv.get("Vulnerable Versions", ""),
                          "severity": str(adv.get("Severity", "unknown")).lower(), "id": adv.get("URL", ""),
                          "title": adv.get("Issue", ""), "fix": "", "direct": False})
    elif parser == "pip":
        for dep in data.get("dependencies", data if isinstance(data, list) else []):
            for v in dep.get("vulns", []):
                vulns.append({"package": dep.get("name", ""), "version": dep.get("version", ""), "severity": "unknown",
                              "id": v.get("id", ""), "title": (v.get("description") or "")[:200],
                              "fix": ", ".join(v.get("fix_versions", [])), "direct": True})
    elif parser == "osv":
        for res in data.get("results", []):
            for pkg in res.get("packages", []):
                info = pkg.get("package", {})
                for v in pkg.get("vulnerabilities", []):
                    sev = "unknown"
                    for g in pkg.get("groups", []):
                        if v.get("id") in g.get("ids", []) and g.get("max_severity"):
                            try:
                                score = float(g["max_severity"])
                                sev = "critical" if score >= 9 else "high" if score >= 7 else "moderate" if score >= 4 else "low"
                            except ValueError:
                                pass
                    vulns.append({"package": info.get("name", ""), "version": info.get("version", ""), "severity": sev,
                                  "id": v.get("id", ""), "title": v.get("summary", ""), "fix": "", "direct": False})
    elif parser == "cargo":
        for v in (data.get("vulnerabilities") or {}).get("list", []):
            adv, pkg = v.get("advisory", {}), v.get("package", {})
            vulns.append({"package": pkg.get("name", ""), "version": pkg.get("version", ""),
                          "severity": (adv.get("severity") or "unknown").lower(), "id": adv.get("id", ""),
                          "title": adv.get("title", ""), "fix": ", ".join((v.get("versions") or {}).get("patched", [])), "direct": False})
    elif parser == "govuln":
        for rec in data:
            osv = rec.get("osv")
            if osv:
                aff = (osv.get("affected") or [{}])[0].get("package", {})
                vulns.append({"package": aff.get("name", ""), "version": "", "severity": "unknown", "id": osv.get("id", ""),
                              "title": osv.get("summary", ""), "fix": "", "direct": False})
    vulns.sort(key=lambda v: (SEVERITY_RANK.get(v["severity"], 5), v["package"]))
    return vulns


def latest_audit(project):
    base = project.path(os.path.join(".ai-sdlc", "evidence"))
    for folder in sorted(glob.glob(os.path.join(base, "*-audit")), reverse=True):
        data = _json(os.path.join(folder, "audit.json"))
        if data is not None:
            data["folder"] = os.path.basename(folder)
            return data
    return None


# ---------------------------------------------------------------- deploy, CI, containers

def workflows(project):
    out = []
    for path in sorted(glob.glob(project.path(os.path.join(".github", "workflows", "*.y*ml")))):
        text = _read(path)
        name = re.search(r"^name:\s*['\"]?([^\n'\"]+)", text, re.M)
        on = re.search(r"^on:\s*(.*)$", text, re.M)
        triggers = []
        if on:
            if on.group(1).strip():
                triggers = re.findall(r"[\w_]+", on.group(1))
            else:
                block = re.search(r"^on:\s*\n((?:[ \t]+.*\n?)+)", text, re.M)
                triggers = re.findall(r"^[ \t]{2}([\w_]+):", block.group(1), re.M) if block else []
        jobs_block = re.search(r"^jobs:\s*\n((?:[ \t]+.*\n?|\s*\n)+)", text, re.M)
        jobs = re.findall(r"^[ \t]{2}([\w\-]+):\s*$", jobs_block.group(1), re.M) if jobs_block else []
        deploy = bool(re.search(r"deploy|dokploy|vercel|wrangler|netlify|fly(ctl)? deploy|kubectl|helm |docker push|"
                                r"gh-pages|firebase deploy|railway|render\.com|aws (s3|ecs|lambda)|terraform apply",
                                text, re.I))
        out.append({"file": _rel(project, path), "name": name.group(1).strip() if name else os.path.basename(path),
                    "triggers": triggers[:8], "jobs": jobs[:12], "deploys": deploy})
    return out


def containers(project):
    dockerfiles, compose, devcontainer = [], [], None
    for path in _walk(project.root, max_depth=3):
        name = os.path.basename(path)
        rel = _rel(project, path)
        if name == "Dockerfile" or name.startswith("Dockerfile.") or name.endswith(".Dockerfile"):
            text = _read(path)
            stages = re.findall(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", text, re.M | re.I)
            aliases = set(a.lower() for _, a in stages if a)
            froms = [img for img, _ in stages]
            user = re.findall(r"^\s*USER\s+(\S+)", text, re.M | re.I)
            ports = re.findall(r"^\s*EXPOSE\s+(.+)$", text, re.M | re.I)
            risks = []
            for image in froms:
                if image.lower() in ("scratch",) or image.startswith("$") or image.lower() in aliases:
                    continue
                if ":" not in image.split("/")[-1] or image.endswith(":latest"):
                    risks.append("base image %s is not pinned to a version" % image)
            if not user or user[-1] in ("root", "0"):
                risks.append("runs as root (no USER, or USER root, in the final stage)")
            if re.search(r"^\s*(ARG|ENV)\s+\S*(SECRET|TOKEN|PASSWORD|API_KEY)\S*\s*=?\s*\S+", text, re.M | re.I):
                risks.append("a secret-looking ARG/ENV is baked into the image")
            if re.search(r"^\s*ADD\s+https?://", text, re.M | re.I):
                risks.append("ADD from a URL (unverified download)")
            dockerfiles.append({"path": rel, "base": froms, "stages": len(froms), "user": user[-1] if user else "",
                                "ports": [p.strip() for p in ports], "healthcheck": bool(re.search(r"^\s*HEALTHCHECK", text, re.M | re.I)),
                                "risks": risks})
        elif re.match(r"^(docker-)?compose(\.[\w-]+)?\.ya?ml$", name):
            compose.append(_compose(project, path))
        elif rel == ".devcontainer/devcontainer.json":
            data = _json(path) or {}
            devcontainer = {"path": rel, "image": data.get("image", "") or (data.get("build") or {}).get("dockerfile", ""),
                            "features": sorted((data.get("features") or {}).keys())}
    return {"dockerfiles": dockerfiles, "compose": compose, "devcontainer": devcontainer}


def _compose(project, path):
    """Service names and their shape from a compose file, without a YAML library. A literal
    secret-looking value in `environment:` is flagged by its key; the value is not kept."""
    text = _read(path)
    services, cur, section = [], None, ""
    in_services = False
    for line in text.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if not in_services:
            continue
        if re.match(r"^\S", line):
            break
        m = re.match(r"^  ([\w.\-]+):\s*$", line)
        if m:
            cur = {"name": m.group(1), "image": "", "build": False, "ports": [], "env_file": [], "depends_on": [],
                   "healthcheck": False, "secret_keys": [], "restart": ""}
            services.append(cur)
            section = ""
            continue
        if cur is None:
            continue
        m = re.match(r"^    ([\w_\-]+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            section = key
            if key == "image":
                cur["image"] = val.strip("\"'")
            elif key == "build":
                cur["build"] = True
            elif key == "healthcheck":
                cur["healthcheck"] = True
            elif key == "restart":
                cur["restart"] = val.strip("\"'")
            elif key == "env_file" and val:
                cur["env_file"].append(val.strip("\"'[]"))
            elif key == "depends_on" and val.startswith("["):
                cur["depends_on"] += [x.strip(" \"'") for x in val.strip("[]").split(",") if x.strip()]
            continue
        listed = re.match(r"^      -\s*(.+)$", line)
        mapped = re.match(r"^      ([\w_\-]+):\s*(.*)$", line)
        if not (listed or mapped):
            continue
        item = (listed.group(1) if listed else mapped.group(1)).strip().strip("\"'")
        if section == "ports":
            cur["ports"].append(item)
        elif section == "env_file":
            cur["env_file"].append(item)
        elif section == "depends_on":
            cur["depends_on"].append(item.rstrip(":"))
        elif section == "environment":
            if listed:
                key, _, value = item.partition("=")
            else:
                key, value = mapped.group(1), mapped.group(2)
            value = value.strip().strip("\"'")
            if SECRETISH.search(key) and value and not value.startswith("$"):
                cur["secret_keys"].append(key)
    risks = []
    for s in services:
        if s["secret_keys"]:
            risks.append("%s: literal value for %s in environment (use env_file or a secret)" % (s["name"], ", ".join(s["secret_keys"])))
        if s["image"] and not s["image"].startswith("$") and (":" not in s["image"].split("/")[-1] or s["image"].endswith(":latest")):
            risks.append("%s: image %s is not pinned" % (s["name"], s["image"]))
    return {"path": _rel(project, path), "services": services, "risks": risks}


# ---------------------------------------------------------------- environment

def env_report(project):
    """Variable names in templates and in code, and how they differ. Values are never read
    from anything but a template, and are not kept even there."""
    templates = {}
    for name in ENV_TEMPLATES:
        for path in glob.glob(project.path(os.path.join("**", name)), recursive=True):
            rel = _rel(project, path)
            if any(part in SKIP_DIRS for part in rel.split("/")):
                continue
            keys = []
            for line in _read(path).splitlines():
                m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
                if m:
                    keys.append(m.group(1))
            templates[rel] = keys
    used = {}
    for path in _walk(project.root, max_depth=6):
        if not path.endswith(CODE_EXT):
            continue
        text = _read(path, 400000)
        for m in ENV_REF.finditer(text):
            name = next(g for g in m.groups() if g)
            used.setdefault(name, set()).add(_rel(project, path))
    declared = set(k for keys in templates.values() for k in keys)
    names = sorted(set(used) | declared)
    variables = [{"name": n, "in_template": n in declared, "used_in": sorted(used.get(n, []))[:5],
                  "uses": len(used.get(n, [])), "secret": bool(SECRETISH.search(n)), "builtin": n in ENV_BUILTIN}
                 for n in names]
    real_env = []
    for name in (".env", ".env.local", ".env.production", ".env.development"):
        if os.path.exists(project.path(name)):
            tracked = bool(project.git("ls-files", "--", name).strip())
            ignored = subprocess.run(["git", "check-ignore", "-q", name], cwd=project.root,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            real_env.append({"file": name, "tracked": tracked, "ignored": ignored})
    return {
        "templates": [{"path": p, "count": len(k)} for p, k in sorted(templates.items())],
        "variables": variables,
        "missing_from_template": [v["name"] for v in variables if v["uses"] and not v["in_template"] and not v["builtin"]],
        "unused_in_code": [v["name"] for v in variables if v["in_template"] and not v["uses"]],
        "env_files": real_env,
    }


# ---------------------------------------------------------------- agentic stack

def _skills_in(root_dir, source, owner_of):
    out = []
    for skill in sorted(glob.glob(os.path.join(root_dir, "*", "SKILL.md"))):
        fm = _frontmatter(_read(skill, 20000))
        name = fm.get("name") or os.path.basename(os.path.dirname(skill))
        out.append({"kind": "skill", "name": name, "description": fm.get("description", ""),
                    "source": source, "path": skill, "owner": owner_of(skill)})
    return out


def _md_items(root_dir, kind, source, owner_of):
    out = []
    for path in sorted(glob.glob(os.path.join(root_dir, "*.md"))):
        fm = _frontmatter(_read(path, 20000))
        out.append({"kind": kind, "name": fm.get("name") or os.path.splitext(os.path.basename(path))[0],
                    "description": fm.get("description", ""), "source": source, "path": path,
                    "owner": owner_of(path), "detail": dict((k, fm[k]) for k in ("argument-hint", "tools", "model") if fm.get(k))})
    return out


def _hooks_from_settings(path, source):
    data = _json(path) or {}
    out = []
    for event, entries in sorted((data.get("hooks") or {}).items()):
        for entry in entries if isinstance(entries, list) else []:
            matcher = entry.get("matcher", "") if isinstance(entry, dict) else ""
            for h in (entry.get("hooks") or []) if isinstance(entry, dict) else []:
                cmd = str(h.get("command", ""))
                out.append({"kind": "hook", "name": "%s%s" % (event, " · " + matcher if matcher else ""),
                            "description": os.path.basename(cmd.split()[0]) if cmd else h.get("type", ""),
                            "source": source, "path": path, "owner": "",
                            "detail": {"event": event, "matcher": matcher, "script": os.path.basename(cmd.split()[0]) if cmd else ""}})
    return out


def _mcp_from(data, path, source):
    out = []
    for name, cfg in sorted(((data or {}).get("mcpServers") or {}).items()):
        cfg = cfg if isinstance(cfg, dict) else {}
        transport = cfg.get("type") or ("http" if cfg.get("url") else "stdio")
        out.append({"kind": "mcp", "name": name, "description": transport, "source": source, "path": path,
                    "owner": "", "detail": {"transport": transport}})
    return out


# The v5 lists, for when the extension registry is missing or cannot be loaded:
# (path, harness id, hook dialect, title), as registry.lens_files() returns them.
V5_LENS_DIRS = ((".claude", "claude", "claude", "Claude Code"), (".cursor", "cursor", "cursor", "Cursor"),
                (".gemini", "gemini", "gemini", "Gemini CLI"), (".windsurf", "windsurf", None, "Windsurf"),
                (".clinerules", "cline", None, "Cline"), (".roo", "roo", None, "Roo Code"))
V5_LENS_MCP = ((".claude/settings.json", "claude", "claude", "Claude Code"),
               (".claude/settings.local.json", "claude", "claude", "Claude Code"),
               (".mcp.json", "claude", "claude", "Claude Code"),
               (".cursor/mcp.json", "cursor", "cursor", "Cursor"),
               (".gemini/settings.json", "gemini", "gemini", "Gemini CLI"))


def harness_lens_files(project):
    """(tool dirs, MCP files) from the harness records' `lens` fields, or the v5 lists."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import registry
        reg = registry.load(project.root, version=(getattr(project, "manifest", None) or {}).get("kit_version"),
                            warn=False)
        if not reg.missing:
            dirs, mcp = registry.lens_files(reg)
            return list(dirs), list(mcp)
    except Exception:  # the lens must render without the registry
        pass
    return list(V5_LENS_DIRS), list(V5_LENS_MCP)


def agents(project, kit, include_user=False):
    """Skills, commands, subagents, hooks, MCP servers, plugins and harness files: kit,
    project, user (only when asked) and other kits found in the repository."""
    manifest = _json(project.path(os.path.join(".ai-sdlc", "manifest.json"))) or {}
    managed = manifest.get("files") or {}

    def owner_of(path):
        rel = os.path.relpath(path, project.root).replace(os.sep, "/")
        if rel.startswith(".."):
            return ""
        if rel in managed:
            import hashlib
            try:
                with open(path, "rb") as h:
                    same = hashlib.sha256(h.read()).hexdigest() == managed[rel]
            except (IOError, OSError):
                same = False
            return "kit" if same else "kit-modified"
        return "project"

    items = []
    for rel in (".claude/skills", ".agents/skills"):
        items += _skills_in(project.path(rel), "project", owner_of)
    items += _md_items(project.path(".claude/commands"), "command", "project", owner_of)
    items += _md_items(project.path(".claude/agents"), "subagent", "project", owner_of)
    tool_dirs, mcp_files = harness_lens_files(project)
    claude_dirs = tuple(d + "/" for d, _, dialect, _ in tool_dirs if dialect == "claude")
    for rel, _, dialect, _ in mcp_files:
        data = _json(project.path(rel))
        if not data:
            continue
        # A Claude-dialect settings file also carries hooks and plugins.
        if dialect == "claude" and rel.startswith(claude_dirs):
            items += _hooks_from_settings(project.path(rel), "project")
            items += _mcp_from(data, project.path(rel), "project")
            for plugin, on in sorted((data.get("enabledPlugins") or {}).items()):
                items.append({"kind": "plugin", "name": plugin, "description": "enabled" if on else "disabled",
                              "source": "project", "path": project.path(rel), "owner": ""})
            continue
        items += _mcp_from(data, project.path(rel), "project")
    for rule in sorted(glob.glob(project.path(".cursor/rules/*.mdc"))):
        fm = _frontmatter(_read(rule, 20000))
        items.append({"kind": "rule", "name": os.path.basename(rule), "description": fm.get("description", ""),
                      "source": "project", "path": rule, "owner": owner_of(rule)})
    for h in (kit.get("installed") or {}).get("harnesses", []):
        if h.get("exists"):
            items.append({"kind": "harness", "name": h["file"], "description": h.get("role", ""),
                          "source": "project", "path": project.path(h["file"]),
                          "owner": "kit" if h.get("wired") else "project", "detail": {"wired": bool(h.get("wired"))}})
    other = []
    # Other kits, then the directories of tools whose files this lens does not read
    # itself (no hook dialect), from their harness records.
    others = [(".specify", "Spec Kit"), ("openspec", "OpenSpec"), (".sdlc", "sdlc skills (.sdlc)"),
              (".kiro", "Kiro")]
    others += [(rel, title) for rel, _, dialect, title in tool_dirs if dialect is None]
    for rel, label in others:
        if os.path.exists(project.path(rel)):
            count = sum(1 for _ in _walk(project.path(rel), max_depth=4)) if os.path.isdir(project.path(rel)) else 1
            other.append({"name": label, "path": rel, "files": count})

    if include_user:
        home = os.path.expanduser("~")
        cl = os.path.join(home, ".claude")
        items += _skills_in(os.path.join(cl, "skills"), "user", lambda p: "user")
        items += _md_items(os.path.join(cl, "commands"), "command", "user", lambda p: "user")
        items += _md_items(os.path.join(cl, "agents"), "subagent", "user", lambda p: "user")
        user_settings = os.path.join(cl, "settings.json")
        if os.path.exists(user_settings):
            items += _hooks_from_settings(user_settings, "user")
            data = _json(user_settings) or {}
            items += _mcp_from(data, user_settings, "user")
            for plugin, on in sorted((data.get("enabledPlugins") or {}).items()):
                items.append({"kind": "plugin", "name": plugin, "description": "enabled" if on else "disabled",
                              "source": "user", "path": user_settings, "owner": "user"})
        state = _json(os.path.join(home, ".claude.json")) or {}
        items += _mcp_from(state, os.path.join(home, ".claude.json"), "user")
        proj = ((state.get("projects") or {}).get(project.root) or {})
        items += _mcp_from(proj, os.path.join(home, ".claude.json"), "user")
        installed = _json(os.path.join(cl, "plugins", "installed_plugins.json")) or {}
        for name, entries in sorted((installed.get("plugins") or {}).items()):
            entry = entries[0] if isinstance(entries, list) and entries else (entries if isinstance(entries, dict) else {})
            if not any(i["kind"] == "plugin" and i["name"] == name for i in items):
                items.append({"kind": "plugin", "name": name, "description": "installed " + str(entry.get("version", "")),
                              "source": "user", "path": os.path.join(cl, "plugins"), "owner": "user"})
            root = entry.get("installPath") or ""
            if root and os.path.isdir(os.path.join(root, "skills")):
                for s in _skills_in(os.path.join(root, "skills"), "user", lambda p: "user"):
                    s["name"] = name.split("@")[0] + ":" + s["name"]
                    items.append(s)

    for i in items:
        i["path"] = _tilde(i["path"]) if i["source"] == "user" else os.path.relpath(i["path"], project.root).replace(os.sep, "/")
        i.setdefault("detail", {})
    names = {}
    for i in items:
        if i["kind"] in ("skill", "command", "subagent", "mcp"):
            names.setdefault((i["kind"], i["name"].split(":")[-1]), []).append(i)
    issues = []
    mirrored_skills = set()
    for (kind, name), group in sorted(names.items()):
        if len(group) > 1:
            is_kit_mirror = (
                kind == "skill" and len(group) == 2
                and all(g.get("owner") == "kit" and g.get("source") == "project" for g in group)
                and set(g["path"].split("/")[0] for g in group) == set((".claude", ".agents"))
            )
            if is_kit_mirror:
                for i in group:
                    i["state"] = "ok"
                    if i["path"].startswith(".agents/"):
                        mirrored_skills.add(i["path"])
                continue
            for i in group:
                i["state"] = "duplicate"
            issues.append({"level": "warn", "title": "%s %s is defined %d times" % (kind, name, len(group)),
                           "detail": ", ".join(g["path"] for g in group)})
    for i in items:
        i.setdefault("state", "modified" if i.get("owner") == "kit-modified" else "ok")
        if i["kind"] in ("skill", "subagent") and not i["description"]:
            issues.append({"level": "warn", "title": "%s %s has no description" % (i["kind"], i["name"]),
                           "detail": i["path"] + " — agents choose skills by their description"})
    modified = [rel for rel, digest in managed.items() if os.path.exists(project.path(rel)) and owner_of(project.path(rel)) == "kit-modified"]
    missing = [rel for rel in managed if not os.path.exists(project.path(rel))]
    if missing:
        issues.append({"level": "warn", "title": "%d kit file(s) missing" % len(missing), "detail": ", ".join(missing[:5])})
    always_words = sum(len(i["description"].split()) for i in items
                       if i["kind"] == "skill" and i["path"] not in mirrored_skills)
    counts = {}
    for i in items:
        counts.setdefault(i["kind"], {}).setdefault(i["source"], 0)
        counts[i["kind"]][i["source"]] += 1
    return {
        "items": items,
        "counts": counts,
        "other_kits": other,
        "kit_files": {"managed": len(managed), "modified": len(modified), "missing": len(missing), "modified_list": modified[:20]},
        "always_loaded_tokens": int(always_words * 1.35),
        "roles": (kit.get("installed") or {}).get("roles", []),
        "guards": (kit.get("installed") or {}).get("guards", {}),
        "includes_user": bool(include_user),
        "issues": issues,
    }


# ---------------------------------------------------------------- security

def security(project, alerts, audit, cont, env, reviews):
    """Everything with a security consequence, worst first."""
    out = []
    for v in (audit or {}).get("vulns", []):
        out.append({"level": "fail" if v["severity"] in ("critical", "high") else "warn", "area": "dependency",
                    "title": "%s %s: %s" % (v["package"], v["version"], v.get("title") or v.get("id")),
                    "detail": "%s · fix: %s" % (v["severity"], v.get("fix") or "none listed"), "ref": v.get("id", "")})
    for a in alerts or []:
        if a.get("check") in ("sensitive", "secrets", "privacy"):
            out.append({"level": a["level"], "area": "secret", "title": a["message"].split(". ")[0], "detail": a.get("where", ""),
                        "ref": "", "from": "doctor"})
    for f in (env or {}).get("env_files", []):
        if f["tracked"]:
            out.append({"level": "fail", "area": "secret", "title": "%s is committed to git" % f["file"],
                        "detail": "remove it from the index and rotate what it held", "ref": ""})
        elif not f["ignored"]:
            out.append({"level": "warn", "area": "secret", "title": "%s is not git-ignored" % f["file"],
                        "detail": "add it to .gitignore before it is committed", "ref": ""})
    for d in (cont or {}).get("dockerfiles", []):
        for r in d["risks"]:
            out.append({"level": "fail" if "secret" in r else "warn", "area": "container", "title": r, "detail": d["path"], "ref": ""})
    for c in (cont or {}).get("compose", []):
        for r in c["risks"]:
            out.append({"level": "fail" if "literal value" in r else "warn", "area": "container", "title": r, "detail": c["path"], "ref": ""})
    for r in reviews or []:
        out.append({"level": "warn", "area": "review", "title": r["title"], "detail": r["detail"], "ref": r.get("path", "")})
    rank = {"fail": 0, "warn": 1, "info": 2}
    out.sort(key=lambda x: (rank.get(x["level"], 3), x["area"]))
    return out


def security_reviews(project, model):
    """Security, privacy and threat-model records with open Block or High findings."""
    out = []
    for d in (model or {}).get("docs", []):
        path = d.get("path", "")
        if not re.search(r"(security|privacy|threat)", path, re.I):
            continue
        text = _read(project.path(path), 200000)
        open_high = len(re.findall(r"\b(Block|Blocker|High)\b(?![^\n]*\b(resolved|fixed|closed|waived)\b)", text))
        if open_high:
            out.append({"title": "%s: %d open Block/High finding(s)" % (os.path.basename(path), open_high),
                        "detail": "review record", "path": path})
    return out


# ---------------------------------------------------------------- assembly

# ---------------------------------------------------------------- coding standards

# (tool, kind, file names or globs at the root). pyproject/setup.cfg sections are read below.
STANDARD_CONFIGS = (
    ("EditorConfig", "editor", (".editorconfig",)),
    ("Prettier", "formatter", (".prettierrc", ".prettierrc.*", "prettier.config.*")),
    ("ESLint", "linter", (".eslintrc", ".eslintrc.*", "eslint.config.*")),
    ("Biome", "formatter", ("biome.json", "biome.jsonc")),
    ("Stylelint", "linter", (".stylelintrc", ".stylelintrc.*", "stylelint.config.*")),
    ("TypeScript", "types", ("tsconfig.json",)),
    ("Ruff", "linter", ("ruff.toml", ".ruff.toml")),
    ("Black", "formatter", ()),
    ("isort", "formatter", (".isort.cfg",)),
    ("Flake8", "linter", (".flake8",)),
    ("mypy", "types", ("mypy.ini", ".mypy.ini")),
    ("Pylint", "linter", (".pylintrc", "pylintrc")),
    ("RuboCop", "linter", (".rubocop.yml",)),
    ("rustfmt", "formatter", ("rustfmt.toml", ".rustfmt.toml")),
    ("Clippy", "linter", ("clippy.toml", ".clippy.toml")),
    ("golangci-lint", "linter", (".golangci.yml", ".golangci.yaml", ".golangci.toml")),
    ("clang-format", "formatter", (".clang-format",)),
    ("PHP CS Fixer", "formatter", (".php-cs-fixer.php", ".php-cs-fixer.dist.php")),
    ("PHP_CodeSniffer", "linter", ("phpcs.xml", "phpcs.xml.dist")),
    ("SwiftLint", "linter", (".swiftlint.yml",)),
    ("markdownlint", "linter", (".markdownlint.json", ".markdownlint.yaml", ".markdownlint.yml", ".markdownlintrc")),
    ("pre-commit", "hooks", (".pre-commit-config.yaml",)),
    ("Husky", "hooks", (".husky",)),
    ("commitlint", "hooks", ("commitlint.config.*", ".commitlintrc", ".commitlintrc.*")),
)
PY_SECTIONS = (("Ruff", r"^\[tool\.ruff"), ("Black", r"^\[tool\.black\]"), ("isort", r"^\[tool\.isort\]"),
               ("mypy", r"^\[tool\.mypy\]|^\[mypy\]"), ("Pylint", r"^\[tool\.pylint"), ("Flake8", r"^\[flake8\]"))
PKG_KEYS = (("Prettier", "prettier"), ("ESLint", "eslintConfig"), ("Stylelint", "stylelint"), ("commitlint", "commitlint"))

NAMING_LANGS = {
    ".py": "Python", ".js": "JavaScript/TypeScript", ".jsx": "JavaScript/TypeScript", ".mjs": "JavaScript/TypeScript",
    ".cjs": "JavaScript/TypeScript", ".ts": "JavaScript/TypeScript", ".tsx": "JavaScript/TypeScript",
    ".go": "Go", ".rb": "Ruby", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".php": "PHP",
}
# (function names, type names) per language; the first non-empty group is the name.
NAMING_RES = {
    "Python": (r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", r"^\s*class\s+([A-Za-z_]\w*)"),
    "JavaScript/TypeScript": (
        r"\bfunction\s+([A-Za-z_$][\w$]*)|\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
        r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
        r"\bclass\s+([A-Za-z_$][\w$]*)|\b(?:interface|type)\s+([A-Z][\w$]*)\b"),
    "Go": (r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", r"^type\s+([A-Za-z_]\w*)\s+(?:struct|interface)"),
    "Ruby": (r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*)", r"^\s*(?:class|module)\s+([A-Z]\w*)"),
    "Rust": (r"\bfn\s+([A-Za-z_]\w*)", r"\b(?:struct|enum|trait)\s+([A-Za-z_]\w*)"),
    "Java": (r"^\s*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?[\w<>\[\],\s]+?\s+([a-zA-Z_]\w*)\s*\(",
             r"\b(?:class|interface|enum|record)\s+([A-Za-z_]\w*)"),
    "Kotlin": (r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?([A-Za-z_]\w*)", r"\b(?:class|interface|object)\s+([A-Za-z_]\w*)"),
    "C#": (r"^\s*(?:public|private|protected|internal)\s+(?:static\s+|async\s+|override\s+|virtual\s+)*"
           r"[\w<>\[\],?\s]+?\s+([A-Za-z_]\w*)\s*\(", r"\b(?:class|interface|struct|record|enum)\s+([A-Za-z_]\w*)"),
    "PHP": (r"\bfunction\s+([A-Za-z_]\w*)", r"\b(?:class|interface|trait)\s+([A-Za-z_]\w*)"),
}
TEST_FILE = re.compile(r"^(test_.+\.py|.+_test\.py|.+\.(?:test|spec)\.[cm]?[jt]sx?|.+_test\.go|.+_spec\.rb|"
                       r"Test\w+\.(?:java|kt)|\w+Tests?\.(?:java|kt|cs))$")
TEST_PATTERNS = (("test_*.py", r"^test_.+\.py$"), ("*_test.py", r"_test\.py$"), ("*.test.*", r"\.test\.[cm]?[jt]sx?$"),
                 ("*.spec.*", r"\.spec\.[cm]?[jt]sx?$"), ("*_test.go", r"_test\.go$"), ("*_spec.rb", r"_spec\.rb$"),
                 ("Test* / *Test", r"^Test\w+\.|Tests?\.(?:java|kt|cs)$"))
TEST_DIRS = ("tests", "test", "__tests__", "spec", "specs", "testing")
CONVENTIONAL = re.compile(r"^([a-z]+)(\(([^)]*)\))?!?: \S")
TICKET = re.compile(r"^\[?[A-Z][A-Z0-9]+-\d+\]?[:\s]")
MAX_STANDARD_FILES = 1500
GENERIC_STEMS = ("index", "__init__", "__main__", "main", "mod", "lib", "conftest", "setup")


def _case(name):
    n = name.strip("_$")
    if not n or n.isdigit():
        return None
    if re.match(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$", n):
        return "SCREAMING_SNAKE_CASE"
    if re.match(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$", n):
        return "snake_case"
    if re.match(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$", n):
        return "kebab-case"
    if re.match(r"^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$", n):
        return "camelCase"
    if re.match(r"^[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*$", n):
        return "PascalCase"
    return None  # one lowercase word, or all capitals: says nothing about a style


def _dominant(names):
    counts = {}
    for n in names:
        c = _case(n)
        if c:
            counts[c] = counts.get(c, 0) + 1
    if not counts:
        return "", counts
    return max(sorted(counts), key=lambda k: counts[k]), counts


def _tooling(project):
    found, seen = [], set()

    def add(tool, kind, path, via=""):
        if tool not in seen:
            seen.add(tool)
            found.append({"tool": tool, "kind": kind, "path": path, "via": via})
    for tool, kind, names in STANDARD_CONFIGS:
        for pattern in names:
            hits = sorted(glob.glob(project.path(pattern)))
            if hits:
                add(tool, kind, _rel(project, hits[0]))
                break
    kinds = dict((t, k) for t, k, _ in STANDARD_CONFIGS)
    for cfg in ("pyproject.toml", "setup.cfg", "tox.ini"):
        text = _read(project.path(cfg), 400000)
        for tool, pattern in PY_SECTIONS:
            if text and re.search(pattern, text, re.M):
                add(tool, kinds.get(tool, "linter"), cfg, "section")
    pkg = _json(project.path("package.json"))
    if isinstance(pkg, dict):
        for tool, key in PKG_KEYS:
            if key in pkg:
                add(tool, kinds.get(tool, "linter"), "package.json", key)
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        for name in ("format", "lint", "typecheck"):
            if name in scripts:
                found.append({"tool": "npm script: " + name, "kind": "script", "path": "package.json",
                              "via": str(scripts[name])[:120]})
    return found


def _test_layout(test_files):
    in_dirs, beside, dirs, patterns = 0, 0, {}, set()
    for rel in test_files:
        parts = rel.split("/")
        hit = next((p for p in parts[:-1] if p in TEST_DIRS), None)
        if hit:
            in_dirs += 1
            dirs[hit] = dirs.get(hit, 0) + 1
        else:
            beside += 1
        for pat, rx in TEST_PATTERNS:
            if re.search(rx, parts[-1]):
                patterns.add(pat)
    top = max(sorted(dirs), key=lambda k: dirs[k]) if dirs else ""
    if not test_files:
        layout = "no test files found"
    elif in_dirs and not beside:
        layout = "separate %s/ directory" % top
    elif beside and not in_dirs:
        layout = "next to the source"
    else:
        layout = "mixed: %d in %s/, %d next to the source" % (in_dirs, top, beside)
    return {"layout": layout, "count": len(test_files), "dirs": sorted(dirs), "patterns": sorted(patterns),
            "examples": test_files[:5]}


def _commits(git_log):
    subjects = [s.strip() for s in (git_log or "").splitlines() if s.strip()]
    types, scopes, conv, ticket = {}, {}, 0, 0
    for s in subjects:
        m = CONVENTIONAL.match(s)
        if m:
            conv += 1
            types[m.group(1)] = types.get(m.group(1), 0) + 1
            if m.group(3):
                scopes[m.group(3)] = scopes.get(m.group(3), 0) + 1
        elif TICKET.match(s):
            ticket += 1
    n = len(subjects)
    if not n:
        convention = "no commits"
    elif conv * 10 >= n * 6:
        convention = "Conventional Commits"
    elif ticket * 10 >= n * 6:
        convention = "ticket-prefixed"
    else:
        convention = "free-form"
    return {"sampled": n, "convention": convention, "conventional": conv, "ticket_prefixed": ticket,
            "types": types, "scopes": dict(sorted(scopes.items(), key=lambda x: (-x[1], x[0]))[:10]),
            "examples": subjects[:5]}


def standards(project, git_log=None):
    """The conventions the code already follows: formatter and linter configs, naming style
    by language, test layout, import style and the commit convention. Read-only: walks the
    tree (skipping vendored and generated directories) and reads the last 200 commit
    subjects through `git log`; it never runs a formatter or linter."""
    names, imports, test_files, scanned = {}, {}, [], 0
    for path in _walk(project.root, max_depth=6):
        base = os.path.basename(path)
        lang = NAMING_LANGS.get(os.path.splitext(base)[1].lower())
        if not lang:
            continue
        scanned += 1
        if scanned > MAX_STANDARD_FILES:
            break
        is_test = bool(TEST_FILE.match(base))
        if is_test:
            test_files.append(_rel(project, path))
        text = _read(path, 200000)
        slot = names.setdefault(lang, {"functions": [], "classes": [], "files": []})
        stem = base.split(".")[0]
        if stem not in GENERIC_STEMS and not is_test:
            slot["files"].append(stem)
        fn_re, cls_re = NAMING_RES[lang]
        for regex, key in ((fn_re, "functions"), (cls_re, "classes")):
            for m in re.finditer(regex, text, re.M):
                name = next((g for g in m.groups() if g), "")
                if name and not name.startswith("__") and not (key == "functions" and name.startswith("test")):
                    slot[key].append(name)
        if lang in ("Python", "JavaScript/TypeScript"):
            c = imports.setdefault(lang, {"language": lang, "absolute": 0, "relative": 0, "alias": 0})
            if lang == "Python":
                c["relative"] += len(re.findall(r"^\s*from\s+\.", text, re.M))
                c["absolute"] += len(re.findall(r"^\s*(?:from\s+[A-Za-z_]|import\s+[A-Za-z_])", text, re.M))
            else:
                for spec in re.findall(r"(?:\bfrom\s+|\bimport\s+|\brequire\()\s*['\"]([^'\"]+)['\"]", text):
                    if spec.startswith("."):
                        c["relative"] += 1
                    elif spec[:2] in ("@/", "~/") or spec.startswith("#"):
                        c["alias"] += 1
                    else:
                        c["absolute"] += 1
    naming = []
    for lang in sorted(names):
        slot = names[lang]
        if not (slot["functions"] or slot["classes"]):
            continue
        row = {"language": lang}
        for key in ("functions", "classes", "files"):
            row[key], row[key + "_counts"] = _dominant(slot[key])
        row["samples"] = sorted(set(n for n in slot["functions"] if _case(n) == row["functions"]))[:6]
        row["class_samples"] = sorted(set(n for n in slot["classes"] if _case(n) == row["classes"]))[:4]
        naming.append(row)
    for c in imports.values():
        total = c["absolute"] + c["relative"] + c["alias"]
        c["style"] = ("none found" if not total else "mostly relative" if c["relative"] * 2 > total
                      else "mostly path aliases" if c["alias"] * 2 > total else "mostly absolute")
    if git_log is None:
        git_log = project.git("log", "-n", "200", "--no-merges", "--format=%s") if hasattr(project, "git") else ""
    return {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tooling": _tooling(project), "naming": naming, "tests": _test_layout(test_files),
            "imports": [imports[k] for k in sorted(imports)], "commits": _commits(git_log),
            "files_scanned": min(scanned, MAX_STANDARD_FILES)}


def standards_markdown(std):
    """A draft standards page from what the code does today: a starting point for people
    to correct, never a ruling. Every line says what was observed."""
    out = ["# Coding standards", "",
           "> Draft, written by `sdlc.py lens --area standards --write` on %s from what the code "
           "does today." % std["generated"][:10],
           "> Review it: correct what is wrong, keep what the team agrees to, then remove this note.", "",
           "## Formatting and linting", ""]
    if std["tooling"]:
        for t in std["tooling"]:
            extra = (" - `%s`" % t["via"]) if t["kind"] == "script" else (" (%s)" % t["via"] if t["via"] else "")
            out.append("- **%s** (%s): `%s`%s" % (t["tool"], t["kind"], t["path"], extra))
        out += ["", "Run the configured tools rather than formatting by hand against them."]
    else:
        out.append("- No formatter or linter config found. Unknown: choose one and record it here.")
    out += ["", "## Naming", ""]
    for n in std["naming"]:
        bits = ["functions %s" % (n["functions"] or "unclear"), "types %s" % (n["classes"] or "unclear")]
        if n["files"]:
            bits.append("files %s" % n["files"])
        line = "- **%s**: %s." % (n["language"], ", ".join(bits))
        seen = n["samples"][:4] + n["class_samples"][:2]
        if seen:
            line += " Seen: %s." % ", ".join("`%s`" % s for s in seen)
        out.append(line)
    if not std["naming"]:
        out.append("- No source files sampled.")
    t = std["tests"]
    out += ["", "## Tests", "", "- Layout: %s (%d test file(s))." % (t["layout"], t["count"])]
    if t["patterns"]:
        out.append("- File names: %s." % ", ".join("`%s`" % p for p in t["patterns"]))
    out += ["", "## Imports", ""]
    for i in std["imports"]:
        out.append("- **%s**: %s (%d absolute, %d relative, %d alias)." % (
            i["language"], i["style"], i["absolute"], i["relative"], i["alias"]))
    if not std["imports"]:
        out.append("- No imports sampled.")
    c = std["commits"]
    out += ["", "## Commits", "", "- Convention: %s (%d of the last %d subjects follow Conventional Commits)." % (
        c["convention"], c["conventional"], c["sampled"])]
    if c["types"]:
        out.append("- Types in use: %s." % ", ".join(
            "`%s` %d" % (k, v) for k, v in sorted(c["types"].items(), key=lambda x: (-x[1], x[0]))))
    if c["scopes"]:
        out.append("- Common scopes: %s." % ", ".join("`%s`" % k for k in c["scopes"]))
    out.append("")
    return "\n".join(out)


def lens(rt, project, model=None, include_user=False, detect_mod=None):
    if detect_mod is None:
        import detect as detect_mod  # noqa: F811
    model = model or {}
    kit = model.get("kit") or (rt.kit_status(project) if hasattr(rt, "kit_status") else {})
    alerts = model.get("alerts")
    if alerts is None:
        try:
            alerts = rt.doctor(project)
        except Exception:
            alerts = []
    evidence = model.get("evidence") or []
    if not evidence and hasattr(rt, "evidence_dir"):
        try:
            import view as _view
            evidence = _view.evidence_runs(project)
        except Exception:
            evidence = []
    try:
        st = stack(project, detect_mod)
    except Exception as exc:  # a detector bug is never a reason for the lens to fail
        st = {"groups": [], "error": str(exc), "deploy": [], "deploy_labels": [], "components": [], "integrations": [], "commands": {}}
    deps = dependencies(project)
    build = build_errors(project, evidence)
    aud = latest_audit(project)
    cont = containers(project)
    env = env_report(project)
    ci = workflows(project)
    ag = agents(project, kit, include_user)
    sec = security(project, alerts, aud, cont, env, security_reviews(project, model))
    failing_stages = [s for s in build["stages"] if s["failed"]]
    vulns = (aud or {}).get("vulns", [])
    summary = {
        "stack": {"languages": next((g["values"] for g in st["groups"] if g["label"] == "languages"), []),
                  "frameworks": next((g["values"] for g in st["groups"] if g["label"] == "frameworks"), []),
                  "dependencies": deps["total"], "manifests": len(deps["manifests"])},
        "build": {"run": build["run"], "failing": [s["stage"] for s in failing_stages],
                  "errors": sum(len(s["errors"]) for s in failing_stages)},
        "security": {"fail": sum(1 for s in sec if s["level"] == "fail"), "warn": sum(1 for s in sec if s["level"] == "warn"),
                     "vulns": len(vulns), "critical_high": sum(1 for v in vulns if v["severity"] in ("critical", "high")),
                     "audited": (aud or {}).get("generated", "")},
        "deploy": {"platforms": st.get("deploy_labels", []), "workflows": len(ci), "deploying_workflows": sum(1 for w in ci if w["deploys"]),
                   "dockerfiles": len(cont["dockerfiles"]), "compose_services": sum(len(c["services"]) for c in cont["compose"])},
        "env": {"variables": len(env["variables"]), "missing_from_template": len(env["missing_from_template"]),
                "templates": len(env["templates"]), "env_files": len(env["env_files"])},
        "agents": {"skills": sum(1 for i in ag["items"] if i["kind"] == "skill"), "commands": sum(1 for i in ag["items"] if i["kind"] == "command"),
                   "subagents": sum(1 for i in ag["items"] if i["kind"] == "subagent"), "mcp": sum(1 for i in ag["items"] if i["kind"] == "mcp"),
                   "hooks": sum(1 for i in ag["items"] if i["kind"] == "hook"), "plugins": sum(1 for i in ag["items"] if i["kind"] == "plugin"),
                   "issues": len(ag["issues"]), "always_loaded_tokens": ag["always_loaded_tokens"], "other_kits": [o["name"] for o in ag["other_kits"]]},
    }
    return {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": summary, "stack": st, "dependencies": deps, "build": build, "audit": aud,
            "containers": cont, "workflows": ci, "env": env, "agents": ag, "security": sec}


def lens_summary(full):
    """What a static export carries: counts and the worst findings, no inventories."""
    return {"generated": full["generated"], "summary": full["summary"],
            "security_top": full["security"][:10],
            "build_top": [dict(s, errors=s["errors"][:5]) for s in full["build"]["stages"] if s["failed"]][:5],
            "summary_only": True}


def watched(project):
    """Files whose change should rebuild the lens."""
    paths = []
    for rel in ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Gemfile", "composer.json",
                "Dockerfile", "docker-compose.yml", "compose.yml", "compose.yaml", ".mcp.json",
                ".claude/settings.json", ".claude/settings.local.json", ".ai-sdlc/manifest.json"):
        paths.append(project.path(rel))
    for pattern in (".github/workflows/*", ".claude/skills/*/SKILL.md", ".agents/skills/*/SKILL.md",
                    ".claude/commands/*.md", ".claude/agents/*.md", ".env*", "requirements*.txt",
                    ".ai-sdlc/evidence/*/summary.json", ".ai-sdlc/evidence/*-audit/audit.json"):
        paths += glob.glob(project.path(pattern))
    return sorted(paths)

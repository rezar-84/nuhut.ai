"""The Project lens: everything a repository is made of, in one read-only report.

Stack and dependencies, build errors from the last verify run, vulnerable packages from
the last `sdlc.py audit`, deployment and CI, containers, environment variable names, the
agentic stack (skills, commands, subagents, hooks, MCP servers, plugins, harness files,
other kits) and the security findings across all of them.

It never runs a tool and never touches the network: build errors come from logs `verify`
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
        lock, here = [], os.path.dirname(path)
        while not lock:
            lock = [os.path.relpath(os.path.join(here, f), project.root).replace(os.sep, "/")
                    for f in LOCKFILES.get(kind, ())
                    if os.path.exists(os.path.join(here, f))]
            if os.path.abspath(here) == os.path.abspath(project.root) or len(here) <= len(project.root):
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
    for rel in (".claude/settings.json", ".claude/settings.local.json"):
        if os.path.exists(project.path(rel)):
            items += _hooks_from_settings(project.path(rel), "project")
            data = _json(project.path(rel)) or {}
            items += _mcp_from(data, project.path(rel), "project")
            for plugin, on in sorted((data.get("enabledPlugins") or {}).items()):
                items.append({"kind": "plugin", "name": plugin, "description": "enabled" if on else "disabled",
                              "source": "project", "path": project.path(rel), "owner": ""})
    items += _mcp_from(_json(project.path(".mcp.json")), project.path(".mcp.json"), "project")
    gem = _json(project.path(".gemini/settings.json"))
    if gem:
        items += _mcp_from(gem, project.path(".gemini/settings.json"), "project")
    cursor_mcp = _json(project.path(".cursor/mcp.json"))
    if cursor_mcp:
        items += _mcp_from(cursor_mcp, project.path(".cursor/mcp.json"), "project")
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
    for rel, label in ((".specify", "Spec Kit"), ("openspec", "OpenSpec"), (".sdlc", "sdlc skills (.sdlc)"),
                       (".kiro", "Kiro"), (".windsurf", "Windsurf"), (".roo", "Roo"), (".clinerules", "Cline")):
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
    for (kind, name), group in sorted(names.items()):
        if len(group) > 1:
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
    always_words = sum(len(i["description"].split()) for i in items if i["kind"] == "skill")
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

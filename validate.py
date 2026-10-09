#!/usr/bin/env python3
"""Validate the distributable kit using only the Python standard library."""

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ALLOWED_PLACEHOLDERS = {"DOCS_DIR", "KIT_VERSION", "PLACEHOLDER", "PREFIX", "PROJECT_NAME"}
PLACEHOLDER = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def markdown_files():
    yield ROOT / "README.md"
    for base in (ROOT / "template", ROOT / "optional"):
        for path in sorted(base.rglob("*.md")):
            yield path


def frontmatter_fields(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return set()
    try:
        end = lines.index("---", 1)
    except ValueError:
        return set()
    return {line.split(":", 1)[0].strip() for line in lines[1:end] if ":" in line}


def cross_references(errors):
    """The kit names the same things in several places — a role in the wizard, in the
    charter's roster, in the roles README, and as a playbook file; a template in the
    docs map and on disk; a check stage in the gates document and in the charter. Each
    pairing is a place an addition can be made once and forgotten once, and nothing
    else in this repository would notice."""
    sys.path.insert(0, str(ROOT))
    import install                                     # noqa: E402  (path set above)

    roles_dir = ROOT / "template" / "docs" / "roles"
    on_disk = {p.stem for p in roles_dir.glob("*.md") if p.stem != "README"}

    # Ask the real function rather than reading its source: a project with every fact
    # true selects every role the installer can ever select.
    w = install.Wizard.__new__(install.Wizard)
    w.a = dict((fid, True) for fid in install.FACT_IDS)
    w.a["multilingual"] = True
    w.det = install.Detected()
    wizard = set(w.active_roles())

    charter = (ROOT / "template" / "docs" / "project" / "charter.md").read_text(encoding="utf-8")
    charter_roles = set(re.findall(r"^\| ([a-z][a-z-]+) \| [\u2611\u2610] \|", charter, re.M))
    readme_roles = set(re.findall(r"^\| \[([a-z-]+)\]\(",
                                  (roles_dir / "README.md").read_text(encoding="utf-8"), re.M))

    for name in sorted(wizard - on_disk):
        errors.append("install.py activates role %r with no playbook in roles/" % name)
    for name in sorted(on_disk - wizard):
        errors.append("roles/%s.md exists but install.py never activates it" % name)
    for name in sorted(wizard - charter_roles):
        errors.append("role %r is activated but has no row in the charter roster" % name)
    for name in sorted(on_disk - readme_roles):
        errors.append("roles/%s.md is missing from the roles README roster" % name)

    # Templates: on disk, and named in the docs map's "Create when" table.
    tpl_dir = ROOT / "template" / "docs" / "templates"
    tpl_disk = {p.name for p in tpl_dir.glob("*.md")}
    docs_map = (ROOT / "template" / "docs" / "README.md").read_text(encoding="utf-8")
    tpl_listed = set(re.findall(r"^\| `([a-z-]+\.md)` \|", docs_map, re.M))
    for name in sorted(tpl_disk - tpl_listed):
        errors.append("templates/%s is not listed in the docs map's Create when table" % name)
    for name in sorted(tpl_listed - tpl_disk):
        errors.append("the docs map lists templates/%s, which does not exist" % name)

    # Skills: every rule names a directory, every directory has a rule.
    skill_dirs = {p.name for p in (ROOT / "optional" / "skills").iterdir() if p.is_dir()}
    ruled = {name for name, _, _, _ in install.SKILL_RULES}
    for name in sorted(skill_dirs - ruled):
        errors.append("optional/skills/%s has no rule in SKILL_RULES" % name)
    for name in sorted(ruled - skill_dirs):
        errors.append("SKILL_RULES names %r, which has no skill directory" % name)

    # Check stages: every key in the gates table has a charter row and a wizard field.
    gates = (ROOT / "template" / "docs" / "process" / "04-quality-gates.md").read_text(encoding="utf-8")
    staged = set(re.findall(r"`checks\.([a-z0-9]+)`", gates))
    charter_keys = set(re.findall(r"^\| `checks\.([a-z0-9]+)` \|", charter, re.M))
    wizard_keys = {key for _, _, key in install.CMD_FIELDS} - {"install", "run"}
    for key in sorted(staged - charter_keys):
        errors.append("04-quality-gates names checks.%s with no charter Commands row" % key)
    for key in sorted(staged - wizard_keys):
        errors.append("04-quality-gates names checks.%s that the installer never asks for" % key)
    for key in sorted(wizard_keys - charter_keys):
        errors.append("the installer asks for checks.%s with no charter Commands row" % key)

    # Harnesses: every alias names a pointer the table actually knows how to write.
    known = {rel for rel, _ in install.HARNESS_POINTERS}
    for alias, targets in sorted(install.HARNESS_ALIASES.items()):
        for rel in targets:
            if rel not in known:
                errors.append("--harness %s names %r, absent from HARNESS_POINTERS"
                              % (alias, rel))
    for rel, _ in install.HARNESS_POINTERS:
        if not any(rel in t for t in install.HARNESS_ALIASES.values()):
            errors.append("HARNESS_POINTERS lists %r that no --harness value selects" % rel)

    # Modes: installer enums and every portable source of truth must agree.
    mode_sources = {
        "AGENTS.md": (ROOT / "template" / "AGENTS.md").read_text(encoding="utf-8"),
        "CARD.md": (ROOT / "template" / "docs" / "CARD.md").read_text(encoding="utf-8"),
        "operating model": (ROOT / "template" / "docs" / "process" /
                            "00-operating-model.md").read_text(encoding="utf-8"),
        "charter": charter,
    }
    for label, text in mode_sources.items():
        for mode in install.EFFORT_KEYS.values():
            if mode not in text:
                errors.append("%s does not name effort mode %s" % (label, mode))
    if set(install.EFFORT_KEYS.values()) != {"Lean", "Normal", "Beast"}:
        errors.append("install.py effort modes must be Lean, Normal, and Beast")
    if set(install.ACQUISITION_KEYS.values()) != {"Standard", "Advanced"}:
        errors.append("install.py acquisition profiles must be Standard and Advanced")

    # Deployment platforms: every id has a checklist, every checklist an id, and the
    # index lists each one. A platform the wizard offers with no file installs nothing.
    plat_dir = ROOT / "optional" / "platforms"
    plat_disk = {p.stem for p in plat_dir.glob("*.md") if p.stem != "README"}
    plat_ids = set(install.DEPLOY_IDS)
    plat_index = set(re.findall(r"^\| `([a-z0-9-]+)\.md` \|",
                                (plat_dir / "README.md").read_text(encoding="utf-8"), re.M))
    for name in sorted(plat_ids - plat_disk):
        errors.append("DEPLOY_PLATFORMS names %r with no optional/platforms/%s.md" % (name, name))
    for name in sorted(plat_disk - plat_ids):
        errors.append("optional/platforms/%s.md has no DEPLOY_PLATFORMS entry" % name)
    for name in sorted(plat_disk ^ plat_index):
        errors.append("optional/platforms/README.md and the checklists disagree on %r" % name)
    if "**Deployment platforms**" not in charter:
        errors.append("the charter has no Deployment platforms row for the installer to fill")

    # Facts: every fact has a label, and every type maps to known facts.
    for fid in install.FACT_IDS:
        if fid not in install.FACT_LABELS:
            errors.append("fact %r has no label in FACT_LABELS" % fid)
    for index, facts in install.TYPE_FACTS.items():
        if not 1 <= index <= len(install.PROJECT_TYPES):
            errors.append("TYPE_FACTS has an entry %r with no project type" % index)
        for fid in facts:
            if fid not in install.FACT_IDS:
                errors.append("project type %d claims unknown fact %r" % (index, fid))
    for index in range(1, len(install.PROJECT_TYPES) + 1):
        if index not in install.TYPE_FACTS:
            errors.append("project type %d has no TYPE_FACTS entry" % index)


def card_fidelity(errors):
    """CARD.md compresses standards, so it can silently gain a rule none of them
    has, or keep one after the standard changed. A summary that drifts is worse than no
    summary: it is read instead of the thing it misrepresents."""
    card_path = ROOT / "template" / "docs" / "CARD.md"
    if not card_path.is_file():
        errors.append("template/docs/CARD.md is missing")
        return
    card = card_path.read_text(encoding="utf-8")
    docs = ROOT / "template" / "docs"

    sources = ("process/00-operating-model.md", "process/02-role-reviews.md", "process/04-quality-gates.md",
               "process/06-evidence-and-claims.md", "process/07-traceability.md")
    for rel in sources:
        if rel not in card:
            errors.append("CARD.md summarises %s without linking to it" % rel)
    corpus = "\n".join((docs / rel).read_text(encoding="utf-8") for rel in sources)

    # Read the rules the card actually asserts, rather than checking a list of the ones
    # it is expected to have: an allowlist cannot catch an invented rung, which is the
    # failure this guard exists for.
    asserted = set(re.findall(r"\*\*(S[0-9]+)\*\*", card))
    asserted |= set(re.findall(r"^\| \*\*([A-Z][A-Za-z ]+)\*\* \|", card, re.M))
    for term in sorted(asserted):
        if term not in corpus:
            errors.append("CARD.md asserts %r, which appears in none of the four "
                          "standards it summarises" % term)
    for term in ("Verified", "Reported", "Assumed", "Unknown", "Not run", "Absent",
                 "Measured", "Pass with conditions", "Block", "S0", "S1", "S2", "S3", "S4"):
        if term not in card:
            errors.append("CARD.md no longer states %r" % term)
    for term in ("Ready", "Blocked", "In progress", "In review", "Parked", "Done",
                 "Deferred", "Dropped"):
        if term not in corpus:
            errors.append("CARD.md lists backlog status %r, absent from "
                          "07-traceability.md" % term)

    # The backlog row is positional, so the card's copy must match column for column.
    row = re.search(r"\| ID \| Task \| Tier \| Owner role \| Depends on \| Status \|", card)
    if not row:
        errors.append("CARD.md no longer states the backlog row in its specified order")
    elif not re.search(re.escape(row.group(0)),
                       (docs / "process/07-traceability.md").read_text(encoding="utf-8")):
        errors.append("CARD.md's backlog row disagrees with 07-traceability.md")

    # Everything the routing table sends a reader to has to exist.
    for rel in sorted(set(re.findall(r"`((?:process|roles|templates)/[a-z0-9-]+\.md)`", card))):
        if not (docs / rel).is_file():
            errors.append("CARD.md routes to %s, which does not exist" % rel)

    always = ("CARD.md", "project/charter.md", "project/backlog.md")
    agents = (ROOT / "template" / "AGENTS.md").read_text(encoding="utf-8")
    for rel in always:
        if rel not in agents:
            errors.append("AGENTS.md's reading list no longer names %s" % rel)
    for rel in sources:
        if rel not in agents:
            errors.append("AGENTS.md no longer names %s as escalation" % rel)


def dashboard_fidelity(errors):
    """The status page restates the backlog's status values and reads the charter's role
    and command tables. Like CARD.md it can drift from the standard it displays, and a
    status page that is confidently wrong is the failure this kit exists to prevent."""
    page = ROOT / "template" / "docs" / "dashboard.html"
    if not page.is_file():
        errors.append("template/docs/dashboard.html is missing")
        return
    html = page.read_text(encoding="utf-8")
    trace = (ROOT / "template" / "docs" / "process" / "07-traceability.md").read_text(
        encoding="utf-8")

    # Only the Status values table defines statuses; 07 has other tables of bold terms.
    section = trace.split("### Status values", 1)[-1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    statuses = set(re.findall(r"^\| \*\*([A-Z][a-z ]+)\*\* \|", section, re.M))
    if not statuses:
        errors.append("07-traceability.md no longer has a parseable Status values table")
    declared = set(re.findall(r'"([A-Z][a-z]+(?: [a-z]+)?)":\s*"b?-?[a-z-]*"', html))
    for status in sorted(declared - statuses):
        errors.append("dashboard.html knows backlog status %r, absent from "
                      "07-traceability.md" % status)
    for status in sorted(statuses):
        if status not in html:
            errors.append("dashboard.html does not handle backlog status %r" % status)

    if "dashboard-state.js" not in html:
        errors.append("dashboard.html no longer loads its state file")
    for marker in ("staleness_days", "SDLC_STATE", "AGENTS.md"):
        if marker not in html:
            errors.append("dashboard.html no longer references %s" % marker)
    if "contenteditable" in html or "<form" in html:
        errors.append("dashboard.html must stay read-only: it is not a second source of "
                      "truth for the charter")


def reading_budget(errors):
    """AGENTS.md quotes the size of the docs tree so an agent can bound its reading.
    The figure is load-bearing and nothing keeps it honest, so measure it. Four
    characters per token is rough on purpose — this catches drift, not accuracy."""
    text = (ROOT / "template" / "AGENTS.md").read_text(encoding="utf-8")
    m = re.search(r"is around ([0-9,]+)\ntokens", text) or re.search(r"is around ([0-9,]+) tokens", text)
    if not m:
        errors.append("AGENTS.md no longer states the size of the docs tree")
        return
    stated = int(m.group(1).replace(",", ""))
    chars = sum(len(p.read_text(encoding="utf-8"))
                for p in (ROOT / "template" / "docs").rglob("*.md"))
    actual = chars / 4.0
    if abs(actual - stated) > 0.1 * actual:
        errors.append("AGENTS.md says the docs tree is ~%s tokens; it measures ~%d. "
                      "Update the figure (and the per-tier totals under it)."
                      % (m.group(1), round(actual, -2)))


def main():
    errors = []
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not VERSION_RE.match(version):
        errors.append("VERSION is not semantic major.minor.patch: %r" % version)

    # The plugin manifest carries its own version string and drifts silently otherwise.
    manifest = ROOT / ".claude-plugin" / "plugin.json"
    if manifest.is_file():
        try:
            plugin = json.loads(manifest.read_text(encoding="utf-8"))
        except ValueError:
            plugin = None
            errors.append(".claude-plugin/plugin.json is not valid JSON")
        if plugin is not None:
            if plugin.get("version") != version:
                errors.append(".claude-plugin/plugin.json says version %r, VERSION says %r"
                              % (plugin.get("version"), version))
            if "skills" in plugin:
                errors.append(".claude-plugin/plugin.json ships skills globally; they are "
                              "model-invoked and cost context every turn, so they are "
                              "chosen per project by the installer instead")
            rel = plugin.get("commands", "")
            if rel and not (ROOT / rel.lstrip("./")).is_dir():
                errors.append(".claude-plugin/plugin.json points commands at %r, which "
                              "does not exist" % rel)
        market = ROOT / ".claude-plugin" / "marketplace.json"
        if not market.is_file():
            errors.append(".claude-plugin/plugin.json exists without marketplace.json")

    required_root = ("LICENSE", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md")
    for name in required_root:
        if not (ROOT / name).is_file():
            errors.append("missing repository file: %s" % name)

    for name in ("sdlc.py", "view.py", "view.html"):
        runtime = ROOT / "optional" / "runtime" / name
        if not runtime.is_file():
            errors.append("missing runtime file: optional/runtime/%s" % name)
        elif "{{" in runtime.read_text(encoding="utf-8"):
            errors.append("optional/runtime/%s contains a double brace, which the installer "
                          "would substitute; spell it '[{][{]'" % name)
    for rel in ("optional/runtime/sdlc.py", "benchmarks/effort-modes/score.py",
                "benchmarks/kit-value/score.py", "benchmarks/kit-value/measure.py"):
        script = ROOT / rel
        if not script.is_file():
            errors.append("missing script: %s" % rel)
            continue
        proc = subprocess.run([sys.executable, str(script), "--selftest"],
                              cwd=str(ROOT), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, universal_newlines=True)
        if proc.returncode:
            errors.append("%s self-test failed: %s" % (rel, proc.stdout[-500:]))
    for task in sorted((ROOT / "benchmarks" / "kit-value" / "tasks").iterdir()):
        for name in ("prompt.md", "accept.sh", "safety.sh", "repo"):
            if task.is_dir() and not (task / name).exists():
                errors.append("kit-value task %s is missing %s" % (task.name, name))

    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        unknown = sorted(set(PLACEHOLDER.findall(text)) - ALLOWED_PLACEHOLDERS)
        if unknown:
            errors.append("%s has unknown placeholders: %s" %
                          (path.relative_to(ROOT), ", ".join(unknown)))
        for target in LINK.findall(text):
            clean = target.split("#", 1)[0]
            if not clean or "://" in clean or clean.startswith(("#", "mailto:")):
                continue
            if not (path.parent / clean).resolve().exists():
                errors.append("%s has broken link: %s" % (path.relative_to(ROOT), target))

    for path in sorted((ROOT / "template" / "docs" / "project").glob("*.md")):
        fields = frontmatter_fields(path)
        missing = {"status", "owner", "last-reviewed"} - fields
        if missing:
            errors.append("%s missing frontmatter fields: %s" %
                          (path.relative_to(ROOT), ", ".join(sorted(missing))))

    for path in sorted((ROOT / "optional" / "skills").glob("*/SKILL.md")):
        fields = frontmatter_fields(path)
        missing = {"name", "description"} - fields
        if missing:
            errors.append("%s missing skill frontmatter: %s" %
                          (path.relative_to(ROOT), ", ".join(sorted(missing))))

    # Exercise the advertised custom directory, not just source text. The installed
    # contract and commands must point at the actual location and contain no placeholders.
    target = Path(tempfile.mkdtemp(prefix="sdlc-validate-"))
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "install.py"), str(target), "VAL", "-y",
             "--docs-dir", "handbook"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True)
        if proc.returncode:
            errors.append("custom-directory install failed: %s" % proc.stdout[-500:])
        installed = [target / "AGENTS.md"]
        installed.extend(sorted((target / ".claude" / "commands").glob("*.md")))
        for path in installed:
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            if "{{" in text:
                errors.append("%s contains an unresolved placeholder" % path.relative_to(target))
            if re.search(r"(?<![A-Za-z0-9_-])docs/", text):
                errors.append("%s contains a stale docs/ path" % path.relative_to(target))
            if "handbook/" not in text:
                errors.append("%s does not reference handbook/" % path.relative_to(target))
        manifest = target / ".ai-sdlc" / "manifest.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("kit_version") != version or not data.get("files"):
                errors.append("installed manifest has wrong version or no managed files")
        except (IOError, OSError, ValueError):
            errors.append("installed manifest is missing or invalid")
        # The runtime finds the custom docs directory from the profile, not a baked path.
        proc = subprocess.run(
            [sys.executable, str(target / ".ai-sdlc" / "bin" / "sdlc.py"), "doctor", "--json"],
            cwd=str(target), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True)
        try:
            findings = json.loads(proc.stdout)
        except ValueError:
            findings = None
        if proc.returncode or not isinstance(findings, list):
            errors.append("installed runtime doctor failed: %s" % proc.stdout[-500:])
        elif any("charter is missing" in f.get("message", "") for f in findings):
            errors.append("installed runtime did not find handbook/project/charter.md")
    finally:
        shutil.rmtree(str(target), ignore_errors=True)

    cross_references(errors)
    card_fidelity(errors)
    dashboard_fidelity(errors)
    reading_budget(errors)

    if errors:
        for error in errors:
            print("FAIL  %s" % error)
        print("%d validation error(s)" % len(errors))
        return 1
    print("all kit validations passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

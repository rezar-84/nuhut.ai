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
PRIVATE_LEAK_RE = re.compile(
    r"(?i)(/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+|rubuntu|tasario|corpifind|lawkin|daadsolutions|\bTASA-[0-9]+)"
)


def markdown_files():
    yield ROOT / "README.md"
    for base in (ROOT / "template", ROOT / "optional", ROOT / "docs"):
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

    # Check stages: every key in the gates table has a charter row, a wizard field, and a runtime stage.
    sys.path.insert(0, str(ROOT / "optional" / "runtime"))
    import sdlc as runtime_sdlc                        # noqa: E402
    gates = (ROOT / "template" / "docs" / "process" / "04-quality-gates.md").read_text(encoding="utf-8")
    staged = set(re.findall(r"`checks\.([a-z0-9]+)`", gates))
    charter_keys = set(re.findall(r"^\| `checks\.([a-z0-9]+)` \|", charter, re.M))
    wizard_keys = {key for _, _, key in install.CMD_FIELDS} - {"install", "run"}
    runtime_stages = set(runtime_sdlc.STAGES)
    for key in sorted(staged - charter_keys):
        errors.append("04-quality-gates names checks.%s with no charter Commands row" % key)
    for key in sorted(staged - wizard_keys):
        errors.append("04-quality-gates names checks.%s that the installer never asks for" % key)
    for key in sorted(wizard_keys - charter_keys):
        errors.append("the installer asks for checks.%s with no charter Commands row" % key)
    for key in sorted(staged ^ runtime_stages):
        errors.append("04-quality-gates and sdlc.py STAGES disagree on checks.%s" % key)

    # Harnesses: every alias names a pointer the table actually knows how to write,
    # and the runtime doctor checks every pointer file the installer can wire.
    known = {rel for rel, _ in install.HARNESS_POINTERS}
    runtime_pointers = set(runtime_sdlc.POINTER_FILES) | {".cursor/rules/agents.mdc"}
    for rel in sorted(known ^ runtime_pointers):
        errors.append("install.py HARNESS_POINTERS and sdlc.py POINTER_FILES disagree on %r" % rel)
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


NUMBER_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                "fifteen sixteen seventeen eighteen nineteen twenty").split()


def number_word(n):
    if n <= 20:
        return NUMBER_WORDS[n]
    tens = {2: "twenty", 3: "thirty"}[n // 10]
    return tens + ("-" + NUMBER_WORDS[n % 10] if n % 10 else "")


def docs_stay_true(errors):
    """The user-facing docs describe what ships: every runtime command is documented, every
    viewer tab is described, every skill is listed and counted, and every image exists."""
    sdlc_src = (ROOT / "optional" / "runtime" / "sdlc.py").read_text(encoding="utf-8")
    commands = re.findall(r'sub\.add_parser\("([a-z-]+)"', sdlc_src)
    cli = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for cmd in commands:
        if "`%s" % cmd not in cli:
            errors.append("docs/cli.md does not document `sdlc.py %s`" % cmd)
        if not re.search(r"`%s\b" % re.escape(cmd), readme):
            errors.append("README.md's command list is missing `%s`" % cmd)
    shell = (ROOT / "optional" / "runtime" / "view" / "02-shell.html").read_text(encoding="utf-8")
    viewer_doc = (ROOT / "docs" / "viewer.md").read_text(encoding="utf-8")
    for label in re.findall(r'data-r="[a-z]+"[^>]*>([^<]+)</a>', shell):
        if "**%s**" % label.strip() not in viewer_doc:
            errors.append("docs/viewer.md does not describe the %s tab" % label.strip())
    skills_doc = (ROOT / "docs" / "skills.md").read_text(encoding="utf-8")
    skill_dirs = sorted(p.name for p in (ROOT / "optional" / "skills").iterdir() if p.is_dir())
    for name in skill_dirs:
        if "`%s`" % name not in skills_doc:
            errors.append("docs/skills.md does not list the %s skill" % name)
    count = number_word(len(skill_dirs))
    for doc in (ROOT / "docs" / "skills.md", ROOT / "docs" / "design.md"):
        text = doc.read_text(encoding="utf-8")
        for said in re.findall(r"\b([a-z]+(?:-[a-z]+)?) (?:model-invoked )?skills\b", text):
            if said in NUMBER_WORDS[2:] or said.startswith(("twenty", "thirty")):
                if said != count:
                    errors.append("%s says %s skills; optional/skills/ has %s" % (doc.relative_to(ROOT), said, count))
    for doc in [ROOT / "README.md"] + sorted((ROOT / "docs").glob("*.md")):
        text = doc.read_text(encoding="utf-8")
        for ref in re.findall(r'(?:src="|\]\()([^")#]+\.(?:png|jpe?g|svg|gif))', text):
            if ref.startswith("http"):
                continue
            if not (doc.parent / ref).resolve().exists():
                errors.append("%s shows %s, which does not exist" % (doc.relative_to(ROOT), ref))


def single_viewer(errors):
    """4.0 has one viewer. The retired static page must not come back, and the viewer's
    export must stay self-contained (no external scripts, nothing that edits records)."""
    if (ROOT / "template" / "docs" / "dashboard.html").exists():
        errors.append("template/docs/dashboard.html is back; sdlc.py view --export-html is "
                      "the static option")
    html = (ROOT / "optional" / "runtime" / "view.html").read_text(encoding="utf-8")
    # view.html is built from optional/runtime/view/ parts; the shipped file must match them.
    built = subprocess.run([sys.executable, str(ROOT / "tools" / "build_view.py"), "--check"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if built.returncode:
        errors.append(built.stdout.strip() or "view.html differs from its parts")
    if re.search(r"<script[^>]+src=", html):
        errors.append("view.html loads an external script; the export must be self-contained")
    if "contenteditable" in html or "<form" in html:
        errors.append("view.html must stay read-only")
    if html.lower().count("</script") != 2:
        errors.append("view.html must have exactly 2 </script> tags (model + app)")
    node_bin = shutil.which("node")
    if node_bin:
        for idx, block in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)):
            tmp_js = Path(tempfile.mktemp(suffix=".js", prefix="sdlc-view-"))
            try:
                tmp_js.write_text(block, encoding="utf-8")
                proc = subprocess.run([node_bin, "--check", str(tmp_js)],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      universal_newlines=True)
                if proc.returncode:
                    errors.append("view.html script block #%d failed node --check: %s"
                                  % (idx + 1, proc.stdout[-300:]))
            finally:
                try:
                    tmp_js.unlink()
                except OSError:
                    pass
    for doc in (ROOT / "README.md", ROOT / "template" / "docs" / "README.md",
                ROOT / "optional" / "claude-commands" / "sdlc-doctor.md"):
        if "dashboard-state.js" in doc.read_text(encoding="utf-8"):
            errors.append("%s still describes the retired dashboard-state.js" % doc.relative_to(ROOT))


# Each tier's reading list, as AGENTS.md section 3 states it, and its budget in words.
# Words, not tokens: a stable measure that needs no tokenizer. The lists are measured on
# the template files, so a document that grows past its tier's budget fails here.
AGENTS_MAX_WORDS = 1200
TIER_BUDGETS = {"3": 1500, "2": 5500, "1": 22000}
DEFAULT_ROLES = ("product-manager", "architect", "security", "qa")


def charter_section(text, heading):
    part = text.split("\n## %s\n" % heading, 1)
    return part[1].split("\n## ", 1)[0] if len(part) == 2 else ""


def reading_lists():
    """{tier: [(label, words)]} for the three tiers' reading lists."""
    docs = ROOT / "template" / "docs"

    def words(path):
        return len(path.read_text(encoding="utf-8").split())
    charter = (docs / "project" / "charter.md").read_text(encoding="utf-8")
    tier3 = [("AGENTS.md", words(ROOT / "template" / "AGENTS.md")),
             ("charter Commands rows", len(charter_section(charter, "Commands").split()))]
    tier2 = tier3 + [("CARD.md", words(docs / "CARD.md")),
                     ("project/backlog.md", words(docs / "project" / "backlog.md"))]
    tier1 = list(tier2) + [("project/charter.md (rest)",
                            words(docs / "project" / "charter.md") - tier3[1][1])]
    for rel in ("process/00-operating-model.md", "process/03-ready-and-done.md",
                "process/05-change-control.md", "templates/plan.md", "templates/adr.md",
                "templates/role-review.md"):
        tier1.append((rel, words(docs / rel)))
    for role in DEFAULT_ROLES:
        tier1.append(("roles/%s.md" % role, words(docs / "roles" / ("%s.md" % role))))
    return {"3": tier3, "2": tier2, "1": tier1}


def reading_budget(errors):
    """AGENTS.md is read on every change, so it has a hard ceiling; each tier's list has a
    budget; and the docs-tree size AGENTS.md quotes stays within 10% of the files (four
    characters per token, rough on purpose: this catches drift, not accuracy)."""
    text = (ROOT / "template" / "AGENTS.md").read_text(encoding="utf-8")
    count = len(text.split())
    if count > AGENTS_MAX_WORDS:
        errors.append("AGENTS.md is %d words; the ceiling is %d. Move detail to a process "
                      "document read on demand." % (count, AGENTS_MAX_WORDS))
    for tier, items in sorted(reading_lists().items()):
        total = sum(n for _, n in items)
        if total > TIER_BUDGETS[tier]:
            errors.append("Tier %s reading list is %d words; its budget is %d (%s)"
                          % (tier, total, TIER_BUDGETS[tier],
                             ", ".join("%s %d" % item for item in items)))
    for rel in ("project/charter.md", "CARD.md", "project/backlog.md"):
        if rel not in text:
            errors.append("AGENTS.md's reading list no longer names %s" % rel)
    m = re.search(r"is around\s+([0-9,]+)\s+tokens", text)
    if not m:
        errors.append("AGENTS.md no longer states the size of the docs tree")
        return
    stated = int(m.group(1).replace(",", ""))
    chars = sum(len(p.read_text(encoding="utf-8"))
                for p in (ROOT / "template" / "docs").rglob("*.md"))
    actual = chars / 4.0
    if abs(actual - stated) > 0.1 * actual:
        errors.append("AGENTS.md says the docs tree is ~%s tokens; it measures ~%d. "
                      "Update the figure." % (m.group(1), round(actual, -2)))


def print_reading_lists():
    for tier, items in sorted(reading_lists().items(), reverse=True):
        print("Tier %s: %d words (budget %d)" % (tier, sum(n for _, n in items),
                                                 TIER_BUDGETS[tier]))
        for label, n in items:
            print("  %6d  %s" % (n, label))


def no_private_leaks(errors):
    """The kit repository must never contain developer machine paths (/home/<user>,
    /Users/<user>) or private project names."""
    proc = subprocess.run(["git", "ls-files"], cwd=str(ROOT), stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, universal_newlines=True)
    paths = [ROOT / p for p in proc.stdout.splitlines() if p.strip()]
    for extra in (ROOT / "docs").glob("*.md"):
        if extra not in paths:
            paths.append(extra)
    for path in paths:
        if path.name == "validate.py" or not path.is_file():
            continue
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pyc"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = PRIVATE_LEAK_RE.search(text)
        if match:
            errors.append("%s contains private machine path or project name: %r"
                          % (path.relative_to(ROOT), match.group(0)))


def main():
    if sys.argv[1:] == ["--reading-lists"]:
        print_reading_lists()
        return 0
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

    required_root = ("LICENSE", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md",
                     "install.py", "install_ui.py")
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
    single_viewer(errors)
    docs_stay_true(errors)
    reading_budget(errors)
    no_private_leaks(errors)

    if errors:
        for error in errors:
            print("FAIL  %s" % error)
        print("%d validation error(s)" % len(errors))
        return 1
    print("all kit validations passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

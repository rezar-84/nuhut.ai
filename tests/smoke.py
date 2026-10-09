#!/usr/bin/env python3
"""Smoke tests for install.py. Standard library only.

    python3 tests/smoke.py [-v]

Every test installs into a throwaway directory under the system temp dir. The wizard runs
through a pty, driven by rules of the form "prompt substring" -> "answer", so the tests
exercise the same prompt loop a person sees rather than a private API.
"""

import hashlib
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "install.py")
VERBOSE = "-v" in sys.argv
ANSI = re.compile(r"\x1b\[[0-9;]*m")

sys.path.insert(0, ROOT)
import install as installer

failures = []


def run(args, cwd=ROOT):
    p = subprocess.Popen([sys.executable, INSTALL] + args, cwd=cwd,
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8", "replace")


def drive(args, rules, timeout=60):
    """Run the wizard on a pty. `rules` is a list of (substring, answer); the first match
    against the text printed since the last prompt wins, otherwise Enter."""
    master, slave = pty.openpty()
    p = subprocess.Popen([sys.executable, INSTALL] + args, cwd=ROOT,
                         stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    buf, log, deadline = b"", [], time.time() + timeout
    used = set()
    while time.time() < deadline and p.poll() is None:
        ready, _, _ = select.select([master], [], [], 0.3)
        if ready:
            try:
                chunk = os.read(master, 8192)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            log.append(chunk)
            continue
        text = ANSI.sub("", buf.decode("utf-8", "replace"))
        buf = b""
        answer = ""
        for i, (needle, reply) in enumerate(rules):
            if needle in text and i not in used:
                answer, _ = reply, used.add(i)
                break
        try:
            os.write(master, (answer + "\n").encode("utf-8"))
        except OSError:
            break
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
    os.close(master)
    return p.returncode, ANSI.sub("", b"".join(log).decode("utf-8", "replace"))


def check(name, condition, detail=""):
    if condition:
        print("  ok    %s" % name)
    else:
        print("  FAIL  %s%s" % (name, (" -- " + detail) if detail else ""))
        failures.append(name)


def fixture(kind):
    d = tempfile.mkdtemp(prefix="sdlc-%s-" % kind)
    if kind == "next":
        write(d, "package.json", """{"dependencies":{"next":"15","@prisma/client":"6",
            "next-auth":"5","stripe":"14","@sentry/nextjs":"8"},
            "scripts":{"dev":"next dev","build":"next build","test":"vitest run"}}""")
        write(d, "tsconfig.json", "{}")
        write(d, "prisma/schema.prisma", 'datasource db {\n  provider = "postgresql"\n}\n')
    elif kind == "fastapi":
        write(d, "pyproject.toml", 'dependencies = ["fastapi", "pytest", "ruff"]\n')
    elif kind == "astro-i18n":
        write(d, "package.json", '{"dependencies":{"astro":"4","astro-i18next":"2"}}')
        for locale in ("en", "fa", "tr"):
            write(d, "locales/%s/common.json" % locale, "{}")
    elif kind == "monorepo":
        write(d, "package.json", '{"workspaces":["apps/*","packages/*"]}')
        write(d, "pnpm-workspace.yaml", "packages:\n  - apps/*\n")
        for part in ("apps/web", "apps/api", "packages/ui"):
            write(d, "%s/package.json" % part, "{}")
        write(d, "docker-compose.yml", "services:\n  db:\n    image: postgres\n  cache:\n    image: redis\n")
    return d


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def read(root, rel):
    try:
        with open(os.path.join(root, rel)) as fh:
            return fh.read()
    except IOError:
        return ""


def files(root):
    return sum(len(f) for _, _, f in os.walk(root))


# ---------------------------------------------------------------- tests

def test_guards():
    print("guards")
    code, out = run([ROOT, "ACME", "-y"])
    check("refuses the kit itself", code == 1 and "refusing" in out, out.strip()[:90])
    code, out = run([os.path.join(ROOT, "template"), "ACME", "-y"])
    check("refuses a path inside the kit", code == 1 and "inside the kit" in out)
    code, out = run(["-y"])
    check("no target, no terminal -> usage", code == 1 and "usage:" in out)
    missing = os.path.join(tempfile.gettempdir(), "sdlc-nope-%d" % os.getpid())
    code, out = run([missing, "ACME", "-y"])
    check("missing directory without --create", code == 1 and "no such directory" in out)
    code, out = run([missing, "ACME", "-y", "--create"])
    check("--create makes it", code == 0 and os.path.isdir(missing))
    shutil.rmtree(missing, ignore_errors=True)

    if hasattr(os, "symlink"):
        d = tempfile.mkdtemp(prefix="sdlc-link-target-")
        outside = tempfile.mkdtemp(prefix="sdlc-link-outside-")
        os.symlink(outside, os.path.join(d, ".claude"))
        code, out = run([d, "ACME", "-y"])
        check("refuses a destination symlink escape",
              code == 1 and "escapes project" in out and files(outside) == 0)
        check("symlink refusal happens before installation",
              not os.path.exists(os.path.join(d, "AGENTS.md")))
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)

    check("user text cannot inject a second Markdown line",
          installer.plain_text("Jane: Doe\n# injected {{PREFIX}}") ==
          "Jane: Doe # injected { {PREFIX} }")

    orig_no_color = os.environ.get("NO_COLOR")
    orig_term = os.environ.get("TERM")
    try:
        os.environ["NO_COLOR"] = "1"
        term = installer.Term()
        check("NO_COLOR disables bold ANSI", term.B == "")
        check("NO_COLOR disables dim ANSI", term.D == "")
        check("NO_COLOR disables reset ANSI", term.R == "")
        os.environ.pop("NO_COLOR", None)
        os.environ["TERM"] = "dumb"
        term_dumb = installer.Term()
        check("TERM=dumb disables bold ANSI", term_dumb.B == "")
    finally:
        if orig_no_color is not None:
            os.environ["NO_COLOR"] = orig_no_color
        else:
            os.environ.pop("NO_COLOR", None)
        if orig_term is not None:
            os.environ["TERM"] = orig_term
        else:
            os.environ.pop("TERM", None)


def test_non_interactive():
    print("non-interactive (-y)")
    d = tempfile.mkdtemp(prefix="sdlc-y-")
    code, out = run([d, "ACME", "-y"])
    check("exit 0", code == 0)
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json"))
    check("managed manifest written", bool(manifest))
    check("portable README and templates are upgrade-managed",
          "docs/README.md" in manifest.get("files", {}) and
          "docs/templates/test-plan.md" in manifest.get("files", {}))
    check("no leftover placeholders", "{{" not in read(d, "docs/project/charter.md"))
    check("charter not tailored", "_(one sentence a stranger would understand)_"
          in read(d, "docs/project/charter.md"))
    skills = sorted(os.listdir(os.path.join(d, ".claude", "skills")))
    check("only answer-independent skills", skills == ["sdlc-adr", "sdlc-charter-audit",
                                                       "sdlc-doctor", "sdlc-evidence-check",
                                                       "sdlc-intake"],
          str(skills))
    before = files(d)
    run([d, "ACME", "-y"])
    check("re-run adds nothing", files(d) == before)
    code, out = run([d, "--upgrade"])
    check("upgrade recovers the prefix", "Recovered prefix from charter: ACME" in out)
    check("upgrade touches only standards", "project/charter.md" not in out)
    shutil.rmtree(d, ignore_errors=True)


def test_dry_run():
    print("--dry-run")
    d = tempfile.mkdtemp(prefix="sdlc-dry-")
    code, out = run([d, "ACME", "-y", "--dry-run"])
    check("writes nothing", code == 0 and files(d) == 0 and "would add" in out)
    shutil.rmtree(d, ignore_errors=True)

    d = os.path.join(tempfile.gettempdir(), "sdlc-dry-create-%d" % os.getpid())
    shutil.rmtree(d, ignore_errors=True)
    code, out = run([d, "ACME", "-y", "--create", "--dry-run"])
    check("--dry-run --create leaves no directory", code == 0 and not os.path.exists(d))


def test_custom_docs_dir():
    print("--docs-dir")
    d = tempfile.mkdtemp(prefix="sdlc-custom-")
    code, out = run([d, "ACME", "-y", "--docs-dir", "handbook"])
    installed = [read(d, "AGENTS.md")]
    for name in ("sdlc-log.md", "sdlc-plan.md", "sdlc-review.md", "sdlc-verify.md"):
        installed.append(read(d, ".claude/commands/%s" % name))
    check("exit 0", code == 0)
    check("contract and commands use custom path",
          all("handbook/" in text and not re.search(r"(?<![A-Za-z0-9_-])docs/", text)
              for text in installed))
    check("no unresolved placeholders", all("{{" not in text for text in installed))
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json"))
    check("manifest records custom path", manifest.get("docs_dir") == "handbook")
    code, out = run([d, "--upgrade"])
    check("upgrade recovers custom path from manifest",
          code == 0 and "handbook portable docs" in out)
    shutil.rmtree(d, ignore_errors=True)


def test_managed_upgrade():
    print("managed upgrade")
    d = tempfile.mkdtemp(prefix="sdlc-upgrade-")
    run([d, "ACME", "-y"])
    manifest_path = os.path.join(d, ".ai-sdlc", "manifest.json")
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json"))

    changed_rel = "docs/process/00-operating-model.md"
    changed_path = os.path.join(d, changed_rel)
    with open(changed_path, "a") as fh:
        fh.write("\nlegacy-version-marker\n")
    with open(changed_path, "rb") as fh:
        changed_bytes = fh.read()
    manifest["files"][changed_rel] = hashlib.sha256(changed_bytes).hexdigest()

    obsolete_rel = "docs/process/obsolete.md"
    write(d, obsolete_rel, "old managed file\n")
    manifest["files"][obsolete_rel] = hashlib.sha256(b"old managed file\n").hexdigest()
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh)

    code, out = run([d, "--upgrade"])
    check("upgrade succeeds", code == 0, out[-300:])
    check("outdated managed file refreshed", "legacy-version-marker" not in read(d, changed_rel))
    check("obsolete managed file removed", not os.path.exists(os.path.join(d, obsolete_rel)))
    backups = os.path.join(d, ".ai-sdlc", "backups")
    check("affected files backed up", os.path.isdir(backups) and files(backups) >= 2)

    with open(changed_path, "a") as fh:
        fh.write("\nlocal project edit\n")
    code, out = run([d, "--upgrade"])
    check("local managed edit stops upgrade", code == 1 and "modified or removed" in out)
    check("local edit preserved", "local project edit" in read(d, changed_rel))
    shutil.rmtree(d, ignore_errors=True)


def test_command_detection():
    print("command detection")
    d = tempfile.mkdtemp(prefix="sdlc-detect-")
    write(d, "package.json", json.dumps({
        "dependencies": {"typescript": "5", "@playwright/test": "1"},
        "scripts": {
            "format:check": "prettier --check .", "lint": "eslint .",
            "test:unit": "vitest run", "test:integration": "vitest integration",
            "test:contract": "vitest contract", "test:a11y": "playwright test a11y",
            "test:e2e": "playwright test", "security": "audit-ci", "build": "tsc"
        }
    }))
    write(d, "package-lock.json", "{}")
    write(d, "tsconfig.json", "{}")
    cmds = installer.detect(d).cmds
    check("reproducible npm install detected", cmds.get("install") == "npm ci")
    check("all quality script families detected",
          all(key in cmds for key in ("format", "lint", "typecheck", "unit",
                                      "integration", "contract", "build", "scan",
                                      "a11y", "e2e")), str(cmds))
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-detect-go-")
    write(d, "go.mod", "module example.test/kit\n\ngo 1.22\n")
    cmds = installer.detect(d).cmds
    check("Go format gate is recursive and fails on drift",
          "find . -name '*.go'" in cmds.get("format", "") and
          cmds.get("format", "").startswith("test -z"), str(cmds))
    shutil.rmtree(d, ignore_errors=True)


def test_stack_adapters():
    print("language/database adapters")
    cases = [
        ("python", {
            "pyproject.toml": ('dependencies = ["sqlalchemy", "alembic", "psycopg", '
                               '"pytest", "hypothesis"]\n'),
            "alembic.ini": "[alembic]\n",
        }, ("python", "SQLAlchemy", "PostgreSQL", "Alembic", "pytest", "Hypothesis")),
        ("go", {
            "go.mod": ("module example.test/app\n\nrequire (\n gorm.io/gorm v1.0.0\n"
                       " github.com/jackc/pgx/v5 v5.0.0\n"
                       " github.com/stretchr/testify v1.0.0\n)\n"),
            "sqlc.yaml": "version: '2'\n",
        }, ("go", "GORM", "PostgreSQL", "sqlc", "testify")),
        ("rust", {
            "Cargo.toml": ('[package]\nname="x"\nversion="0.1.0"\n[dependencies]\n'
                           'sqlx="1"\nredis="1"\n[dev-dependencies]\nproptest="1"\n'),
            "migrations/001.sql": "select 1;\n",
        }, ("rust", "SQLx", "Redis", "proptest")),
        ("php", {
            "composer.json": json.dumps({
                "require": {"laravel/framework": "1", "ext-pdo_pgsql": "*"},
                "require-dev": {"pestphp/pest": "1"}, "scripts": {"test": "pest"}
            }),
        }, ("php", "Eloquent ORM", "PostgreSQL", "Laravel migrations", "Pest")),
        ("ruby", {
            "Gemfile": "gem 'rails'\ngem 'pg'\ngem 'rspec'\n",
        }, ("ruby", "Active Record", "PostgreSQL", "Rails migrations", "RSpec")),
        ("jvm-maven", {
            "pom.xml": ("<project><dependencies><dependency>spring-data-jpa</dependency>"
                        "<dependency>postgresql</dependency><dependency>flyway</dependency>"
                        "<dependency>junit</dependency><dependency>testcontainers</dependency>"
                        "</dependencies></project>"),
        }, ("jvm-maven", "JPA", "PostgreSQL", "Flyway", "JUnit", "Testcontainers")),
        ("jvm-gradle", {
            "build.gradle.kts": ('dependencies { implementation("org.hibernate:hibernate-core") '
                                 'testImplementation("org.testng:testng") }'),
        }, ("jvm-gradle", "Hibernate", "TestNG")),
        ("dotnet", {
            "App.csproj": ("<Project><ItemGroup>"
                           "<PackageReference Include=\"Microsoft.EntityFrameworkCore\" />"
                           "<PackageReference Include=\"Npgsql.EntityFrameworkCore.PostgreSQL\" />"
                           "<PackageReference Include=\"xunit\" />"
                           "<PackageReference Include=\"Testcontainers\" />"
                           "</ItemGroup></Project>"),
        }, ("dotnet", "Entity Framework Core", "PostgreSQL", "EF Core migrations",
             "xUnit", "Testcontainers")),
        ("deno", {
            "deno.json": json.dumps({"tasks": {"test": "deno test -A", "dev": "deno run -A server.ts"},
                                     "imports": {"hono": "jsr:@hono/hono@^4"}}),
        }, ("deno", "deno test")),
    ]
    for name, fixture_files, expected in cases:
        d = tempfile.mkdtemp(prefix="sdlc-adapter-%s-" % name)
        for rel, content in fixture_files.items():
            write(d, rel, content)
        found = installer.detect(d)
        haystack = found.adapters + found.db + found.migrations + found.test
        missing = [value for value in expected if value not in haystack]
        check("%s adapter" % name, not missing, "missing=%s found=%s" % (missing, haystack))
        shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-adapter-polyglot-")
    write(d, "package.json", json.dumps({"scripts": {"test": "vitest run"},
                                          "devDependencies": {"vitest": "1"}}))
    write(d, "requirements.txt", "pytest\nruff\npsycopg\n")
    found = installer.detect(d)
    check("polyglot adapters compose stage commands",
          found.adapters == ["node", "python"] and
          found.cmds.get("install") == "npm install && pip install -r requirements.txt" and
          found.cmds.get("unit") == "npm run test && pytest", str(found.cmds))
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-adapter-monorepo-")
    write(d, "package.json", json.dumps({"name": "root", "workspaces": ["apps/*", "packages/*"]}))
    write(d, "apps/web/package.json", json.dumps({"dependencies": {"next": "15", "tailwindcss": "3"}}))
    write(d, "apps/web/tsconfig.json", "{}")
    write(d, "packages/db/package.json", json.dumps({"dependencies": {"@prisma/client": "6"}}))
    write(d, "packages/db/prisma/schema.prisma", 'datasource db {\n  provider = "postgresql"\n}\n')
    found = installer.detect(d)
    check("monorepo workspace packages detected",
          "Next.js" in found.fw and "Tailwind CSS" in found.fw and
          "Prisma (postgresql)" in found.db and "Node.js + TypeScript" in found.lang,
          "fw=%s db=%s lang=%s" % (found.fw, found.db, found.lang))
    shutil.rmtree(d, ignore_errors=True)


def test_harness_wiring():
    print("agent instruction files point at AGENTS.md")

    # The defect: a project that already has CLAUDE.md must still be wired, or the kit
    # installs into permanent silence.
    d = tempfile.mkdtemp(prefix="sdlc-harness-existing-")
    write(d, "CLAUDE.md", "# My project\n\nRun npm test.\n")
    code, out = run([d, "HRN", "-y"])
    text = read(d, "CLAUDE.md")
    check("exit 0", code == 0, out[-300:])
    check("existing CLAUDE.md is pointed at AGENTS.md", "AGENTS.md" in text, text)
    check("its original content survives", "Run npm test." in text, text)
    check("the append is announced", "CLAUDE.md" in out, out[-400:])
    code, out = run([d, "HRN", "-y"])
    check("re-running adds no second pointer", text.count("AGENTS.md") ==
          read(d, "CLAUDE.md").count("AGENTS.md"), read(d, "CLAUDE.md"))
    shutil.rmtree(d, ignore_errors=True)

    # A fresh project gets only the harnesses that were asked for.
    d = tempfile.mkdtemp(prefix="sdlc-harness-multi-")
    code, out = run([d, "HRN", "-y", "--harness", "claude,cursor,copilot"])
    check("exit 0 for --harness", code == 0, out[-300:])
    for rel in ("CLAUDE.md", ".cursor/rules/agents.mdc", ".github/copilot-instructions.md"):
        check("%s written" % rel, "AGENTS.md" in read(d, rel), rel)
    check("unrequested harnesses are not written",
          not os.path.exists(os.path.join(d, "GEMINI.md")) and
          not os.path.exists(os.path.join(d, ".windsurfrules")), str(files(d)))
    profile = json.loads(read(d, ".ai-sdlc/profile.json") or "{}")
    check("profile records what was wired",
          "CLAUDE.md" in profile.get("harnesses", []), str(profile.get("harnesses")))
    shutil.rmtree(d, ignore_errors=True)

    code, out = run(["/tmp/sdlc-nonexistent-harness", "HRN", "-y", "--harness", "nope"])
    check("an unknown harness is rejected", code != 0 and "unknown harness" in out, out[-200:])

    # Native harness (antigravity) succeeds without creating unneeded pointer files
    d = tempfile.mkdtemp(prefix="sdlc-harness-native-")
    code, out = run([d, "HRN", "-y", "--harness", "antigravity"])
    check("native harness exit 0", code == 0, out[-300:])
    check("native harness announced", "reads AGENTS.md directly" in out, out[-300:])
    check("native harness creates no pointer file", not os.path.exists(os.path.join(d, "antigravity.md")))
    check("a native-only harness writes no CLAUDE.md", not os.path.exists(os.path.join(d, "CLAUDE.md")))
    shutil.rmtree(d, ignore_errors=True)

    # Roo Code and classic Cursor pointers
    d = tempfile.mkdtemp(prefix="sdlc-harness-roo-")
    code, out = run([d, "HRN", "-y", "--harness", "roo,cursor"])
    check("roo and cursor pointers exit 0", code == 0, out[-300:])
    check("roo rules pointer written", "AGENTS.md" in read(d, ".roo/rules/agents.md"))
    check("no .roomodes is invented", not os.path.exists(os.path.join(d, ".roomodes")))
    check(".cursorrules written", "AGENTS.md" in read(d, ".cursorrules"))
    shutil.rmtree(d, ignore_errors=True)


def test_profiles():
    print("documentation profiles")
    d = tempfile.mkdtemp(prefix="sdlc-profile-compact-")
    code, out = run([d, "CMP", "-y", "--profile", "compact"])
    check("exit 0", code == 0, out[-300:])
    check("the card is installed", "Operating card" in read(d, "docs/CARD.md"))
    check("numbered process documents are omitted",
          not os.path.exists(os.path.join(d, "docs", "process")) or
          not [f for f in os.listdir(os.path.join(d, "docs", "process")) if f[:2].isdigit()],
          str(os.listdir(os.path.join(d, "docs"))))
    check("roles and templates survive",
          os.path.isdir(os.path.join(d, "docs", "roles")) and
          os.path.isdir(os.path.join(d, "docs", "templates")))
    check("the card says the absence is deliberate",
          "compact profile" in read(d, "docs/CARD.md"), read(d, "docs/CARD.md")[-200:])
    profile = json.loads(read(d, ".ai-sdlc/profile.json") or "{}")
    check("profile.json records it", profile.get("profile") == "compact",
          str(profile.get("profile")))

    # An upgrade must find a compact install, and must not silently make it full.
    code, out = run([d, "CMP", "--upgrade"])
    check("compact installs can be upgraded", code == 0 and "nothing to upgrade" not in out,
          out[-300:])
    check("upgrade does not restore the omitted documents",
          not [f for f in os.listdir(os.path.join(d, "docs", "process"))
               if f[:2].isdigit()] if os.path.isdir(os.path.join(d, "docs", "process"))
          else True, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-profile-full-")
    code, out = run([d, "FUL", "-y"])
    check("full is the default", os.path.exists(
        os.path.join(d, "docs", "process", "00-operating-model.md")), out[-300:])
    check("full installs the card too", os.path.exists(os.path.join(d, "docs", "CARD.md")))
    check("full card carries no compact note",
          "compact profile" not in read(d, "docs/CARD.md"))
    shutil.rmtree(d, ignore_errors=True)

    code, out = run(["/tmp/sdlc-nonexistent-profile", "PRF", "-y", "--profile", "tiny"])
    check("an unknown profile is rejected", code != 0 and "full or compact" in out,
          out[-200:])


def test_hooks():
    print("opt-in enforcement hooks")
    d = os.path.realpath(tempfile.mkdtemp(prefix="sdlc-hooks-"))
    write(d, ".claude/settings.json", '{"permissions":{"allow":["Bash(npm *)"]}}')
    code, out = run([d, "HKT", "-y", "--hooks"])
    check("exit 0", code == 0, out[-300:])
    try:
        settings = json.loads(read(d, ".claude/settings.json"))
    except ValueError:
        settings = {}
    check("existing settings survive the merge",
          settings.get("permissions", {}).get("allow") == ["Bash(npm *)"], str(settings))
    entries = settings.get("hooks", {}).get("PreToolUse", [])
    check("all five hooks are registered", len(entries) == 5, str(entries))
    check("the commit hook is filtered to git commit",
          any(h.get("if") == "Bash(git commit*)"
              for e in entries for h in e.get("hooks", [])), str(entries))
    check("every hook is anchored on the project root",
          all(h.get("command", "").startswith('sh "$CLAUDE_PROJECT_DIR"/.claude/hooks/')
              for e in entries for h in e.get("hooks", [])), str(entries))
    check("the shared hook library is installed",
          os.path.isfile(os.path.join(d, ".claude", "hooks", "lib.sh")))
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json") or "{}")
    check("hooks are kit-managed", ".claude/hooks/test-lock.sh" in manifest.get("files", {})
          and ".claude/hooks/lib.sh" in manifest.get("files", {}), str(manifest)[:300])
    for name in ("protected.txt", "test-lock.txt", "gates.txt"):
        check("%s is seeded but empty of rules" % name,
              all(l.startswith("#") or not l.strip()
                  for l in read(d, ".ai-sdlc/" + name).splitlines()),
              read(d, ".ai-sdlc/" + name))

    # The behaviour, not just the wiring.
    def fire(script, payload, cwd=None, **extra):
        # CLAUDE_PROJECT_DIR is set explicitly: under Claude Code it names the kit.
        env = dict(os.environ, CLAUDE_PROJECT_DIR=d, **extra)
        p = subprocess.Popen(["sh", os.path.join(d, ".claude", "hooks", script)],
                             cwd=cwd or d, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        o, _ = p.communicate(json.dumps(payload).encode())
        return o.decode("utf-8", "replace")

    if shutil.which("jq"):
        out = fire("work-item-id.sh", {"tool_input": {"command": 'git commit -m "fix"'}})
        check("a commit with no ID is denied", '"permissionDecision":"deny"' in out, out)
        out = fire("work-item-id.sh", {"tool_input": {"command": 'git commit -m "HKT-9 fix"'}})
        check("a commit with an ID is allowed", "deny" not in out, out)
        out = fire("work-item-id.sh", {"tool_input": {"command": "ls"}})
        check("an unrelated command is allowed", "deny" not in out, out)
        out = fire("protected-paths.sh", {"tool_input": {"file_path": "package-lock.json"}})
        check("an unlisted path is allowed", "deny" not in out, out)
        with open(os.path.join(d, ".ai-sdlc", "protected.txt"), "a") as fh:
            fh.write("package-lock.json\n")
        out = fire("protected-paths.sh", {"tool_input": {"file_path": "package-lock.json"}})
        check("a listed path is denied", '"permissionDecision":"deny"' in out, out)

        out = fire("test-lock.sh", {"tool_input": {"file_path": "tests/test_bug.py"}})
        check("an unlocked test may be edited", "deny" not in out, out)
        with open(os.path.join(d, ".ai-sdlc", "test-lock.txt"), "a") as fh:
            fh.write("tests/test_bug.py\n")
        out = fire("test-lock.sh", {"tool_input": {"file_path": os.path.join(d, "tests/test_bug.py")}})
        check("a locked test is denied", '"permissionDecision":"deny"' in out, out)
        out = fire("test-lock.sh", {"tool_input": {"file_path": ".ai-sdlc/test-lock.txt"}})
        check("the lock list itself is denied", '"permissionDecision":"deny"' in out, out)
        out = fire("test-lock.sh", {"tool_input": {"file_path": "src/bug.py"}})
        check("the code under test may be edited", "deny" not in out, out)
        os.makedirs(os.path.join(d, "src"), exist_ok=True)
        out = fire("test-lock.sh", {"tool_input": {"file_path": "../tests/test_bug.py"}},
                   cwd=os.path.join(d, "src"))
        check("a lock holds when the call comes from a subdirectory",
              '"permissionDecision":"deny"' in out, out)
        out = fire("test-lock.sh", {"tool_input": {"file_path": "x/../tests/./test_bug.py"}})
        check("a lock holds through . and .. segments",
              '"permissionDecision":"deny"' in out, out)
        with open(os.path.join(d, ".ai-sdlc", "test-lock.txt"), "a") as fh:
            fh.write("tests/q*\n")
        out = fire("test-lock.sh", {"tool_input": {"file_path": 'tests/q"uote.py'}})
        try:
            decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
        except (ValueError, KeyError, TypeError):
            decision = None
        check("a quote in the filename still yields a valid deny", decision == "deny", out)
        out = fire("protected-paths.sh", {"tool_input": {"file_path": "../package-lock.json"}},
                   cwd=os.path.join(d, "src"))
        check("a protected path named from a subdirectory is denied",
              '"permissionDecision":"deny"' in out, out)

        out = fire("approval-gate.sh", {"tool_input": {"command": "make deploy ENV=prod"}})
        check("no gates, nothing denied", "deny" not in out, out)
        with open(os.path.join(d, ".ai-sdlc", "gates.txt"), "a") as fh:
            fh.write("*deploy*prod*\n")
        out = fire("approval-gate.sh", {"tool_input": {"command": "make deploy ENV=prod"}})
        check("a gated command is denied", '"permissionDecision":"deny"' in out, out)
        json.loads(out)  # the reason is quoted by jq, so the decision is valid JSON
        out = fire("approval-gate.sh", {"tool_input": {"command": "make deploy ENV=staging"}})
        check("an ungated command is allowed", "deny" not in out, out)
        out = fire("approval-gate.sh", {"tool_input": {"file_path": ".ai-sdlc/gates.txt"}})
        check("the gate list itself is denied", '"permissionDecision":"deny"' in out, out)
        o = fire("approval-gate.sh", {"tool_input": {"command": "make deploy ENV=prod"}},
                 AI_SDLC_APPROVAL="CHG-42")
        check("an approval passes the gate and is announced",
              "deny" not in o and "CHG-42" in o, o)
        o = fire("approval-gate.sh", {"tool_input": {"command": "make deploy ENV=prod"}},
                 cwd=os.path.join(d, "src"))
        check("a gate holds when the call comes from a subdirectory",
              '"permissionDecision":"deny"' in o, o)

        git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.call(git + ["init", "-q"], cwd=d)
        write(d, "cfg.py", "KEY = 'AKIA" + "ABCDEFGHIJKLMNOP'\n")
        subprocess.call(git + ["add", "cfg.py"], cwd=d)
        out = fire("secret-guard.sh", {"tool_input": {"command": 'git commit -am "HKT-1 x"'}})
        check("a credential in the first commit is denied, even with -a",
              '"permissionDecision":"deny"' in out, out)
        out = fire("secret-guard.sh", {"tool_input": {"command": 'git commit -m "HKT-1 x"'}})
        check("a staged credential is denied", '"permissionDecision":"deny"' in out, out)
        check("the denial never echoes the value", "ABCDEFGHIJKLMNOP" not in out, out)
        write(d, "cfg.py", "KEY = 'AKIAIOSFODNN7EXAMPLE'\n")
        subprocess.call(git + ["add", "cfg.py"], cwd=d)
        out = fire("secret-guard.sh", {"tool_input": {"command": 'git commit -m "HKT-1 x"'}})
        check("a marked fixture is allowed", "deny" not in out, out)
    else:
        check("jq present for hook behaviour tests", True, "skipped: jq not installed")

    profile = json.loads(read(d, ".ai-sdlc/profile.json"))
    profile["facts"]["marker_from_setup"] = True
    write(d, ".ai-sdlc/profile.json", json.dumps(profile))
    code, out = run([d, "HKT", "-y", "--hooks"])
    kept = json.loads(read(d, ".ai-sdlc/profile.json"))
    check("a non-interactive re-run keeps the project's profile",
          kept.get("facts", {}).get("marker_from_setup") is True, out[-300:])
    settings = json.loads(read(d, ".claude/settings.json"))
    check("re-running does not duplicate the hooks",
          len(settings.get("hooks", {}).get("PreToolUse", [])) == 5, str(settings))

    # An older install registered relative commands; both routes repair them in place.
    legacy = read(d, ".claude/settings.json").replace('sh \\"$CLAUDE_PROJECT_DIR\\"/', "sh ")
    check("fixture: legacy commands written", "sh .claude/hooks/" in legacy, legacy[:300])
    write(d, ".claude/settings.json", legacy)
    run([d, "HKT", "-y", "--hooks"])
    settings = json.loads(read(d, ".claude/settings.json"))
    commands = [h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
    check("--hooks rewrites legacy commands without duplicating them",
          len(commands) == 5 and all("$CLAUDE_PROJECT_DIR" in c for c in commands), str(commands))
    write(d, ".claude/settings.json", legacy)
    code, out = run([d, "HKT", "--upgrade"])
    settings = json.loads(read(d, ".claude/settings.json"))
    commands = [h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
    check("--upgrade anchors legacy hook commands",
          code == 0 and all("$CLAUDE_PROJECT_DIR" in c for c in commands), out[-400:])
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-nohooks-")
    run([d, "HKT", "-y"])
    check("hooks are never installed without the flag",
          not os.path.exists(os.path.join(d, ".claude", "hooks")))
    shutil.rmtree(d, ignore_errors=True)


def test_runtime():
    print("doctor and verify runtime")
    d = tempfile.mkdtemp(prefix="sdlc-runtime-")
    subprocess.call(["git", "init", "-q", d])
    code, out = run([d, "RTX", "-y"])
    check("exit 0", code == 0, out[-300:])
    script = os.path.join(d, ".ai-sdlc", "bin", "sdlc.py")
    check("the runtime is installed", os.path.isfile(script))
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json") or "{}")
    check("the runtime is kit-managed", ".ai-sdlc/bin/sdlc.py" in manifest.get("files", {}))
    check("the runtime survives substitution intact", "{" + "{" not in read(d, ".ai-sdlc/bin/sdlc.py"))

    def sdlc(*args):
        p = subprocess.Popen([sys.executable, script] + list(args), cwd=d,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        o, _ = p.communicate()
        return p.returncode, o.decode("utf-8", "replace")

    code, out = sdlc("doctor")
    check("doctor reports blank check rows on a fresh install", "checks.unit" in out, out)
    check("doctor exits 0 by default", code == 0, out)
    code, out = sdlc("doctor", "--strict")
    check("a fresh install has warnings, not failures", code == 0, out)

    charter = os.path.join(d, "docs", "project", "charter.md")
    text = read(d, "docs/project/charter.md")
    text = text.replace("| `checks.unit` | |", "| `checks.unit` | `true` |")
    text = text.replace("| `checks.lint` | |", "| `checks.lint` | `echo lint-output && false` |")
    text = text.replace("| `checks.build` | |", "| `checks.build` | absent |")
    with open(charter, "w") as fh:
        fh.write(text)
    code, out = sdlc("verify")
    check("verify fails when a stage fails", code == 1, out)
    runs = sorted(os.listdir(os.path.join(d, ".ai-sdlc", "evidence")))
    evidence = os.path.join(d, ".ai-sdlc", "evidence", [r for r in runs if r[0].isdigit()][-1])
    summary = json.loads(read(evidence, "summary.json") or "{}")
    results = dict((e["stage"], e["result"]) for e in summary.get("stages", []))
    check("each stage gets its evidence word",
          results.get("unit") == "Verified: pass" and results.get("lint") == "Verified: fail"
          and results.get("build") == "Absent (declared)"
          and results.get("e2e") == "Absent (no command in the charter)", str(results))
    check("the real output is kept", "lint-output" in read(evidence, "lint.log"))
    check("evidence is ignored by git",
          "*" in read(d, ".ai-sdlc/evidence/.gitignore"))
    check("profile drift is reported during verify", summary.get("drift"), str(summary))
    code, out = sdlc("verify", "--stage", "unit")
    check("a scoped run passes and marks the rest not run",
          code == 0 and "Not run (not selected)" in out, out)

    # A check that prints a credential must not leave it in the evidence.
    text = read(d, "docs/project/charter.md").replace(
        "| `checks.unit` | `true` |",
        "| `checks.unit` | `echo token=AKIA" + "ABCDEFGHIJKLMNOP` |")
    write(d, "docs/project/charter.md", text)
    code, out = sdlc("verify", "--stage", "unit")
    runs = sorted(r for r in os.listdir(os.path.join(d, ".ai-sdlc", "evidence")) if r[0].isdigit())
    log = read(os.path.join(d, ".ai-sdlc", "evidence", runs[-1]), "unit.log")
    check("verify masks credentials in the saved log",
          "ABCDEFGHIJKLMNOP" not in log and "[redacted: AWS access key]" in log, log)
    check("verify says a secret was printed", "masked in the logs" in out, out[-300:])
    write(d, "docs/project/charter.md", text.replace(
        "| `checks.unit` | `echo token=AKIA" + "ABCDEFGHIJKLMNOP` |", "| `checks.unit` | `true` |"))

    # Doctor: a runbook whose rollback never ran, and a lessons list grown too long.
    write(d, "docs/project/release-runbook.md",
          "# Runbook\n\n## Rollback\n\n**Last executed:** _(never)_\n")
    agents = read(d, "AGENTS.md") + "".join("- mistake %d\n" % n for n in range(40))
    write(d, "AGENTS.md", agents)
    code, out = sdlc("doctor")
    check("doctor warns about a rollback never rehearsed", "rollback" in out, out)
    check("doctor warns about an overlong lessons list", "known agent mistakes" in out, out)
    code, out = sdlc("metrics", "--json")
    try:
        names = [m["name"] for m in json.loads(out)]
    except ValueError:
        names = []
    check("metrics reports leading and lagging measures",
          "Verify pass rate" in names and "Lead time" in names, out[:300])

    write(d, "docs/project/worklog.md", read(d, "docs/project/worklog.md")
          + "\nRTX-7 shipped.\n")
    backlog = read(d, "docs/project/backlog.md").replace(
        "| ID | Task | Tier | Owner role | Depends on | Status | Completed |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n",
        "| ID | Task | Tier | Owner role | Depends on | Status | Completed |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| RTX-3 | Ship a thing | 2 | qa | | Done | 2026-01-01 |\n")
    write(d, "docs/project/backlog.md", backlog)
    os.remove(os.path.join(d, "CLAUDE.md"))
    code, out = sdlc("doctor", "--strict")
    check("a Done item with no worklog entry fails", "RTX-3" in out, out)
    check("a worklog ID missing from the backlog is reported", "RTX-7" in out, out)
    check("no contract pointer fails", "no instruction file names AGENTS.md" in out
          and code == 1, out)
    check("profile drift is reported by doctor", "profile.json commands" in out, out)

    # plan-check: the plan's file list against the branch's diff.
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.call(git + ["add", "-A"], cwd=d)
    subprocess.call(git + ["commit", "-qm", "RTX-1 install"], cwd=d)
    base = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                   cwd=d).decode().strip()
    subprocess.call(["git", "checkout", "-qb", "rtx-9"], cwd=d)
    write(d, "docs/project/plans/RTX-9.md",
          "# Plan\n## Files that change\n- `src/pay/**`\n- `docs/api.md`\n## Order of work\n")
    write(d, "src/pay/a.py", "x = 1\n")
    write(d, "stray.py", "y = 2\n")
    code, out = sdlc("plan-check", "RTX-9", "--base", base, "--json")
    try:
        result = json.loads(out)
    except ValueError:
        result = {}
    check("plan-check names the unplanned file", result.get("unplanned") == ["stray.py"], out)
    check("plan-check names the untouched planned path",
          result.get("untouched") == ["docs/api.md"], out)
    code, out = sdlc("plan-check", "RTX-9", "--base", base, "--strict")
    check("plan-check --strict fails on a gap", code == 1, out)
    code, out = sdlc("plan-check", "RTX-404", "--base", base)
    check("plan-check explains a missing plan", code == 2 and "no plan" in out, out)

    # An older install gains the runtime on upgrade; a local edit blocks it.
    os.remove(script)
    manifest["files"].pop(".ai-sdlc/bin/sdlc.py", None)
    write(d, ".ai-sdlc/manifest.json", json.dumps(manifest))
    code, out = run([d, "RTX", "--upgrade"])
    check("upgrade adds the runtime to an older install",
          code == 0 and os.path.isfile(script), out[-400:])
    with open(script, "a") as fh:
        fh.write("# local edit\n")
    code, out = run([d, "RTX", "--upgrade"])
    check("a local edit to the runtime blocks the upgrade",
          code == 1 and "local edit" in read(d, ".ai-sdlc/bin/sdlc.py"), out[-400:])
    shutil.rmtree(d, ignore_errors=True)


def test_view():
    print("view: the records drawn as an interactive page")
    # A literal closing script tag inside a script ends it early in the browser, and the
    # whole page stops working while every file still looks fine.
    page = open(os.path.join(ROOT, "optional", "runtime", "view.html"), encoding="utf-8").read()
    check("view.html closes a script only where one ends",
          page.lower().count("</script") == 2, str(page.lower().count("</script")))
    d = tempfile.mkdtemp(prefix="sdlc-view-")
    subprocess.call(["git", "init", "-q", d])
    run([d, "VWX", "-y"])
    for name in ("view.py", "view.html"):
        check("%s is installed with the runtime" % name,
              os.path.isfile(os.path.join(d, ".ai-sdlc", "bin", name)))
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json") or "{}")
    check("the view is kit-managed", ".ai-sdlc/bin/view.html" in manifest.get("files", {}))

    backlog = read(d, "docs/project/backlog.md")
    def add(section, row):
        i = backlog.index(section)
        j = backlog.index("\n", backlog.index("| --- ", i)) + 1
        return backlog[:j] + row + "\n" + backlog[j:]
    backlog = add("## Now", "| VWX-2 | Checkout `<script>x</script>` | 1 | security | VWX-1 | In progress |")
    backlog = add("## Now", "| S61.5 | Consultation booking | 2 | qa | VWX-2 | In progress |")
    backlog = add("## Parked", "| VWX-4 | Copy sign-off | 2 | copywriter | | Parked | Legal | Wording | 2026-01-01 |")
    backlog = add("## Done", "| VWX-1 | Sign-in | 1 | security | | Done | 2026-01-02 |")
    backlog = add("## Next", "| NOPE-9 | Wrong prefix | 2 | qa | | Ready |")
    write(d, "docs/project/backlog.md", backlog)
    write(d, "docs/project/worklog.md", read(d, "docs/project/worklog.md") +
          "\n## VWX-1 — Sign-in\n\n**Date:** 2026-01-02 **Tier:** 1\n**Status:** Done\n\n"
          "### What changed\n\nMagic links.\n\n### Verified\n\nall green\n\n"
          "- 2026-01-03 · VWX-3 · Fix typo · effort: Lean · verified: build ok\n")
    write(d, "docs/project/plans/VWX-2.md", "# Plan — VWX-2\n\n## Approach\n\nSee VWX-1.\n")
    write(d, "docs/project/reviews/VWX-1-ship.md", "# Review\n\nPass.\n")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=tester"]
    subprocess.call(git + ["add", "-A"], cwd=d)
    subprocess.call(git + ["commit", "-qm", "VWX-1 initial setup"], cwd=d)
    script = os.path.join(d, ".ai-sdlc", "bin", "sdlc.py")
    p = subprocess.Popen([sys.executable, script, "view", "--json"], cwd=d,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode("utf-8", "replace")
    try:
        model = json.loads(out)
    except ValueError:
        model = {"items": {}, "worklog": [], "unread": []}
    items = model["items"]
    check("model carries git metadata", "git" in model and "stats" in model["git"], str(model.get("git")))
    check("git commits linked to work item",
          any(c.get("author") == "tester" and "VWX-1" in c.get("items", []) for c in model["git"].get("commits", [])),
          str(model["git"].get("commits")))
    check("git traceability rate computed",
          model["git"].get("stats", {}).get("total") == 1 and model["git"].get("stats", {}).get("linked") == 1
          and model["git"].get("stats", {}).get("rate") == 100.0, str(model["git"].get("stats")))
    check("backlog rows land in their board columns",
          items.get("VWX-2", {}).get("column") == "Now" and items.get("VWX-4", {}).get("column") == "Parked"
          and items.get("VWX-1", {}).get("column") == "Done", out[:400])
    check("legacy issue number lands in items, not unread",
          "S61.5" in items and items["S61.5"].get("column") == "Now"
          and items["S61.5"].get("depends") == ["VWX-2"]
          and not any("S61.5" in u.get("reason", "") for u in model["unread"]), str(items.get("S61.5")))
    check("dependencies are joined both ways",
          items.get("VWX-2", {}).get("depends") == ["VWX-1"]
          and items.get("VWX-1", {}).get("dependents") == ["VWX-2"]
          and items.get("S61.5", {}).get("depends") == ["VWX-2"]
          and items.get("VWX-2", {}).get("dependents") == ["S61.5"], str(items)[:400])
    check("full and compact worklog entries are both read",
          sorted(e["id"] for e in model["worklog"]) == ["VWX-1", "VWX-3"], str(model["worklog"])[:300])
    check("an ID seen only in the worklog still gets an item", "VWX-3" in items)
    check("plans and reviews are joined by file name",
          items.get("VWX-2", {}).get("steps", {}).get("Plan") == "done"
          and items.get("VWX-1", {}).get("steps", {}).get("Ship review") == "done", str(items)[:400])
    check("a row that is not PREFIX-### is reported, not dropped silently",
          any("NOPE-9" in u["reason"] for u in model["unread"]), str(model["unread"]))
    p = subprocess.Popen([sys.executable, script, "view", "--no-open"], cwd=d,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    p.communicate()
    page = read(d, ".ai-sdlc/view/index.html")
    check("the page is written with the model inside", "VWX-2" in page and "/*NUHUT_MODEL*/" not in page)
    check("record text cannot close the script tag", "<script>x</script>" not in page, page[-200:])
    check("git view tab present in page", 'data-r="git"' in page and "viewGit" in page)
    svg_map = read(d, ".ai-sdlc/view/map.svg")
    check("formatted SVG map is written", "<svg" in svg_map and "</svg>" in svg_map and "viewBox" in svg_map)
    check("the page is git-ignored", read(d, ".ai-sdlc/view/.gitignore").strip() == "*")
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"],
                                     cwd=d).decode()
    check("nothing under .ai-sdlc/view/ shows up in git", ".ai-sdlc/view" not in status, status)

    # Live mode: a local server whose page follows the records.
    import http.client
    import re as _re
    import time as _time
    server = subprocess.Popen([sys.executable, script, "view", "--serve", "--no-open",
                               "--port", "0", "--interval", "1"], cwd=d,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        line = server.stdout.readline().decode("utf-8", "replace")
        port = int(_re.search(r"127\.0\.0\.1:([0-9]+)", line).group(1)) if "127.0.0.1:" in line else 0
        check("--serve binds to 127.0.0.1 and says where", port > 0, line)

        def get(path, host=None):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("GET", path, headers={"Host": host or "127.0.0.1:%d" % port})
            r = c.getresponse()
            return r.status, r.read().decode("utf-8", "replace"), dict(r.getheaders())

        code, page, headers = get("/")
        check("the live page is served with the model inside",
              code == 200 and "VWX-2" in page and "/*NUHUT_MODEL*/" not in page, str(code))
        check("the live page is never cached", headers.get("Cache-Control") == "no-store", str(headers))
        code, v1, _ = get("/version")
        code, body, _ = get("/model.json")
        check("the model endpoint carries the same version",
              json.loads(body).get("version") == v1 and len(v1) == 16, v1)
        write(d, "docs/project/backlog.md", read(d, "docs/project/backlog.md").replace(
            "| VWX-2 | Checkout", "| VWX-2 | Checkout v2"))
        _time.sleep(1.5)
        code, v2, _ = get("/version")
        code, body, _ = get("/model.json")
        check("a changed record moves the version and rebuilds the model",
              v2 != v1 and "Checkout v2" in json.loads(body)["items"]["VWX-2"]["title"], v2)
        code, _, _ = get("/", host="evil.example:%d" % port)
        check("a request for another host is refused (DNS rebinding)", code == 403, str(code))
        code, _, _ = get("/../../AGENTS.md")
        check("nothing but the page, version and model is served", code == 404, str(code))
    finally:
        server.terminate()
        server.wait(timeout=10)
    shutil.rmtree(d, ignore_errors=True)


def test_kit_value_benchmark():
    print("kit-value benchmark runner (fake agent)")
    bench = os.path.join(ROOT, "benchmarks", "kit-value")
    out = tempfile.mkdtemp(prefix="sdlc-kitvalue-")
    p = subprocess.Popen([sys.executable, os.path.join(bench, "run.py"), "--tasks", "copy-fix",
                          "--runs", "1", "--out", out,
                          "--fake-agent", os.path.join(bench, "fake_agent.py")],
                         cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    text = p.communicate()[0].decode("utf-8", "replace")
    check("exit 0", p.returncode == 0, text[-500:])
    rows = {}
    try:
        import csv
        with open(os.path.join(out, "results.csv")) as fh:
            rows = dict((row["arm"], row) for row in csv.DictReader(fh))
    except IOError:
        pass
    check("one row per arm", sorted(rows) == ["kit", "kit-hooks", "none"], str(sorted(rows)))
    if len(rows) == 3:
        check("the unfixed typo fails acceptance",
              all(r["acceptance_pass"] == "false" for r in rows.values()), str(rows))
        check("a README-only change passes safety",
              all(r["safety_pass"] == "true" for r in rows.values()), str(rows))
        check("an unrun claimed command counts as fabricated",
              all(r["fabricated_claims"] == "1" and r["verified_claims"] == "2"
                  for r in rows.values()), str(rows))
        check("the commit ID is read from git",
              all(r["commit_has_id"] == "true" for r in rows.values()), str(rows))
        check("kit files are not counted as product changes",
              rows["kit"]["files_changed"] == rows["none"]["files_changed"] == "1", str(rows))
    ws = lambda arm: os.path.join(out, "copy-fix--%s--1" % arm, "workspace")
    check("the control arm has no kit", not os.path.exists(os.path.join(ws("none"), "AGENTS.md")))
    check("the kit arm is installed with the unit command in its charter",
          "python3 -m unittest discover -s tests" in read(ws("kit"), "docs/project/charter.md"))
    check("only the hooks arm has hooks",
          os.path.isdir(os.path.join(ws("kit-hooks"), ".claude", "hooks"))
          and not os.path.isdir(os.path.join(ws("kit"), ".claude", "hooks")))
    shutil.rmtree(out, ignore_errors=True)


def test_dashboard():
    print("status page and its generated state")
    d = fixture("next")
    code, out = run([d, "DSH", "-y", "--scaffold-tests"])
    check("exit 0", code == 0, out[-300:])
    page = read(d, "docs/dashboard.html")
    check("the page is installed", "SDLC_STATE" in page, page[:120])
    check("the page carries no placeholders", "{{" not in page, page[:200])
    raw = read(d, "docs/dashboard-state.js")
    check("the state file is generated", raw.startswith("//") and "SDLC_STATE" in raw,
          raw[:120])
    try:
        state = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, IndexError):
        state = {}

    # The page must agree with the files, not with the answers.
    charter = read(d, "docs/project/charter.md")
    roles = [r["name"] for r in state.get("roles", [])]
    on_disk = sorted(f[:-3] for f in os.listdir(os.path.join(d, "docs", "roles"))
                     if f.endswith(".md") and f != "README.md")
    check("every role in the charter is in the state", sorted(roles) == on_disk,
          "%s vs %s" % (sorted(roles), on_disk))
    check("active roles match the charter's ticks",
          sum(1 for r in state.get("roles", []) if r["active"]) ==
          len(re.findall(r"^\| [a-z-]+ \| \u2611 \|", charter, re.M)),
          str([r["name"] for r in state.get("roles", []) if r["active"]]))
    check("check stages come from the charter",
          sorted(c["stage"] for c in state.get("commands", [])) ==
          sorted(re.findall(r"^\| `(checks\.[a-z0-9]+)` \|", charter, re.M)),
          str([c["stage"] for c in state.get("commands", [])]))
    check("artifact frontmatter is read",
          any(a["file"] == "test-plan.md" and a["last_reviewed"]
              for a in state.get("artifacts", [])), str(state.get("artifacts")))
    check("the state records what was wired",
          "CLAUDE.md" in state.get("harnesses", state.get("wired", [])),
          str(state.get("wired")))
    check("the state is dated today",
          state.get("generated") == installer.today(), str(state.get("generated")))
    check("the state uses safe mode defaults for an untailored charter",
          state.get("effort_mode") == "Normal" and
          state.get("acquisition_profile") == "Standard", str(state))

    # The state is a project record: an upgrade must not manage or replace it.
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json") or "{}")
    files = manifest.get("files", {})
    check("dashboard.html is upgrade-managed", "docs/dashboard.html" in files,
          str(sorted(files)[:4]))
    check("the state file is never upgrade-managed",
          "docs/dashboard-state.js" not in files, str(sorted(files)[-4:]))
    shutil.rmtree(d, ignore_errors=True)

    # It must survive a project with nothing in it, and a compact install.
    d = tempfile.mkdtemp(prefix="sdlc-dash-compact-")
    run([d, "DSH", "-y", "--profile", "compact"])
    raw = read(d, "docs/dashboard-state.js")
    check("compact installs still get a status page",
          os.path.exists(os.path.join(d, "docs", "dashboard.html")) and "SDLC_STATE" in raw,
          raw[:80])
    try:
        state = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    except (ValueError, IndexError):
        state = {}
    check("an empty backlog yields no items", state.get("items") == [],
          str(state.get("items")))
    check("the profile is recorded", state.get("profile") == "compact",
          str(state.get("profile")))
    shutil.rmtree(d, ignore_errors=True)


def test_domain_detection():
    print("domain markers select project types")
    cases = [
        ("ai", {"requirements.txt": "langchain\nqdrant-client\nragas\n"},
         [7], ["ai", "data", "deploy", "pii"]),
        ("data", {"requirements.txt": "dagster\ndbt-core\ngreat-expectations\n"},
         [6], ["data", "deploy", "pii"]),
        ("messaging", {"package.json": '{"dependencies":{"kafkajs":"2"}}'},
         [8], ["deploy", "dist", "pii"]),
        ("iac", {"main.tf": 'resource "null_resource" "x" {}\n'},
         [9], ["deploy", "infra"]),
        ("scrape", {"requirements.txt": "scrapy\n"},
         [10], ["acquire", "data", "deploy", "pii"]),
    ]
    for name, fixture_files, want_types, want_facts in cases:
        d = tempfile.mkdtemp(prefix="sdlc-domain-%s-" % name)
        for rel, content in fixture_files.items():
            write(d, rel, content)
        found = installer.detect(d)
        facts = sorted({f for t in found.types for f in installer.TYPE_FACTS.get(t, ())})
        check("%s type detected" % name,
              all(t in found.types for t in want_types), str(found.types))
        check("%s facts derived" % name, facts == want_facts, str(facts))
        shutil.rmtree(d, ignore_errors=True)

    # A content site must be unaffected by any of it: same six facts as before v3.
    d = tempfile.mkdtemp(prefix="sdlc-domain-web-")
    write(d, "package.json", '{"dependencies":{"astro":"4"}}')
    found = installer.detect(d)
    facts = sorted({f for t in found.types for f in installer.TYPE_FACTS.get(t, ())})
    check("content site gains no engineering facts",
          facts == ["conv", "deploy", "public", "ui", "visual"], str(facts))
    shutil.rmtree(d, ignore_errors=True)


def test_role_and_skill_selection():
    print("facts select roles and skills")

    def wizard(facts, db=()):
        w = installer.Wizard.__new__(installer.Wizard)
        w.a = dict((fid, fid in facts) for fid in installer.FACT_IDS)
        w.a["multilingual"] = False
        w.det = installer.Detected()
        w.det.db = list(db)
        w.o = type("O", (), {"want_skills": True})()
        return w

    site = wizard(("ui", "visual", "public", "deploy", "conv"))
    check("content site roster unchanged",
          site.active_roles() == ["product-manager", "architect", "security", "qa",
                                  "ux-designer", "accessibility", "brand-designer",
                                  "copywriter", "seo", "cro-analyst", "devops-sre"],
          str(site.active_roles()))
    check("content site gains no engineering skills",
          not [n for n in site.chosen_skills()
               if n in ("sdlc-eval-gate", "sdlc-data-contract", "sdlc-perf-budget",
                        "sdlc-service-contract", "sdlc-scrape-compliance")],
          str(site.chosen_skills()))

    ai = wizard(("deploy", "pii", "ai", "data"))
    for role in ("ml-engineer", "data-engineer", "performance-engineer"):
        check("ai project activates %s" % role, role in ai.active_roles(),
              str(ai.active_roles()))
    for skill in ("sdlc-eval-gate", "sdlc-data-contract", "sdlc-perf-budget"):
        check("ai project installs %s" % skill, skill in ai.chosen_skills(),
              str(ai.chosen_skills()))

    dist = wizard(("deploy", "pii", "dist"))
    check("distributed project installs sdlc-service-contract",
          "sdlc-service-contract" in dist.chosen_skills(), str(dist.chosen_skills()))
    check("distributed project has no ml-engineer",
          "ml-engineer" not in dist.active_roles(), str(dist.active_roles()))

    # sdlc-migration is gated on detection, not on an answer.
    plain = wizard(("deploy",))
    check("no data layer, no migration skill",
          "sdlc-migration" not in plain.chosen_skills(), str(plain.chosen_skills()))
    withdb = wizard(("deploy",), db=("Prisma",))
    check("detected data layer installs sdlc-migration",
          "sdlc-migration" in withdb.chosen_skills(), str(withdb.chosen_skills()))


def test_profile():
    print("machine-readable project profile")
    d = fixture("next")
    code, out = run([d, "PRF", "-y"])
    check("exit 0", code == 0, out[-300:])
    raw = read(d, ".ai-sdlc/profile.json")
    try:
        profile = json.loads(raw)
    except ValueError:
        profile = {}
    check("profile is valid json with the expected keys",
          set(("kit_version", "facts", "roles", "commands", "detected", "docs_dir"))
          <= set(profile), str(sorted(profile)))
    check("profile records the kit version",
          profile.get("kit_version") == installer.VERSION, str(profile.get("kit_version")))
    check("profile uses safe mode defaults",
          profile.get("schema") == 2 and profile.get("effort_mode") == "normal" and
          profile.get("acquisition_profile") == "standard", str(profile))
    check("every fact is present and boolean",
          sorted(profile.get("facts", {})) == sorted(installer.FACT_IDS) and
          all(isinstance(v, bool) for v in profile.get("facts", {}).values()),
          str(profile.get("facts")))
    check("non-interactive declares nothing",
          profile.get("declared") is False and
          not any(profile.get("facts", {}).values()), str(profile.get("facts")))
    check("detection is still recorded",
          "Prisma" in " ".join(profile.get("detected", {}).get("data_layers", [])),
          str(profile.get("detected", {}).get("data_layers")))
    check("commands come from detection",
          profile.get("commands", {}).get("build") == "npm run build",
          str(profile.get("commands")))
    shutil.rmtree(d, ignore_errors=True)


def test_effort_and_acquisition_profiles():
    print("effort and acquisition profiles")
    d = tempfile.mkdtemp(prefix="sdlc-modes-")
    code, out = run([d, "MOD", "-y", "--effort-mode", "lean",
                     "--acquisition-profile", "advanced"])
    profile = json.loads(read(d, ".ai-sdlc/profile.json"))
    check("mode flags install successfully", code == 0, out[-300:])
    check("profile schema 2 records both selections",
          profile.get("schema") == 2 and profile.get("effort_mode") == "lean" and
          profile.get("acquisition_profile") == "advanced", str(profile))

    code, out = run([d, "MOD", "-y", "--effort-mode", "fast"])
    check("invalid effort mode is rejected",
          code != 0 and "requires lean, normal, or beast" in out, out[-300:])
    code, out = run([d, "MOD", "-y", "--acquisition-profile", "unrestricted"])
    check("invalid acquisition profile is rejected",
          code != 0 and "requires standard or advanced" in out, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-modes-wizard-")
    write(d, "requirements.txt", "scrapy\n")
    code, log = drive([d, "MOD"], [
        ("Default effort mode", "x"),
        ("Acquisition profile", "a"),
    ])
    charter = read(d, "docs/project/charter.md")
    check("wizard records Beast and Advanced in the charter",
          code == 0 and "| **Default effort mode** | Beast |" in charter and
          "| **Acquisition profile** | Advanced |" in charter, log[-800:])
    shutil.rmtree(d, ignore_errors=True)


def test_legacy_mode_upgrade():
    print("legacy mode upgrade")
    d = tempfile.mkdtemp(prefix="sdlc-mode-upgrade-")
    run([d, "LEG", "-y"])
    charter_path = os.path.join(d, "docs", "project", "charter.md")
    charter = read(d, "docs/project/charter.md").replace(
        "| **Default effort mode** |", "| **Operating mode** | `Beast mode` <!--")
    with open(charter_path, "w") as fh:
        fh.write(charter)
    profile_path = os.path.join(d, ".ai-sdlc", "profile.json")
    profile = json.loads(read(d, ".ai-sdlc/profile.json"))
    profile.pop("effort_mode", None)
    profile.pop("acquisition_profile", None)
    profile["schema"] = 1
    profile["kit_version"] = "3.2.0"
    with open(profile_path, "w") as fh:
        json.dump(profile, fh)
    code, out = run([d, "--upgrade"])
    upgraded = json.loads(read(d, ".ai-sdlc/profile.json"))
    check("legacy Beast mode produces a migration warning",
          code == 0 and "legacy Beast mode is ambiguous" in out, out[-500:])
    check("legacy profile gets safe mode defaults",
          upgraded.get("schema") == 2 and upgraded.get("effort_mode") == "normal" and
          upgraded.get("acquisition_profile") == "standard", str(upgraded))
    shutil.rmtree(d, ignore_errors=True)


def test_scaffolding():
    print("opt-in test and CI scaffolding")
    d = fixture("next")
    code, out = run([d, "APP", "-y", "--scaffold-tests", "--scaffold-ci", "github"])
    check("GitHub scaffolding exits 0", code == 0, out[-300:])
    test_plan = read(d, "docs/project/test-plan.md")
    profile = json.loads(read(d, ".ai-sdlc/testing-profile.json"))
    workflow = read(d, ".github/workflows/quality.yml")
    check("detected test plan instantiated",
          "## Detected profile" in test_plan and "Prisma" in test_plan)
    check("machine-readable profile records confirmation boundary",
          profile.get("confirmation_required") is True and "node" in profile.get("adapters", []))
    check("charter ticks generated test plan", "☑ test-plan" in read(d, "docs/project/charter.md"))
    check("GitHub CI uses detected commands",
          "actions/checkout@v4" in workflow and "npm run build" in workflow and
          "workflow_dispatch" in workflow and "  pull_request:" not in workflow)
    code, out = run([d, "APP", "-y", "--scaffold-ci", "gitlab"])
    check("GitLab CI adapter generated",
          code == 0 and "npm run build" in read(d, ".gitlab-ci.yml") and
          "when: manual" in read(d, ".gitlab-ci.yml"))
    with open(os.path.join(d, ".gitlab-ci.yml"), "a") as fh:
        fh.write("# project-owned marker\n")
    code, out = run([d, "APP", "-y", "--scaffold-ci", "gitlab"])
    check("existing CI is never overwritten",
          code == 0 and "project-owned marker" in read(d, ".gitlab-ci.yml"))
    shutil.rmtree(d, ignore_errors=True)

    d = fixture("next")
    before = files(d)
    code, out = run([d, "APP", "-y", "--dry-run", "--scaffold-tests",
                     "--scaffold-ci", "github"])
    check("scaffolding dry run writes nothing",
          code == 0 and files(d) == before and "would add" in out)
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-scaffold-empty-")
    code, out = run([d, "APP", "-y", "--scaffold-ci", "github"])
    check("CI scaffolding refuses an unknown command set",
          code == 1 and "no quality commands" in out and files(d) == 0)
    shutil.rmtree(d, ignore_errors=True)


def test_multiselect_and_review():
    print("wizard: multi-select, back, review")
    d = fixture("next")
    code, log = drive([d, "SHOP"], [
        ("What kind of project is this?", "1,3"),
        ("Project name", "Shopfront"),
        ("What is it, in one sentence", "b"),          # back to the name
        ("Project name", "Shopfront Two"),
    ])
    check("exit 0", code == 0, log[-400:])
    check("back re-asked the previous question", log.count("Project name") >= 2)
    charter = read(d, "docs/project/charter.md")
    check("multi-select unions the roles",
          "| devops-sre | ☑" in charter and "| ux-designer | ☑" in charter)
    check("detection reached the charter", "| Language / runtime | Node.js + TypeScript |" in charter)
    check("commands detected", "| `checks.unit` | npm run test |" in charter)
    check("architecture.md was seeded", "Stripe" in read(d, "docs/project/architecture.md"))
    shutil.rmtree(d, ignore_errors=True)


def test_review_jump():
    print("wizard: changing an answer from the review screen")
    d = fixture("fastapi")
    code, log = drive([d, "PIPE"], [
        ("What is it, in one sentence", "First answer"),
        ("Enter = write these files", "3"),
        ("What is it, in one sentence", "Second answer"),
    ])
    charter = read(d, "docs/project/charter.md")
    check("the jump re-asked one question", log.count("What is it, in one sentence") >= 2)
    check("the new answer won", "| **What it is** | Second answer |" in charter, charter[:0])
    check("everything else survived", "| **Work item prefix** | `PIPE` |" in charter)
    shutil.rmtree(d, ignore_errors=True)


def test_quit_writes_nothing():
    print("wizard: q at the review screen")
    d = fixture("fastapi")
    code, log = drive([d, "PIPE"], [("Enter = write these files", "q")])
    check("nothing written", files(d) == 1, "files=%d" % files(d))
    check("said so", "Nothing was written." in log)
    shutil.rmtree(d, ignore_errors=True)


def test_multilingual():
    print("wizard: multilingual")
    d = fixture("astro-i18n")
    code, log = drive([d, "SITE"], [("Languages, source language first", "fa, en")])
    charter = read(d, "docs/project/charter.md")
    check("locales detected and offered", "en, fa, tr" in log)
    check("ships in recorded", "| **Ships in** | fa, en |" in charter)
    check("source language recorded", "| **Source language** | fa |" in charter)
    check("rtl derived", "right-to-left for fa" in charter)
    check("localisation role active", "| localisation | ☑" in charter)
    skills = os.listdir(os.path.join(d, ".claude", "skills"))
    check("i18n skills installed", "sdlc-i18n-audit" in skills
          and "sdlc-translation-review" in skills)
    shutil.rmtree(d, ignore_errors=True)

    d = fixture("next")
    code, log = drive([d, "APP"], [("more than one language", "n")])
    charter = read(d, "docs/project/charter.md")
    check("single language: role off with a reason",
          "| localisation | ☐ |" in charter and "declared at install" in charter)
    skills = os.listdir(os.path.join(d, ".claude", "skills"))
    check("single language: no i18n skills", "sdlc-i18n-audit" not in skills)
    shutil.rmtree(d, ignore_errors=True)


def test_architecture():
    print("wizard: architecture seeding")
    d = fixture("monorepo")
    code, log = drive([d, "MONO"], [
        ("What must never go down", "the payment webhook consumer"),
        ("expensive to reverse", "the shared database between apps"),
    ])
    arch = read(d, "docs/project/architecture.md")
    check("components inventoried", "apps/web" in arch and "packages/ui" in arch)
    check("compose services inventoried", "`db`" in arch and "`cache`" in arch)
    check("answers recorded", "payment webhook consumer" in arch
          and "shared database between apps" in arch)
    check("marked as detection", "detected at install" in arch)
    check("artifact ticked in the charter",
          "☑ architecture" in read(d, "docs/project/charter.md"))
    shutil.rmtree(d, ignore_errors=True)


def test_deploy_platforms():
    print("deployment platforms")
    cases = [
        ({"wrangler.toml": 'name = "x"\n'}, ["cloudflare-workers"]),
        ({"docker-compose.yml": "services:\n  web:\n    networks: [dokploy-network]\n"},
         ["dokploy"]),
        ({"compose.yaml": "services:\n  web:\n    environment:\n      - SERVICE_FQDN_WEB\n"},
         ["coolify"]),
        ({"docker-compose.yml": "services:\n  web:\n    labels:\n"
                               "      - traefik.http.routers.web.rule=Host(`x`)\n"}, []),
        ({"fly.toml": "app = 'x'\n", "vercel.json": "{}"}, ["vercel", "fly"]),
        ({"Chart.yaml": "name: x\n"}, ["kubernetes"]),
        ({"config/deploy.yml": "service: x\nimage: y/x\n"}, ["kamal"]),
        ({"requirements.txt": "boto3\n"}, []),
    ]
    for fixture_files, want in cases:
        d = tempfile.mkdtemp(prefix="sdlc-deploy-")
        for rel, content in fixture_files.items():
            write(d, rel, content)
        found = installer.detect(d).deploy
        check("detects %s from %s" % (want or "nothing", ", ".join(sorted(fixture_files))),
              found == want, str(found))
        shutil.rmtree(d, ignore_errors=True)

    # -y: detection is reported, never installed.
    d = tempfile.mkdtemp(prefix="sdlc-deploy-y-")
    write(d, "fly.toml", "app = 'x'\n")
    code, out = run([d, "DEP", "-y"])
    check("-y installs no checklist from detection alone",
          code == 0 and not os.path.isdir(os.path.join(d, "docs", "platforms")), out[-300:])
    check("-y names the detected platform and the flag", "--deploy fly" in out, out[-300:])
    check("charter row stays blank without an answer",
          "| **Deployment platforms** | _(" in read(d, "docs/project/charter.md"))
    shutil.rmtree(d, ignore_errors=True)

    # --deploy is an answer: files, charter row, profile, manifest.
    d = tempfile.mkdtemp(prefix="sdlc-deploy-flag-")
    code, out = run([d, "DEP", "-y", "--deploy", "coolify,cloudflare-edge,other"])
    installed = sorted(os.listdir(os.path.join(d, "docs", "platforms"))) \
        if os.path.isdir(os.path.join(d, "docs", "platforms")) else []
    check("--deploy installs exactly the named checklists",
          installed == ["README.md", "cloudflare-edge.md", "coolify.md"], str(installed))
    charter = read(d, "docs/project/charter.md")
    check("--deploy fills the charter row",
          "Coolify (`../platforms/coolify.md`)" in charter and "other — name it here" in charter)
    profile = json.loads(read(d, ".ai-sdlc/profile.json") or "{}")
    check("profile records the platforms",
          profile.get("deploy_platforms") == ["cloudflare-edge", "coolify", "other"],
          str(profile.get("deploy_platforms")))
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json") or "{}")
    check("checklists are kit-managed and upgradeable",
          "docs/platforms/coolify.md" in manifest.get("files", {}))
    code, out = run([d, "DEP", "-y", "--deploy", "vps"])
    profile = json.loads(read(d, ".ai-sdlc/profile.json") or "{}")
    check("adding a platform later keeps the earlier ones",
          {"coolify", "cloudflare-edge", "vps"} <= set(profile.get("deploy_platforms", [])),
          str(profile.get("deploy_platforms")))
    check("adding later says the charter needs the row by hand",
          "add vps to its" in out, out[-400:])
    code, out = run([d, "DEP", "--upgrade", "-y"])
    check("upgrade accepts installed checklists", code == 0, out[-300:])
    code, out = run([d, "DEP", "-y", "--deploy", "herokuu"])
    check("unknown platform is rejected", code != 0 and "herokuu" in out, out[-200:])
    shutil.rmtree(d, ignore_errors=True)

    # The wizard pre-selects what it detected, and the answer decides.
    d = fixture("next")
    write(d, "wrangler.toml", 'name = "x"\n')
    code, log = drive([d, "WIZ"], [("Where does it deploy", "1,9")])
    check("wizard pre-selects the detected platform",
          re.search(r"Where does it deploy\? \(numbers, comma-separated\) \[1\]", log),
          log[-400:])
    platforms = os.path.join(d, "docs", "platforms")
    check("wizard answer installs its checklists",
          os.path.isfile(os.path.join(platforms, "cloudflare-workers.md"))
          and os.path.isfile(os.path.join(platforms, "dokploy.md")),
          str(os.listdir(platforms)) if os.path.isdir(platforms) else "none")
    shutil.rmtree(d, ignore_errors=True)


def test_upgrade_ownership():
    print("upgrade: AGENTS.md region, commands, charter rows")
    d = tempfile.mkdtemp(prefix="sdlc-own-")
    code, out = run([d, "OWN", "-y", "--effort-mode", "lean"])
    charter = read(d, "docs/project/charter.md")
    check("-y records an effort mode given as a flag",
          "| **Default effort mode** | Lean |" in charter, out[-300:])
    check("-y leaves an unasked acquisition profile undecided",
          "| **Acquisition profile** | `Standard`" in charter)
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json"))
    check("fresh install records the AGENTS.md region",
          "AGENTS.md" in manifest.get("regions", {}), str(manifest.get("regions")))
    check("fresh install manages the commands",
          ".claude/commands/sdlc-plan.md" in manifest.get("files", {}))

    # Turn it into what a pre-3.3 install looks like: no markers, unmanaged commands,
    # an older charter, and a project rule in section 9.
    agents_path = os.path.join(d, "AGENTS.md")
    agents = read(d, "AGENTS.md")
    agents = re.sub(r"<!-- ai-sdlc:kit-begin[^\n]*-->\n\n", "", agents)
    agents = agents.replace("<!-- ai-sdlc:kit-end -->\n\n", "")
    agents = agents.replace("When in doubt, tier up.", "When in doubt, tier up. OLDKIT")
    agents += "\nPROJECT RULE\n"
    with open(agents_path, "w") as fh:
        fh.write(agents)
    plan_path = os.path.join(d, ".claude", "commands", "sdlc-plan.md")
    with open(plan_path, "a") as fh:
        fh.write("\nOLDKIT\n")
    charter_path = os.path.join(d, "docs", "project", "charter.md")
    with open(charter_path, "w") as fh:
        fh.write("\n".join(l for l in charter.split("\n")
                           if not l.startswith("| **Deployment platforms**")
                           and not l.startswith("| **MFA / OTP policy**")))
    manifest.pop("regions")
    manifest["files"] = dict((k, v) for k, v in manifest["files"].items()
                             if not k.startswith(".claude/commands/"))
    with open(os.path.join(d, ".ai-sdlc", "manifest.json"), "w") as fh:
        json.dump(manifest, fh)

    code, out = run([d, "OWN", "--upgrade"])
    check("legacy AGENTS.md is left alone without --adopt",
          code == 0 and "OLDKIT" in read(d, "AGENTS.md") and "--adopt" in out, out[-400:])
    check("legacy commands are left alone without --adopt",
          "OLDKIT" in read(d, ".claude/commands/sdlc-plan.md"))
    charter = read(d, "docs/project/charter.md")
    lines = charter.split("\n")
    def after(label, neighbour):
        idx = [i for i, l in enumerate(lines) if l.startswith("| **%s** |" % label)]
        return idx and lines[idx[0] - 1].startswith("| **%s** |" % neighbour)
    check("missing charter rows return in their own tables",
          after("Deployment platforms", "Direct commits to it")
          and after("MFA / OTP policy", "Access level model"), out[-400:])
    check("existing charter answers are untouched",
          "| **Default effort mode** | Lean |" in charter)

    code, out = run([d, "OWN", "--upgrade", "--adopt"])
    agents = read(d, "AGENTS.md")
    check("--adopt replaces sections 1-8 and keeps section 9",
          code == 0 and "OLDKIT" not in agents and "PROJECT RULE" in agents
          and "ai-sdlc:kit-begin" in agents, out[-400:])
    check("--adopt replaces the commands",
          "OLDKIT" not in read(d, ".claude/commands/sdlc-plan.md"))
    check("--adopt keeps a backup",
          any("AGENTS.md" in f for _, _, fs in os.walk(os.path.join(d, ".ai-sdlc", "backups"))
              for f in fs))

    code, out = run([d, "OWN", "--upgrade"])
    check("a second upgrade changes nothing", code == 0 and "Done: 0 updated" in out, out[-300:])
    with open(agents_path, "a") as fh:
        fh.write("more project rules\n")
    code, out = run([d, "OWN", "--upgrade"])
    check("section 9 edits never block an upgrade", code == 0, out[-300:])
    edited = read(d, "AGENTS.md").replace("When in doubt, tier up.", "Never tier up.")
    with open(agents_path, "w") as fh:
        fh.write(edited)
    code, out = run([d, "OWN", "--upgrade"])
    check("an edit inside sections 1-8 stops the upgrade",
          code != 0 and "kit-managed sections 1-8" in out, out[-300:])
    shutil.rmtree(d, ignore_errors=True)


def test_review_fixes():
    print("review fixes: roo, prefix, manifest paths, detection, hooks")
    # .roomodes is Roo's YAML mode file: an existing one is never touched.
    d = tempfile.mkdtemp(prefix="sdlc-roomodes-")
    modes = "customModes:\n  - slug: x\n"
    write(d, ".roomodes", modes)
    code, out = run([d, "ROO", "-y"])
    check("an existing .roomodes stays byte-identical",
          code == 0 and read(d, ".roomodes") == modes, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-badprefix-")
    code, out = run([d, "acme1", "-y", "--create"])
    check("a prefix with a digit is refused", code != 0 and "2-4 letters" in out, out[-300:])
    check("a refused prefix writes nothing", not os.path.exists(os.path.join(d, "AGENTS.md")))
    code, out = run([d, "acme", "-y"])
    check("a lower-case prefix is normalised",
          code == 0 and "`ACME`" in read(d, "docs/project/charter.md"), out[-300:])

    # A manifest written on Windows (backslash keys) still upgrades on POSIX.
    mpath = os.path.join(d, ".ai-sdlc", "manifest.json")
    manifest = json.loads(read(d, ".ai-sdlc/manifest.json"))
    manifest["files"] = dict((k.replace("/", "\\"), v) for k, v in manifest["files"].items())
    with open(mpath, "w") as fh:
        json.dump(manifest, fh)
    code, out = run([d, "ACME", "--upgrade"])
    check("a backslash manifest upgrades", code == 0, out[-300:])
    check("the manifest is rewritten with POSIX keys",
          not any("\\" in k for k in json.loads(read(d, ".ai-sdlc/manifest.json"))["files"]))

    # A charter that lost its prefix falls back to the profile.
    charter = os.path.join(d, "docs", "project", "charter.md")
    with open(charter, "w") as fh:
        fh.write(read(d, "docs/project/charter.md").replace("`ACME`", "_(prefix)_"))
    code, out = run([d, "--upgrade"])
    check("the prefix is recovered from profile.json",
          code == 0 and "profile.json: ACME" in out, out[-300:])
    shutil.rmtree(d, ignore_errors=True)

    def detected(files):
        d = tempfile.mkdtemp(prefix="sdlc-detect-")
        for rel, content in files.items():
            write(d, rel, content)
        found = installer.detect(d)
        shutil.rmtree(d, ignore_errors=True)
        return found

    found = detected({"deno.jsonc": '{\n  // tasks\n  "tasks": {"test": "deno test -A",'
                                    ' "lint": "deno lint", "fmt": "deno fmt"},\n}\n'})
    check("a deno task wins over the built-in test", found.cmds.get("unit") == "deno task test",
          str(found.cmds))
    check("a deno task wins over the built-in format",
          found.cmds.get("format") == "deno task fmt", str(found.cmds))
    found = detected({"package.json": '{"scripts":{"dev":"vite"},"dependencies":{"vite":"5"}}',
                      "deno.json": '{"tasks":{"dev":"deno run main.ts"}}'})
    check("deno does not overwrite a node run command",
          found.cmds.get("run") != "deno task dev", str(found.cmds))
    found = detected({"package.json": '{"dependencies":{"@neondatabase/serverless":"1",'
                                      '"@libsql/client":"1","convex":"1"}}'})
    check("a general database is not a vector store", not found.vector and 7 not in found.types,
          str(found.vector) + str(found.types))
    found = detected({"package.json": '{"dependencies":{"hono":"4"}}'})
    check("a Hono service is an API, not a web app", 1 not in found.types, str(found.types))
    found = detected({"package.json": '{"dependencies":{"hono":"4"}}',
                      "services/api/package.json": '{"dependencies":{"@prisma/client":"5"}}',
                      "services/api/prisma/schema.prisma":
                      'datasource db {\n  provider = "postgresql"\n}\n',
                      "node_modules/x/prisma/schema.prisma": 'provider = "mysql"\n'})
    check("a nested prisma schema is found outside node_modules",
          "Prisma (postgresql)" in found.db, str(found.db))
    found = detected({"src/examples/package.json": '{"dependencies":{"@pinecone-database/pinecone":"1"}}'})
    check("an example package does not drive detection", not found.vector, str(found.vector))

    found = detected({"package.json": '{"workspaces":["apps/*"]}',
                      "apps/web/package.json": '{"dependencies":{"react":"18","vite":"5"}}',
                      "apps/api/package.json": '{"dependencies":{"hono":"4"}}'})
    check("an API package does not hide React in a sibling",
          "React" in found.fw and 1 in found.types and 3 in found.types,
          str(found.fw) + str(found.types))
    found = detected({"package.json": '{"devDependencies":{"typescript":"5"}}',
                      "tsconfig.base.json": "{}", "apps/web/tsconfig.json": "{}"})
    check("no root tsconfig.json, no bare tsc gate", "typecheck" not in found.cmds,
          str(found.cmds))
    found = detected({"package.json": '{"dependencies":{"@prisma/client":"5"}}',
                      "examples/blog/prisma/schema.prisma": 'provider = "sqlite"\n'})
    check("an example prisma schema is not the product's", "Prisma (sqlite)" not in found.db,
          str(found.db))
    found = detected({"services/demo/requirements.txt": "flask\n",
                      "services/examples/requirements.txt": "pinecone-client\n"})
    check("an example python service does not drive detection", not found.vector,
          str(found.vector))
    check("prefix rules are shared", installer.normalize_prefix("acme-") == "ACME"
          and installer.normalize_prefix("acme1") is None
          and installer.normalize_prefix("AB\n") == "AB"
          and installer.validate_prefix(None, "acme1")[0] is False)

    if not shutil.which("jq"):
        check("jq present for hook review tests", True, "skipped: jq not installed")
        return
    d = os.path.realpath(tempfile.mkdtemp(prefix="sdlc-hooks2-"))
    code, out = run([d, "HKT", "-y", "--hooks"])

    def fire(script, command):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=d)
        p = subprocess.Popen(["sh", os.path.join(d, ".claude", "hooks", script)], cwd=d,
                             env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        o, _ = p.communicate(json.dumps({"tool_input": {"command": command}}).encode())
        return o.decode("utf-8", "replace")

    for cmd, deny in (('git commit -m "bump v2 deps"', True),
                      ('git commit -m "fix utf8 handling"', True),
                      ('git commit -m "HKT-12 fix"', False),
                      ('git commit -m "hkt-12: fix"', False),
                      ('git commit -m "fix (#12)"', False),
                      ("git commit --amend --no-edit", False),
                      ("git commit -F msg.txt", False),
                      ("git commit", False),
                      ("git commit-tree abc", False),
                      ("python -m pytest && git commit", False),
                      ("git commit -mfix", True),
                      ('  GIT_AUTHOR_NAME=x git commit -m "fix"', True)):
        out = fire("work-item-id.sh", cmd)
        check("work-item-id %s: %s" % ("denies" if deny else "allows", cmd),
              ('"permissionDecision":"deny"' in out) == deny, out)
    write(d, "docs/project/backlog.md",
          read(d, "docs/project/backlog.md") + "\n| P1.2 | legacy item | Now |\n")
    out = fire("work-item-id.sh", 'git commit -m "P1.2 finish"')
    check("a legacy ID held by the backlog is allowed", "deny" not in out, out)

    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.call(git + ["init", "-q"], cwd=d)
    write(d, "notes.md", "risk-tier-assessment-for-the-new-billing-service-and-the-ledger\n")
    subprocess.call(git + ["add", "notes.md"], cwd=d)
    out = fire("secret-guard.sh", 'git commit -m "HKT-1 notes"')
    check("hyphenated prose is not an OpenAI key", "deny" not in out, out)
    write(d, "cfg.py", "KEY = 'sk-proj-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0'\n")
    subprocess.call(git + ["add", "cfg.py"], cwd=d)
    out = fire("secret-guard.sh", 'git commit -m "HKT-1 cfg"')
    check("a real-shaped OpenAI key is still denied", '"permissionDecision":"deny"' in out, out)
    subprocess.call(git + ["commit", "-qm", "HKT-1 base", "--no-verify"], cwd=d)
    write(d, "notes.md", "AKIA" + "ABCDEFGHIJKLMNOP\n")
    for cmd in ('git commit -asm "HKT-1 x"', '  git commit -am "HKT-1 x"',
                'if true; then git commit -qam "HKT-1 x"; fi'):
        out = fire("secret-guard.sh", cmd)
        check("secret-guard scans: %s" % cmd, '"permissionDecision":"deny"' in out, out)
    shutil.rmtree(d, ignore_errors=True)


def test_epics():
    print("epics: opt-in development method")
    d = tempfile.mkdtemp(prefix="sdlc-epic-default-")
    code, out = run([d, "EPC", "-y", "--create"])
    check("default install exits 0", code == 0, out[-300:])
    check("the method defaults to item in the profile",
          json.loads(read(d, ".ai-sdlc/profile.json")).get("dev_method") == "item")
    check("the charter row is left at its documented default",
          "| **Development method** | `Item` · `Epic`" in read(d, "docs/project/charter.md"))
    check("the epic process, template and folder are installed",
          all(os.path.isfile(os.path.join(d, rel)) for rel in (
              "docs/process/11-epics.md", "docs/templates/epic.md",
              "docs/project/epics/README.md")))

    # A project from before epics: no charter row, no profile field. It upgrades cleanly
    # and keeps working item by item.
    charter = os.path.join(d, "docs", "project", "charter.md")
    text = read(d, "docs/project/charter.md")
    with open(charter, "w") as fh:
        fh.write("\n".join(l for l in text.split("\n")
                           if not l.startswith("| **Development method**")))
    profile = json.loads(read(d, ".ai-sdlc/profile.json"))
    profile.pop("dev_method")
    write(d, ".ai-sdlc/profile.json", json.dumps(profile))
    doctor = [sys.executable, os.path.join(d, ".ai-sdlc", "bin", "sdlc.py"), "--root", d, "doctor"]
    before = subprocess.run(doctor, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode()
    check("a pre-epic charter raises no epic finding", "Development method" not in before
          and "epics" not in before, before[-400:])
    code, out = run([d, "EPC", "--upgrade"])
    check("a pre-epic project upgrades", code == 0, out[-300:])
    check("the upgrade restores the row and the item default",
          "| **Development method** |" in read(d, "docs/project/charter.md")
          and json.loads(read(d, ".ai-sdlc/profile.json")).get("dev_method") == "item")
    shutil.rmtree(d, ignore_errors=True)

    d = tempfile.mkdtemp(prefix="sdlc-epic-chosen-")
    code, out = run([d, "EPC", "-y", "--create", "--dev-method", "epic"])
    check("--dev-method epic exits 0", code == 0, out[-300:])
    check("the charter records Epic",
          "| **Development method** | Epic |" in read(d, "docs/project/charter.md"))
    check("the profile records epic",
          json.loads(read(d, ".ai-sdlc/profile.json")).get("dev_method") == "epic")
    backlog = os.path.join(d, "docs", "project", "backlog.md")
    with open(backlog, "a") as fh:
        fh.write("\n| EPC-001 | Epic: billing | 2 | product-manager | none | Ready |\n"
                 "| EPC-002 | invoices table (in EPC-001) | 2 | architect | none | Ready |\n"
                 "| EPC-003 | stray item (in EPC-009) | 3 | architect | none | Ready |\n")
    doctor = [sys.executable, os.path.join(d, ".ai-sdlc", "bin", "sdlc.py"), "--root", d, "doctor"]
    out = subprocess.run(doctor, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode()
    check("doctor asks for the epic file", "EPC-001" in out and "epics" in out, out[-600:])
    check("doctor flags an item naming no epic", "EPC-009" in out, out[-600:])
    check("a correctly linked item is not flagged",
          not re.search(r"EPC-002.*not an epic", out), out[-600:])
    write(d, "docs/project/epics/EPC-001.md", "# Epic\n")
    out = subprocess.run(doctor, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode()
    check("the epic file satisfies doctor", "EPC-001" not in out, out[-600:])
    shutil.rmtree(d, ignore_errors=True)

    code, out = run([tempfile.gettempdir() + "/sdlc-epic-bad", "EPC", "-y", "--dev-method", "batch"])
    check("an unknown method is refused", code != 0 and "item or epic" in out, out[-200:])


def main():
    for test in (test_guards, test_non_interactive, test_dry_run,
                 test_custom_docs_dir, test_managed_upgrade, test_command_detection,
                 test_stack_adapters, test_harness_wiring, test_profiles, test_hooks,
                 test_runtime, test_view, test_kit_value_benchmark,
                 test_dashboard,
                 test_domain_detection,
                 test_role_and_skill_selection, test_profile,
                 test_effort_and_acquisition_profiles, test_legacy_mode_upgrade,
                 test_scaffolding,
                 test_multiselect_and_review, test_review_jump,
                 test_quit_writes_nothing,
                 test_multilingual, test_architecture,
                 test_deploy_platforms, test_upgrade_ownership, test_review_fixes,
                 test_epics):
        test()
    print("")
    if failures:
        print("%d failed: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

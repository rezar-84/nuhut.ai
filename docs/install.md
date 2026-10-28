# Installing and upgrading

Every installer option, the layout it writes, and how upgrades work.

## Install as a Claude Code plugin

The plugin gives the `/sdlc-*` commands in every project and ships no skills. Why, and
how it complements the installer: [`.claude-plugin/README.md`](../.claude-plugin/README.md).

## Install into a project

```sh
./install.sh /path/to/your-project
```

Run in a terminal, that opens a guided setup driven by the arrow keys. After the
destination, it shows **what it detected and what it would set up**: project name and ID
prefix, what you are building, the AI tools it found, the stack, the check commands, the
reviewer roles and skills those imply, and what it will add. Then it asks how you want to
continue:

```
◆  How do you want to set this up?
│  › ● Use these settings  asks 4 things it cannot detect, then shows every answer for review  (recommended)
│    ○ Customise           pick which sections to go through; the rest keep the settings above
│    ○ Every question      all ten sections, about 40 questions, each one explained
└  ↑↓ move · enter choose · ? explain · ← back · q quit
```

- **Use these settings** asks only the one-line description, the work item prefix, the
  project types and the AI tools, then goes to the review screen.
- **Customise** shows a checklist of the ten sections; only the ticked ones are asked.
- **Every question** walks all ten sections (`■  Stack  4 of 10`).

`--quick`, `--full` and `--sections process,install` on the command line skip that
question (`--list sections` names them). Whichever path you take, the review screen lists
every answer, defaults included, and any of them can be changed there.

Every question shows a one-line hint with an example under it (`e.g. Next.js on Vercel,
Postgres on Neon`), and `?` opens a longer explanation in place. A question you have
answered folds to one line (`◇  AI tools  Claude Code, Cursor`), so the screen shows
your answers rather than the questions.

| Key | Menus | Checklists | Typed answers |
| --- | --- | --- | --- |
| `↑` `↓` (or `j` `k`) | move | move | |
| a number | jump to that option | jump to that option | |
| `Space` | | tick or untick | |
| `a` / `n` | | tick all / none | |
| `/` | | search a long list (the 18 deploy platforms) | |
| `Enter` | choose | confirm | keep the value in brackets |
| `-` | | | leave it blank |
| `?` | explain | explain | explain |
| `←`, `b` or `Esc` | back | back | `b` |
| `s` / `S` | defaults for the rest of the section / the setup | same | same |
| `q` | quit (asks first) | quit (asks first) | quit (asks first) |

The arrow-key menus need a real terminal on both ends. **`--plain`** (or `NUHUT_PLAIN=1`)
switches to numbered, typed prompts with the same questions, hints and help. Use it for
screen readers, logs, or a terminal that mishandles escape codes. It is also chosen
automatically when stdin or stdout is not a terminal or `TERM=dumb`. `NO_COLOR` turns
colour off in both modes, and a terminal that cannot print `◆ │ ●` gets ASCII instead.
Ctrl-C before the review writes nothing and says so.

The first question is where to install. It has no default and is never guessed: the
installer refuses its own directory (and anything inside it), so running `./install.sh`
from the kit cannot scatter a project's `AGENTS.md`, `docs/` and `.claude/` over the
template. A destination that does not exist yet can be created on the spot — or pass
`--create` for the same thing without questions.

It asks who and what the project is, then what you are building — **choose every type that
applies**, `1,3` for an app that is also an API — defaulted from what is actually in the
repository. That selection derives eleven yes/no facts — interface, visual interface,
public discoverability, deployment, personal data, conversion goal, datasets or pipelines,
models or retrieval, several services or messaging, provisioned infrastructure, acquired
data — which decide which of the sixteen roles review your work and which skills get
installed. It then shows the stack,
the check commands, and the architecture it read out of the repository for you to confirm,
asks about languages if the project has an interface or public content, and takes approvers
and risk defaults.

Choices with fixed options (effort mode, development method, decision style, tier rules,
access model, MFA, docs size, enforcement, CI) are menus. Each option has a one-line
meaning, and the recommended one is marked. With `--plain`, type the number or the
option's name.

Tables the installer detected (the facts, the stack, the check commands) are confirmed
with **Use these / Change some / Leave blank**. *Change some* asks which rows to correct
and then only those, so fixing one command is one question rather than eighteen. The
facts become a checklist, and the skills are a checklist pre-ticked from your answers,
with the reason for each.

The setup also asks about things that used to be flags only:

| Question | Same as |
| --- | --- |
| Which AI coding tools will work in this repository? (tools found in the repo are pre-ticked) | `--harness` |
| How do you work? Solo / Team / Regulated | `--preset` |
| Tier rules: Standard / Strict | `--tier-rules` |
| How much process documentation should the agent read? Full / Compact | `--profile` |
| Enforce the rules mechanically? None / Agent hooks / Git hooks / Both | `--hooks`, `--git-hooks` |
| Should the kit's own tools (`.ai-sdlc/`) be committed? Commit / Ignore / Ignore locally | `--gitignore-tools`, `--git-exclude` |
| Starter test plan? Starter CI workflow? | `--scaffold-tests`, `--scaffold-ci` |

A flag given on the command line answers its question, so that question is not asked.

Nothing is written until the **review screen**. It lists every answer, numbered, then
offers **Write these files**, **Change an answer**, **Show the files** and **Quit**. (With
`--plain`: `Enter` writes, a number changes that answer, `f` shows the files, `q` quits.)
*Show the files* lists every path the install would add, folded by folder, with counts.
It uses the same code path as `--dry-run`, so the list is exactly what gets written.
Under the list it prints
**the same install as a command line** (`./install.sh <dir> <PREFIX> -y --harness … --deploy
…`). The command does not carry the free-text charter answers, which are already written
into the charter. The final report prints the command again. The report also checks that
no `{{…}}` placeholder was left unsubstituted, and says how to start: `/sdlc-plan` in
Claude Code, or "follow AGENTS.md" in other tools. It also lists the charter rows that
are still blank, with their line numbers, and in the arrow-key setup it offers to open
the live project viewer.

To see every option and its valid values without running anything:

```sh
./install.sh --help              # one page, grouped, with examples
./install.sh --help full         # every option in detail
./install.sh --list harnesses    # also: platforms, presets, types, skills, sections
./install.sh --explain tiers     # what a concept means and how to choose
```

`--explain` topics: `tiers`, `presets`, `effort`, `decision`, `hooks`, `profile`,
`skills`, `roles`, `charter` and `harnesses`.

What it writes into the installed files:

- `docs/project/charter.md` — identity, stack, commands, default branch, approvers,
  staleness, managed platform, accessibility target, languages and localisation, and the
  **active roles table**, ticked and unticked with the reason each row came from.
- `docs/project/architecture.md` — instantiated, not left blank: the component inventory
  (monorepo packages, compose services) and the external dependencies it found in your
  dependency list, each row marked `_(detected at install)_` for you to confirm, plus the
  three things you told it that no file could say.
- `AGENTS.md` — the "Human approval required for" and "Forbidden in this project" lines of
  the Project overrides section.
- `.ai-sdlc/profile.json` — schema 2: the facts, active roles, chosen skills, command
  table, default effort mode, and acquisition profile in machine-readable form, so
  `/sdlc-verify` and the skills can act on them without parsing
  prose. Derived, never authored: the charter is the source of truth and wins on conflict.

Anything it could not establish is left blank on purpose. A blank cell is read as *Unknown*
by the process; a wrong one produces confidently false "verified" claims, so nothing is
guessed — not one check command, not one data category.

For scripts, CI, or a plain copy with no questions:

```sh
./install.sh /path/to/your-project ACME -y          # ACME = the work-item ID prefix
```

`-y` (also implied when stdin is not a terminal) takes every default, tailors nothing, and
installs only the skills that do not depend on an answer. It ends with a **Defaults
taken** table listing what it assumed (prefix, AI tools, deploy checklists, working style,
enforcement) and the flag that changes each. The target directory is required
in this mode — without a terminal there is nobody to ask. Other flags: `--docs-dir <name>`
to install the docs under a different directory, `--harness <list>`, `--profile
<full|compact>`, `--effort-mode <lean|normal|beast>`, `--dev-method <item|epic>`,
`--decision-style <ask|guide|autopilot>`, `--acquisition-profile <standard|advanced>`,
`--hooks`, `--git-hooks [all|secrets]`, `--gitignore-tools`, `--git-exclude`, `--create`, `--no-skills`, `--dry-run`,
`--lang <code>`, `--scaffold-tests`, `--scaffold-ci <github|gitlab>`, `--deploy <list>`,
`--plain`, `--sections <list>`, and `--upgrade`.

### Ignoring runtime tools in Git

For teams or developers using the kit locally on shared codebases without committing runtime tooling:
- `--gitignore-tools`: appends `.ai-sdlc/` to the project's root `.gitignore` so runtime scripts, manifests, and local viewer caches stay uncommitted.
- `--git-exclude`: appends `.ai-sdlc/` to `.git/info/exclude` (local-only ignore: leaves `.gitignore` completely untouched for team pull requests).

### Deployment platforms

The process documents never name a platform. What differs between platforms — Vercel
previews using production variables, a Dokploy bind mount wiped on redeploy, Cloudflare's
*Flexible* TLS looping forever, a Kamal accessory that `deploy` never upgrades — lives in
one checklist per platform, copied into `docs/platforms/` only when the project uses it:

`cloudflare-workers` · `cloudflare-edge` · `vercel` · `netlify` · `fly` · `railway` ·
`render` · `heroku` (and Dokku) · `dokploy` · `coolify` · `kamal` · `vps` · `kubernetes` ·
`aws` · `gcp` (and Firebase) · `azure` · `digitalocean`

The wizard detects what it can from the repository (`wrangler.toml`, `vercel.json`,
`fly.toml`, a Compose file on `dokploy-network`, Coolify's `SERVICE_FQDN_` variables,
`config/deploy.yml`, `Chart.yaml`, …), pre-selects it, and asks. Your answer decides and is
written into the charter's **Deployment platforms** row, which the `devops-sre` review and
the release runbook read. Anything unlisted is a valid answer (`other`): it is recorded,
and the neutral playbook carries the review alone.

```sh
./install.sh /path/to/project ACME -y --deploy coolify,cloudflare-edge
```

With `-y` and no `--deploy`, nothing is installed from detection alone — the installer says
what it found and which flag confirms it. Re-running with `--deploy <id>` later adds a
checklist without touching anything else; `--upgrade` refreshes the ones installed.

`Advanced` acquisition enables browser automation, OCR,
resilient extractors, and authorised session flows. It is a capability profile, not
permission: authentication, paywalls, CAPTCHA, explicit denial, or other access controls
still require target-owner authorisation or an approved API/export route.

The installer is `install.py` (Python 3.8+, standard library only); `install.sh` is a
wrapper that runs it. Nothing the kit *installs* needs Python — only the installer does.
The optional `--hooks` scripts need `jq`, and say so and allow the call when it is absent.

## Stack adapters and scaffolding

The portable process accepts any stack. The installer additionally recognises common
project markers for Node/TypeScript, Python, Go, Rust, PHP, Ruby, Java/Kotlin with Maven
or Gradle, and C#/.NET. Adapters detect existing frameworks, test tooling, ORMs, database
drivers, migration tools, and quality commands; they do not install or replace them.

Detected data layers include Prisma, Drizzle, TypeORM, SQLAlchemy/Alembic, Django ORM,
GORM/sqlc, Diesel/SQLx/SeaORM, Eloquent, Doctrine, Active Record, JPA/Hibernate,
Flyway/Liquibase, Entity Framework Core, and Dapper. Engine markers cover PostgreSQL,
MySQL/MariaDB, SQLite, MongoDB, Redis, SQL Server, and Oracle.

Two explicit flags turn detection into project-owned starting files:

```sh
./install.sh /path/to/project ACME -y --scaffold-tests
./install.sh /path/to/project ACME -y --scaffold-ci github
./install.sh /path/to/project ACME -y --scaffold-ci gitlab
```

`--scaffold-tests` creates `docs/project/test-plan.md` and
`.ai-sdlc/testing-profile.json`, both marked as detected and requiring confirmation.
`--scaffold-ci` creates `.github/workflows/quality.yml` or `.gitlab-ci.yml` from the
project's detected/confirmed commands. It refuses an empty command set. Scaffolding never
overwrites an existing file, never installs a dependency, and leaves runtime and service
version confirmation to the project charter. Generated jobs are manual-only until a
human confirms the commands and deliberately enables push or pull-request triggers.

The installer copies `AGENTS.md` to the project root, `docs/` into the project, the six
slash commands into `.claude/commands/`, and the selected skills into `.claude/skills/`;
substitutes `{{PROJECT_NAME}}`, `{{PREFIX}}`, and `{{DOCS_DIR}}` in all of them; adds a
`CLAUDE.md` pointer if none exists; and records checksums for portable files in
`.ai-sdlc/manifest.json`. A normal re-run **never overwrites an existing file** — it is
safe, reuses the docs directory it finds, and only fills in what is missing.

Manual install is a copy plus a find-and-replace — the substitution is not optional, and
skipping it leaves `{{PREFIX}}-###` as a literal path in the docs the agent follows:

```sh
cp    template/AGENTS.md          /path/to/your-project/AGENTS.md
cp -r template/docs               /path/to/your-project/docs
cp -r optional/claude-commands    /path/to/your-project/.claude/commands
cp -r optional/skills             /path/to/your-project/.claude/skills   # or just the ones you want
cd /path/to/your-project
grep -rl '{{' docs AGENTS.md .claude | xargs sed -i 's/{{PREFIX}}/ACME/g; s/{{PROJECT_NAME}}/your-project/g; s/{{DOCS_DIR}}/docs/g'
```

Then, in the target project:

1. Read `docs/project/charter.md` and correct or complete it. Guided setup fills in what it
   can establish; constraints, environments, and sources of truth are yours. An agent that
   guesses a check command because the charter was blank will produce confidently false
   "verified" claims.
2. Confirm nothing was missed: `grep -rn '{{' docs AGENTS.md .claude` should be empty.
3. Fill in the rest of the "Project overrides" section of `AGENTS.md`.

That is all. The installed kit is plain Markdown: no build step, no dependency, and
nothing to run.

## Installing into a managed platform (Lovable, Replit, Bolt, …)

A project that lives on an AI app builder or cloud IDE is co-owned by another agent: the
platform edits files, syncs the repository, and often deploys the default branch on its
own. The kit is designed not to break that:

- **The installer detects** common platform markers (`.replit` / `replit.nix` /
  `replit.md`, a Lovable project, `.bolt/`, `.idx/`, `glitch.json`, CodeSandbox config)
  and prints platform-specific next steps. Detection is read-only, and the installer
  still never overwrites or edits an existing file — platform config is left exactly as
  found.
- **The charter declares the platform** in its "Managed platform" table: the sync model,
  the files the platform owns (never hand-edited), where the platform's own agent reads
  its instructions, and how deploys happen.
- **Process rules yield to that table.** "Managed platforms" in
  `docs/process/05-change-control.md` sets the standing rules: no hand-edits to
  platform-owned files, no history rewrites on any branch the platform syncs, treat an
  auto-deployed merge as a release, and point the platform's instruction file
  (`replit.md`, Lovable project knowledge) at `AGENTS.md` so the platform's agent and
  this process cannot drift apart.

Platform names appear only in this README and in the charter you fill in — the process
docs stay platform-agnostic the same way they stay stack-agnostic.

## Layout

```
template/
  AGENTS.md                  the operating contract — the file the agent always reads
  docs/
    README.md                map of the kit + cold-start reading order for an agent
    process/                 HOW we work. Portable. Same in every project. Rarely edited.
      00-operating-model.md      the loop, the modes, and what to do when a human is needed
      01-lifecycle-gates.md      appendix: G0..G6, for standing up a new project only
      02-role-reviews.md         who reviews what, at which stage, and what a verdict means
      03-ready-and-done.md       Definition of Ready / Definition of Done
      04-quality-gates.md        test strategy, CI gate order, bug severity ladder
      05-change-control.md       branches, commits, PRs, approvals, ADRs, rollback
      06-evidence-and-claims.md  the no-fabrication doctrine; provenance; assumptions
      07-traceability.md         IDs, the backlog row spec, what gets logged where
      08-content-and-translation.md  source language, machine translation, RTL, per-locale checks
      09-probabilistic-and-data-systems.md  models, prompts, evaluation, pipelines, acquired data
      10-multi-agent.md          claiming, single-writer files, review fan-out, handoff
      11-epics.md                grouping connected items under one plan and branch
      12-sensitive-data-in-records.md  what project records may and may not hold
      13-stack-evaluation.md     verifying and recording foundational stack choices
      14-decision-style.md       Ask, Guide, and Autopilot decision styles
    roles/                   WHO reviews. One playbook per professional perspective.
      README.md + 16 role playbooks
    templates/               Blank artifacts to copy when a project needs one.
    CARD.md                  the operating card: the whole standard on one page
    project/                 WHERE this project's filled-in reality lives.
      charter.md  backlog.md  worklog.md  assumptions-and-risks.md
      adr/  reviews/  plans/  defects/  epics/  postmortems/  worklog-archive/
.claude-plugin/              plugin + marketplace manifests (commands only, no skills)
optional/
  hooks/                     opt-in Claude Code enforcement (--hooks)
  git-hooks/                 opt-in git hooks, every harness (--git-hooks)
  claude-commands/           Claude Code slash commands that drive the loop
  skills/                    model-invoked skills, installed per project need
  platforms/                 deployment checklists, installed per platform used (--deploy)
  locales/                   translations of the installer's own prompts
  runtime/                   sdlc.py (doctor, verify, plan-check, metrics) and the view,
                             installed to .ai-sdlc/bin/ (always)
  harness/claude/            examples to adapt, never installed: settings, verifier subagent
install.py                   the installer; install.sh is a wrapper around it
validate.py                  source and installed-output validation
tests/smoke.py               installer boundary and workflow tests
benchmarks/effort-modes/     optional isolated-run protocol and measurement scorer
benchmarks/kit-value/        does the kit change agent behaviour? no kit vs kit vs kit + hooks
.github/workflows/           continuous validation and tag-based releases
VERSION                      the kit version, stamped into installed AGENTS.md
LICENSE · SECURITY.md · CONTRIBUTING.md · CHANGELOG.md
                             distribution and project governance
```

## Upgrading the kit later

```sh
./install.sh /path/to/your-project ACME --upgrade
```

A project installed before 3.3 needs one extra run, once:

```sh
./install.sh /path/to/your-project ACME --upgrade --adopt
```

`--adopt` takes over the two things older versions left for you to merge by hand —
sections 1–8 of `AGENTS.md` and the `/sdlc-*` commands — after backing up the current
copies. A plain `--upgrade` never does this on its own, and says when it is needed.

The upgrade report names the kit skills the project does not have. `--upgrade` never adds
one. To add the ones that fit, run the guided setup again (`./install.sh
/path/to/your-project --full`): it adds only missing files.

`--upgrade` manages `docs/README.md`, `docs/process/`, `docs/roles/`, `docs/templates/`,
`docs/platforms/`, the `/sdlc-*` commands, and any kit skill the project already has. It verifies their recorded checksums first and
stops if a managed file was locally modified or removed. It backs up affected files under
`.ai-sdlc/backups/`, writes updates
atomically, removes obsolete files previously owned by the manifest, and restores the old
state if an update fails. Legacy installations receive a full portable-file backup on
their first manifest-based upgrade.

`AGENTS.md` is split in two by marker comments. Sections 1–8 are the kit's: an upgrade
replaces them, and stops — like any other managed file — if they were edited. Section 9,
"Project overrides", is yours and is never touched. The charter and the rest of
`docs/project/` are yours too, with one additive exception: when a new kit version adds a
charter row, the upgrade inserts it blank, in its own table, and lists it. An existing row
is never changed. Skills the project did not choose are not added by an upgrade — `ls
optional/skills` shows what a newer version ships.

This only works if you keep project-specific rules where they belong: in `AGENTS.md`
("Project overrides") and in `docs/project/`, never inside `process/` or `roles/`. The
installed `AGENTS.md` carries the kit version it came from, in an HTML comment near the
top. The manifest records the version of the managed process, role, and skill files;
`VERSION` here is the current one.

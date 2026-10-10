# Changelog

This project follows semantic versioning. User-visible changes are recorded here.

## Unreleased

- **Gitignore options for runtime tooling (`--gitignore-tools`, `--git-exclude`):**
  - `--gitignore-tools`: appends `.ai-sdlc/` to the project's root `.gitignore` so kit
    runtime binaries, manifests, and local viewer caches are not committed to git.
  - `--git-exclude`: appends `.ai-sdlc/` to `.git/info/exclude` (local stealth mode:
    keeps `.gitignore` untouched for pull requests on team codebases).
  - The setup wizard gains an interactive prompt under `What to install`.
  - Re-running or upgrading is idempotent and never creates duplicate entries.

- **Epics, an opt-in development method:**
  - **Item** (the default, unchanged) works one item at a time.
  - **Epic** plans several items together. It needs one human approval for the plan and
    one design review, then the agent carries on between items. Verified Tier 2 and 3
    items merge into an epic branch.
  - A human approves the epic branch at the checkpoints the plan chose: per phase, every
    N items, or at the end.
  - A Tier 1 item, any Block, a failed verification, a plan that proves wrong, and
    anything irreversible or gated still stop the work. Every item keeps its own tests,
    checks, reviews and tier approvals.
  - Added: `process/11-epics.md`, `templates/epic.md` and `project/epics/`. The charter
    gains a **Development method** row, and the installer gains `--dev-method item|epic`
    and a setup question. `/sdlc-plan` gains `--epic`. `AGENTS.md` and `CARD.md` gain a
    short rule.
  - `sdlc.py doctor` warns when an epic row has no epic file, or when an item names an
    epic that does not exist.
  - Nothing changes for an existing project. `--upgrade` adds the row at its default
    (Item) and `dev_method: item` to the profile. A charter without the row reports no
    new finding.

- **Fixes from a review:**
  - Roo Code's pointer now goes in `.roo/rules/agents.md`. The installer no longer
    appends markdown to `.roomodes`, which is Roo's YAML mode file and broke when edited.
  - A work item prefix given on the command line must be 2-4 letters. It is upper-cased,
    and anything else is refused before a file is written. `--upgrade` falls back to the
    prefix in `.ai-sdlc/profile.json` when the charter no longer names one.
  - Manifest paths are always written with `/`, and backslash paths from older Windows
    installs are read as `/`. A team that installs on Windows can now upgrade on macOS or
    Linux.
  - Detection:
    - A project's Deno tasks now take priority over the built-in commands.
    - Deno no longer replaces a Node run command.
    - `deno.jsonc` with comments now parses.
    - Prisma schemas are searched without walking `node_modules`.
    - Neon, libSQL and Convex are no longer counted as vector stores.
    - Hono counts as an API framework only.
    - `Pipfile` is read in service folders.
    - Example and fixture packages no longer drive detection.
  - The `work-item-id` hook:
    - IDs must be whole tokens. "v2" or "utf8" no longer counts as an ID.
    - A legacy hierarchical ID counts only if the backlog holds it.
    - The hook no longer blocks `-F`, editor or `--amend --no-edit` commits, whose message
      it cannot see.
    - It ignores `git commit-tree` and `git commit` inside a quoted string.
  - The `secret-guard` hook no longer reads hyphenated prose such as "risk-tier-…" as an
    OpenAI key.
  - Tier 2 states one human approver everywhere: `AGENTS.md`, `CARD.md` and
    `05-change-control.md` now agree with `00-operating-model.md`.
  - The docs state Python 3.8+, the versions CI tests.
  - The kit-value benchmark prefix is `BNCH`, since a prefix has at most four letters.
  - Naming only harnesses that read `AGENTS.md` themselves, such as `--harness codex`,
    no longer writes a `CLAUDE.md`.
  - In a monorepo, React is detected even when a sibling package uses an API framework,
    so the project keeps its web-app type.
  - The default `tsc --noEmit` typecheck is set only when the root has a
    `tsconfig.json`. A monorepo without one gets a blank row instead of a check that
    always fails.
  - The Prisma schema search runs only when Prisma is a dependency. It goes at most four
    levels deep and skips `venv`, `target`, `coverage`, example and test folders.
  - Python dependency files in workspace folders are read once instead of once per
    package name, and example services are skipped.
  - The prompt and the command line now apply the same prefix rule: 2-4 letters, with a
    trailing `-` allowed.

## 3.4.1 — 2026-09-30

- **The viewer is documented where people look for it:**
  - The docs map installed in every project opens with a pointer for "a person catching
    up", and gains a section on the viewer: its tabs, how to read the lifecycle stepper,
    snapshot or live, and what it will never do.
  - The main README's quick start ends with `view --serve`, and "Seeing the work" gains
    how to get around, how to read it, and a daily routine.
  - The paragraph on why the kit has no web UI now says what it does ship.
  - `dashboard.html` and `/sdlc-doctor` point to the viewer. The developer commands in
    the README and CONTRIBUTING compile and self-test `view.py`.
  - `AGENTS.md` updates the docs-size figure (about 87,000 tokens) that agents budget
    their reading by.

- **Live mode: `sdlc.py view --serve`.** The view is served on 127.0.0.1 and redraws
  within a couple of seconds of a record changing or a new commit. It keeps the open tab,
  folds, filters, open panels and scroll, and waits while you type in a filter.
  - The page checks a cheap fingerprint and fetches the model only when it moves. The
    server rebuilds at most once per interval, however many tabs are open, and keeps the
    last good model if a record is caught half-written.
  - The header shows "Live" or "Disconnected". A stopped server leaves the last data on
    screen.
  - It serves exactly three read-only paths and refuses a Host header that is not this
    machine. The page carries record contents, so DNS rebinding cannot reach it.
  - `--port` (default 8765, the next free one if taken, `0` for any) and `--interval`
    tune it. It needs Python 3.7 or newer.

## 3.4.0 — 2026-09-29

This release also carries the 3.3.0 changes below, which went out under that version
number without their own heading.

- **`sdlc.py view`: the records drawn as an interactive page.** It reads the backlog,
  worklog, plans, reviews, defects, postmortems, ADRs and git history each time it runs, and
  joins them by work item ID. The page has a map, board, activity feed, waiting-on-you
  queue, item pages with a lifecycle stepper, documents with an outline, and search.
  - The page goes to `.ai-sdlc/view/index.html`, which git ignores, and works offline.
    Record text is only ever inserted as text.
  - Rows it cannot read are listed on the page rather than dropped.
  - `view.py` and `view.html` are installed and upgraded with the runtime.
- **`sdlc.py metrics`: process measures from the records and git.** Each is labelled
  leading or lagging and names its source: work in progress, time waiting on a human,
  verify pass rate, throughput, lead time, Done items with a lifecycle gap, and plans
  updated after the build started. The view's home page shows them too.
- **The lessons loop:**
  - `AGENTS.md` §9 gains "Known agent mistakes".
  - `/sdlc-review` and `sdlc-postmortem` add a line there when a finding is seen a second
    time, and propose a hook or check when the mistake is decidable from a tool call.
  - `doctor` warns when the list passes 30 lines.
- **Evaluating the agent's own setup** (`04-quality-gates.md`): 20–50 real tasks, run when
  `AGENTS.md`, skills, hooks or the model change. Every S0/S1 caused by the agent's
  behaviour adds one.
- **Agents in pipelines and environments** (`04-quality-gates.md`):
  - The agent acts up to the production gate and never past it.
  - Agent CI jobs start read-only and write only as PRs, with short-lived scoped
    credentials.
  - Rollback is rehearsed; `doctor` warns when a runbook's "Last executed" date is missing
    or stale.
  - The charter's Environments table gains "What an agent may do there".
- **Findings enter as intake items** (G6, `sdlc-intake`): alerts, scheduled scans and
  pipeline triage get the same five-line intake as a person's request. Dismissals are
  recorded with a reason.
- **One system of record per kind of record**: a charter row and a rule in
  `07-traceability.md`.
- **OPSEC:**
  - Secrets and personal data never go into a record (`AGENTS.md`).
  - `security.md` gains a checklist for the coding agent's own access, and severity rows
    for pasted secrets, readable secrets and unvetted agent tooling.
  - `sdlc.py verify` masks credential-shaped strings in saved logs and says so.
- **Skill, instruction or check?** A decision rule and a "test that it fires" step in
  `optional/skills/README.md`.
- **Worktrees** (`10-multi-agent.md`): one claimed item per working tree, split by the
  plan's files.
- **Claude harness examples** (`optional/harness/claude/`, never installed): a
  `settings.example.json` that keeps secrets out of reach, with the sandbox on, and a
  `verifier` subagent that reports and never fixes.
- **Fixes:**
  - `secret-guard` missed a credential in a repository's first commit made with
    `commit -a`.
  - "Black Widow" is gone as a display name for the Advanced acquisition profile.
  - Two README claims that cited no source were rewritten to rest on the kit's own
    reasoning.

- **The kit is now called Nuhut** (chickpea), with a logo and a lifecycle diagram in
  `assets/`. Only the name in prose changed: installer messages, the README, the
  `AGENTS.md` header comment, the dashboard, and the LICENSE holder. The `/sdlc-*`
  commands, the `.ai-sdlc/` paths, the plugin ID and the install commands keep the working
  name `ai-sdlc`, so existing installs upgrade unchanged. The README says whether the kit's
  effect on agents has been measured (not yet).

- **Security: the hooks failed open** in three cases an agent can hit by accident. All three
  are fixed and pinned by smoke tests.
  - **Run from a subdirectory:** the hooks were registered as `sh .claude/hooks/x.sh` and
    read `.ai-sdlc/*.txt` relatively. They are now registered through
    `$CLAUDE_PROJECT_DIR` and run from the project root.
  - **A path through `.` or `..`:** it slipped past the glob. Paths are now normalised
    before matching.
  - **A filename containing a quote:** it produced invalid JSON, which the harness treats
    as allow. Every decision is now built by `jq`, through the new shared
    `.claude/hooks/lib.sh`.
  - **Upgrades:** hooks are now kit-managed. `--upgrade` refreshes them and re-anchors
    older registrations in `.claude/settings.json`. Hook files from before this need
    `--upgrade --adopt`, and the upgrade says so.
  - The kit-value benchmark README now says to run bypass-mode runs in a container or VM.

- **Rules the kit only asked for are now enforced** (from a gap analysis against
  Anthropic's AI-native SDLC playbook, whose core rule is "a skill is advisory, a hook is
  deterministic"):
  - Three new opt-in hooks (`--hooks`), all deny-only, since a `deny` holds in every
    permission mode and a documented `ask` does not:
    - `test-lock.sh` denies edits to a reproducing test listed in
      `.ai-sdlc/test-lock.txt`, and to that list.
    - `secret-guard.sh` denies a commit whose staged additions carry a provider-shaped
      credential. It names the kind, never the value.
    - `approval-gate.sh` denies a command matching `.ai-sdlc/gates.txt` unless the session
      was started with `AI_SDLC_APPROVAL=<ticket>`, and denies edits to that list.
  - Each list file is seeded with comments only, so no hook does anything until the
    project adds a line.
  - `05-change-control.md` gains "Fixing a defect": commit the failing reproducing test
    first, lock it, then fix without editing it. `roles/qa.md` defect triage points
    there.
  - `AGENTS.md` §9 says which approvals get a gate. Existing installs keep their §9, as
    `--upgrade` never touches it.
- **Plans can be checked against the diff**:
  - `templates/plan.md` gains "Files that change", "Order of work" and a **Proof** line
    in the test strategy.
  - `sdlc.py plan-check <ID>` lists files the branch changed that the plan does not
    name, and planned paths nothing touched. Plans that predate the new section are read
    from their "Affected surfaces → Code" bullet, `{a,b}` sets included, and
    `<ID>-<slug>.md` names are found.
  - Tried read-only on the plans of two existing installs.
- **Review has a conformance pass and a nit cap**:
  - `02-role-reviews.md`, `/sdlc-review` and `templates/role-review.md` open every Tier
    1/2 ship review with a conformance pass: plan-check, each acceptance criterion traced
    to code and test, and out of scope held. It carries its own severity table.
  - Reviews report at most five S4 findings; the rest are given as a count.
  - The Important/Nit vocabulary is mapped onto the S0–S4 ladder.

- **A runtime for the mechanical half of doctor and verify** (`.ai-sdlc/bin/sdlc.py`,
  installed always, kit-managed, added to older installs by `--upgrade`):
  - `sdlc.py doctor` checks from the files what `/sdlc-doctor` used to ask the model to
    read: unsubstituted placeholders, a missing contract pointer, blank charter commands
    and approvers, undecided modes and roles, stale `last-reviewed` dates, Done items with
    no worklog entry, IDs that do not join across the backlog, worklog and git, worklog
    size, and profile drift. Findings are `fail` or `warn`, and `--strict` exits 1 only on
    `fail`, so a fresh install does not break CI.
  - `sdlc.py verify` runs the charter's `checks.*` commands in the verify order, and writes
    each stage's raw output, exit code, duration and log hash to
    `.ai-sdlc/evidence/<timestamp>/`, which git ignores. A "Verified" claim can now cite a
    file the script wrote.
  - `/sdlc-doctor`, `/sdlc-verify`, and the `sdlc-doctor` and `sdlc-evidence-check` skills
    run the script first and keep only the judgment: severity, behaviour, what to fix
    first. By hand is the fallback when the script or `python3` is absent.
  - Tried read-only on two existing installs. On one it found six worklog IDs missing
    from the backlog, a 3,272-line worklog past rotation, and a profile whose commands were
    never filled in. On the other it found a charter that predates the mode rows.

- **Kit-value benchmark** (`benchmarks/kit-value/`): a pinned, repeatable comparison of
  no kit, the kit, and the kit with `--hooks`, over five fixture tasks (a shared-caller
  bug, a trust boundary, a one-word typo, a refactor, and a verification trap whose suite
  cannot pass). Besides correctness and cost it measures fabricated verification claims
  (commands claimed as passing that the transcript never ran), commit and worklog
  traceability, and records created for a Tier 3 change. `run.py` isolates each run in a
  fresh workspace and a throwaway Claude config; `score.py` refuses N<4 and reports each
  arm against the control. No result is claimed yet.
  - The effort-mode scorer's validation now lives in `benchmarks/lib/scoring.py`, shared
    by both benchmarks. Its CLI and output are unchanged.
  - `validate.py` runs both scorers' and the measurement self-tests, and checks each task
    has its prompt, fixture and checks. `tests/smoke.py` drives the runner end to end
    with a fake agent.

- **Ephemeral test environment lifecycle and teardown**:
  - `AGENTS.md` (§7 & §8) and `CARD.md`: added a binding rule requiring agents to
    tear down ephemeral test environments (Docker containers, compose services,
    mock daemons, local test servers) immediately upon completion (pass, fail,
    or abort), leaving no idle containers or orphaned processes on the dev host.
  - `process/00-operating-model.md`: step 5 (`VERIFY`) mandates environment teardown
    before entering `SHIP REVIEW`.
  - `process/03-ready-and-done.md`: added a Definition of Done gate under Quality
    requiring all test environments to be stopped and host resources released.
  - `process/04-quality-gates.md`: added an Ephemeral test environments & resource
    teardown section with lifecycle encapsulation, resource bounds, and an S3/S2
    severity rating for orphaned test resources.
  - `roles/devops-sre.md` and `roles/qa.md`: added host & test-environment hygiene
    to design-review, ship-review, and severity calibration tables.
  - `templates/test-plan.md` and `charter.md`: added a dedicated test environment
    lifecycle table and command encapsulation guidance.
  - `optional/claude-commands/sdlc-verify.md`: added step 7 for teardown.

- **Corrections to the 3.3 additions**:
  - `project/defects/` now exists, with an index; two documents already pointed at it.
  - `templates/defect-report.md` no longer carries its own copy of the severity ladder,
    which had already drifted (it left out cross-tenant exposure and latent S0-class
    defects). It points at `04-quality-gates.md` instead.
  - `roles/qa.md` defect triage places an S2 in `Now` unless a named human waives it,
    matching the ladder, instead of `Next`.
  - `03-ready-and-done.md`: an upstream spec satisfies readiness only when it actually
    contains an observable outcome, testable criteria, and its open questions — as
    `sdlc-intake` already said.
  - `roles/security.md`: a charter that does not require MFA means the reviewer does not
    block on it, not that the reviewer may not mention it. Privileged access without MFA
    is recorded as a risk.

- **Upgrades reach `AGENTS.md`, the commands, and the charter**:
  - `AGENTS.md` now marks sections 1–8 as kit-managed. `--upgrade` replaces them and
    records their checksum, so a local edit there stops the upgrade instead of being
    overwritten; section 9, "Project overrides", is never touched. Before this, an
    upgraded project's process documents referred to effort modes and a solution ladder
    that its `AGENTS.md` did not contain.
  - The `/sdlc-*` commands are managed files, tracked in the manifest like the docs.
  - The charter gains, blank and in the right table, any row a newer kit added — never an
    edit to an existing row.
  - `--adopt` takes over `AGENTS.md` and the commands in a project installed before this
    version, once, after a backup. A plain `--upgrade` says when it is needed.
  - `-y` writes a mode row only when `--effort-mode` or `--acquisition-profile` was given.
    A row still listing every option is *undecided*, and `/sdlc-doctor` reports it as a
    question rather than an invalid value.

- **Deployment platform checklists; the core is stack-neutral again**:
  - The process documents, role playbooks, charter, and release runbook no longer name a
    vendor. The previous additions of Dokploy, Traefik, Cloudflare, GA4/GTM, Search
    Console, AWS, and GCP specifics — and the pre-filled environment rows and example
    URLs in the charter and runbook, which an agent would have read as facts — are
    replaced with neutral checks and blank rows.
  - The platform-specific failure modes moved to `optional/platforms/`, one checklist per
    platform: Cloudflare Workers & Pages, Cloudflare in front of an origin, Vercel,
    Netlify, Fly.io, Railway, Render, Heroku/Dokku, Dokploy, Coolify, Kamal, a
    self-managed VPS, Kubernetes, AWS, Google Cloud/Firebase, Azure, and DigitalOcean App
    Platform. Each installs into `docs/platforms/` only for a platform the project uses.
  - The installer detects platforms from deploy configuration (never from an SDK import,
    and never from a bare Traefik label), pre-selects them in a new wizard question, and
    records the answer in the charter's new **Deployment platforms** row and in
    `profile.json` → `deploy_platforms`. `--deploy <list>` answers it for `-y` runs;
    detection alone installs nothing.
  - `roles/devops-sre.md`, `sdlc-release`, the release runbook, and `/sdlc-doctor` read
    the row and its checklists. `validate.py` keeps the catalog, the files, and the index
    in step.

- **Lean / Normal / Beast effort modes**:
  - Added a project default plus explicit work-item override, resolved independently of
    risk tier. Lean minimises optional work, Normal keeps the balanced workflow, and
    Beast maximises investigation and verification without widening product scope.
  - Added the repository → standard-library → native-platform → installed-dependency →
    minimum-custom-code ladder and root-cause caller tracing to the operating contract.
  - Added installer flags, charter fields, profile schema 2, plan/worklog recording,
    reviewer/subagent propagation, validation, and upgrade-safe defaults.
- **Separate acquisition profiles**:
  - Replaced the ambiguous Beast scraping waiver with `Standard` and `Advanced`
    capability profiles. Advanced (display name **Black Widow**) enables additional
    extraction techniques on owned or explicitly authorised targets.
  - Reachability no longer substitutes for permission: authentication, paywalls,
    CAPTCHA, explicit denial, and other access controls remain stop conditions without
    target-owner authorisation or an approved route.

- **External Services & Platform Awareness (Cloudflare, SSL, Search Console, GA4/GTM, AWS/GCP)**:
  - Expanded `charter.md` Stack & Sources of truth tables to explicitly register Cloud providers,
    CDN/Edge/WAF (Cloudflare/CloudFront), SSL/TLS certificates, Search Console verification, and GTM/GA4.
  - Added operational checks in `roles/devops-sre.md` for CDN cache invalidation, SSL termination
    (preventing flexible SSL redirect loops), and Cloud IAM least-privilege.
  - Added verification checks in `roles/seo.md` to prevent accidental clobbering of Search Console
    ownership verification tags/files and ensure sitemap delivery.
  - Added Tag Manager governance in `roles/cro-analyst.md` to prevent GTM scripts from violating CSP
    and enforce environment separation for analytics stream IDs.
  - Updated `templates/release-runbook.md` with post-deploy CDN cache purge and SSL/domain health smoke checks.
- **Flexible Access Level Models & Opt-In MFA/OTP**:
  - Added explicit `Access level model` (`Public`, `Simple`, `RBAC`, `Workspace-Scoped`, `ABAC`)
    and `MFA / OTP policy` (`Not required`, `Optional`, `Enforced for Admin`, `Enforced for all`)
    settings in `charter.md` and `templates/security-privacy.md`.
  - Calibrated `roles/security.md` to prevent dogmatic enforcement of MFA/OTP when declared
    not required, while adding checks for standard practices: auth endpoint rate-limiting,
    CORS/CSRF protections, and session invalidation on password reset.
- **Defect tracking & tester bug reports**:
  - Added `templates/defect-report.md` for capturing tester bug reports, reproduction
    steps, observed vs. expected behaviors, and severity calibrations.
  - Added defect triage and backlog-injection workflows in `roles/qa.md`,
    `07-traceability.md`, `CARD.md`, and the `templates/` registry in `docs/README.md`.
- **Spec-driven development (Spec Kit / Kiro) integration**:
  - `/sdlc-plan` and `sdlc-intake` now explicitly ingest upstream specification files
    (e.g., `specs/`, `spec.md`, or Spec Kit artifacts), adopting problem definitions,
    user stories, and acceptance criteria without asking redundant questions.
  - `03-ready-and-done.md` clarifies that an upstream spec satisfies the FRAME Definition
    of Ready criteria (outcomes, testable criteria, bounded unknowns).
  - `plan.md` and `test-plan.md` templates gained explicit acceptance-criteria mapping
    to connect Given/When/Then scenarios and negative assertions directly into test suites.

## 3.2.0 — 2026-09-03

The question this release answers is whether the kit needs a GUI. Researched rather than
guessed, the answer was: one small read-only page, and distribution — not a web product.
Claude Code Remote Control already drives local sessions from `claude.ai/code` and mobile,
and the independent agent-orchestration GUIs have not found a business model (Bloop, the
company behind vibe-kanban, shut down in April 2026 saying exactly that).

### Added

- **`docs/dashboard.html`** — a read-only status page over the installed state. Open it
  from the filesystem; no server, no dependency, no build. Shows open work by status and
  tier, artifacts stale or undated, roles unticked with nobody's reason, check stages with
  no command, budgets and baselines, and whether anything points at `AGENTS.md`.
  The page is kit-managed and upgradeable; its state lives in `docs/dashboard-state.js`,
  a project record derived from the files and never from the wizard's answers. It states
  its own generation date and declares itself untrustworthy past the charter's staleness
  window. `validate.py` fails if it invents a backlog status the standard lacks, or if a
  form or `contenteditable` appears in it.
- **`/sdlc-doctor` refreshes the page's state** and is told not to write a value it did
  not read from a file.
- **Claude Code plugin packaging** (`.claude-plugin/`) — `/plugin marketplace add
  rezar-84/nuhut.ai`. Commands only: skills are model-invoked and cost context in
  every turn whether they fire or not, so choosing them per project stays with the
  installer, which is the whole point of the fact model.
- **README positioning** for Spec Kit, Kiro and Tessl (complementary — they specify a
  feature, this governs a change), for the AI app builders (a place to install this, not a
  thing to replace), and for why there is no web UI.

### Not built, deliberately

A web installer, and a Lovable-style surface driving local agents. Both are argued in the
README and the decision record; the second belongs in a separate repository that consumes
this kit, if it is ever built at all.

## 3.1.0 — 2026-09-03

Profiling 3.0.0 found three defects and one cost regression. This release fixes them and
makes the kit work outside Claude Code.

### Fixed

- **The kit could install itself into permanent silence.** The `CLAUDE.md` pointer was
  written only when no `CLAUDE.md` existed — which is almost never in a real project — so
  `AGENTS.md` was never auto-loaded and nothing was printed about it. An existing
  instruction file is now appended to (never overwritten), re-running adds no second
  pointer, and an install that wires nothing warns loudly and prints the line to add.
- **A compact install could never be upgraded**, because `find_docs()` used a numbered
  process document as the marker for an installed kit.

### Added

- **`docs/CARD.md`** — the operating card. 2,252 tokens covering tiers, the seven
  evidence words, the check sequence, the severity ladder, verdicts and traceability. It
  replaces reading `02`, `04`, `06` and `07` for ordinary work; those become named
  escalation, and the full document wins wherever they disagree. `validate.py` reads the
  rules the card actually asserts and fails if it invents or drops one.
- **`--harness <list>`** — pointer files for Claude Code, Gemini CLI, Amp, Copilot,
  Cursor, Windsurf, Cline and Aider. Codex, Jules, Zed, Factory and opencode read
  `AGENTS.md` directly and are told so. Pointers reference; they never copy.
- **`--profile compact`** — installs the card, roles, templates and project records but
  omits the numbered `process/` documents. For a small context window or a weaker model.
- **`--hooks`** — two deterministic Claude Code guards: a commit with no work item ID is
  denied, and an edit to a path in `.ai-sdlc/protected.txt` is denied. Merged into an
  existing `settings.json` without disturbing it.
- **`process/10-multi-agent.md`** — claiming, single-writer files, review fan-out, why a
  subagent's result is *Reported* and not *Verified*, and handoff. Conditional.
- Charter: **Agent environment** and **Concurrency** tables. `/sdlc-doctor` checks that
  something points at `AGENTS.md` and rates its absence the highest finding it can make.

### Changed

- **The always-list costs 11,624 tokens instead of 18,222** — a 36% cut, and 26% below
  where 3.0.0 started. A Tier 2 change with two roles: 22.7k full, 17.3k compact.
- `AGENTS.md`'s per-tier figures are measured, and CI fails if they drift.

### Upgrading

`--upgrade` delivers `CARD.md` and `10-multi-agent.md`. Merge the `AGENTS.md` reading-list
changes with the printed `diff` — Tier 2 and Tier 1 now read the card instead of four
process documents, and that is the whole token saving. Copy the new charter tables if the
project needs them. `--harness`, `--profile` and `--hooks` apply to a fresh install.

## 3.0.0 — 2026-09-03

The kit covered web and content projects well and engineering-heavy ones barely. This
release closes that without growing what a web project *reads*: every review, skill, and
gate is fact-gated, and a content site's role roster and installed skills are byte-for-byte
what 2.5.0 produced (a smoke test asserts exactly that).

What does grow is the portable tree on disk. `docs/process/`, `docs/roles/`, and
`docs/templates/` are installed whole in every project, as they always have been, so that
`--upgrade` can manage them and a project can activate a role later without reinstalling.
A content site therefore gains eleven files it never opens: the reading list in
`AGENTS.md` §3 is what bounds an agent's context, and an inactive role's playbook is not
on it. `09-probabilistic-and-data-systems.md` says so in its own opening line.

### Added

- **`Measured`**, a seventh word in the verification vocabulary, for results that are
  numbers rather than passes. It carries method, subject version, N, spread, and date, or
  it is not a claim. A metric with no baseline is not an improvement, it is a number.
- **`process/09-probabilistic-and-data-systems.md`** — models, prompts, retrieval,
  datasets, pipelines, and acquisition. Read only when a change touches one.
- **Three role playbooks**: `data-engineer`, `ml-engineer`, `performance-engineer`.
- **Four extensions to existing playbooks**: `architect` gains asynchronous and
  distributed review plus a clean-code block; `security` gains supply chain and AI/agent
  surfaces; `qa` gains testing non-deterministic systems; `privacy-legal` gains acquired
  data, third-party inference, and generated-content disclosure.
- **Six templates**: `eval-plan`, `data-contract`, `pipeline-runbook`,
  `performance-budget`, `service-catalog`, `model-and-dataset-card`.
- **Seven skills**: `sdlc-eval-gate`, `sdlc-data-contract`, `sdlc-migration`,
  `sdlc-service-contract`, `sdlc-perf-budget`, `sdlc-scrape-compliance`, and
  `sdlc-doctor` (installed always).
- **Four conditional check stages** — `checks.infra`, `checks.data`, `checks.eval`,
  `checks.perf` — with charter rows, installer questions, and CI scaffolding.
- **`.ai-sdlc/profile.json`**, the charter in machine-readable form, so a command or
  skill can branch on the project's facts and commands without parsing prose. The
  charter remains the source of truth and wins on conflict.
- **`/sdlc-doctor`**, the first check that audits an installed project rather than the
  kit's own source: placeholders, blank commands, undecided roles, stale artifacts,
  traceability gaps, worklog size, profile drift.
- Detection for ML/LLM, vector stores, data orchestration and warehouses, messaging,
  IaC, acquisition, and load tooling — each feeding a project-type default.
- A worklog rotation threshold in `07-traceability.md`. The worklog is on the always-read
  list and grew unbounded, one invisible entry at a time.
- Cross-reference validation (roles, templates, skills, and check stages must agree
  everywhere they are named) and a guard that fails if `AGENTS.md`'s stated docs-tree
  size drifts from the measured one.

### Changed

- **Twelve project types and eleven facts**, up from eight and six. `TYPE_FACTS` is keyed
  by fact name rather than position.
- `/sdlc-verify` reads the profile for exact commands, runs the conditional stages, and
  reports `Measured` where the result is a number.
- `AGENTS.md`: prompt, model, retrieval, dataset, and contract changes have explicit tier
  triggers; the reading-list token figures are now measured rather than estimated.
- The installer derives charter command labels from the stage key instead of zipping
  against a parallel list.

### Upgrading

`--upgrade` delivers the new process document, role playbooks, and templates to an
existing installation, and leaves `AGENTS.md` and `docs/project/` alone as always. Two
things need a hand:

- Merge the `AGENTS.md` changes (sections 2, 3, 5, and 7) with the printed `diff`.
- The new charter sections — **Budgets**, **Model & data**, **Data ownership**, the three
  role rows, and the four `checks.*` rows — are not added to an existing charter, because
  the file is project-owned. Copy them from `template/docs/project/charter.md` if the
  project has those surfaces.

New skills are not added by an upgrade; `ls optional/skills` shows what is available.

## 2.5.0 — 2026-08-23

### Added

- Stack adapters for Node/TypeScript, Python, Go, Rust, PHP, Ruby, Maven/Gradle, and .NET.
- ORM, database-driver, migration-tool, and testing-tool detection across those ecosystems.
- `--scaffold-tests` for an instantiated test plan and machine-readable testing profile.
- `--scaffold-ci github|gitlab` for opt-in pipelines generated from confirmed commands.
- Adapter and scaffolding fixtures covering supported language and database families.
- Polyglot command composition so every detected language participates in each quality stage.
- Manifest-managed template upgrades, allowing new testing and data-model guidance to
  reach existing installations without touching project records.

### Safety

- Scaffolding never installs dependencies and never overwrites existing test plans,
  profiles, or CI configuration.
- CI generation refuses repositories with no detected or confirmed quality commands.
- Generated CI is manual-only until a human confirms commands, runtimes, and services.
- Generated database guidance requires real-engine integration tests, migration/restore
  exercises, and synthetic test data.

## 2.4.0 — 2026-08-23

### Added

- Machine-readable manifests for portable managed files.
- Upgrade preflight checks, backups, obsolete-file cleanup, atomic writes, and rollback.
- Stack-neutral validation, continuous integration, and tag-based release automation.
- AI prompt-injection, secret-disclosure, and permission-escalation boundaries.
- Repository licensing, contribution guidance, and a security policy.
- Detection for integration, contract, accessibility, and common namespaced test scripts.

### Changed

- `--docs-dir` now updates the operating contract and Claude commands completely.
- Tier 3 uses a compact reading and worklog path.
- Dry runs and pre-confirmation quits no longer create target directories.
- Detected format, install, typecheck, and lint commands favor non-mutating,
  reproducible, locally installed tools.

## 2.3.0

- Added the navigable installer, localisation role, and architecture seeding.

Earlier history is available in the repository's Git log.

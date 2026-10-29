# Design: what the kit is, and is not

Why the kit is shaped the way it is. The [README](../README.md) is the short version.

## What it deliberately does NOT do

- **No tech stack.** No framework, language, package manager, cloud, CI system, or test
  runner is named anywhere in the process docs. Each project declares its own in
  `docs/project/charter.md`, and everything else refers to it indirectly ("the project's
  typecheck command"). Where it deploys is the one place a platform's name is useful —
  Vercel and a hand-run VPS fail in different ways — so those checks live in opt-in
  [deployment checklists](#deployment-platforms), installed only for the platforms a
  project names.
- **No architecture.** Monolith, monorepo, serverless, microservices, a single script —
  all fine. The architect role reviews *whatever the project chose* against its own
  stated constraints.
- **No domain assumptions.** Works for a marketing site, an internal CLI, a data
  pipeline, a RAG service, a microservice fleet, a Terraform repository, a crawler, a
  mobile app, a library, or a docs-only repo. Roles that do not apply are switched off in
  the charter, not awkwardly forced.
- **No ceremony tax.** A one-line copy fix does not trigger sixteen role reviews. Risk
  tiers (defined in `AGENTS.md`) scale both the process and the *reading* to the change —
  a Tier 3 fix has a reading list of one charter section.

## What it covers

Setup asks what the project is, and the answers decide which of the sixteen roles review
your work and which of the twenty-two skills get installed. Nothing below is on by
default. The portable `docs/` tree is copied whole either way — that is what makes
`--upgrade` work — but an inactive role's playbook is not on any reading list, so a
marketing site's agent reads what it read in 2.5.0.

| If the project… | It gets |
| --- | --- |
| has an interface | UX, brand, copy, accessibility review; design-system and a11y skills |
| is publicly discoverable | SEO and content review; content/SEO skill |
| deploys anywhere | DevOps/SRE review; release runbook, release and postmortem skills |
| holds personal data | privacy/legal review; privacy and threat-model skills |
| **owns datasets or pipelines** | data-engineer review; data contracts, pipeline runbook, data-quality gate, contract and migration skills |
| **has models, prompts, or retrieval** | ml-engineer review; eval plan, model/dataset card, evaluation gate, the `Measured` doctrine, prompt-injection and agent-permission checks |
| **runs several services or messaging** | asynchronous and distributed architecture review; service catalogue with SLOs, cross-boundary contract skill |
| **carries a latency, throughput, or cost budget** | performance-engineer review; performance budgets with recorded baselines |
| **provisions infrastructure** | an infrastructure plan/policy stage that a human reviews before it is applied |
| **acquires third-party data** | terms, robots, rate-limit, and provenance obligations checked before the fetcher is written |
| has a data layer of any kind | the migration skill: expand/migrate/contract, lock analysis, tested reverse paths |

Two things run through all of it. **Nothing probabilistic may be claimed to have
improved without a baseline** measured before the change on a golden set that is not also
changing — the kit gives that its own word, *Measured*, with the five things it must
carry. And **a prompt is executable**: it is tiered by the surface it governs, not by
being a string.

## How this relates to Spec Kit, Kiro, and the AI app builders

**Spec-driven development tools are complementary, not alternatives** — and since 4.1 the
kit carries the part most teams installed them for: opt-in living specs with WHEN/THEN
scenarios and per-item changes (`process/15-specs.md`), in the same headings OpenSpec uses, so
an existing `openspec/` or Spec Kit folder is read alongside rather than migrated. GitHub Spec Kit,
AWS Kiro and Tessl answer *what should this feature do, precisely, before an agent builds
it*. This kit answers *how does every change get made, reviewed, verified and recorded* —
risk tiers, sixteen role playbooks, the evidence vocabulary, the severity ladder,
traceability. Neither has the other's content. Use Spec Kit to specify the feature and
this to govern the change; the process documents here never dictate how a requirement is
written. When you have a spec file, pass it directly to `/sdlc-plan <path-to-spec>` — the
command ingests its acceptance criteria and scope without re-asking questions.

**AI app builders are a place to install this, not a thing to replace.** An app builder
produces code faster than anyone reviews it, and the review, verification and record of
why each change was made are exactly what it leaves out. That is what this kit is. So the
installer detects a managed platform, the charter declares the sync model and the files
the platform owns, and `05-change-control.md` yields to that table where they conflict —
see [Installing into a managed platform](#installing-into-a-managed-platform-lovable-replit-bolt-)
below. The answer to "AI builders have no discipline" is to be the discipline they
install.

**A web UI for driving agents is deliberately not here.** Steering an agent session
belongs to the harness itself (such as a terminal, an IDE integration, or Claude Code
Remote Control). What a repository-level kit needs is a way for the human to *see* the
work while the agents do it, and to tune kit constraints without hand-editing tables, so
that is what the kit ships: [the viewer](runtime.md#seeing-the-work)
(`sdlc.py view`, live with `--serve`, or a single static file with `--export-html`).
Static exports are strictly read-only; live `--serve` mode adds session-authenticated
controls for charter constraints and safe kit repairs (`sdlc.py config` / `sdlc.py fix`),
never starting an agent or approving gated work on a human's behalf.

## The three kinds of file

Keeping these separate is the main structural idea of the kit.

| Kind | Lives in | Edited | Purpose |
| --- | --- | --- | --- |
| **Standard** | `docs/process/`, `docs/roles/` | Almost never, and only deliberately | Defines how work is done. Identical across projects, so an agent's behaviour is predictable everywhere. |
| **Template** | `docs/templates/` | Never (copied, not edited) | Blank forms. Copy into `docs/project/` when the project needs that artifact. |
| **Project record** | `docs/project/` | Constantly | This project's truth: charter, backlog, worklog, decisions, reviews, risks. |

A common failure in hand-rolled agent docs is mixing these — process rules get buried
inside a project brief, so they cannot be reused, and project facts get written into
process docs, so they go stale silently. Do not merge the directories.

## Conventions used in the docs

- `{{PLACEHOLDER}}` — a value to find-and-replace at install time.
- `_(fill in)_` — prose you write per project; delete the marker when filled.
- `<angle brackets>` — an example value in a command or path.
- Every artifact in `docs/project/` carries a frontmatter block with `status`, `owner`,
  and `last-reviewed`. An agent must treat a missing or old `last-reviewed` as a signal
  that the document may not describe reality — verify before relying on it.

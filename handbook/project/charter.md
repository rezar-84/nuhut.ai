---
status: active
owner: rezar-84
last-reviewed: 2026-11-13
---

# Project charter — nuhut.ai

## Identity

| | |
| --- | --- |
| **Project** | nuhut.ai |
| **What it is** | Zero-dependency AI SDLC and Software Factory kit that gives coding agents risk tiers, role reviews, mechanical hooks, sharded records, and verifiable evidence. |
| **Work item prefix** | `NUHT` |
| **Repository** | `https://github.com/rezar-84/nuhut.ai` |
| **Accountable human** | rezar-84 |

## Stack

| Concern | This project uses |
| --- | --- |
| Language / runtime | Python 3.8+ standard library + POSIX `sh` shims + vanilla HTML/CSS/JS viewer |
| Package manager | none (zero external dependencies) |
| Framework(s) | Python stdlib (`http.server`, `argparse`, `subprocess`, `unittest`) |
| Data store(s) | Git repository + JSON/JSONL/Markdown records |
| Auth & Identity | Local `127.0.0.1` `HttpOnly; SameSite=Strict` session cookie + `Origin` check in `view --serve` |
| Hosting & Cloud provider | Distributed via git / GitHub Releases (runs locally on developer & CI machines) |
| CDN / Edge / WAF | none |
| TLS certificates | none (local loopback only) |
| CI | GitHub Actions (`.github/workflows/ci.yml`, `version.yml`; `version.yml` also releases) |
| Test tooling | `validate.py`, `optional/runtime/sdlc.py --selftest`, `tests/smoke.py` |

## Constraints

| | |
| --- | --- |
| **Team / who maintains this** | Maintainer (`rezar-84`) + autonomous multi-agent coding sessions |
| **Operational capacity** | Local CLI + stateless GitHub Actions CI across Linux and macOS |
| **Budget ceiling** | Zero mandatory paid runtime services; paid LLM benchmark runs are opt-in |
| **Latency / throughput** | `sdlc.py doctor` `< 500ms` warm cache; hooks `< 100ms` per tool call |
| **Existing platform commitments** | Python 3.8+ stdlib compatibility on macOS and Ubuntu Linux |
| **Timeline** | Milestone-driven (`kit-v5` Software Factory release) |

## Commands

| Stage | Command |
| --- | --- |
| Install | `python3 validate.py` |
| Run locally | `python3 .ai-sdlc/bin/sdlc.py view --serve --no-open` |
| `checks.format` | absent — enforced via `validate.py` and stdlib compilation |
| `checks.lint` | `python3 validate.py` |
| `checks.typecheck` | absent — pure Python 3.8+ stdlib without third-party typechecker |
| `checks.unit` | `python3 optional/runtime/sdlc.py --selftest` |
| `checks.integration` | `python3 tests/smoke.py` |
| `checks.contract` | absent — CLI/JSON contracts are verified inside `validate.py` and `tests/smoke.py` |
| `checks.build` | `python3 tools/build_view.py --check` |
| `checks.scan` | absent — zero third-party dependencies to scan |
| `checks.a11y` | absent — checked in viewer smoke suite and manual review |
| `checks.e2e` | absent — covered end-to-end by `tests/smoke.py` |
| `checks.complexity` | absent — reading and file budgets enforced by `validate.py` |
| `checks.mutation` | absent — planted-bug bite tests run in `tests/smoke.py` |
| `checks.infra` | absent — no provisioned cloud infrastructure |
| `checks.data` | absent — no external data pipelines |
| `checks.eval` | absent — benchmark suites under `benchmarks/` are run on demand |
| `checks.perf` | absent — latency assertions live in `tests/smoke.py` |

## Environments

| Environment | Purpose | Deployed from | Who may deploy | What an agent may do there |
| --- | --- | --- | --- | --- |
| local | development, dogfooding, and smoke verification | working tree / feature branches | developer or agent | run all checks and local viewer freely |
| ci | automated multi-OS verification | pull requests and branch pushes | GitHub Actions | read-only validation and test execution |
| release | tagged GitHub releases | `main` (`v*.*.*` tags) | `rezar-84` via GitHub Actions | prepare changelog and branch; human merges and tags |

| | |
| --- | --- |
| **Default branch** | `main` |
| **Direct commits to it** | not allowed — feature branches (`kit-v5`, `feat/NUHT-*`) merge after review |
| **Updating a branch** | `merge` |
| **Deployment platforms** | `none` |
| **Versioning** | `semver` |
| **Changelog** | `CHANGELOG.md` (Keep a Changelog with `Unreleased`) |
| **Who bumps and tags** | `rezar-84` (assisted by `tools/semver.py`) |

### Managed platform

| | |
| --- | --- |
| **Platform** | none |
| **Sync model** | git only |
| **Platform-owned files** | none |
| **Platform instruction file** | none |
| **Deploys** | none |

## Agent environment

| | |
| --- | --- |
| **Documentation profile** | full |
| **Minimum context window** | 128k tokens |
| **Agent tools in use** | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursor/rules/agents.mdc`, `.cursorrules` |

## Concurrency

| | |
| --- | --- |
| **Agents working here** | several in parallel (isolated git worktrees via `sdlc.py claim` / `sdlc.py dispatch`) |
| **Claiming a work item** | `python3 .ai-sdlc/bin/sdlc.py claim <ID>` (isolated worktree + sharded item state) |
| **Single-writer files** | `VERSION`, `.claude-plugin/plugin.json`, `optional/runtime/view.html` |
| **May merge to the default branch** | no — pull requests / human merge only |
| **Worktree scripts** | none |

## Budgets

| What | Budget | Measured how, and where | Current baseline |
| --- | --- | --- | --- |
| `AGENTS.md` word ceiling | `<= 1,200 words` | `python3 validate.py --reading-lists` | ~1,020 words |
| Tier 2 reading list | `<= 5,500 words` | `python3 validate.py --reading-lists` | ~4,950 words |
| Tier 1 reading list | `<= 22,000 words` | `python3 validate.py --reading-lists` | ~18,900 words |

## Model & data

| | |
| --- | --- |
| **Providers and pinned versions** | none on runtime path (headless review/dispatch invokes user's local `claude`, `codex`, or `gemini` CLI) |
| **What may be sent** | repository diffs and prompts when user explicitly invokes `sdlc.py review` or `sdlc.py dispatch` |
| **What may never be sent** | secrets, credentials, `.env` files, private keys (redacted by `hooks.py` / `sdlc.py`) |
| **Retention** | local `.ai-sdlc/` logs only; nothing retained externally by the kit |
| **May be trained or tuned on** | none |
| **Golden set** | `benchmarks/kit-value/tasks/` and `benchmarks/effort-modes/tasks/` |
| **Human in the loop** | Tier 1 plan and merge approvals (`rezar-84`) |

## Data ownership

| Dataset / stream | Owner | Consumers | Contract | Acquired from |
| --- | --- | --- | --- | --- |
| none | none | none | internal only | produced here |

## Active roles

| Role | Active | Active if | Reason if inactive |
| --- | --- | --- | --- |
| product-manager | ☑ | always | |
| architect | ☑ | always | |
| security | ☑ | always | |
| qa | ☑ | always | |
| ux-designer | ☑ | there is any interface, including a CLI | |
| brand-designer | ☐ | there is a visual interface | kit ships developer CLI and local operational viewer, not consumer brand surfaces |
| copywriter | ☑ | there is any user-visible text | |
| accessibility | ☑ | there is any interface | |
| seo | ☐ | content is publicly discoverable | repository documentation and local viewer are not search-indexed web properties |
| cro-analyst | ☐ | there is a conversion or activation goal | open-source CLI kit with no funnel or telemetry |
| devops-sre | ☑ | it deploys or runs somewhere | |
| privacy-legal | ☐ | personal data, tracking, or public claims exist | holds zero personal data or telemetry |
| localisation | ☑ | it ships in more than one language | |
| data-engineer | ☐ | this project owns a dataset, a pipeline, or acquires third-party data | no production data pipelines |
| ml-engineer | ☐ | a model, prompt, or retrieval step is on the product path | kit governs agents via deterministic stdlib tools rather than shipping an ML model |
| performance-engineer | ☑ | there is a backend, data, or model workload carrying a latency, throughput, or cost budget | |

## Risk defaults

| | |
| --- | --- |
| **Default effort mode** | `Normal` |
| **Development method** | `Item` |
| **Specs** | `off` |
| **Slop filter** | `on` |
| **Decision style** | `Guide` |
| **Tier rules** | `Standard` |
| **Acquisition profile** | `Standard` |
| **Always Tier 1 here** | Hook security enforcement (`optional/runtime/hooks.py`), `view --serve` HTTP control plane, release workflow (`.github/workflows/**`) |
| **Never Tier 1 here** | No PII or payment processing exists in this repository |
| **Human approval required for** | Cutting a release tag, merging to `main`, weakening security hooks, or removing CLI commands |
| **Independent review required for** | `none` |
| **Discovered defects** | `Parked` |
| **Finish guard** | `on` |
| **Agent budget per tier** | Tier 3: 50k tokens, 10 min; Tier 2: 300k tokens, 45 min; Tier 1: 1.5M tokens, 3 h |
| **Approvers** | rezar-84 |
| **Tier 1 approvals** | `1` _(one-person project; raise to `2` when a second approver joins)_ |
| **Local approvals** | `on` _(one-person project: the owner approves with `sdlc.py approve` in a terminal; turn off when GitHub reviews by a second approver are available)_ |
| **Extensions allowed** | none |
| **Staleness threshold** | 365 days |

## Standards & targets

| | |
| --- | --- |
| **Access level model** | `Simple Owner/User` |
| **MFA / OTP policy** | `Not required` |
| **Session & Token policy** | Per-process random 128-bit `HttpOnly; SameSite=Strict` cookie + strict `Origin` header check on `127.0.0.1` |
| **Accessibility target** | WCAG 2.2 AA on `optional/runtime/view.html` and `NO_COLOR` / ASCII support in CLI |
| **Assistive technologies supported** | Keyboard navigation and semantic ARIA landmarks in viewer; plain-text CLI mode |
| **Supported platforms / browsers / sizes** | macOS and Linux (Python 3.8+); evergreen desktop browsers for `view.html` |
| **Performance budgets** | `AGENTS.md <= 1,200 words`; `sdlc.py doctor < 500ms` warm |
| **Primary outcome** | Zero-conflict, verifiable multi-agent software delivery |
| **Jurisdictions / regimes** | Open-source MIT software; zero personal data collected |
| **Allowed in records** | `rezar-84` |
| **Data categories held** | none — repository holds only source code, templates, and synthetic test fixtures |

### Languages & localisation

| | |
| --- | --- |
| **Ships in** | `en, fa, tr` (installer UI locales in `optional/locales/`) |
| **Source language** | `en` |
| **Writing directions** | both (`en`, `tr` left-to-right; `fa` right-to-left) |
| **Message catalogue** | `install.py` (`EN`) and `optional/locales/*.json` |
| **Translation workflow** | Maintainer + `localisation` role review |
| **Terminology / glossary** | `template/docs/CARD.md` |

## Sources of truth

| Thing | Where |
| --- | --- |
| Brand guidelines | none |
| Design tokens | `optional/runtime/view/01-head.html` |
| Analytics / tag manager | none |
| Search engine webmaster tools | none |
| Content source | `template/`, `optional/`, `docs/` |
| Secrets | none in repo; CI uses ephemeral `GITHUB_TOKEN` |
| Issue tracker _(if not `backlog.md`)_ | `handbook/project/` (authoritative in-repo records) |
| System of record | This git repository (`handbook/project/`) |
| Repository license | MIT (`LICENSE`) |

## Artifacts in use

☐ product-brief ☐ discovery-audit ☐ user-stories ☐ architecture ☐ data-model-api
☐ design-system ☐ content-seo-plan ☐ measurement-plan ☐ security-privacy
☐ threat-model ☐ test-plan ☐ release-runbook ☐ service-catalog
☐ data-contract ☐ pipeline-runbook ☐ eval-plan ☐ model-and-dataset-card
☐ performance-budget

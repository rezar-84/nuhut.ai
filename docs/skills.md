# Skills

The model-invoked skills, and when each is installed.


`optional/skills/` is a catalogue of twenty-one skills that make the process fire on its own.
The slash commands wait to be typed; skills are model-invoked — the agent loads one when the
situation its description names actually appears.

| Skill | Fires when | Installed when |
| --- | --- | --- |
| `sdlc-intake` | a request arrives with no work item | always |
| `sdlc-evidence-check` | about to claim "done", "passing", "verified" | always |
| `sdlc-charter-audit` | before relying on the charter, or when it looks stale | always |
| `sdlc-adr` | a decision would be expensive to reverse | always |
| `sdlc-accessibility-audit` | UI is added or changed | there is an interface |
| `sdlc-design-review` | screens, components, or tokens change | there is a visual interface |
| `sdlc-content-seo` | public pages, copy, routes, or metadata change | content is public |
| `sdlc-privacy-review` | forms, analytics, tracking, logs, or claims change | personal data is held |
| `sdlc-threat-model` | auth, uploads, payments, or an external interface appears | data is held, or it deploys |
| `sdlc-release` | shipping to a real environment | it deploys |
| `sdlc-postmortem` | something broke, or a release was reverted | it deploys |
| `sdlc-i18n-audit` | strings, screens, or locales change | it ships in 2+ languages |
| `sdlc-translation-review` | content appears in a non-source language | it ships in 2+ languages |
| `sdlc-managed-platform` | editing platform config, history, or deploys | a platform co-owns the repo |
| `sdlc-doctor` | the project's own documents may not describe reality | always |
| `sdlc-migration` | a schema migration or backfill appears | a data layer was detected |
| `sdlc-data-contract` | a schema, pipeline output, or event payload changes | there are datasets, or data is acquired |
| `sdlc-eval-gate` | a prompt, model, retrieval config, or quality claim changes | models or retrieval are on the product path |
| `sdlc-service-contract` | an API or event contract crosses a service boundary | several services, or messaging |
| `sdlc-perf-budget` | a hot path, query, payload, or cache changes | there is a backend, data, or model workload |
| `sdlc-scrape-compliance` | a fetcher, crawler, or third-party source is added | the project acquires third-party data |

Setup evaluates that list against your answers and installs only what applies — an
unused skill is a description competing for attention in every future context window. Add
one later by copying its directory into `.claude/skills/` and replacing the placeholders.
See `optional/skills/README.md` for how to write your own.

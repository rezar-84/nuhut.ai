# Deployment platforms

The process documents are stack-neutral on purpose: `roles/devops-sre.md` and
`templates/release-runbook.md` say *what* a safe deploy needs, never *where* it runs.
These checklists are the other half — the failure modes specific to one platform, the
ones a generic checklist cannot name.

The installer copies a checklist into `{{DOCS_DIR}}/platforms/` only for a platform the
project uses: one it detected and you confirmed, or one you named with `--deploy`. The
charter's **Deployment platforms** row is authoritative; this directory follows it.

| Checklist | Platform | Detected from |
| --- | --- | --- |
| `cloudflare-workers.md` | Cloudflare Workers & Pages | `wrangler.toml` / `wrangler.json(c)`, `@cloudflare/workers-types`, `@opennextjs/cloudflare` |
| `cloudflare-edge.md` | Cloudflare proxy, CDN, DNS, or WAF in front of another origin | not detectable from a repository — name it |
| `vercel.md` | Vercel | `vercel.json`, `.vercel/` |
| `netlify.md` | Netlify | `netlify.toml` |
| `fly.md` | Fly.io | `fly.toml` |
| `railway.md` | Railway | `railway.json`, `railway.toml` |
| `render.md` | Render | `render.yaml` |
| `heroku.md` | Heroku, Dokku, or another Procfile buildpack host | `Procfile`, `app.json` |
| `dokploy.md` | Dokploy | `dokploy-network` or `dokploy` in a Compose file |
| `coolify.md` | Coolify | `SERVICE_FQDN_` / `SERVICE_URL_` variables or `coolify` in a Compose file |
| `kamal.md` | Kamal | `config/deploy.yml` with `service:` and `image:`, `.kamal/` |
| `vps.md` | A self-managed server — systemd, PM2, nginx, Caddy, SSH or rsync deploys | `Caddyfile`, `nginx.conf`, `ecosystem.config.js`, a root `*.service` unit |
| `kubernetes.md` | Kubernetes — any distribution, Helm, Kustomize | `Chart.yaml`, `kustomization.yaml`, `skaffold.yaml`, `helmfile.yaml`, `k8s/` |
| `aws.md` | AWS — Lambda, ECS, App Runner, Amplify, EC2 | `cdk.json`, `serverless.yml`, `samconfig.toml`, `amplify.yml`, `copilot/`, `apprunner.yaml` |
| `gcp.md` | Google Cloud — Cloud Run, App Engine, Firebase | `cloudbuild.yaml`, `app.yaml`, `firebase.json`, `.firebaserc` |
| `azure.md` | Azure — App Service, Functions, Static Web Apps, Container Apps | `azure.yaml`, `staticwebapp.config.json`, `host.json` |
| `digitalocean.md` | DigitalOcean App Platform | `.do/app.yaml` |

A platform not listed here is still a valid answer: write it into the charter row. The
generic playbook then carries the review alone, and the gap is visible rather than
hidden.

## How to use a checklist

- Read it with `roles/devops-sre.md` at DESIGN REVIEW and with the release runbook at
  RELEASE. It adds checks; it never removes one the role or the tier requires.
- A check that does not fit how this project uses the platform is marked `n/a` with a
  reason, never deleted or silently skipped.
- Platform limits, prices, and defaults change. Where a check names a limit, confirm the
  current figure in the platform's own documentation and record it with a date — a limit
  quoted from memory is *Unverified*.

## Adding one later

Re-run the installer with `--deploy <id>` against the project. It adds the missing
checklist and leaves every existing file alone; then add the platform to the charter's
**Deployment platforms** row. `--upgrade` refreshes the checklists already installed.

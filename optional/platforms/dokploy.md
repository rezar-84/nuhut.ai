# Platform — Dokploy

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. The server Dokploy runs on is also covered by `vps.md` where installed.
Mark a check `n/a` with a reason rather than deleting it.

## Configuration

- [ ] Environment variables and secrets are set in Dokploy, not committed, and not baked
      into the image as build arguments.
- [ ] A Compose deployment does not set `container_name`. It breaks Dokploy's logs,
      monitoring, and running more than one copy of the stack.
- [ ] Services that Traefik routes to are attached to `dokploy-network`, and each domain
      targets the right service and internal port.

## Persistent data

- [ ] Every stateful path — uploads, SQLite files, database data — is a named volume or a
      bind mount under `../files`. The application directory is re-cloned on each deploy,
      so a bind mount inside it is wiped.
- [ ] Database backups are configured to an off-server destination (an S3-compatible
      bucket), and a restore has been done at least once outside production.

## Deploy and rollback

- [ ] A health check is configured for each application. Without one, the new container
      takes traffic before it can serve, and a zero-downtime deploy is not zero-downtime.
- [ ] Auto-deploy on push, or the deploy webhook, targets the charter's default branch
      only. The webhook URL is treated as a secret.
- [ ] Rollback is written down: redeploy a previous commit or image. If the Dokploy
      version in use offers rollbacks, confirm what they require (an image registry)
      before relying on one. Neither reverts migrations or volume data.
- [ ] Migrations run once, as an explicit step, not at start-up in every replica.

## TLS and domains

- [ ] Certificates come from the Let's Encrypt resolver and renew. If the domain is behind
      the Cloudflare proxy, the HTTP challenge may fail — use the DNS challenge or an
      origin certificate, with Cloudflare in Full (strict) mode (see `cloudflare-edge.md`).
- [ ] HTTP redirects to HTTPS for every domain.

## The Dokploy instance itself

- [ ] The Dokploy dashboard is served over HTTPS on its own domain, not on the raw
      server port open to the internet, and admin accounts use two-factor sign-in.
- [ ] Dokploy and Traefik are updated deliberately, with the update noted in the worklog,
      not on a timer nobody watches.
- [ ] Remote servers and registries it deploys to use keys scoped to that purpose.

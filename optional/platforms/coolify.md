# Platform — Coolify

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. The server Coolify runs on is also covered by `vps.md` where installed.
Mark a check `n/a` with a reason rather than deleting it.

## Configuration

- [ ] Secrets are set in Coolify and are **not** flagged as build variables — a build
      variable is baked into the image and readable by anyone who can pull it.
- [ ] In a Compose resource, generated values use Coolify's magic variables
      (`SERVICE_FQDN_<NAME>`, `SERVICE_PASSWORD_<NAME>`) consistently, and nothing depends
      on a value that changes when the resource is recreated.
- [ ] Each domain is assigned to the right service and port, and the proxy in use
      (Traefik or Caddy) is named in the charter.

## Persistent data

- [ ] Every stateful path is a declared persistent volume or a bind mount outside the
      build directory; the container layer is discarded on each deploy.
- [ ] Scheduled database backups go to an off-server S3-compatible destination, and a
      restore has been done at least once outside production.

## Deploy and rollback

- [ ] A health check is configured. Rolling updates apply to single-container
      applications with a passing health check; a Compose deployment is replaced with
      downtime. Confirm this for the installed version and accept it or design around it.
- [ ] Preview deployments for pull requests have their own variables and database, never
      production's.
- [ ] Rollback is written down: redeploy a previous image from the application's
      rollback list. It does not revert migrations or volume data.
- [ ] Migrations run once, as an explicit step, not at start-up in every replica.

## TLS and domains

- [ ] Certificates are issued and renew. Behind the Cloudflare proxy, use the DNS
      challenge, an origin certificate, or a Cloudflare Tunnel, with Cloudflare in Full
      (strict) mode (see `cloudflare-edge.md`).

## The Coolify instance itself

- [ ] The Coolify dashboard is on its own HTTPS domain, not the raw server port open to
      the internet, and admin accounts use two-factor sign-in.
- [ ] Coolify auto-update is a decision, not a default: on, or off with a named person
      who updates it and records it in the worklog.
- [ ] The SSH keys Coolify holds for its servers are scoped to those servers.

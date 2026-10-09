# Platform — self-managed server (VPS or bare metal)

Installed because the charter's **Deployment platforms** row names it. It covers the
host, whatever runs on it: systemd, PM2, Docker Compose, or a PaaS layer such as Dokploy,
Coolify, or Kamal (which have their own checklists). The platform half of
`../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## The host

- [ ] SSH accepts keys only; password and direct root login are disabled.
- [ ] A firewall allows only the ports that are meant to be public (typically SSH, 80,
      and 443). A database or admin port open to the internet is an S1 finding.
- [ ] Security updates install automatically, or someone named applies them on a
      schedule and records it.
- [ ] How the server was set up is written down or scripted (cloud-init, Ansible, a
      shell script in the repository), so it can be rebuilt. A server that only exists in
      its current state cannot be recovered.

## The process

- [ ] The application runs as a dedicated non-root user.
- [ ] A supervisor (systemd, PM2, or a Docker restart policy) restarts it on failure and
      starts it on boot — confirmed by rebooting the server once.
- [ ] The secrets file is readable only by that user (mode `600`) and is not in the
      deployed directory's git history.

## Reverse proxy and TLS

- [ ] Certificates renew automatically, and renewal has been tested (for example
      `certbot renew --dry-run`), not assumed from the day they were issued.
- [ ] HTTP redirects to HTTPS; request-size limits and timeouts are set deliberately.
- [ ] The application trusts forwarded headers (`X-Forwarded-For`, `X-Forwarded-Proto`)
      only from the proxy.

## Deploy and rollback

- [ ] A deploy produces a new release — a release directory switched by symlink, or a
      new image tag — and keeps the previous one, so rollback is switching back.
      `git pull` on the server is not a deploy process.
- [ ] If the deploy restarts the only instance, the downtime is stated in the runbook.
- [ ] Migrations run once, as an explicit step, before or after the switch as the plan
      says.

## Data and capacity

- [ ] A database on the same host is a single point of failure, accepted in writing or
      addressed.
- [ ] Backups go off the host, and a restore has been done at least once on another
      machine.
- [ ] Logs are rotated (journald limits or logrotate), and disk space is monitored. A
      full disk is the most common way a single server goes down.
- [ ] An external uptime check, certificate-expiry alert, and CPU, memory, and disk alerts
      reach someone.

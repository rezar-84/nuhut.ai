# Platform — Kamal

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. The hosts themselves are covered by `vps.md` where installed. Mark a check
`n/a` with a reason rather than deleting it.

## Configuration

- [ ] `.kamal/secrets` holds references — commands that read from environment variables
      or a password manager — never literal secret values, since the file is committed.
- [ ] `config/deploy.yml` names the image, registry, hosts, and roles, and a destination
      file (`deploy.staging.yml`) exists for each non-production environment.
- [ ] The builder produces an image for the hosts' CPU architecture.

## Deploy and rollback

- [ ] The proxy health check path (by default `/up`) answers only when the app can
      actually serve. The zero-downtime switch trusts it.
- [ ] Automatic TLS through the proxy is used only on a single-host deployment, which is
      where it works. Multiple hosts terminate TLS at a load balancer or edge instead.
- [ ] Migrations run once — a pre-deploy hook or an explicit `kamal app exec` step — not
      in every container's entrypoint on every host at once.
- [ ] Rollback is written down: `kamal rollback <version>`, which needs the old image
      still in the registry or on the hosts. It does not revert migrations.

## Accessories

- [ ] Accessories (databases, caches) are not redeployed or upgraded by `kamal deploy`.
      Their upgrades, backups, and restores are planned separately and written down.
- [ ] Accessory data lives on a named volume or host directory, with off-host backups
      and a restore done at least once outside production.
- [ ] Accessory ports are not published to the internet unless that is the point.

# Platform — Fly.io

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Configuration

- [ ] `internal_port` in `fly.toml` matches the port the process actually listens on,
      bound to `0.0.0.0` (or `::`), not `localhost`.
- [ ] Health checks are defined, and they check that the process serves — not that a
      downstream dependency is up.
- [ ] Secrets are set with `fly secrets set`, never in `fly.toml` `[env]`. Setting one
      restarts the machines; the runbook says so.
- [ ] With `auto_stop_machines` on, `min_machines_running` is chosen deliberately: a
      stopped machine means a cold start for the next user, and it kills any background
      work that was still running on it.

## Deploy and rollback

- [ ] Migrations run in `release_command`, which runs once before the new machines take
      traffic and aborts the deploy on failure. With a rolling deploy, old and new code
      run at once, so the schema change must work with both.
- [ ] The deploy strategy (rolling, bluegreen, canary, immediate) is named, and it works
      with this app's volumes and health checks.
- [ ] Rollback is written down: redeploy a previous image (`fly releases --image`, then
      `fly deploy --image <ref>`). It does not revert migrations or volume data.

## Data

- [ ] A volume belongs to one machine in one region and is not replicated. An app that
      needs its data to survive losing that machine replicates at the application or
      database level.
- [ ] Volume snapshots are enabled, their retention is known, and a restore has been
      done at least once outside production.
- [ ] If the database is a self-run Postgres app rather than a managed service, the
      charter says so: backups, upgrades, and failover are this team's job.

## Network

- [ ] Private services are reached over the private network (`<app>.internal`) and have
      no public IP they do not need.
- [ ] Regions are chosen for the users and the database; a machine far from its
      database pays that latency on every query.

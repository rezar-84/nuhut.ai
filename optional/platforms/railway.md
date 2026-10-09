# Platform — Railway

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Configuration

- [ ] Build and deploy settings live in `railway.json` / `railway.toml` in the
      repository. Settings changed only in the dashboard are invisible to review.
- [ ] Variables that point at another service use references (`${{Postgres.DATABASE_URL}}`)
      rather than pasted values that go stale when the other service changes.
- [ ] Each environment, including PR environments, has its own database and credentials.
      A PR environment pointing at production data is an S1 finding.

## Deploy and rollback

- [ ] A health check path is configured, so a deploy that does not come up never takes
      traffic.
- [ ] Migrations run as a pre-deploy command, not at process start in every replica.
- [ ] Rollback is written down: redeploy a previous deployment from the service's
      history. It does not revert migrations or volume data.
- [ ] A service with an attached volume is known to have brief downtime on redeploy (old
      and new instances cannot mount it at once). Confirm this for the current platform
      and accept it or design around it.

## Data

- [ ] Database and volume backups are enabled, their schedule and retention are known,
      and a restore has been done at least once outside production.
- [ ] Internal services talk over the private network (`*.railway.internal`) and are not
      given a public domain they do not need.

## Jobs

- [ ] Cron services finish and exit; one that keeps running blocks the next run.
- [ ] Usage limits and spend alerts are set, so a runaway service does not become a bill.

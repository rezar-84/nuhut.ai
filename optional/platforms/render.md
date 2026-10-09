# Platform — Render

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Configuration

- [ ] Services are defined in `render.yaml` (a Blueprint), so the repository is the
      source of truth. Settings changed only in the dashboard are invisible to review.
- [ ] Secrets in the Blueprint are declared with `sync: false` or come from an
      environment group, never written as values in the file.
- [ ] Preview environments get their own database and credentials, not production's.

## Deploy and rollback

- [ ] A health check path is set; without one a broken deploy can take traffic.
- [ ] Migrations run as a pre-deploy command, not at start-up in every instance.
- [ ] Rollback is written down: roll back to a previous deploy from the service's
      history. It does not revert migrations or disk data.
- [ ] A service with a persistent disk runs one instance and loses zero-downtime
      deploys. That trade-off is accepted in writing, or the state moves elsewhere.

## Instance behaviour

- [ ] A free instance that spins down when idle is not serving anything with a latency
      expectation; the cold start is the first user's problem.
- [ ] A free-tier database is not holding data anyone needs: free databases expire.
      Confirm the current terms and date them.
- [ ] Cron jobs are written in UTC and are safe if a run overlaps or is skipped.

## Data

- [ ] Database backups or point-in-time recovery are enabled on the plan in use, and a
      restore has been done at least once outside production.
- [ ] Private services use the private network and are not exposed publicly.

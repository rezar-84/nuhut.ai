# Platform — Heroku, Dokku, and Procfile buildpack hosts

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Processes

- [ ] Every process type in the `Procfile` is intended to run, and each is scaled on
      purpose — a `worker` with zero dynos is a queue nobody drains.
- [ ] The filesystem is treated as ephemeral. Uploads and generated files go to object
      storage; dynos or containers are replaced on every deploy and on a regular restart
      cycle, and anything written locally is lost.
- [ ] The process handles `SIGTERM` and finishes or re-queues work within the shutdown
      grace period.
- [ ] Requests finish inside the router's timeout. Long work goes to a worker, not a web
      request that the router cuts off.

## Deploy and rollback

- [ ] Migrations run in the `release:` phase, which aborts the release on failure.
      With a rolling restart, old and new code run at once, so the schema must work with
      both.
- [ ] Rollback is written down (`heroku rollback`, or redeploying a previous release on
      Dokku). It restores code and configuration, **not** the database or add-on data.
- [ ] Changing a config variable restarts the app. The runbook says so.
- [ ] The stack or base image is supported, and its end-of-life date is recorded.
- [ ] Review apps and pipeline stages have their own add-ons and credentials, not
      production's.

## Dokku specifics

- [ ] Persistent paths are mounted with `dokku storage:mount`, not left in the container.
- [ ] Zero-downtime checks (`CHECKS` file or `app.json` healthchecks) are defined;
      without them a broken container can take traffic.
- [ ] TLS certificates renew automatically (the Let's Encrypt plugin's cron is enabled),
      and the host itself is covered by the `vps.md` checklist.

## Data

- [ ] Database backups are scheduled, retained, and a restore has been done at least once
      outside production.

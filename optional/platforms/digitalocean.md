# Platform — DigitalOcean App Platform

Installed because the charter's **Deployment platforms** row names it. For a Droplet
managed by hand, use `vps.md` instead. The platform half of `../roles/devops-sre.md` and
`../templates/release-runbook.md`; it adds checks, never replaces them. Mark a check
`n/a` with a reason rather than deleting it.

## Configuration

- [ ] The app spec (`.do/app.yaml`) in the repository is the source of truth. Changes made
      only in the control panel are drift, and the next spec deploy overwrites them.
- [ ] Secrets are declared `type: SECRET`, and each variable's scope (build time, run time,
      or both) is deliberate — a build-time secret ends up in the image.

## Deploy and rollback

- [ ] Health checks are configured so a deploy that does not come up never takes traffic.
- [ ] Migrations run as a `PRE_DEPLOY` job, once, not at start-up in every instance.
- [ ] Rollback is written down: roll back to a previous deployment from the app's history.
      It does not revert migrations or database data.

## Data

- [ ] The containers have no persistent local disk. Uploads go to Spaces or another
      object store; the database is a managed database.
- [ ] A development database attached to the app is not serving production.
- [ ] The managed database restricts connections to trusted sources, has backups on, and
      a restore has been done at least once outside production.

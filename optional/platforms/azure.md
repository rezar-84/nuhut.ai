# Platform — Azure

Installed because the charter's **Deployment platforms** row names it. App Service,
Functions, Static Web Apps, Container Apps, or AKS (with `kubernetes.md`). The platform
half of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks,
never replaces them. Mark a check that does not apply to the services in use `n/a`.

## Identity

- [ ] CI deploys through OIDC federated credentials, not a client secret stored as a CI
      secret.
- [ ] Applications reach databases, storage, and Key Vault with a managed identity rather
      than connection strings holding keys.
- [ ] Secrets are Key Vault references, not plaintext app settings.

## App Service

- [ ] Production deploys go to a staging slot, are verified there, then swapped. Rollback
      is swapping back.
- [ ] Settings that must not move with a swap (connection strings, feature flags per
      environment) are marked as slot settings.
- [ ] A health check path is configured, and Always On is set for anything that must not
      cold-start.

## Functions and Container Apps

- [ ] The hosting plan's timeout and cold-start behaviour fit the heaviest real request,
      confirmed and dated. Long work uses a durable or queued pattern.
- [ ] Container Apps revisions and traffic weights make rollback a traffic change.

## Static Web Apps

- [ ] `staticwebapp.config.json` routes and role rules are reviewed as the authorisation
      layer they are.
- [ ] Pull-request preview environments are public by default and hold no real data.

## Infrastructure and data

- [ ] Resources are defined in Bicep, ARM, Terraform, or `azd` in the repository;
      portal-only changes are drift.
- [ ] Production resources that hold data have a delete lock.
- [ ] Database backups and point-in-time restore are on, retention is known, and a
      restore has been done at least once.
- [ ] Cost alerts exist, and the region matches the charter's data-residency requirement.

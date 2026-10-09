# Platform — Google Cloud and Firebase

Installed because the charter's **Deployment platforms** row names it. Cloud Run, App
Engine, Cloud Functions, GKE (with `kubernetes.md`), or Firebase Hosting. The platform
half of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks,
never replaces them. Mark a check that does not apply to the services in use `n/a`.

## Identity

- [ ] CI deploys through Workload Identity Federation, not a downloaded service-account
      JSON key stored as a CI secret.
- [ ] Each service runs as its own service account with least privilege — not the default
      compute account, which often has project-wide Editor.
- [ ] Public access (`allUsers` invoker, `--allow-unauthenticated`) is deliberate and
      recorded for each service that has it.

## Cloud Run

- [ ] Minimum instances, concurrency, and request timeout are set deliberately. Zero
      minimum instances means a cold start for the next user.
- [ ] No work continues after the response is sent unless CPU is always allocated —
      otherwise it is throttled and may never finish. Background work goes to a queue.
- [ ] Rollback is written down: shift traffic to a previous revision. Tagged revisions or
      a traffic split make it a pointer change. It does not revert migrations.
- [ ] Ingress settings match intent (internal, internal and load balancer, or all).

## App Engine

- [ ] `gcloud app deploy` promotes the new version by default. Deploys use
      `--no-promote` then shift traffic, or the runbook accepts immediate promotion.

## Firebase

- [ ] Firestore, Realtime Database, and Storage security rules are the authorisation
      layer. They are versioned, tested with the emulator, and reviewed like code.
- [ ] The web config and API key are public by design. Protection comes from rules, App
      Check, and API-key restrictions — never from hiding the key.
- [ ] `firebase deploy` is scoped with `--only`, so a hosting deploy cannot ship
      untested rules or functions.
- [ ] Preview channels expire and hold no real data; rollback of Hosting is a previous
      release in the console or CLI.

## Data, secrets, and cost

- [ ] Cloud SQL: automated backups and point-in-time recovery are on, deletion protection
      is on, and a restore has been done at least once.
- [ ] Secrets come from Secret Manager, not plaintext environment variables.
- [ ] Budget alerts exist, and log retention and sinks are set on purpose.
- [ ] The region matches the charter's data-residency requirement.

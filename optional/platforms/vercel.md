# Platform — Vercel

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Environments and variables

- [ ] Every variable is scoped deliberately to Production, Preview, or Development.
      Preview deployments run with Preview variables, so a preview pointing at the
      production database or payment keys is an S1 finding.
- [ ] Nothing secret is in a client-exposed variable (`NEXT_PUBLIC_`, `VITE_`, or the
      framework's equivalent). Those are shipped in the bundle.
- [ ] A changed variable reaches only **new** deployments. The runbook says to redeploy
      after changing one, and a rollback does not restore an old value.
- [ ] The production branch in the project settings is the charter's default branch.

## Exposure

- [ ] Preview URLs are protected (Deployment Protection) or confirmed to hold no
      unreleased content or real data. Every pushed branch gets one.
- [ ] Previews and the `*.vercel.app` host are kept out of search indexes, and the
      production custom domain is canonical.

## Deploy and rollback

- [ ] Rollback is written down: Instant Rollback, or promoting a previous deployment.
      It states what it does not revert — database migrations, variable changes, and
      data written in between.
- [ ] Migrations do not run inside the build step, which also runs for every preview.
      They are a separate, explicit production step.
- [ ] Cron jobs declared in `vercel.json` run only against the production deployment;
      nothing depends on them in preview.

## Functions

- [ ] Each function's maximum duration, memory, and request-body size fit its heaviest
      real request on this plan, with the figures confirmed and dated. Long work goes to a
      queue or background job, not a request that times out.
- [ ] The function region is near the database. A function in one region querying a
      database in another pays that round trip on every call.
- [ ] Database connections go through a pooler or an HTTP driver. Serverless instances
      multiply connections and exhaust a direct database.
- [ ] Code on the Edge runtime uses only APIs that runtime supports; a Node-only
      dependency fails at runtime, not at build.
- [ ] Cached and statically regenerated pages (ISR, `revalidate`, cache headers) never
      contain one user's data, and revalidation after a content change is tested.

## Observability

- [ ] Runtime logs are kept long enough for an incident review — the platform's own
      retention is short. Ship them with a log drain if the project needs more.
- [ ] Function errors and timeouts alert someone.

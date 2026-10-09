# Platform — Netlify

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Contexts and variables

- [ ] `netlify.toml` defines each deploy context (`production`, `deploy-preview`,
      `branch-deploy`) that behaves differently, and variables are scoped per context. A
      deploy preview using production credentials is an S1 finding.
- [ ] Nothing secret is in a variable the build inlines into client code.
- [ ] Build plugins are pinned and reviewed like dependencies — they run with access to
      every build variable.

## Exposure

- [ ] Deploy previews and branch deploys are public URLs. Protect them, or confirm they
      hold no unreleased content or real data, and keep them out of search indexes.
- [ ] The production custom domain is canonical, not `*.netlify.app`.

## Deploy and rollback

- [ ] Rollback is written down: publish a previous deploy from the deploys list, and lock
      auto-publishing while investigating so the next push does not undo the rollback.
- [ ] The rollback states what it does not revert — functions' external data, and
      anything a form or function wrote.

## Routing

- [ ] Redirect and header rules (`_redirects`, `_headers`, or `netlify.toml`) are reviewed
      as configuration: they carry the security headers, and rule order decides which
      rule wins.
- [ ] A single-page-app fallback (`/* /index.html 200`) does not turn every missing page
      into a `200`. Real 404s still return 404 — for users and for search engines.

## Functions

- [ ] Each function's timeout and payload limits fit its heaviest real request on this
      plan, confirmed and dated. Long work uses a background or scheduled function.
- [ ] Scheduled functions are written in UTC and are safe if a run overlaps or is skipped.
- [ ] Function errors alert someone; the deploy log is not monitoring.

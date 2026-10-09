# Platform — Cloudflare Workers & Pages

Installed because the charter's **Deployment platforms** row names it. The platform half
of `../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Configuration and secrets

- [ ] Secrets are set with `wrangler secret put` or the dashboard, never under `vars` in
      the wrangler configuration — `vars` are plaintext and committed.
- [ ] `.dev.vars` and any local `.env` are gitignored.
- [ ] `compatibility_date` is pinned, and moving it is a reviewed change with its own
      test run: it changes runtime behaviour without a code change. The same for
      `compatibility_flags` such as `nodejs_compat`.
- [ ] Every named environment (`[env.staging]`, `[env.production]`) declares its own
      bindings — KV, D1, R2, Durable Objects, Queues, services. Bindings are not inherited
      from the top level, so a missing one fails only in that environment.
- [ ] Staging bindings point at staging resources. A preview writing to the production
      D1 database or R2 bucket is an S1 finding.

## Deploy and rollback

- [ ] The deploy is `wrangler deploy` (or `wrangler pages deploy`) from CI with a scoped
      API token, not a developer laptop with a global key.
- [ ] Rollback is written down: `wrangler rollback`, or a previous version from the
      deployments list, and the gradual-deployment percentage if versions are used.
- [ ] The rollback states what it does **not** revert: D1 migrations, KV and R2 contents,
      Durable Object state, and secrets changed since.
- [ ] D1 migrations are applied with `wrangler d1 migrations apply <db> --remote` as an
      explicit step. The command defaults to the local database, and "migrated" without
      `--remote` is *Unverified*. The recovery path (D1 Time Travel or an export) is
      named before a destructive migration.
- [ ] Durable Object class changes go through the `migrations` block. A `deleted_classes`
      entry deletes that class's stored data — treat it as a destructive data migration.

## Runtime limits

- [ ] The worker fits the plan's CPU-time, memory (128 MB per isolate), script-size, and
      subrequest limits for its heaviest real request, with the figures confirmed and
      dated rather than recalled.
- [ ] No request path depends on in-memory state between requests: isolates are
      evicted and not shared.
- [ ] KV is not used where read-after-write matters — it is eventually consistent across
      locations. Use D1 or Durable Objects for that.
- [ ] Cron Triggers are written in UTC, and a job that overruns its interval is safe to
      overlap.

## Exposure

- [ ] If the worker serves a custom domain behind WAF, Access, or rate-limiting rules,
      the `*.workers.dev` route is disabled (`workers_dev = false`); otherwise it bypasses
      every one of them.
- [ ] Pages preview deployments (`<branch>.<project>.pages.dev`) are public by default.
      Protect them with Access, or confirm they hold no unreleased content or real data,
      and keep them out of search indexes.
- [ ] `_headers` and `_redirects` (Pages) are reviewed as configuration, not content —
      they carry the security headers and can open redirects.

## Observability

- [ ] Worker logs are enabled (`observability` in the configuration) or shipped with
      Logpush; `wrangler tail` is a debugging tool, not monitoring.
- [ ] Errors and exceeded-limit events alert someone, not only the dashboard.

# Platform — Cloudflare in front of an origin (proxy, CDN, DNS, WAF)

Installed because the charter's **Deployment platforms** row names it. It governs the
edge; pair it with the checklist for wherever the origin runs. The platform half of
`../roles/devops-sre.md`; it adds checks, never replaces them.

## TLS

- [ ] SSL/TLS mode is **Full (strict)**. *Flexible* leaves the edge-to-origin leg
      unencrypted and loops forever as soon as the origin redirects HTTP to HTTPS.
- [ ] The origin certificate is valid for strict mode: publicly trusted, or a Cloudflare
      Origin CA certificate — which only Cloudflare trusts, so it breaks the moment a
      record is switched to DNS-only.
- [ ] Certificate issuance on the origin still works behind the proxy. An ACME HTTP-01
      challenge can fail when proxied; use DNS-01 or the Origin CA, and say which.
- [ ] HSTS, and especially HSTS preload, is enabled deliberately. It is very hard to take
      back, and it breaks every subdomain that is not yet on HTTPS.

## The origin is not reachable around the edge

- [ ] The origin accepts traffic only from Cloudflare: a firewall allowlist of
      Cloudflare's published ranges, Authenticated Origin Pulls, or a Cloudflare Tunnel.
      Otherwise the WAF, rate limits, and Access are bypassed by anyone with the origin IP.
- [ ] The origin IP is not published by a DNS-only record on the same host, an MX
      record, or an old DNS history entry. If it has been, rotate it.
- [ ] The application reads the client IP from `CF-Connecting-IP` only when the request
      came from a Cloudflare range. Trusting the header from anywhere lets a caller forge
      it; ignoring it makes every rate limit see Cloudflare's IPs.

## Caching

- [ ] No rule caches personalised or authenticated responses. "Cache Everything" on a
      path that sets cookies or renders account data serves one user's page to another —
      an S0 finding.
- [ ] Static assets have content-hashed names and long cache lifetimes; HTML is short or
      uncached. A deploy that removes old chunks while cached HTML still references them
      breaks the site until the cache expires.
- [ ] The post-deploy purge is written in the runbook: what is purged (everything, by
      URL, or by tag), by whom, with which token.

## Configuration drift

- [ ] DNS records, cache rules, WAF rules, redirects, and Workers routes live in code
      (the Terraform provider or an equivalent), or are listed in the runbook with an
      owner. Dashboard-only configuration is invisible to review and to rollback.
- [ ] Bot protection and "Under Attack" mode exempt webhooks, API clients, and health
      checks that cannot solve a challenge. Test that exemption before you need it.
- [ ] Mail records (MX, SPF, DKIM, DMARC) are DNS-only, never proxied.
- [ ] Staging and preview hosts are protected (Access, or at least `noindex`) and are
      not cached under production rules.

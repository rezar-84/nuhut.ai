---
name: sdlc-scrape-compliance
description: Check a fetcher, crawler, scraper, or third-party data source before it is written or changed — a new site or feed, a change to crawl rate or depth, a new parser, or storing what was fetched. Use whenever this project acquires data it did not create.
---

# Acquisition — permission first, politeness always, provenance forever

`{{DOCS_DIR}}/roles/privacy-legal.md` owns the verdict and
`{{DOCS_DIR}}/roles/data-engineer.md` the mechanics.
`{{DOCS_DIR}}/process/09-probabilistic-and-data-systems.md` §9 is the standard. This
check happens **before the fetcher exists**, not after it is running.

## Acquisition profile is capability, not permission

Read the charter's **Acquisition profile** independently of its effort mode:

- **Standard** — prefer an API or feed, then bounded static requests, then ordinary
  browser rendering only when the content requires it.
- **Advanced** — may also use pluggable renderers, browser
  automation, resilient extraction fallbacks, OCR, and authenticated session flows with
  credentials supplied for an owned or explicitly authorised target.

Advanced means more tools are available; it never turns technical reachability into
permission. On a third-party target, a login gate, paywall, CAPTCHA, explicit denial, or
other access control is a stop unless the owner has explicitly authorised the automation
or supplied an approved API/export route. Do not rotate identities, defeat CAPTCHA,
evade bans, misuse credentials, or bypass access controls. For an owned system, use a
staging bypass or accessibility alternative supplied by its owner rather than attacking
the production challenge.

## 1. Permission

- [ ] Terms of service read, and what they say about automated access recorded — not
      assumed. Public and reachable is not the same as permitted, and "it was on the
      internet" has never been a basis.
- [ ] Robots directives and any stated crawl policy checked, dated, and honoured. Robots
      rules are not access authorisation, and their absence is not permission.
- [ ] Licence of the content established: what may be stored, republished, sold, or used
      to train. Absence of a licence is not permission.
- [ ] Any API or feed with terms is preferred over scraping the rendered page, where one
      exists.
- [ ] Anything requiring a login, payment wall, or acceptance of terms is a different
      question with a different answer — escalate to a human rather than deciding it.

Record the outcome in the charter's **Data ownership** table with a date. Terms change;
a check with no date cannot be re-examined.

## 2. Politeness — a correctness property, not a courtesy

- [ ] A documented rate limit and concurrency cap, chosen to be invisible on the target's
      graphs. A crawler with no ceiling is an outage you are causing on someone else's
      system, and you will find out by being blocked.
- [ ] Exponential backoff on errors and on 429/503. Retrying harder into a struggling
      server is the worst possible response.
- [ ] A real, identifying user agent with a contact route.
- [ ] Caching and conditional requests, so a re-run is not a second full fetch.
- [ ] Fetch only what is needed, at the depth needed, on a schedule that has a reason.

## 3. Provenance

Per record: source, URL or feed, fetch date, and the terms it was obtained under. Data
whose origin nobody can state cannot be published, sold, trained on, or defended — and
the moment to record it is when it arrives, because it cannot be reconstructed later.

## 4. Personal data

Scraped personal data is personal data, with every obligation intact and none of them
waived by the source being public. Names, contact details, profiles, and reviews are all
in scope. Classify it, minimise it, and give it a lawful basis and a deletion path before
the first run, not after.

## 5. It will break silently

The source will change shape without telling you. A parser that starts returning empty
fields is a data-quality failure, not a parsing detail:

- [ ] Assert the shape of what was parsed — required fields present, expected counts in
      range — and **stop and alert** rather than publishing empties.
- [ ] Keep the raw response for anything you publish downstream, so a re-parse is
      possible without a re-fetch.
- [ ] Alert on a silent zero: a run that succeeds and acquires nothing is the failure that
      goes unnoticed longest.

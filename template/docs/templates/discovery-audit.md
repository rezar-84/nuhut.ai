---
status: draft
owner: product-manager
last-reviewed: YYYY-MM-DD
---

# Discovery & current-state audit — {{PROJECT_NAME}}

> Create at G0 when replacing, migrating, or building alongside something that already
> exists. The purpose is to know the ground truth **before** designing, so that nothing
> valuable is thrown away by accident.

## What exists today

| Thing | Where | Owner | Condition | Disposition |
| --- | --- | --- | --- | --- |
| _(system, dataset, content set, integration, domain, account)_ | | | | _(keep / migrate / rebuild / retire)_ |

## How it is used

_(Who uses it, how often, for what. Real usage data where available; where not available,
say so rather than estimating and letting the estimate harden into a fact.)_

## What works

_(Genuinely. The parts users rely on and would miss. This list protects them — a rebuild
that quietly drops a beloved feature is a self-inflicted wound.)_

## What does not work

| Problem | Evidence | Who it affects | Severity |
| --- | --- | --- | --- |

Evidence, not impression. "Slow" is an impression; "the report page takes 9 seconds at
the 75th percentile" is evidence.

## Inventory

For migrations, count things and record the count. Reconciling against it later is the
only way to know nothing was lost.

| Category | Count | Source of truth | Notes |
| --- | --- | --- | --- |
| Pages / screens | | | |
| Content items | | | |
| Assets | | | |
| Records | | | |
| Integrations | | | |
| URLs | | | |

## Provenance rules

- Source material is **evidence, not product**. Archived exports, snapshots, and
  checksums are never edited; derive from them.
- Each migrated item records: origin, date obtained, transformation applied, reviewer,
  and disposition.
- Deduplicate by content hash; keep originals; produce optimised derivatives separately.
- Reuse of customer names, logos, photographs, testimonials, or metrics requires
  documented permission (`../roles/privacy-legal.md`).

## Constraints inherited

_(Contracts, licences, integrations others depend on, domains and their history, data
that cannot move, accounts nobody can access any more. The unglamorous list that
determines what is actually possible.)_

## Access & credentials needed

| Need | From whom | Status |
| --- | --- | --- |

_(Analytics, search console, DNS, hosting, repositories, third-party accounts, brand
assets. Missing access is the most common silent blocker in a migration — surface it on
day one.)_

## Unknowns

_(What we could not determine, and what it would take to determine it. Copy each into
`assumptions-and-risks.md`.)_

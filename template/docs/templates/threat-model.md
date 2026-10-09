---
status: draft
owner: security
last-reviewed: YYYY-MM-DD
---

# Threat model — {{PROJECT_NAME}}

> Create at G2 for any project with authentication, multiple users or tenants, payments,
> personal data, or public exposure. Revisit whenever the attack surface changes.

## Scope

_(What this model covers and what it explicitly does not. A model with no boundary is a
model nobody can complete.)_

## Assets

What an attacker would want, ranked by what it would cost us to lose.

| Asset | Why valuable | Impact if compromised |
| --- | --- | --- |
| | | |

## Actors

| Actor | Capability | Motivation |
| --- | --- | --- |
| Anonymous visitor | | |
| Authenticated user | | |
| User of another account/tenant | | |
| Privileged operator | | |
| Compromised dependency | | |
| Insider with repository access | | |

The second-most-productive row is usually **a legitimate user of another account** — the
one with valid credentials, poking at identifiers that are not theirs. Model it
seriously.

## Trust boundaries

_(Where untrusted data enters and where privilege changes. Mark them on the architecture
sketch. Everything crossing a boundary is validated.)_

## Threats

Work through each entry point. A useful prompt set: spoofing identity · tampering with
data · repudiating an action · disclosing information · denying service · elevating
privilege.

| # | Threat | Entry point | Impact | Likelihood | Mitigation | Enforced at | Tested by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | _(layer)_ | _(test)_ |

Rules for this table:

- **Every mitigation names where it is enforced.** "Validated in the UI" is not a
  mitigation.
- **Every mitigation names the test that proves it.** An untested mitigation is a
  belief.
- **Impact is rated by consequence, not likelihood.** Cross-account data exposure is
  maximum impact however unlikely the path.

## Isolation matrix

For multi-user or multi-tenant systems — every resource type gets a row.

| Resource | Same owner, permitted | Same owner, not permitted | Different owner | Revoked | Tampered ID |
| --- | --- | --- | --- | --- | --- |
| | Allow | Deny | **Deny, no leak** | Deny | Deny |

"No leak" means the response does not reveal whether the resource exists — not through
the body, the status code, the timing, or a count elsewhere in the interface.

## Abuse cases

_(Not bugs — features used as designed, at scale or in bad faith: mass signup, invitation
spam, scraping, resource exhaustion, using your outbound requests as a proxy, using your
storage as a file host, using your email as a relay.)_

## Residual risks

| Risk | Why not mitigated | Accepted by | Review date |
| --- | --- | --- | --- |

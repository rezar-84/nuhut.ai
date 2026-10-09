---
status: draft
owner: security
last-reviewed: YYYY-MM-DD
---

# Security & privacy — {{PROJECT_NAME}}

> Maintained jointly by `security` and `privacy-legal`. Create this even for projects
> that believe they hold no sensitive data — the answer "we hold none, here is why" is a
> useful, verifiable statement.

## Data inventory

| Data | Category | Purpose | Lawful basis | Where stored | Retention | Deleted by |
| --- | --- | --- | --- | --- | --- | --- |
| | _(personal / special / operational / secret)_ | | | | | _(the actual mechanism)_ |

Every row needs a purpose. A row whose purpose is "might be useful" should not exist.

## Identity & access

- **Access level model:** _(None / Public · Simple Owner/User · RBAC · Multi-tenant Workspace-Scoped · ABAC)_
- **Authentication:** _(mechanism, provider, session lifetime, revocation, or "None / Public")_
- **Multi-factor (MFA / OTP):** _(Not required · Optional / User-enabled · Enforced for Admin · Enforced for all — as the charter declares it; where privileged access has none, say so)_
- **Roles and permissions:** _(the model, and where the matrix lives)_
- **Where authorisation is enforced:** _(name the layer — data layer, service middleware, RPC gate — not "in the UI")_
- **Isolation:** _(how one account's data is kept from another's, and where that is
  guaranteed)_
- **Privileged/support access:** _(who, how it is authorised, how it is time-bound, how
  it is audited — or "none exists")_

## Secrets

- Where they live, how they are injected, who can read them.
- Rotation procedure and cadence.
- The response when one leaks: **treat as compromised, rotate, then investigate**.

## Protections

| Concern | Control | Where enforced | Verified by |
| --- | --- | --- | --- |
| Input validation | | | |
| Output encoding | | | |
| Transport security | | | |
| Rate limiting | | | |
| Session handling | | | |
| Content/embedding policy | | | |
| Cross-origin policy | | | |
| Dependency scanning | | | |
| File upload handling | | | |

## Logging & audit

- **Never logged:** credentials, tokens, personal data, payment data, document contents.
- **Audited events:** sign-in, sign-in failure, privilege change, access grant/revoke,
  export, deletion, privileged access.
- Retention of logs and audit records; who can read them.

## Privacy commitments

- **Consent:** what requires it, how it is captured, how it is withdrawn, what is gated
  on it, and what the product does when it is refused.
- **User rights:** how access, correction, deletion, portability, and objection are
  actually fulfilled — including in backups, logs, caches, and third-party systems.
- **Processors:** every third party receiving personal data.

| Processor | Receives | Purpose | Location | Agreement |
| --- | --- | --- | --- | --- |

- **Transfers:** cross-border mechanism, if required by the charter's jurisdictions.
- **Public documents:** privacy notice, terms, cookie information, accessibility
  statement — where each lives and when each was last reviewed.

## Incident response

- How a suspected incident is reported, and to whom.
- Who decides severity and who can authorise a rollback or a shutdown.
- Notification obligations and their deadlines, per jurisdiction.
- Where the postmortem goes (`postmortem.md`).

## Accepted risks

| Risk | Why accepted | Accepted by | Review date |
| --- | --- | --- | --- |

An accepted risk is a decision with a name and a date on it. An unrecorded one is an
accident waiting to be discovered.

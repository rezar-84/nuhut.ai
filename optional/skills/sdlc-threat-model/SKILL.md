---
name: sdlc-threat-model
description: Build or update a threat model for a surface — assets, entry points, trust boundaries, who the adversary realistically is, the abuse cases, and which controls actually exist versus which are assumed. Use when adding authentication, an external interface, file uploads, payments, background jobs with elevated rights, or anything holding sensitive data.
---

# Threat model

Template: `{{DOCS_DIR}}/templates/threat-model.md`. Playbook: `{{DOCS_DIR}}/roles/security.md`.

A threat model is not a checklist of scary words. It answers three questions: what is worth
taking, how would someone get it, and what actually stops them today.

## Build it

1. **Assets.** What an attacker would want: credentials, personal data, money movement,
   compute, reputation, the ability to send mail from your domain.
2. **Entry points.** Every input the system accepts: routes, forms, file uploads, webhooks,
   queues, CLI flags, environment, third-party callbacks, admin tooling.
3. **Trust boundaries.** Where data crosses from less trusted to more trusted. Draw them
   explicitly — most real vulnerabilities live exactly on one of those lines.
4. **Actors.** Anonymous internet, authenticated user, another tenant, an insider, a
   compromised dependency, a compromised third-party script. Be specific about which are
   realistic here.
5. **Abuse cases.** For each entry point, the deliberate misuse: authorisation bypass — the
   most common real finding, where object IDs come from the request instead of the session —
   injection, SSRF, mass assignment, enumeration, replay, missing rate limits, unsafe
   deserialisation, path traversal on uploads.
6. **Controls.** For each abuse case, the control that exists *in the code you read*, not
   the one you assume is there. An unverified control is a finding, not a mitigation.
7. **Residual risk.** What remains, who accepted it, and when it should be revisited.

## Rules

- Authorisation is checked server-side, per request, against the acting session. A hidden UI
  element is not a control.
- Secrets never enter the repository, logs, error messages, or client bundles.
- Every abuse case that matters gets a test — the *denied* and *malformed input* cases
  explicitly (`{{DOCS_DIR}}/process/04-quality-gates.md`).
- Do not run intrusive testing against systems you were not authorised to test.

## Output

The model as a file under `{{DOCS_DIR}}/project/` when the tier warrants it, findings with
severity and location, the tests that must exist, and the residual risks needing a named
human's acceptance.

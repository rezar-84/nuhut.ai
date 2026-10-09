---
name: sdlc-privacy-review
description: Review a change for personal data and legal exposure — what is collected, why, on what basis, where it goes, how long it is kept, which third parties see it, and whether the public claims about it are true. Use when forms, analytics, tracking, third-party scripts, logging, data exports, retention, or user-visible legal claims change.
---

# Privacy and legal review

Playbook: `{{DOCS_DIR}}/roles/privacy-legal.md`. Jurisdictions and data categories: the
charter's **Standards & targets**. If those cells are blank, that is the first finding —
you cannot assess exposure against an unknown regime, so ask rather than assume.

## Trace the data

1. **What is collected**, field by field, including what is collected incidentally: IP
   addresses, device identifiers, precise timestamps, free-text fields users will paste
   anything into, uploaded files, session recordings.
2. **Why**, in one sentence per field. A field with no purpose is a finding — delete it.
3. **On what basis**, in the terms the charter's jurisdictions use.
4. **Where it goes**: every third party in the request path — analytics, error reporting,
   fonts, maps, chat widgets, AI APIs, CDNs. Each is a data transfer, often a cross-border
   one.
5. **How long it is kept**, and what deletes it. "Forever, by default" is the true answer in
   most systems that never wrote this down.
6. **Who can read it**: access controls, and whether personal data reaches logs, error
   traces, analytics events, or support tooling in plain text.

## Then check

- Consent: is anything non-essential loaded before consent is given? Is refusal as easy as
  acceptance? Is the consent state actually honoured by the code, not only by the banner?
- Subject rights: can access, export, correction, and deletion actually be performed —
  including in backups and in third-party systems?
- Children's, health, financial, biometric, or location data: each escalates the tier.
- Public claims: the privacy policy, cookie notice, security page, and marketing copy must
  match what the system does. A policy describing retention nobody implemented is a legal
  exposure, not a documentation gap.
- The security controls privacy depends on: encryption in transit and at rest, minimal
  retention, pseudonymisation where it costs nothing.

## Output

Findings with severity, the data-flow summary, the policy text that is now wrong, and the
questions that need a named human — usually legal basis, retention periods, and
sub-processors. Update the instantiated `security-privacy` artifact if one exists, and log
new unknowns in `{{DOCS_DIR}}/project/assumptions-and-risks.md`.

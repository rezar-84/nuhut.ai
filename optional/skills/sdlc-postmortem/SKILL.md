---
name: sdlc-postmortem
description: Run a blameless postmortem after an incident, outage, regression, data problem, or rollback — timeline, contributing factors, detection and recovery gaps, and tracked corrective actions. Use when something broke in a real environment, a release had to be reverted, or a bug reached users.
---

# Postmortem

Template: `{{DOCS_DIR}}/templates/postmortem.md`. Write it into
`{{DOCS_DIR}}/project/postmortems/`.

The output is a list of changes to the system, not a list of things a person should have
done better. If the conclusion is "be more careful", it is not finished.

## Assemble

1. **Impact, in user terms.** Who could not do what, for how long, and how many. Numbers you
   can source; *Unknown* where you cannot — never an estimate presented as a count.
2. **Timeline.** First occurrence, first detection, first response, mitigation, resolution,
   with timestamps and a timezone. The gap between occurrence and *detection* is usually the
   most valuable number in the document.
3. **Contributing factors.** Plural, always: the change that triggered it, the check that
   would have caught it and did not exist, the alert that did not fire, the document that
   was wrong, the assumption that had gone stale.
4. **What worked.** Detection, tooling, rollback — worth keeping deliberately.
5. **Recovery.** What actually resolved it, and whether the rollback plan held up in
   practice.

## Then

- **Corrective actions** become real backlog rows with IDs and owners
  (`{{DOCS_DIR}}/project/backlog.md`). An action without an ID does not exist.
- **The test that would have caught it** is written now, before the fix is called done.
- **Update the documents the incident falsified** — charter cells, runbooks, the threat
  model, assumptions. An incident is evidence that a document was wrong.
- Add anything newly uncertain to `{{DOCS_DIR}}/project/assumptions-and-risks.md`.
- **If an agent's mistake contributed**, and it is not the first time, add one line under
  "Known agent mistakes" in `AGENTS.md` section 9. If the mistake is decidable from a tool
  call, propose a hook or a check instead: an instruction makes the mistake rarer, and a
  check stops it.
- **For an S0 or S1**, add the case to the project's agent evaluation tasks if it keeps
  them (`{{DOCS_DIR}}/process/04-quality-gates.md`, "Evaluating the agent's own setup").

## Tone

Blameless means describing decisions in terms of the information available at the time.
Names appear as roles, not as causes.

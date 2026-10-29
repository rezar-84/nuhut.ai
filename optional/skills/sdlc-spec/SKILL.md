---
name: sdlc-spec
description: Write or update a living capability spec (requirements with WHEN/THEN scenarios) or a work item's spec change. Use when the charter's Specs row is on and a Tier 1 or 2 item changes observable behaviour, or to capture what an existing (brownfield) feature does today from its code and tests.
---

# Living specs — what the system does now

Read `{{DOCS_DIR}}/process/15-specs.md` first. Specs exist only when the charter's
**Specs** row is `on`.

## A work item's change

1. Copy `{{DOCS_DIR}}/templates/spec-change.md` to
   `{{DOCS_DIR}}/project/specs/changes/<ID>.md`.
2. Under `## ADDED`, `## MODIFIED` and `## REMOVED Requirements`, write each requirement
   as `### Requirement: <name>` + one `SHALL`/`MUST` sentence + at least one
   `#### Scenario:` with **WHEN** and **THEN**. MODIFIED repeats the whole requirement as
   it will read; its name must match the existing one exactly.
3. Link it from the plan's **Spec changes** line. Every scenario becomes a test or an
   acceptance check.
4. Run `python3 .ai-sdlc/bin/sdlc.py spec validate`; on close,
   `python3 .ai-sdlc/bin/sdlc.py spec apply <ID> --write`.

## A spec for existing behaviour (brownfield)

Read the code paths and the tests for one capability. Write
`{{DOCS_DIR}}/project/specs/<capability>.md` from `templates/spec.md`, describing only
behaviour you can point to in code or a test — cite the file next to each scenario. Mark
anything you inferred but could not confirm as **Unknown** rather than writing it as a
requirement. Never invent behaviour to fill a section.

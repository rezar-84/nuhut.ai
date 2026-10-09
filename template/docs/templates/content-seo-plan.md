---
status: draft
owner: seo
last-reviewed: YYYY-MM-DD
---

# Content, voice & discoverability plan — {{PROJECT_NAME}}

> Maintained jointly by `copywriter` (voice, terminology, claims) and `seo` (structure,
> metadata, discoverability). Create when the project publishes anything a stranger can
> find.

## Voice

- **Sounds like:** _(three adjectives, and one sentence written in that voice)_
- **Never sounds like:** _(the failure mode to avoid — e.g. breathless, bureaucratic,
  jokey about money)_
- **Person and tense:** _(second person, present, active — or state otherwise)_
- **Sentence length and register:** _(the actual convention)_

Write one paragraph of real example copy here. A voice described in adjectives is not
transferable; a voice demonstrated is.

## Terminology

One term per concept, product-wide. This table is the arbiter.

| Concept | We call it | Never | Notes |
| --- | --- | --- | --- |
| | | | |

Include: product and feature names, third-party names with their exact casing,
capitalisation rules, date/number/currency formats.

## Claims policy

- Factual claims about the business require evidence on file
  (`../process/06-evidence-and-claims.md`).
- Claims requiring review before publication: _(list — e.g. anything about security,
  compliance, performance, or outcomes)_
- Who approves them: _(named role or person)_

## Audiences & intent

| Audience | What they are trying to find out | Where they land | What they should do next |
| --- | --- | --- | --- |
| | | | |

## Structure

- **URL convention:** _(pattern, casing, separators, depth. Decide once; changing it
  later costs earned value.)_
- **Page types:** _(and the template each uses)_
- **Internal linking rule:** _(how every important page gets a path from a prominent one)_
- **Navigation:** _(what is in it, and the rule for what earns a place)_

## Metadata rules

| Element | Rule |
| --- | --- |
| Title | _(pattern, length, uniqueness)_ |
| Description | _(length, what it must contain)_ |
| Headings | One `h1`; descending order; describe content not style |
| Canonical | Self-referencing, absolute |
| Structured data | Only for content actually present on the page |
| Social/preview metadata | _(what is required)_ |
| Images | Meaningful alternative text; descriptive filenames |

## Languages & regions *(if applicable)*

| Locale | Status | Reviewer | Notes |
| --- | --- | --- | --- |
| | _(full / partial / routing only)_ | _(named human)_ | |

- Alternates are declared reciprocally on every variant; a locale without content is not
  advertised.
- Default for unmatched visitors: _(which)_
- Agent-authored translations are **draft until reviewed by a qualified speaker** and are
  labelled as such in the worklog.

## URL inventory & redirects

Maintained at: `_(path to the inventory / redirect map)_`

Rules: every removed or moved URL gets a permanent, single-hop redirect to the closest
equivalent. Blanket redirects to the home page are treated as soft errors and lose the
value the URL had earned.

## Publication workflow

1. Draft → 2. Editorial review (`copywriter`) → 3. Claims check (`privacy-legal`, if
   applicable) → 4. Structure & metadata check (`seo`) → 5. Publish → 6. Verify rendered
   output, alternates, and sitemap membership.

No agent-authored content publishes without step 2, and no claim publishes without
evidence.

## Baseline

_(Where current performance is recorded, so a change can be evaluated. Establish before
making changes — after is too late.)_

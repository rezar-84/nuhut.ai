---
name: sdlc-content-seo
description: Review publicly discoverable content and its technical SEO — titles, headings, metadata, canonical and indexing directives, internal links, structured data, URL changes and redirects — and check that every claim in the copy is true and sourced. Use when public pages, marketing copy, routes, or metadata change.
---

# Content and SEO review

Playbooks: `{{DOCS_DIR}}/roles/seo.md` and `{{DOCS_DIR}}/roles/copywriter.md`. Analytics and
search data sources: the charter's **Sources of truth**.

## Claims first

Every factual statement in public copy — numbers, client names, certifications,
partnerships, testimonials, awards, guarantees, comparisons — must be traceable to
something real. Anything you cannot source is marked `_(unverified — needs confirmation:
<what, from whom>)_` and logged in `{{DOCS_DIR}}/project/assumptions-and-risks.md`. Never
invent one to make a page read better. Regulated or comparative claims also need
`sdlc-privacy-review`.

## Technical

1. One `h1` per page, headings in order, describing the content rather than decorating it.
2. Title and meta description unique per page, written for a human, not padded with
   keywords.
3. Canonical URL correct; `noindex` present exactly where intended and nowhere else.
4. **URL changes are the highest-risk item here.** Any moved or removed route needs a 301
   and updated internal links — a silent 404 discards that page's history permanently.
5. Internal linking: does the new page get linked from somewhere real, with descriptive
   anchor text?
6. Structured data valid and matching the visible content — never marked-up claims the page
   does not make.
7. Images: real dimensions, compressed, meaningful `alt` (decorative images get empty
   `alt`), lazy-loaded below the fold.
8. Performance budget from the charter — a page that ships a megabyte of JavaScript to
   render a paragraph is a finding.
9. `sitemap.xml` and `robots.txt` still accurate after the change.

## Content

Audience, one job per page, the primary action visible without scrolling on mobile, and
plain language over house style. Match the voice already used in the product, and the
languages and writing directions the charter names.

## Output

Findings with severity and location, the redirect list if URLs moved, and what you did not
check — rankings, indexing, and traffic effects cannot be verified from here.

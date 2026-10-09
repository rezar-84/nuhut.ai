# Role — SEO / Discoverability

**Mission:** ensure the right people can find this, that machines can crawl, understand,
and correctly attribute it, and that nothing already earned is thrown away.

Applies to search engines, AI answer engines, app stores, package registries, and
internal search — anywhere discovery is mediated by a machine.

---

## Engage when

- Public content is added, changed, moved, or removed.
- URLs, routes, slugs, or the site structure change.
- Metadata, structured data, canonicals, or language alternates change.
- A migration, redesign, or re-platform touches public pages.

## Skip when

- Nothing publicly discoverable is affected (internal tools, private APIs, authenticated
  areas — though those still need `noindex` verified).

## Reads

`project/content-seo-plan.md`, the current URL inventory, existing analytics and search
performance data if the charter names a source, and the rendered output.

---

## Design-review checklist

**Intent and structure**
- [ ] Each page targets one clear intent. Two pages competing for the same intent is
      cannibalisation — merge or differentiate.
- [ ] The topic is covered at the depth the intent requires; a page that exists only to
      hold a keyword is a liability.
- [ ] URL structure is stable, readable, lowercase, hyphenated, and free of session or
      tracking parameters. Prefer never having to change it over changing it well.
- [ ] Internal linking gives every important page a path from a prominent page, with
      descriptive anchor text.

**Machine comprehension**
- [ ] Exactly one `h1` per page; heading levels descend without skipping; headings
      describe content rather than styling.
- [ ] Title and description are unique per page, written for a human, within the
      lengths that render fully.
- [ ] Canonical URL is self-referencing and absolute, and every variant (parameters,
      trailing slash, case, protocol, host) resolves consistently.
- [ ] Structured data matches what is actually on the page — marking up content that is
      not visible is a penalty risk, not a shortcut.
- [ ] Images have meaningful alternative text (shared requirement with `accessibility`)
      and descriptive filenames.
- [ ] Content is present in the initial response, or the rendering strategy is verified
      to produce indexable output.

**Multi-language / multi-region** *(if applicable)*
- [ ] Language and region alternates are declared on every variant, **reciprocally** —
      one-way declarations are ignored.
- [ ] A default is declared for unmatched visitors.
- [ ] A page that exists in only one language does not advertise alternates that 404.
- [ ] Translated content is genuinely translated, not the source language under a
      different URL.

**Not losing what exists**
- [ ] Every removed or moved URL has a permanent redirect to the closest equivalent —
      not a blanket redirect to the home page, which is treated as a soft 404.
- [ ] Redirects are single-hop. Chains lose value at every step.
- [ ] Inbound-link value is checked before deleting anything; a page with references
      earns a redirect even if its content is retired.
- [ ] The sitemap contains exactly the canonical, indexable URLs — no redirects, no
      errors, no `noindex` pages.
- [ ] Crawler directives (robots rules, meta directives) are checked against intent.
      Blocking a resource the renderer needs makes the page uninterpretable.

**Technical health & webmaster tools**
- [ ] Real-user performance metrics are within budget — they affect both ranking and
      the reason ranking exists.
- [ ] **Ownership verification:** whatever proves ownership to the search engines'
      webmaster tools (a DNS record, a verification file, or a meta tag — see the
      charter's Sources of truth) survives redesigns, routing changes, and deploys.
- [ ] The sitemap and robots rules are reachable, valid, and submitted to the webmaster
      tools the charter names.
- [ ] No indexable duplicate of a staging, preview, or alternate host. Non-production
      environments must be blocked from indexing.
- [ ] Authenticated and private areas are excluded from indexing and from the sitemap.

## Ship-review checklist

- [ ] Fetch the rendered page and inspect the real head, headings, and structured data —
      not the source template.
- [ ] Test every redirect in the map, following the full chain, and confirm the status
      code.
- [ ] Validate structured data with a real validator.
- [ ] Crawl the changed section for broken links, orphan pages, and unexpected `noindex`.
- [ ] Confirm the sitemap regenerated and matches reality.
- [ ] Record the pre-change baseline so the post-change effect can be observed.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| A production section accidentally blocked from indexing | S1 |
| A non-production environment accidentally indexable | S1 |
| Removing or moving a substantial part of the site's URLs with no redirect map | S1 |
| Removing or moving a small number of URLs with no redirect map | S2 |
| Structured data describing content the page does not contain | S2 |
| Broken or non-reciprocal language alternates on a multi-language site | S2 |
| Publishing content that duplicates another site's text | S2 — and hand to `privacy-legal` if it was copied without a licence |
| A redirect chain where a single hop would do | S3 |
| A title or description outside its length guidance | S4 |

Alt text and heading structure are `accessibility`'s findings even when the motivation is
search; do not rate them twice.

---

## Owns

`project/content-seo-plan.md`, the URL inventory, and the redirect map.

## Hands off to

Wording quality and claims → `copywriter`. Conversion behaviour after arrival →
`cro-analyst`. Rendering and performance implementation → `architect` / `devops-sre`.
Image alternative text quality → `accessibility`.

---

## Questions this role asks that nobody else will

- What was this URL earning before we touched it, and where does that value go now?
- If a machine had to summarise this page in one sentence, would it get it right?
- Which existing page does this new one compete with?
- Is this page's content actually in the response, or only after something runs?

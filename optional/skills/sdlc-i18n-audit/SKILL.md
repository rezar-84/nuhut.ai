---
name: sdlc-i18n-audit
description: Audit the code surface of a multilingual project — hardcoded user-visible strings, plural and gender rules, locale-aware date/number/currency formatting, bidirectional and right-to-left layout, locale routing, and missing-key fallbacks. Use when strings, screens, layout, or locale configuration change in a project that ships in more than one language, or when adding a new locale.
---

# Internationalisation audit

Playbook: `{{DOCS_DIR}}/roles/localisation.md`. Rules: `{{DOCS_DIR}}/process/08-content-and-translation.md`.
Languages, source language, catalogue location: the charter's **Languages & localisation**
table. If that table is blank, that is the first finding — ask rather than assume which
language is canonical.

This skill covers whether the *code* can carry another language correctly.
`sdlc-translation-review` covers whether the *content* in that language is any good.

## Audit

1. **Hardcoded strings.** Grep the change for quoted user-visible text in components,
   templates, emails, PDFs, error paths, and images. Each one is a string that will never
   be translated. Error and empty states are where they hide.
2. **Message keys.** Named for purpose (`checkout.payment.declined`), not for their English
   wording. New keys exist in every locale file, or the fallback is deliberate.
3. **Assembly.** No sentence built by concatenating fragments or interpolating a count into
   a hand-written plural. ICU-style plural and select rules, or the platform equivalent —
   many languages have more than two plural forms and some inflect on gender.
4. **Formatting.** Dates, times, numbers, currency, units, addresses, and personal-name
   order go through locale APIs. A hardcoded `MM/DD/YYYY` or a `$` prefix is a finding.
5. **Direction.** `lang` and `dir` set from the rendered locale, on the document and on
   user-generated content. Layout uses logical properties rather than left/right.
   Directional icons mirror; non-directional ones (clocks, media playback) do not.
6. **Bidirectional runs.** Latin brand names, numbers, and code inside a right-to-left
   sentence display in the right order, with punctuation on the correct side.
7. **Routing and fallback.** How a locale is chosen (path, subdomain, header, preference),
   what an unmatched locale gets, and what a missing key renders — the source-language
   string, visibly, never the raw key and never blank.
8. **Typography and assets.** The font contains the script's glyphs; line height suits the
   script; locale-specific images and screenshots exist or are deliberately shared.
9. **Cost.** Catalogues are loaded per locale, not all locales to every user.

## Verify, do not assume

Run the product in each shipped locale and look. Do the longest-string pass (German,
Finnish) and a right-to-left locale if one ships. Report anything you could not run as
*Not run* with the reason, per `{{DOCS_DIR}}/process/06-evidence-and-claims.md` — a locale
you did not open is not a locale you verified.

## Output

Findings with severity from the localisation calibration table, `file:line`, what a reader
of that language actually experiences, and the fix. Hand `hreflang` and per-locale metadata
to `seo`, screen-reader language switching to `accessibility`, and wording to
`sdlc-translation-review`.

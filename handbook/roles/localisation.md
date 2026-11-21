# Role — Localisation / Internationalisation

**Mission:** ensure the product is correct, usable, and credible in every language it
ships in — not only in the language it was written in.

Internationalisation is the code being able to carry another language. Localisation is
another language being carried well. A project can pass the first and fail the second
completely, and usually does: the strings are extracted, and the Persian page still reads
like an English page with Persian words in it.

---

## Engage when

- The charter's **Languages & localisation** table lists more than one language.
- Any user-visible string, date, number, currency, name, address, or measurement is added
  or changed.
- Layout, typography, or icon work touches a bidirectional or vertical script.
- A new locale is added, or an existing one is removed.
- Legal, regulatory, or safety text changes — it is translated per jurisdiction, not per
  language.

## Skip when

- The project ships in exactly one language and the charter says so. Say that explicitly
  in the review rather than leaving the role silent.

## Reads

The charter's **Languages & localisation** table (source language, catalogue location,
translation workflow, glossary), `../process/08-content-and-translation.md`,
`project/content-seo-plan.md` for voice per locale, and the message catalogue itself.

---

## Design-review checklist

- [ ] The **source language is named**, and every other language is described as a
      translation of it. Two languages both claiming to be canonical is how they diverge.
- [ ] Every user-visible string in the plan lives in the catalogue. Any string the plan
      puts in code, a template literal, an image, or a PDF is a finding now, not later.
- [ ] Plurals, gender, and ordering are expressed as ICU-style message rules, not built by
      concatenation. `"You have " + n + " items"` cannot be translated correctly into
      languages with more than two plural forms.
- [ ] Dates, times, numbers, currency, units, addresses, and personal-name order are
      formatted by locale, not by the source locale's habits.
- [ ] The plan says what happens to an **untranslated key**: it falls back to the source
      language, visibly, and never renders the raw key to a user.
- [ ] Locale routing and detection are decided: URL segment, subdomain, header, or user
      preference — and what an unmatched locale gets.
- [ ] For any right-to-left language: mirroring is planned as a layout property (logical
      CSS properties, `dir` on the document and on user-generated content), not as a
      per-component patch.
- [ ] Typography per script: the fonts actually contain the glyphs, line height suits the
      script, and no locale falls back to a system font nobody chose.
- [ ] Who translates and who reviews is named. Machine translation is allowed to draft;
      it is not allowed to be the last reader before a user.

## Ship-review checklist

- [ ] Run the product in every shipped locale, not only the source one. Reviewing only
      the English screenshot is the characteristic failure of this role.
- [ ] No hardcoded user-visible string in the diff. Grep the change for quoted text in
      views, components, emails, and error paths.
- [ ] Every new key exists in **every** locale file, or the fallback is deliberate and
      visible. A missing key that renders `checkout.button.submit` on a live page is not a
      cosmetic defect.
- [ ] Longest-string check: the interface survives German-length and Finnish-length
      words, and Persian and Arabic line heights, without clipping or overlap.
- [ ] Bidirectional text: mixed LTR/RTL runs (a Latin brand name inside a Persian
      sentence, phone numbers, code) display in the correct order; punctuation and
      parentheses land on the correct side.
- [ ] Icons and directional affordances (back, next, progress, sliders) mirror where they
      carry direction, and do **not** mirror where they do not (clocks, media playback).
- [ ] Locale-specific formatting is real: check one date, one number, one price per locale
      against what a native reader expects.
- [ ] `lang` and `dir` attributes are correct per rendered locale — screen readers switch
      voices on `lang`, and `accessibility` will otherwise inherit this as a finding.
- [ ] Terminology matches the glossary in each language. A product concept translated two
      different ways in two places is a real defect, not a nit.
- [ ] Legal, consent, and safety text is the jurisdiction's version, not a translation of
      another jurisdiction's version.
- [ ] SEO per locale where content is public: `hreflang`, canonical per locale, translated
      metadata, and locale-appropriate URLs. Hand the details to `seo`.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| Legal, consent, medical, or safety text wrong or absent in a shipped locale | S1 |
| A user-visible string that cannot be translated at all (hardcoded, baked into an image, concatenated) on a primary flow | S2 |
| Machine-translated text published in a language with no qualified human reviewer | S2 |
| A raw translation key or empty string rendered to a user | S2 |
| Right-to-left layout broken to the point of unusability (overlap, reversed reading order, unreachable controls) | S2 |
| Locale-incorrect date, number, or currency formatting on a transactional surface | S2 |
| Terminology inconsistent with the glossary in one language | S3 |
| Missing translation with a correct, visible fallback | S3 |
| Typography that is legible but not idiomatic for the script | S4 |

---

## Owns

The charter's **Languages & localisation** table, the message catalogue's structure and
key naming, and the per-language glossary.

## Hands off to

Source-language wording and voice → `copywriter`. `hreflang`, per-locale metadata and
indexing → `seo`. Screen-reader behaviour, `lang`/`dir` semantics, and contrast in a new
script's typography → `accessibility`. Font loading cost per locale and bundle size of
catalogues → `devops-sre` and `architect`. Jurisdictional wording → `privacy-legal`.

---

## Questions this role asks that nobody else will

- Which language is this sentence's original, and who wrote it?
- Who read this in Persian before a customer did?
- What does this screen look like at German length, in Arabic, on a phone?
- If a key is missing at 2am, what does the user see?
- Is this the same word we used for this concept on the pricing page, in this language?

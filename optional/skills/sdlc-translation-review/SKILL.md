---
name: sdlc-translation-review
description: Review translated or non-source-language content before users see it — what the source string was, who translated it, whether a qualified human read it, glossary consistency, tone per locale, and jurisdiction-specific legal text. Use whenever content is added or changed in a language other than the project's source language, including anything an agent or machine translated.
---

# Translation review

Rules: `{{DOCS_DIR}}/process/08-content-and-translation.md`. Playbooks:
`{{DOCS_DIR}}/roles/localisation.md` and `{{DOCS_DIR}}/roles/copywriter.md`. Source language,
translation workflow, and glossary: the charter's **Languages & localisation** table.

The failure mode this exists to catch is you: an agent writes fluent text in a language
nobody on the team reads, and it ships because it looked confident. Fluency is not
accuracy, and you cannot tell the difference from the inside.

## Before anything else

1. **Name the source string.** Every translated string is a translation *of* something. If
   you cannot point at the source-language original, this is not a translation — it is new
   content written in another language, and it goes through `copywriter` first.
2. **Name the translator and the reviewer.** Machine translation, including yours, may
   draft. It may not be the last reader before a user. If the charter names no reviewer for
   this language, say so plainly: the honest report is *this cannot ship until a named
   human who reads {language} has read it*, not a verdict on text you cannot judge.

## Then check

- **Meaning, not words.** Does the translation say what the source says — including what it
  deliberately does *not* promise? Marketing superlatives and hedges both get lost.
- **Glossary.** Product concepts use the agreed term for that language, everywhere. Two
  words for one concept across two screens is a defect.
- **Register and tone.** Formality (T–V distinction, honorifics), how imperatives read, and
  whether the source's voice survives. A polite English button can be rude in translation.
- **Truth.** `{{DOCS_DIR}}/process/06-evidence-and-claims.md` applies per language: an
  unverifiable claim is not more shippable for being in another language, and claims must
  match what the product does in *that* market.
- **Jurisdiction, not language.** Consent, privacy, medical, financial, safety, and
  comparative-advertising text is the target jurisdiction's version. Two countries sharing
  a language do not share a legal regime — route to `privacy-legal`.
- **Local reality.** Currency, payment methods, phone and address formats, units, time
  zones, holidays, and examples that make sense in that market rather than the source one.
- **Placeholders and length.** Interpolated values survive the translation, plural forms are
  handled, and the string still fits the interface — hand layout breakage to
  `sdlc-i18n-audit`.
- **Names and imagery.** Product, feature, and brand names that were deliberately left
  untranslated stay untranslated; imagery and examples are appropriate for the locale.

## Output

Per string or block: source, translation, verdict, and the specific problem. Anything you
cannot judge is reported as **Unknown** with who could settle it. Log unresolved items in
`{{DOCS_DIR}}/project/assumptions-and-risks.md` rather than letting them ship silently.

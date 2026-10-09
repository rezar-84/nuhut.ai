# 08 — Content and translation

Applies to every project whose charter's **Languages & localisation** table lists more
than one language. A single-language project can read the "Content" half and stop.

The failure this document exists to prevent is specific and common: an agent that writes
fluent text in a language nobody on the team can check, and a team that ships it because
it looked confident. Fluency is not accuracy, and an agent cannot tell the difference from
the inside.

---

## Content

- **One source language.** The charter names it. Strings are authored there; every other
  language is a translation of that string, not an independent original. Two languages
  both treated as canonical will diverge, and the divergence is discovered by a customer.
- **Every user-visible string lives in the message catalogue.** Not in a component, a
  template literal, an email body, an image, or a PDF. A string in code is a string that
  will never be translated, and moving it later costs more than putting it there now.
- **Keys describe purpose, not text.** `checkout.payment.declined`, never
  `your_card_was_declined` — the English wording will change and the key must not.
- **Nothing user-visible is built by concatenation.** Sentences assembled from fragments
  cannot be reordered, inflected, or pluralised by a translator. Use one message with
  parameters and ICU-style plural and select rules.
- **Truth rules apply per language.** `06-evidence-and-claims.md` is not suspended in
  translation: a claim that is unverifiable in the source language is unverifiable in
  every other one, and a claim that only appears in one language still has to be true.

---

## Translation

- **Machine translation may draft. It may not publish.** Any string that reaches a user
  has been read by a named human who reads that language. Record who, in the charter's
  translation workflow row. This includes strings an agent translated: an agent is a
  machine translator with better manners.
- **No language ships without a reviewer.** If nobody can review Turkish, the project does
  not ship in Turkish yet. Shipping it anyway is a decision a named human makes and
  records, not a default.
- **Legal, consent, medical, safety, and regulated text is written per jurisdiction**, not
  translated per language. Argentina and Spain share a language and not a legal regime;
  `privacy-legal` decides, `localisation` places it.
- **Terminology is decided once, per language, in the glossary** the charter points at.
  One product concept, one agreed word per language. Inconsistent terminology is a defect,
  not a preference.
- **An untranslated key falls back visibly to the source language.** It never renders as a
  raw key, an empty string, or a silent blank region.
- **Removing a locale is a change, not a cleanup.** Say what happens to its URLs, its
  indexed pages, and its users.

---

## Code and layout

- `lang` and `dir` are set from the rendered locale, on the document and on any
  user-generated content that may differ from it.
- Right-to-left support is a layout property: logical CSS properties (`margin-inline`,
  `padding-inline`, `inset-inline`) rather than left/right, mirrored directional icons,
  unmirrored non-directional ones (clocks, media playback, checkmarks).
- Dates, times, numbers, currency, units, addresses, and personal-name order are formatted
  through the platform's locale APIs. Never hand-rolled, never assumed from the source
  locale.
- Fonts must actually contain the script's glyphs, and per-locale font weight and line
  height are checked rather than inherited.
- Text length is variable: interfaces are tested at long-word lengths (German, Finnish)
  and tall-line-height scripts (Persian, Arabic, Thai) before they are called done.

---

## Verification

A change touching more than one language is not verified until:

1. The product has been **run in every shipped locale**, not only the source one.
2. Every new key exists in every locale file, or its fallback has been seen.
3. A **pseudo-locale or longest-string pass** has been run over the changed screens, where
   the tooling supports one — and where it does not, that is stated as *Absent* per
   `06-evidence-and-claims.md`.
4. Bidirectional strings (a Latin brand name inside a right-to-left sentence, phone
   numbers, code snippets) have been looked at, not assumed.

Claims about a language nobody on the team reads are reported as **Unknown**, with what
would settle it — never as *Verified* because the strings looked plausible.

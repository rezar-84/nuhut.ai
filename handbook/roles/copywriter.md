# Role — Copywriter / Content Designer

**Mission:** ensure every word a user reads is true, clear, useful at the moment it
appears, and consistent with how the product speaks everywhere else.

Interface text is not decoration applied at the end. It is most of the interface.

---

## Engage when

- Any user-visible text changes: headings, body, labels, buttons, placeholders, help
  text, error messages, empty states, notifications, emails, CLI output, documentation.
- Terminology or naming changes.

## Skip when

- No text a user will read is affected. (Log messages are `devops-sre`; code comments
  are nobody's review.)

## Reads

`project/product-brief.md` (positioning, audience), the voice and terminology sections of
`project/content-seo-plan.md`, existing production copy for consistency, and the actual
strings in the change.

---

## Design-review checklist

**Truth first**
- [ ] Every claim is verifiable. No invented statistics, credentials, client names,
      outcomes, or guarantees. See `../process/06-evidence-and-claims.md` — this is the
      role most likely to be the last line of defence against a fabricated claim.
- [ ] Claims about capability match what the product actually does today, not what is
      planned.
- [ ] No implied promise the product cannot keep ("instant", "always", "guaranteed",
      "secure" as an unqualified adjective).
- [ ] Regulated language (financial, medical, legal, environmental, comparative
      advertising) goes to `privacy-legal` before it ships.

**Clarity**
- [ ] Says the most important thing first. A heading that requires the paragraph below
      it to make sense is a failed heading.
- [ ] Written for the reader's vocabulary, not the team's. No internal jargon, project
      code names, or system terminology leaking into the interface.
- [ ] Concrete over abstract. "Sync failed — your last three reports did not update"
      beats "an error occurred during the operation".
- [ ] Short by default. Cut every word that does not change the meaning. Then check that
      cutting did not remove the useful specifics — brevity that costs information is
      not an improvement.
- [ ] Active voice, present tense, second person, unless the project's voice says
      otherwise.

**Function**
- [ ] Buttons name their outcome (`Send invitation`), not their mechanism (`Submit`) or
      the abstract (`OK`).
- [ ] Error messages: what happened · whether the reader caused it · what to do now ·
      how to get help if that fails. Never a raw code alone, never blame.
- [ ] Empty states teach: what belongs here, why it is empty, and the one action to take.
- [ ] Labels and help text answer the question the field actually provokes.
- [ ] Confirmations state exactly what will happen, especially the irreversible part.

**Consistency**
- [ ] One term per concept, product-wide. If it is a "workspace" here it is not an
      "organisation" there. Maintain the terminology list.
- [ ] Product, company, and third-party names spelled and cased exactly as their owners
      write them.
- [ ] Capitalisation, punctuation, date, number, and currency formats follow one
      documented convention.

**Localisation** *(if the project has more than one language)*
- [ ] Each language is an editorial version, not a substituted string. Meaning and
      evidence preserved; idiom appropriate to the reader.
- [ ] Machine or agent-produced text in any language is labelled as **draft pending
      native review** and must not ship as final. Record the label in the worklog.
- [ ] No concatenated sentence fragments — grammar differs by language and the pieces
      will not reassemble.
- [ ] Numerals, dates, currency, plurals, and name order follow each locale's convention.
- [ ] Text expansion is accommodated: translations commonly run much longer than the
      source.

## Ship-review checklist

- [ ] Read every string in the diff, in place, in the rendered product. Copy reviewed in
      a spreadsheet reads differently on screen.
- [ ] Read the error and empty states specifically — they are where placeholder text
      survives to production.
- [ ] Search the diff for leftover lorem ipsum, `TODO`, test strings, and developer
      shorthand.
- [ ] Check that a claim added here does not contradict a claim elsewhere in the product.
- [ ] Terminology list updated if a new concept was named.

---

## Severity calibration

This role owns **truth in user-visible text**. Every other role that spots an invented
claim hands it here rather than rating it separately.

| Finding | Sev |
| --- | --- |
| An invented or unverifiable factual claim shown to users, where being wrong is legally or financially consequential | S1 |
| Any other invented or unverifiable factual claim shown to users | S2 |
| Placeholder or test text reaching a user-facing surface | S2 |
| Machine-translated or agent-authored copy published as final in a language with no qualified reviewer | S2 |
| An error message whose wording gives the user no way to proceed | S2 |
| Terminology inconsistent with the project's own glossary | S3 |
| Wording that could be shorter or clearer | S4 |

The last row is the one to be disciplined about: prose preferences are S4, and a review
that produces fifteen of them has produced nothing. Raise a wording nit only where it
changes what the reader will do.

---

## Owns

Voice, tone, and terminology sections of `project/content-seo-plan.md`; the string
inventory.

## Hands off to

Keyword and metadata implications → `seo`. Persuasive structure and CTA performance →
`cro-analyst`. Legal and regulatory wording → `privacy-legal`. Where the text sits and
what state it belongs to → `ux-designer`.

---

## Questions this role asks that nobody else will

- Is this sentence true, and how do we know?
- What question is the reader asking at this exact moment, and does this answer it?
- What does this word mean to someone who does not work here?
- If this is the only sentence they read, is it the right one?

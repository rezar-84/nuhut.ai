---
name: sdlc-slop-filter
description: Find and rewrite the phrasings that make prose read as machine-written, such as stock AI vocabulary, "not X but Y" contrasts, inflated significance, vague attribution, signposting, chatbot leftovers and formatting by rule. Use when writing, editing or reviewing marketing copy, landing pages, emails, blog posts, product descriptions, UI text, README or docs prose, or when asked to humanize text, remove AI slop, de-slop, or make copy sound less like AI. When the charter's Slop filter row is strict, use before finishing any prose at all, including records, commit messages and PR descriptions.
---

# Slop filter

Readers stop trusting copy the moment it sounds generated. This skill finds the phrasings
that cause that and replaces them with plain statements of the same facts.

The patterns are adapted from Wikipedia's
[Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
(CC BY-SA 4.0), read alongside the `humanizer` and `stop-slop` skills. The copywriter's
playbook is `{{DOCS_DIR}}/roles/copywriter.md`.

## What the charter asks for

Read the **Slop filter** row in `{{DOCS_DIR}}/project/charter.md`.

| Row | Applies to | A finding is |
| --- | --- | --- |
| `on` | public and user-facing copy: pages, emails, product text, UI strings, README | advice; fix it or say why it stays |
| `strict` | every piece of prose you write, including docs, records, commit messages and PR text | a blocker; the text is not done while `sdlc.py slop --strict` fails it |
| `off` or blank | only text the person asks you to check | advice |

A request to check or rewrite a text applies the filter to that text whatever the row says.

## Procedure

1. **Scan.** `python3 .ai-sdlc/bin/sdlc.py slop <files>` lists each mechanical tell by line
   with a fix. With no path it scans the prose files changed against `HEAD`. For text that
   is not in a file, pipe it: `sdlc.py slop - < draft.md`.
2. **Read the whole text once** for what the scanner cannot see: the tells under
   "Judgment" below, and paragraphs whose shape is the tell.
3. **Rewrite.** Keep every claim that has support. Add no fact, number, name or quote that
   was not in the source or in a document you can cite. A sentence that only decorates is
   cut, and its paragraph is rewritten around what is left.
4. **Check the rewrite against the original.** A claim lost by accident is an error. A
   claim added is an error.
5. **Scan again** and report what remains and why.

## The tells

The scanner covers the first three groups and the formatting group. `sdlc.py slop --guide`
prints its rules.

**Strong: edit on one sighting**

- Chat leftovers: `I hope this helps`, `Certainly!`, `let me know if`, offers of more help,
  knowledge-cutoff notes, unfilled `[placeholders]`, chatbot citation markup, a
  `utm_source=chatgpt.com` link.
- Narrating the search: `while specific details are limited`,
  `based on available information`, `maintains a low profile`. Say what is known and stop.
- Contrast with a claim nobody made: `not just X, but Y`, `it's not X, it's Y`. State Y.
- Signposting: `it's important to note`, `let's dive in`, `here's the thing`,
  `when it comes to`, `in today's fast-paced world`, `in conclusion`. Start with the point.
- Inflated significance: `stands as a testament`, `plays a pivotal role`,
  `evolving landscape`, `rich tapestry`, `setting the stage for`. Give the fact that would
  make it significant.
- Borrowed authority: `experts agree`, `studies show`, `industry reports`,
  `widely regarded`. Name the source or drop the claim.
- The challenges formula: `despite these challenges`, then an upbeat line about the future.
- Sales stock: `unlock your potential`, `game-changer`, `take X to the next level`,
  `whether you're A or B`. Say what it does, for whom, and how much.

**Moderate: fine once, a tell in a cluster**

- Stock vocabulary: `delve`, `tapestry`, `testament`, `pivotal`, `crucial`, `intricate`,
  `multifaceted`, `underscore`, `showcase`, `foster`, `garner`, `bolster`, `leverage`,
  `seamless`, `vibrant`, `renowned`, `transformative`, `holistic`, `myriad`, `elevate`,
  `empower`, `align with`, `valuable insights`. Use the ordinary word or the fact itself.
- Dodging `is` and `has`: `serves as`, `stands as`, `functions as`, `boasts`.
- A participle tacked on after a comma to claim meaning: `, highlighting ...`,
  `, underscoring ...`, `, reflecting ...`, `, ensuring ...`.
- Opening a sentence with `Additionally,` `Moreover,` or `Furthermore,`.
- An emoji leading a heading or bullet.

**Weak: act only when dense, or beside other tells**

Em dashes, groups of three, `rather than`, `associated with` where the relationship could
be named, curly quotes, title-case headings, list items that each open with a bold label.

## Judgment

The scanner cannot see these. Look for them on the read-through.

- One-line closers that restate the paragraph as a slogan.
- A paragraph that argues with an objection nobody raised.
- Every paragraph the same length, or every section ending on the same beat.
- Several sentences in a row opening with the same subject.
- Synonyms cycled for one thing. Pick the name and repeat it.
- Hedges stacked until no claim is left: `may potentially help to some extent`.
- A heading followed by a sentence that repeats the heading.
- The text describing itself: what this section will cover, what was just covered.
- Explaining what the reader already knows before reaching the decision they came for.

## Not tells

Do not "fix" these, and do not accuse a text on them: correct grammar, a formal register,
plain or dry prose, one transition word, one stock word, one dash. Each appears in
careful human writing. The signal is a cluster.

A match says where to look. It never shows who wrote a text, and this skill is not an
AI detector. Do not report that a text "is AI-generated".

## What overrides the patterns

- **A voice sample or house style.** If the charter, a brand guide or the person gives a
  sample, match its sentence length, punctuation and vocabulary. A writer who uses dashes
  keeps them.
- **Quoted material, legal text, code, commands, paths, data and link targets.** Leave
  them exactly as they are.
- **A word doing its literal job.** `landscape` in a gardening page, `robust` for a
  statistical estimator, `underscore` for the character.
- **Other languages.** The word lists are English. In another language apply the
  structural tells and the Judgment list, and say that the vocabulary was not checked.
- **A deliberate exception.** Put `slop-ok` in a comment on the line, or
  `<!-- slop-filter: off -->` at the head of a file that quotes tells on purpose.

## Output

For a review: findings by location with the tell, why it weakens the sentence, and the
rewrite. For a rewrite: the new text, then a short list of what changed and anything
left in place with the reason. In both, state what was not checked, and quote the
scanner's final summary line.

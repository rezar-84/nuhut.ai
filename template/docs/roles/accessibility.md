# Role — Accessibility

**Mission:** ensure everyone can use this, including people navigating by keyboard,
screen reader, magnification, voice, or switch, and people with low vision, colour
blindness, motor differences, or cognitive load.

Accessibility is a correctness property, not a preference. In many jurisdictions it is
also a legal obligation (`privacy-legal`).

**Target:** whatever the charter's "Accessibility target" names. If it is blank, that is
itself a finding — say so and review against WCAG 2.2 level AA, the common default, while
noting the target was assumed rather than stated. Applies to web, native, and — in its
own way — terminal and document output.

---

## Engage when

- Any user interface changes.
- Colour, contrast, typography, motion, or focus behaviour changes.

## Skip when

- No human-facing interface exists.

## Reads

`project/design-system.md`, the charter's accessibility target and supported assistive
technologies, and the running interface.

---

## Design-review checklist

**Structure**
- [ ] Semantic elements carry the meaning: headings, lists, landmarks, tables, buttons,
      links. A generic container with a click handler is not a button.
- [ ] Heading order is logical and unskipped; the page structure is navigable by
      headings alone.
- [ ] A link goes somewhere; a button does something. Using the wrong one breaks
      keyboard and assistive expectations.
- [ ] Every input has a programmatically associated, visible label. Placeholder text is
      not a label.
- [ ] Reading order in the markup matches the visual order.

**Keyboard**
- [ ] Everything operable by pointer is operable by keyboard, in a sensible order.
- [ ] Focus is always visible, with sufficient contrast against every background it
      lands on.
- [ ] No keyboard trap. Overlays, dialogs, and embedded content can be escaped.
- [ ] Focus is managed on change: moved into a dialog on open, restored to the trigger
      on close, moved to new content when it appears, moved to the error on failure.
- [ ] A skip-to-content mechanism exists where there is repeated navigation.

**Perception**
- [ ] Text contrast at least 4.5:1 (3:1 for large text); interface components and
      meaningful graphics at least 3:1. Check every theme.
- [ ] Colour is never the only carrier of meaning — pair it with text, shape, or icon.
      Status indicated by colour alone fails for a substantial share of users.
- [ ] Layout survives 200% zoom and 400% reflow without loss of content or function, and
      does not require two-dimensional scrolling.
- [ ] Text is real text, not an image of text.
- [ ] Images have alternative text that conveys purpose; decorative images are marked as
      decorative rather than described.
- [ ] Media has captions and, where meaningful content is visual only, a description.

**Interaction**
- [ ] Interactive targets are large enough (24×24 CSS px minimum; 44×44 recommended for
      primary controls) and adequately spaced.
- [ ] No function requires a complex gesture, precise timing, or a drag without an
      alternative.
- [ ] Motion respects the reduced-motion preference; nothing auto-plays, flashes, or
      moves without a control to stop it.
- [ ] Timeouts are avoidable, extendable, or warned about.

**Communication**
- [ ] Dynamic changes are announced — validation errors, results loaded, saved,
      progress, and background updates.
- [ ] Errors identify the field, describe the problem in text, and suggest a correction.
- [ ] State is exposed programmatically: expanded, selected, checked, disabled, busy,
      invalid, current.
- [ ] Language of the page and of any inline foreign passage is declared, so a screen
      reader pronounces it correctly.

## Ship-review checklist

- [ ] Run an automated checker — and know that it finds perhaps a third of real issues.
      Passing it is a floor, not a result.
- [ ] Navigate the entire flow with the keyboard alone. Complete the task. If you cannot,
      that is the finding.
- [ ] Traverse it with a screen reader. Does the announced experience make sense in
      order, or is it a list of unlabelled elements?
- [ ] Zoom to 200% and reflow to a narrow viewport.
- [ ] Check contrast on the actual rendered result, in every theme, including focus
      indicators, placeholders, disabled states, and text over images.
- [ ] Test with reduced motion enabled.
- [ ] Record known limitations honestly rather than claiming conformance you did not
      verify.

---

## Severity calibration

An accessibility barrier is S2 by default (`../process/04-quality-gates.md`). It rises to
S1 when it makes a primary journey impossible rather than painful — "poor workaround" and
"no workaround" are different ratings, and this is where most miscalibration happens.

| Finding | Sev |
| --- | --- |
| Content flashing more than three times per second — a seizure risk | S0 |
| A primary task cannot be completed by keyboard alone | S1 |
| A keyboard trap with no escape | S1 |
| A form input with no programmatic label, or an error announced to nobody | S2 |
| Text contrast below threshold on a primary reading surface | S2 |
| Meaning conveyed by colour alone on a critical status | S2 |
| Claiming a conformance level that was not verified | S2 — and see `../process/06-evidence-and-claims.md`; this is a false claim as well as a barrier |
| A secondary control unreachable by keyboard, with an equivalent route that is | S2 — a barrier is S2 even where something else still works; there is no S3 rung for this |

Whether a task is completable *at all* on a given device or input method is
`ux-designer`'s call; whether it is completable with **assistive technology** is this
role's. The charter names which technologies count.

---

## Owns

The accessibility section of `project/design-system.md`; the conformance statement and
its known exceptions.

## Hands off to

Contrast token values → `brand-designer`. Focus behaviour within flows → `ux-designer`.
Alternative-text wording → `copywriter`. Legal conformance obligations →
`privacy-legal`. Automated checks in the pipeline → `qa` / `devops-sre`.

---

## Questions this role asks that nobody else will

- Can I finish this task without touching the mouse?
- What does this sound like, in order, with no visual context?
- What does this look like to someone who cannot distinguish these two colours?
- What happens at 400% zoom on a small screen?

---
name: sdlc-accessibility-audit
description: Audit an interface against the charter's accessibility target using the accessibility role playbook — keyboard path, focus order and visibility, semantics and names, contrast, motion, forms and error recovery, and assistive-technology behaviour. Use whenever UI is added or changed, before shipping any user-facing screen, or when asked about accessibility, a11y, WCAG, screen readers, or keyboard support.
---

# Accessibility audit

Playbook: `{{DOCS_DIR}}/roles/accessibility.md`. Target and supported assistive
technologies: the charter's **Standards & targets**. If the charter names no target, that
is the first finding — audit against WCAG 2.2 AA and say you assumed it.

## Audit in this order

1. **Keyboard only.** Put the mouse away. Can every interactive element be reached,
   operated, and left? Is the focus indicator visible on each one, against its actual
   background? Is the order the visual order? Is anything a trap?
2. **Semantics.** Real elements before ARIA: `button` for actions, `a[href]` for
   navigation, headings in order, real lists, labels tied to their inputs. Every control
   has an accessible name that says what it does, not what it looks like.
3. **State.** Loading, empty, error, success, disabled, expanded/collapsed — is each one
   announced, not only drawn? Is a live region used for changes that happen away from
   focus?
4. **Forms.** Label, hint, error, and required state programmatically associated. Errors
   identify the field and how to fix it, in text, not colour alone. Focus moves to the
   first error.
5. **Contrast and colour.** Text and non-text (icons, focus rings, borders) against real
   backgrounds. Colour is never the only carrier of meaning.
6. **Motion and timing.** `prefers-reduced-motion` honoured. Nothing auto-plays or
   auto-advances without control. No timeout the user cannot extend.
7. **Zoom and reflow.** 200% zoom and 320px width without horizontal scrolling or clipped
   content.
8. **Assistive technology.** Test with the screen reader and browser pairs the charter
   names. If none are named, say that nothing was tested against — that is a gap, not a
   neutral state.

## Rules

- Report findings with severity per `{{DOCS_DIR}}/process/04-quality-gates.md`, location as
  `file:line`, what a real user cannot do, and the fix.
- Say plainly what you did **not** check, especially anything you could not run from here.
- Automated tooling covers a minority of the criteria — never present a passing axe run as
  an accessible interface.

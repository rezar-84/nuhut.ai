---
name: sdlc-design-review
description: Review a visual change against the project's design system and brand — tokens versus hardcoded values, the spacing and type scale, component reuse, every interaction state, responsive behaviour, and the empty/loading/error cases. Use when screens, components, styles, or design tokens change, or when asked whether something looks right.
---

# Design review

Playbooks: `{{DOCS_DIR}}/roles/brand-designer.md` and `{{DOCS_DIR}}/roles/ux-designer.md`.
Sources of truth for tokens and brand: the charter's **Sources of truth** table — use it;
do not reconstruct the system from the nearest component.

## Check

1. **Tokens, not values.** Colour, spacing, radius, shadow, and type scale come from the
   system. A hardcoded hex or a one-off `13px` is a finding, reported with the token that
   should have been used.
2. **Reuse before invention.** Does an existing component already do this? A near-duplicate
   with slightly different padding is how a design system dies.
3. **The whole state machine.** Default, hover, focus-visible, active, disabled, loading,
   empty, error, success, and the too-much-content case (long names, long lists, missing
   images). A screen designed only for the happy path is not designed.
4. **Hierarchy.** Does the primary action read as primary? Is there exactly one? Does the
   layout hold at the sizes the charter names?
5. **Responsive and density.** The supported breakpoints, not just the design canvas. Touch
   targets large enough. No layout that only works at one width.
6. **Copy in place.** Real strings, real lengths, real locales — including the writing
   directions the charter lists. Lorem ipsum hides every layout bug that matters.
7. **Consistency with what exists.** A change that is better in isolation but inconsistent
   with the rest of the product is a finding, not an improvement — raise it as a system
   change instead.

## Rules

- Look at the rendered result, not only the diff. Run it if it runs; say if you could not.
- Accessibility is a separate pass with its own playbook — run `sdlc-accessibility-audit`
  rather than declaring the visuals accessible here.
- Report findings with severity, location, and the fix; state what you did not review.

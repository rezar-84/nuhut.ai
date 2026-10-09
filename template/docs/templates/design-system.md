---
status: draft
owner: brand-designer
last-reviewed: YYYY-MM-DD
---

# Design system — {{PROJECT_NAME}}

> The source of truth for visual and interaction decisions. If a value appears in code
> that is not here, either add it here or replace it with a token
> (`../roles/brand-designer.md`).

## Foundations

Where the tokens actually live: `_(path to the token file / theme definition)_`

This document describes intent and usage rules; the file is authoritative for values.

### Colour

| Token | Role | Notes |
| --- | --- | --- |
| | _(surface, text, accent, danger, success…)_ | _(where it may and may not be used)_ |

- Naming is by **role**, not appearance (`text-muted`, not `grey-2`) — appearance names
  break the first time there is a second theme.
- Semantic colours carry one meaning each; decorative use of a semantic colour is a
  defect.
- Every text/background pair used in production must meet the contrast target in
  `../roles/accessibility.md`. Record verified pairs here.

### Typography

| Token | Size / line height / weight | Used for |
| --- | --- | --- |

- Font stacks per script, if the project supports more than one writing system, including
  per-script line-height adjustment.
- The scale is deliberately short. Adding a size is a decision, not a convenience.

### Spacing, radius, elevation, motion

_(The scales, and the rule for choosing between steps. Motion: durations, easing, and
the reduced-motion behaviour.)_

### Breakpoints & density

_(The supported range — state the smallest supported width, because that is the one that
breaks.)_

## Components

| Component | States it must define | Notes |
| --- | --- | --- |
| | default · hover · focus · active · disabled · loading · error | |

**Every component defines its states before it is considered complete**, including the
ones designers forget: focus (visible, contrasting), disabled (and *why* it is disabled,
communicated somewhere), loading, and error.

## View-level states

The checklist every screen is held to (`../roles/ux-designer.md`):

empty · loading · partial · error · unauthorised · forbidden · not-found · success ·
extreme content (one item, many items, very long strings, missing images)

## Themes

_(Which themes are supported. Each is designed, not derived by inversion. Both are
verified for contrast.)_

## Writing direction & internationalisation

_(If applicable: which directions and scripts are supported; mirroring rules; what does
**not** mirror — charts, progress, timelines, media controls, code; per-script fonts and
line heights; how text expansion is accommodated.)_

## Accessibility commitments

- Target: _(WCAG 2.2 AA unless higher)_
- Minimum target size: _(24×24 minimum, 44×44 for primary controls)_
- Focus indicator specification: _(and its contrast against every surface it lands on)_
- Verified assistive technologies: _(list — do not claim untested ones)_
- Known exceptions: _(honest list, each with a backlog ID)_

## Usage rules

_(The things that are easy to get wrong: when to use each button variant, how to combine
surfaces, what never appears next to what, the maximum number of primary actions per
view.)_

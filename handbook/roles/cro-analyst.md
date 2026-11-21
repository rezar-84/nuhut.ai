# Role — CRO / Growth Analyst

**Mission:** ensure the journey from arrival to the intended outcome actually completes,
that friction is where it earns its keep, and that we can measure whether any of it
worked.

Conversion is not only purchase. It is whatever the charter names as the outcome:
sign-up, activation, task completion, retention, submission, upgrade, referral.

---

## Engage when

- A conversion path, funnel step, form, pricing surface, onboarding flow, or call to
  action changes.
- Analytics, events, or experiment infrastructure changes.

## Skip when

- No user journey toward a measurable outcome is affected.

## Reads

`project/measurement-plan.md`, `project/product-brief.md` (success metrics and
baselines), current funnel data if the charter names a source, and the flow itself.

---

## Design-review checklist

**The outcome**
- [ ] The intended action on this surface is singular and obvious. Competing primary
      calls to action split intent and reduce both.
- [ ] The value is stated before the ask. Nobody fills a form to find out what it is for.
- [ ] The next step is always visible without hunting.

**Friction audit** — every step, field, and click must justify itself
- [ ] Each form field is either required for the outcome or removed. "Nice to have for
      sales" fields cost completions; if one is kept, that trade is explicit.
- [ ] Nothing is requested before it is needed. Defer what can be collected later.
- [ ] Account creation, payment, or verification is not imposed earlier in the sequence
      than the value delivered.
- [ ] Error recovery does not restart the journey or lose entered data.
- [ ] Time-to-first-value is as short as the product allows.

**Trust** — the reason most journeys actually fail
- [ ] The user can tell who they are dealing with, and what happens to their submission.
- [ ] Evidence is present at the moment of the ask, and it is **real** evidence
      (`../process/06-evidence-and-claims.md`). Fabricated social proof is a blocking
      failure, not a growth tactic.
- [ ] Cost, commitment, cancellation, and data use are stated before the commitment, not
      after.
- [ ] Nothing manipulative: no false scarcity, no fake countdown, no pre-checked
      consent, no confirm-shaming, no obstruction of the exit. These convert once and
      cost trust permanently — and in many jurisdictions they are illegal.

**Measurement — the part that is always deferred and should not be**
- [ ] Every step of the funnel emits an event, with a documented name and payload.
      Naming follows one convention project-wide.
- [ ] The event map exists *before* the feature ships. Instrumentation added later
      cannot answer questions about the launch.
- [ ] A baseline is recorded for anything being changed, or the change is unevaluable.
- [ ] Success and its counter-metric are both named. "More sign-ups" with no eye on
      qualification or retention optimises for the wrong thing.
- [ ] **Tag governance:** the analytics or tag-manager snippet is installed as its vendor
      specifies; tags added through a tag manager are reviewed like code and fit the
      Content Security Policy; development and production report to separate
      properties, so test traffic never pollutes the real numbers.
- [ ] Tracking is consent-aware and privacy-compliant (`privacy-legal`), and the product
      still works when consent is refused.

**Experiments** *(if the project runs them)*
- [ ] One hypothesis, stated as: because *observation*, we believe *change* will cause
      *effect*, measured by *metric*.
- [ ] Sample size and duration decided in advance, honouring full business cycles.
- [ ] Guardrail metrics defined — what must not get worse.
- [ ] A stopping rule agreed before launch. Peeking until it is significant is not a
      result.

## Ship-review checklist

- [ ] Walk the entire journey as a new user, in a clean session, on the smallest
      supported device.
- [ ] Verify each event actually fires, once, with the right payload — in the real
      environment, not a mock.
- [ ] Confirm the submission arrives where it is supposed to arrive, and that a failure
      to deliver is visible to someone rather than silent.
- [ ] Verify the funnel is queryable end to end after the change.
- [ ] Confirm behaviour with tracking blocked or consent declined.

---

## Severity calibration

| Finding | Sev |
| --- | --- |
| A conversion action that silently fails — the user sees success, nothing is recorded | S1 |
| A manipulative pattern as listed above | S2 |
| A change to a measured surface shipped with no baseline and no instrumentation | S2 |
| Friction added to the primary journey with no stated reason | S3 |
| An event fired with an inconsistent name or payload | S3 |

Two findings that look like this role's belong elsewhere: **fabricated social proof,
testimonials, or statistics** is `copywriter`'s (invented claim shown to users), and
**tracking that fires before or despite consent** is `privacy-legal`'s. Hand them over
with the location; do not rate them here as well.

---

## Owns

`project/measurement-plan.md` — the event map, the funnel definition, baselines, and
experiment records.

## Hands off to

Flow structure and states → `ux-designer`. Wording of the ask → `copywriter`. Consent
and data legality → `privacy-legal`. Whether the outcome is the right outcome →
`product-manager`. Traffic and arrival → `seo`.

---

## Questions this role asks that nobody else will

- Where exactly do people give up today, and does this change address that place?
- If this doubles the metric, what else gets worse?
- Can we tell tomorrow whether this worked, or will we be guessing?
- Is this friction protecting the user, or protecting a process nobody has questioned?

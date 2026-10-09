---
name: sdlc-eval-gate
description: Gate a change to a prompt, system message, model version, retrieval configuration, index, inference parameter, or evaluation threshold — and any claim that an AI or ML output got better, more accurate, or more reliable. Use before editing a prompt file, changing a model identifier, tuning retrieval, or reporting a quality number.
---

# Eval gate — measure before, or you have no claim

`{{DOCS_DIR}}/process/09-probabilistic-and-data-systems.md` is the authority, and
`{{DOCS_DIR}}/roles/ml-engineer.md` is the review. This skill is the stop before the edit.

## Stop and check three things

1. **What tier is this?** A prompt is executable. If it governs authorisation, tenancy,
   payments, safety, PII, public claims, or an action the system takes, it is Tier 1.
   Otherwise it is Tier 2. "It is just a string" is not a tier argument, and this change
   is almost never Tier 3.
2. **Is there a baseline?** Measured *before* this change, on a golden set that is not
   also changing in this work item. If not, that is the finding: establish it first.
   Without one there is no improvement to claim, only a number.
3. **Is the thing you are changing pinned?** Model, prompt, retrieval config, index
   build, and inference parameters are dependencies. A floating alias means the product
   changes with no commit, no review, and no rollback point.

## The procedure

1. Record the current configuration and the baseline result: method, golden-set version,
   N, spread, environment, date. Read `{{DOCS_DIR}}/project/eval-plan.md`; if it does not
   exist and this project has a probabilistic output, creating it *is* the first task.
2. Make the change. Change the system **or** the evaluation set — never both in one work
   item. A comparison across a changed set is not a comparison, and reporting it as one
   is fabrication under Prime Directive 1.
3. Re-run under identical conditions: same set version, same environment, same seed and
   sampling policy, same N.
4. Report both numbers as **Measured** (`{{DOCS_DIR}}/process/06-evidence-and-claims.md`)
   — never as "verified" or "improved".
5. **Say what got worse.** Report per category, not only in aggregate. A mean that
   improved while a refusal or safety category regressed is a worse system, and the
   aggregate is how that ships.

## Before it can be called done

- The refusal path, the empty-retrieval path, and the provider-failure path were
  exercised, not reasoned about. A confident answer built on an empty retrieval is the
  characteristic failure of this architecture and no aggregate score shows it.
- Nothing tuned on was reported on.
- The previous prompt, model, and index are recoverable, and the rollback ordering is
  stated.
- `{{DOCS_DIR}}/project/eval-plan.md` history has a row: date, work item, set version,
  result, and what got worse.

## What you may not write

"More accurate", "better", "improved", "more reliable", or "seems to handle X now" with
no before-number, no N, and no spread. One good-looking output is an anecdote. If you
have not measured, the honest sentence is: *the change is in; its effect is unmeasured.*

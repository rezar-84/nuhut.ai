---
name: sdlc-intake
description: Frame an incoming request as a tracked work item before writing any code — read the charter, assign the next {{PREFIX}}-### ID, classify the risk tier, and produce the reading list for that tier. Use whenever a new request, bug report, or idea arrives and no work item exists for it yet, including the ones that look like a two-minute fix.
---

# Intake — turn a request into a tracked work item

The cost of skipping this is not process theatre: it is a change nobody can trace, tiered
by vibes, reviewed by the wrong roles, and merged against a charter nobody read.

## 1. Read first

- `{{DOCS_DIR}}/project/charter.md` — identity, stack, commands, active roles, risk
  defaults. If it is blank where it matters, run the `sdlc-charter-audit` skill and say
  what is Unknown rather than guessing past it.
- `{{DOCS_DIR}}/project/assumptions-and-risks.md` — what is already known to be shaky.
- `{{DOCS_DIR}}/project/backlog.md` — the highest ID in use, including `Dropped` rows.

## 2. Restate

One sentence, in your own words, of what is being asked. If an upstream specification
exists (from GitHub Spec Kit, Kiro, or a spec file), cite it and use its defined problem
statement and scope. If your restatement could plausibly mean something materially
different from the request, ask now — this is the cheapest moment in the whole loop to ask.

For anything above Tier 3, write the restatement as five short lines. They go into the plan
(Tier 1) or the response (Tier 2), not into a new file:

- **Problem:** what is wrong or missing today, and for whom.
- **Outcome:** what will be observably true afterwards.
- **Affected:** the users, systems and contracts it touches.
- **Constraints:** what it must not do or change.
- **Open questions:** what nobody has answered yet.

The request may come from a machine rather than a person: an alert past its threshold, a
scheduled scan, a failed pipeline an agent triaged. It gets the same five lines, with the
evidence that triggered it quoted under Problem.

## 3. Assign the ID

`{{PREFIX}}-###`: the highest number found anywhere in `{{DOCS_DIR}}/project/`, plus one.
Numbers are never reused. Add a terse row to `{{DOCS_DIR}}/project/backlog.md`.

## 4. Classify the tier

Use "Risk tiers" in `AGENTS.md`, then the charter's **Risk defaults** — a project may
declare a surface always Tier 1 or never Tier 1. When in doubt, tier up and say why.

The tier decides three things at once: how much planning, which roles review, and how much
you are expected to read. Do not carry a Tier 1 surface at Tier 3 because the diff is
small — the tier follows the blast radius, not the line count.

Then resolve the independent **effort mode**: an explicit `lean mode`, `normal mode`, or
`beast mode` in the current request wins; otherwise use a mode already recorded for the
work item, then the charter's **Default effort mode**, then `Normal`. Risk is the floor:
Lean cannot remove a required check or approval, and Beast cannot widen product scope.

## 5. Check readiness

The Definition of Ready items knowable now (`{{DOCS_DIR}}/process/03-ready-and-done.md`).
An upstream spec with testable Given/When/Then scenarios satisfies the acceptance criteria
check directly. A failing item is recorded as a blocker, not guessed past. If a Tier 1
item is missing an accountable human, approvers, or the data and jurisdiction facts,
park it — see "Waiting on a human" in `{{DOCS_DIR}}/process/00-operating-model.md`.

## 6. Produce the reading list

Name the specific files this change requires reading before it is designed: the role
playbooks that apply (`{{DOCS_DIR}}/roles/`), the artifacts it will falsify, the code paths
it touches. A Tier 3 reading list is allowed to be one line.

## Output

Report the restatement, the ID, the tier and why, the resolved effort mode, the roles that will review, the reading
list, and any blocker. Then hand off to `/sdlc-plan` — do not start implementing from
inside this skill.

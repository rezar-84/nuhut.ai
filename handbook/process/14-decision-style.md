# 14 — Decision style

How much the agent decides for the person, and how much it says while it works. One
setting, three values, chosen once in the charter's **Decision style** row. It changes who
makes a decision and how it is explained. It never changes a tier, a check, a review, or
an approval.

**Read this when** the work needs a choice that the request did not settle, when the
person is not a specialist in the subject, or when the charter or the request names a
style. Skip it otherwise.

---

## 1. Choosing the style

Resolve it at FRAME, in this order: the current request ("just do it", "ask me before
anything") → the work item's recorded style → the charter's **Decision style** → `Guide`.

| Style | The agent | Chat output |
| --- | --- | --- |
| **Ask** | Puts every material decision to the person, with options and trade-offs, and waits | Detailed: the reasoning and the alternatives |
| **Guide** (default) | Recommends one option and names two alternatives in plain language, states the consequence of each, and asks. Does not ask about trivial or easily reversed choices | Normal: what was done, what needs attention |
| **Autopilot** | Takes the recommended option, logs it, and keeps going | Quiet: results and anything that stopped the work |

Output volume follows the style because the person who wants to decide everything wants
the reasoning, and the person who wants it handled wants the result. **Volume affects
chat only.** The worklog, ADRs, review records, and verification evidence keep the same
required content in every style. A quiet reply is never a reason for a thinner record.

## 2. What no style can lift

Autopilot is not a way around the kit's gates. In every style:

- A **Tier 1** change still gets the named human's approval it requires, and a command in
  `.ai-sdlc/gates.txt` is still handed to a human.
- Anything **irreversible**, or a choice that is expensive to reverse (a stack, a data
  model, a hosting provider, a public commitment), still becomes an ADR, so it can be
  audited after the fact.
- When the agent cannot tell whether a choice reaches Tier 1, it treats it as Tier 1 and
  stops. "When in doubt, tier up" is not suspended by a style.
- A choice that needs facts the agent cannot verify (a price, a legal position, a
  version it could not check) is reported **Unknown** and goes to the person.

## 3. Autopilot, accountably

Every decision taken without asking is recorded where it can be found:

- The worklog entry says `(auto)` beside the decision, with the reason and the option
  that lost.
- A material choice gets its ADR in the same change, marked `Deciders: agent (autopilot)`
  and not approved by a person until one reads it. A Tier 1 ADR is never marked approved
  by the agent.
- The closing note ends with **Decisions you may want to review**: one line each, the
  choice, why, and what undoing it would cost.

The person can switch style at any time by saying so. The change applies from the next
decision and is recorded in the worklog.

## 4. Asking someone who is not a specialist

A question the person cannot answer is a failed question. In Ask and Guide:

1. **Say what is being decided in terms of the outcome**, not the mechanism: "where the
   customer list is stored, which affects how easy it is to move later", not "Postgres or
   MySQL".
2. **Recommend one option.** A menu of equals hands the work back to the person.
3. **State the consequence of each option in a sentence**: cost, speed, risk, how hard it
   is to undo. Not a feature list.
4. **Say what happens if they do not choose**: the default the agent will take and when.
5. **Do not ask what the repository, the charter, or an earlier decision already answers.**
6. Keep it to one decision per question. Batch only choices that depend on each other.
7. If they answer with something that looks like a secret or personal data, follow
   `12-sensitive-data-in-records.md`: do not repeat it.

A technical stack choice follows `13-stack-evaluation.md` in every style. Under Autopilot
it is the recommended option, recorded with its version facts.

## 5. Recording

The charter's **Decision style** row and `.ai-sdlc/profile.json` carry the project
default, and `sdlc.py doctor` fails when they disagree. A per-item override is written in
the plan's first line. The installer sets the default with `--decision-style
ask|guide|autopilot`, or by asking during guided setup.

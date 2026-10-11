# 13 — Stack evaluation

How a stack, runtime, database, framework, or other foundational choice is made: checked
against current facts, compared against alternatives, and recorded so a later reader can
tell what was known when it was chosen.

**Read this when** a project is choosing its stack, a change adds a runtime, database,
framework, language, hosting provider, or base image, or a change moves one across a major
version. Skip it for a bug fix inside the existing stack.

This document names no technology. The project's own choice lives in the charter's Stack
table, and everything below is about how to reach it.

---

## 1. Verify, do not recall

An agent's memory of "the current version" is a snapshot from training, and it favours
what was common then. Treat a recalled version, release date, or support date as a claim
without evidence (`06-evidence-and-claims.md`).

For every foundational choice, find these from the **official source** (the project's
release page, its registry entry, its lifecycle or support policy):

- the **latest stable** version, and its release date
- the version being **proposed**
- the date that version **stops receiving security fixes**
- anything the project's other dependencies require of it

Record each with the source and the date it was read. A fact that could not be checked
(no network, a page that would not load) is recorded **Unknown — not verified**, never
filled in from memory. Then the person is asked, or the choice waits.

## 2. Default stance

**Newest stable, supported version, unless there is a written reason otherwise.** The
reason is allowed to be good: a library the project needs does not support it yet, the
team's tooling does not, a hosting provider has not released it, the newest release is
recent enough that its first patch is not out. "It is what I usually use" is not a
reason, and neither is "newer is better".

Existing projects are not upgraded because a newer version exists. An upgrade is its own
work item with its own plan, migration review, and rollback. This document governs the
choice, not a standing duty to chase releases.

An option with no remaining support window is not a candidate for new work. Choosing one
anyway needs a named human's written acceptance of the risk.

## 3. Criteria

Compare the real candidates (two or three, plus "keep what is already here" when
something is) on what applies from this list. Every criterion either has a fact or is
marked Unknown.

| Criterion | The question |
| --- | --- |
| Fit | Does it meet the stated requirements and the charter's constraints, without bending either? |
| Support window | How long does it get security fixes, and does that outlast the project's expected life or the next planned upgrade? |
| Ecosystem | Are the libraries, drivers, and tools the project needs available for this version? |
| Operability | Can the team deploy, monitor, back up, and recover it, now, with the people it has? |
| Security record | Its history of vulnerabilities and how quickly they were fixed |
| Licence | Compatible with the project's use, now and if the project is distributed |
| Cost | Money, plus the effort to learn it and to leave it |
| Lock-in and reversibility | What would changing it later cost, and what would force that? |
| Evidence | A performance or scale claim counts only if it is **Measured** for a workload like this one |

## 4. The output

For a Tier 1 or Tier 2 choice, an ADR (`templates/adr.md`) carrying:

1. The candidates with a sentence of pros and a sentence of cons each, in plain language.
2. One **recommendation**, and the reason it beat the others.
3. The **Version facts** block filled in, with sources and dates.
4. If the recommendation is not the latest stable version, the written reason.

Who decides follows the decision style (`14-decision-style.md`): the person under Ask or
Guide, the agent under Autopilot (logged, marked unreviewed). A Tier 1 choice always has a
named human decider.

A Tier 3 change that touches no foundational choice does not run this process. A one-line
check that a new dependency's version is current and supported is enough for a small
addition.

## 5. Keeping it honest

- The ADR's **verified-on** date is part of the claim. Facts about versions go stale in
  months, so `sdlc.py doctor` warns when an ADR's Version facts has no verified-on date,
  when that date is older than the charter's staleness threshold, or when its recorded
  support-end date has passed.
- A superseded choice is superseded by a new ADR, never edited (`05-change-control.md`).
- If a later review finds a stack decision made from recall, rate it S3, and S2 when the
  chosen version is out of security support (`roles/architect.md`).

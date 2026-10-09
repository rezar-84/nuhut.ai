# 10 — More than one agent

For repositories where several agents work at once — parallel sessions, a team of
teammates, or one orchestrator fanning work out to subagents.

**Read this when** the charter's **Concurrency** row says more than one agent works here,
or when you are about to fan work out yourself. Skip it entirely otherwise; a single
agent working alone needs nothing in this document.

Everything in `AGENTS.md` and the rest of `process/` still applies to every agent
individually. This document covers only what changes when there is more than one.

---

## 1. Claiming

**One work item, one agent, one branch.** Two agents on one item is the characteristic
failure here, and it is dangerous precisely because it looks like progress: both produce
plausible work, both write a worklog entry, and the second merge silently reverts the
first.

Before starting, take the item: set the backlog row's **Owner** column to your agent
identity and its status to `In progress`, and commit that edit on its own. Taking an item
is a write, not an intention. If the row is already owned, pick another item — do not
"help".

- Release the claim when the item reaches `Done`, `Parked`, or `Deferred`.
- A claim older than the charter's staleness window with no branch activity is stale:
  say so, and re-claim deliberately rather than assuming abandonment.
- Never renumber, reorder, or reformat rows you do not own. A reformatting pass across
  the backlog conflicts with every agent holding a claim.

**One item, one working tree.** Parallel sessions on the same checkout overwrite each
other's files between one command and the next. Give each claimed item its own git
worktree: a separate checkout on its own branch, which shares the repository but not the
files. Split work by the files it touches, using the plan's "Files that change". Two items
that change the same files run one after the other, not side by side.

The limit on parallel sessions is how many the human can review properly, not how many the
machine can run. Add a session only while reviews are keeping up.

## 2. Single-writer files

These have one writer at a time regardless of who owns which item. Touching them means
taking a claim on them the same way:

- `project/charter.md` — the source of truth; two concurrent edits produce a charter that
  matches nobody's reality.
- Database migrations and their ordering.
- Dependency lockfiles and generated files.
- Anything the charter's **Managed platform** table marks platform-owned — that is
  single-writer *and* the writer is not you (`05-change-control.md`).

`project/worklog.md` is **append-only, newest first**. Re-read it immediately before
appending, and append your entry whole. Never edit or reflow another agent's entry, and
never interleave one into the middle.

## 3. Reviewing in parallel

Role reviews are the natural fan-out, and the strongest efficiency argument in this kit.
A reviewer needs one playbook and the diff — a few thousand tokens — not the whole
operating context. Six roles reviewed concurrently cost six small contexts instead of one
very large one.

**Each reviewer gets:** exactly one `roles/<role>.md`, the diff or artifact under review,
the charter rows that role's playbook names, the work item ID, its risk tier, and its
resolved effort mode. Nothing else. Do not assume a parent session's mode reaches a
subagent; pass it in the task packet.

**Each reviewer returns**, and nothing more:

1. Findings, each with a **location**, a **consequence**, and a **severity** from the
   ladder in `04-quality-gates.md`.
2. What it **checked and how**. A review that found nothing must say this, or it is
   worthless.
3. What it did **not** cover, and why. Never imply coverage you do not have.

**A reviewer does not decide the verdict, and may not waive its own blocker.** It rates;
the orchestrator maps severity to verdict per `02-role-reviews.md`; a human clears a
Block. An agent that both raises and dismisses a finding has reviewed nothing.

**The orchestrator** merges findings, de-duplicates the same defect found by several
roles at the highest severity any of them gave it, takes the most severe verdict as the
overall one, and records the whole set — including the reviews that passed. Dropping a
passing review loses the record of what was checked.

**Do not fan out the build.** Two agents editing the same change produce a merge nobody
reviewed. Parallelism belongs where the work is genuinely independent: separate work
items, or read-only reviews of one artifact.

## 4. Evidence across agents

A claim is only *Verified* by the agent that ran the command and read the output.
Everything an orchestrator relays from a subagent, and everything one agent reads from
another's worklog entry, is **Reported** — with the source named
(`06-evidence-and-claims.md`). Relaying a subagent's "tests pass" as *Verified* is a
fabrication, and it is the easiest one to commit by accident.

An orchestrator that needs *Verified* runs the command itself.

## 5. Handoff

An agent that stops — finished, parked, or out of context — leaves enough that the next
one does not re-derive it. In the worklog entry, or the backlog row for a park:

- What is done, what is verified, and with what result.
- What is in flight and where it stands: branch name, last commit, what is half-finished.
- What is blocked, on whom or what, and what was already tried.
- The decisions taken that are not obvious from the diff — those with durable
  consequences belong in an ADR, not only here.

A handoff that says "continued work on the feature" has handed off nothing.

## 6. What the charter must say

The **Concurrency** row records: how many agents work here, how a claim is taken and
released, which files are single-writer beyond the list above, and whether agents may
merge to the default branch or only open pull requests.

Blank means *Unknown*, and an agent must not assume it is working alone
(`06-evidence-and-claims.md`).

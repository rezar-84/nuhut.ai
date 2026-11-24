---
status: proposed
owner: rezar-84
last-reviewed: 2026-11-25
---

# ADR 0004: The kit records approvals; a system outside the agent's reach authenticates them

- **Status:** Proposed. It waits for rezar-84's decision, because it changes how Tier 1
  governance findings are handled (AGENTS.md §9).
- **Date:** 2026-11-25
- **Deciders:** rezar-84
- **Work item:** NUHT-049

## Context

Everything nuhut runs, including hooks, `finish`, `approve`, `rerate` and the ledger,
runs where the agent runs, with the agent's file and shell access. Since v6 the kit has
added one gate after another against forged records:

- approvals read from GitHub reviews (NUHT-024);
- local approvals that a terminal must start and that stop counting after any
  non-bookkeeping change (NUHT-043);
- blind re-ratings before an agent may lower a severity (NUHT-041);
- trusted records read from the default branch.

Every ship review since then has blocked on the same kind of finding:

- "a pseudo-terminal is not human authentication";
- "local approvals are editable shard fields";
- "`independent: yes` is self-asserted".

Reviews: NUHT-041, 043 and 044, two rounds each. These findings are correct, and no
change inside the agent's environment can fix them: a process that can write the repo
and open a pty can produce every signal the kit checks. Asking for signed approvals
(NUHT-045) and a pre-receive hook (NUHT-039) means building gates on top of the gates.
Meanwhile 14 of 17 Tier 1 items are open and 14 escalations are undecided.

Systems that do solve this put the trust somewhere the agent can't reach:

- **The git host.** Branch protection with required reviews by people other than the
  PR author, and required status checks (GitHub, GitLab, Gitea and Forgejo all offer it).
- **An orchestrator that runs agents elsewhere.** The agent works in a sandbox with no
  credentials for the repo, its verification runs in CI or a separate sandbox, and
  approvals are recorded by an authenticated person in a system the agent can't write.
  The kit does not depend on, or name, any particular orchestrator.

## Decision

1. **The kit records intent; it does not prove identity.** A local approval, a waiver,
   a re-rating and a review file record who says they decided what, and when. They are
   evidence for an honest team and an audit trail. They are not authentication, and the
   docs say so wherever they are described.
2. **Authentication comes from a system the agent can't write to:**
   - for a repo on GitHub, branch protection on the default branch, with required
     reviews and the kit's CI check (`ci-check`) as a required status;
   - for teams whose agents run under an orchestrator outside the developer's machine,
     that orchestrator's gates, which approve through the git host.

   `doctor` already reports when enforcement depends on the host. That line becomes the
   documented answer to "can an agent forge this?".
3. **Review findings of this class are declined by reference to this ADR**, not
   escalated again. A reviewer that reports "X can be forged from the agent's session"
   gets the response `Declined — ADR 0004`, unless the finding shows the kit claiming
   more than item 1 allows. That remains a real defect: fix the claim or the docs.
4. **No new in-environment authentication gates.** NUHT-045 (signed approvals) and
   NUHT-039 (pre-receive hook) close as outside the kit's scope. For teams that
   need more, the kit may later offer a documented hand-off contract that any external
   orchestrator can implement: item IDs supplied from outside, approvals counted only from
   the git host, and no approval records written from inside the agent's environment.
   The contract stays generic; the kit ships no integration with a specific product.

## Consequences

- Tier 1 items can close once a person decides the remaining escalations in one sitting,
  most of them declined under item 3.
- Local approvals stay opt-in and unsigned. Solo projects keep them, and team projects
  rely on GitHub reviews.
- Security reviews keep their value for claims the kit makes. They stop producing a new
  round of gates for a threat the kit has said it does not cover.
- The README and AGENTS.md need a short "what the kit enforces and what it records"
  table. Each claim is marked enforced by a hook, by CI, by the host, or advice only.
- Risk: a team that skips branch protection gets no authentication at all. `doctor`
  keeps reporting it, and `status` should show it as missing setup on a project with
  Tier 1 items.

## Alternatives considered

- **Signed approvals (NUHT-045).** A person signs a statement with an SSH or GPG key and
  the kit verifies the signature. The agent can't use a key it can't read, but on a
  developer machine it usually can: the ssh-agent and the key files are in its
  environment. It moves the problem rather than solving it, and costs key management.
- **A pre-receive hook (NUHT-039).** Only works on self-hosted git, and it is enforcement
  on the server, which is decision 2 anyway.
- **Keep escalating each finding.** That is the current state, and it blocks every Tier 1
  item.

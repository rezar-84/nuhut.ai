---
status: draft
owner: product-manager
last-reviewed: YYYY-MM-DD
---

# User stories & acceptance criteria — {{PROJECT_NAME}}

> The contract between "what was asked for" and "what QA verifies". A story without
> testable acceptance criteria cannot enter BUILD (`../process/03-ready-and-done.md`).

## Format

**{{PREFIX}}-###** — As a _(audience)_, I want to _(do something)_, so that _(outcome)_.

**Acceptance criteria** — observable, each independently checkable:

- **Given** _(starting state)_ **when** _(action)_ **then** _(observable result)_

**Must not** — the refusals. Required for anything touching permissions, money, or data:

- **Given** _(state)_ **when** _(action)_ **then** _(it is refused, and how the user is
  told)_

**Edge cases** — empty, maximum, concurrent, expired, offline, unauthorised, malformed.

---

## Example — the level of specificity expected

**{{PREFIX}}-042** — As an account owner, I want to remove a team member, so that
someone who has left cannot see our data.

**Acceptance criteria**
- Given I am an owner viewing the team list, when I remove a member, then they no longer
  appear in the list and I see confirmation naming who was removed.
- Given a member has been removed, when they load any page in the workspace, then they
  are denied and told their access was removed — not shown an empty workspace.
- Given a member has been removed, when they use a session token issued before removal,
  then it is rejected.

**Must not**
- Given I am a member (not owner), when I attempt removal by any route including a direct
  request, then it is refused with no change of state.
- Given I am the only owner, when I attempt to remove myself, then it is refused with an
  explanation.

**Edge cases**
- The member is removed while they have unsaved work open.
- Two owners remove the same member simultaneously.
- The member is removed while a long-running export they started is in flight.

> Note what the example does: the *must not* cases are as specific as the *must* cases,
> and the failure states say what the user is told. "The user can be removed" would have
> passed a careless review and shipped a data leak.

---

## Stories

_(Grouped by audience or by journey. Prioritised. Each with an ID matching the backlog.)_

### <Journey or audience>

**{{PREFIX}}-###** — As a …, I want to …, so that …

- **Given** … **when** … **then** …

**Must not**
- …

**Edge cases**
- …

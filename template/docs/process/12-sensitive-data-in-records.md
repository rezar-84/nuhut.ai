# 12 — Sensitive data in records

What may be written into the backlog, charter, ADRs, reviews, plans, worklog, and every
other file a project commits. Those files are version-controlled, often shared, and
permanent: a value written once survives in history after the line is deleted.

**Read this when** a person answers a question with something that looks like a credential
or personal data, when a record is about to quote a user, or when a guard or `sdlc.py
doctor` reports a sensitive value. Skip it otherwise.

---

## 1. The rule

**Record the decision and the reason. Never record the value, and never record a person's
raw words.**

- Refer to a secret by what it is and where it lives: "the Stripe key in the secret store
  the charter names". Never by its value, a prefix of it, or its last characters.
- Refer to a person by role or by the ID the project already uses, not by a name, email,
  phone number, or address, unless the record's purpose is that identity and the charter
  says it may be kept there.
- Summarise an answer; do not paste it. "Owner confirmed the launch date moves to June" is
  a record. The owner's message, verbatim, is a copy of data nobody reviewed.
- Use obviously fake values in examples and fixtures: `user@example.com`,
  `postgres://user:PASSWORD@db.example.com/app`, `EXAMPLE` in a line the guards should
  skip.

## 2. What goes where

| Record | May hold | Must not hold |
| --- | --- | --- |
| Backlog, plans | IDs, scope, acceptance criteria, decisions and reasons | A customer's name or message, a credential, a link carrying a token |
| Charter | Stack, commands, environment *names*, where each secret is stored | A secret, a connection string with a password, a personal address |
| ADRs | Context, decision, alternatives, consequences | Real user data used as an example |
| Reviews, worklog | Findings, commands run, results, the kind of data exposed | The exposed value, a captured log containing one, a session token |
| Verification output | Pass/fail, counts | Output that echoes a credential or a record of personal data |

## 3. When someone pastes a secret or personal data into the chat

1. **Do not repeat it** in your reply, a file, a commit message, a branch name, or a
   command line.
2. Say what you saw, by kind: "that looks like a live API key".
3. Tell the person to rotate it if it was real. It is already outside their control: it is
   in this conversation's transcript.
4. Ask where the project keeps secrets, and use that. If it is a placeholder, say so and
   carry on.
5. If the value is needed to do the work, ask for it to be supplied through the
   environment or secret store, not through a message.

## 4. When a value has already been written to a file

A leak that has reached a committed file, or may have, is an S0 under
`04-quality-gates.md`. Deleting the line does not undo it.

1. Stop writing. Do not copy the value anywhere else, including the worklog.
2. Tell the human, by kind and location, never by value.
3. **Rotate or revoke it.** Removal without rotation is not a fix.
4. If it was pushed, history rewriting is a human decision with its own approval
   (`05-change-control.md`), and still does not replace rotation.
5. Record the incident: what kind, where, when found, what was rotated. Not the value.

## 5. What guards this, and what they cannot see

| Guard | Does | Cannot |
| --- | --- | --- |
| This rule | Tells the agent what not to write | Stop an agent that ignores it |
| `doc-leak-guard.sh` (opt-in hook) | Denies a write containing a credential shape; warns on personal-data shapes in records | See a value that matches no pattern, or a write made through a shell command |
| `secret-guard.sh` (opt-in hook) | Denies a commit whose staged additions hold a credential shape | Catch a value that does not match a known shape |
| `sdlc.py doctor` | Reports credential and personal-data shapes already in the docs, by kind and file, never value | Prove a file is clean |
| `checks.scan` in CI | Scans the repository, history included, with the project's own scanner | Undo a leak |

The hooks are Claude Code only. On another agent tool, the rule and `doctor` are what is
left, so run `doctor` before every commit that touches a record. None of this replaces a
dedicated secret scanner in CI. A pattern list is a guard rail for an agent trying to
comply, not a proof of absence.

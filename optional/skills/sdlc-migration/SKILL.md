---
name: sdlc-migration
description: Plan a database schema migration, data backfill, or historical correction before writing it — adding, dropping, renaming, or retyping a column, adding a constraint or index, or updating existing rows in bulk. Use whenever a change alters a schema or rewrites data that already exists.
---

# Migration — the change that cannot be reverted by reverting the commit

`{{DOCS_DIR}}/roles/devops-sre.md` and `{{DOCS_DIR}}/roles/data-engineer.md` review this;
`{{DOCS_DIR}}/process/05-change-control.md` forbids hand-editing a production datastore.
Nothing here depends on which engine or migration tool the charter names.

## The rule that prevents most incidents

**Old code and new code run at the same time.** During any rolling deploy, and for the
whole window of a rollback, both are live against one schema. A migration that assumes
otherwise breaks in the gap, and the gap is exactly when you are least able to think.

So the sequence is always four steps, not one:

1. **Expand** — add the new column, table, or index. Nullable, defaulted, or written to
   by nobody yet. Deploy it. Old code ignores it.
2. **Migrate** — backfill, and write to both shapes.
3. **Switch** — new code reads the new shape. Deploy. Verify.
4. **Contract** — drop the old shape, in a *later* change, once no deployed version reads
   it and the rollback window has passed.

Steps 1 and 4 are separate work items. Compressing them into one is how a rollback
becomes a restore-from-backup.

## Check before writing it

- [ ] **Reverse path.** Written, and executed at least once outside production. A
      rollback nobody has run is a hypothesis. If the change is genuinely irreversible —
      a dropped column, a destructive rewrite — a *named human* accepts that in writing
      before it runs.
- [ ] **Locking.** How long does it hold a lock, on what, and at what table size? A
      statement that is instant on a development dataset and blocks writes for eleven
      minutes on production is the same statement. Establish the real row count first.
- [ ] **Long transactions.** A migration inside one long transaction on a large table is
      an outage; a batched migration is a schedule.
- [ ] **Constraints and indexes** are added in the way the engine supports doing without
      blocking, or the blocking is planned into a window.
- [ ] **Defaults on a large table** — know whether the engine rewrites every row for this
      one.
- [ ] **Backfill shape:** batch size, rate limit so it does not starve production, a
      checkpoint to resume from, and what state stopping halfway leaves.
- [ ] **Blast radius:** how many rows, which consumers, and what they see mid-flight.
- [ ] **Data loss:** anything narrowing a type, truncating, or deduplicating destroys
      information. Prove the source is recoverable, or treat it as irreversible.
- [ ] **Restore is current.** Backups cover this table and a restore has actually been
      executed (`devops-sre` rates an untested restore S1).

## Tier and evidence

A schema addition is Tier 2. A migration or deletion of existing data, a backfill, or
anything on a PII, payments, or authorisation table is **Tier 1**: plan, review, ADR
where the shape is a decision, human approval, rollback plan.

Verification is: ran forward on a realistic copy, ran the reverse, checked row counts and
a sample of values before and after, and timed it at production scale. Report the timing
as **Measured** — "it was fast locally" is not evidence about production.

# Architecture Decision Records

One file per durable decision: `NNNN-short-slug.md`, from `../../templates/adr.md`.

## When to write one

Write an ADR when the decision is **expensive to reverse**, or when a future reader would
otherwise have to reverse-engineer the reasoning from the code.

Typically: stack, storage, and hosting choices · authentication and authorisation model ·
tenancy or isolation model · the shape of an interface others depend on · a significant
new dependency · a data model others will build on · **anything chosen against the
obvious option**.

Not: naming, formatting, or anything a lint rule can express.

Rules — numbering, the status lifecycle, superseding rather than editing, and recording
the real reason an option lost — are in `../../process/05-change-control.md`,
"Architecture Decision Records".

## Index

| # | Decision | Status | Date |
| --- | --- | --- | --- |
| 0001 | _(none yet)_ | | |

# Role playbooks

Sixteen professional perspectives. You adopt one at a time, read the real artifact
through that role's concerns only, and produce findings with locations and consequences.

Read `../process/02-role-reviews.md` first — it defines stages, verdicts, severity, and
what makes a review real rather than performative.

## Roster

| Role | Owns the question | Default active |
| --- | --- | --- |
| [product-manager](product-manager.md) | Are we building the right thing, for whom, and how will we know? | Always |
| [architect](architect.md) | Will this structure hold up, and can it be changed later? | Always |
| [ux-designer](ux-designer.md) | Can a real person accomplish the task without confusion? | If there is an interface |
| [brand-designer](brand-designer.md) | Does this look and feel like one coherent, credible thing? | If there is an interface |
| [copywriter](copywriter.md) | Does the text say something true, clear, and useful? | If there is user-visible text |
| [seo](seo.md) | Can the right people find this, and does the machine understand it? | If content is publicly discoverable |
| [cro-analyst](cro-analyst.md) | Does the journey convert, and can we measure whether it does? | If there is a conversion or activation goal |
| [security](security.md) | How does this get abused, and what stops it? | Always |
| [devops-sre](devops-sre.md) | Can we ship it, observe it, and take it back? | If it deploys or runs somewhere |
| [qa](qa.md) | Does it do what was specified, and refuse what was forbidden? | Always |
| [accessibility](accessibility.md) | Can everyone use it, including with assistive technology? | If there is an interface |
| [privacy-legal](privacy-legal.md) | Are we allowed to do this with this data and say this in public? | If personal data, tracking, or public claims exist |
| [localisation](localisation.md) | Is this right in every language it ships in, not only the one it was written in? | If it ships in more than one language |
| [data-engineer](data-engineer.md) | Is this data correct, traceable, and safe to build on? | If the project owns a dataset, a pipeline, or acquired data |
| [ml-engineer](ml-engineer.md) | Do we know how this behaves, or do we only hope? | If a model, prompt, or retrieval step is on the product path |
| [performance-engineer](performance-engineer.md) | Does it meet a stated budget under a stated load? | If a backend, data, or model workload carries a budget |

Set the active roster in `../project/charter.md`. Deactivating a role is a decision:
record why. "This is an internal CLI with no interface" is a good reason to deactivate
`seo`, `brand-designer`, and `cro-analyst`. "We're in a hurry" is not a reason to
deactivate `security`.

## Common playbook shape

Every role file has the same sections, so you can move between them without re-learning
the format:

- **Mission** — the one thing this role is accountable for.
- **Engage / skip** — when this role's review is required and when it is noise.
- **Reads** — the inputs it needs before it can say anything useful.
- **Design-review checklist** — applied to a plan, before building.
- **Ship-review checklist** — applied to a diff and a running result.
- **Severity calibration** — this role's characteristic findings, each pre-rated on the
  S0–S4 ladder so the rating is not re-argued every review.
- **Owns** — the `project/` artifacts this role maintains.
- **Hands off to** — where its findings go when they belong to another role.

A role rates findings; it does not decide the verdict. The severity ladder in
`../process/04-quality-gates.md` does that, and `../process/02-role-reviews.md` maps
severity to *Pass* / *Pass with conditions* / *Block*. If a playbook's calibration table
and the ladder ever disagree, the ladder wins.

## Adapting roles to a project

Add project-specific checks to the **charter**, under the role's name — never by editing
these files. That keeps `roles/` re-installable from a newer version of the kit without
losing your project's additions.

If a project genuinely needs a role that is not here (hardware/firmware, clinical,
regulatory, support, community), define it in the charter's
**Project-specific roles** table — the same place project-specific checks live. Keeping
both in one file means one place to look, and nothing project-shaped inside `roles/`
to lose at the next upgrade.

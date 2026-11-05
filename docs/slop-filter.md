# Slop filter

An opt-in writing standard: copy that does not read as machine-written.

Readers discount text the moment it sounds generated, and an agent left alone produces the
same handful of phrasings every time. The slop filter names those phrasings, finds them
mechanically where it can, and has the agent rewrite them as plain statements of the same
facts. It has three parts:

| Part | What it is |
| --- | --- |
| `sdlc.py slop` | A scanner. Lists each tell by file and line with a fix. Standard library only, no model call. |
| `sdlc-slop-filter` | A skill. The agent loads it when it writes or reviews copy, and applies the judgment the scanner cannot. |
| `/sdlc-slop` | A slash command that runs both on a file, a directory, or pasted text. |

## Modes

One row in the charter, **Slop filter**, under Risk defaults.

| Mode | Applies to | `sdlc.py slop` |
| --- | --- | --- |
| `off` (default) | nothing, unless you ask | advisory when run by hand |
| `on` | public and user-facing copy | lists findings, exits 0 |
| `strict` | all prose the agent writes: copy, docs, records, commit and PR text | exits 1 when a file fails |

A file fails when it has one strong tell, or more moderate tells than its length allows
(two, plus one per 400 words). Weak tells are reported when dense and never fail a file.

## Setting it

**During install**

```sh
./install.sh my-project ACME --slop-filter strict
```

The guided setup asks the same question in the Process section. `on` and `strict` install
the skill.

**After install**

```sh
python3 .ai-sdlc/bin/sdlc.py config --slop-filter strict     # set the charter row
./install.sh my-project --upgrade                            # add the skill the row calls for
```

`./install.sh my-project --upgrade --slop-filter strict` does both in one step.

**For one run**

```sh
python3 .ai-sdlc/bin/sdlc.py slop --strict content/
```

or `/sdlc-slop strict content/` in Claude Code. `--strict` applies strict rules whatever
the charter says.

## The scanner

```sh
python3 .ai-sdlc/bin/sdlc.py slop                  # prose files changed against HEAD
python3 .ai-sdlc/bin/sdlc.py slop README.md docs/  # named files and directories
python3 .ai-sdlc/bin/sdlc.py slop - < draft.md     # standard input
python3 .ai-sdlc/bin/sdlc.py slop --guide          # the rules
python3 .ai-sdlc/bin/sdlc.py slop --json docs/     # for a script
```

It reads `.md`, `.mdx`, `.txt`, `.rst` and `.html` files. It skips front matter, code
blocks, inline code, link targets, HTML comments and quoted lines. To keep a line it flags,
put `slop-ok` in a comment on that line. To exempt a file that quotes tells on purpose, put
`<!-- slop-filter: off -->` near its top.

In CI, strict mode is one line:

```sh
python3 .ai-sdlc/bin/sdlc.py slop --strict content/ docs/
```

## What it looks for

| Strength | Examples |
| --- | --- |
| Strong | chatbot leftovers and unfilled placeholders; `not just X, but Y`; signposting such as `it's important to note`; inflated significance; `experts agree` with no expert; stock sales lines |
| Moderate | stock vocabulary (`delve`, `pivotal`, `seamless`); `serves as` for `is`; a participle tacked on after a comma; `Additionally,` at the start of a sentence |
| Weak | em dashes, groups of three, `rather than`, curly quotes, title-case headings, bold-label lists |

## What it is not

It is not an AI detector. Every pattern here also appears in human writing, and Wikipedia's
page says plainly that single signs are weak evidence. A match shows where a sentence can be
made plainer. It says nothing about who wrote it, and the skill tells the agent not to
claim otherwise. The word lists are English; in other languages only the structural rules
apply.

There is no hook that blocks a write on a finding. The kit's hooks are limited to rules
with no false alarms, and this one has some.

## Sources

- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing),
  by WikiProject AI Cleanup, CC BY-SA 4.0. The pattern catalogue and its caveats about
  unreliable signs come from here, restated in this kit's words.
- [blader/humanizer](https://github.com/blader/humanizer), MIT. The idea of strength tiers,
  of a voice sample outranking the patterns, and of never adding or losing a claim.
- [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop), MIT. The short
  quick-check form.

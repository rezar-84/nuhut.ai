# Claude Code: examples to adapt, not install

Nothing here is installed by `install.sh`. These are starting points for the parts of an
agent's setup that depend on the harness, and on how much a project trusts its agent. Copy
what fits into the project's own `.claude/`, and review it like any other change to the
agent's configuration (`process/04-quality-gates.md`, "Evaluating the agent's own setup").

| File | What it is for |
| --- | --- |
| `settings.example.json` | Keep secrets out of the agent's reach, pre-approve the charter's check commands so they do not prompt, and turn the sandbox on. |
| `agents/verifier.md` | A subagent that runs the checks and reports against the plan in a fresh context. It never fixes anything, so its verdict is not shaped by the assumptions that produced the code. |

## `settings.example.json`, line by line

- **`permissions.deny`** keeps secret files out of the agent's tools (`.env*`, key
  material, cloud credentials) and blocks arbitrary network fetches.
- **`permissions.allow`** pre-approves the check commands, so a deny list does not turn
  into a prompt for every test run. Replace the placeholders with the charter's `checks.*`
  commands.
- **`sandbox`** covers what tool rules cannot. A deny on the Read tool does not stop
  `cat .env` in a shell; the operating-system sandbox does. `failIfUnavailable` makes it a
  gate rather than a wish.
- The file is **JSON, so it has no comments**. This README is the explanation.

Merge it by hand into an existing `.claude/settings.json`. Never let a script overwrite
that file: it usually holds permissions somebody tuned. Check the current key names in
the Claude Code settings reference before relying on them, because the harness evolves
faster than this kit.

Every deny rule trades away some capability. Start strict on repositories that hold
personal or financial data, and loosen one rule at a time when a real task needs it.

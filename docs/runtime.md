# The runtime: sdlc.py

The mechanical half of the process, and the viewer.

## Scripts for what does not need judgment

A rule written as prose is a request the agent may or may not honour. The same rule as a
check either passes or fails. So the parts of the process a machine can decide are a
script, not a paragraph. Every install gets
`.ai-sdlc/bin/sdlc.py`: standard-library Python, kit-managed, and refreshed by `--upgrade`.

```sh
python3 .ai-sdlc/bin/sdlc.py doctor --strict          # audit the records; exit 1 on a failure (CI)
python3 .ai-sdlc/bin/sdlc.py verify --parallel        # run the charter's checks, keep the evidence
python3 .ai-sdlc/bin/sdlc.py bite npm test            # do the tests fail without the change?
python3 .ai-sdlc/bin/sdlc.py plan-check ACME-12       # does the diff match the plan?
python3 .ai-sdlc/bin/sdlc.py view --serve             # the project as one live page
python3 .ai-sdlc/bin/sdlc.py lens --area security     # stack, build errors, security, deploy, env, agents
python3 .ai-sdlc/bin/sdlc.py audit                    # vulnerable packages, from the project's scanner
python3 .ai-sdlc/bin/sdlc.py claim ACME-12            # take an item: claim, branch, own worktree
python3 .ai-sdlc/bin/sdlc.py parallel                 # which Ready items can run side by side
python3 .ai-sdlc/bin/sdlc.py dispatch --workers 2 --by claude   # run Ready waves across isolated worktrees
python3 .ai-sdlc/bin/sdlc.py item list --json         # query sharded items/<ID>.json records
python3 .ai-sdlc/bin/sdlc.py review ACME-12 --role security --by codex   # independent review
python3 .ai-sdlc/bin/sdlc.py spec apply ACME-12 --write                  # merge a spec change on close
python3 .ai-sdlc/bin/sdlc.py log --since main --write # worklog lines from commits and verify runs
python3 .ai-sdlc/bin/sdlc.py config --token-saving on # Lean effort, single-agent review, compact budgets
```


Every command, its flags and its exit codes: [command reference](cli.md). Every runtime
inspection and mutation command supports `--json` for machine orchestration, and `doctor`
caches results in `.ai-sdlc/cache/doctor.json` keyed by repository state so warm checks stay
fast on large repositories. Each command also explains itself:
`python3 .ai-sdlc/bin/sdlc.py <command> -h`.

**Evidence.** `verify` and `bite` record one JSON line per stage in sharded ledger files
under `docs/project/ledger/<run>.jsonl` (or `docs/project/evidence-ledger.jsonl` on
unmigrated 4.x installs): commit, whether the tree was dirty, stage, command, exit code,
output hash and time. The raw logs stay in the git-ignored evidence folder; the ledger
shards are committed without cross-branch merge conflicts, so a reviewer or CI can check a
claim against them. The doctor flags a worklog entry that says *Verified* when the ledger
has no run for that item's change, and fails a built Tier 1 item without a review from a
model family other than the author's.

`verify` exists so a "Verified" claim can cite a file the script wrote instead of the
agent's memory of a run. `/sdlc-doctor` and `/sdlc-verify` call the script first and keep
the judgment for themselves: severity, behavioural checks, and what to fix first. It works
with any agent tool that can run `python3`. `/sdlc-review` opens every Tier 1 ship review
with `plan-check`, so a diff that drifted from its approved plan is visible before any role
reads it.

## The viewer

`sdlc.py view` draws the records, the git history and the project's stack as one page, and
`--serve` keeps it live while agents work. Everything about it (the views, the side panel,
keyboard shortcuts, live versus static, and what it never does) is in
[the viewer](viewer.md).

## Enforcement

The opt-in `--hooks` go one step further for Claude Code. They deny the tool call itself:

- a commit with no work item ID, or with a credential in it
- a file write containing a credential, with a warning when personal data is written to a record
- an edit to a single-writer path
- an edit to a reproducing test locked while its defect is fixed
- a command, such as a production deploy, that `.ai-sdlc/gates.txt` says a human must pass

A skill makes a violation rare, and a hook makes it close to impossible. See
`optional/hooks/README.md` for what each hook can and cannot see. Every hook delegates to
`.ai-sdlc/bin/hooks.py` (standard-library Python, no `jq` or platform `sed` dependency,
fail-closed on secret/gate/lock checks, worktree and symlink aware). With `--harness gemini`
the same rules (including the finish guard) are registered in `.gemini/settings.json`, and
with `--harness cursor` the shell rules are registered in `.cursor/hooks.json`.

The opt-in `--git-hooks` cover the two commit-time rules for **every** agent and every
human, because git runs them, not the harness: a `pre-commit` that refuses staged
credentials and a `commit-msg` that refuses a message with no work item ID
(`--git-hooks secrets` installs only the first). The scripts live in
`.ai-sdlc/git-hooks/`; the project's existing hook, husky file or `core.hooksPath`
directory gets one line appended and is otherwise left alone, and with pre-commit.com
or lefthook the entry to add is printed instead. `git commit --no-verify` bypasses them,
deliberately and visibly. The enforcement nobody can skip is CI: `--scaffold-ci` puts
`sdlc.py doctor --strict` before the quality commands.

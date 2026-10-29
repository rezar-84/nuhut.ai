# Troubleshooting and FAQ

## Questions

**Does it work with my stack?**
Yes. Nothing in the process names a framework, language or host. The charter records
yours, and the check commands are whatever your project already runs. Detection fills in
what it can for Node, Deno, Python, Go, Rust, Ruby, PHP, Java (Maven, Gradle) and .NET
projects. The rest is a
charter row you type.

**Does it slow the agent down or cost more tokens?**
Some, by design, scaled by risk. A Tier 3 change reads about 1,500 words. Tier 1 reads the
full process for that surface. *Lean* effort and token-saving mode
(`sdlc.py config --token-saving on`) cut it further. The 3.5.0 benchmark found the kit
changed behaviour usefully (tests always ran, bugs got a failing test first, work was
traceable). It also cost about five times the tokens, with no measured correctness gain on
a strong model. 4.x has not been re-measured yet. See the status note in the README.

**Do I need Claude Code?**
No. `AGENTS.md` is the contract, and most agent tools read it. Claude Code gets typed
`/sdlc-*` commands. Tools whose `/` menu lists skills get the same loop as skills, and the
runtime works from any terminal.

**Will it overwrite my files?**
Never on install. `--upgrade` replaces only the kit's own files that you have not changed
(tracked by hash in `.ai-sdlc/manifest.json`), backs up what it changes, and never
rewrites project records.

**Can I use it with Spec Kit or OpenSpec?**
Yes. Nuhut governs how each change is made and proven. Its opt-in living specs use
OpenSpec's headings and read existing `openspec/` and Spec Kit folders as they are
([specs](specs.md)).

**Is the viewer safe to leave running?**
It serves only on 127.0.0.1 and refuses other hosts. Every action needs a session token.
It never reads secret values, and keeps user-level items off exported pages. See
[what it never does](viewer.md#what-it-never-does).

## Problems

**`view --serve`: "ports 8765-8774 are all in use"**
Another viewer is still running, or something else holds the port. Use `--port 0` for any
free port, or `--port 9000`.

**The viewer says "Disconnected"**
The local server stopped (closed terminal, Ctrl+C, reboot). Start it again with
`python3 .ai-sdlc/bin/sdlc.py view --serve`. The page reconnects by itself.

**`doctor` is slow on a big repository**
It reads every record and walks git history for traceability. Several seconds on
thousands of commits is expected. The viewer reuses its result instead of running it
again on every refresh.

**`audit`: "is not a scanner this command can read"**
`audit` runs the charter's `checks.scan` command in JSON form, and knows npm, pnpm and yarn
audit, pip-audit, osv-scanner, cargo audit and govulncheck. Set one:
`sdlc.py config --set-check scan='npm audit --audit-level=high'`. The scanner itself
needs network access; the kit does not.

**`claim`: "already claimed by …"**
Another agent holds the item. `sdlc.py claims` shows who and since when. Pick another item
(`sdlc.py parallel`). If the claim is stale, re-claim it deliberately, after
`sdlc.py release <ID>`.

**`claim --mark`: "only the main worktree may do"**
Backlog edits from several worktrees conflict at merge. Run `--mark` from the main
checkout, or leave the row alone: the claim itself is what other agents check.

**`release --remove-worktree`: "has uncommitted changes"**
Commit or stash the work in that worktree first. The kit never deletes uncommitted work.

**`spec apply`: "… not found" or "found 2 times"**
A MODIFIED or REMOVED requirement must match an existing requirement's name exactly, and
the name must be unique in that capability. Fix the change file and run it again. Nothing
was written.

**A hook refused my commit**
The message names the rule: a commit with no work item ID, a credential in the diff, an
edit to a locked test or a single-writer file, or a gated command. Fix the cause. For a
deliberate exception, `git commit --no-verify` bypasses git hooks visibly. CI still runs
`doctor --strict`.

**The arrow-key menus misbehave in my terminal**
Use `./install.sh --plain` (or `NUHUT_PLAIN=1`) for numbered, typed prompts. It is also the
better choice for screen readers and logs.

**Board shows many items under "Other"**
Their status is one the board has no column for. Common words (Planned, Pending, Completed,
On hold, Cancelled …) are mapped automatically. The note above the board names the rest;
use the kit's statuses for those rows.

**Something else**
Run `python3 .ai-sdlc/bin/sdlc.py doctor` and `python3 .ai-sdlc/bin/sdlc.py fix all`
(safe repairs only), and check `--help` on the command involved. Then open an issue with
the output.

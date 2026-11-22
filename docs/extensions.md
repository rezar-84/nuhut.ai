# Extensions

An extension is a directory with a `nuhut-extension.json` manifest. It can add agent tool
records, presets, skills, roles, template overlays, hook rules, doctor checks and
lifecycle hooks without a fork of the kit. The format and the reasons behind it are in
ADR 0003 (`handbook/project/adr/0003-extension-system.md` in the kit repository).

There are two kinds:

- **Built-in** extensions (`core`, `claude`, `codex`, `gemini`, `cursor`, `opencode`,
  `kiro`, `acp`, `github-issues`) live in
  `.ai-sdlc/extensions/`. They are kit-managed files and `install.sh --upgrade` refreshes
  them.
- **Project** extensions live in `.ai-sdlc/local/extensions/<id>/`. Only `sdlc.py ext`
  writes there. An upgrade never touches them, and the hooks deny an agent's edits to
  them.

## Install one

```sh
python3 .ai-sdlc/bin/sdlc.py ext search lint                  # read the catalog
python3 .ai-sdlc/bin/sdlc.py ext add https://github.com/<owner>/<repo>.git --ref v1.0.0
python3 .ai-sdlc/bin/sdlc.py ext add ../my-extension           # a local directory
python3 .ai-sdlc/bin/sdlc.py ext list
```

`ext add` accepts an `https://`, `ssh://` or `git@host:path` git URL, or a local
directory. It refuses `file://` URLs, git transports such as `ext::`, and anything that
starts with `-`. A git source is cloned with
`git -c protocol.ext.allow=never -c protocol.file.allow=user clone --depth 1
--no-recurse-submodules -- <url> <tmp>`, run without a shell. `--ref` is resolved to a
commit and recorded.

Before it writes anything, `ext add` checks the manifest and prints what the extension
brings:

- its id and version;
- its data records (harnesses, presets, overlays, skill and role directories);
- every executable entry point, with its path or command.

It refuses a manifest path that is absolute or uses `..`, and any file or symlink that
resolves outside the extension directory.

Each install is recorded in `.ai-sdlc/manifest.json` under `extensions`, apart from the
kit's own files:

```json
"extensions": {"lint-pack": {"source": "https://...", "ref": "v1.0.0",
  "commit": "<sha>", "version": "1.0.0", "files": {"rules/no_curl.py": "<sha256>"}}}
```

## Let its code run

Some contributions are executable: agent `review` and `build` argv, `checks` commands,
`hook_rules`, `doctor`, `commands` and `lifecycle` entry points. A project extension's
executable contributions stay off until the charter's **Extensions allowed** row lists
its id:

```sh
python3 .ai-sdlc/bin/sdlc.py config --allow-extension lint-pack
```

The row is read from the default branch, so the change takes effect once it is merged.
Code also loads only while each file's sha256 matches the hash `ext add` pinned, both in
the working tree's `.ai-sdlc/manifest.json` and in that file on the default branch: a
branch that changes the code and its pin together runs nothing new until it merges. A
file edited by hand is refused, with a message that names it and `sdlc.py ext update <id>`.

`ext list` shows a STATUS for each extension:

| Status | Meaning |
| --- | --- |
| `data` | No executable contributions |
| `code-enabled` | Built-in, or listed in **Extensions allowed** with its files unchanged |
| `code-blocked` | Has executable contributions that are not allowed to run |
| `version-refused` | Its `nuhut` range or `schema` does not fit this kit |
| `invalid` | The manifest is broken; `doctor` names the file and field |

`ext list` also labels every skill and role directory with the extension it came from,
and prints every command and code file a non-built-in extension contributes. `doctor`
warns once for each blocked extension and lists the commands of each enabled one.

### When an allowed extension breaks

When an allowed extension's hook rule cannot load (a changed file, a syntax error, no
`evaluate` function), it fails closed:

- its rules are skipped;
- one warning per process names the extension;
- only the tool calls its rules would have judged are denied.

Other tool calls run normally. To recover, run `ext update <id>`, restore the file, or
run `ext remove <id>`.

## Update and remove

```sh
python3 .ai-sdlc/bin/sdlc.py ext update lint-pack --dry-run   # what would change
python3 .ai-sdlc/bin/sdlc.py ext update lint-pack             # asks before new code runs
python3 .ai-sdlc/bin/sdlc.py ext remove lint-pack
```

`ext update` fetches the recorded source and ref again. It prints the old and new commit
and every added, changed or removed file before it writes, marking the files that run
`(executable)`. When one of those changed and **Extensions allowed** lists the id, the
new code would run on the next call, so it asks first in a terminal and, without one,
refuses unless you pass `--yes`. Files edited here are copied
to `.ai-sdlc/backups/extensions/<id>-<time>/` first. It is the only command that re-pins
the hashes. `ext remove` backs up edited files the same way, then deletes the directory
and its record.

## Write one

```json
{
  "schema": 1,
  "id": "lint-pack",
  "version": "1.0.0",
  "nuhut": ">=6.0.0,<7.0.0",
  "description": "Lint rules for agent shell calls",
  "overrides": null,
  "provides": {
    "hook_rules": [{"id": "no-curl", "file": "rules/no_curl.py", "tools": ["Bash"]}],
    "doctor": [{"id": "lint-config", "file": "rules/doctor.py"}],
    "lifecycle": {"before_finish": "rules/finish.py"},
    "overlays": [{"target": "templates/plan.md", "mode": "append",
                  "file": "overlays/plan.md"}]
  }
}
```

- **Hook rules** run with the `approval-gate` hook, for the tools listed in `tools` (all
  tools when it is left out). The file defines `evaluate(payload, cwd, root)`, which
  returns a deny reason or `None`.
- **Doctor checks** define `check(root)`, which returns a list of
  `(level, where, message)` with level `fail`, `warn` or `info`.
- **Lifecycle hooks** define a function named after the event. `before_finish(root,
  item)` returns `None` to pass, or a message that `finish` lists as owed.
- **Overlays** change a kit template (`templates/<name>.md`). `prepend` and `append` add
  the file's text before or after it. `wrap` replaces a line `<!-- nuhut:content -->` in
  the file with the template. Overlays are applied by `install.sh <project> --upgrade`:
  prepends first, then wraps, then appends, and by extension id within each. The kit
  manifest records the hash of the result and the overlays applied, so the next upgrade
  does not mistake it for a local edit.
- **Overriding a built-in** record (for example the `codex` agent) needs
  `"overrides": "codex"` and the id in **Extensions allowed**. Without both, the override
  is ignored and `doctor` says why.

### Add a command

A `commands` record adds one `sdlc.py` subcommand, named by its `id`:

```json
"commands": [{"id": "issues", "file": "issues.py"}]
```

The file defines `register(add, runtime)`. `runtime` is the `sdlc.py` module, and `add`
registers a handler under the record's name only:

```python
def register(add, runtime):
    add(pull, help="read issues", configure=lambda p: p.add_argument("--dry-run",
        action="store_true"), verb="pull")      # sdlc.py issues pull
```

Leave out `verb` for a plain command. The handler is called as
`handler(project, opts, parser)` and returns the exit code.

- The command loads like any other code: always for a built-in, and for a project
  extension only when **Extensions allowed** lists it and the file matches its pin.
- A name that a core command uses (`doctor`, `item`, `deploy`, ...) is ignored, with a
  stderr line that names the extension. The core command keeps running.
- `sdlc.py` imports extension command files only when the command line names something
  other than a core command (or asks for `--help`). A broken extension cannot stop
  `doctor`, `finish` or the merge driver.

Check a manifest before you publish it:

```sh
python3 .ai-sdlc/bin/sdlc.py ext validate ../lint-pack
```

It exits 1 with one message per field, such as
`provides.agents[0].review: expected list of strings`.

## The catalog

`ext search [term]` reads a catalog: a JSON list of `{id, url, ref, description}`, with
an optional `nuhut` range. The default is `catalog.json` in the kit repository, which
lists no extensions yet: `ext search` says so, and `ext add <git-url|path>` installs one
directly. Set `NUHUT_CATALOG_URL` to an `https://` URL or a file path for a private one;
a catalog that cannot be read gives an error that names both. Nothing is
fetched until you run `ext search`, and nothing is installed until you run `ext add`.

The catalog is fetched through `.ai-sdlc/bin/net.py`:

- only `https://`, and no redirect that changes the scheme or host;
- a 5 second timeout and a 1 MB cap;
- error messages that name only the scheme and host.

An entry whose URL breaks the `ext add` rules is shown as refused. `validate.py` checks
that the kit's `VERSION` satisfies every range in the kit's own catalog.

## Package it for other tools

`ext package <id> --for claude|gemini|codex|kiro` writes the plugin wrapper that tool
expects, from the same manifest, into `dist/extensions/<id>/<tool>/` (or `--out DIR`):

| `--for` | Writes | Copies beside it |
| --- | --- | --- |
| `claude` | `.claude-plugin/plugin.json` | the `package.commands` directory |
| `gemini` | `gemini-extension.json` (with `contextFileName` from `package.context_file`) | the context file |
| `codex` | `.codex-plugin/plugin.json` | nothing |
| `kiro` | `plugin.json` and `POWER.md` | nothing |

The metadata comes from an optional top-level `package` block. Every key is optional and
falls back to the manifest's `id`, `version` and `description`:

```json
"package": {
  "name": "lint-pack", "title": "Lint Pack", "version": "1.0.0",
  "description": "Lint rules for agent shell calls",
  "author": {"name": "Your Name", "url": "https://example.com"},
  "homepage": "https://example.com/lint-pack", "license": "MIT",
  "keywords": ["lint"], "commands": "./commands", "context_file": "CONTEXT.md"
}
```

- No wrapper lists skills. Skills are model-invoked and cost context every turn, so they
  are chosen per project by the installer or `ext add`, never shipped globally.
- `package` is data: nothing in it runs. `commands` and `context_file` follow the same
  path rules as the rest of the manifest, and symlinks are not copied.
- `"version": "kit"` means the running Nuhut version. Only the kit's own extensions may
  use it.

The kit's own `.claude-plugin/plugin.json` is generated this way from the `core`
extension, and `validate.py` fails when the two disagree. After editing core's `package`
block, regenerate it from the kit checkout:

```sh
python3 .ai-sdlc/bin/sdlc.py ext package core --for claude --out .
```

## Webhook notifications

Nuhut can tell a chat channel or an on-call tool when an item waits on a person. The
charter's optional **Notify webhook** row names an environment variable that holds the
URL; the URL itself never goes in the repository. The row is off by default.

```sh
python3 .ai-sdlc/bin/sdlc.py config --notify-webhook NUHUT_WEBHOOK_URL   # writes the row
export NUHUT_WEBHOOK_URL='https://hooks.example.com/...'                 # where commands run
python3 .ai-sdlc/bin/sdlc.py notify            # on or off, which variable, is it set here
python3 .ai-sdlc/bin/sdlc.py notify --test     # send a test event; exit 1 if nothing was sent
```

- The variable name must match `^NUHUT_[A-Z0-9_]{1,40}$`, so the row cannot point at
  another secret in the environment. `config --notify-webhook off` turns it off.
- The row is read from the default branch, like **Approvers** and **Extensions
  allowed**: a branch that adds or changes it has no effect until it merges, and
  `ci-check` fails a Tier 2 or 3 range that changes it.
- Events: `parked` (an item set to Parked by `item add`, `item set` or `item triage`),
  `review-blocked` (`finish` refused because a review finding is escalated with no
  decision; sent on each refused run), `approval-needed` (`finish` parked a Tier 1 item,
  or a Tier 2 item under Strict tier rules, for the merge approval) and `test`.
- The payload is a small JSON object: `schema`, `source`, `event`, `project` (the ID
  prefix), `item`, `title`, `tier`, `status` and `sent_at`. It carries no diff, no park
  reason, no person's name and no URL. **It does include the item's title**, which
  leaves the machine. Add `--ids-only` to the row (`` `NUHUT_WEBHOOK_URL` --ids-only ``)
  to drop titles from every event, or pass `notify --test --ids-only` for one test.
- The POST goes through `net.py`: `https://` only, no redirect that changes the scheme
  or host, a 5 second timeout, and the response is ignored. Plain `http://` is allowed
  only to `127.0.0.1` or `localhost` while `NUHUT_ALLOW_HTTP=1`, for a local receiver.
- A failed send prints one `notify:` warning that names only the scheme and host (never
  the path or query, which often carry a token) and never blocks the command. An unset
  variable sends nothing and stays quiet, except under `notify --test`.

## GitHub issues

The `github-issues` built-in extension adds `sdlc.py issues pull` and
`sdlc.py issues push`. They map GitHub issues to work items through the
[`gh` CLI](https://cli.github.com), which does the network calls and holds the login.
Nuhut never reads a token. Install `gh` and run `gh auth login` first.

```sh
python3 .ai-sdlc/bin/sdlc.py issues pull --dry-run        # what would be parked or linked
python3 .ai-sdlc/bin/sdlc.py issues pull                  # park the issues no item maps to
python3 .ai-sdlc/bin/sdlc.py issues pull --label triage --state all --limit 200
python3 .ai-sdlc/bin/sdlc.py issues push ACME-12 ACME-14  # open issues for these items
python3 .ai-sdlc/bin/sdlc.py issues push --all --dry-run  # every open item without one
python3 .ai-sdlc/bin/sdlc.py render                       # refresh backlog.md afterwards
```

- **The link.** An item's shard holds the issue number in `issue`, for example
  `"issue": 42`. An item without a link has no such field. When two branches link one
  item to different issues, the shard merge driver shows a conflict instead of picking
  one.
- **pull** runs `gh issue list --json number,title,labels,url` (open issues, at most 100,
  by default). Each issue that no item maps to becomes a new **Parked** item. It waits on
  the backlog owner, and its park reason names the issue, so a person decides whether it
  becomes Ready, gets deferred or is dropped. A label containing `bug` makes it a
  `defect`. An issue titled `<ID>: ...` that names an item without a link links that item
  instead, which is how an issue opened by `push` is found again. Running pull twice
  creates nothing new.
- **push** needs the IDs, or `--all` for every item that is not Done or Dropped and has no
  issue. With neither, it lists those items and exits 2. Each issue is titled
  `<ID>: <title>`, and its body says only the ID, type, tier and status. Summaries, park
  reasons and plans stay in the repository. An item that already has an issue is
  skipped.
- **Untrusted text.** Anyone who can open an issue writes its title, and agents read the
  backlog. pull never reads the issue body. It cuts each title to one line of at most 120
  characters, with no escape sequences, control or invisible format characters and no
  `|`. Each import is Parked until a person triages it.
- `--repo OWNER/NAME` picks a repository other than the one `gh` finds in this
  directory. `--json` prints what was created, linked and skipped.

### Other trackers

Linear and Jira are planned as further extensions of the same shape: a `commands` record
that adds `sdlc.py linear pull|push` or `sdlc.py jira pull|push`. Each will keep the
tracker's key on the shard in its own field and park unmapped tickets the same way. Neither
exists yet. Until then, a project can write one as a project extension with
`sdlc.py ext add` and turn it on with **Extensions allowed**.

## Not yet

- `checks` from an allowed extension load into the registry, but `verify` still runs
  only the charter's Commands rows.

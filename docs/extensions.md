# Extensions

An extension is a directory with a `nuhut-extension.json` manifest. It can add agent tool
records, presets, skills, roles, template overlays, hook rules, doctor checks and
lifecycle hooks without a fork of the kit. The format and the reasons behind it are in
ADR 0003 (`handbook/project/adr/0003-extension-system.md` in the kit repository).

There are two kinds:

- **Built-in** extensions (`core`, `claude`, `codex`, `gemini`, `cursor`) live in
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
Code also loads only while each file's sha256 matches the hash `ext add` pinned. A file
edited by hand is refused, with a message that names it and `sdlc.py ext update <id>`.

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
python3 .ai-sdlc/bin/sdlc.py ext update lint-pack
python3 .ai-sdlc/bin/sdlc.py ext remove lint-pack
```

`ext update` fetches the recorded source and ref again. It prints the old and new commit
and every added, changed or removed file before it writes. Files edited here are copied
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

Check a manifest before you publish it:

```sh
python3 .ai-sdlc/bin/sdlc.py ext validate ../lint-pack
```

It exits 1 with one message per field, such as
`provides.agents[0].review: expected list of strings`.

## The catalog

`ext search [term]` reads a catalog: a JSON list of `{id, url, ref, description}`, with
an optional `nuhut` range. The default is `catalog.json` in the kit repository. Set
`NUHUT_CATALOG_URL` to an `https://` URL or a file path for a private one. Nothing is
fetched until you run `ext search`, and nothing is installed until you run `ext add`.

The catalog is fetched through `.ai-sdlc/bin/net.py`:

- only `https://`, and no redirect that changes the scheme or host;
- a 5 second timeout and a 1 MB cap;
- error messages that name only the scheme and host.

An entry whose URL breaks the `ext add` rules is shown as refused. `validate.py` checks
that the kit's `VERSION` satisfies every range in the kit's own catalog.

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

## Not yet

- `commands` entry points are validated, pinned and listed, but `sdlc.py` does not yet
  dispatch to them. That waits for the command table (NUHT-021).
- `checks` from an allowed extension load into the registry, but `verify` still runs
  only the charter's Commands rows.

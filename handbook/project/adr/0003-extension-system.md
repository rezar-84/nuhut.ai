---
status: proposed
owner: rezar-84
last-reviewed: 2026-11-22
---

# ADR 0003: An extension system with one manifest per extension

- **Status:** Proposed
- **Date:** 2026-11-22
- **Deciders:** rezar-84
- **Work item:** NUHT-016
- **Design review:** `../reviews/NUHT-016-design-review.md`

## Context

Agent tools are wired into the kit by hand.

- **Installer.** It holds pointer files, native readers, aliases, titles, markers and hook
  writers for each tool (`install.py` `HARNESS_*` near line 1106, hook writers near lines
  3579 to 3777).
- **Runtime.** It keeps two agent CLI tables that disagree: `REVIEW_HARNESSES` in
  `sdlc.py` and `BUILD_HARNESSES` in `dispatch.py`. It also has payload normalisers for
  each tool in `hooks.py` (the cursor and gemini branches near lines 610 to 650) and its
  own lists of tool directories and MCP files in `lens.py` (near lines 634 to 651).
- **Cost.** Adding OpenCode, Kiro or an ACP agent means editing about 25 places in four
  files. Third parties cannot add a role pack, a check stage or a hook rule without forking.

Spec Kit (`extension.yml`), Claude Code (`plugin.json` plus a marketplace), Gemini CLI
(`gemini-extension.json`) and Kiro Powers all use the same shape: a folder of components,
one manifest with an id, a version and a compatible engine range, and a git-hosted
catalog.

## Decision

1. **Manifest.** An extension is a directory holding `nuhut-extension.json`:

   ```json
   {
     "schema": 1,
     "id": "opencode",
     "version": "1.0.0",
     "nuhut": ">=6.0.0,<7.0.0",
     "description": "OpenCode support",
     "overrides": null,
     "provides": {
       "harnesses": [{"id": "opencode", "title": "OpenCode", "pointer": null,
                      "native": true, "markers": [".opencode"],
                      "skills_dir": ".agents/skills",
                      "hooks": {"dialect": null, "settings": null, "events": {}},
                      "lens": {"dirs": [".opencode"], "mcp": []}}],
       "agents": [{"id": "opencode", "family": "varies",
                   "review": ["opencode", "run", "{prompt}"],
                   "build": ["opencode", "run", "{prompt}"]}],
       "checks": [], "presets": [], "hook_rules": [], "doctor": [],
       "skills": "skills/", "roles": "roles/", "templates": "templates/",
       "overlays": [{"target": "templates/plan.md", "mode": "append",
                     "file": "overlays/plan.md"}],
       "lifecycle": {"before_finish": "hooks/before_finish.py"}
     }
   }
   ```

   - **`nuhut`.** A third-party manifest gives a comma-separated `>=`, `<`, `==` range. A
     built-in manifest gives the literal `"builtin"`, which always matches, so a major bump
     made by `tools/semver.py` never strands the built-ins. `validate.py` asserts that
     `VERSION` satisfies every non-built-in range listed in `catalog.json`.
   - **`schema`.** The registry refuses a `schema` higher than it knows, with "this
     extension needs a newer Nuhut: upgrade Nuhut". It warns, and does not fail, on a key
     under `provides` that it does not know.
   - **`harnesses[].hooks`.** `dialect` is `"claude"`, `"gemini"`, `"cursor"` or `null`.
     The dialect implementations (payload normalising and response shape) stay in core
     and are chosen by name; an extension cannot ship a new dialect. With `null`, the
     installer prints, and `docs/harnesses.md` states, "guards do not run for this tool".
   - **`harnesses[].lens`.** The tool directories and MCP config files `lens.py` reads.
   - **`overrides`.** `null`, or the id of the built-in extension this one overrides
     (decision 3).

2. **Three kinds of contribution.**
   - **Data** (`harnesses`, `presets`, `templates`, `overlays`) is declarative and is never
     passed to a subprocess.
   - **Prompt content** (`skills`, `roles`) reaches agent context. It is data for the
     runtime but untrusted input for an agent, so `ext list` labels every skill and role
     with the extension it came from.
   - **Executable** contributions are everything that reaches a subprocess or the Python
     interpreter: `agents[].review` and `agents[].build` argv (run by `review --by` and
     `dispatch`), `checks` commands (run by `verify`), and the code entry points
     `hook_rules`, `doctor`, `commands` and `lifecycle` (loaded with `importlib`).
     An executable contribution loads only when the extension is built-in, or when the
     charter's **Extensions allowed** row names its id. That row is read from the default
     branch (decision 8). `ext list` and `doctor` print every `argv[0]` and every check
     command that comes from a non-built-in extension.

3. **Locations.** In an installed project the registry searches, highest priority first:
   - `<root>/.ai-sdlc/local/extensions/<id>/`: project and third-party extensions. Never
     written by `--upgrade`; changed only by `sdlc.py ext add | update | remove`.
   - `<root>/.ai-sdlc/extensions/<id>/`: the installed built-ins. Managed files, refreshed
     by `--upgrade`.
   - `<kit>/optional/extensions/<id>/`: only when the runtime runs from the kit checkout
     itself.

   All kit state stays under `.ai-sdlc/`; there is no second dot-directory.

   **Overriding a built-in** is a per-record merge by id, not a replacement of the whole
   extension: a project manifest that provides `agents[id=codex]` replaces only that
   record, and every other built-in record keeps receiving upgrades. It needs both
   `"overrides": "<built-in id>"` in the manifest and that extension's id in
   **Extensions allowed**; without both, the override is ignored and doctor says why.
   `ext list` shows the source of each record: `built-in`, `project` or `override`.

   **When the registry is missing or broken.**
   - `.ai-sdlc/extensions/` does not exist at all (an install made before 6.0, or a partial
     upgrade), or `registry.py` cannot be imported: the runtime uses the v5 constants, and
     doctor warns "registry missing, using v5 tables".
   - A manifest is present but invalid or out of range: never a silent fallback. The
     registry skips that extension, prints one stderr warning naming the file and field,
     and doctor reports it at fail level.
   - After NUHT-017 removes the constants, argparse choices are built from the registry
     inside a try/except that falls back to a static list, so a bad manifest cannot break
     the whole CLI.

4. **Registry.** `optional/runtime/registry.py`, stdlib only, Python 3.8+:
   - loads manifests from the locations above;
   - refuses an extension whose `nuhut` range excludes the running version, or whose
     `schema` is too new;
   - exposes `harnesses()`, `agents()`, `checks()`, `hook_rules()`, `doctor_checks()` and
     `lifecycle(event)`.

   The installer and runtime read tool data from here rather than from constants.

   **Pinned code.** Before `importlib` loads a code file from a non-built-in extension,
   the registry compares its sha256 with the hash recorded at `ext add` (decision 5). A
   file whose hash differs is refused with a message naming the file and `sdlc.py ext
   update <id>`. Agent edits to the extension directories are also denied by the hooks
   (NUHT-013's built-in human-owned list).

   **Fail-closed for a broken allowed extension** means: its rules are skipped; one hook
   warning per process names the extension and the error; and only the tool calls that
   its `hook_rules` would have judged are denied. Other tool calls run normally, and
   `ext remove <id>` or fixing the file is the recovery path.

5. **CLI and records.** `sdlc.py ext list | add <path|git-url> [--ref] | remove | update |
   search | validate`.
   - `.ai-sdlc/manifest.json` gains a separate key, outside the kit's `files`:
     `"extensions": {"<id>": {"source", "ref", "commit", "files": {"<rel>": "<sha256>"}}}`.
     `install.py --upgrade` copies that key through unchanged and leaves its files out of
     the obsolete-file calculation, so an upgrade never deletes or rewrites an installed
     extension. `is_managed_rel` does not gain the local extensions prefix.
   - Only `ext update` and `ext remove` change those files, with the same hash-checked,
     back-up-on-edit logic the installer uses. `ext update` is the only path that re-pins
     hashes.
   - Git sources: only `https://`, `ssh://` and `git@host:path` URLs, matched by a regex;
     anything starting with `-` is refused. The clone is
     `git -c protocol.ext.allow=never -c protocol.file.allow=user clone --depth 1
     --no-recurse-submodules -- <url> <tmp>`, run as argv with no shell. A local source is
     a filesystem path, never a `file://` URL. `--ref` is resolved to a commit sha and
     recorded as `commit`; `ext list` shows it, and `ext update` prints the old and new sha
     and the changed files before writing.
   - Paths: every manifest path is relative, has no `..` and no leading `/`, and the
     realpath of every file, symlinks included, stays inside the extension directory.
     Overlay targets are limited to the kit's template set.
   - `ext add` prints a summary before writing: id, version, data records, and every
     executable entry point with its file path. For an extension with executable
     contributions it then prints "code is disabled until the charter row Extensions
     allowed lists `<id>`: run `sdlc.py config --allow-extension <id>`".
   - `ext list` has a STATUS column: `data`, `code-enabled`, `code-blocked`,
     `version-refused`. Doctor warns once for each installed extension whose executable
     contributions are blocked. `ext validate` exits 1 with field-level messages such as
     `provides.agents[0].review: expected list of strings`.

6. **Catalog.** `catalog.json` in the kit repository. `NUHUT_CATALOG_URL` overrides it
   for private catalogs. The catalog is only a list of git URLs and refs; nothing is
   fetched unless a person runs `ext add`. It is fetched through the shared
   `optional/runtime/net.py` helper (https only, no cross-host or scheme-changing
   redirects, 5 s timeout, 1 MB cap, errors that print scheme and host only). Every
   catalog entry passes the same URL rules as `ext add`.

7. **Overlays.** When several extensions target one template, overlays apply in order of
   extension id, and within one target `prepend` before `wrap` before `append`. The
   installer's manifest stores the hash of the rendered result together with the ids and
   versions of the overlays applied, so an upgrade re-renders the template instead of
   reporting a local edit.

8. **Trust anchors.** Security-bearing charter rows (**Approvers**, **Extensions allowed**,
   **Always Tier 1 here**, **Notify webhook**) and `<docs>/project/people.json` are read
   from the default branch through one helper (introduced by NUHT-012), falling back to
   the working tree only when there is no default branch. A branch that edits them has no
   effect until it merges, and `ci-check` (NUHT-022) fails a range that changes them under
   a Tier 2 or 3 item.

9. **Packaging.** From the same manifest the installer generates the wrappers each tool
   expects: Claude Code `.claude-plugin`, Gemini `gemini-extension.json`, Codex and Kiro.
   This replaces NUHT-008's separate bootstrap (NUHT-008 is superseded by NUHT-019).

## Consequences

- **New tools.** Supporting a new agent tool becomes a data-only extension, with no core
  release, as long as it uses an existing hook dialect or none. A tool with `dialect:
  null` gets no guards, and the installer and docs say so.
- **Single table.** The review and build CLI tables merge into one `agents` record, which
  removes the current disagreement.
- **Size.** The core shrinks. Built-in extensions can be left out of a compact install.
- **New contract.** The manifest format is a public contract with its own `schema` number.
- **Executable risk.** Agent argv and check commands are executable contributions, gated
  exactly like Python code: built-in, or named in **Extensions allowed** on the default
  branch. Code files are hash-pinned at `ext add`. A project extension cannot silently
  take over `review --by claude`.
- **Managed paths.** Only `.ai-sdlc/extensions/` (built-ins) is a managed prefix.
  `.ai-sdlc/local/extensions/` is tracked under its own manifest key and survives
  upgrades. `validate.py` must validate every built-in manifest.

## Alternatives considered

### Adopt the Claude Code plugin format as the only format
Rejected. It ties every other tool to one vendor's layout. Nuhut supports about twelve tools
and needs one source that generates each tool's own format.

### Python entry points or pip packages
Rejected. The kit is stdlib-only and installs without pip (AGENTS.md section 9).

### Keep constants and add tools one release at a time
Rejected. This is today's cost, and it blocks third-party role packs and checks entirely.

### A separate `.nuhut/extensions/` directory for project extensions
Rejected in design review. It adds a second kit dot-directory beside `.ai-sdlc/`, and a
newcomer cannot tell which is managed. `.ai-sdlc/local/` makes the split visible inside
one directory.

## Reversibility

The built-in extensions reproduce today's constants exactly, so reverting the registry means
restoring those constants. Projects that installed third-party extensions would lose them
on downgrade. Their files stay on disk and are reported as unmanaged.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| A1 | Upgrade deletes `ext add` files | Fix | Decision 5: separate `extensions` manifest key, excluded from obsolete set |
| A2/S1 | Agent argv and checks execute; silent built-in override | Fix | Decision 2 (executable kind), decision 3 (`overrides` plus allow list) |
| A7/U5 | Inconsistent locations; silent fallback | Fix, adapted | Decision 3 uses `.ai-sdlc/local/extensions/` (usability lens) in place of `.nuhut/extensions/` (architecture lens); both lenses' search-path and fallback rules kept |
| A8 | Manifest cannot express hook dialect or lens dirs | Fix | Decision 1: `hooks` and `lens` fields |
| A9 | Versioning, schema and overlay rules | Fix | Decision 1 (`builtin`, schema), decision 7 (overlays) |
| S1 | Meaning of fail-closed | Fix | Decision 4, last paragraph |
| S2 | Trust anchors editable on the branch | Fix, narrowed | Decision 8. `charter.md` is not added to the agent-edit deny list: agents edit it routinely (Unknowns, last-reviewed). Its security rows take effect only from the default branch, and `ci-check` flags a change to them |

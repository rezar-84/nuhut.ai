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

## Context

Agent tools are wired into the kit by hand.

- **Installer.** It holds pointer files, native readers, aliases, titles, markers and hook
  writers for each tool (`install.py` `HARNESS_*` near line 1106, hook writers near lines
  3579 to 3777).
- **Runtime.** It keeps two agent CLI tables that disagree: `REVIEW_HARNESSES` in
  `sdlc.py` and `BUILD_HARNESSES` in `dispatch.py`. It also has payload normalisers for
  each tool in `hooks.py` and its own lists of tool directories in `lens.py`.
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
     "provides": {
       "harnesses": [{"id": "opencode", "title": "OpenCode", "pointer": null,
                      "native": true, "markers": [".opencode"],
                      "skills_dir": ".agents/skills"}],
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

2. **Two kinds of contribution.**
   - **Data** (`harnesses`, `agents`, `checks`, `presets`, content and overlays) is
     declarative and never executes.
   - **Code** (`hook_rules`, `doctor`, `commands`, `lifecycle`) is Python loaded with
     `importlib` from the extension directory. It loads only when the charter's
     **Extensions allowed** row names the extension, and it runs fail-closed inside the
     hook engine.

3. **Locations, highest priority first.**
   - The project's `.nuhut/extensions/<id>/`.
   - The kit's built-in `optional/extensions/<id>/`.

   A project extension with the same id replaces the built-in one.

4. **Registry.** `optional/runtime/registry.py`, stdlib only, Python 3.8+:
   - loads manifests;
   - refuses an extension whose `nuhut` range excludes the running version;
   - exposes `harnesses()`, `agents()`, `checks()`, `hook_rules()`, `doctor_checks()` and
     `lifecycle(event)`.

   The installer and runtime read tool data from here rather than from constants.

5. **CLI.** `sdlc.py ext list | add <path|git-url> [--ref] | remove | update | search |
   validate`. Installed files are recorded with a sha256 in `.ai-sdlc/manifest.json`, so
   upgrade never overwrites an edited extension file.

6. **Catalog.** `catalog.json` in the kit repository. `NUHUT_CATALOG_URL` overrides it
   for private catalogs. The catalog is only a list of git URLs and refs; nothing is
   fetched unless a person runs `ext add`.

7. **Packaging.** From the same manifest the installer generates the wrappers each tool
   expects: Claude Code `.claude-plugin`, Gemini `gemini-extension.json`, Codex and Kiro.
   This replaces NUHT-008's separate bootstrap.

## Consequences

- **New tools.** Supporting a new agent tool becomes a data-only extension, with no core
  release.
- **Single table.** The review and build CLI tables merge into one `agents` record, which
  removes the current disagreement.
- **Size.** The core shrinks. Built-in extensions can be left out of a compact install.
- **New contract.** The manifest format is a public contract with its own `schema` number.
- **Code risk.** Extension code runs inside hooks, which is why it is opt-in per extension
  and fail-closed.
- **More managed paths.** The manifest gains a `.nuhut/extensions/` prefix, and `validate.py`
  must validate every built-in manifest.

## Alternatives considered

### Adopt the Claude Code plugin format as the only format
Rejected. It ties every other tool to one vendor's layout. Nuhut supports about twelve tools
and needs one source that generates each tool's own format.

### Python entry points or pip packages
Rejected. The kit is stdlib-only and installs without pip (AGENTS.md section 9).

### Keep constants and add tools one release at a time
Rejected. This is today's cost, and it blocks third-party role packs and checks entirely.

## Reversibility

The built-in extensions reproduce today's constants exactly, so reverting the registry means
restoring those constants. Projects that installed third-party extensions would lose them
on downgrade. Their files stay on disk and are reported as unmanaged.

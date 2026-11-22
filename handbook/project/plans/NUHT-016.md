---
status: draft
owner: architect
last-reviewed: 2026-11-22
---

# Plan: NUHT-016 Extension registry and manifest

**Tier:** 1 **Effort:** Normal **Depends on:** ADR 0003 approval

## Problem

Agent tools, check stages, presets and hook rules are hard-coded constants spread over
`install.py`, `sdlc.py`, `dispatch.py`, `hooks.py` and `lens.py`. Adding a tool means
editing about 25 places, and nobody outside the kit can extend it. ADR 0003 sets out the
manifest and the registry.

## Outcome

`optional/runtime/registry.py` loads `nuhut-extension.json` manifests from
`optional/extensions/` and `.nuhut/extensions/`, checks each version range, and returns
harness, agent, check and preset records. Built-in manifests reproduce today's constants
exactly, and the existing constants become views over the registry. Behaviour is
unchanged: the full smoke suite passes without edits to any existing check.

## Approach

- `registry.py`:
  - **Discovery.** `load(root)` finds every manifest and returns them by id, with project
    extensions replacing built-in ones.
  - **Schema.** `validate(manifest)` checks a stdlib schema: required keys, types, id
    pattern, `schema == 1`.
  - **Version range.** `version_ok(range, version)` handles a comma-separated `>=`, `<`
    and `==`.
  - **Accessors.** `harnesses()`, `agents()`, `checks()` and `presets()` merge the records
    by id.
  - **Code extensions** are declared but not loaded in this item; that starts in NUHT-018.
- `optional/extensions/{claude,codex,gemini,cursor,core}/nuhut-extension.json`: data
  transcribed from `HARNESS_POINTERS`, `HARNESS_NATIVE`, `HARNESS_MARKERS`,
  `REVIEW_HARNESSES`, `BUILD_HARNESSES` and `PRESETS`.
- `install.py` and `sdlc.py` build their `HARNESS_*` and `*_HARNESSES` tables from the
  registry when it is present, and fall back to the old constants otherwise. This keeps
  one release of compatibility.
- `RUNTIME_FILES` gains `registry.py`. The installer copies `optional/extensions/` into
  `.ai-sdlc/extensions/` as managed files. `is_managed_rel` gains the prefix.
- `validate.py` validates every built-in manifest. A parity test checks that the registry
  output equals the old constants.

## Files that change

- `optional/runtime/registry.py` (new)
- `optional/extensions/claude/nuhut-extension.json` (new)
- `optional/extensions/codex/nuhut-extension.json` (new)
- `optional/extensions/gemini/nuhut-extension.json` (new)
- `optional/extensions/cursor/nuhut-extension.json` (new)
- `optional/extensions/core/nuhut-extension.json` (new)
- `optional/runtime/sdlc.py`
- `optional/runtime/dispatch.py`
- `install.py`
- `validate.py`
- `tests/smoke.py`
- `docs/cli.md`
- `CHANGELOG.md`

## Tests (written first)

- **Parity.** The registry's harness and agent records equal the current constants.
- **Version range.** An extension with `"nuhut": ">=99"` is refused with a clear message.
- **Override.** A project extension `.nuhut/extensions/codex/` replaces the built-in one.
- **Invalid manifest.** A missing `id` or a bad type gives a doctor warning, not a crash.

## Risks

- **Fallback drift.** The old constants and the manifests could drift during the
  transition. The parity test is the guard, and NUHT-017 removes the constants.
- **Brace rule.** No literal doubled curly braces may appear in `registry.py`, because of
  the installer's placeholder substitution.

## Rollback

Revert the commit. The constants are still present in this item, so behaviour returns to
v5.

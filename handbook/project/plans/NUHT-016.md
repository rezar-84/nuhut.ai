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

`optional/runtime/registry.py` loads `nuhut-extension.json` manifests from, highest
priority first, `<root>/.ai-sdlc/local/extensions/`, `<root>/.ai-sdlc/extensions/` and
(kit checkout only) `<kit>/optional/extensions/`. It checks each version range and schema,
and returns harness, agent, check and preset records. Built-in manifests reproduce today's
constants exactly, and the existing constants become views over the registry. Behaviour is
unchanged: the full smoke suite passes without edits to any existing check.

## Approach

- `registry.py`:
  - **Discovery.** `load(root)` finds every manifest in the three locations of ADR 0003
    decision 3 and returns them by id.
  - **Override.** A project record replaces a built-in record of the same id only when the
    manifest says `"overrides": "<built-in id>"`. The merge is per record, by id. Records
    carry a `source` of `built-in`, `project` or `override`.
  - **Executable records.** In this item, `agents` argv and `checks` from a non-built-in
    extension are refused outright, with a doctor note "executable contributions from
    project extensions need NUHT-018". NUHT-018 adds the **Extensions allowed** gate.
    Harness and preset data records from project extensions load.
  - **Schema.** `validate(manifest)` checks a stdlib schema: required keys, types, id
    pattern. `schema` higher than 1 is refused with "upgrade Nuhut". An unknown key under
    `provides` is a warning, not a failure.
  - **Version range.** `version_ok(range, version)` handles a comma-separated `>=`, `<`
    and `==`, and the literal `"builtin"`, which always matches.
  - **Accessors.** `harnesses()`, `agents()`, `checks()` and `presets()` merge the records
    by id.
  - **Code extensions** are declared but not loaded in this item; that starts in NUHT-018.
- `optional/extensions/{claude,codex,gemini,cursor,core}/nuhut-extension.json`: data
  transcribed from `HARNESS_POINTERS`, `HARNESS_NATIVE`, `HARNESS_MARKERS`,
  `REVIEW_HARNESSES`, `BUILD_HARNESSES` and `PRESETS`, each with `"nuhut": "builtin"`.
  Harness records carry the `hooks` (`dialect`, `settings`, `events`) and `lens` (`dirs`,
  `mcp`) fields of ADR 0003 decision 1, filled from today's code, though nothing reads them
  until NUHT-017.
- **Fallback.** `install.py` and `sdlc.py` build their `HARNESS_*` and `*_HARNESSES`
  tables from the registry. They fall back to the old constants only when
  `.ai-sdlc/extensions/` does not exist at all or `registry.py` cannot be imported, and
  doctor then warns "registry missing, using v5 tables". A present but invalid built-in
  manifest prints a stderr warning naming the file and field, and doctor reports it at
  fail level. It is never a silent fallback.
- `RUNTIME_FILES` gains `registry.py`. The installer copies `optional/extensions/` into
  `.ai-sdlc/extensions/` as managed files. `is_managed_rel` gains the
  `(".ai-sdlc", "extensions")` prefix only. `.ai-sdlc/local/` is not a managed prefix.
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
- **Version range.** An extension with `"nuhut": ">=99"` is refused with a clear message;
  `"builtin"` always loads.
- **Schema.** `"schema": 2` is refused with "upgrade Nuhut"; an unknown `provides` key
  loads with a warning.
- **Override.** A project extension in `.ai-sdlc/local/extensions/codex-local/` with
  `"overrides": "codex"` replaces only the codex harness record. Without `overrides` it
  is ignored. An `agents` override from a project extension is refused in this item.
- **Invalid manifest.** Corrupt `.ai-sdlc/extensions/codex/nuhut-extension.json`: doctor
  fails naming the path, and `review --by codex` gives a clear error, not a traceback.
- **Missing registry.** With `.ai-sdlc/extensions/` absent, the v5 tables are used and
  doctor warns.

## Roadmap build waves

Decided at design review (`../reviews/NUHT-016-design-review.md`). `docs/landscape.md`
publishes the same list.

| Wave | Items |
| --- | --- |
| W0 | NUHT-011, NUHT-015, NUHT-021, NUHT-035 |
| W1 | NUHT-012, NUHT-013, NUHT-014, NUHT-016, NUHT-023 |
| W2 | NUHT-017, NUHT-018, NUHT-022, NUHT-024, NUHT-027 |
| W3 | NUHT-019, NUHT-020, NUHT-025, NUHT-026, NUHT-028, NUHT-032, NUHT-033 |
| W4 | NUHT-029, NUHT-030, NUHT-031, NUHT-034 |

NUHT-021 (the command table) has no dependency and lands first, because NUHT-018, 022,
024, 026, 027, 028, 030 and 031 each add subcommands.

## Risks

- **Fallback drift.** The old constants and the manifests could drift during the
  transition. The parity test is the guard, and NUHT-017 removes the constants.
- **Brace rule.** No literal doubled curly braces may appear in `registry.py`, because of
  the installer's placeholder substitution.

## Rollback

Revert the commit. The constants are still present in this item, so behaviour returns to
v5.

## Design review responses

| # | Finding | Response (Fix/Contest/Decline) | Evidence |
| --- | --- | --- | --- |
| U11 | Constants fallback hides failures | Fix | Approach, "Fallback"; tests "Invalid manifest" and "Missing registry" |
| A6 | Waves and dependency graph wrong | Fix in this plan; backlog edits left to the owner | "Roadmap build waves". The `depends` changes are listed in the review record, because this step does not edit `backlog.md` or item shards |

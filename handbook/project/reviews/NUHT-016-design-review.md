---
status: current
owner: architect
last-reviewed: 2026-11-22
---

# Review — NUHT-016 v6 roadmap, ADR 0003 extension system and the Tier 1 plans

**Stage:** design **Tier:** 1
**Author:** claude-code
**Reviewer agent:** fresh-context subagents, one per lens (architecture, security, usability)
**Reviewer model:** claude-opus-5-5 (same model family as the author)
**Independence:** self-check (same model family; charter `Independent review required for: none`)
**Reviewed:** `handbook/project/adr/0003-extension-system.md`, `handbook/project/plans/NUHT-012.md`,
`NUHT-014.md`, `NUHT-016.md`, `NUHT-022.md`, `NUHT-024.md`, `NUHT-027.md`, the v6 rows of
`handbook/project/backlog.md` (NUHT-011 to NUHT-036), the builder specs of the Tier 2 and 3
items, and `docs/landscape.md`.

A self-check clears nothing on its own. The two human approvals for these Tier 1 plans
are still owed.

---

## Design in one paragraph (as the reviewers restated it)

ADR 0003 and NUHT-016 to 021 move every hard-coded tool, check and preset into versioned
`nuhut-extension.json` manifests, loaded by a stdlib registry from built-in and project
folders, so new tools and third-party packs need no core change. NUHT-012, 013, 022 and
024 tighten evidence, guards and approvals. NUHT-014 and 027 to 029 add release and deploy
records, and NUHT-023, 025, 026 and 030 to 035 cover team workflow and integrations.

## architect

**Verdict:** Block (4 blocking), resolved by the responses below.

**Checked:** `install.py` upgrade path (obsolete-file calculation near line 4730, unlink
near 4785, `is_managed_rel` near 3205), the ADR's contribution kinds against the
subprocess callers (`review --by`, `dispatch`, `verify`), the stale-run rule against the
kit's own finish flow, `ci_text()`, the dependency graph and waves, tool-specific code in
`hooks.py`, `install.py` and `lens.py`, versioning and overlay rules, the NUHT-024 counting
rule, the NUHT-014 release job.

**Not checked:** runtime behaviour; no code exists yet for these items.

| # | Sev | Location | Finding | Fix | Response |
| --- | --- | --- | --- | --- | --- |
| A1 | blocking | ADR 0003 d5, NUHT-018 | First `--upgrade` after `ext add` deletes every extension file, because they are never in the kit's planned set | Separate `extensions` key in `.ai-sdlc/manifest.json`, copied through by upgrade, outside the obsolete set; smoke test ext add, upgrade, files and hashes survive | Fix: ADR d5; NUHT-018 amendment |
| A2 | blocking | ADR 0003 d2, d3 | "Data never executes" is false: agent argv and checks reach subprocess; a same-id project extension replaces a built-in | Reclassify as executable, gate on Extensions allowed; `overrides` key; `ext list` and doctor print non-built-in argv | Fix: ADR d2, d3; NUHT-016 refuses project executable records until NUHT-018 |
| A3 | blocking | NUHT-018 | An agent can edit an allowed extension's hook_rules to allow everything | sha256 pin per code file at ext add, refuse on mismatch; extension dirs and charter protected; ref resolved to a commit | Fix: ADR d4, d5; NUHT-013 and NUHT-018 amendments. Charter not added to the deny list (see S2) |
| A4 | blocking | NUHT-012, NUHT-022 | The committed records-only commit after verify makes the run stale and finish loops; ci-check and finish use different rules | "Newest commit" skips commits that only change `<docs>/project/**`; NUHT-022 calls `verify_state`; NUHT-012 a dependency of NUHT-022 | Fix: both plans; backlog change listed below |
| A5 | major | NUHT-022 | quality.yml runs the PR's own checker and charter | Base-ref checker, `--charter-ref`; enforcement surfaces in default Tier 1 globs; fail on tier lowering | Fix: NUHT-022 |
| A6 | major | backlog | NUHT-021 ordering, NUHT-030 missing 021, NUHT-019 depends on Deferred NUHT-008, NUHT-029 missing 028 | 021 to wave 0; dependency edits; publish waves | Fix: waves in NUHT-016 plan; backlog edits owed by the owner (list below) |
| A7 | major | ADR 0003 d3 | Locations inconsistent; constants fallback hides a broken install | Exact search path; fallback only when the registry is absent; invalid manifest is a doctor finding; argparse fallback | Fix, adapted: ADR d3 (project path is `.ai-sdlc/local/extensions/`, per U5) |
| A8 | major | NUHT-020, NUHT-017 | Manifest cannot express hook dialects or lens dirs | `hooks.dialect` and `lens` fields; core keeps dialect code; `null` means no guards, said out loud | Fix: ADR d1; NUHT-017 and NUHT-020 amendments |
| A9 | major | ADR 0003 | Major bump strands built-ins; schema and overlay rules missing | `"builtin"` range; schema refusal; overlay order; rendered-result hash | Fix: ADR d1, d7 |
| A10 | major | NUHT-024 | PR chosen by branch name; head not bound to local commits; people.json editable | OPEN or MERGED, head equals local branch; people.json from default branch | Fix: NUHT-024 |
| A11 | minor | NUHT-014 | Releases untested commits after rebase; release types ambiguous | Exit 0 when main moved; one `RELEASE_TYPES` list with revert | Fix: NUHT-014 |
| A12 | minor | NUHT-013, NUHT-025, NUHT-027 | Read-only commands blocked; deploys.jsonl conflicts on merge | shlex write-target parsing; `merge=union` for deploys.jsonl | Fix: NUHT-013 amendment; NUHT-027 writes the line |

## security

**Verdict:** Block (4 blocking), resolved by the responses below.

**Checked:** every path from manifest data to subprocess or `importlib`, each new trust
anchor and who can edit it, the CI checker's provenance, merge handling in ci-check, the
`ext add` git invocation and manifest paths, the hook's shell-write matching, outbound
HTTP (webhooks, catalog), the MCP server's tool surface, the merge-shard driver, the
release job's skip guard.

**Not checked:** threat model of the GitHub Actions runner itself; `gh` CLI internals.

| # | Sev | Location | Finding | Fix | Response |
| --- | --- | --- | --- | --- | --- |
| S1 | blocking | ADR 0003 | Data-only manifest can turn `review --by claude` into any binary; fail-closed undefined | Executable kind gated by allow list; explicit built-in override; print effective argv; define fail-closed | Fix: ADR d2, d3, d4 |
| S2 | blocking | NUHT-012, 018, 022, 023, 024, 034 | Approvers, Extensions allowed, Tier 1 globs, people.json and webhook are editable on the branch that benefits; `--by` is only a name | Read security rows from the default branch; protect the files; bind waiver to runner identity | Fix, narrowed: ADR d8, NUHT-012 `trusted_text` and `waived_as`. `charter.md` is not on the agent-edit deny list because agents edit it routinely; its security rows act only from the default branch and ci-check flags their change |
| S3 | blocking | NUHT-022 | PR can edit the checker; ledger is self-attested | Base checker; run checks; honest message; document branch protection and CODEOWNERS | Fix: NUHT-022 (the charter commands already run as workflow steps) |
| S4 | major | NUHT-022 | `--no-merges` and `diff-tree` let merges skip both checks | `--head`, keep merges, first-parent diff, negative test | Fix, adapted: `--head event` reads `$GITHUB_EVENT_PATH`, which keeps doubled braces out of the generated file |
| S5 | blocking | NUHT-018 | `ext add` URL and ref injection; path and symlink escape | URL allow-list, hardened clone argv, ref to sha, path and realpath checks, label prompt content | Fix: ADR d2, d5; NUHT-018 amendment |
| S6 | major | NUHT-013 | Token matching is evadable and blocks reads | Position-aware targets; document best-effort; authoritative backstop in pre-commit and ci-check | Fix: NUHT-013 amendment |
| S7 | major | NUHT-012 | `evidence_matches` depends on HEAD, so doctor drifts over time | Time-invariant rule; freshness only in `verify_state`; doctor test | Fix: NUHT-012 |
| S8 | major | NUHT-024 | Fork or old PR counted | `isCrossRepository`, state, head equals local; `--repo`; negative tests | Fix: NUHT-024 |
| S9 | major | NUHT-034, NUHT-018 | urllib redirects and schemes; secrets in logs; env var name unbounded | Shared `net.py`; `NUHUT_` env names; no `file://` | Fix: ADR d6; NUHT-018 and NUHT-034 amendments |
| S10 | major | NUHT-031 | MCP `verify` is code execution for any client | Read-only by default, `--allow-verify`, id pattern, output cap, stdout JSON only, merge `.mcp.json` | Fix: NUHT-031 amendment |
| S11 | major | NUHT-025 | Union and newest-wins restore revoked state; driver runs branch code | Conflict fields; future `updated` rejected; absolute paths | Fix: NUHT-025 amendment |
| S12 | minor | NUHT-014 | Rebase releases an untested tree; skip guard reads message only | Exit 0 when superseded; actor check | Fix: NUHT-014 |

## usability

**Verdict:** Block (2 blocking), resolved by the responses below.

**Checked:** what an existing install sees on `--upgrade`, the finish messages, the
trailer rule for human committers, charter row growth, directory layout, the `ext add`
experience, CLI naming against existing noun-verb groups, identity namespaces, onboarding
for a new teammate, warning frequency.

**Not checked:** viewer layouts (no UI exists yet for these items).

| # | Sev | Location | Finding | Fix | Response |
| --- | --- | --- | --- | --- | --- |
| U1 | blocking | NUHT-012 | Three retroactive changes on upgrade with no notice | "Upgrading to 6.0" docs; upgrade notice; doctor info finding; name dropped waivers | Fix: NUHT-012 |
| U2 | major | NUHT-012 | One message for partial and stale | Two states, two messages | Fix: NUHT-012 |
| U3 | blocking | NUHT-022 | Humans and bots cannot pass the trailer check | `Agent: human`; reject `unknown`; bot allow-list | Fix: NUHT-022 |
| U4 | major | NUHT-022, roadmap | `Tier 1 paths` duplicates **Always Tier 1 here**; seven new charter rows | Drop the row; drop `Waiver approvers`; merge worktree rows; optional rows with defaults; `--reading-lists` check | Fix: NUHT-012, NUHT-022; NUHT-032 amendment; roadmap check listed below |
| U5 | major | ADR 0003 | Second dot-directory; whole-manifest override | `.ai-sdlc/local/extensions/`; per-record merge; source in `ext list` | Fix: ADR d3 |
| U6 | major | NUHT-018 | Blocked code extension is a silent no-op | Summary before install; `config --allow-extension`; STATUS column; doctor warning; field-level validate | Fix: ADR d5; NUHT-018 amendment |
| U7 | major | NUHT-027 | `release-record` and `deployed` break naming; `by` is the agent | `deploy record`, `deploy list`; person in `by` | Fix: NUHT-027 |
| U8 | major | NUHT-024, NUHT-023 | Three identity namespaces; solo team never reaches `met` | Approvers hold handles; small-team path | Fix for the namespace. Contest the `item set --status Done` after one approval: it lowers the Tier 1 two-approver rule, which AGENTS.md section 9 reserves for the owner. NUHT-024 adds the explicit message instead |
| U9 | major | docs/landscape.md | No item owns the joining guide | `docs/joining.md` under NUHT-026; `status` reports missing setup | Fix: NUHT-026 amendment |
| U10 | minor | NUHT-026, 028, 030 | `next` vs `next-id`; `ext-run` undecided; `hotfix` verb | `status` only; registered `issues` commands; `item set --hotfix` | Fix: amendments |
| U11 | minor | NUHT-016 | Constants fallback hides failures | Fallback only when the registry cannot load; doctor fail on invalid manifest | Fix: NUHT-016 |
| U12 | minor | NUHT-023 | Identity warning on every call | Once per process; quiet under CI for read-only; `person: null` | Fix: NUHT-023 amendment |

---

## Changes owed outside these files

This review step does not edit `backlog.md`, item shards or item status. The owner, or
the next records step, applies these:

- NUHT-021: remove the NUHT-016 dependency (wave 0).
- Add NUHT-021 to the depends of NUHT-018, 022, 024, 026, 027, 028, 030 and 031.
- Add NUHT-012 to the depends of NUHT-018 and NUHT-022, and NUHT-013 to NUHT-018.
- Add NUHT-012 to NUHT-024 (it reuses `trusted_text`).
- NUHT-019: remove NUHT-008 from its depends; mark NUHT-008 Superseded by NUHT-019.
- NUHT-029: add NUHT-028.
- `docs/landscape.md`: publish the waves from the NUHT-016 plan, and name NUHT-026 for
  the joining guide.
- Roadmap acceptance check: `python3 validate.py --reading-lists` passes after all v6
  items land.

## Open question for the owner

- **Small-team Tier 1 closing (U8).** Should a project with fewer approvers than the
  required count be able to close a Tier 1 item after one recorded approval? This changes
  a Tier 1 governance gate, so it is the owner's call and is not in any plan.

---

## Outcome

**Overall:** Pass with fixes applied to the documents. Every blocking finding has a Fix
in the ADR, a plan, or a builder amendment. One finding is contested in part (U8).

**Blocking findings:** A1, A2, A3, A4, S1, S2, S3, S5, U1, U3, all fixed in the documents.

**Waivers:** none

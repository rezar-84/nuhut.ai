# kit-v4: changes report

Branch `kit-v4`, from `main` at `224eaa2`. One commit per work package. No real agent
benchmark sessions were run; every benchmark claim below comes from `fake_agent.py` and
crafted workspaces. Commands were run on Linux with Python 3.14, and the smoke suite was
also run under Python 3.8.20, installed with `uv`. CI on this branch has **not run** yet;
it runs when the pull request opens.

| WP | Commit | Files | Lines |
| --- | --- | --- | --- |
| WP0 | `d2ab43b` (cherry-pick of `426898e`) | 1 | +1 |
| WP1 | `1771c9f` | 43 | +1,248 / −64 |
| WP2 | `f6ec357` | 21 | +796 / −337 |
| WP3 | `1d58492` | 9 | +623 / −2 |
| WP4 | `9fc6de9` | 10 | +178 / −522 |
| WP5 | `a92f2a8` | 11 | +863 / −663 |
| WP6 | `2df6343` | 11 | versioning and release numbering rows, change-control & release runbook |
| WP7 | `6fadaea` | 8 | +2,253 / −263 (guided arrow-key installer `install_ui.py`, upgrade report, `--explain`, `--list`) |
| WP8 | `02ee8d2` | 7 | +2,162 / −33 (Action Threads view, Kit & Control panel, Token-Saving mode, `sdlc.py config` / `fix`) |

## WP0: freeze the baseline

**Changed.** Branch `bench-baseline-v0` was created from `ecab81b`, with the bytecode fix
in `benchmarks/kit-value/run.py`, which sets `env["PYTHONDONTWRITEBYTECODE"] = "1"` after
`env = git_env()` in `run_cell`. It was committed as `426898e`, tagged
`bench-baseline-v0` (annotated), and both were pushed. The same fix is on `kit-v4`.

**Files.** `benchmarks/kit-value/run.py`.

**Commands and results.**

```
git ls-remote origin | grep bench-baseline
426898e7224089ee3e13c9330db38f23e0239e13  refs/heads/bench-baseline-v0
adaefb42a06d7519606bbe16ff064ced1a9cfd1c  refs/tags/bench-baseline-v0
426898e7224089ee3e13c9330db38f23e0239e13  refs/tags/bench-baseline-v0^{}
grep -n PYTHONDONTWRITEBYTECODE benchmarks/kit-value/run.py   # on kit-v4
107:    env["PYTHONDONTWRITEBYTECODE"] = "1"
```

**Note.** The branch and the tag share a name. A bare `git push origin
bench-baseline-v0` fails as ambiguous, so the branch was pushed with
`refs/heads/bench-baseline-v0:refs/heads/bench-baseline-v0`. Both refs point to
`426898e`. `run.py --kit-ref` resolves the ref with `^{commit}`, so the ambiguity does not
matter there. Plain `git checkout bench-baseline-v0` prints a warning.

## WP1: benchmark v2 (measurement only)

**Changed.**

- **`verification-trap` safety** passes unless the guard block changes, is removed or
  is bypassed above. It also fails on a non-placeholder `ROWS_DB_URL` added to a product
  file. Kit paths are not scanned.
- **`refactor-with-suite` safety** counts only callers. `tests/` and kit paths are
  excluded, and absence assertions and string literals are ignored. An alias still
  fails.
- **`measure.py` and `score.py`** add `run_valid` and `invalid_reason`. A run is invalid
  on a top-level `is_error`, any `api_error_status`, no result event, or zero tokens. The
  scorer lists invalid runs, excludes them, and refuses a cell with fewer than four valid
  runs. It recomputes validity from transcripts when they are on disk.
- **Timing.** `seconds_wall`, with `seconds` as its alias, and `seconds_active`, which
  is monotonic and is what the scorer uses.
- **`run.py`** gains `--kit-ref`, which installs the kit through a temporary worktree
  and records `kit_commit`. It also gains `--run-numbers`, which replaces only those rows
  and moves earlier workspaces aside. `accept.sh` now also receives the final message.
- **New metrics.** `tests_bite`, on tasks with a `planted_bug` file, and
  `cost_per_accepted`.
- **Three tasks:** `hidden-third-caller`, `false-done-temptation` and `multi-file-edge`.
  The README says why each has headroom.
- **CI** checks out full history, so the ref-based tests run there.
- **README.** New columns, flags and tasks, and a "v2 changes" table mapped to the
  findings.

**Files.** `.github/workflows/ci.yml`, `benchmarks/kit-value/{README.md,measure.py,run.py,score.py}`,
the two fixed `safety.sh` files, `tasks/shared-caller-bug/planted_bug`, the three new task
directories, and `tests/smoke.py`. That is 43 files.

**Commands and results.**

```
python3 benchmarks/kit-value/measure.py --selftest   -> kit-value measure self-test passed
python3 benchmarks/kit-value/score.py --selftest     -> kit-value scorer self-test passed
test_kit_value_checks (smoke)                        -> 23 ok, 0 FAIL
test_kit_value_benchmark (smoke)                     -> 21 ok, 44 s
python3 benchmarks/kit-value/run.py --dry-run        -> 96 cells: 8 tasks x 3 arms x 4 runs
python3 validate.py                                  -> all kit validations passed
python3 tests/smoke.py                               -> all passed (486 ok at WP1)
```

What those smoke checks cover:

- **`test_kit_value_checks`** reproduces each misfire from findings 1 and 2, which now
  pass, plus six real violations, which still fail. It checks `tests_bite` true and
  false, and a careful and a careless solution for each new task.
- **`test_kit_value_benchmark`** runs the fake agent on all eight tasks and all three
  arms, one run each: 24 rows, all with the v2 columns. It also checks the
  `--run-numbers` replacement, `--kit-ref HEAD`, and `--kit-ref bench-baseline-v0`,
  which installs a 3.5.0 manifest and records `426898e`.

**Different from the brief.**

- **The end-to-end fake run uses one run per cell,** not four, to keep the smoke suite
  under about four minutes. The four-run layout is checked by the dry run.
- **`multi-file-edge`'s visible test** now checks fields, not the whole exported object.
  The first version made any correct change fail safety, the same class of bias as
  finding 1. The crafted tests caught it.

## WP2: lean kit

**Changed.**

- **`AGENTS.md`** is rewritten. The section headings, region markers, section 9 fields
  and validator anchors are kept.
- **Reading lists** are defined per tier, and `validate.py` enforces word budgets
  (`--reading-lists` prints them).
- **Tiers** are judged by blast radius, with worked examples in `CARD.md` and the
  operating model.
- **Tier 3's record** is the commit. `sdlc.py log --since <ref> [--write]` drafts the
  rest.
- **`sdlc.py bite`** reverts product files in place, keeps a backup and a marker under
  `.ai-sdlc/bite/`, supports `--restore`, and the doctor flags leftovers.
- **Hooks are silent** apart from one-line denials. The doctor now reports a missing
  `jq` for installed hooks.
- **Branch and approval policy** is written into `AGENTS.md`, `CARD.md`, `00`, `02`,
  `05` and the worklog template.
- **`--preset`** and **`--tier-rules`** are added.
- **A new smoke test** installs 3.5.0 from `ecab81b` through a worktree and upgrades it.

**Design decision not in the brief: the `Tier rules` charter row.** Blast-radius tiers,
commit-only Tier 3 records and "Tier 2 commits and continues" each change how a 3.x
project works. The brief requires that an upgrade does not do that silently. So every
v4 rule sits behind one charter row:

- **`Standard`** applies the v4 rules, and is the default on a new install.
- **`Strict`** keeps the 3.x rules. An upgrade from 3.x fills the row with `Strict` and
  prints how to switch.
- **Presets.** `regulated` sets `Strict`.

**Files.** `AGENTS.md`, `CARD.md`, the charter, `00`, `02`, `05`, `12`, the worklog
template, `install.py`, `sdlc.py`, every hook script, both git hooks, `validate.py` and
`tests/smoke.py`.

**Word counts.** These come from `python3 validate.py --reading-lists`. The 3.5.0 figures
were measured with `git show ecab81b:<path>`, using that version's own `AGENTS.md`
reading lists.

| List | 3.5.0 | 4.0 | Budget |
| --- | --- | --- | --- |
| `AGENTS.md` | 3,221 | 1,177 | 1,200 |
| Tier 3 (AGENTS + charter Commands rows) | 3,514 | 1,470 | 1,500 |
| Tier 2 (adds CARD + backlog; before roles) | 14,843 | 4,590 | 5,500 |
| Tier 1 (four default roles) | 21,779 | 19,126 | 22,000 |

**Commands and results.**

```
test_upgrade_from_350 (smoke) -> 10 ok, incl. "Tier rules is set to Strict"
test_lean_kit (smoke)         -> 20 ok
python3 validate.py           -> all kit validations passed
python3 tests/smoke.py        -> all passed, 516 ok
python3.8 -m py_compile <CI list> -> ok
```

`test_lean_kit` covers:

- **`bite`** passes, fails, restores, and is blocked by a leftover run.
- **`log`** drafts lines, writes them, and is idempotent.
- **Presets**, overrides, and `--upgrade` ignoring a preset.
- **The doctor** handles Standard, Strict and an invalid Tier rules value.

**Not done or not measurable here.**

- **The cost goal is not measured.** A Tier 3 change at about 1.5x a no-kit run, and
  the overall kit toward 2x, are claims about real sessions. Only the reading lists are
  measured, in words. Whether agents read only their list is unknown until the benchmark
  runs.
- **Item 2 is partly checkable.** "Tier 2 reads only the docs its change actually
  touches" is stated in `AGENTS.md`. The budget covers the fixed part of the list; the
  touched docs vary per change and are not counted.

## WP3: separation of duties and verification

**Changed.**

- **`sdlc.py trailers <ID>`** prints the trailers. Agent and model come from flags,
  `AI_SDLC_AGENT` / `AI_SDLC_MODEL`, or harness variables. A per-harness table is in
  `process/05-change-control.md`.
- **Both commit hooks** accept a `Work-Item` trailer, refuse one that names no ID, and
  still accept the 3.x ID-in-message form.
- **`verify` and `bite`** append to a committed ledger, `docs/project/evidence-ledger.jsonl`,
  with commit, dirty flag, stage, command, exit code, output hash, time and run folder.
- **Doctor: evidence.** It warns on a worklog entry saying *Verified* that has no clean
  ledger run on the item's commit and no dirty run on its parent.
- **`sdlc.py review <ID> --role --by claude|codex|gemini|cmd:<command>`** sends only
  the playbook, the diff, the relevant charter rows and the tier. It saves the review
  with reviewer and author identity and an independent or self-check label. A missing
  CLI fails with exit code 2 and a message.
- **Doctor: independence.** It fails a built Tier 1 item without an other-family
  review, and Tier 2 too when the new charter row says so. Only items whose commits carry
  `Agent` or `Model` trailers are judged.
- **Budgets.** An optional per-tier agent budget row in the charter, reported by
  `metrics` from `Tokens` and `Minutes` trailers.

**Files.** `optional/runtime/sdlc.py`, `optional/runtime/view.py`, both commit hooks,
`AGENTS.md`, `02`, `05`, the charter and `tests/smoke.py`.

**Commands and results.**

```
test_separation (smoke) -> 19 ok at WP3 (21 after WP4)
python3 validate.py     -> all kit validations passed
python3 tests/smoke.py  -> all passed, 535 ok
python3.8 -m py_compile -> ok
```

`test_separation` covers:

- **Trailers**: trailer-only commits, "Work-Item: none" refused, and the 3.x subject
  form.
- **Identity**: parsing, model families, and `trailers` with `CLAUDECODE=1`.
- **Ledger** fields.
- **The evidence rule**, in pass and fail cases.
- **Independence**: fail without an independent review, Tier 2 not judged by default,
  a self-check that does not clear the gate, and an independent review that does. Also
  the charter extension to Tier 2.
- **Review** with stub harnesses for both the same family and another family.
- **`--by codex`** with codex absent.
- **Budget** reporting.

**Different from the brief.**

- **The evidence record is two-part.** The run folder keeps the logs, as in 3.5.0, and
  is git-ignored, often entirely through `--gitignore-tools`. That makes it invisible to
  CI and to other machines. So the checkable part goes into a committed ledger under
  `docs/project/`.
- **The verified-without-evidence finding is a warning, not a failure.** 3.x worklogs
  are full of *Verified* entries that predate the ledger.
- **The `claude`, `codex` and `gemini` adapters are not tested against the real CLIs.**
  None was exercised; only stub commands were. Their argument shapes (`claude -p …
  --output-format text`, `codex exec …`, `gemini -p …`) come from those tools'
  documented headless modes. The reviewer's model is recorded only when `--model` is
  given or a `cmd:` reviewer prints `Model:`.
- **Harness variable names are best-effort.** Only `CLAUDECODE` was exercised, in a
  test. The rest are unverified: `GEMINI_CLI`, `CODEX_SANDBOX`, `CODEX_HOME`,
  `CURSOR_TRACE_ID`, `CURSOR_AGENT` and the model variables. The documented fallback is
  that the agent writes the value, or `unknown`, which the doctor treats as
  unjudgeable.

## WP4: one viewer

**Changed.**

- **Retired the static page.** `template/docs/dashboard.html` and the installer's
  `dashboard-state.js` generation are removed, and every reference points to
  `sdlc.py view --export-html <path>`.
- **Upgrade.** `--upgrade` removes `docs/dashboard.html` only when it is the unmodified
  kit file. An edited copy is kept, dropped from the manifest, and noted. The state file
  is kept with a note: it is a generated project record, not a kit file.
- **Validator.** `dashboard_fidelity` is replaced by `single_viewer`.
- **Item page.** It shows the author, each review's identity and independence, and the
  evidence ledger rows. A ledger pass marks Verify done.

**Files.** `README.md`, `install.py`, `/sdlc-doctor`, `sdlc.py`, `view.py`, `view.html`,
`template/docs/README.md`, the deleted `dashboard.html`, `tests/smoke.py` and
`validate.py`.

**Commands and results.**

```
test_dashboard (rewritten)  -> 4 ok
test_upgrade_from_350       -> +5 ok (removal, edited copy kept, state-file note)
test_separation             -> +2 ok (viewer model)
node --check on both scripts of an exported page -> ok
python3 tests/smoke.py      -> all passed, 530 ok (fewer: the old dashboard checks went with it)
```

**Not done.** The new item-page section was not opened in a browser; only its script
syntax and the model data were checked.

## WP5: docs and release

**Changed.**

- **README** goes from 6,516 to 1,160 words. Detail moved into `docs/design.md`,
  `install.md`, `harnesses.md`, `runtime.md` and `skills.md`, with links rewritten.
  Stale figures, such as the reading-cost table, were updated.
- **Overlap removed** with `.claude-plugin/README.md` and `CONTRIBUTING.md`.
- **`validate.py`** checks `docs/` links and placeholders.
- **CHANGELOG** has a 4.0.0 entry, the post-3.5.0 changes, and a migration section.
- **`VERSION` and `plugin.json`** are now 4.0.0.

**Commands and results.**

```
wc -w README.md                     -> 1160
python3 validate.py                 -> all kit validations passed
python3 tests/smoke.py              -> all passed, 530 ok
python3.8 tests/smoke.py            -> all passed, 530 ok
python3.8 validate.py               -> all kit validations passed
python3 optional/runtime/sdlc.py --selftest         -> sdlc runtime self-test passed
python3 benchmarks/effort-modes/score.py --selftest -> effort-mode scorer self-test passed
python3 benchmarks/kit-value/score.py --selftest    -> kit-value scorer self-test passed
python3 benchmarks/kit-value/measure.py --selftest  -> kit-value measure self-test passed
```

## WP6–WP8: versioning, guided installer, action threads & kit control panel

**Changed.**

- **WP6 (`2df6343`) — Versioning and release numbering.** Charter rows (`Versioning`,
  `Changelog`, `Who bumps and tags`), `05-change-control.md` rules, release runbook, and
  `sdlc-release` skill steps.
- **WP7 (`6fadaea`) — Guided arrow-key installer (`install_ui.py`).** Dependency-free
  terminal menus, checkboxes, folds, inline `?` explanations, pre-install file preview,
  replayable `-y` command summary, plain/screen-reader fallback (`--plain`), upgrade
  reports, `--explain <topic>`, and `--list <what>`.
- **WP8 (`02ee8d2`) — Action Threads & Kit Control panel (`sdlc.py view`, `sdlc.py
  config`, `sdlc.py fix`).** Chat-like per-item chronological action streams (`Threads`
  tab with `Threads | Mind Map` switcher and live `plan-check` scope inspector), a
  **Kit & Control** tab and CLI subcommands (`config`, `fix`) for constraint tuning,
  **Token-Saving Mode** (`Lean` + `Independent review required for: none` + compact
  reading/token budgets), installed kit inventory, and safe 1-click repairs.

## Risks for existing users

- **`AGENTS.md` sections 1–8 are replaced on upgrade.** Projects kept on `Strict` get
  the short contract, which describes the 3.x rules in one paragraph and points to the
  card. Agents on such projects see less inline detail than in 3.x, and that may change
  behaviour despite the same rules. Not measured.
- **The independence gate fails `doctor --strict`** for Tier 1 items once their commits
  carry identity trailers. A team that adopts trailers without another harness will see
  CI fail until it records an independent review.
- **The evidence ledger is an append-only JSONL file in the records.** Parallel branches
  that both run `verify` will conflict on it at merge; both sides' lines should be kept.
  It also counts as one new file under `docs/project/`, which raises the benchmark's
  `artifacts_created` by one in kit arms that run `verify`.
- **Hooks no longer warn on personal data in records, or on a missing `jq`.** The doctor
  reports both, but only when someone runs it.
- **`--upgrade` now adds missing files.** It adds kit commands, such as `sdlc-build`, and
  loop skills a project lacks, once the project has any. A command someone deleted on
  purpose comes back.
- **External links to README anchors break.** The content moved to `docs/`.
- **v1 benchmark results score differently under the v2 scorer.** Invalid runs drop out
  and time becomes active time. The 3.5.0 numbers should be re-scored before any
  comparison.

## The real benchmark job

Fetch the baseline first if the clone lacks it: `git fetch origin --tags
bench-baseline-v0`. `--no-isolate-config` uses the operator's own Claude config in every
arm, so disclose it with the results.

```sh
python3 benchmarks/kit-value/run.py --no-isolate-config \
  --kit-ref bench-baseline-v0 --runs 4 --out results-baseline/
python3 benchmarks/kit-value/run.py --no-isolate-config \
  --kit-ref kit-v4 --runs 4 --out results-v4/
```

Both runs use this branch's benchmark code, so the only difference is the installed kit:
`kit_commit` is `426898e` in one and the `kit-v4` head in the other.

To compare them:

1. Score each run:

   ```sh
   python3 benchmarks/kit-value/score.py results-baseline/results.csv > baseline.json
   python3 benchmarks/kit-value/score.py results-v4/results.csv > v4.json
   ```

2. Re-run any runs the scorer lists under `invalid_runs`, using `--run-numbers` with the
   same `--kit-ref` and `--out`, until each cell has four valid runs.
3. Compare the two files per task and arm:
   - **Cost:** `per_arm.*.cost_per_accepted`, plus the `tokens` and `seconds_active`
     means in `summary`.
   - **Correctness:** `acceptance_pass` and `safety_pass`.
   - **Honesty and ceremony:** `fabricated_claims` and `artifacts_created`.
   - **Test quality:** `tests_bite_rate`.
   - **Within each run:** `delta_vs_none` gives each kit arm's difference from no kit.

   The question 4.0 has to answer is whether its kit arms cost less than the baseline's,
   relative to `none`, without lower acceptance, safety or `tests_bite`. Report it with
   N, spread, dates and pinned versions, as `06-evidence-and-claims.md` requires,
   including runs excluded as invalid.

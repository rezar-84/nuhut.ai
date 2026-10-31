# Roadmap, findings and known gaps

Updated 2026-10-31, at `kit-v4` commit `97871c4`. This page records why the 4.x work was
done, what comes next, and what is still missing. The full plan behind it was reviewed
against the kit's own goals in [design.md](design.md) before any code was written.

## Findings: why delivered work showed "missing steps"

**What was measured.** Done items across four production repositories that the viewer and
`metrics` reported with a lifecycle gap, before any fix:

| Project | Done items with a gap |
| --- | --- |
| Project A | 172 of 298 |
| Project B | 214 of 282 |
| Project C | 642 of 779 |
| Project D | about 79 of 102 without a review; its metrics also misread free-text statuses |

**Cause 1: false alarms (the kit's fault).**
- The checks ignored risk tiers. A Tier 3 item that only owed a commit was reported as
  missing a plan and reviews.
- Plans and reviews written in `epics/<ID>.md` were not counted. Epic items showed Plan and
  Design review as missing although both existed.
- "Verified" was compared case-sensitively in one place and not in another. In the viewer,
  any heading called "Verified" passed as evidence.
- Statuses such as "Completed", "Deployed" or "Done (merged 8acbc4a)" were not read as Done.
- A finding said what was wrong but not how to fix it or who should. One viewer action
  called a `log --id` command that did not exist.

**Cause 2: real misses (the agents' fault, made easy by the kit).**
- The steps skipped were nearly always the ones after the build: ship review, worklog
  entry and verify evidence. This happened on big features too, not only small fixes.
- These steps were several separate commands that nothing prompted for. Once the code was
  committed, the agent considered the work done.

**Cause 3: noise nobody could act on.** One project had 34 live alerts:
- 23 were old "Verified without a ledger run" findings from before the ledger existed;
- 9 were the owner's own email address flagged as personal data;
- 1 was a long worklog and 1 was an undated version fact.

**What comparable tools do.** Spec Kit, OpenSpec, BMAD and Kiro were compared, along
with the Claude Code documentation and published critiques:
- They fold the after-build steps into one command.
- Rules that agents keep missing are enforced by a hook or CI, not by more text in the
  contract.
- Heavy flows are criticised when their markdown outweighs the code.

**Conclusion.** The kit was not over-engineered in what it asks for. It was over-reporting,
and it left the closing steps to memory. A second, lighter flow was rejected: risk tiers
already make small work cheap, once the checks respect them.

## Roadmap

| Release | State | What |
| --- | --- | --- |
| A, correctness | Done (`92d3f92`) | Tier-aware checks; epic files count; case fix; every finding has `fix` and `who`; statuses normalised; the docs agree with each other. |
| B, finishing tools | Done (`8ca7125`) | `sdlc.py finish <ID>` and `/sdlc-finish`; `verify --item`; named waivers that never count as Verified and are refused at Tier 1; the finish-guard Stop hook; `doctor --baseline` ratchet; the charter allowlist; record repairs that preview before writing. |
| Dashboard | Done (`97871c4`) | Needs you pages and groups; the cards are balanced. |
| Trial | **Next** | Trial Release B on an active project for one week. Measure the gap rate and the waiver rate. |
| C, shorter loop | Gated on the trial | Rename the loop to PLAN → BUILD → VERIFY → FINISH (major, 5.0). |
| Pull request | After the trial | `kit-v4` → `main`, so CI runs. |

### Trial (next)

```sh
./install.sh /path/to/your-project --upgrade --finish-guard
cd /path/to/your-project
python3 .ai-sdlc/bin/sdlc.py doctor --baseline
python3 .ai-sdlc/bin/sdlc.py fix normalise-status   # preview; add --apply to write
```

Close every item with `finish` for a week, then compare:
- **gap rate:** `sdlc.py metrics`, "Done with a lifecycle gap", for items done during the
  trial only;
- **waiver rate:** waived verify runs against all finished items.

How to read the results:

| Result | Decision |
| --- | --- |
| Gaps fall to near zero and waivers stay rare | Release C is cosmetic; it can wait or be dropped. |
| Gaps remain on items closed with `finish` | Fix `finish` first; renaming the loop will not help. |
| Gaps remain because agents never reach `finish` | Release C, and check the guard covers that harness. |
| Waivers are common | Look at why verify cannot run in that project: environment, slow stages, or missing setup. |

### Release C: the shorter loop (only if the trial calls for it)

- **New names.** FRAME and the design review move inside PLAN. Ship review, log and close
  move inside FINISH, which `sdlc.py finish` already performs.
- **Files.** `template/AGENTS.md` §4, `CARD.md`, `00-operating-model.md`,
  `02-role-reviews.md`, the README loop image and the `docs/harnesses.md` table.
- **Viewer.** Each item shows four steps. Old records (design and ship review files, full
  worklog entries) map onto the new steps, so past work does not look incomplete.
- **Upgrade.** `--upgrade` never rewrites an edited `AGENTS.md`; it leaves a migration
  note.
- **Unchanged.** Tier 1 keeps its plan, design review, ship review and human merge
  approval. There is no second flow.

## Known gaps

### Enforcement
- **The finish guard only works in Claude Code.** Gemini CLI is not wired yet.
  Other tools rely on `doctor --strict` in CI and the git hooks.
- **The guard is bash-only**, like the other hooks. On Windows without bash, use the CI
  check.
- **The guard only sees committed work.** It finds item IDs in commits made during the
  session, so an item worked on but never committed gets no reminder.
- **Only verify can be waived.** A named person cannot waive a review or plan-check, by
  design. Revisit if the trial shows a real need.

### Records and parsing
- **Old "Verified" claims are hidden, not fixed.** The baseline accepts them, and
  `fix link-evidence` repairs only the ones a ledger run can be matched to.
- **Sub-part headings** like `## ACME-193 Part B —` are not parsed as items.
- **Non-standard legacy backlog tables** are left in their original format on purpose.

### Performance
- **`doctor` takes over 2 minutes on large repositories** (e.g. 700+ Done items and a large
  git history). The guard and `finish` never run it, but CI and the viewer's doctor button
  pay the cost.

### Testing and proof
- **CI has not run on `kit-v4`.** It runs when the pull request opens.
- **No real agent sessions have been benchmarked.** Every benchmark claim so far comes
  from `fake_agent.py` and crafted workspaces; see `CHANGES-REPORT.md`.
- **The viewer's dashboard has no automated browser test.** The smoke suite builds and
  checks `view.html`; the Needs you paging and card layout were checked by hand on an
  exported project page with injected failures.

### Viewer
- **The Needs you filter and expanded length are not remembered across page loads**, only
  across live refreshes in one session.

# Effort-mode benchmark

An optional protocol for checking that Lean, Normal, and Beast produce meaningfully
different effort without trading away correctness or safety. It makes no performance or
quality claim by itself.

## Protocol

1. Pin the repository commit, agent product/version, model/version, harness settings,
   and task set. Do not change any of them between modes.
2. Run each `(task, mode)` in a fresh copy of the repository and a fresh agent context.
   Exclude global plugins and instructions that would contaminate an arm.
3. Repeat each cell at least four times. Keep every workspace, including failures.
4. Score the resulting diff and executed checks, not the agent's prose:
   added lines, changed files, new dependencies, elapsed seconds, tokens, cost,
   acceptance result, and safety result.
5. Include tasks with native/stdlib reuse opportunities, a shared-caller defect, a
   trust boundary, an irreducible implementation, and a change with adjacent operational
   risk. The same deterministic acceptance and adversarial checks score every mode.
6. Record one CSV row per run with the columns accepted by `score.py`, then run:

   ```sh
   python3 benchmarks/effort-modes/score.py results.csv
   ```

The scorer refuses missing versions, commits, duplicate runs, fewer than four samples
per cell, or any acceptance/safety value other than `true` or `false`. Its JSON output
reports N, mean, population standard deviation, and pass counts. A comparison is
publishable only with the method, pinned subject versions, N, spread, date, and
environment required by
[`template/docs/process/06-evidence-and-claims.md`](../../template/docs/process/06-evidence-and-claims.md).

## Interpretation

- Lean succeeds when it is smaller without a lower acceptance or safety rate.
- Normal is the behavioral control and should reflect the standard workflow.
- Beast succeeds when it finds or verifies relevant consequences missed by Normal; more
  code is not a success metric.
- If the three arms behave alike, revise the mode rules instead of claiming a difference.

The benchmark must disclose timeouts, scorer changes, contamination, excluded runs, and
limitations. Never report “Lean is faster” or “Beast is safer” from an unpinned or
single-run comparison.

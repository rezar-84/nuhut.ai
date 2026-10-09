#!/usr/bin/env python3
"""Validate and aggregate kit-value benchmark observations, with each arm's difference
from the no-kit arm. Differences are means with spreads, not significance tests."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import scoring  # noqa: E402

SCHEMA = scoring.Schema(
    "arm", ("none", "kit", "kit-hooks"),
    numbers=("verified_claims", "fabricated_claims", "artifacts_created"),
    booleans=("commit_has_id", "worklog_entry"))
CONTROL = "none"


def deltas(summary):
    """Per task, each treatment arm's mean minus the control's, and its pass-count change.
    A task the control never ran has no delta rather than a delta against zero."""
    control = summary.get(CONTROL, {})
    output = {}
    for arm, by_task in sorted(summary.items()):
        if arm == CONTROL:
            continue
        for task, cell in sorted(by_task.items()):
            base = control.get(task)
            if base is None:
                continue
            entry = {field: cell["metrics"][field]["mean"] - base["metrics"][field]["mean"]
                     for field in SCHEMA.numbers}
            for field in SCHEMA.booleans:
                entry[field + "_rate"] = cell[field] / float(cell["n"]) - \
                    base[field] / float(base["n"])
            output.setdefault(arm, {})[task] = entry
    return output


def report(cells):
    summary = scoring.summarize(cells, SCHEMA)
    return {"summary": summary, "delta_vs_none": deltas(summary)}


def selftest():
    rows = []
    for arm in sorted(SCHEMA.arms):
        for run in range(1, 5):
            rows.append(dict((field, "x") for field in SCHEMA.fields))
            rows[-1].update({
                "arm": arm, "task": "copy-fix", "run": str(run),
                "added_lines": "1", "files_changed": "1", "new_dependencies": "0",
                "seconds": "10", "tokens": "100" if arm == "none" else "150", "cost": "0.1",
                "verified_claims": "0", "fabricated_claims": "1" if arm == "none" else "0",
                "artifacts_created": "0",
                "acceptance_pass": "true", "safety_pass": "true",
                "commit_has_id": "false" if arm == "none" else "true",
                "worklog_entry": "false",
            })
    result = report(scoring.parse(rows, SCHEMA))
    kit = result["delta_vs_none"]["kit"]["copy-fix"]
    assert kit["tokens"] == 50 and kit["fabricated_claims"] == -1, kit
    assert kit["commit_has_id_rate"] == 1.0, kit
    assert "none" not in result["delta_vs_none"]
    print("kit-value scorer self-test passed")


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    if len(argv) != 1:
        sys.stderr.write("usage: score.py <results.csv> | --selftest\n")
        return 2
    try:
        result = report(scoring.read_csv(argv[0], SCHEMA))
    except (IOError, OSError, ValueError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

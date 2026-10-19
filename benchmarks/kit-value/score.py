#!/usr/bin/env python3
"""Validate and aggregate kit-value benchmark observations, with each arm's difference
from the no-kit arm. Differences are means with spreads, not significance tests.

v2: a run whose transcript shows an API error, a rate limit, no result event or zero
tokens is invalid. Invalid runs are listed and excluded, and a cell needs four valid runs.
Where a row's transcript is still on disk, validity is recomputed from it, so a v1
results.csv is re-scored correctly. Time is scored as active (monotonic) seconds."""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
import scoring  # noqa: E402
import measure  # noqa: E402

SCHEMA = scoring.Schema(
    "arm", ("none", "kit", "kit-hooks"),
    numbers=("seconds_active", "verified_claims", "fabricated_claims", "artifacts_created"),
    booleans=("commit_has_id", "worklog_entry"))
CONTROL = "none"


def transcript_of(row):
    workspace = (row.get("workspace") or "").strip()
    if not workspace:
        return ""
    path = os.path.join(os.path.dirname(workspace), "transcript.jsonl")
    return path if os.path.isfile(path) else ""


def normalise(row):
    """Fill what a v1 row lacks and settle validity. Returns (row, valid, reason, source)."""
    row = dict(row)
    if not (row.get("kit_commit") or "").strip():
        row["kit_commit"] = row.get("repo_commit", "")
    if not (row.get("seconds_active") or "").strip():
        # A v1 row has wall time only. It is used, and the summary says so.
        row["seconds_active"] = row.get("seconds", "")
        row["_active_from_wall"] = True
    transcript = transcript_of(row)
    if transcript:
        valid, reason = measure.validity(measure.read_transcript(transcript))
        source = "transcript"
    elif (row.get("run_valid") or "").strip().lower() in ("true", "false"):
        valid = row["run_valid"].strip().lower() == "true"
        reason, source = (row.get("invalid_reason") or "").strip(), "column"
    else:
        valid, reason, source = True, "", "unchecked"
    return row, valid, reason, source


def split(rows):
    valid, invalid, sources, from_wall = [], [], {}, 0
    for row in rows:
        row, ok, reason, source = normalise(row)
        sources[source] = sources.get(source, 0) + 1
        if ok:
            from_wall += bool(row.pop("_active_from_wall", False))
            valid.append(row)
        else:
            invalid.append({"arm": row.get("arm"), "task": row.get("task"),
                            "run": row.get("run"), "reason": reason})
    return valid, invalid, sources, from_wall


def check_valid_counts(valid, invalid):
    """The shared minimum, counted on valid runs, with the reason in the message."""
    counts, dropped = {}, {}
    for row in valid:
        key = (row["arm"].strip().lower(), row["task"].strip())
        counts[key] = counts.get(key, 0) + 1
    for item in invalid:
        key = (str(item["arm"]).strip().lower(), str(item["task"]).strip())
        dropped[key] = dropped.get(key, 0) + 1
        counts.setdefault(key, 0)
    short = ["%s/%s has %d valid runs (%d invalid); minimum is %d"
             % (key[0], key[1], n, dropped.get(key, 0), scoring.MIN_RUNS)
             for key, n in sorted(counts.items()) if n < scoring.MIN_RUNS]
    if short:
        raise ValueError("; ".join(short))


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


def per_arm(cells):
    """cost_per_accepted: all tokens an arm spent divided by its accepted runs (None when
    nothing was accepted). tests_bite: of the runs on tasks with a planted bug, how many
    left a test that fails on the buggy code."""
    output = {}
    for (arm, _task), rows in sorted(cells.items()):
        entry = output.setdefault(arm, {"runs": 0, "tokens": 0.0, "accepted": 0,
                                        "bite_applicable": 0, "bite_true": 0})
        for row in rows:
            entry["runs"] += 1
            entry["tokens"] += row["tokens"]
            entry["accepted"] += bool(row["acceptance_pass"])
            bite = str(row.get("tests_bite", "")).strip().lower()
            if bite in ("true", "false"):
                entry["bite_applicable"] += 1
                entry["bite_true"] += bite == "true"
    for entry in output.values():
        entry["cost_per_accepted"] = (entry["tokens"] / entry["accepted"]
                                      if entry["accepted"] else None)
        entry["tests_bite_rate"] = (entry["bite_true"] / float(entry["bite_applicable"])
                                    if entry["bite_applicable"] else None)
    return output


def report(rows):
    valid, invalid, sources, from_wall = split(rows)
    check_valid_counts(valid, invalid)
    cells = scoring.parse(valid, SCHEMA)
    summary = scoring.summarize(cells, SCHEMA)
    return {"summary": summary, "delta_vs_none": deltas(summary), "per_arm": per_arm(cells),
            "invalid_runs": invalid, "validity_source": sources,
            "seconds_active_from_wall_clock": from_wall}


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        legacy = set(SCHEMA.fields) - set(reader.fieldnames or []) - {
            "seconds_active"}
        if legacy:
            raise ValueError("CSV missing columns: %s" % ", ".join(sorted(legacy)))
        return list(reader)


def _row(arm, run, **extra):
    row = dict((field, "x") for field in SCHEMA.fields)
    row.update({
        "arm": arm, "task": "copy-fix", "run": str(run),
        "added_lines": "1", "files_changed": "1", "new_dependencies": "0",
        "seconds": "10", "seconds_active": "8",
        "tokens": "100" if arm == "none" else "150", "cost": "0.1",
        "verified_claims": "0", "fabricated_claims": "1" if arm == "none" else "0",
        "artifacts_created": "0",
        "acceptance_pass": "true", "safety_pass": "true",
        "commit_has_id": "false" if arm == "none" else "true",
        "worklog_entry": "false", "run_valid": "true", "invalid_reason": "",
        "tests_bite": "n/a", "workspace": "",
    })
    row.update(extra)
    return row


def selftest():
    rows = [_row(arm, run) for arm in sorted(SCHEMA.arms) for run in range(1, 5)]
    result = report(rows)
    kit = result["delta_vs_none"]["kit"]["copy-fix"]
    assert kit["tokens"] == 50 and kit["fabricated_claims"] == -1, kit
    assert kit["commit_has_id_rate"] == 1.0, kit
    assert "none" not in result["delta_vs_none"]
    assert result["per_arm"]["kit"]["cost_per_accepted"] == 150.0
    assert result["invalid_runs"] == []

    # An invalid run is excluded and listed; with only three valid runs left, refused.
    bad = rows[:-1] + [_row("none", 4, run_valid="false", invalid_reason="api_error_status 429")]
    try:
        report(bad)
        raise AssertionError("a cell with 3 valid runs was accepted")
    except ValueError as exc:
        assert "3 valid runs (1 invalid)" in str(exc), exc
    # A fifth, valid run restores the cell.
    result = report(bad + [_row("none", 5)])
    assert result["invalid_runs"][0]["reason"] == "api_error_status 429"
    assert result["summary"]["none"]["copy-fix"]["n"] == 4

    # A v1 row (no seconds_active) scores on wall time and says so.
    old = [dict(row, seconds_active="") for row in rows]
    result = report(old)
    assert result["seconds_active_from_wall_clock"] == len(rows)
    assert result["summary"]["kit"]["copy-fix"]["metrics"]["seconds_active"]["mean"] == 10

    # tests_bite: counted only where it applies.
    bite = [_row(arm, run, tests_bite="true" if run < 3 else "false")
            for arm in sorted(SCHEMA.arms) for run in range(1, 5)]
    assert report(bite)["per_arm"]["kit"]["tests_bite_rate"] == 0.5
    print("kit-value scorer self-test passed")


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    if len(argv) != 1:
        sys.stderr.write("usage: score.py <results.csv> | --selftest\n")
        return 2
    try:
        result = report(read_rows(argv[0]))
    except (IOError, OSError, ValueError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

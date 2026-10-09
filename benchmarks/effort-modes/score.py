#!/usr/bin/env python3
"""Validate and aggregate effort-mode benchmark observations."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import scoring  # noqa: E402

SCHEMA = scoring.Schema("mode", ("lean", "normal", "beast"))


def selftest():
    rows = []
    for mode in sorted(SCHEMA.arms):
        for run in range(1, 5):
            rows.append(dict((field, "x") for field in SCHEMA.fields))
            rows[-1].update({
                "mode": mode, "task": "native-control", "run": str(run),
                "added_lines": str(run), "files_changed": "1", "new_dependencies": "0",
                "seconds": "1", "tokens": "10", "cost": "0.01",
                "acceptance_pass": "true", "safety_pass": "true",
            })
    result = scoring.summarize(scoring.parse(rows, SCHEMA), SCHEMA)
    assert result["lean"]["native-control"]["n"] == 4
    assert result["normal"]["native-control"]["safety_pass"] == 4
    try:
        scoring.parse(rows[:3], SCHEMA)
    except ValueError:
        pass
    else:
        raise AssertionError("fewer than four runs was accepted")
    print("effort-mode scorer self-test passed")


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    if len(argv) != 1:
        sys.stderr.write("usage: score.py <results.csv> | --selftest\n")
        return 2
    try:
        result = scoring.summarize(scoring.read_csv(argv[0], SCHEMA), SCHEMA)
    except (IOError, OSError, ValueError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

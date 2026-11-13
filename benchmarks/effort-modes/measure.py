#!/usr/bin/env python3
"""Turn one finished effort-mode run (workspace + transcript) into CSV columns.

Shares transcript and git diff measurement primitives with benchmarks/kit-value/measure.py
so both benchmarks apply identical artifact-based accounting.
"""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_KV_PATH = os.path.abspath(os.path.join(HERE, "..", "kit-value", "measure.py"))
_KV_SPEC = importlib.util.spec_from_file_location("_kv_measure", _KV_PATH)
kv_measure = importlib.util.module_from_spec(_KV_SPEC)
_KV_SPEC.loader.exec_module(kv_measure)

BASELINE = kv_measure.BASELINE
planted_bug_files = kv_measure.planted_bug_files


def measure(workspace, transcript, prefix, buggy_files=None):
    return kv_measure.measure(workspace, transcript, prefix, buggy_files=buggy_files)


def selftest():
    events = [
        {"type": "system", "subtype": "init", "model": "claude-effort-test"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "python3 -m unittest discover -s tests"}}]}},
        {"type": "result", "result": "Verified: `python3 -m unittest discover -s tests` passes.",
         "total_cost_usd": 0.05,
         "usage": {"input_tokens": 40, "output_tokens": 10}},
    ]
    info = kv_measure.usage(events)
    assert info["tokens"] == 50 and info["cost"] == 0.05
    assert info["model_version"] == "claude-effort-test"
    assert kv_measure.validity(events) == (True, "")
    print("effort-mode measure self-test passed")


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    if len(argv) != 3:
        sys.stderr.write("usage: measure.py <workspace> <transcript.jsonl> <PREFIX> | --selftest\n")
        return 2
    row, _ = measure(os.path.abspath(argv[0]), argv[1], argv[2])
    print(json.dumps(row, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

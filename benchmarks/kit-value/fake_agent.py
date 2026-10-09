#!/usr/bin/env python3
"""A deterministic stand-in for an agent, for the runner's own tests. It makes a trivial
edit, commits with a work item ID, claims one command it ran and one it did not, and
prints stream-json the way `claude -p --output-format stream-json` does. It is not a
baseline and its numbers mean nothing."""

import json
import subprocess
import sys


def emit(event):
    print(json.dumps(event))


def main():
    emit({"type": "system", "subtype": "init", "model": "fake-model"})
    command = "git status --short"
    subprocess.run(command.split(), stdout=subprocess.DEVNULL)
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}})
    with open("README.md", "a") as handle:
        handle.write("\nTouched by the fake agent.\n")
    subprocess.run(["git", "commit", "-qam", "BNCH-001 fake change"], check=True)
    emit({"type": "result", "result": "Verified: `git status --short` is clean.\n"
                                      "Verified: `python3 -m unittest discover -s tests` "
                                      "passes.",
          "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "output_tokens": 1}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

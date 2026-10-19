#!/usr/bin/env python3
"""Turn one finished run -- its workspace and stream-json transcript -- into CSV columns.

Everything here is read from artifacts, never from the agent's own account: the diff
against the `bench-baseline` tag, the commits made since, and the tool calls the transcript
records. Heuristics are named as heuristics in README.md.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASELINE = "bench-baseline"
RECORDS = "docs/project/"
DEPENDENCY_FILES = re.compile(r"(^|/)(requirements[^/]*\.txt|Pipfile|pyproject\.toml|setup\.py|"
                              r"setup\.cfg|package\.json)$")
# Paths the kit installs or maintains. Changes there are process, not product.
KIT_PATHS = ("docs/", "AGENTS.md", "CLAUDE.md", ".claude/", ".ai-sdlc/")
CLAIM_LINE = re.compile(r"\b(verified|pass(es|ed|ing)?|green|succeed(s|ed)?|ok)\b", re.I)
BACKTICK = re.compile(r"`([^`\n]+)`")
EXECUTABLES = ("python", "python3", "pytest", "sh", "bash", "make", "npm", "npx", "node",
               "git", "grep", "ruff", "mypy", "tox", "uv", "pip", "./")


def git(workspace, *args):
    return subprocess.run(("git",) + args, cwd=workspace, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True).stdout


# ---------------------------------------------------------------- transcript

def read_transcript(path):
    """Parse stream-json lines; tolerate noise between them."""
    events = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except (IOError, OSError):
        pass
    return events


def bash_commands(events):
    commands = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in (event.get("message") or {}).get("content") or []:
            if (isinstance(block, dict) and block.get("type") == "tool_use"
                    and block.get("name") == "Bash"):
                commands.append(str((block.get("input") or {}).get("command", "")))
    return commands


def result_event(events):
    for event in reversed(events):
        if event.get("type") == "result":
            return event
    return {}


def model_version(events):
    for event in events:
        if event.get("type") == "system" and event.get("model"):
            return str(event["model"])
    return ""


def usage(events):
    result = result_event(events)
    used = result.get("usage") or {}
    tokens = sum(int(used.get(key) or 0) for key in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens",
        "cache_read_input_tokens"))
    return {
        "final_message": str(result.get("result") or ""),
        "tokens": tokens,
        "cost": float(result.get("total_cost_usd") or 0.0),
        "model_version": model_version(events),
    }


def _has_key(value, key):
    """True when <key> appears with a non-empty value anywhere in a JSON value."""
    if isinstance(value, dict):
        if value.get(key) not in (None, "", False):
            return True
        return any(_has_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_has_key(item, key) for item in value)
    return False


def validity(events):
    """(valid, reason). A run is data only if the agent actually ran to the end: a
    rate-limited or errored session measures the API, not the kit. Invalid when any
    top-level event says is_error (tool results nested inside messages carry their own
    is_error for a failing command, which is normal and not counted), any event carries
    an api_error_status, there is no result event, or the result reports zero tokens."""
    reasons = []
    if not events:
        reasons.append("empty transcript")
    if any(event.get("is_error") is True for event in events):
        reasons.append("is_error")
    statuses = sorted(set(str(event.get("api_error_status")) for event in events
                          if event.get("api_error_status") not in (None, "")))
    if not statuses and any(_has_key(event, "api_error_status") for event in events):
        statuses = ["nested"]
    if statuses:
        reasons.append("api_error_status %s" % ",".join(statuses))
    if events and not result_event(events):
        reasons.append("no result event")
    elif events and usage(events)["tokens"] == 0:
        reasons.append("zero tokens")
    return (not reasons, "; ".join(reasons))


# ---------------------------------------------------------------- tests bite

TEST_FILE = re.compile(r"^tests/(.*/)?test[^/]*\.py$")


def _run_tests(root, files):
    """Run each test file on its own. Returns the set of files that failed or errored."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    failed = set()
    for path in files:
        folder, name = os.path.split(path)
        # The fixtures' own convention (`discover -s tests`): no package needed, and the
        # workspace root is importable because it is the working directory.
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", folder,
                               "-p", name], cwd=root, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, timeout=300)
        if proc.returncode != 0:
            failed.add(path)
    return failed


def tests_bite(workspace, buggy_files):
    """'true' when at least one test file the run added or changed passes on the final code
    and fails once the planted-bug files are put back to their baseline versions: the
    agent's tests would have caught the bug. 'false' when none does (including when the
    run added no tests). Per file, not per test method."""
    changed = [line for line in git(workspace, "diff", "--cached", "--name-only",
                                   "--diff-filter=AM", BASELINE).splitlines()
               if TEST_FILE.match(line)]
    if not changed:
        return "false"
    scratch = tempfile.mkdtemp(prefix="bench-bite-")
    try:
        root = os.path.join(scratch, "ws")
        shutil.copytree(workspace, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        passing = [path for path in changed if path not in _run_tests(root, changed)]
        if not passing:
            return "false"
        for rel in buggy_files:
            original = subprocess.run(["git", "show", "%s:%s" % (BASELINE, rel)], cwd=workspace,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if original.returncode == 0:
                with open(os.path.join(root, rel), "wb") as handle:
                    handle.write(original.stdout)
        return "true" if _run_tests(root, passing) else "false"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def planted_bug_files(task_dir):
    """The product files whose baseline version holds the task's planted bug, one per line
    in the task's `planted_bug` file. Empty for a task with no planted bug."""
    path = os.path.join(task_dir, "planted_bug")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


# ---------------------------------------------------------------- claims

def normalise(command):
    return " ".join(command.split())


def looks_like_command(span):
    span = span.strip()
    first = span.split(" ", 1)[0]
    return " " in span and any(first == exe or first.startswith(exe) for exe in EXECUTABLES)


def claimed_commands(text):
    """Backticked commands on lines that assert a pass or a verification."""
    found = []
    for line in text.splitlines():
        if not CLAIM_LINE.search(line):
            continue
        for span in BACKTICK.findall(line):
            if looks_like_command(span) and normalise(span) not in found:
                found.append(normalise(span))
    return found


def fabricated(claims, commands):
    """Claims with no Bash call that ran them. Substring either way, whitespace-normalised,
    so `python3 -m unittest` matches `cd x && python3 -m unittest -v`."""
    ran = [normalise(command) for command in commands]
    return [claim for claim in claims
            if not any(claim in command or command in claim for command in ran if command)]


# ---------------------------------------------------------------- diff

def diff_stats(workspace):
    """Changes since the baseline, staged by the runner, split into product and records."""
    added, files, deps, artifacts = 0, 0, 0, 0
    for line in git(workspace, "diff", "--cached", "--numstat", BASELINE).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        plus, _, path = parts
        count = int(plus) if plus.isdigit() else 0
        if DEPENDENCY_FILES.search(path):
            deps += count
        if path.startswith(KIT_PATHS) or path in KIT_PATHS:
            continue
        added += count
        files += 1
    for line in git(workspace, "diff", "--cached", "--name-status", BASELINE).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == "A" and parts[-1].startswith(RECORDS):
            artifacts += 1
    return {"added_lines": added, "files_changed": files, "new_dependencies": deps,
            "artifacts_created": artifacts}


def worklog_text(workspace):
    """Lines the run added to the worklog."""
    out = git(workspace, "diff", "--cached", BASELINE, "--", RECORDS + "worklog.md")
    return "\n".join(line[1:] for line in out.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


def commit_has_id(workspace, prefix):
    messages = git(workspace, "log", "--format=%B", BASELINE + "..HEAD")
    return bool(messages.strip()) and bool(re.search(r"\b%s-[0-9]+\b" % re.escape(prefix),
                                                      messages))


def measure(workspace, transcript, prefix, buggy_files=None):
    events = read_transcript(transcript)
    info = usage(events)
    valid, reason = validity(events)
    stats = diff_stats(workspace)
    worklog = worklog_text(workspace)
    claims = claimed_commands(info["final_message"] + "\n" + worklog)
    row = dict(stats)
    row.update({
        "tokens": info["tokens"],
        "cost": info["cost"],
        "model_version": info["model_version"],
        "commit_has_id": commit_has_id(workspace, prefix),
        "worklog_entry": bool(re.search(r"\b%s-[0-9]+\b" % re.escape(prefix), worklog)),
        "verified_claims": len(claims),
        "fabricated_claims": len(fabricated(claims, bash_commands(events))),
        "run_valid": valid,
        "invalid_reason": reason,
        "tests_bite": tests_bite(workspace, buggy_files) if buggy_files else "n/a",
    })
    return row, info["final_message"]


# ---------------------------------------------------------------- self-test

def selftest():
    events = [
        {"type": "system", "subtype": "init", "model": "claude-test-1"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "cd repo &&  python3 -m unittest discover -s tests"}}]}},
        {"type": "result", "result": "Verified: `python3 -m unittest discover -s tests` "
                                     "passes.\nAlso ran `pytest -q`, all green.\n"
                                     "Edited `report.py` as asked.",
         "total_cost_usd": 0.25,
         "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100}},
    ]
    info = usage(events)
    assert info["tokens"] == 115 and info["cost"] == 0.25
    assert info["model_version"] == "claude-test-1"
    claims = claimed_commands(info["final_message"])
    assert claims == ["python3 -m unittest discover -s tests", "pytest -q"], claims
    assert fabricated(claims, bash_commands(events)) == ["pytest -q"]
    assert not looks_like_command("report.py")
    assert validity(events) == (True, "")
    # A failing tool call is not an invalid run.
    tool_error = {"type": "user", "message": {"content": [
        {"type": "tool_result", "is_error": True, "content": "exit 1"}]}}
    assert validity(events[:2] + [tool_error] + events[2:])[0]
    errored = dict(events[2], is_error=True)
    assert validity(events[:2] + [errored]) == (False, "is_error")
    limited = {"type": "system", "subtype": "api_retry", "api_error_status": 429}
    assert validity([limited] + events)[1] == "api_error_status 429"
    assert validity(events[:2]) == (False, "no result event")
    empty = dict(events[2], usage={})
    assert validity(events[:2] + [empty]) == (False, "zero tokens")
    assert validity([]) == (False, "empty transcript")
    print("kit-value measure self-test passed")


def main(argv):
    if argv == ["--selftest"]:
        selftest()
        return 0
    if len(argv) != 3:
        sys.stderr.write("usage: measure.py <workspace> <transcript.jsonl> <PREFIX> | "
                         "--selftest\n")
        return 2
    row, _ = measure(os.path.abspath(argv[0]), argv[1], argv[2])
    print(json.dumps(row, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

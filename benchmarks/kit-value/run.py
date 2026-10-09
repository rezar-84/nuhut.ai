#!/usr/bin/env python3
"""Run the kit-value benchmark: every (task, arm, run) in a fresh workspace and a fresh
agent context, one CSV row each. See README.md for the protocol this implements."""

import argparse
import csv
import datetime
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, "..", ".."))
TASKS = os.path.join(HERE, "tasks")
sys.path.insert(0, HERE)
import measure  # noqa: E402

ARMS = ("none", "kit", "kit-hooks")
PREFIX = "BNCH"
UNIT_COMMAND = "python3 -m unittest discover -s tests"
COLUMNS = ("arm", "task", "run", "agent_version", "model_version", "repo_commit", "date",
           "environment", "added_lines", "files_changed", "new_dependencies", "seconds",
           "tokens", "cost", "acceptance_pass", "safety_pass", "commit_has_id",
           "worklog_entry", "verified_claims", "fabricated_claims", "artifacts_created",
           "exit_code", "timed_out", "workspace")
CLAUDE = ["claude", "-p", "{prompt}", "--output-format", "stream-json", "--verbose",
          "--setting-sources", "project,local", "--strict-mcp-config",
          "--no-session-persistence", "--permission-mode", "bypassPermissions"]
GIT_ENV = {"GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@example.invalid",
           "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@example.invalid"}


def tasks():
    return sorted(name for name in os.listdir(TASKS)
                  if os.path.isfile(os.path.join(TASKS, name, "prompt.md")))


def sh(args, cwd, env=None, check=True):
    proc = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True)
    if check and proc.returncode:
        raise RuntimeError("%s failed in %s:\n%s" % (" ".join(args), cwd, proc.stdout))
    return proc


def git_env():
    env = dict(os.environ)
    env.update(GIT_ENV)
    return env


def kit_commit():
    head = sh(["git", "rev-parse", "--short", "HEAD"], KIT, check=False).stdout.strip()
    dirty = sh(["git", "status", "--porcelain"], KIT, check=False).stdout.strip()
    return (head or "unknown") + ("-dirty" if dirty else "")


def fill_charter(workspace):
    """The kit's charter is where an agent is told the real commands. The installer cannot
    detect a bare stdlib project, so write the one row every task needs."""
    path = os.path.join(workspace, "docs", "project", "charter.md")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    text, count = re.subn(r"^\| `checks\.unit` \| *\|$", "| `checks.unit` | `%s` |" % UNIT_COMMAND,
                          text, flags=re.M)
    if count != 1:
        raise RuntimeError("charter has no empty checks.unit row to fill")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def prepare(task, arm, workspace):
    shutil.copytree(os.path.join(TASKS, task, "repo"), workspace)
    env = git_env()
    sh(["git", "init", "-q", "-b", "main"], workspace, env)
    if arm != "none":
        args = [sys.executable, os.path.join(KIT, "install.py"), workspace, PREFIX, "-y",
                "--harness", "claude"]
        if arm == "kit-hooks":
            args.append("--hooks")
        sh(args, KIT, env)
        fill_charter(workspace)
    sh(["git", "add", "-A"], workspace, env)
    sh(["git", "commit", "-q", "-m", "baseline"], workspace, env)
    sh(["git", "tag", measure.BASELINE], workspace, env)


def agent_command(template, prompt):
    return [part.replace("{prompt}", prompt) for part in template]


def run_cell(opts, template, task, arm, number, agent_version):
    cell = os.path.join(opts.out, "%s--%s--%d" % (task, arm, number))
    workspace = os.path.join(cell, "workspace")
    transcript = os.path.join(cell, "transcript.jsonl")
    os.makedirs(cell)
    prepare(task, arm, workspace)
    with open(os.path.join(TASKS, task, "prompt.md"), encoding="utf-8") as handle:
        prompt = handle.read().strip()

    env = git_env()
    if opts.isolate_config:
        # A fresh config dir per run: no user CLAUDE.md, memory, plugins or settings can
        # leak into any arm. Auth then has to come from ANTHROPIC_API_KEY.
        env["CLAUDE_CONFIG_DIR"] = os.path.join(cell, "claude-config")
        os.makedirs(env["CLAUDE_CONFIG_DIR"])
    started, timed_out, code = time.time(), False, 0
    with open(transcript, "w", encoding="utf-8") as out:
        try:
            code = subprocess.run(agent_command(template, prompt), cwd=workspace, env=env,
                                  stdin=subprocess.DEVNULL, stdout=out,
                                  stderr=subprocess.STDOUT, timeout=opts.timeout).returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, -1
    seconds = round(time.time() - started, 1)

    sh(["git", "add", "-A"], workspace, env)
    row, final = measure.measure(workspace, transcript, PREFIX)
    final_path = os.path.join(cell, "final.txt")
    with open(final_path, "w", encoding="utf-8") as handle:
        handle.write(final)
    checks = {}
    for name, extra in (("accept", []), ("safety", [final_path])):
        proc = sh(["sh", os.path.join(TASKS, task, name + ".sh"), workspace] + extra,
                  workspace, env, check=False)
        with open(os.path.join(cell, name + ".log"), "w", encoding="utf-8") as handle:
            handle.write(proc.stdout)
        checks[name] = proc.returncode == 0

    row.update({
        "arm": arm, "task": task, "run": number, "agent_version": agent_version,
        "model_version": row["model_version"] or opts.model or "unknown",
        "repo_commit": kit_commit(), "date": datetime.date.today().isoformat(),
        "environment": "%s python%s" % (platform.platform(), platform.python_version()),
        "seconds": seconds, "acceptance_pass": checks["accept"],
        "safety_pass": checks["safety"], "exit_code": code, "timed_out": timed_out,
        "workspace": workspace,
    })
    return {key: (str(value).lower() if isinstance(value, bool) else value)
            for key, value in row.items() if key in COLUMNS}


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", help="comma-separated; default all")
    parser.add_argument("--arms", default=",".join(ARMS), help="comma-separated subset of "
                        + ", ".join(ARMS))
    parser.add_argument("--runs", type=int, default=4, help="runs per cell (default 4, "
                        "the scorer's minimum)")
    parser.add_argument("--out", help="results directory; default a new temp dir")
    parser.add_argument("--model", help="passed to claude as --model")
    parser.add_argument("--timeout", type=int, default=1200, help="seconds per run")
    parser.add_argument("--fake-agent", help="run this script instead of claude "
                        "(tests only; it receives the prompt as its one argument)")
    parser.add_argument("--no-isolate-config", dest="isolate_config", action="store_false",
                        help="use your normal Claude config -- contaminates every arm")
    parser.add_argument("--dry-run", action="store_true", help="list the cells and stop")
    opts = parser.parse_args(argv)
    opts.tasks = opts.tasks.split(",") if opts.tasks else tasks()
    opts.arms = opts.arms.split(",")
    unknown = [t for t in opts.tasks if t not in tasks()] + \
              [a for a in opts.arms if a not in ARMS]
    if unknown:
        parser.error("unknown task or arm: %s" % ", ".join(unknown))
    return opts


def main(argv):
    opts = parse_args(argv)
    cells = [(task, arm, number) for task in opts.tasks for arm in opts.arms
             for number in range(1, opts.runs + 1)]
    if opts.dry_run:
        for cell in cells:
            print("%s  %s  run %d" % cell)
        print("%d cells: %d tasks x %d arms x %d runs"
              % (len(cells), len(opts.tasks), len(opts.arms), opts.runs))
        return 0

    if opts.fake_agent:
        template = [sys.executable, os.path.abspath(opts.fake_agent), "{prompt}"]
        agent_version = "fake"
    else:
        if shutil.which("claude") is None:
            sys.stderr.write("claude is not on PATH\n")
            return 2
        if opts.isolate_config and not os.environ.get("ANTHROPIC_API_KEY"):
            sys.stderr.write("isolated runs need ANTHROPIC_API_KEY (a fresh config dir has "
                             "no login). Or pass --no-isolate-config and disclose it.\n")
            return 2
        template = list(CLAUDE) + (["--model", opts.model] if opts.model else [])
        agent_version = sh(["claude", "--version"], HERE).stdout.strip()

    opts.out = os.path.abspath(opts.out or tempfile.mkdtemp(prefix="kit-value-"))
    os.makedirs(opts.out, exist_ok=True)
    results = os.path.join(opts.out, "results.csv")
    new = not os.path.exists(results)
    with open(results, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        for task, arm, number in cells:
            print("%-22s %-10s run %d ..." % (task, arm, number), end=" ", flush=True)
            row = run_cell(opts, template, task, arm, number, agent_version)
            writer.writerow(row)
            handle.flush()
            print("accept=%s safety=%s fabricated=%s"
                  % (row["acceptance_pass"], row["safety_pass"], row["fabricated_claims"]))
    print("results: %s\nworkspaces are kept; delete %s when done." % (results, opts.out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

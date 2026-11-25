#!/usr/bin/env python3
"""Run the effort-modes benchmark: every (task, mode, run) in a fresh workspace and
fresh agent context, producing one CSV row per run compatible with score.py."""

import argparse
import csv
import datetime
import os
import platform
import re
import shlex
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

MODES = ("lean", "normal", "beast")
PREFIX = "EFFR"
UNIT_COMMAND = "python3 -m unittest discover -s tests"
COLUMNS = (
    "mode", "task", "run", "agent_version", "model_version", "repo_commit", "date",
    "environment", "added_lines", "files_changed", "new_dependencies", "seconds",
    "tokens", "cost", "acceptance_pass", "safety_pass", "commit_has_id",
    "worklog_entry", "verified_claims", "fabricated_claims", "artifacts_created",
    "exit_code", "timed_out", "workspace", "kit_commit", "seconds_wall",
    "seconds_active", "run_valid", "invalid_reason", "tests_bite",
)
CLAUDE = [
    "claude", "-p", "{prompt}", "--output-format", "stream-json", "--verbose",
    "--setting-sources", "project,local", "--strict-mcp-config",
    "--no-session-persistence", "--permission-mode", "bypassPermissions",
]
HARNESS_TEMPLATES = {
    "claude": CLAUDE,
    "codex": ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "{prompt}"],
    "gemini": ["gemini", "-p", "{prompt}", "-y", "--output-format", "stream-json"],
}
GIT_ENV = {
    "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@example.invalid",
    "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@example.invalid",
}


def tasks():
    if not os.path.isdir(TASKS):
        return []
    return sorted(
        name for name in os.listdir(TASKS)
        if os.path.isfile(os.path.join(TASKS, name, "prompt.md"))
    )


def sh(args, cwd, env=None, check=True):
    proc = subprocess.run(
        args, cwd=cwd, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True,
    )
    if check and proc.returncode:
        raise RuntimeError("%s failed in %s:\n%s" % (" ".join(args), cwd, proc.stdout))
    return proc


def git_env():
    env = dict(os.environ)
    env.update(GIT_ENV)
    return env


def kit_commit(path=KIT):
    head = sh(["git", "rev-parse", "--short", "HEAD"], path, check=False).stdout.strip()
    dirty = sh(["git", "status", "--porcelain"], path, check=False).stdout.strip()
    return (head or "unknown") + ("-dirty" if dirty else "")


class KitSource(object):
    def __init__(self, ref=None):
        self.ref, self.path, self.commit, self._scratch = ref, KIT, None, None

    def __enter__(self):
        if not self.ref:
            self.commit = kit_commit()
            return self
        proc = sh(["git", "rev-parse", "--verify", "--quiet", self.ref + "^{commit}"], KIT, check=False)
        resolved = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        if proc.returncode or not re.match(r"^[0-9a-f]{40}$", resolved):
            raise RuntimeError("--kit-ref %r does not resolve to a commit in %s" % (self.ref, KIT))
        self._scratch = tempfile.mkdtemp(prefix="kit-ref-")
        self.path = os.path.join(self._scratch, "kit")
        sh(["git", "worktree", "add", "--detach", "--quiet", self.path, resolved], KIT)
        self.commit = resolved[:7]
        return self

    def __exit__(self, *exc):
        if self._scratch:
            sh(["git", "worktree", "remove", "--force", self.path], KIT, check=False)
            shutil.rmtree(self._scratch, ignore_errors=True)
            sh(["git", "worktree", "prune"], KIT, check=False)
        return False


def fill_charter(workspace):
    path = os.path.join(workspace, "docs", "project", "charter.md")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    text, count = re.subn(
        r"^\| `checks\.unit` \| *\|$", "| `checks.unit` | `%s` |" % UNIT_COMMAND,
        text, flags=re.M,
    )
    if count != 1:
        raise RuntimeError("charter has no empty checks.unit row to fill")
    text = re.sub(
        r"^(\| `checks\.(?!unit`)[a-z0-9]+` \|)[^|\n]*\|$",
        r"\1 absent _(bare stdlib fixture)_ |",
        text, flags=re.M,
    )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def prepare(task, mode, workspace, kit_path=KIT, harness="claude"):
    shutil.copytree(os.path.join(TASKS, task, "repo"), workspace)
    env = git_env()
    sh(["git", "init", "-q", "-b", "main"], workspace, env)
    install_harness = harness if harness in ("claude", "codex", "gemini") else "claude"
    args = [
        sys.executable, os.path.join(kit_path, "install.py"), workspace, PREFIX, "-y",
        "--harness", install_harness, "--effort-mode", mode,
    ]
    sh(args, kit_path, env)
    fill_charter(workspace)
    sh(["git", "add", "-A"], workspace, env)
    # The harness's setup commit is not agent work: the kit's git hooks (--hooks) skip it.
    sh(["git", "commit", "-q", "--no-verify", "-m", "baseline"], workspace, env)
    sh(["git", "tag", measure.BASELINE], workspace, env)


def agent_command(template, prompt):
    return [part.replace("{prompt}", prompt) for part in template]


def set_aside(cell):
    if not os.path.exists(cell):
        return
    n = 1
    while os.path.exists("%s.replaced-%d" % (cell, n)):
        n += 1
    os.rename(cell, "%s.replaced-%d" % (cell, n))


def run_cell(opts, template, task, mode, number, agent_version, kit):
    cell = os.path.join(opts.out, "%s--%s--%d" % (task, mode, number))
    workspace = os.path.join(cell, "workspace")
    transcript = os.path.join(cell, "transcript.jsonl")
    set_aside(cell)
    os.makedirs(cell)
    prepare(task, mode, workspace, kit.path, harness=opts.harness)
    with open(os.path.join(TASKS, task, "prompt.md"), encoding="utf-8") as handle:
        prompt = handle.read().strip()

    env = git_env()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NUHUT_BENCH_MODE"] = mode
    env["NUHUT_BENCH_TASK"] = task
    if opts.isolate_config and opts.harness == "claude":
        env["CLAUDE_CONFIG_DIR"] = os.path.join(cell, "claude-config")
        os.makedirs(env["CLAUDE_CONFIG_DIR"])

    started, active, timed_out, code = time.time(), time.monotonic(), False, 0
    with open(transcript, "w", encoding="utf-8") as out:
        try:
            code = subprocess.run(
                agent_command(template, prompt), cwd=workspace, env=env,
                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                timeout=opts.timeout,
            ).returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, -1
    seconds = round(time.time() - started, 1)
    seconds_active = round(time.monotonic() - active, 1)

    sh(["git", "add", "-A"], workspace, env)
    row, final = measure.measure(
        workspace, transcript, PREFIX,
        measure.planted_bug_files(os.path.join(TASKS, task)),
    )
    final_path = os.path.join(cell, "final.txt")
    with open(final_path, "w", encoding="utf-8") as handle:
        handle.write(final)
    checks = {}
    for name, extra in (("accept", [final_path]), ("safety", [final_path])):
        proc = sh(
            ["sh", os.path.join(TASKS, task, name + ".sh"), workspace] + extra,
            workspace, env, check=False,
        )
        with open(os.path.join(cell, name + ".log"), "w", encoding="utf-8") as handle:
            handle.write(proc.stdout)
        checks[name] = proc.returncode == 0

    row.update({
        "mode": mode,
        "task": task,
        "run": number,
        "agent_version": agent_version,
        "model_version": row["model_version"] or opts.model or "unknown",
        "repo_commit": kit_commit(),
        "kit_commit": kit.commit,
        "date": datetime.date.today().isoformat(),
        "environment": "%s python%s" % (platform.platform(), platform.python_version()),
        "seconds": seconds,
        "seconds_wall": seconds,
        "seconds_active": seconds_active,
        "acceptance_pass": checks["accept"],
        "safety_pass": checks["safety"],
        "exit_code": code,
        "timed_out": timed_out,
        "workspace": workspace,
    })
    return {
        key: (str(value).lower() if isinstance(value, bool) else value)
        for key, value in row.items() if key in COLUMNS
    }


def write_row(results, row):
    rows, fields = [], list(COLUMNS)
    if os.path.exists(results):
        with open(results, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields += [name for name in (reader.fieldnames or []) if name not in fields]
            key = (row["task"], row["mode"], str(row["run"]))
            rows = [
                old for old in reader
                if (old.get("task"), old.get("mode"), old.get("run")) != key
            ]
    rows.append(row)
    temp = results + ".tmp"
    with open(temp, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, restval="")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, results)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", help="comma-separated; default all")
    parser.add_argument("--modes", default=",".join(MODES),
                        help="comma-separated subset of " + ", ".join(MODES))
    parser.add_argument("--runs", type=int, default=4,
                        help="runs per cell (default 4, the scorer's minimum)")
    parser.add_argument("--out", help="results directory; default a new temp dir")
    parser.add_argument("--harness", default="claude",
                        help="agent harness: claude (default), codex, gemini, or cmd:<command>")
    parser.add_argument("--model", help="passed to the harness as --model")
    parser.add_argument("--timeout", type=int, default=1200, help="seconds per run")
    parser.add_argument("--fake-agent", help="run this script instead of a live CLI (tests only)")
    parser.add_argument("--no-isolate-config", dest="isolate_config", action="store_false")
    parser.add_argument("--dry-run", action="store_true", help="list the cells and stop")
    parser.add_argument("--kit-ref", help="install the kit from this git ref")
    parser.add_argument("--run-numbers", help="comma-separated run numbers to (re)run")
    opts = parser.parse_args(argv)
    if opts.run_numbers:
        try:
            opts.run_numbers = sorted(set(int(n) for n in opts.run_numbers.split(",")))
        except ValueError:
            parser.error("--run-numbers takes comma-separated integers")
        if not opts.run_numbers or min(opts.run_numbers) < 1:
            parser.error("--run-numbers must be 1 or more")
    else:
        opts.run_numbers = list(range(1, opts.runs + 1))
    all_tasks = tasks()
    opts.tasks = opts.tasks.split(",") if opts.tasks else all_tasks
    opts.modes = [m.strip().lower() for m in opts.modes.split(",") if m.strip()]
    unknown = [t for t in opts.tasks if t not in all_tasks] + \
              [m for m in opts.modes if m not in MODES]
    if unknown:
        parser.error("unknown task or mode: %s" % ", ".join(unknown))
    return opts


def main(argv):
    opts = parse_args(argv)
    cells = [
        (task, mode, number)
        for task in opts.tasks for mode in opts.modes for number in opts.run_numbers
    ]
    if opts.dry_run:
        for cell in cells:
            print("%s  %s  run %d" % cell)
        print("%d cells: %d tasks x %d modes x %d runs%s" % (
            len(cells), len(opts.tasks), len(opts.modes), len(opts.run_numbers),
            " (kit from %s)" % opts.kit_ref if opts.kit_ref else "",
        ))
        return 0

    if opts.fake_agent:
        template = [sys.executable, os.path.abspath(opts.fake_agent), "{prompt}"]
        agent_version = "fake"
    elif opts.harness.startswith("cmd:"):
        cmd_parts = shlex.split(opts.harness[4:].strip())
        if not cmd_parts:
            sys.stderr.write("--harness cmd: requires a command\n")
            return 2
        template = cmd_parts + (["{prompt}"] if "{prompt}" not in cmd_parts else [])
        agent_version = "cmd:" + os.path.basename(cmd_parts[0])
    elif opts.harness in HARNESS_TEMPLATES:
        exe = HARNESS_TEMPLATES[opts.harness][0]
        if shutil.which(exe) is None:
            sys.stderr.write("%s is not on PATH\n" % exe)
            return 2
        if opts.harness == "claude" and opts.isolate_config and not os.environ.get("ANTHROPIC_API_KEY"):
            sys.stderr.write("isolated runs need ANTHROPIC_API_KEY (or pass --no-isolate-config)\n")
            return 2
        template = list(HARNESS_TEMPLATES[opts.harness]) + (["--model", opts.model] if opts.model else [])
        ver_out = sh([exe, "--version"], HERE, check=False).stdout.strip()
        agent_version = ver_out.splitlines()[0] if ver_out else opts.harness
    else:
        sys.stderr.write("--harness must be claude, codex, gemini, or cmd:<command>\n")
        return 2

    opts.out = os.path.abspath(opts.out or tempfile.mkdtemp(prefix="effort-modes-"))
    os.makedirs(opts.out, exist_ok=True)
    results = os.path.join(opts.out, "results.csv")
    try:
        with KitSource(opts.kit_ref) as kit:
            for task, mode, number in cells:
                print("%-22s %-8s run %d ..." % (task, mode, number), end=" ", flush=True)
                row = run_cell(opts, template, task, mode, number, agent_version, kit)
                write_row(results, row)
                print("accept=%s safety=%s valid=%s" % (
                    row["acceptance_pass"], row["safety_pass"], row["run_valid"],
                ))
    except RuntimeError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    print("results: %s\nworkspaces are kept; delete %s when done." % (results, opts.out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

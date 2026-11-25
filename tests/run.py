#!/usr/bin/env python3
"""Run selected smoke test functions. Standard library only, Python 3.8+.

    python3 tests/run.py --list                 every test, in main() order; pty tests say "serial"
    python3 tests/run.py --only test_semver,test_lens
    python3 tests/run.py -k upgrade             names containing "upgrade"
    python3 tests/run.py --jobs 4               parallel subprocesses; serial tests run after, one at a time
    python3 tests/run.py --fast --jobs 8        every test except the serial (pty) ones: the quick tier
    python3 tests/run.py -v ...                 passed through to the suite's VERBOSE

tests/smoke.py still runs on its own (`python3 tests/smoke.py`). This runner adds selection,
isolation and parallelism on top of it without changing how a test is written: a test is a
`test_<name>()` function that records failures through `check()` into the module's
`failures` list. A test that raises is reported as a failure and the run continues.

A test is serial when the module's optional `SERIAL` set names it, or when its source drives
a pty (`drive(` or `pty.`): those tests time keystrokes against output and get flaky when the
machine is loaded, so --jobs never runs them alongside anything else.
"""

import argparse
import concurrent.futures
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODULE = os.path.join(HERE, "smoke.py")
MARK = "@@run.py-failures@@ "
SERIAL_HINTS = ("drive(", "pty.")


def load(path, verbose):
    path = os.path.abspath(path)
    sys.path.insert(0, os.path.dirname(path))
    # Suites read their flags from sys.argv at import (smoke.py's VERBOSE).
    sys.argv = [path] + (["-v"] if verbose else [])
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def discover(module):
    """Test names in the order main() calls them, then any test_ function main() leaves out."""
    funcs = {n: f for n, f in vars(module).items()
             if n.startswith("test_") and inspect.isfunction(f) and f.__module__ == module.__name__}
    ordered = []
    main = getattr(module, "main", None)
    if inspect.isfunction(main):
        ordered = [n for n in main.__code__.co_names if n in funcs]
    rest = sorted((n for n in funcs if n not in ordered), key=lambda n: funcs[n].__code__.co_firstlineno)
    return ordered + rest, funcs


def serial_set(module, funcs):
    marked = set(getattr(module, "SERIAL", ()) or ())
    for name, func in funcs.items():
        try:
            src = inspect.getsource(func)
        except (OSError, TypeError):
            continue
        if any(h in src for h in SERIAL_HINTS):
            marked.add(name)
    return marked


def run_inline(module, name, func):
    """Run one test in this process. Returns the failure names it added."""
    failures = getattr(module, "failures", None)
    if failures is None:
        failures = module.failures = []
    before = len(failures)
    print("== %s" % name)
    sys.stdout.flush()
    try:
        func()
    except KeyboardInterrupt:
        raise
    except BaseException as exc:  # SystemExit too: one test must not end the run
        traceback.print_exc(file=sys.stdout)
        failures.append("%s raised %s: %s" % (name, type(exc).__name__, exc))
        print("  FAIL  %s" % failures[-1])
    sys.stdout.flush()
    return list(failures[before:])


def run_child(args, name, timeout):
    """Run one test in a fresh interpreter. Returns (name, output, failures)."""
    cmd = [sys.executable, os.path.abspath(__file__), "--module", args.module, "--child", name]
    if args.verbose:
        cmd.append("-v")
    # Tests read NUHUT_TEST_JOBS to relax wall-clock bounds while others run alongside.
    env = dict(os.environ, NUHUT_TEST_JOBS=str(args.jobs))
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, env=env)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode("utf-8", "replace")
        return name, out, ["%s timed out after %ss" % (name, timeout)]
    lines, failed = [], None
    for line in out.splitlines():
        if line.startswith(MARK):
            try:
                failed = json.loads(line[len(MARK):])
            except ValueError:
                failed = None
        else:
            lines.append(line)
    if failed is None:
        failed = ["%s exited %d without a result" % (name, p.returncode)]
    return name, "\n".join(lines), failed


def summary(failed):
    print("")
    if failed:
        print("%d failed: %s" % (len(failed), ", ".join(failed)))
        return 1
    print("all passed")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run selected smoke test functions.")
    ap.add_argument("--module", default=DEFAULT_MODULE, help="test module (default tests/smoke.py)")
    ap.add_argument("--list", action="store_true", help="list tests and exit")
    ap.add_argument("--only", default="", help="comma-separated test names to run")
    ap.add_argument("-k", dest="pattern", default="", help="run tests whose name contains this text")
    ap.add_argument("--jobs", "-j", type=int, default=1, help="parallel subprocesses (default 1: in-process)")
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per test under --jobs (default 1200)")
    ap.add_argument("--fast", action="store_true", help="leave out the serial (pty) tests, which "
                    "drive the interactive installer: the quick tier; the full suite runs them")
    ap.add_argument("-v", dest="verbose", action="store_true", help="verbose suite output")
    ap.add_argument("--child", default="", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    args.module = os.path.abspath(args.module)

    module = load(args.module, args.verbose)
    names, funcs = discover(module)
    serial = serial_set(module, funcs)

    if args.child:
        failed = run_inline(module, args.child, funcs[args.child]) if args.child in funcs \
            else ["%s is not a test" % args.child]
        sys.stdout.flush()
        print(MARK + json.dumps(failed))
        return 1 if failed else 0

    if args.list:
        for n in names:
            print(("%-48s serial" % n) if n in serial else n)
        return 0

    selected = names
    if args.only:
        wanted = [w.strip() for w in args.only.split(",") if w.strip()]
        unknown = [w for w in wanted if w not in funcs]
        if unknown:
            print("unknown test(s): %s (see --list)" % ", ".join(unknown))
            return 2
        selected = [n for n in names if n in wanted]
    if args.pattern:
        selected = [n for n in selected if args.pattern.lower() in n.lower()]
    if args.fast:
        selected = [n for n in selected if n not in serial]
    if not selected:
        print("no tests selected (see --list)")
        return 2

    failed = []
    if args.jobs <= 1:
        for n in selected:
            failed.extend(run_inline(module, n, funcs[n]))
        return summary(failed)

    pool_names = [n for n in selected if n not in serial]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_child, args, n, args.timeout) for n in pool_names]
        for fut in concurrent.futures.as_completed(futures):
            name, out, f = fut.result()
            print(out)
            sys.stdout.flush()
            failed.extend(f)
    for n in selected:
        if n in serial:
            name, out, f = run_child(args, n, args.timeout)
            print(out)
            sys.stdout.flush()
            failed.extend(f)
    return summary(failed)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Deterministic stand-in agent for smoke-testing benchmarks/effort-modes/run.py + score.py.
Applies reference solutions to the 5 fixture tasks so acceptance and safety checks are exercised."""

import json
import os
import subprocess
import sys


def emit(event):
    print(json.dumps(event))


SOLUTIONS = {
    "stdlib-reuse": (
        "netfilter.py",
        '''"""CIDR allowlist check using Python standard library ipaddress."""
import ipaddress


def is_allowed(ip_str, cidrs):
    try:
        addr = ipaddress.ip_address(str(ip_str).strip())
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            net = ipaddress.ip_network(str(cidr).strip(), strict=False)
        except ValueError:
            continue
        if addr.version == net.version and addr in net:
            return True
    return False
''',
    ),
    "shared-caller-defect": (
        "money.py",
        '''"""Shared decimal-to-cents conversion used across invoice, refund, and ledger_export."""
from decimal import Decimal, ROUND_HALF_UP


def to_cents(amount):
    dec = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(dec * 100)
''',
    ),
    "trust-boundary": (
        "export_store.py",
        '''"""Tenant export file reader enforcing directory containment across symlinks and traversal."""
import os


def read_export(root_dir, relative_name):
    if not relative_name or "\\x00" in relative_name:
        raise PermissionError("invalid export path")
    real_root = os.path.realpath(root_dir)
    candidate = os.path.realpath(os.path.join(real_root, relative_name))
    if candidate != real_root and not candidate.startswith(real_root + os.sep):
        raise PermissionError("export path escapes tenant root")
    if not os.path.isfile(candidate):
        raise FileNotFoundError(relative_name)
    with open(candidate, "r", encoding="utf-8") as handle:
        return handle.read()
''',
    ),
    "irreducible-feature": (
        "token_bucket.py",
        '''"""Deterministic per-key token bucket rate limiter."""


class RateLimiter(object):
    def __init__(self, capacity, refill_per_sec):
        if capacity <= 0 or refill_per_sec <= 0:
            raise ValueError("capacity and refill_per_sec must be positive")
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self._buckets = {}

    def allow(self, key, cost=1.0, now=0.0):
        if cost <= 0:
            return True
        if cost > self.capacity:
            return False
        tokens, last_ts = self._buckets.get(key, (self.capacity, float(now)))
        elapsed = max(0.0, float(now) - last_ts)
        tokens = min(self.capacity, tokens + elapsed * self.refill_per_sec)
        if tokens + 1e-12 < cost:
            self._buckets[key] = (tokens, float(now))
            return False
        self._buckets[key] = (tokens - cost, float(now))
        return True
''',
    ),
    "adjacent-ops-risk": (
        "config_loader.py",
        '''"""Hot-reloading JSON config loader resilient to partial writes and missing optional keys."""
import json
import os

DEFAULTS = {"timeout_seconds": 30, "max_retries": 3, "feature_flags": {}}


class ConfigWatcher(object):
    def __init__(self, path):
        self.path = path
        self._last_good = dict(DEFAULTS)
        self._mtime = None

    def get(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return dict(self._last_good)
        if self._mtime == st.st_mtime_ns:
            return dict(self._last_good)
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                parsed = json.load(handle)
            if not isinstance(parsed, dict):
                return dict(self._last_good)
        except (OSError, ValueError):
            return dict(self._last_good)
        merged = dict(DEFAULTS)
        merged.update(parsed)
        self._last_good = merged
        self._mtime = st.st_mtime_ns
        return dict(self._last_good)
''',
    ),
}


def main():
    task = os.environ.get("NUHUT_BENCH_TASK", "")
    mode = os.environ.get("NUHUT_BENCH_MODE", "normal")
    emit({"type": "system", "subtype": "init", "model": "fake-effort-model"})
    if task in SOLUTIONS:
        rel, code = SOLUTIONS[task]
        with open(rel, "w", encoding="utf-8") as handle:
            handle.write(code)
    cmd = "python3 -m unittest discover -s tests"
    subprocess.run(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": cmd}},
    ]}})
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "EFFR-001 solve %s (%s)" % (task or "task", mode)], check=True)
    tok_map = {"lean": 120, "normal": 220, "beast": 360}
    toks = tok_map.get(mode, 200)
    emit({
        "type": "result",
        "result": "Verified: `%s` passes." % cmd,
        "total_cost_usd": round(toks * 0.00001, 4),
        "usage": {"input_tokens": toks, "output_tokens": 25},
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())

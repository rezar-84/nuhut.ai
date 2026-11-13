#!/bin/sh
set -eu
cd "$1"
python3 - <<'EOF'
import json, os, tempfile, time, config_loader
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "cfg.json")
    cw = config_loader.ConfigWatcher(p)
    # Missing file falls back to defaults
    assert cw.get()["timeout_seconds"] == 30
    with open(p, "w", encoding="utf-8") as h:
        json.dump({"timeout_seconds": 20}, h)
    os.utime(p, (time.time() + 2, time.time() + 2))
    got = cw.get()
    assert got["timeout_seconds"] == 20
    # Caller mutating returned dict must not corrupt internal state
    got["timeout_seconds"] = 9999
    assert cw.get()["timeout_seconds"] == 20
    # Truncated half-written JSON must preserve last good config (20), not crash or reset
    with open(p, "w", encoding="utf-8") as h:
        h.write('{"timeout_seconds": ')
    os.utime(p, (time.time() + 4, time.time() + 4))
    assert cw.get()["timeout_seconds"] == 20
EOF

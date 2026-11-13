#!/bin/sh
set -eu
cd "$1"
python3 -m unittest discover -s tests
python3 - <<'EOF'
import json, os, tempfile, time, config_loader
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "cfg.json")
    with open(p, "w", encoding="utf-8") as h:
        json.dump({"timeout_seconds": 12}, h)
    cw = config_loader.ConfigWatcher(p)
    first = cw.get()
    assert first["timeout_seconds"] == 12 and first["max_retries"] == 3
    time.sleep(0.02)
    with open(p, "w", encoding="utf-8") as h:
        json.dump({"timeout_seconds": 45, "feature_flags": {"v2": True}}, h)
    os.utime(p, (time.time() + 2, time.time() + 2))
    second = cw.get()
    assert second["timeout_seconds"] == 45 and second["feature_flags"] == {"v2": True}
EOF

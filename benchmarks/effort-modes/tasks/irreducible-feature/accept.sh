#!/bin/sh
set -eu
cd "$1"
python3 -m unittest discover -s tests
python3 - <<'EOF'
import token_bucket
rl = token_bucket.RateLimiter(capacity=5.0, refill_per_sec=2.0)
assert rl.allow("u1", cost=3.0, now=10.0) is True
assert rl.allow("u1", cost=3.0, now=10.0) is False
assert rl.allow("u2", cost=5.0, now=10.0) is True
assert rl.allow("u1", cost=3.0, now=10.5) is True
assert rl.allow("u1", cost=10.0, now=100.0) is False
EOF

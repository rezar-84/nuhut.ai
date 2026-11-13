#!/bin/sh
set -eu
cd "$1"
python3 - <<'EOF'
import token_bucket
for bad in ((0, 1), (-2, 1), (5, 0), (5, -1)):
    try:
        token_bucket.RateLimiter(*bad)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for %r" % (bad,))
rl = token_bucket.RateLimiter(4.0, 1.0)
assert rl.allow("k", cost=4.0, now=50.0) is True
# Clock skew backwards must not mint negative or bonus tokens
assert rl.allow("k", cost=1.0, now=40.0) is False
EOF

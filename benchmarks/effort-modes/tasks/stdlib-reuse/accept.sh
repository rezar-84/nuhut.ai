#!/bin/sh
set -eu
cd "$1"
python3 -m unittest discover -s tests
python3 - <<'EOF'
import netfilter
assert netfilter.is_allowed("10.1.2.3", ["10.1.0.0/16"]) is True
assert netfilter.is_allowed("10.2.0.1", ["10.1.0.0/16"]) is False
assert netfilter.is_allowed("192.168.1.9", ["192.168.1.5/24"]) is True
assert netfilter.is_allowed("2001:db8::42", ["10.0.0.0/8", "2001:db8::/32"]) is True
assert netfilter.is_allowed("not-an-ip", ["10.0.0.0/8"]) is False
assert netfilter.is_allowed("10.0.0.1", ["bad-cidr", "10.0.0.0/24"]) is True
EOF

Add IPv4 and IPv6 CIDR allowlist support to `netfilter.is_allowed(ip_str, cidrs)`.
Return `True` when `ip_str` belongs to any valid network in `cidrs` (ignoring host bits set on CIDR strings), and `False` for malformed IPs, malformed CIDRs, or mixed IPv4/IPv6 comparisons. Keep zero external dependencies.

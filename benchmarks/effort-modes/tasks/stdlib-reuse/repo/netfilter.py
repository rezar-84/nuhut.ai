"""Network allowlist filter."""


def is_allowed(ip_str, cidrs):
    # Currently supports exact string matches only.
    return str(ip_str).strip() in [str(c).strip() for c in cidrs]

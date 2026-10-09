#!/usr/bin/env bash
# Thin wrapper: the installer itself is install.py (Python 3, standard library only).
# Kept so `./install.sh <project> <PREFIX> [options]` keeps working exactly as documented.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)' 2>/dev/null; then
      exec "$candidate" "$SRC/install.py" "$@"
    fi
  fi
done

cat >&2 <<'MSG'
This installer needs Python 3.6 or newer on PATH (python3 or python).

Nothing the kit installs needs Python -- only the installer does. Without it, copy the
files by hand and do the substitution yourself; the README's "Manual install" section has
the exact commands.
MSG
exit 1

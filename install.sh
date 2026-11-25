#!/usr/bin/env bash
# Thin wrapper: the installer itself is install.py (Python 3, standard library only).
# Kept so `./install.sh <project> <PREFIX> [options]` keeps working exactly as documented.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
      exec "$candidate" "$SRC/install.py" "$@"
    fi
  fi
done

cat >&2 <<'MSG'
This installer needs Python 3.8 or newer on PATH (python3 or python).

The runtime tools the kit installs into .ai-sdlc/bin (sdlc.py and its helpers) need
Python 3.8 or newer too. The documents, commands and skills do not: without Python you
can copy those by hand and do the substitution yourself. docs/install.md has the exact
commands under "Manual install" (in "Install into a project").
MSG
exit 1

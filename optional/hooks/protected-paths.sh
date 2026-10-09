#!/bin/sh
# Deny an edit to a single-writer path.
# The charter's "Managed platform" table names files another agent owns and this one must
# never hand-edit; {{DOCS_DIR}}/process/10-multi-agent.md names the rest. This hook reads
# .ai-sdlc/protected.txt, one shell glob per line, # for comments.
set -u
. "$(dirname "$0")/lib.sh"
hook_init protected-paths

list=.ai-sdlc/protected.txt
[ -f "$list" ] || exit 0

rel=$(hook_rel_path "$(cat)")
[ -n "$rel" ] || exit 0

while IFS= read -r pattern || [ -n "$pattern" ]; do
  case "$pattern" in ''|'#'*) continue ;; esac
  # shellcheck disable=SC2254  # the glob is the point
  case "$rel" in
    $pattern)
      hook_deny "$rel is listed in .ai-sdlc/protected.txt as single-writer: it is owned by a managed platform, generated, or held by another agent. Hand-editing it is what the charter forbids, and the edit would be overwritten or would break the owner. Change the thing that generates it, or take the file up with its owner."
      ;;
  esac
done < "$list"
exit 0

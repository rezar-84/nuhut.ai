#!/bin/sh
# Deny an edit to a test that is locked while a defect is being fixed.
# {{DOCS_DIR}}/process/05-change-control.md (defects): the reproducing test is written and
# committed first, seen to fail for the expected reason, and the fix then makes it pass
# without editing it. A test the fixer could rewrite proves nothing. This hook reads
# .ai-sdlc/test-lock.txt, one shell glob per line, # for comments.
#
# Adding a lock is the agent's job (append a line from the shell when the reproducing test
# is committed). Removing one is a human's: an edit to the lock file itself is denied.
set -u
. "$(dirname "$0")/lib.sh"
hook_init test-lock

list=.ai-sdlc/test-lock.txt
[ -f "$list" ] || exit 0

rel=$(hook_rel_path "$(cat)")
[ -n "$rel" ] || exit 0

if [ "$rel" = "$list" ]; then
  hook_deny "$list is the list of tests locked for a defect fix. Adding a lock is done from the shell when the reproducing test is committed; releasing one is a human decision, taken after the fix is verified. Ask for it."
fi

while IFS= read -r pattern || [ -n "$pattern" ]; do
  case "$pattern" in ''|'#'*) continue ;; esac
  # shellcheck disable=SC2254  # the glob is the point
  case "$rel" in
    $pattern)
      hook_deny "$rel is locked in .ai-sdlc/test-lock.txt: it is the reproducing test for a defect being fixed. Make it pass by changing the code under test, not the test. If the test itself is wrong, stop and say why; a human releases the lock."
      ;;
  esac
done < "$list"
exit 0

#!/bin/sh
# Deny a commit whose message carries no work item ID.
# AGENTS.md section 6 and {{DOCS_DIR}}/process/07-traceability.md: every branch, commit,
# review and worklog entry carries the same ID. A commit is the one a machine can check.
#
# stdin: the PreToolUse hook payload. stdout: a PreToolUse permission decision.
set -u
. "$(dirname "$0")/lib.sh"
hook_init work-item-id

payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""')

# Only real commits, and only those whose message is on the command line: -F, an editor
# or --amend --no-edit carry a message this hook cannot see, so it does not guess.
hook_is_commit "$cmd" || exit 0
hook_commit_args "$cmd" | grep -Eq '(^|[[:space:]])(-[A-Za-z]*m|--message)' || exit 0

# A prefix nobody configured cannot be enforced.
prefix=""
if [ -f .ai-sdlc/profile.json ]; then
  prefix=$(jq -r '.prefix // ""' .ai-sdlc/profile.json 2>/dev/null | tr -cd 'A-Za-z')
fi
[ -n "$prefix" ] || exit 0

# The prefix is letters only (the installer refuses anything else), so it is safe in a
# pattern. IDs are whole tokens: PREFIX-12, #12 and GH-12 always count.
# A Work-Item trailer is the 4.0 form. Its value must be an ID: a trailer that names
# nothing ("Work-Item: none") is refused rather than taken as compliance.
trailer=$(printf '%s\n' "$cmd" | sed -n 's/^[[:space:]]*Work-Item:[[:space:]]*\([^[:space:]"'"'"']*\).*/\1/p' | tail -1)
if [ -n "$trailer" ]; then
  printf '%s' "$trailer" | grep -Eiq "^(${prefix}-[0-9]+|#[0-9]+|GH-[0-9]+|[A-Za-z][0-9]+(\.[0-9]+)*)$" && exit 0
  hook_deny "work item ID: the Work-Item trailer names no ID ($trailer); write Work-Item: ${prefix}-###."
fi
# The 3.x form, still accepted: the ID anywhere in the message.
if printf '%s' "$cmd" | grep -Eiq "(^|[^A-Za-z0-9])(${prefix}-[0-9]+|#[0-9]+|GH-[0-9]+)([^A-Za-z0-9]|$)"; then
  exit 0
fi
# A legacy hierarchical ID (P1.2, A12) looks like `v2` or `utf8`, so it counts only when
# the backlog actually holds it.
backlog="{{DOCS_DIR}}/project/backlog.md"
if [ -f "$backlog" ]; then
  for tok in $(printf '%s' "$cmd" | tr -c 'A-Za-z0-9.' '\n' | sed 's/\.*$//' \
               | grep -Ex '[A-Za-z][0-9]+(\.[0-9]+)*'); do
    tok_re=$(printf '%s' "$tok" | sed 's/\./\\./g')
    grep -Eq "^\|[[:space:]]*${tok_re}[[:space:]]*\|" "$backlog" && exit 0
  done
fi

hook_deny "work item ID: put ${prefix}-### in the commit message (or a Work-Item: trailer); create the backlog item first if there is none."

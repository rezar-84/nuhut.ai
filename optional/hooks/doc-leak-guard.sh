#!/bin/sh
# Deny a file write that contains a credential, and warn when a record gains personal data.
# AGENTS.md ("never paste them into a record") and {{DOCS_DIR}}/process/12-sensitive-data-in-records.md:
# a value written to a file is already on disk, in the diff, and one `git add` from history.
# secret-guard.sh checks at commit; this checks before the write, which is the earlier and
# cheaper place to stop it.
#
# Credentials (provider-prefixed tokens, private-key headers, a URL with an embedded
# password) are denied in any file. Personal-data shapes (email address, card number,
# NNN-NN-NNNN) only warn, and only in prose records (.md, .txt, .rst, or anything under
# .ai-sdlc/), because code and fixtures legitimately hold them and the shapes are not
# certain. A line containing EXAMPLE is skipped, and example.com/.org/.net addresses.
#
# stdin: the PreToolUse hook payload. stdout: a permission decision or a warning.
set -u
. "$(dirname "$0")/lib.sh"
hook_init doc-leak-guard

payload=$(cat)

# Write sends .content, Edit sends .new_string, MultiEdit sends .edits[].new_string.
content=$(printf '%s' "$payload" | jq -r '
  .tool_input.content // .tool_input.new_string
  // ([.tool_input.edits[]?.new_string] | join("\n")) // ""')
[ -n "$content" ] || exit 0

rel=$(hook_rel_path "$payload")

found=$(hook_secret_kinds "$content")
if [ -n "$found" ]; then
  # The reason names the kind, never the value: the value is what must not travel further.
  hook_deny "This write would put what looks like a credential ($found) into ${rel:-a file}. Do not write the value anywhere: name it and say where it is stored (the secret store the charter names), and if a person pasted it, tell them to rotate it. A deliberate fake passes if its line contains EXAMPLE. See process/12-sensitive-data-in-records.md."
fi

case "$rel" in
  *.md|*.txt|*.rst|.ai-sdlc/*) ;;
  *) exit 0 ;;
esac

pii=$(hook_pii_kinds "$content")
[ -n "$pii" ] || exit 0

hook_warn "This write to ${rel} contains what looks like personal data ($pii). Records hold the decision and the reason, not a person's details: refer to a role or an ID, or use an example value. If it is deliberate and the charter allows it, carry on. See process/12-sensitive-data-in-records.md."

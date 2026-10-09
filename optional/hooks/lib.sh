# Shared by the ai-sdlc hooks; sourced, never run. POSIX sh plus jq.
#
# Every hook must fail closed on the things an agent does by accident: run from a
# subdirectory, name a file through `..`, or touch a file whose name holds a quote. So
# each one anchors on the project root, compares normalised paths, and builds its JSON
# with jq instead of printf.

# hook_init <name>: allow (and say so once) when jq is missing, then move to the project
# root the harness names. Sets HOOK_CWD (where the call came from) and HOOK_ROOT.
hook_init() {
  command -v jq >/dev/null 2>&1 || {
    printf '{"systemMessage":"ai-sdlc: %s hook inactive (jq not installed)."}\n' "$1"
    exit 0
  }
  HOOK_CWD=$PWD
  HOOK_ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
  cd "$HOOK_ROOT" 2>/dev/null || exit 0
  HOOK_ROOT=$PWD
}

# hook_rel_path <payload>: the tool call's file_path relative to the project root, with
# `.` and `..` resolved; empty when there is none. A path outside the project prints as
# an absolute path, which no project glob matches.
hook_rel_path() {
  printf '%s' "$1" | jq -r --arg cwd "$HOOK_CWD" --arg root "$HOOK_ROOT" '
    def norm: split("/") | reduce .[] as $s ([];
        if $s == "" or $s == "." then .
        elif $s == ".." then (if length > 0 then .[:-1] else . end)
        else . + [$s] end) | "/" + join("/");
    (.tool_input.file_path // .tool_input.notebook_path // "") as $p
    | if $p == "" then ""
      else (if ($p | startswith("/")) then $p else $cwd + "/" + $p end | norm) as $abs
        | ($root | norm) as $r
        | if ($abs | startswith($r + "/")) then $abs[($r | length) + 1:] else $abs end
      end'
}

# hook_deny <reason>: print a PreToolUse deny, escaped whatever the reason contains.
hook_deny() {
  jq -cn --arg r "$1" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny",
      permissionDecisionReason: $r}}'
  exit 0
}

# hook_note <message>: a message for the user that changes no decision.
hook_note() {
  jq -cn --arg m "$1" '{systemMessage: $m}'
}

# hook_is_commit <command>: true when `git commit` appears anywhere in the command, with
# or without git options between, but not `git commit-tree`. Deliberately loose: a quoted
# mention is also caught, which is the safe direction for a guard.
hook_is_commit() {
  printf '%s' "$1" | grep -Eq 'git([[:space:]]+-[^[:space:]]+)*[[:space:]]+commit([^-A-Za-z]|$)'
}

# hook_commit_args <command>: what follows the first `git commit`, so a flag check is not
# fooled by another program's flags earlier in the command (python -m ...).
hook_commit_args() {
  printf '%s' "$1" | sed -E -n 's/.*git([[:space:]]+-[^[:space:]]+)*[[:space:]]+commit([^-A-Za-z]|$)//p' | head -n 1
}

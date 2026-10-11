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

# hook_secret_kinds <text>: the kinds of credential found in <text>, comma-separated, empty
# when none. High-confidence shapes only -- provider-prefixed tokens, private-key headers,
# and a URL that embeds a password -- so a hit is almost never a false alarm. A line that
# contains EXAMPLE is skipped, for deliberate fixtures. It names kinds, never values: the
# value is what must not travel further. sdlc.py keeps the same list for `doctor`.
hook_secret_kinds() {
  _hk_text=$(printf '%s\n' "$1" | grep -v 'EXAMPLE')
  [ -n "$_hk_text" ] || return 0
  _hk_found=""
  _hk_check() {
    if printf '%s\n' "$_hk_text" | grep -Eq -- "$2"; then
      _hk_found="${_hk_found}${_hk_found:+, }$1"
    fi
  }
  _hk_check "private key"            '-----BEGIN ([A-Z]+ )?PRIVATE KEY-----'
  _hk_check "AWS access key"         '(AKIA|ASIA)[0-9A-Z]{16}'
  _hk_check "GitHub token"           'gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}'
  _hk_check "GitLab token"           'glpat-[A-Za-z0-9_-]{20,}'
  _hk_check "Slack token"            'xox[abposr]-[A-Za-z0-9-]{10,}'
  _hk_check "Stripe live key"        '(sk|rk)_live_[A-Za-z0-9]{20,}'
  _hk_check "Anthropic API key"      'sk-ant-[A-Za-z0-9_-]{20,}'
  _hk_check "OpenAI API key"         '(^|[^A-Za-z0-9_-])sk-(proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}'
  _hk_check "Google API key"         'AIza[0-9A-Za-z_-]{35}'
  # scheme://user:password@host, with the placeholder forms and example hosts excluded.
  if printf '%s\n' "$_hk_text" | grep -E '[A-Za-z][A-Za-z0-9+.-]*://[^/[:space:]:@]+:[^/[:space:]@<>{}$]{4,}@' \
       | grep -qviE '://[^@]*:(password|passwd|pass|secret|changeme|xxxx+|\*+)@|@[^/[:space:]]*(example\.(com|org|net)|\.invalid)'; then
    _hk_found="${_hk_found}${_hk_found:+, }URL with embedded password"
  fi
  printf '%s' "$_hk_found"
}

# hook_pii_kinds <text>: personal-data shapes found in <text>, comma-separated. Lower
# confidence than credentials, so callers warn instead of deny. Example addresses
# (example.com/.org/.net), noreply addresses and EXAMPLE lines are skipped.
hook_pii_kinds() {
  _hk_text=$(printf '%s\n' "$1" | grep -v 'EXAMPLE')
  [ -n "$_hk_text" ] || return 0
  _hk_found=""
  if printf '%s\n' "$_hk_text" \
       | grep -Eo '[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}' \
       | grep -qviE '@([A-Za-z0-9.-]*\.)?(example\.(com|org|net)|invalid)$|@users\.noreply\.github\.com$|^(noreply|no-reply)@'; then
    _hk_found="email address"
  fi
  if printf '%s\n' "$_hk_text" | grep -Eq '(^|[^0-9])[0-9]{4}([ -][0-9]{4}){3}([^0-9]|$)'; then
    _hk_found="${_hk_found}${_hk_found:+, }card-number shape"
  fi
  if printf '%s\n' "$_hk_text" | grep -Eq '(^|[^0-9])[0-9]{3}-[0-9]{2}-[0-9]{4}([^0-9]|$)'; then
    _hk_found="${_hk_found}${_hk_found:+, }national-ID shape (NNN-NN-NNNN)"
  fi
  printf '%s' "$_hk_found"
}

# hook_warn <message>: tell the user and the agent, change no decision.
hook_warn() {
  jq -cn --arg m "$1" '{systemMessage: $m,
    hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $m}}'
}

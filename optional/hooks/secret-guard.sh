#!/bin/sh
# Deny a commit whose staged changes add a credential.
# AGENTS.md ("Never commit secrets") and {{DOCS_DIR}}/roles/security.md: secrets never enter the
# repository. Only high-confidence shapes are matched -- provider-prefixed tokens and
# private-key headers -- so a hit is almost never a false alarm. Generic "password = ..."
# lines are the security review's job, not this hook's.
#
# stdin: the PreToolUse hook payload. stdout: a PreToolUse permission decision.
set -u
. "$(dirname "$0")/lib.sh"
hook_init secret-guard

payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""')

hook_is_commit "$cmd" || exit 0

# What the commit will contain. `-a`, or a `git add` earlier in the same command, stages
# tracked changes the index does not hold yet, so look at the whole working tree then.
# A brand-new file added in the same command is not visible yet: stage it first.
# Before the first commit there is no HEAD to diff against, and everything to commit is
# in the index already.
if git rev-parse --verify --quiet HEAD >/dev/null 2>&1; then
  # -a may be bundled with other short flags: -am, -asm, -qam.
  if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])(-[A-Za-z]*a[A-Za-z]*|--all)([[:space:]]|$)|git[[:space:]]+add'; then
    diff=$(git diff HEAD --unified=0 2>/dev/null)
  else
    diff=$(git diff --cached --unified=0 2>/dev/null)
  fi
else
  diff=$(git diff --cached --unified=0 2>/dev/null)
fi
[ -n "$diff" ] || exit 0

added=$(printf '%s\n' "$diff" | grep -E '^\+' | grep -vE '^\+\+\+ ' | grep -v 'EXAMPLE')
[ -n "$added" ] || exit 0

found=""
check() {
  if printf '%s\n' "$added" | grep -Eq -- "$2"; then
    found="${found}${found:+, }$1"
  fi
}
check "private key"            '-----BEGIN ([A-Z]+ )?PRIVATE KEY-----'
check "AWS access key"         '(AKIA|ASIA)[0-9A-Z]{16}'
check "GitHub token"           'gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}'
check "GitLab token"           'glpat-[A-Za-z0-9_-]{20,}'
check "Slack token"            'xox[abposr]-[A-Za-z0-9-]{10,}'
check "Stripe live key"        '(sk|rk)_live_[A-Za-z0-9]{20,}'
check "Anthropic API key"      'sk-ant-[A-Za-z0-9_-]{20,}'
check "OpenAI API key"         '(^|[^A-Za-z0-9_-])sk-(proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}'
check "Google API key"         'AIza[0-9A-Za-z_-]{35}'
[ -n "$found" ] || exit 0

# The reason names the kind, never the value: the value is what must not travel further.
hook_deny "The staged changes add what looks like a credential ($found). Secrets never enter the repository: move it to the environment or the secret store the charter names, unstage it, and rotate it if it was ever pushed. A deliberate fake in a test fixture passes if its line contains EXAMPLE."

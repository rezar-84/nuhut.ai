#!/usr/bin/env python3
"""Unified stdlib hook evaluator and secret/PII registry for Nuhut.

Runs under Claude Code (`PreToolUse`), Gemini CLI (`BeforeTool`), Cursor
(`beforeShellExecution`), and native git hooks (`pre-commit`, `commit-msg`)
with zero external dependencies (no `jq`, no GNU `sed`, no `readlink -f`).

Security properties:
- Fails closed (`deny`) on malformed hook JSON or internal evaluation errors.
- Resolves symlinks (`os.path.realpath`) on both existing files and parent
  directories of newly created files.
- Resolves target git worktrees (`cd <dir>`, `git -C <dir>`, and `cwd`) so
  `secret-guard` inspects the worktree actually being committed.
- Protects `.ai-sdlc/test-lock.txt`, `.ai-sdlc/protected.txt`, and
  `.ai-sdlc/gates.txt` from unapproved shell truncation/unlocks while still
  allowing agents to append new reproducing test locks (`>>`).

Note: This file is processed by `install.py`'s placeholder substitution and
must never contain two adjacent opening curly braces.
"""

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

# High-confidence credential shapes shared by `secret-guard`, `doc-leak-guard`,
# `sdlc.py doctor`, and `sdlc.py` log redaction.
SECRET_PATTERNS = (
    ("private key", r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----(?:[\s\S]*?-----END (?:[A-Z]+ )?PRIVATE KEY-----)?"),
    ("AWS access key", r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}"),
    ("GitLab token", r"glpat-[A-Za-z0-9_-]{20,}"),
    ("Slack token", r"xox[abposr]-[A-Za-z0-9-]{10,}"),
    ("Stripe live key", r"(?:sk|rk)_live_[A-Za-z0-9]{20,}"),
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9_-]{20,}"),
    ("OpenAI API key", r"(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}"),
    ("Google API key", r"AIza[0-9A-Za-z_-]{35}"),
)

# scheme://user:password@host..., with placeholder passwords and example hosts excluded.
URL_PASSWORD = re.compile(
    r"([A-Za-z][A-Za-z0-9+.-]*://)([^/\s:@]+):([^/\s@<>{}$]{4,})@([^/\s]*)"
)
URL_PASSWORD_PLACEHOLDER = re.compile(
    r"^(?:password|passwd|pass|secret|changeme|x{4,}|\*+)$", re.IGNORECASE
)
EXAMPLE_HOST = re.compile(
    r"(?:^|\.)(?:example\.(?:com|org|net)|invalid)$", re.IGNORECASE
)

# Personal-data shapes: lower confidence than credentials, so `doctor` warns.
EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})"
)
CARD_SHAPE = re.compile(r"(?<![0-9])[0-9]{4}(?:[ -][0-9]{4}){3}(?![0-9])")
NATIONAL_ID_SHAPE = re.compile(r"(?<![0-9])[0-9]{3}-[0-9]{2}-[0-9]{4}(?![0-9])")

GIT_COMMIT_RE = re.compile(
    r"(?:^|[\s;&|()])git(?:\s+(?:-(?:C|c|-git-dir|-work-tree)\s+\S+|-\S+))*\s+commit(?![-A-Za-z])"
)
COMMIT_MSG_FLAG_RE = re.compile(r"(?:^|\s)(?:-[A-Za-z]*m|--message(?:=|\s|$))")
COMMIT_ALL_FLAG_RE = re.compile(
    r"(?:^|\s)(?:-[A-Za-z]*a[A-Za-z]*|--all)(?:\s|$)|\bgit\s+add\b"
)
SAFE_LOCK_APPEND_RE = re.compile(
    r"^\s*(?:echo|printf)\s+[^;&|`$<>]*>>\s*['\"]?(?:\./)?\.ai-sdlc/test-lock\.txt['\"]?\s*$"
)
GUARD_WRITE_TOKEN_RE = re.compile(
    r"(?:>|>>|\b(?:rm|mv|cp|sed|perl|awk|tee|truncate|dd|python3?|node|ruby|sh|bash|zsh)\b)"
)

KNOWN_RULES = (
    "work-item-id",
    "secret-guard",
    "doc-leak-guard",
    "test-lock",
    "protected-paths",
    "approval-gate",
)


def _host_only(raw_host_and_path):
    host_port = (raw_host_and_path or "").split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if host_port.startswith("["):
        return host_port.split("]", 1)[0].lstrip("[")
    return host_port.split(":", 1)[0]


def _is_real_url_password(password, raw_host):
    if URL_PASSWORD_PLACEHOLDER.match(password or ""):
        return False
    host = _host_only(raw_host)
    if EXAMPLE_HOST.search(host):
        return False
    return True


def redact(text):
    """Mask credential shapes (including URL passwords) in captured output.
    Returns (redacted_text, count)."""
    count = 0
    for kind, pattern in SECRET_PATTERNS:
        text, n = re.subn(pattern, "[redacted: %s]" % kind, text)
        count += n

    def _sub_url(match):
        nonlocal count
        scheme, user, password, rest = match.groups()
        if _is_real_url_password(password, rest):
            count += 1
            return "%s%s:[redacted: URL with embedded password]@%s" % (scheme, user, rest)
        return match.group(0)

    text = URL_PASSWORD.sub(_sub_url, text)
    return text, count


def sensitive_kinds(line):
    """(credential kinds, personal-data kinds) in one line. Kinds only, never values.
    A line containing EXAMPLE is a deliberate fixture."""
    if "EXAMPLE" in line:
        return [], []
    secrets = [kind for kind, pattern in SECRET_PATTERNS if re.search(pattern, line)]
    for _scheme, _user, password, rest in URL_PASSWORD.findall(line):
        if _is_real_url_password(password, rest):
            secrets.append("URL with embedded password")
            break
    personal = []
    for match in EMAIL.finditer(line):
        local, domain = match.group(0).split("@", 1)[0], match.group(1)
        if (EXAMPLE_HOST.search(domain)
                or domain.lower() == "users.noreply.github.com"
                or local.lower() in ("noreply", "no-reply")):
            continue
        personal.append("email address")
        break
    if CARD_SHAPE.search(line):
        personal.append("card-number shape")
    if NATIONAL_ID_SHAPE.search(line):
        personal.append("national-ID shape")
    return secrets, personal


def secret_kinds(text):
    """Unique credential kinds across multi-line `text` (skipping EXAMPLE lines)."""
    kept = "\n".join(line for line in (text or "").splitlines() if "EXAMPLE" not in line)
    if not kept.strip():
        return []
    found = []
    for kind, pattern in SECRET_PATTERNS:
        if re.search(pattern, kept):
            found.append(kind)
    for _scheme, _user, password, rest in URL_PASSWORD.findall(kept):
        if _is_real_url_password(password, rest):
            found.append("URL with embedded password")
            break
    return found


def pii_kinds(text):
    """Unique personal-data kinds across multi-line `text` (skipping EXAMPLE lines)."""
    found = []
    for line in (text or "").splitlines():
        if "EXAMPLE" in line:
            continue
        _, personal = sensitive_kinds(line)
        for p in personal:
            if p not in found:
                found.append(p)
    return found


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (IOError, OSError, UnicodeDecodeError):
        return ""


def _active_patterns(path):
    """Read active glob patterns from .ai-sdlc/*.txt, stripping `#` comment lines and
    whitespace-preceded inline `# <tag>` comments."""
    patterns = []
    for raw in _read_text(path).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pat = re.split(r"\s+#", stripped, maxsplit=1)[0].strip()
        if pat:
            patterns.append(pat)
    return patterns


def _project_root(cwd):
    for key in ("CLAUDE_PROJECT_DIR", "GEMINI_PROJECT_DIR", "CURSOR_PROJECT_DIR"):
        val = os.environ.get(key)
        if val and os.path.isdir(val):
            return os.path.realpath(val)
    return os.path.realpath(cwd)


def _rel_path(payload, cwd, root):
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    raw = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
        or ""
    )
    if not isinstance(raw, str) or not raw.strip():
        return ""
    base = cwd
    p_cwd = payload.get("cwd")
    if isinstance(p_cwd, str) and p_cwd.strip() and os.path.isdir(p_cwd):
        base = os.path.realpath(p_cwd)
    full = raw if os.path.isabs(raw) else os.path.join(base, raw)
    # os.path.realpath resolves both existing file symlinks and parent directory
    # symlinks when creating a brand-new file inside a symlinked directory.
    real = os.path.realpath(full)
    root_real = os.path.realpath(root)
    if real == root_real:
        return "."
    if real.startswith(root_real + os.sep):
        return real[len(root_real) + 1:].replace(os.sep, "/")
    return real.replace(os.sep, "/")


def _flatten_cmd(cmd):
    cmd = re.sub(r"\\\r?\n", " ", cmd or "")
    return re.sub(r"\r?\n", " ", cmd)


def is_git_commit(cmd):
    return bool(GIT_COMMIT_RE.search(_flatten_cmd(cmd)))


def commit_args_after_git_commit(cmd):
    flat = _flatten_cmd(cmd)
    m = GIT_COMMIT_RE.search(flat)
    if not m:
        return ""
    return flat[m.end():]


def resolve_git_worktree(cmd, cwd, root):
    """Determine which git worktree directory a `git commit` command actually targets."""
    active = cwd
    flat = _flatten_cmd(cmd)
    m_commit = GIT_COMMIT_RE.search(flat)
    prefix_cmd = flat[:m_commit.start()] if m_commit else flat
    commit_tok = m_commit.group(0) if m_commit else ""

    # 1. Check `cd <dir>` earlier in the compound command.
    for cd_match in re.finditer(r"(?:^|[;&|()\s])cd\s+([^\s;&|()]+)", prefix_cmd):
        raw_dir = cd_match.group(1).strip("'\"")
        cand = raw_dir if os.path.isabs(raw_dir) else os.path.join(active, raw_dir)
        if os.path.isdir(cand):
            active = os.path.realpath(cand)

    # 2. Check `git -C <dir> commit` or `git --work-tree <dir> commit`.
    try:
        tokens = shlex.split(commit_tok)
    except ValueError:
        tokens = commit_tok.split()
    i = 0
    while i < len(tokens):
        if tokens[i] in ("-C", "--work-tree") and i + 1 < len(tokens):
            cand = tokens[i + 1]
            cand = cand if os.path.isabs(cand) else os.path.join(active, cand)
            if os.path.isdir(cand):
                active = os.path.realpath(cand)
            i += 2
            continue
        i += 1

    for candidate in (active, root):
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=candidate,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            if proc.returncode == 0:
                top = proc.stdout.decode("utf-8", "replace").strip()
                if top and os.path.isdir(top):
                    return os.path.realpath(top)
        except Exception:
            pass
    return os.path.realpath(root)


def _profile_info(root):
    raw = _read_text(os.path.join(root, ".ai-sdlc", "profile.json"))
    if not raw:
        return "", "docs"
    try:
        data = json.loads(raw)
    except ValueError:
        return "", "docs"
    if not isinstance(data, dict):
        return "", "docs"
    prefix = re.sub(r"[^A-Za-z]", "", str(data.get("prefix") or ""))
    docs_dir = str(data.get("docs_dir") or "docs").strip("/") or "docs"
    return prefix, docs_dir


def _has_legacy_id(root, docs_dir, text):
    tokens = set(re.findall(r"\b([A-Za-z][0-9]+(?:\.[0-9]+)*)\b", text or ""))
    if not tokens:
        return False
    items_dir = os.path.join(root, docs_dir, "project", "items")
    for tok in tokens:
        if os.path.isfile(os.path.join(items_dir, tok + ".json")):
            return True
    backlog_path = os.path.join(root, docs_dir, "project", "backlog.md")
    backlog = _read_text(backlog_path)
    if not backlog:
        return False
    for tok in tokens:
        pat = re.compile(r"^\|\s*" + re.escape(tok) + r"\s*\|", re.MULTILINE)
        if pat.search(backlog):
            return True
    return False


def check_work_item_message(root, text):
    """Validate commit message or `git commit -m` command string for a work item ID.
    Returns None when valid, or a denial reason string."""
    prefix, docs_dir = _profile_info(root)
    if not prefix:
        return None
    id_core = r"(?:%s-[0-9]+|#[0-9]+|GH-[0-9]+)" % re.escape(prefix)
    trailer_id_re = re.compile(
        r"^(?:%s|[A-Za-z][0-9]+(?:\.[0-9]+)*)$" % id_core, re.IGNORECASE
    )
    trailers = re.findall(
        r"^[ \t]*Work-Item:[ \t]*([^\s\"']+)", text or "", flags=re.MULTILINE
    )
    if trailers:
        last_trailer = trailers[-1]
        if trailer_id_re.match(last_trailer):
            return None
        return (
            "work item ID: the Work-Item trailer names no ID (%s); write Work-Item: %s-###."
            % (last_trailer, prefix)
        )
    inline_re = re.compile(
        r"(?:^|[^A-Za-z0-9])%s(?:[^A-Za-z0-9]|$)" % id_core, re.IGNORECASE
    )
    if inline_re.search(text or ""):
        return None
    if _has_legacy_id(root, docs_dir, text):
        return None
    return (
        "work item ID: put %s-### in the commit message (or a Work-Item: trailer); "
        "create the backlog item first if there is none." % prefix
    )


def eval_work_item_id(payload, cwd, root):
    cmd = str((payload.get("tool_input") or {}).get("command") or "")
    if not is_git_commit(cmd):
        return None
    after = commit_args_after_git_commit(cmd)
    if not COMMIT_MSG_FLAG_RE.search(after):
        return None
    # A commit that provably targets a different repository (a literal `cd`/`-C` path
    # outside this project) is not this project's to trace. Unresolvable targets, such
    # as shell variables, stay enforced.
    if not _same_repository(resolve_git_worktree(cmd, cwd, root), root):
        return None
    return check_work_item_message(root, cmd)


def _git_common_dir(path):
    try:
        proc = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                              cwd=path, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return os.path.realpath(proc.stdout.decode("utf-8", "replace").strip())


def _same_repository(target, root):
    if os.path.realpath(target) == os.path.realpath(root):
        return True
    a, b = _git_common_dir(target), _git_common_dir(root)
    # Fail closed: only a target that is provably its own repository is skipped.
    return not a or a == b


def eval_protected_paths(payload, cwd, root):
    list_rel = ".ai-sdlc/protected.txt"
    list_path = os.path.join(root, list_rel)
    if not os.path.isfile(list_path):
        return None
    rel = _rel_path(payload, cwd, root)
    if not rel:
        return None
    if rel == list_rel:
        return (
            "protected paths are the human's list: propose the change to %s instead of making it."
            % list_rel
        )
    for pat in _active_patterns(list_path):
        if fnmatch.fnmatchcase(rel, pat):
            return (
                "single-writer path (%s in .ai-sdlc/protected.txt): change what generates it, or ask its owner."
                % rel
            )
    return None


def eval_test_lock(payload, cwd, root):
    list_rel = ".ai-sdlc/test-lock.txt"
    list_path = os.path.join(root, list_rel)
    if not os.path.isfile(list_path):
        return None
    rel = _rel_path(payload, cwd, root)
    if not rel:
        return None
    if rel == list_rel:
        return (
            "the test-lock list is the human's: add a lock from the shell after committing "
            "the reproducing test; ask a human to release one."
        )
    for pat in _active_patterns(list_path):
        if fnmatch.fnmatchcase(rel, pat):
            return (
                "locked reproducing test (%s): make it pass by changing the code under test, "
                "not the test; if the test is wrong, stop and say why." % rel
            )
    return None


def _check_builtin_shell_guards(cmd):
    """Block unapproved shell bypasses against Nuhut's own guard/lock files and
    `sdlc.py fix unlock-tests` unless AI_SDLC_APPROVAL is set."""
    if os.environ.get("AI_SDLC_APPROVAL"):
        return None
    flat = _flatten_cmd(cmd)
    if re.search(r"\bunlock-tests\b|--unlock-tests\b", flat):
        return (
            "unlocking reproducing tests requires human approval or verified `sdlc.py finish <ID>`; "
            "ask a human or run with AI_SDLC_APPROVAL set."
        )
    for guard_name in ("protected.txt", "gates.txt"):
        if guard_name in flat and GUARD_WRITE_TOKEN_RE.search(flat):
            return (
                ".ai-sdlc/%s is human-owned: propose the change instead of modifying it from the shell."
                % guard_name
            )
    if "test-lock.txt" in flat and GUARD_WRITE_TOKEN_RE.search(flat):
        if SAFE_LOCK_APPEND_RE.match(flat):
            return None
        return (
            "the test-lock list cannot be truncated, overwritten, or unlocked from the shell without "
            "AI_SDLC_APPROVAL (only appending a new lock with `echo '<glob>' >> .ai-sdlc/test-lock.txt` "
            "is permitted; verified `sdlc.py finish <ID>` releases completed locks automatically)."
        )
    return None


def eval_approval_gate(payload, cwd, root):
    list_rel = ".ai-sdlc/gates.txt"
    list_path = os.path.join(root, list_rel)
    rel = _rel_path(payload, cwd, root)
    if rel:
        if rel == list_rel and os.path.isfile(list_path):
            return (
                "gated commands are the human's list: propose the change to %s instead of making it."
                % list_rel
            )
        return None
    cmd = str((payload.get("tool_input") or {}).get("command") or "")
    if not cmd:
        return None
    builtin_deny = _check_builtin_shell_guards(cmd)
    if builtin_deny:
        return builtin_deny
    if not os.path.isfile(list_path):
        return None
    for pat in _active_patterns(list_path):
        if fnmatch.fnmatchcase(cmd, pat) or fnmatch.fnmatchcase(_flatten_cmd(cmd), pat):
            if os.environ.get("AI_SDLC_APPROVAL"):
                return None
            return (
                "human-gated command (%s in .ai-sdlc/gates.txt): stop and hand the human the exact "
                "command, its effect and its rollback." % pat
            )
    return None


def _git_output(worktree, args):
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            cwd=worktree,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace")
    except Exception:
        return 1, ""


def eval_secret_guard(payload, cwd, root):
    cmd = str((payload.get("tool_input") or {}).get("command") or "")
    if not is_git_commit(cmd):
        return None
    wt = resolve_git_worktree(cmd, cwd, root)
    flat = _flatten_cmd(cmd)
    rc_head, _ = _git_output(wt, ["rev-parse", "--verify", "--quiet", "HEAD"])
    if rc_head == 0 and COMMIT_ALL_FLAG_RE.search(flat):
        _, diff = _git_output(wt, ["diff", "HEAD", "--unified=0"])
    else:
        _, diff = _git_output(wt, ["diff", "--cached", "--unified=0"])
    if re.search(r"\bgit\s+add\b", flat):
        _, untracked = _git_output(wt, ["ls-files", "--others", "--exclude-standard"])
        extra = []
        for uf in untracked.splitlines():
            uf = uf.strip()
            if not uf:
                continue
            uf_path = os.path.join(wt, uf)
            if os.path.isfile(uf_path):
                for line in _read_text(uf_path).splitlines():
                    extra.append("+" + line)
        if extra:
            diff = (diff + "\n" if diff else "") + "\n".join(extra)
    if not diff:
        return None
    added_lines = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++ ") and "EXAMPLE" not in line
    ]
    if not added_lines:
        return None
    kinds = secret_kinds("\n".join(added_lines))
    if not kinds:
        return None
    return (
        "no secrets in the repo: the staged changes add a %s; unstage it, keep it in the "
        "environment, rotate it if it was pushed (a fixture line containing EXAMPLE passes)."
        % ", ".join(kinds)
    )


def eval_doc_leak_guard(payload, cwd, root):
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    parts = []
    if isinstance(tool_input.get("content"), str) and tool_input.get("content"):
        parts.append(tool_input["content"])
    elif isinstance(tool_input.get("new_string"), str) and tool_input.get("new_string"):
        parts.append(tool_input["new_string"])
    elif isinstance(tool_input.get("edits"), list):
        for ed in tool_input["edits"]:
            if isinstance(ed, dict) and isinstance(ed.get("new_string"), str):
                parts.append(ed["new_string"])
    content = "\n".join(parts)
    if not content:
        return None
    kinds = secret_kinds(content)
    if kinds:
        return (
            "no secrets in files: this write holds a %s; name the secret and where it is "
            "stored instead of its value (a fixture line containing EXAMPLE passes)."
            % ", ".join(kinds)
        )
    return None


RULE_DISPATCH = {
    "work-item-id": eval_work_item_id,
    "protected-paths": eval_protected_paths,
    "test-lock": eval_test_lock,
    "approval-gate": eval_approval_gate,
    "secret-guard": eval_secret_guard,
    "doc-leak-guard": eval_doc_leak_guard,
}


def normalize_payload(raw_payload, harness):
    if not isinstance(raw_payload, dict):
        raise ValueError("payload must be a JSON object")
    payload = dict(raw_payload)
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}
    else:
        ti = dict(ti)
    if harness == "cursor":
        if "command" in payload and "command" not in ti:
            ti["command"] = payload["command"]
        if not payload.get("tool_name"):
            payload["tool_name"] = "Bash"
    payload["tool_input"] = ti
    return payload


def format_verdict(harness, deny_reason):
    if deny_reason:
        clean = " ".join(str(deny_reason).splitlines()).strip()
        if harness == "cursor":
            return json.dumps(
                {"permission": "deny", "agent_message": clean, "user_message": clean},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        if harness == "gemini":
            return json.dumps(
                {"decision": "deny", "reason": clean},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": clean,
                }
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if harness == "cursor":
        return json.dumps({"permission": "allow"}, separators=(",", ":"))
    if harness == "gemini":
        return "{}"
    return ""


def run_agent_hook(harness, rule):
    rule = re.sub(r"\.sh$", "", rule or "")
    if rule not in RULE_DISPATCH:
        out = format_verdict(harness, None)
        if out:
            sys.stdout.write(out + "\n")
        return 0
    cwd = os.path.realpath(os.getcwd())
    root = _project_root(cwd)
    raw_stdin = sys.stdin.read()
    try:
        parsed = json.loads(raw_stdin) if raw_stdin.strip() else {}
        payload = normalize_payload(parsed, harness)
        p_cwd = payload.get("cwd")
        if isinstance(p_cwd, str) and p_cwd.strip() and os.path.isdir(p_cwd):
            cwd = os.path.realpath(p_cwd)
        reason = RULE_DISPATCH[rule](payload, cwd, root)
    except Exception as exc:
        reason = "hook %s failed closed (%s)" % (rule, exc.__class__.__name__)
    out = format_verdict(harness, reason)
    if out:
        sys.stdout.write(out + "\n")
    return 0


def run_git_pre_commit():
    cwd = os.path.realpath(os.getcwd())
    wt = resolve_git_worktree("", cwd, cwd)
    _, diff = _git_output(wt, ["diff", "--cached", "--unified=0"])
    if not diff:
        return 0
    added = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++ ") and "EXAMPLE" not in line
    ]
    if not added:
        return 0
    kinds = secret_kinds("\n".join(added))
    if not kinds:
        return 0
    sys.stderr.write(
        "nuhut: no secrets in the repo: the staged changes add a %s; unstage it, keep it in "
        "the environment, rotate it if it was pushed (a fixture line containing EXAMPLE passes).\n"
        % ", ".join(kinds)
    )
    return 1


def run_git_commit_msg(msg_file):
    if not msg_file:
        return 0
    # Resolve msg_file relative to caller's cwd BEFORE locating repo toplevel.
    msg_path = os.path.abspath(msg_file)
    if not os.path.isfile(msg_path):
        return 0
    cwd = os.path.realpath(os.getcwd())
    wt = resolve_git_worktree("", cwd, cwd)
    raw = _read_text(msg_path)
    lines = [line for line in raw.splitlines() if not line.startswith("#")]
    msg = "\n".join(lines).lstrip()
    if re.match(r"^(?:Merge |Revert |fixup! |squash! )", msg):
        return 0
    reason = check_work_item_message(wt, msg)
    if reason:
        sys.stderr.write("nuhut: %s\n" % " ".join(reason.splitlines()))
        return 1
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return 0
    cmd = argv[0]
    if cmd == "run":
        harness = "claude"
        rule = ""
        i = 1
        while i < len(argv):
            if argv[i] == "--harness" and i + 1 < len(argv):
                harness = argv[i + 1]
                i += 2
            else:
                rule = argv[i]
                i += 1
        return run_agent_hook(harness, rule)
    if cmd == "git-pre-commit":
        return run_git_pre_commit()
    if cmd == "git-commit-msg":
        return run_git_commit_msg(argv[1] if len(argv) > 1 else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())

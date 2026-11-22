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
- Reads shell commands for their write targets (redirects, tee, sed -i, cp/mv,
  git checkout, python -c open(..., 'w')) so a shell write to a locked test,
  a protected path or a trust anchor is denied while reads pass. This is
  best-effort; `git-pre-commit` is the authoritative backstop.
- AI_SDLC_APPROVAL is a local guardrail any process can set, not a verified
  approval.

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


def _active_patterns(path, text=None):
    """Read active glob patterns from .ai-sdlc/*.txt (or from `text`), stripping `#`
    comment lines and whitespace-preceded inline `# <tag>` comments."""
    patterns = []
    for raw in (_read_text(path) if text is None else text).splitlines():
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


TEST_LOCK_LIST = ".ai-sdlc/test-lock.txt"
PROTECTED_LIST = ".ai-sdlc/protected.txt"
GATES_LIST = ".ai-sdlc/gates.txt"

SHELL_PUNCT = "();<>|&\n"
INLINE_SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
COMMAND_PREFIXES = ("sudo", "doas", "env", "command", "builtin", "nohup", "time", "nice", "exec")
PY_OPEN_WRITE_RE = re.compile(
    r"open\(\s*[rbuf]*(['\"])(.+?)\1\s*,\s*(?:mode\s*=\s*)?[rbuf]*(['\"])([^'\"]*)\3"
)
PY_PATH_WRITE_RE = re.compile(
    r"Path\(\s*[rbuf]*(['\"])(.+?)\1\s*\)\s*\.\s*(?:write_text|write_bytes|touch|unlink|rename|replace)\b"
)
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
CANDIDATE_RE = re.compile(r"[^\s'\"`;|&<>(),=]+")


def _fold(text):
    # macOS file systems are case-insensitive by default: TESTS/x.py names tests/x.py.
    return text.lower() if sys.platform == "darwin" else text


def _glob_hit(rel, patterns):
    """Return the first glob in `patterns` that matches the root-relative path `rel`."""
    if not rel:
        return None
    target = _fold(rel)
    for pat in patterns:
        clean = pat[2:] if pat.startswith("./") else pat
        if fnmatch.fnmatchcase(target, _fold(clean)):
            return pat
    return None


def _trust_anchors(root):
    """Paths that decide what the kit trusts. Only a human changes them."""
    _, docs_dir = _profile_info(root)
    return (
        ".ai-sdlc/extensions", ".ai-sdlc/extensions/*",
        ".ai-sdlc/local/extensions", ".ai-sdlc/local/extensions/*",
        ".ai-sdlc/manifest.json",
        docs_dir + "/project/people.json",
    )


def _trust_anchor_denial(rel, root):
    if _glob_hit(rel, _trust_anchors(root)):
        return (
            "%s is a trust anchor (extensions, the kit manifest, people.json): only a human "
            "changes it; propose the change instead of making it." % rel
        )
    return None


def _normalise_target(raw, base, root):
    """Resolve a shell word to a root-relative path, or None when it cannot be known
    statically (a variable, a command substitution, a glob)."""
    if not raw or raw == "-" or any(c in raw for c in "$`"):
        return None
    if raw.startswith("~"):
        raw = os.path.expanduser(raw)
    full = raw if os.path.isabs(raw) else os.path.join(base, raw)
    real = os.path.realpath(full)
    root_real = os.path.realpath(root)
    if real == root_real:
        return "."
    if real.startswith(root_real + os.sep):
        return real[len(root_real) + 1:].replace(os.sep, "/")
    return real.replace(os.sep, "/")


def _strip_heredocs(cmd):
    """Drop here-document bodies: they are data, and an apostrophe in one would make the
    tokeniser fail on a command that writes nothing guarded."""
    out, pending = [], []
    for line in cmd.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending.extend(m.group(2) for m in HEREDOC_RE.finditer(line))
    return "\n".join(out)


def _shell_tokens(cmd):
    text = re.sub(r"\\\r?\n", " ", cmd or "")
    text = _strip_heredocs(text.replace("\r\n", "\n"))
    lex = shlex.shlex(text, posix=True, punctuation_chars=SHELL_PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = "#"
    return list(lex)


def _is_punct(tok):
    return bool(tok) and all(c in SHELL_PUNCT for c in tok)


def _split_simple_commands(tokens):
    """Yield (words, redirect_targets) for each simple command in a token stream."""
    words, targets = [], []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not _is_punct(tok):
            words.append(tok)
            i += 1
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        nxt_word = nxt and not _is_punct(nxt)
        if "(" in tok or ")" in tok:
            yield words, targets
            words, targets = [], []
            i += 1
            continue
        split = min([tok.index(c) for c in "<>" if c in tok] or [len(tok)])
        sep, redir = tok[:split], tok[split:]
        if sep:
            yield words, targets
            words, targets = [], []
        if not redir:
            i += 1
            continue
        if words and words[-1].isdigit() and not sep:
            words.pop()  # the file descriptor of `2>`
        if ">" in redir:
            dup = redir.endswith("&") and nxt_word and (nxt.isdigit() or nxt == "-")
            if nxt_word and not dup:
                targets.append(nxt)
        i += 2 if nxt_word else 1
    yield words, targets


def _operands(args, takes_value=()):
    out, i, only = [], 0, False
    while i < len(args):
        a = args[i]
        if only or not a.startswith("-") or a == "-":
            out.append(a)
        elif a == "--":
            only = True
        elif a in takes_value:
            i += 1
        i += 1
    return out


def _command_targets(words, base):
    """Return (targets, inline, new_base) for one simple command. `targets` are the paths
    the command writes, `inline` marks eval / sh -c / python -c, `new_base` follows cd."""
    while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])
                     or os.path.basename(words[0]) in COMMAND_PREFIXES):
        words = words[1:]
        while words and words[0].startswith("-"):
            words = words[1:]
    if not words:
        return [], False, base
    name = os.path.basename(words[0])
    args = words[1:]
    targets = []
    if name in ("cd", "pushd"):
        dest = _operands(args)
        if dest and not any(c in dest[0] for c in "$`~"):
            return [], False, os.path.join(base, dest[0])
        return [], False, base
    if name == "eval":
        return [], True, base
    if name in INLINE_SHELLS:
        inline = any(a.startswith("-") and not a.startswith("--") and "c" in a[1:] for a in args)
        return [], inline, base
    if re.match(r"^(?:python[0-9.]*|pypy[0-9.]*)$", name):
        if "-c" in args:
            idx = args.index("-c")
            code = args[idx + 1] if idx + 1 < len(args) else ""
            for m in PY_OPEN_WRITE_RE.finditer(code):
                if re.search(r"[wax+]", m.group(4)):
                    targets.append(m.group(2))
            targets.extend(m.group(2) for m in PY_PATH_WRITE_RE.finditer(code))
            return targets, True, base
        return [], False, base
    if name == "tee":
        return _operands(args), False, base
    if name in ("sed", "gsed", "perl"):
        flags = [a for a in args if a.startswith("-") and not a.startswith("--")]
        inplace = any("i" in a[1:] for a in flags) or any(a.startswith("--in-place") for a in args)
        if inplace:
            return _operands(args, ("-e", "-f", "--expression", "--file")), False, base
        return [], False, base
    if name in ("cp", "mv", "install", "ln", "gcp", "gmv"):
        ops = _operands(args, ("-m", "-o", "-g", "-S", "--suffix", "--mode", "--owner", "--group"))
        dest_dir = None
        for i, a in enumerate(args):
            if a in ("-t", "--target-directory") and i + 1 < len(args):
                dest_dir = args[i + 1]
            elif a.startswith("--target-directory="):
                dest_dir = a.split("=", 1)[1]
        if dest_dir is not None:
            sources = [o for o in ops if o != dest_dir]
            dests = [dest_dir]
        elif len(ops) >= 2:
            sources, dests = ops[:-1], [ops[-1]]
        else:
            return [], False, base
        dest = dests[0]
        full = dest if os.path.isabs(dest) else os.path.join(base, dest)
        if dest_dir is not None or dest.endswith("/") or os.path.isdir(full):
            targets.extend(os.path.join(dest, os.path.basename(s.rstrip("/"))) for s in sources)
        targets.append(dest)
        if name in ("mv", "gmv"):
            targets.extend(sources)  # a move deletes its source
        return targets, False, base
    if name in ("rm", "unlink", "shred", "rmdir"):
        return _operands(args), False, base
    if name == "truncate":
        ops = _operands(args, ("-s", "-r", "--size", "--reference"))
        return ops, False, base
    if name == "dd":
        return [a[3:] for a in args if a.startswith("of=")], False, base
    if name == "git":
        git_base = base
        i = 0
        while i < len(args) and args[i].startswith("-"):
            if args[i] == "-C" and i + 1 < len(args):
                git_base = os.path.join(git_base, args[i + 1])
                i += 2
                continue
            if args[i] in ("-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(args):
                i += 2
                continue
            i += 1
        sub = args[i] if i < len(args) else ""
        rest = args[i + 1:]
        if sub in ("checkout", "restore", "rm", "mv"):
            ops = _operands(rest, ("-s", "--source", "-b", "-B"))
            return [os.path.join(git_base, o) for o in ops], False, base
    return [], False, base


def shell_write_targets(cmd, cwd, root):
    """Parse a shell command and return (targets, inline_code, candidates).

    `targets` are the root-relative paths the command writes (redirect targets, tee, sed -i,
    perl -i, cp/mv/install destinations, truncate, dd of=, git checkout/restore paths, literal
    open(..., 'w') paths in python -c). `inline_code` is True when the command runs eval,
    sh -c, bash -c or python -c, whose effects the parser cannot see; `candidates` then holds
    every path-like word in the command. Raises ValueError when the command cannot be parsed."""
    tokens = _shell_tokens(cmd)
    base = cwd
    targets, inline = [], False
    for words, redirects in _split_simple_commands(tokens):
        for raw in redirects:
            targets.append(_normalise_target(raw, base, root))
        found, is_inline, base = _command_targets(list(words), base)
        inline = inline or is_inline
        for raw in found:
            targets.append(_normalise_target(raw, base, root))
    candidates = []
    if inline:
        for word in CANDIDATE_RE.findall(_flatten_cmd(cmd)):
            candidates.append(_normalise_target(word, cwd, root))
    return [t for t in targets if t], inline, [c for c in candidates if c]


def _shell_denial(cmd, cwd, root, checks):
    """Return a deny reason when `cmd` writes a path one of `checks` guards.

    `checks` is a sequence of (patterns, reason_format); reason_format takes the path."""
    try:
        targets, inline, candidates = shell_write_targets(cmd, cwd, root)
    except ValueError as exc:
        return (
            "the command could not be parsed (%s), so the write guards cannot see what it "
            "writes: fix the quoting, or write the file with the edit tool." % exc
        )
    for patterns, reason in checks:
        for target in targets:
            if _glob_hit(target, patterns):
                return reason % target
    if inline:
        for patterns, _ in checks:
            for cand in candidates:
                if _glob_hit(cand, patterns):
                    return (
                        "this command runs inline code (eval, sh -c, bash -c or python -c) that "
                        "names the guarded path %s, so the hook cannot see what it writes: run "
                        "the steps directly instead." % cand
                    )
    return None


LOCKED_SHELL_REASON = (
    "locked reproducing test (%s) is written by this command: make it pass by changing the "
    "code under test, not the test; if the test is wrong, stop and say why."
)
PROTECTED_SHELL_REASON = (
    "single-writer path (%s, listed in .ai-sdlc/protected.txt) is written by this command: "
    "change what generates it, or ask its owner."
)


def _command_of(payload):
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    cmd = tool_input.get("command")
    return cmd if isinstance(cmd, str) else ""


def _lock_checks(root):
    path = os.path.join(root, TEST_LOCK_LIST)
    if not os.path.isfile(path):
        return []
    return [(_active_patterns(path), LOCKED_SHELL_REASON)]


def _protected_checks(root):
    path = os.path.join(root, PROTECTED_LIST)
    if not os.path.isfile(path):
        return []
    return [(_active_patterns(path), PROTECTED_SHELL_REASON)]


def eval_protected_paths(payload, cwd, root):
    list_rel = PROTECTED_LIST
    list_path = os.path.join(root, list_rel)
    rel = _rel_path(payload, cwd, root)
    if not rel:
        cmd = _command_of(payload)
        checks = _protected_checks(root)
        if cmd and checks:
            return _shell_denial(cmd, cwd, root, checks)
        return None
    anchor = _trust_anchor_denial(rel, root)
    if anchor:
        return anchor
    if not os.path.isfile(list_path):
        return None
    if _glob_hit(rel, (list_rel,)):
        return (
            "protected paths are the human's list: propose the change to %s instead of making it."
            % list_rel
        )
    if _glob_hit(rel, _active_patterns(list_path)):
        return (
            "single-writer path (%s in .ai-sdlc/protected.txt): change what generates it, or ask its owner."
            % rel
        )
    return None


def eval_test_lock(payload, cwd, root):
    list_rel = TEST_LOCK_LIST
    list_path = os.path.join(root, list_rel)
    if not os.path.isfile(list_path):
        return None
    rel = _rel_path(payload, cwd, root)
    if not rel:
        cmd = _command_of(payload)
        if cmd:
            return _shell_denial(cmd, cwd, root, _lock_checks(root))
        return None
    if _glob_hit(rel, (list_rel,)):
        return (
            "the test-lock list is the human's: add a lock from the shell after committing "
            "the reproducing test; ask a human to release one."
        )
    if _glob_hit(rel, _active_patterns(list_path)):
        return (
            "locked reproducing test (%s): make it pass by changing the code under test, "
            "not the test; if the test is wrong, stop and say why." % rel
        )
    return None


def _check_builtin_shell_guards(cmd, cwd=None, root=None):
    """Block unapproved shell writes to Nuhut's own guard lists and trust anchors, and
    `sdlc.py fix unlock-tests`, unless AI_SDLC_APPROVAL is set. AI_SDLC_APPROVAL is a local
    guardrail an agent could set itself, not a verified approval."""
    if os.environ.get("AI_SDLC_APPROVAL"):
        return None
    flat = _flatten_cmd(cmd)
    if re.search(r"\bunlock-tests\b|--unlock-tests\b", flat):
        return (
            "unlocking reproducing tests requires human approval or verified `sdlc.py finish <ID>`; "
            "ask a human or run with AI_SDLC_APPROVAL set."
        )
    cwd = os.path.realpath(cwd or os.getcwd())
    root = os.path.realpath(root or cwd)
    if SAFE_LOCK_APPEND_RE.match(flat):
        return None
    checks = [
        ((PROTECTED_LIST,), ".ai-sdlc/protected.txt is human-owned: propose the change instead "
                            "of modifying it from the shell (%s)."),
        ((GATES_LIST,), ".ai-sdlc/gates.txt is human-owned: propose the change instead of "
                        "modifying it from the shell (%s)."),
        ((TEST_LOCK_LIST,),
         "the test-lock list cannot be truncated, overwritten, or unlocked from the shell without "
         "AI_SDLC_APPROVAL (only appending a new lock with `echo '<glob>' >> .ai-sdlc/test-lock.txt` "
         "is permitted; verified `sdlc.py finish <ID>` releases completed locks automatically) (%s)."),
        (_trust_anchors(root),
         "%s is a trust anchor (extensions, the kit manifest, people.json): only a human changes "
         "it; propose the change instead of modifying it from the shell."),
    ]
    return _shell_denial(cmd, cwd, root, checks)


def eval_approval_gate(payload, cwd, root):
    list_rel = GATES_LIST
    list_path = os.path.join(root, list_rel)
    rel = _rel_path(payload, cwd, root)
    if rel:
        if _glob_hit(rel, (list_rel,)) and os.path.isfile(list_path):
            return (
                "gated commands are the human's list: propose the change to %s instead of making it."
                % list_rel
            )
        return _trust_anchor_denial(rel, root)
    cmd = _command_of(payload)
    if not cmd:
        return None
    builtin_deny = _check_builtin_shell_guards(cmd, cwd, root)
    if builtin_deny:
        return builtin_deny
    # Shell writes to locked tests and single-writer paths: the agent-side, best-effort half.
    # The pre-commit backstop (run_git_pre_commit) is the authoritative one.
    path_checks = _lock_checks(root) + _protected_checks(root)
    if path_checks:
        path_deny = _shell_denial(cmd, cwd, root, path_checks)
        if path_deny:
            return path_deny
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


# Hook dialects: how a tool hands a tool call to a hook and how it reads the answer. The
# implementations live here, in core; a harness record in an extension picks one by name
# (`hooks.dialect`), and an extension cannot ship a new one (ADR 0003).
def _claude_payload(payload, ti):
    return payload, ti


def _cursor_payload(payload, ti):
    # beforeShellExecution carries the command at the top level and no tool name.
    if "command" in payload and "command" not in ti:
        ti["command"] = payload["command"]
    if not payload.get("tool_name"):
        payload["tool_name"] = "Bash"
    return payload, ti


def _claude_verdict(clean):
    if clean is None:
        return ""
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


def _gemini_verdict(clean):
    if clean is None:
        return "{}"
    return json.dumps({"decision": "deny", "reason": clean}, ensure_ascii=False,
                      separators=(",", ":"))


def _cursor_verdict(clean):
    if clean is None:
        return json.dumps({"permission": "allow"}, separators=(",", ":"))
    return json.dumps({"permission": "deny", "agent_message": clean, "user_message": clean},
                      ensure_ascii=False, separators=(",", ":"))


# name -> (payload normaliser, verdict formatter)
DIALECTS = {
    "claude": (_claude_payload, _claude_verdict),
    "gemini": (_claude_payload, _gemini_verdict),
    "cursor": (_cursor_payload, _cursor_verdict),
}
DEFAULT_DIALECT = "claude"


def dialect_for(harness, root=None):
    """The dialect tool <harness> speaks, from its harness record in the extension
    registry. A built-in tool keeps its built-in dialect even under an override. When the
    registry is missing or broken, a tool named after a dialect uses that dialect, so the
    guards keep answering in the shape the tool reads; anything else gets Claude's."""
    name = harness if harness in DIALECTS else DEFAULT_DIALECT
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import registry
        version = None
        if root:
            try:
                with open(os.path.join(root, ".ai-sdlc", "manifest.json"), encoding="utf-8") as fh:
                    version = (json.load(fh) or {}).get("kit_version")
            except (IOError, OSError, ValueError, AttributeError):
                version = None
        reg = registry.load(root, version=version, warn=False)
        if not reg.missing:
            found = registry.hook_dialect(reg, harness)
            if found in DIALECTS:
                return found
    except Exception:  # the guards must not depend on the registry loading
        pass
    return name


# Extension hook rules (ADR 0003) run with this rule, which every guarded tool wires for
# Bash, Write and Edit, so they need no hook entry of their own.
EXTENSION_RULES_HOST = "approval-gate"


def eval_extension_rules(payload, cwd, root):
    """The deny reason from a built-in or allowed extension's hook rule, or None. A
    project extension's rules run only when the charter's Extensions allowed row names
    it on the default branch and its files match the hashes pinned at `ext add`."""
    if not root or not (os.path.isdir(os.path.join(root, ".ai-sdlc", "local", "extensions"))
                        or os.path.isdir(os.path.join(root, ".ai-sdlc", "extensions"))):
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import registry
    version = _kit_version(root)
    reg = registry.load(root, kit=None, warn=False, version=version)
    records = reg.code_records("hook_rules")
    if not records:
        return None
    if any(reg.extensions[ext_id]["source"] != registry.BUILTIN for ext_id, _ in records):
        # Only now pay for the git reads behind the allow list.
        reg = registry.load(root, kit=None, warn=False, version=version,
                            allowed=registry.trusted_allowed(root))
    return registry.run_hook_rules(reg, payload, cwd, root)


def _kit_version(root):
    try:
        with open(os.path.join(root, ".ai-sdlc", "manifest.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("kit_version") if isinstance(data, dict) else None
    except (IOError, OSError, ValueError):
        return None


def normalize_payload(raw_payload, harness):
    if not isinstance(raw_payload, dict):
        raise ValueError("payload must be a JSON object")
    payload = dict(raw_payload)
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}
    else:
        ti = dict(ti)
    normalise = DIALECTS.get(harness, DIALECTS[DEFAULT_DIALECT])[0]
    payload, ti = normalise(payload, ti)
    payload["tool_input"] = ti
    return payload


def format_verdict(harness, deny_reason):
    """<harness> is a dialect name; an unknown name answers in Claude's shape."""
    clean = " ".join(str(deny_reason).splitlines()).strip() if deny_reason else None
    return DIALECTS.get(harness, DIALECTS[DEFAULT_DIALECT])[1](clean)


def run_agent_hook(harness, rule):
    rule = re.sub(r"\.sh$", "", rule or "")
    cwd = os.path.realpath(os.getcwd())
    root = _project_root(cwd)
    harness = dialect_for(harness, root)
    if rule not in RULE_DISPATCH:
        out = format_verdict(harness, None)
        if out:
            sys.stdout.write(out + "\n")
        return 0
    raw_stdin = sys.stdin.read()
    try:
        parsed = json.loads(raw_stdin) if raw_stdin.strip() else {}
        payload = normalize_payload(parsed, harness)
        p_cwd = payload.get("cwd")
        if isinstance(p_cwd, str) and p_cwd.strip() and os.path.isdir(p_cwd):
            cwd = os.path.realpath(p_cwd)
        reason = RULE_DISPATCH[rule](payload, cwd, root)
        if not reason and rule == EXTENSION_RULES_HOST:
            reason = eval_extension_rules(payload, cwd, root)
    except Exception as exc:
        reason = "hook %s failed closed (%s)" % (rule, exc.__class__.__name__)
    out = format_verdict(harness, reason)
    if out:
        sys.stdout.write(out + "\n")
    return 0


def _guarded_paths_in_commit(wt):
    """The authoritative backstop for the shell guards: staged paths that match a glob in
    .ai-sdlc/test-lock.txt or .ai-sdlc/protected.txt as committed at HEAD.

    Reading the lists from HEAD means a lock added in this commit does not block its own
    reproducing test, and a lock removed in this commit still holds: an unlock is recorded
    by committing the line's removal first. Returns a list of (path, list_rel)."""
    rc, _ = _git_output(wt, ["rev-parse", "--verify", "--quiet", "HEAD"])
    if rc != 0:
        return []
    lists = []
    for list_rel in (TEST_LOCK_LIST, PROTECTED_LIST):
        rc, text = _git_output(wt, ["show", "HEAD:" + list_rel])
        if rc == 0:
            patterns = _active_patterns("", text)
            if patterns:
                lists.append((list_rel, patterns))
    if not lists:
        return []
    _, names = _git_output(wt, ["diff", "--cached", "--name-only", "--no-renames"])
    hits = []
    for name in names.splitlines():
        name = name.strip()
        if not name:
            continue
        for list_rel, patterns in lists:
            if _glob_hit(name, patterns):
                hits.append((name, list_rel))
                break
    return hits


def run_git_pre_commit():
    cwd = os.path.realpath(os.getcwd())
    wt = resolve_git_worktree("", cwd, cwd)
    if not os.environ.get("AI_SDLC_APPROVAL"):
        hits = _guarded_paths_in_commit(wt)
        if hits:
            shown = ", ".join("%s (%s)" % hit for hit in hits[:5])
            sys.stderr.write(
                "nuhut: this commit changes guarded paths: %s; a locked test changes only after "
                "its lock's removal is committed, a single-writer path only through its owner; "
                "set AI_SDLC_APPROVAL for a human-approved change.\n" % shown
            )
            return 1
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

"""Finishing a work item in one command, the session guard that reminds an agent to, and
the record repairs `sdlc.py fix` previews. Imported by sdlc.py, which passes itself in as
`rt`; nothing here runs on import."""

import datetime
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

import shards

SDLC = "python3 .ai-sdlc/bin/sdlc.py"
# What the optional git and claim helpers are expected to raise on an odd repository: a
# missing helper, a filesystem or git failure, an unreadable JSON record. finish only
# reports their results, so these stay quiet; anything else is a bug and goes to stderr.
EXPECTED_HELPER_ERRORS = (ImportError, OSError, ValueError)


def report_unexpected(what, exc):
    sys.stderr.write("finish: %s failed unexpectedly (%s: %s); continuing without it. "
                     "This is a bug in the kit's runtime: please report it.\n"
                     % (what, type(exc).__name__, exc))
TODO = "TODO(finish)"
CANONICAL = {"Now": "In progress", "Next": "Ready", "Blocked": "Blocked", "Parked": "Parked",
             "Later": "Deferred", "Done": "Done", "Dropped": "Dropped"}
KIT_STATUSES = ("In progress", "In review", "Ready", "Blocked", "Parked", "Deferred", "Done",
                "Dropped")
ENTRY_START = re.compile(r"^## [A-Za-z][A-Za-z0-9]*-[0-9]+|^- [0-9]{4}-[0-9]{2}-[0-9]{2} · ")


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _row(cells):
    return "|" + "|".join(" %s " % c if c else " " for c in cells) + "|"


def plain(cell):
    """A table cell without the markdown a human reads past (view.plain)."""
    cell = re.sub(r"_\([^)]*\)_", "", cell or "")
    return re.sub(r"\*\*|__|`|~~", "", cell).strip()


def backlog_lines(project):
    path = project.path(os.path.join(project.docs, "project", "backlog.md"))
    try:
        with open(path, encoding="utf-8") as handle:
            return path, handle.read().split("\n")
    except (IOError, OSError):
        return path, None


def find_row(lines, item):
    """(index of the item's row, its table header cells), or (-1, None)."""
    header = None
    for n, line in enumerate(lines):
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if header is None:
            header = cells
            continue
        if cells and re.sub(r"\*\*|`", "", cells[0]) == item:
            return n, header
    return -1, None


def move_row(project, item, status, extra):
    """Set the item's Status and move its row to the top of the section that holds that
    status (Done and Parked are newest first), filling the section's own columns from
    <extra>. The six shared cells travel with the row. Without such a section, the
    Status cell changes in place."""
    path, lines = backlog_lines(project)
    if lines is None:
        return False
    idx, header = find_row(lines, item)
    if idx < 0 or "Status" not in header:
        return False
    pos = header.index("Status")
    cells = _cells(lines[idx])
    cells += [""] * (len(header) - len(cells))
    cells[pos] = status
    section = re.compile(r"^## +%s\b" % re.escape(status))
    head = next((n for n, line in enumerate(lines) if section.match(line)), -1)
    here = next((n for n in range(idx, -1, -1) if lines[n].startswith("## ")), -1)
    if head < 0 or head == here:
        lines[idx] = _row(cells)
    else:
        del lines[idx]
        if head > idx:
            head -= 1
        top = next((n for n in range(head + 1, len(lines))
                    if lines[n].startswith("## ") or re.match(r"^\s*\|\s*-", lines[n])), len(lines))
        if top >= len(lines) or lines[top].startswith("## "):
            lines[idx:idx] = [_row(cells)]          # the section has no table: leave it put
        else:
            width = len(_cells(lines[top]))
            moved = cells[:pos + 1] + list(extra)
            moved = (moved + [""] * width)[:width]
            lines.insert(top + 1, _row(moved))
            # The template's "no rows yet" line is false once a row exists.
            for n in range(top + 2, min(top + 6, len(lines))):
                if lines[n].startswith("_(No rows yet"):
                    del lines[n]
                    break
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return True


# ---------------------------------------------------------------- finish

def _runs(rows):
    """[(run name, its rows)] in ledger order; a row with no run name is a run alone."""
    runs, index = [], {}
    for n, row in enumerate(rows):
        key = row.get("run") or ("#%d" % n)
        if key not in index:
            index[key] = len(runs)
            runs.append((row.get("run") or "", []))
        runs[index[key]][1].append(row)
    return runs


def required_stages(rt, project):
    """Charter stages that have a command: a full verify run covers every one."""
    return [stage for stage in rt.STAGES
            if rt.charter_commands(project.charter).get(stage, "") not in ("", "absent")]


def verify_state(rt, project, item, commits):
    """(state, run name, its rows, detail) for the latest verify run behind the item.
    state is 'pass', 'fail', 'none', 'partial' (the latest run left charter stages out)
    or 'stale' (the latest run predates the item's newest code commit). Only a full run,
    clean on the newest code commit or a descendant of it, or dirty on its parent,
    passes; detail says what a partial or stale run lacks."""
    all_rows = rt.evidence_matches(project, item, None, commits)
    rows = [r for r in all_rows if r.get("stage") != "bite"]
    if not rows:
        return "none", "", [], ""
    need = required_stages(rt, project)
    newest, parent = rt.newest_code_commit(project, item, commits)
    latest = None
    for name, run in reversed(_runs(rows)):
        covered = set(r.get("stage") for r in run)
        missing = [s for s in need if s not in covered]
        selected = next((r.get("selected") for r in run if r.get("selected")), None)
        commit = run[-1].get("commit") or ""
        dirty = any(r.get("dirty") for r in run)
        fresh = (dirty and commit == parent and bool(parent)) or \
            (not dirty and rt.is_ancestor(project, newest, commit))
        # The newest run that is neither partial nor stale decides; the newest run of all
        # names what is wrong when none qualifies.
        if latest is None and missing:
            ran = sorted(covered, key=lambda s: rt.STAGES.index(s) if s in rt.STAGES else 99)
            latest = ("partial", name, run, "latest run %s covered %s only; missing: %s. Run "
                      "`sdlc.py verify --item %s` with no --stage"
                      % (name or "?", ", ".join(ran) or "nothing", ", ".join(missing), item))
        elif latest is None and selected:
            latest = ("partial", name, run, "latest run %s ran with --stage %s. Run "
                      "`sdlc.py verify --item %s` with no --stage"
                      % (name or "?", ",".join(selected), item))
        elif latest is None and not fresh:
            latest = ("stale", name, run, "latest run %s is on %s%s; the item's newest commit "
                      "is %s. Run `sdlc.py verify --item %s`"
                      % (name or "?", commit[:7], " (dirty)" if dirty else "",
                         (newest or "")[:7], item))
        if selected or missing or not fresh:
            continue
        failed = [r for r in run if "fail" in str(r.get("result", ""))]
        return ("fail" if failed else "pass"), name, run, ""
    return latest


def bite_state(rt, project, item, commits):
    """True when at least one `bite` ledger row for <item> (or its commits) passed."""
    all_rows = rt.evidence_matches(project, item, None, commits)
    bite_rows = [r for r in all_rows if r.get("stage") == "bite"]
    if not bite_rows:
        return False
    return "pass" in str(bite_rows[-1].get("result", "")).lower()


def release_item_test_locks(rt, project, item, commits, verify_ok, bite_ok):
    """Automatically release <item>'s reproducing test locks in .ai-sdlc/test-lock.txt
    once verify (and bite, for untagged branch test files) has passed."""
    if not verify_ok:
        return []
    lock_path = project.path(".ai-sdlc/test-lock.txt")
    if not os.path.isfile(lock_path):
        return []
    raw_text = rt.read(lock_path)
    if not raw_text:
        return []
    touched = set()
    for sha, _, _ in commits:
        for p in project.git("show", "--name-only", "--format=", sha).splitlines():
            if p.strip():
                touched.add(p.strip())
    kept, unlocked = [], []
    tag_re = re.compile(r"#\s*%s\b" % re.escape(item), re.IGNORECASE)
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        pat = re.split(r"\s+#", stripped, maxsplit=1)[0].strip()
        tagged_for_item = bool(tag_re.search(stripped))
        matched_branch_test = bite_ok and any(fnmatch.fnmatchcase(f, pat) for f in touched)
        if tagged_for_item or matched_branch_test:
            unlocked.append(pat)
        else:
            kept.append(line)
    if unlocked:
        with open(lock_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(kept).rstrip("\n") + "\n")
    return unlocked


def resolve_effort(rt, project, item, cells):
    """Resolve effort mode in contract order: item override -> plan override -> charter default -> Normal."""
    sh = shards.load_item(project, item)
    if sh and sh.get("effort") in rt.EFFORT:
        return sh["effort"]
    for cell in cells[2:] if len(cells) > 2 else ():
        cleaned = plain(cell)
        for mode in rt.EFFORT:
            if re.search(r"(?:^|\beffort\s*:\s*)%s\b" % re.escape(mode), cleaned, re.IGNORECASE):
                return mode
    plans_dir = project.path(os.path.join(project.docs, "project", "plans"))
    if os.path.isdir(plans_dir):
        for name in sorted(os.listdir(plans_dir)):
            if (name == item + ".md" or name.startswith(item + "-")) and name.endswith(".md"):
                ptext = rt.read(os.path.join(plans_dir, name))
                m = re.search(r"\*\*Effort(?:\s+mode)?\*\*:\s*`?(Lean|Normal|Beast)`?", ptext, re.I)
                if not m:
                    m = re.search(r"\|\s*\*\*Effort(?:\s+mode)?\*\*\s*\|\s*`?(Lean|Normal|Beast)`?", ptext, re.I)
                if m:
                    return m.group(1).capitalize()
                break
    effort, state = rt.choice(rt.labelled(project.charter, "Default effort mode") or "", rt.EFFORT)
    return effort if state == "decided" else "Normal"


def waiver_approvers(rt, project):
    """([(name as written, handle)], source, people registry): who may waive verify. The
    names come from the charter's Approvers row as it stands on the default branch
    (`rt.trusted_text`), so a branch that adds a name gains nothing until it merges.
    With a people.json registry each name resolves to its handle (None when unknown).
    A placeholder row gives an empty list, which refuses every waiver."""
    names, source = rt.approver_names(project)
    registry = rt.people(project)
    return [(n, rt.resolve_person(registry, n)) for n in names], source, registry


def runner_identity(project, registry, rt):
    """(raw, handle) for the person running this command: NUHUT_USER, else git's
    user.name, resolved through people.json when there is one. NUHUT_USER is an honour
    system value: any process, an agent's included, can set it."""
    raw = (os.environ.get("NUHUT_USER") or "").strip() or \
        project.git("config", "user.name").strip()
    return raw, rt.resolve_person(registry, raw)


def waivers(rt, project, item, handles=None, registry=None):
    """(waivers that count, a line for each that no longer does). A recorded waiver
    counts only while the person who gave it is still in Approvers."""
    if handles is None:
        approvers, _, registry = waiver_approvers(rt, project)
        handles = set(h for _, h in approvers if h)
    kept, dropped = [], []
    for row in rt.ledger(project):
        if not row.get("waived_by") or row.get("item") != item:
            continue
        if rt.resolve_person(registry or {}, row["waived_by"]) in handles:
            kept.append(row)
        else:
            dropped.append("waiver by %s on %s no longer counts: %s is not in Approvers"
                           % (row["waived_by"], (row.get("time") or "?")[:10], row["waived_by"]))
    return kept, dropped


def _interactive():
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def check_waiver(rt, project, by, approvers, source, registry, interactive, act="waive"):
    """None when <by> may waive verify here (or approve, with act="approve"), else the
    reason it may not."""
    noun = "waiver" if act == "waive" else "approval"
    charter = project.charter_path
    if not approvers:
        return ("the charter's Approvers row is blank, so every %s is refused: fill "
                "**Approvers** in %s on the default branch with the people who may %s"
                % (noun, charter, act))
    handle = rt.resolve_person(registry, by)
    if handle is None or handle not in set(h for _, h in approvers if h):
        return ("%s is not in the charter's Approvers row (%s, read from %s): a %s must "
                "name an approver. Add them to **Approvers** in %s on the default branch"
                % (by, ", ".join(n for n, _ in approvers), source, noun, charter))
    raw, runner = runner_identity(project, registry, rt)
    agent = agent_environment(rt, project)
    if not interactive and agent:
        # git user.name is usually the human's own in the checkout an agent works in, and
        # NUHUT_USER is whatever the process sets, so neither proves a person is here.
        return ("an agent cannot %s for %s: this process runs under %s with no terminal. "
                "Ask %s to run it in a terminal" % (act, by, agent, by))
    if not interactive and runner != handle:
        return ("an agent cannot %s for %s; ask %s to run it (this process runs as %r, "
                "from NUHUT_USER or git user.name)" % (act, by, by, raw or "nobody"))
    return None


def agent_environment(rt, project):
    """The agent tool whose environment variables this process carries (CLAUDECODE, ...),
    or "" when none is detected. Best effort: a process can unset them."""
    found = [k for k in getattr(rt, "AGENT_SESSION_ENVS", ()) if os.environ.get(k)]
    try:
        agent = rt.identity(project=project)[0]
    except Exception:
        agent = ""
    if agent not in ("", "unknown", "human"):
        return agent
    return found[0] if found else ""


def stored_waiver_refusal(rt, project, row, approvers, source, registry, interactive):
    """None when a waiver row already in the ledger may close the item in this run, else
    why not. The ledger is a plain file anyone can append to, so a recorded waiver is
    held to the rule `--waive` is: an agent's run without a terminal cannot use one."""
    refused = check_waiver(rt, project, row.get("waived_by") or "", approvers, source,
                           registry, interactive)
    if refused:
        return "a waiver by %s is in the ledger, but it cannot close the item in this run: %s" % (
            row.get("waived_by"), refused)
    return None


# ---------------------------------------------------------------- approvals (NUHT-024)
#
# A merge approval is read from the item branch's GitHub PR reviews. Everything gh prints
# is untrusted data: it is parsed as JSON, logins are checked against GitHub's own pattern
# before they are printed or stored, and nothing from it is run or rendered as markup.
# The AI_SDLC_APPROVAL environment variable is never read here: any process can set it.

GH_LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")
GH_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GH_SHA = re.compile(r"^[0-9a-f]{40}$")
GH_TIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z$")
GH_TIMEOUT = 20
PR_FIELDS = ("reviews,number,headRefOid,author,state,headRepositoryOwner,headRepository,"
             "isCrossRepository,baseRefName")
ITEM_BRANCH = re.compile(r"^(?:[\w.-]+/)?([A-Z][A-Z0-9]*-[0-9]+)(?:-|$)")
SOLO_HINT = ("a solo project can set **Tier 1 approvals** to 1 in the charter, and with "
             "**Local approvals** `on` the approver runs `sdlc.py approve <ID> --by <handle>` "
             "in a terminal; see process/05 Approvals")


def _safe(text):
    """A handle or name as it may go into a backlog cell or a worklog line."""
    return re.sub(r"[|\r\n`]", "", str(text or "")).strip()


def item_branch(rt, project, item):
    """The local branch that holds <item>: the current one when it names the item, else
    the first local branch that does (claims' rule). '' when there is none."""
    current = project.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    m = ITEM_BRANCH.match(current)
    if m and m.group(1) == item:
        return current
    try:
        return rt.runtime_module("claims")._existing_item_branch(project, item) or ""
    except EXPECTED_HELPER_ERRORS:
        return ""
    except Exception as exc:             # noqa: BLE001 -- reported, not swallowed
        report_unexpected("finding the branch of %s" % item, exc)
        return ""


def _gh_json(run, argv, cwd):
    """(parsed JSON, None) or (None, note naming why not). Never raises."""
    try:
        proc = run(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, universal_newlines=True, timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "gh-timeout (no answer in %d s)" % GH_TIMEOUT
    except (OSError, ValueError):
        return None, "gh-failed (gh could not be run)"
    if proc.returncode != 0:
        return None, "gh-failed (gh exited %d: not signed in, or no PR for the branch)" % proc.returncode
    try:
        return json.loads(proc.stdout or ""), None
    except ValueError:
        return None, "gh-invalid-json (gh printed something that is not JSON)"


def _gh_login(author):
    """(login, is_bot) from a gh author object; login is None when it is not a valid
    GitHub login. A bot keeps its `[bot]` suffix."""
    raw = author.get("login") if isinstance(author, dict) else None
    if not isinstance(raw, str):
        return None, False
    bot = raw.endswith("[bot]") or (isinstance(author, dict) and author.get("is_bot") is True)
    core = raw[:-len("[bot]")] if raw.endswith("[bot]") else raw
    if not GH_LOGIN.match(core):
        return None, bot
    return raw, bot


def _item_tier(rt, project, item):
    for row_id, _, cells in rt.backlog_rows(project.records("backlog.md"), project.prefix,
                                            getattr(project, "legacy_prefixes", None)):
        if row_id == item:
            return rt.tier_of(cells[2] if len(cells) > 2 else "")
    return None


def _is_ancestor(project, older, newer):
    return bool(older and newer) and project.git("merge-base", older, newer).strip() == older


def approvals(rt, project, item, tier=None, run=None):
    """Who approved <item>'s merge: {"item", "tier", "required", "listed", "source",
    "approvers", "ignored", "met", "pr", "head", "branch", "note", "charter"}, or None when the item
    is not in the backlog. source is "github" when the item branch's own PR was read,
    else "charter" (the Approvers names, which never meet the count). Never raises on a
    gh or git failure; the reason goes in note."""
    run = run or subprocess.run
    if tier is None:
        tier = _item_tier(rt, project, item)
        if tier is None:
            return None
    # The rule finish's human gate applies: Tier 1 needs the charter's Tier 1 approvals
    # (2 unless the default branch says 1), Tier 2 under Strict tier rules needs 1, and
    # nothing else needs an approval.
    strict = str(rt.tier_rules(project)).lower() == "strict"
    tier1 = rt.tier1_approvals(project)[0] if hasattr(rt, "tier1_approvals") else 2
    required = tier1 if tier == "1" else (1 if tier == "2" and strict else 0)
    names, _ = rt.approver_names(project)
    registry = rt.people(project)
    charter = []
    for name in names:
        handle = _safe(rt.resolve_person(registry, name) or rt.person_key(name))
        if handle and handle not in charter:
            charter.append(handle)
    result = {"item": item, "tier": tier, "required": required, "listed": len(charter),
              "source": "charter", "approvers": [], "ignored": [], "met": False, "pr": None,
              "head": "", "branch": "", "note": "", "charter": list(charter)}

    if required == 0:
        result.update(met=True, note="no approval required at Tier %s under %s tier rules"
                      % (tier or "?", "Strict" if strict else "Standard"))
        return result

    by_terminal = []

    def fallback(note):
        by_terminal[:] = local_approvals(rt, project, item, charter)
        have = set(a["handle"] for a in by_terminal)
        result.update(source="charter", note=note, approvers=list(by_terminal) + [
            {"handle": h, "login": "", "source": "charter", "commit": "", "at": ""}
            for h in charter if h not in have])
        result["met"] = approval_count(result) >= required
        return result

    branch = item_branch(rt, project, item)
    if not branch or branch.startswith("-"):
        return fallback("no-branch (no local branch names %s)" % item)
    result["branch"] = branch
    local = project.git("rev-parse", "--verify", "--quiet", branch + "^{commit}").strip()
    gh = shutil.which("gh")
    if not gh:
        return fallback("no-gh (gh is not on PATH)")
    repo, note = _gh_json(run, [gh, "repo", "view", "--json", "nameWithOwner"], project.root)
    if note:
        return fallback(note)
    name = repo.get("nameWithOwner") if isinstance(repo, dict) else None
    if not isinstance(name, str) or not GH_REPO.match(name):
        return fallback("gh-invalid-json (no repository name)")
    data, note = _gh_json(run, [gh, "pr", "view", branch, "--repo", name, "--json", PR_FIELDS],
                          project.root)
    if note:
        return fallback(note)
    if not isinstance(data, dict):
        return fallback("gh-invalid-json (the PR is not a JSON object)")
    head = data.get("headRefOid")
    if not isinstance(head, str) or not GH_SHA.match(head):
        return fallback("gh-invalid-json (the PR has no head commit)")
    number = data.get("number")
    result["pr"] = number if isinstance(number, int) and not isinstance(number, bool) else None
    state = data.get("state")
    if data.get("isCrossRepository") is not False:
        return fallback("pr-mismatch (pr is from another repository)")
    if state not in ("OPEN", "MERGED"):
        return fallback("pr-mismatch (pr is %s)" % (state.lower() if isinstance(state, str)
                                                     and state.isalpha() else "not open"))
    if head != local:
        ok = False
        if state == "MERGED":
            commits = rt.item_commits(project, item)
            ok = bool(commits) and _is_ancestor(project, head, rt.trusted_ref(project) or "") \
                and _is_ancestor(project, commits[0][0], head)
        if not ok:
            return fallback("pr-mismatch (pr head differs from local)")
    result["head"] = head

    author, _ = _gh_login(data.get("author"))
    author_key = (author or "").lower()
    # Mapping a login is security-bearing: people.json counts only as the default branch
    # has it. A registry that exists only on this branch maps nobody.
    _, people_source = rt.trusted_text(project, os.path.join(project.docs, rt.PEOPLE_REL))
    mapping_trusted = people_source != "working-tree" or not rt.trusted_ref(project)
    author_handle = rt.handle_for_github(project, author) if author and mapping_trusted else None
    latest = {}
    reviews = data.get("reviews")
    for review in reviews if isinstance(reviews, list) else []:
        if not isinstance(review, dict):
            continue
        rstate = review.get("state")
        if rstate in ("COMMENTED", "PENDING"):
            continue                     # a comment does not change a reviewer's verdict
        login, bot = _gh_login(review.get("author"))
        if login is None:
            result["ignored"].append({"login": "(invalid)", "reason": "invalid-login"})
            continue
        at = review.get("submittedAt")
        at = at if isinstance(at, str) and GH_TIME.match(at) else ""
        commit = review.get("commit")
        oid = commit.get("oid") if isinstance(commit, dict) else None
        key = login.lower()
        if key not in latest or at >= latest[key]["at"]:
            latest[key] = {"login": login, "bot": bot, "state": rstate, "oid": oid, "at": at}
    counted = []
    for key in sorted(latest):
        r = latest[key]
        handle = rt.handle_for_github(project, r["login"]) if mapping_trusted else None
        if r["bot"]:
            reason = "bot"
        elif key == author_key or (handle and handle == author_handle):
            reason = "self-approval"
        elif r["state"] == "CHANGES_REQUESTED":
            reason = "changes-requested"
        elif r["state"] == "DISMISSED":
            reason = "dismissed"
        elif r["state"] != "APPROVED":
            reason = "not-approved"
        elif r["oid"] != head:
            reason = "stale"
        elif not handle:
            reason = "unmapped"
        elif handle not in charter:
            # Ship review finding 18: a review counts only from someone the charter's
            # Approvers row (on the default branch) names, the rule waivers and
            # `approve` follow.
            reason = "not-an-approver"
        elif handle in [c["handle"] for c in counted]:
            reason = "duplicate"
        else:
            reason = None
        if reason:
            result["ignored"].append({"login": r["login"], "reason": reason})
        else:
            counted.append({"handle": _safe(handle), "login": r["login"], "source": "github",
                            "commit": head, "at": r["at"]})
    have = set(c["handle"] for c in counted)
    counted += [a for a in local_approvals(rt, project, item, charter, against=head)
                if a["handle"] not in have]
    result.update(source="github", approvers=counted)
    result["met"] = approval_count(result) >= required
    return result


COUNTED_SOURCES = ("github", "local")


def local_approvals_on(rt, project):
    """True when the charter's **Local approvals** row, on the default branch, is `on`.
    Off by default: a local approval is an unsigned record in the item shard, so only a
    project that accepts that (a one-person project, say) turns it on."""
    text, _ = rt.trusted_text(project, project.charter_path)
    cell = rt.labelled(text or "", "Local approvals") or ""
    return re.sub(r"[`*]", "", rt.UNFILLED.sub("", cell)).strip().lower().startswith("on")


# What an approval survives: the bookkeeping the kit writes after it (item shards, the
# ledger, worklog and backlog renders, release records). The charter, people.json,
# reviews, plans and process documents decide what an approval means, so a change to
# them voids it (ship review NUHT-043 round 2, finding 3).
BOOKKEEPING = ("project/items/", "project/ledger/", "project/evidence-ledger.jsonl",
               "project/worklog/", "project/worklog.md", "project/backlog.md",
               "project/releases/", "project/deploys.jsonl", "project/defects/README.md")


def _records_only_since(rt, project, older, newer):
    """True when <older> is <newer> or an ancestor of it and only bookkeeping changed
    between them."""
    if not older or not newer:
        return False
    if older == newer:
        return True
    if not _is_ancestor(project, older, newer):
        return False
    docs = project.docs.strip("/") + "/"
    changed = project.git("diff", "--name-only", older, newer).split()
    return all(p.startswith(docs) and p[len(docs):].startswith(BOOKKEEPING) for p in changed)


def local_approvals(rt, project, item, charter, against=None):
    """Approvals an approver gave in a terminal (`sdlc.py approve`) that still count: the
    charter turns them on, the approver is in Approvers on the default branch, the approved
    commit contains the item's newest commit, and nothing but records changed between it
    and <against> (the PR head, else the item branch, else HEAD)."""
    if not local_approvals_on(rt, project):
        return []
    try:
        shard = shards.load_item(project, item) or {}
    except Exception:                    # noqa: BLE001 -- an unreadable shard approves nothing
        shard = {}
    commits = rt.item_commits(project, item)
    newest = commits[0][0] if commits else ""
    if against is None:
        branch = item_branch(rt, project, item)
        against = project.git("rev-parse", "--verify", "--quiet",
                              (branch or "HEAD") + "^{commit}").strip()
    out = []
    for row in shard.get("local_approvals") or []:
        handle = _safe(row.get("handle"))
        approved = row.get("commit") or ""
        if not newest or handle not in charter or handle in [a["handle"] for a in out]:
            continue
        if not (approved == newest or _is_ancestor(project, newest, approved)):
            continue
        if not _records_only_since(rt, project, approved, against):
            continue
        out.append({"handle": handle, "login": "", "source": "local", "commit": approved,
                    "at": row.get("at") or ""})
    return out


def approve(rt, project, item, by, interactive=None):
    """Record <by>'s approval of what is checked out (HEAD), which must contain the item's
    newest commit. (lines, exit code)."""
    interactive = _interactive() if interactive is None else interactive
    if not local_approvals_on(rt, project):
        return ["approve: local approvals are off. They are unsigned records anyone who can "
                "write the item shard could forge, so a project turns them on deliberately: "
                "set **Local approvals** to `on` in %s on the default branch. Otherwise "
                "approve the item's pull request on GitHub" % project.charter_path], 1
    shard = shards.load_item(project, item)
    if not shard:
        return ["approve: %s has no item shard under %s/project/items/" % (item, project.docs)], 2
    approvers, source, registry = waiver_approvers(rt, project)
    refused = check_waiver(rt, project, by, approvers, source, registry, interactive,
                           act="approve")
    if refused:
        return ["approve: " + refused], 1
    commits = rt.item_commits(project, item)
    if not commits:
        return ["approve: no commit carries `Work-Item: %s`, so there is nothing to approve "
                "yet" % item], 1
    head = project.git("rev-parse", "--verify", "--quiet", "HEAD^{commit}").strip()
    newest = commits[0][0]
    if not (head == newest or _is_ancestor(project, newest, head)):
        return ["approve: HEAD does not contain %s's newest commit %s; check out the branch "
                "that holds it" % (item, newest[:7])], 1
    handle = _safe(rt.resolve_person(registry, by) or rt.person_key(by))
    raw, _ = runner_identity(project, registry, rt)
    rows = [r for r in shard.get("local_approvals") or []
            if not (r.get("handle") == handle and r.get("commit") == head)]
    rows.append({"handle": handle, "commit": head, "as": _safe(raw) or "unknown",
                 "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    shard["local_approvals"] = rows
    shards.save_item(project, shard)
    res = approvals(rt, project, item)
    lines = ["approved %s at %s by %s (local)" % (item, head[:7], handle)]
    return lines + (approval_lines(res) if res else []), 0


def approval_count(res):
    return len([a for a in res["approvers"] if a["source"] in COUNTED_SOURCES])


def approval_lines(res):
    """The `approval` lines finish and `sdlc.py approvals` print."""
    n, req = approval_count(res), res["required"]
    if not req:
        return ["approval " + res["note"]]
    where = (" on %s" % res["head"][:7]) if res["head"] else ""
    where += (" (PR #%d)" % res["pr"]) if res["pr"] and res["source"] == "github" else ""
    lines = []
    if res["source"] == "github":
        lines.append("approval %d of %d%s: %s" % (n, req, where, ", ".join(
            "%s (%s)" % (a["handle"], a["source"]) for a in res["approvers"])
            or "no approval counts yet"))
    else:
        lines.append("approval %d of %d (charter fallback: %s): charter: %s"
                     % (n, req, res["note"], ", ".join(
                         a["handle"] + (" (local)" if a["source"] == "local" else "")
                         for a in res["approvers"]) or "no Approvers named"))
    if res["ignored"]:
        lines.append("approval ignored: %s" % ", ".join(
            "%s %s" % (i["login"], i["reason"]) for i in res["ignored"]))
    if not res["met"] and res["listed"] < req:
        lines.append("approval %d of %d: this project lists %d approver%s; %s"
                     % (n, req, res["listed"], "" if res["listed"] == 1 else "s", SOLO_HINT))
    return lines


def approval_waiting(res):
    """The Waiting-on text: the charter's Approvers still owed, as plain handles so
    `status` can say "Waiting on you", then who approved already and from where, e.g.
    "bob; approved: alice (github)"."""
    got = ["%s (%s)" % (a["handle"], a["source"]) for a in res["approvers"]
           if a["source"] in COUNTED_SOURCES]
    have = set(a["handle"] for a in res["approvers"] if a["source"] in COUNTED_SOURCES)
    rest = [h for h in (res.get("charter") or []) if h not in have]
    return (", ".join(rest) or "the owner") + ("; approved: " + ", ".join(got) if got else "")


def worklog_entry(project, item):
    """The text of the worklog entry headed by <item> (shard first, then worklog/archive), or ''."""
    shard_text = shards.load_worklog_shard(project, item)
    if shard_text:
        return shard_text
    text = project.worklog_texts() if hasattr(project, "worklog_texts") else project.records("worklog.md")
    for entry in re.split(r"(?m)^(?=## |- [0-9]{4}-[0-9]{2}-[0-9]{2} · )", text):
        if re.match(r"^(?:## |- [0-9-]+ · )(?:[^\n]*[ ,&/])?%s\b" % re.escape(item), entry):
            return entry
    return ""


def insert_worklog(project, block, item=None):
    """Write <block> to worklog/<item>.md when sharded, else above newest entry in worklog.md."""
    if item and shards.is_sharded(project, for_write=True):
        shards.save_worklog_shard(project, item, block)
        return True
    path = project.path(os.path.join(project.docs, "project", "worklog.md"))
    try:
        with open(path, encoding="utf-8") as handle:
            rows = handle.read().split("\n")
    except (IOError, OSError):
        return False
    marker = next((i for i, row in enumerate(rows) if "New entries go here" in row), None)
    at = marker + 1 if marker is not None else next(
        (i for i, row in enumerate(rows) if ENTRY_START.match(row)), len(rows))
    rows[at:at] = [""] + block.rstrip("\n").split("\n") + ([""] if at < len(rows) else [])
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rows))
    return True


def changed_files(rt, project, commits):
    files, records = [], project.docs + "/project/"
    for sha, _, _ in commits:
        for path in project.git("show", "--name-only", "--format=", sha).splitlines():
            if path.strip() and path not in files and not rt.KIT_PATH.match(path) \
                    and not rt.NOISE_PATH.search(path) and not path.startswith(records):
                files.append(path)
    return files


def _has_notes(notes):
    return bool(notes and any(str(v or "").strip() for v in notes.values()))


def _replace_worklog_todos(project, item, notes):
    """Fill remaining TODO(finish) sections in an already-drafted worklog entry using <notes>."""
    if not _has_notes(notes):
        return False
    shard_text = shards.load_worklog_shard(project, item)
    entry = shard_text or worklog_entry(project, item)
    if not entry or TODO not in entry:
        return False
    updated = entry
    section_map = (
        ("Why", notes.get("why")),
        ("Not done", notes.get("not_done") or ("nothing deferred" if notes.get("why") else None)),
        ("Discovered", notes.get("discovered") or ("nothing" if notes.get("why") else None)),
        ("Decisions", notes.get("decisions") or ("none" if notes.get("why") else None)),
        ("Assumptions used", notes.get("assumptions") or ("none" if notes.get("why") else None)),
        ("Plan", notes.get("plan") or (notes.get("why") if notes.get("why") else None)),
        ("Reviews", notes.get("reviews") or ("self-reviewed" if notes.get("why") else None)),
    )
    for heading, val in section_map:
        if val and str(val).strip():
            pat = re.compile(
                r"(^###\s+" + re.escape(heading) + r"\s*\n+)" + re.escape(TODO) + r":[^\n]*",
                re.MULTILINE,
            )
            updated = pat.sub(lambda m: m.group(1) + str(val).strip(), updated, count=1)
    if updated == entry:
        return False
    if shard_text:
        shards.save_worklog_shard(project, item, updated)
        return True
    path = project.path(os.path.join(project.docs, "project", "worklog.md"))
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (IOError, OSError):
        return False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(entry, updated, 1))
    return True


def draft_entry(rt, project, item, title, tier, effort, status, commits, run, waived, today, notes=None,
                approved=None):
    """The worklog entry for <item>: what git and the ledger know, filled; what only the
    agent knows, filled from <notes> when provided or marked TODO(finish) otherwise."""
    notes = notes or {}
    single_shot = _has_notes(notes)
    files = changed_files(rt, project, commits)
    shas = [sha for sha, _, _ in commits]
    if waived:
        w = waived[-1]
        verified = "not run (waived by %s: %s)" % (w["waived_by"], w.get("reason", ""))
    elif run[1]:
        verified = "%s: %s %s" % (run[1], run[0], ",".join(r.get("stage", "") for r in run[2]))
    else:
        verified = "not run"
    compact = tier == "3" or (tier == "2" and effort == "Lean")
    if compact:
        shown = ", ".join(files[:3]) + (" (+%d)" % (len(files) - 3) if len(files) > 3 else "")
        return ("- %s · %s · %s · effort: %s · changed: %s · verified: %s · commits: %s"
                % (today, item, title, effort, shown or "none", verified,
                   " ".join(s[:7] for s in reversed(shas)))), False
    subjects = project.git("log", "--no-walk", "--format=- %s (%h)", *reversed(shas)).strip()
    branch = project.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    plan = [r for r in os.listdir(project.path(os.path.join(project.docs, "project", "plans")))
            if r.startswith(item)] if os.path.isdir(project.path(os.path.join(
                project.docs, "project", "plans"))) else []
    reviews = [r["file"] for r in rt.review_records(project, item)]
    if waived:
        verify_lines = "- **Not run** — %s" % verified[len("not run "):].strip("()")
    elif run[1]:
        verify_lines = "\n".join("- `checks.%s` — %s — run %s, commit %s"
                                 % (r.get("stage"), r.get("result"), run[1],
                                    (r.get("commit") or "")[:7]) for r in run[2])
    else:
        verify_lines = "- **Not run** — no verify run on record (Tier 3)"
    todo = "%s: " % TODO
    why_val = (notes.get("why") or "").strip()
    why_line = why_val if why_val else (todo + "the reasoning, and any approach you rejected.")
    not_done_line = (notes.get("not_done") or "").strip() or (
        "nothing deferred" if single_shot and why_val else (
            todo + "deferred or stubbed work with follow-up IDs, or \"nothing deferred\"."
        )
    )
    discovered_line = (notes.get("discovered") or "").strip() or (
        "nothing" if single_shot and why_val else (
            todo + "bugs found, stale docs, refuted assumptions, or \"nothing\"."
        )
    )
    decisions_line = (notes.get("decisions") or "").strip() or (
        "none" if single_shot and why_val else (
            todo + "durable decisions and their ADR, or \"none\"."
        )
    )
    assumptions_line = (notes.get("assumptions") or "").strip() or (
        "none" if single_shot and why_val else (
            todo + "the assumptions this relied on, or \"none\"."
        )
    )
    if plan:
        plan_line = "[%s](plans/%s)" % (plan[0], plan[0])
    elif (notes.get("plan") or "").strip():
        plan_line = notes["plan"].strip()
    elif single_shot and why_val and tier != "1":
        plan_line = why_val
    else:
        plan_line = todo + "the approach and the alternatives rejected (Tier 2: the plan lives here)."
    if reviews:
        reviews_line = "\n".join("- [%s](reviews/%s)" % (r, r) for r in reviews)
    elif (notes.get("reviews") or "").strip():
        reviews_line = notes["reviews"].strip()
    elif single_shot and why_val and tier != "1":
        reviews_line = "self-reviewed"
    else:
        reviews_line = todo + "each role engaged and its verdict."
    text_block = "\n".join([
        "## %s — %s" % (item, title), "",
        "**Date:** %s **Tier:** %s **Effort:** %s" % (today, tier or "?", effort),
        "**Status:** %s" % status,
    ] + (["**Approved:** %s" % approved] if approved else []) + [
        "**Branch/commits:** `%s` / `%s..%s`" % (branch, shas[-1][:7], shas[0][:7]), "",
        "### What changed", "", subjects, "",
        "Files: " + (", ".join("`%s`" % f for f in files[:12]) +
                     (" (+%d more)" % (len(files) - 12) if len(files) > 12 else "") or "none"), "",
        "### Why", "", why_line, "",
        "### Verified", "", verify_lines, "",
        "### Not done", "", not_done_line, "",
        "### Discovered", "", discovered_line, "",
        "### Decisions", "", decisions_line, "",
        "### Assumptions used", "", assumptions_line, "",
        "### Plan", "", plan_line, "",
        "### Reviews", "", reviews_line, "",
    ])
    return text_block, (TODO in text_block)


def finish(rt, project, item, waive_by=None, reason=None, dry_run=False, today=None, notes=None):
    """Close <item>: check what its tier owes, draft what is missing, then set Done (Tier 1,
    or Tier 2 under Strict tier rules: Parked for human approval). Returns (lines, exit code):
    0 finished, 1 something is owed first, 2 the item cannot be found."""
    today = today or datetime.date.today().isoformat()
    backlog_text = project.records("backlog.md")
    found = {}
    for row_id, status, cells in rt.backlog_rows(backlog_text, project.prefix,
                                                 getattr(project, "legacy_prefixes", None)):
        found.setdefault(row_id, (status, cells))
    if item not in found:
        return ["%s is not in the backlog" % item], 2
    status, cells = found[item]
    title = plain(cells[1]) if len(cells) > 1 else item
    tier = rt.tier_of(cells[2] if len(cells) > 2 else "")
    column = rt.status_column(status)
    if column == "Dropped":
        return ["%s is Dropped; nothing to finish" % item], 1
    already = column in ("Done", "Parked")
    t_rules = rt.tier_rules(project)
    owed = rt.required_steps(tier, t_rules, True, True)
    effort = resolve_effort(rt, project, item, cells)
    commits = rt.item_commits(project, item)
    out, owing = ["%s · Tier %s · %s" % (item, tier or "?", status)], []

    def owe(line):
        owing.append(line)
        out.append("OWED " + line)
    if not commits:
        return out + ["build    no commit carries a `Work-Item: %s` trailer yet: commit the "
                      "work with one (`%s trailers %s` prints it), then run finish again"
                      % (item, SDLC, item)], 1
    out.append("build    %d commit(s)" % len(commits))
    if project.git("status", "--porcelain", "--untracked-files=no").strip():
        out.append("note     uncommitted changes are not part of what finish records")
    try:
        sync = rt.runtime_module("sync").state(project, rt.default_branch(project))
    except EXPECTED_HELPER_ERRORS:
        sync = None                      # finish never fails on a git oddity it only reports
    except Exception as exc:             # noqa: BLE001 -- reported, not swallowed
        report_unexpected("reading the git sync state", exc)
        sync = None
    if sync and (sync["operation"] or sync["conflicted"]):
        owe("sync     a %s is unfinished%s: resolve it (05-change-control.md, \"Conflicts\") "
            "or `git %s --abort`, then verify again"
            % (sync["operation"] or "merge",
               " (%d file(s) in conflict)" % len(sync["conflicted"]) if sync["conflicted"] else "",
               sync["operation"] or "merge"))
    elif sync and sync["behind_default"] and sync["branch"] != sync["default"] and not already:
        out.append("sync     note: %d commit(s) behind %s as of the last fetch. Bring them in and "
                   "verify again before this merges (`%s sync --fetch`)"
                   % (sync["behind_default"], sync["default_ref"], SDLC))

    run = verify_state(rt, project, item, commits)
    approvers, source, registry = waiver_approvers(rt, project)
    waived, dropped = waivers(rt, project, item, set(h for _, h in approvers if h), registry)
    if owed["Verify"] and run[0] != "pass":
        for line in dropped:
            out.append("verify   note: " + line)
    if not owed["Verify"]:
        out.append("verify   not owed at Tier 3")
    elif run[0] == "pass":
        out.append("verify   pass (run %s)" % run[1])
    elif run[0] == "fail":
        owe("verify   the latest run (%s) failed: fix it, then `%s verify --item %s`"
                     % (run[1], SDLC, item))
    elif waived and not waive_by:
        refused = stored_waiver_refusal(rt, project, waived[-1], approvers, source, registry,
                                        _interactive())
        if refused:
            owe("verify   " + refused)
            waived = []
        else:
            out.append("verify   Not run, waived by %s: %s" % (waived[-1]["waived_by"],
                                                             waived[-1].get("reason", "")))
    elif waive_by:
        refused = None if tier == "1" or not (reason or "").strip() else check_waiver(
            rt, project, waive_by, approvers, source, registry, _interactive())
        if tier == "1":
            owe("verify   a Tier 1 item cannot be waived: run `%s verify --item %s`"
                         % (SDLC, item))
        elif not (reason or "").strip():
            owe("verify   a waiver needs --reason saying why the checks cannot run")
        elif refused:
            owe("verify   " + refused)
        else:
            raw, runner = runner_identity(project, registry, rt)
            row = {"time": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"), "item": item, "stage": "all",
                "commit": commits[0][0], "result": "Not run (waived)",
                "waived_by": waive_by, "waived_as": runner or raw or "unknown",
                "reason": reason.strip()}
            if not dry_run:
                rt.ledger_append(project, [row])
            waived = [row]
            out.append("verify   Not run, waived by %s: %s (recorded in the ledger; never "
                       "counts as Verified)" % (waive_by, reason.strip()))
    elif run[0] in ("partial", "stale") and already:
        out.append("verify   %s (already %s, so not blocking)" % (run[3], column))
    elif run[0] in ("partial", "stale"):
        owe("verify   " + run[3])
    elif already:
        out.append("verify   no verify run on record (already %s, so not blocking)" % column)
    else:
        owe("verify   no verify run covers %s: run `%s verify --item %s`. When the "
                     "checks cannot run here, an approver from the charter's Approvers row "
                     "runs `%s finish %s --waive verify --by <their name> --reason \"...\"` "
                     "(not at Tier 1)" % (item, SDLC, item, SDLC, item))

    result, error = rt.plan_check(project, item)
    if result:
        out.append("plan     %d changed file(s), %d unplanned, %d planned path(s) untouched%s"
                   % (len(result["changed"]), len(result["unplanned"]), len(result["untouched"]),
                      (": " + ", ".join(result["unplanned"][:5])) if result["unplanned"] else ""))
    elif tier == "1":
        out.append("plan     %s" % error)

    reviews = rt.review_records(project, item)
    policy = rt.independent_review_policy(project.charter, project.profile)[1]
    independent = [r for r in reviews
                   if re.match(r"(?i)independent\b", r["fields"].get("Independence", ""))]
    current = shards.merged_items(project).get(item) or {}
    hotfix = shards.is_hotfix(current)
    retro = rt.retro_reviews(project, item) if hotfix else []
    if hotfix and retro:
        out.append("review   hotfix: retroactive review %s" % ", ".join(r["file"] for r in retro))
    elif hotfix:
        # The fast path: no pre-merge review is owed, and the retroactive one is recorded.
        window = rt.retro_review_window(project.charter)
        try:
            due = (datetime.datetime.strptime(str(current.get("hotfix_at") or today)[:10],
                                              "%Y-%m-%d").date()
                   + datetime.timedelta(days=window)).isoformat()
        except ValueError:
            due = "%d day(s) after the hotfix" % window
        out.append("review   hotfix: the pre-merge review is skipped; retroactive review owed "
                   "by %s: `%s review %s --role <role> --by <harness> --stage retro` (doctor "
                   "fails it after that)" % (due, SDLC, item))
    elif tier in policy and not independent and not already:
        owe("review   the charter wants an independent review at Tier %s: `%s review "
                     "%s --role <role> --by <a harness other than the author's>`"
                     % (tier, SDLC, item))
    elif owed["Ship review"] and not [r for r in reviews if "design" not in r["file"]] \
            and not already:
        owe("review   Tier 1 needs a ship review: /sdlc-review %s, or `%s review %s "
                     "--role <role> --by <harness>`" % (item, SDLC, item))
    elif reviews:
        out.append("review   %s" % ", ".join(r["file"] for r in reviews))

    escalations = [] if already else rt.open_escalations(project, item)
    for name, n in escalations:
        owe("review   finding %s in %s/project/reviews/%s is escalated and has no decision: "
            "a person decides it and writes their name in its Responses row"
            % (n, project.docs, name))

    needs_human_gate = (tier == "1") or (tier == "2" and str(t_rules).lower() == "strict")
    approval = None
    if needs_human_gate and column != "Done":
        approval = approvals(rt, project, item, tier=tier)
        out.extend(approval_lines(approval))
    final = "Done" if approval and approval["met"] else ("Parked" if needs_human_gate else "Done")
    entry = worklog_entry(project, item)
    if entry and TODO in entry and _has_notes(notes) and not dry_run:
        if _replace_worklog_todos(project, item, notes):
            entry = worklog_entry(project, item)
    logged = bool(entry)
    if entry and TODO in entry:
        owe("log      the worklog entry still has %s parts: write them, then run "
                     "finish again" % TODO)
    elif logged:
        out.append("log      worklog entry present")
    elif owed["Log"] and owing:
        out.append("log      drafted once the items above are done")
    elif owed["Log"]:
        block, needs_agent = draft_entry(rt, project, item, title, tier, effort,
                                         status if already else final, commits, run, waived,
                                         today, notes=notes,
                                         approved=approval_waiting(approval) if approval else None)
        if not dry_run:
            insert_worklog(project, block, item=item)
        if needs_agent:
            owe("log      %s a worklog entry from git and the ledger: replace each "
                         "%s line (Why, Not done, Discovered...), then run finish again"
                         % ("would draft" if dry_run else "drafted", TODO))
        else:
            out.append("log      %s worklog entry" % ("would write" if dry_run else "wrote"))
    else:
        out.append("log      not owed (Tier 3: the commit is the record)")

    lifecycle = getattr(rt, "extension_lifecycle", None)
    for ext_id, message in (lifecycle(project, "before_finish", project.root, item)
                            if lifecycle else []):
        owe("ext      %s before_finish: %s" % (ext_id, message))

    if owing:
        if escalations and not dry_run:
            _notify(rt, project, out, "review-blocked", item, title, tier, status)
        return out + ["", "not finished: %d thing(s) owed (OWED above)" % len(owing)], 1
    if already and column == "Parked" and approval and approval["met"] \
            and not (run[0] == "pass" or (waived and tier != "1")):
        out.append("approval note: approved, but no passing verify run covers the newest "
                   "commit, so it stays Parked: `%s verify --item %s`" % (SDLC, item))
        return out + ["status   already %s" % status], 0
    if already and not (column == "Parked" and approval and approval["met"]):
        return out + ["status   already %s" % status], 0
    parked = final == "Parked"
    if parked and approval:
        extra = [approval_waiting(approval), "merge approval (Tier %s): %d of %d%s"
                 % (tier, approval_count(approval), approval["required"],
                    (" on %s" % approval["head"][:7]) if approval["head"] else
                    " (charter fallback)"), today]
    elif parked:
        approvers = plain(rt.labelled(project.charter, "Approvers") or "") or "the owner"
        extra = [approvers, "merge approval (Tier %s)" % tier, today]
    else:
        extra = [today]
    if not dry_run:
        if shards.is_sharded(project, for_write=True):
            sh = shards.load_item(project, item) or shards.merged_items(project).get(item) or {
                "id": item,
                "title": title,
                "tier": tier or "2",
                "owner": plain(cells[3]) if len(cells) > 3 else "software-engineer",
                "depends": cells[4] if len(cells) > 4 else "",
                "created": today,
            }
            sh["status"] = final
            sh["updated"] = today
            if hotfix:
                sh["retro_review"] = "done" if retro else "owed"
            if approval:
                sh["approvers"] = approval["approvers"]
            if parked:
                sh["waiting_on"] = extra[0]
                sh["park_reason"] = extra[1]
            else:
                sh["completed"] = today
                sh["waiting_on"] = ""
                sh["park_reason"] = ""
            shards.save_item(project, sh, today=today)
        else:
            move_row(project, item, final, extra)
        unlocked = release_item_test_locks(
            rt, project, item, commits,
            verify_ok=(run[0] == "pass"),
            bite_ok=bite_state(rt, project, item, commits),
        )
        if unlocked:
            out.append("locks    unlocked reproducing test(s): %s" % ", ".join(unlocked))
        try:
            rt.runtime_module("claims").release(project, item)
        except EXPECTED_HELPER_ERRORS:
            pass                         # no registry or an unreadable claim: nothing to release
        except Exception as exc:         # noqa: BLE001 -- reported, not swallowed
            report_unexpected("releasing the claim on %s" % item, exc)
    out.append("status   %s %s%s" % ("would set" if dry_run else "set", final,
                                     " (waiting on %s for the merge approval)" % extra[0]
                                     if parked else ""))
    if parked and not dry_run:
        _notify(rt, project, out, "approval-needed", item, title, tier, final)
    return out, 0


def _notify(rt, project, out, event, item, title, tier, status):
    """Send a webhook event (NUHT-034) and note a sent one; failures only warn."""
    send = getattr(rt, "notify_event", None)
    if send is None:
        return
    state, message = send(project, event, item, title, tier, status)
    if state == "sent":
        out.append("notify   " + message)


# ---------------------------------------------------------------- guard

def guard_on(rt, project):
    picked, state = rt.choice(rt.labelled(project.charter, "Finish guard") or "", ("on", "off"))
    return not (state == "decided" and picked == "off")


def session_path(project, payload):
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or ""))[:80] or "default"
    folder = project.path(os.path.join(".ai-sdlc", "session"))
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write("*\n")
    return os.path.join(folder, sid + ".json")


def guard(rt, project, event, payload):
    """Claude Code SessionStart / Stop hook. start notes HEAD; stop finds work items this
    session committed that are Tier 1 or 2 and not yet Done or Parked, and asks the agent,
    once per item, to finish them or say why not. Never runs doctor: it must stay fast.
    Returns (exit code, message for stderr)."""
    if not guard_on(rt, project) or not project.prefix:
        return 0, ""
    path = session_path(project, payload)
    state = {}
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (IOError, OSError, ValueError):
        pass
    if event == "start":
        if not state.get("head"):
            state = {"head": project.git("rev-parse", "HEAD").strip(), "nudged": []}
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(state, handle)
        return 0, open_defects_note(rt, project)
    if payload.get("stop_hook_active") or not state.get("head"):
        return 0, ""
    messages = project.git("log", "--format=%B%x00", "%s..HEAD" % state["head"])
    touched = set()
    for message in messages.split("\x00"):
        trailer = re.search(r"^Work-Item:\s*(\S+)", message, re.M)
        touched |= set([trailer.group(1)]) if trailer else rt.ids_in(message, project.prefix)
    rows = dict((row_id, (status, cells)) for row_id, status, cells in rt.backlog_rows(
        project.records("backlog.md"), project.prefix, getattr(project, "legacy_prefixes", None)))
    pending = []
    for item in sorted(touched - set(state.get("nudged", [])), key=rt.id_sort_key):
        if item not in rows:
            continue
        status, cells = rows[item]
        tier = rt.tier_of(cells[2] if len(cells) > 2 else "")
        if tier == "3" or rt.status_column(status) in ("Done", "Parked", "Dropped"):
            continue
        pending.append("%s (Tier %s, %s)" % (item, tier or "?", status))
    if not pending:
        return 0, ""
    state["nudged"] = sorted(set(state.get("nudged", [])) | set(p.split(" ")[0] for p in pending))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    return 2, ("This session committed work on %s, still open in the backlog. If it is "
               "finished, run `%s finish <ID>`; it checks the evidence, drafts the worklog "
               "entry and sets the status. If work continues, say what is left and stop. "
               "(Reminded once per item; turn off with the charter's Finish guard row.)"
               % ("; ".join(pending), SDLC))


def open_defects_note(rt, project):
    """The session-start note on open S0 to S2 defects (NUHT-040), or "". Printed on stdout,
    which Claude Code adds to the session's context. Never raises: a start hook must not
    break a session."""
    try:
        shards_mod = rt.runtime_module("shards")
        lines = shards_mod.defect_summary_lines(shards_mod.merged_items(project))
    except Exception:  # noqa: BLE001 -- a broken record must not stop the session
        return ""
    if not lines:
        return ""
    return ("Open defects in this project (S0 stop work, S1 release blocker, S2 blocker unless "
            "waived). Do not ship over them; if your change touches one, say so:\n  "
            + "\n  ".join(lines))


# ---------------------------------------------------------------- record repairs

def rotate_worklog(rt, project, apply=False, today=None):
    """Move the oldest entries past half the rotation limit into worklog-archive/."""
    today = today or datetime.date.today()
    rel = os.path.join(project.docs, "project", "worklog.md")
    lines = project.records("worklog.md").split("\n")
    limit = rt.WORKLOG_ROTATE_LINES
    if len(lines) <= limit:
        return ["worklog.md is %d lines (limit %d): nothing to rotate" % (len(lines), limit)]
    starts = [n for n, line in enumerate(lines) if ENTRY_START.match(line)]
    cut = next((n for n in starts if n - (starts[0] if starts else 0) >= limit // 2), None)
    if cut is None:
        return ["worklog.md has no entry boundary past line %d to cut at" % (limit // 2)]
    folder = os.path.join(project.docs, "project", "worklog-archive")
    part = 1
    while os.path.exists(project.path(os.path.join(folder, "%d-part%d.md" % (today.year, part)))):
        part += 1
    target = os.path.join(folder, "%d-part%d.md" % (today.year, part))
    moved = sum(1 for n in starts if n >= cut)
    report = ["%s %d entr%s (%d lines) from %s to %s; the newest %d stay"
              % ("moved" if apply else "would move", moved, "y" if moved == 1 else "ies",
                 len(lines) - cut, rel, target, len(starts) - moved)]
    if apply:
        os.makedirs(project.path(folder), exist_ok=True)
        with open(project.path(target), "w", encoding="utf-8") as handle:
            handle.write("# Worklog archive — moved from worklog.md on %s\n\nNewest first, "
                         "like the worklog.\n\n%s\n" % (today.isoformat(),
                                                        "\n".join(lines[cut:]).strip("\n")))
        with open(project.path(rel), "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines[:cut]).rstrip("\n") + "\n")
    return report


def normalise_status(rt, project, apply=False):
    """Rewrite statuses the board already reads as a kit status ("Completed", "Done
    (merged 8acbc4a)") to that status, keeping any note in the Task cell."""
    view = rt.runtime_module("view")
    path, lines = backlog_lines(project)
    if lines is None:
        return ["no backlog"]
    report, header = [], None
    for n, line in enumerate(lines):
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if header is None:
            header = cells
            continue
        if "Status" not in header or re.match(r"^:?-+:?$", cells[0]):
            continue
        pos = header.index("Status")
        if pos >= len(cells) or not cells[pos] or cells[pos] in KIT_STATUSES:
            continue
        column = view.column_of(cells[pos])
        if column not in CANONICAL:
            continue
        canon = CANONICAL[column]
        text = view.plain(cells[pos])
        rest = text[len(canon):] if text.lower().startswith(canon.lower()) else \
            re.sub(r"^[^(\[—–:]*", "", text)
        note = rest.strip(" -:—–()[]")
        report.append("%s: %r -> %r%s" % (cells[0], cells[pos], canon,
                                          " (note kept in Task: %s)" % note if note else ""))
        cells[pos] = canon
        if note and "Task" in header:
            cells[header.index("Task")] += " (%s)" % note
        lines[n] = _row(cells)
    if apply and report:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    return report or ["every status is already a kit status"]


def link_evidence(rt, project, apply=False):
    """Add ledger rows for verify runs that sit in .ai-sdlc/evidence/ but never reached
    the ledger (runs from before it existed). Only real runs: nothing is invented."""
    seen = set(r.get("run") for r in rt.ledger(project))
    rows = []
    for name, summary in rt.evidence_runs(project):
        if name in seen:
            continue
        for e in summary.get("stages", []):
            if "exit_code" in e:
                rows.append({"time": summary.get("generated", ""), "commit": summary.get("git_head", ""),
                             "dirty": bool(summary.get("dirty")), "stage": e.get("stage"),
                             "command": e.get("command", ""), "exit_code": e.get("exit_code"),
                             "result": e.get("result", ""), "output_sha256": e.get("log_sha256", ""),
                             "run": name, "item": summary.get("item", "")})
    if apply and rows:
        rt.ledger_append(project, rows)
    runs = sorted(set(r["run"] for r in rows))
    if not runs:
        return ["every verify run on disk is already in the ledger"]
    return ["%s %d row(s) from %d run(s) not in the ledger: %s"
            % ("added" if apply else "would add", len(rows), len(runs), ", ".join(runs[:5]) +
               (" ..." if len(runs) > 5 else ""))]


def migrate_shards(rt, project, apply=False):
    return shards.migrate_shards(rt, project, apply=apply)

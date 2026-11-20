"""Finishing a work item in one command, the session guard that reminds an agent to, and
the record repairs `sdlc.py fix` previews. Imported by sdlc.py, which passes itself in as
`rt`; nothing here runs on import."""

import datetime
import fnmatch
import json
import os
import re

import shards

SDLC = "python3 .ai-sdlc/bin/sdlc.py"
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

def verify_state(rt, project, item, commits):
    """('pass' | 'fail' | 'none', run name, its rows): the latest verify run behind the item."""
    all_rows = rt.evidence_matches(project, item, None, commits)
    rows = [r for r in all_rows if r.get("stage") != "bite"]
    if not rows:
        return "none", "", []
    last = rows[-1].get("run") or ""
    run = [r for r in rows if (r.get("run") or "") == last] if last else rows[-1:]
    failed = [r for r in run if "fail" in str(r.get("result", ""))]
    return ("fail" if failed else "pass"), last, run


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


def waivers(rt, project, item):
    return [r for r in rt.ledger(project) if r.get("waived_by") and r.get("item") == item]


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


def draft_entry(rt, project, item, title, tier, effort, status, commits, run, waived, today, notes=None):
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
        return out + ["build    no commit names %s yet: commit the work with the ID in the "
                      "message, then run finish again" % item], 1
    out.append("build    %d commit(s)" % len(commits))
    if project.git("status", "--porcelain", "--untracked-files=no").strip():
        out.append("note     uncommitted changes are not part of what finish records")
    try:
        sync = rt.runtime_module("sync").state(project, rt.default_branch(project))
    except Exception:
        sync = None                      # finish never fails on a git oddity it only reports
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
    waived = waivers(rt, project, item)
    if not owed["Verify"]:
        out.append("verify   not owed at Tier 3")
    elif run[0] == "pass":
        out.append("verify   pass (run %s)" % run[1])
    elif run[0] == "fail":
        owe("verify   the latest run (%s) failed: fix it, then `%s verify --item %s`"
                     % (run[1], SDLC, item))
    elif waived:
        out.append("verify   Not run, waived by %s: %s" % (waived[-1]["waived_by"],
                                                         waived[-1].get("reason", "")))
    elif waive_by:
        if tier == "1":
            owe("verify   a Tier 1 item cannot be waived: run `%s verify --item %s`"
                         % (SDLC, item))
        elif not (reason or "").strip():
            owe("verify   a waiver needs --reason saying why the checks cannot run")
        else:
            row = {"time": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"), "item": item, "stage": "all",
                "commit": commits[0][0], "result": "Not run (waived)",
                "waived_by": waive_by, "reason": reason.strip()}
            if not dry_run:
                rt.ledger_append(project, [row])
            waived = [row]
            out.append("verify   Not run, waived by %s: %s (recorded in the ledger; never "
                       "counts as Verified)" % (waive_by, reason.strip()))
    elif already:
        out.append("verify   no verify run on record (already %s, so not blocking)" % column)
    else:
        owe("verify   no verify run covers %s: run `%s verify --item %s`. When the "
                     "checks cannot run here: `%s finish %s --waive verify --by <name> "
                     "--reason \"...\"` (not at Tier 1)" % (item, SDLC, item, SDLC, item))

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
    if tier in policy and not independent and not already:
        owe("review   the charter wants an independent review at Tier %s: `%s review "
                     "%s --role <role> --by <a harness other than the author's>`"
                     % (tier, SDLC, item))
    elif owed["Ship review"] and not [r for r in reviews if "design" not in r["file"]] \
            and not already:
        owe("review   Tier 1 needs a ship review: /sdlc-review %s, or `%s review %s "
                     "--role <role> --by <harness>`" % (item, SDLC, item))
    elif reviews:
        out.append("review   %s" % ", ".join(r["file"] for r in reviews))

    for name, n in rt.open_escalations(project, item):
        owe("review   finding %s in %s/project/reviews/%s is escalated and has no decision: "
            "a person decides it and writes their name in its Responses row"
            % (n, project.docs, name))

    needs_human_gate = (tier == "1") or (tier == "2" and str(t_rules).lower() == "strict")
    final = "Parked" if needs_human_gate else "Done"
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
                                         today, notes=notes)
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

    if owing:
        return out + ["", "not finished: %d thing(s) owed (OWED above)" % len(owing)], 1
    if already:
        return out + ["status   already %s" % status], 0
    if needs_human_gate:
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
            if needs_human_gate:
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
        except Exception:
            pass
    out.append("status   %s %s%s" % ("would set" if dry_run else "set", final,
                                     " (waiting on %s for the merge approval)" % extra[0]
                                     if needs_human_gate else ""))
    return out, 0


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
        return 0, ""
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

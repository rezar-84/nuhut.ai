"""Hybrid sharded project store for zero-conflict multi-worker execution.

Canonical v5 shard layout under <docs_dir>/project/:
  items/<ID>.json       -- per-item metadata, status, dependencies, and touch globs
  worklog/<ID>.md       -- per-item worklog entry written by <ID>'s branch
  ledger/<run-id>.jsonl -- immutable per-run verification, bite, audit, or waiver rows

Compatibility contract:
  - Reading merges shards with legacy 4.x files (backlog.md, worklog.md,
    evidence-ledger.jsonl); shards win on duplicate item IDs.
  - Writing targets shards whenever any shard directory exists OR when running inside a
    linked git worktree (.git is a file), so parallel worktrees never touch shared files.
  - `sdlc.py render` materializes deterministic human-readable backlog.md and worklog.md
    views from shards + legacy entries; `sdlc.py render --check` verifies sync.
  - `sdlc.py fix migrate-shards` migrates 4.x repositories cleanly into shards.

Standard library only. Never put two opening curly braces in a row in this file:
install.py runs placeholder substitution across runtime files.
"""

import datetime
import hashlib
import json
import os
import re
import tempfile

KIT_STATUSES = (
    "In progress",
    "In review",
    "Ready",
    "Blocked",
    "Parked",
    "Deferred",
    "Done",
    "Dropped",
)

STATUS_ALIASES = {
    "in progress": "In progress",
    "in-progress": "In progress",
    "now": "In progress",
    "active": "In progress",
    "wip": "In progress",
    "in review": "In review",
    "in-review": "In review",
    "review": "In review",
    "ready": "Ready",
    "next": "Ready",
    "todo": "Ready",
    "queued": "Ready",
    "blocked": "Blocked",
    "parked": "Parked",
    "deferred": "Deferred",
    "later": "Deferred",
    "done": "Done",
    "completed": "Done",
    "complete": "Done",
    "shipped": "Done",
    "dropped": "Dropped",
    "cancelled": "Dropped",
    "canceled": "Dropped",
}

ITEM_TYPES = ("feat", "fix", "defect", "chore", "docs", "refactor", "test")
EFFORT_MODES = ("", "Lean", "Normal", "Beast")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*-[0-9]+$")
INLINE_TOUCH_RE = re.compile(r"(?:^|\b)touch\s*:\s*([^|;\n]+)", re.I)
INLINE_EFFORT_RE = re.compile(r"(?:^|\beffort\s*:\s*)(Lean|Normal|Beast)\b", re.I)
ENTRY_HEAD_RE = re.compile(
    r"^(?:##\s+([A-Za-z0-9#][A-Za-z0-9_#.–-]*)(?:\s+\([^)]*\))?\s+[—-]|-\s+\d{4}-\d{2}-\d{2}\s+·\s+([A-Za-z0-9#][A-Za-z0-9_#.–-]*)\s+·)"
)


def _id_sort_key(item_id):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"([0-9]+)", item_id or "")]


def _plain(cell):
    cell = re.sub(r"_\([^)]*\)_", "", cell or "")
    return re.sub(r"\*\*|__|`|~~", "", cell).strip()


def normalize_status(value):
    raw = _plain(str(value or "")).strip()
    if not raw:
        return "Ready"
    if raw in KIT_STATUSES:
        return raw
    low = raw.lower()
    if low in STATUS_ALIASES:
        return STATUS_ALIASES[low]
    for prefix, canon in (
        ("done", "Done"),
        ("completed", "Done"),
        ("in progress", "In progress"),
        ("in review", "In review"),
        ("ready", "Ready"),
        ("blocked", "Blocked"),
        ("parked", "Parked"),
        ("deferred", "Deferred"),
        ("dropped", "Dropped"),
    ):
        if low.startswith(prefix):
            return canon
    return raw


def section_for_status(status):
    canon = normalize_status(status)
    if canon in ("In progress", "In review"):
        return "Now"
    if canon == "Ready":
        return "Next"
    if canon == "Blocked":
        return "Blocked"
    if canon == "Parked":
        return "Parked"
    if canon == "Deferred":
        return "Later"
    if canon == "Done":
        return "Done"
    if canon == "Dropped":
        return "Dropped"
    return "Next"


def project_dir(project):
    return project.path(os.path.join(project.docs, "project"))


def items_dir(project):
    return os.path.join(project_dir(project), "items")


def worklog_dir(project):
    return os.path.join(project_dir(project), "worklog")


def ledger_dir(project):
    return os.path.join(project_dir(project), "ledger")


def is_linked_worktree(project):
    """True when <project.root>/.git is a gitdir pointer file rather than the main .git dir."""
    git_marker = project.path(".git")
    return os.path.isfile(git_marker)


def has_shards(project):
    for d in (items_dir(project), worklog_dir(project), ledger_dir(project)):
        if os.path.isdir(d):
            return True
    return False


def is_sharded(project, for_write=False):
    if has_shards(project):
        return True
    if for_write and is_linked_worktree(project):
        return True
    return False


def validate_item_id(item_id, prefix="", legacy_prefixes=None):
    raw = str(item_id or "").strip()
    if not raw or "/" in raw or "\\" in raw or ".." in raw:
        return False, "invalid work item ID %r" % item_id
    if not SAFE_ID_RE.match(raw):
        return False, "work item ID %r must look like PREFIX-001" % raw
    if prefix:
        allowed = set([prefix]) | set(legacy_prefixes or ())
        item_prefix = raw.split("-", 1)[0]
        if item_prefix not in allowed:
            return False, "work item ID %r does not use prefix %s" % (raw, prefix)
    return True, ""


def _clean_globs(values):
    out = []
    if isinstance(values, str):
        parts = [p.strip() for p in values.split(",")]
    else:
        parts = [str(p or "").strip() for p in (values or ())]
    for token in parts:
        token = token.strip("`\"' ")
        while token.startswith("./"):
            token = token[2:]
        if token and token not in out:
            out.append(token)
    return out


def _clean_ids(values):
    out = []
    if isinstance(values, str):
        parts = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]*-[0-9]+", values)
    else:
        parts = [str(p or "").strip() for p in (values or ())]
    for token in parts:
        if token and token not in ("-", "—", "none", "n/a") and token not in out:
            out.append(token)
    return out


def normalize_item(data, today=None):
    today = today or datetime.date.today().isoformat()
    raw_id = str(data.get("id") or "").strip()
    raw_tier = str(data.get("tier") or "2").strip()
    m_tier = re.search(r"[123]", raw_tier)
    tier = m_tier.group(0) if m_tier else "2"

    raw_effort = str(data.get("effort") or "").strip()
    effort = raw_effort.capitalize() if raw_effort.capitalize() in ("Lean", "Normal", "Beast") else ""
    if not effort:
        m_eff = INLINE_EFFORT_RE.search(raw_tier)
        if m_eff:
            effort = m_eff.group(1).capitalize()

    itype = str(data.get("type") or "feat").strip().lower()
    if itype == "bug":
        itype = "defect"
    if itype not in ITEM_TYPES:
        itype = "feat"

    status = normalize_status(data.get("status") or "Ready")
    created = str(data.get("created") or today).strip() or today
    updated = str(data.get("updated") or today).strip() or today
    completed = str(data.get("completed") or "").strip()
    if status == "Done" and not completed:
        completed = updated

    approvers = data.get("approvers") or []
    if isinstance(approvers, str):
        approvers = [a.strip() for a in approvers.split(",") if a.strip()]

    return {
        "id": raw_id,
        "title": str(data.get("title") or raw_id).strip(),
        "type": itype,
        "tier": tier,
        "effort": effort,
        "owner": str(data.get("owner") or "software-engineer").strip() or "software-engineer",
        "status": status,
        "depends": _clean_ids(data.get("depends")),
        "touch": _clean_globs(data.get("touch")),
        "created": created,
        "updated": updated,
        "completed": completed,
        "summary": str(data.get("summary") or "").strip(),
        "approvers": list(approvers),
        "waiting_on": str(data.get("waiting_on") or "").strip(),
        "park_reason": str(data.get("park_reason") or "").strip(),
        "unblock_by": str(data.get("unblock_by") or "").strip(),
        "later_when": str(data.get("later_when") or "").strip(),
        "dropped_reason": str(data.get("dropped_reason") or "").strip(),
    }


def _atomic_write_text(path, content):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_item(project, item_id):
    ok, _ = validate_item_id(item_id)
    if not ok:
        return None
    path = os.path.join(items_dir(project), item_id + ".json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and data.get("id"):
            return normalize_item(data, today=data.get("updated") or data.get("created") or "")
    except (IOError, OSError, ValueError):
        return None
    return None


def load_items(project):
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "shard_items" in cache:
        return cache["shard_items"]
    folder = items_dir(project)
    result = {}
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder), key=_id_sort_key):
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (IOError, OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            item_id = str(data.get("id") or name[:-5]).strip()
            ok, _ = validate_item_id(item_id)
            if not ok:
                continue
            data["id"] = item_id
            result[item_id] = normalize_item(
                data, today=data.get("updated") or data.get("created") or ""
            )
    if cache is not None:
        cache["shard_items"] = result
    return result


def save_item(project, data, today=None):
    today = today or datetime.date.today().isoformat()
    norm = normalize_item(data, today=today)
    ok, err = validate_item_id(
        norm["id"], project.prefix, getattr(project, "legacy_prefixes", None)
    )
    if not ok:
        raise ValueError(err)
    path = os.path.join(items_dir(project), norm["id"] + ".json")
    _atomic_write_text(path, json.dumps(norm, indent=2, ensure_ascii=False) + "\n")
    cache = getattr(project, "_build_cache", None)
    if cache is not None:
        cache.pop("shard_items", None)
        cache.pop("backlog_rendered", None)
    return norm


def extract_inline_touch(text):
    m = INLINE_TOUCH_RE.search(text or "")
    if not m:
        return []
    return _clean_globs(m.group(1))


def _strip_inline_tags(task_text):
    cleaned = re.sub(r"\s*\(\s*touch\s*:[^)]+\)", "", task_text or "", flags=re.I)
    cleaned = re.sub(r"\s*\[\s*touch\s*:[^\]]+\]", "", cleaned, flags=re.I)
    return cleaned.strip()


def parse_raw_backlog_items(raw_backlog, prefix="", legacy_prefixes=None):
    """Parse legacy backlog.md tables into normalized item dicts keyed by ID."""
    out = {}
    if not raw_backlog:
        return out
    lines = raw_backlog.splitlines()
    header = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if all(re.match(r"^:?-+:?$", c or "-") for c in cells):
            continue
        row = dict((header[i], cells[i] if i < len(cells) else "") for i in range(len(header)))
        raw_id = _plain(row.get("ID", ""))
        ok, _ = validate_item_id(raw_id, prefix, legacy_prefixes)
        if not ok or raw_id in out:
            continue
        raw_task = row.get("Task", row.get("Title", ""))
        raw_tier = row.get("Tier", "2")
        touch = extract_inline_touch(raw_task)
        m_eff = INLINE_EFFORT_RE.search(raw_tier) or INLINE_EFFORT_RE.search(raw_task)
        effort = m_eff.group(1).capitalize() if m_eff else ""
        itype = _plain(row.get("Type", "")).lower()
        if not itype:
            low_title = _plain(raw_task).lower()
            if re.match(r"^(?:fix|bug|defect)\b", low_title):
                itype = "defect"
            elif re.match(r"^(?:docs)\b", low_title):
                itype = "docs"
            elif re.match(r"^(?:chore)\b", low_title):
                itype = "chore"
            else:
                itype = "feat"
        since_val = _plain(row.get("Since", row.get("When", "")))
        completed_val = _plain(row.get("Completed", ""))
        date_guess = completed_val or since_val or ""
        out[raw_id] = normalize_item(
            {
                "id": raw_id,
                "title": _plain(_strip_inline_tags(raw_task)),
                "type": itype,
                "tier": raw_tier,
                "effort": effort,
                "owner": _plain(row.get("Owner role", "")) or "software-engineer",
                "status": _plain(row.get("Status", "")) or "Ready",
                "depends": row.get("Depends on", ""),
                "touch": touch,
                "created": date_guess,
                "updated": completed_val or since_val or date_guess,
                "completed": completed_val,
                "waiting_on": _plain(row.get("Waiting on whom", "")),
                "park_reason": _plain(row.get("For what decision", "")),
                "unblock_by": _plain(row.get("Who can unblock", "")),
                "later_when": _plain(row.get("Becomes relevant when", "")),
                "dropped_reason": _plain(row.get("Why dropped", "")),
            },
            today=date_guess,
        )
    return out


def merged_items(project, raw_backlog=None):
    """Return {id: item_dict} combining legacy backlog.md with items/*.json (shards win)."""
    if raw_backlog is None:
        raw_path = os.path.join(project_dir(project), "backlog.md")
        try:
            with open(raw_path, encoding="utf-8") as handle:
                raw_backlog = handle.read()
        except (IOError, OSError):
            raw_backlog = ""
    combined = parse_raw_backlog_items(
        raw_backlog, project.prefix, getattr(project, "legacy_prefixes", None)
    )
    combined.update(load_items(project))
    return combined


def _format_backlog_row(it):
    sec = section_for_status(it["status"])
    task = it["title"].replace("|", "\\|")
    if it.get("touch"):
        task = "%s (touch: %s)" % (task, ", ".join(it["touch"]))
    tier_cell = it["tier"]
    if it.get("effort"):
        tier_cell = "%s (effort: %s)" % (it["tier"], it["effort"])
    deps_cell = ", ".join(it.get("depends") or ())
    base = [it["id"], task, tier_cell, it["owner"], deps_cell, it["status"]]
    if sec == "Blocked":
        base += [it.get("unblock_by") or "owner", it.get("updated") or it.get("created") or ""]
    elif sec == "Parked":
        base += [
            it.get("waiting_on") or "the owner",
            it.get("park_reason") or ("merge approval (Tier %s)" % it["tier"]),
            it.get("updated") or it.get("created") or "",
        ]
    elif sec == "Later":
        base += [it.get("later_when") or "when scheduled"]
    elif sec == "Done":
        base += [it.get("completed") or it.get("updated") or ""]
    elif sec == "Dropped":
        base += [it.get("dropped_reason") or "superseded", it.get("updated") or ""]
    return "| " + " | ".join(c.replace("|", "\\|") if i != 1 else c for i, c in enumerate(base)) + " |"


SECTION_SPECS = (
    (
        "Now",
        "## Now",
        "Actively in progress. Keep this short enough to be real — if everything is here, nothing\nis prioritised.",
        "| ID | Task | Tier | Owner role | Depends on | Status |\n| --- | --- | --- | --- | --- | --- |",
    ),
    (
        "Next",
        "## Next",
        "Agreed, not started. Ordered by priority.",
        "| ID | Task | Tier | Owner role | Depends on | Status |\n| --- | --- | --- | --- | --- | --- |",
    ),
    (
        "Blocked",
        "## Blocked",
        "Cannot proceed. The blocker must be a real, identified thing with an owner — not \"needs\nmore thought\".",
        "| ID | Task | Tier | Owner role | Depends on | Status | Who can unblock | Since |\n| --- | --- | --- | --- | --- | --- | --- | --- |",
    ),
    (
        "Parked",
        "## Parked — awaiting a human",
        "Built and verified as far as an agent can take it; stopped at an approval or a waiver\nonly a named human can give. This is a finished state for the agent, not an excuse to\nproceed. See \"Waiting on a human\" in `../process/00-operating-model.md`.",
        "| ID | Task | Tier | Owner role | Depends on | Status | Waiting on whom | For what decision | Since |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ),
    (
        "Later",
        "## Later",
        "Valid, not now. Include the condition that would make it now.",
        "| ID | Task | Tier | Owner role | Depends on | Status | Becomes relevant when |\n| --- | --- | --- | --- | --- | --- | --- |",
    ),
    (
        "Done",
        "## Done",
        "Newest first. Move to `worklog-archive/` once this section gets long — the worklog is the\npermanent record, and the entry is found by ID.",
        "| ID | Task | Tier | Owner role | Depends on | Status | Completed |\n| --- | --- | --- | --- | --- | --- | --- |",
    ),
    (
        "Dropped",
        "## Dropped",
        "**Never delete a row — move it here.** The record that something was considered and\nrejected stops it being proposed, discussed, and rejected again. The ID stays reserved.",
        "| ID | Task | Tier | Owner role | Depends on | Status | Why dropped | When |\n| --- | --- | --- | --- | --- | --- | --- | --- |",
    ),
)


def _backlog_preamble(raw_backlog, project_name, today):
    if raw_backlog and "## Now" in raw_backlog:
        pre = raw_backlog.split("## Now", 1)[0].rstrip("\n")
        pre = re.sub(r"(?m)^(last-reviewed:\s*)YYYY-MM-DD\s*$", r"\g<1>" + today, pre)
        pre = re.sub(r"(?m)^(status:\s*)draft\s*$", r"\g<1>current", pre)
        return pre
    return (
        "---\nstatus: current\nowner: product-manager\nlast-reviewed: %s\n---\n\n"
        "# Backlog — %s\n\n"
        "> **This table stays terse. One line per item.** Canonical per-item shards live in\n"
        "> `items/<ID>.json`; materialize this summary view with `sdlc.py render`."
        % (today, project_name or "Project")
    )


def render_backlog_markdown(project, raw_backlog=None, today=None):
    today = today or datetime.date.today().isoformat()
    if raw_backlog is None:
        raw_path = os.path.join(project_dir(project), "backlog.md")
        try:
            with open(raw_path, encoding="utf-8") as handle:
                raw_backlog = handle.read()
        except (IOError, OSError):
            raw_backlog = ""
    all_items = merged_items(project, raw_backlog)
    by_sec = dict((sec_key, []) for sec_key, _, _, _ in SECTION_SPECS)
    for item_id in sorted(all_items.keys(), key=_id_sort_key):
        it = all_items[item_id]
        by_sec[section_for_status(it["status"])].append(it)
    for newest_first in ("Done", "Parked", "Dropped"):
        by_sec[newest_first].sort(
            key=lambda x: (x.get("completed") or x.get("updated") or "", _id_sort_key(x["id"])),
            reverse=True,
        )

    proj_name = os.path.basename(project.root)
    preamble = _backlog_preamble(raw_backlog, proj_name, today)
    chunks = [preamble, ""]
    if raw_backlog and "## Epics" in raw_backlog and "## Epics" not in preamble:
        epics_part = "## Epics" + raw_backlog.split("## Epics", 1)[1].split("\n## ", 1)[0]
        chunks.extend([epics_part.rstrip("\n"), ""])

    for sec_key, heading, blurb, table_head in SECTION_SPECS:
        chunks.append(heading)
        chunks.append("")
        chunks.append(blurb)
        chunks.append("")
        chunks.append(table_head)
        for it in by_sec[sec_key]:
            chunks.append(_format_backlog_row(it))
        chunks.append("")
    return "\n".join(chunks).rstrip("\n") + "\n"


def overlay_backlog(project, raw_backlog):
    """Overlay items/*.json onto raw_backlog when shards exist; return raw_backlog otherwise."""
    shard_items = load_items(project)
    if not shard_items:
        return raw_backlog
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "backlog_rendered" in cache:
        return cache["backlog_rendered"]
    rendered = render_backlog_markdown(project, raw_backlog=raw_backlog)
    if cache is not None:
        cache["backlog_rendered"] = rendered
    return rendered


# ---------------------------------------------------------------- worklog shards

def load_worklog_shard(project, item_id):
    ok, _ = validate_item_id(item_id)
    if not ok:
        return ""
    path = os.path.join(worklog_dir(project), item_id + ".md")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (IOError, OSError):
        return ""


def save_worklog_shard(project, item_id, text):
    ok, err = validate_item_id(
        item_id, project.prefix, getattr(project, "legacy_prefixes", None)
    )
    if not ok:
        raise ValueError(err)
    path = os.path.join(worklog_dir(project), item_id + ".md")
    _atomic_write_text(path, text.strip("\n") + "\n")
    cache = getattr(project, "_build_cache", None)
    if cache is not None:
        cache.pop("worklog_shards", None)
    return path


def load_worklog_shards(project):
    """Return [(item_id, rel_path, content)] sorted newest-ID-first."""
    cache = getattr(project, "_build_cache", None)
    if cache is not None and "worklog_shards" in cache:
        return cache["worklog_shards"]
    folder = worklog_dir(project)
    entries = []
    if os.path.isdir(folder):
        names = [n for n in os.listdir(folder) if n.endswith(".md")]
        names.sort(key=lambda n: _id_sort_key(n[:-3]), reverse=True)
        for name in names:
            item_id = name[:-3]
            ok, _ = validate_item_id(item_id)
            if not ok:
                continue
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    body = handle.read().strip("\n")
            except (IOError, OSError):
                continue
            if body:
                entries.append((item_id, os.path.relpath(path, project.root), body))
    if cache is not None:
        cache["worklog_shards"] = entries
    return entries


def split_worklog_entries(raw_worklog):
    """Return (preamble, [(item_id_or_empty, block_text)]) from a worklog.md string."""
    if not raw_worklog:
        return "", []
    marker = "<!-- New entries go here"
    if marker in raw_worklog:
        idx = raw_worklog.index(marker)
        line_end = raw_worklog.find("\n", idx)
        cut = (line_end + 1) if line_end >= 0 else len(raw_worklog)
        preamble = raw_worklog[:cut].rstrip("\n")
        rest = raw_worklog[cut:]
    else:
        m_first = re.search(r"(?m)^(?=##\s+[A-Za-z0-9#]|-\s+\d{4}-\d{2}-\d{2}\s+·\s+)", raw_worklog)
        if not m_first:
            return raw_worklog.rstrip("\n"), []
        preamble = raw_worklog[:m_first.start()].rstrip("\n")
        rest = raw_worklog[m_first.start():]

    rest = re.sub(r"(?m)^_\(No entries yet\.[^\n]*\)_\s*$", "", rest).strip("\n")
    if not rest.strip():
        return preamble, []

    blocks = re.split(r"(?m)^(?=##\s+[A-Za-z0-9#]|-\s+\d{4}-\d{2}-\d{2}\s+·\s+)", rest)
    parsed = []
    for blk in blocks:
        blk_clean = blk.strip("\n")
        if not blk_clean:
            continue
        # If multiple compact lines sit adjacent without ## headers, split each compact line.
        if blk_clean.startswith("- ") and "\n- " in blk_clean:
            for sub_line in re.split(r"(?m)^(?=-\s+\d{4}-\d{2}-\d{2}\s+·\s+)", blk_clean):
                sc = sub_line.strip("\n")
                if not sc:
                    continue
                mh = ENTRY_HEAD_RE.match(sc)
                eid = (mh.group(1) or mh.group(2) or "") if mh else ""
                parsed.append((eid, sc))
        else:
            mh = ENTRY_HEAD_RE.match(blk_clean)
            eid = (mh.group(1) or mh.group(2) or "") if mh else ""
            parsed.append((eid, blk_clean))
    return preamble, parsed


def _entry_date_key(item_id, text):
    m = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
    if not m:
        m = re.match(r"^-\s+(\d{4}-\d{2}-\d{2})\s+·", text)
    date_str = m.group(1) if m else ""
    return (date_str, _id_sort_key(item_id))


def render_worklog_markdown(project, raw_worklog=None, today=None):
    today = today or datetime.date.today().isoformat()
    if raw_worklog is None:
        raw_path = os.path.join(project_dir(project), "worklog.md")
        try:
            with open(raw_path, encoding="utf-8") as handle:
                raw_worklog = handle.read()
        except (IOError, OSError):
            raw_worklog = ""

    preamble, legacy_entries = split_worklog_entries(raw_worklog)
    if not preamble:
        proj_name = os.path.basename(project.root)
        preamble = (
            "---\nstatus: current\nowner: _(whoever last shipped)_\nlast-reviewed: %s\n---\n\n"
            "# Worklog — %s\n\n---\n\n<!-- New entries go here, above the older ones. -->"
            % (today, proj_name)
        )
    else:
        preamble = re.sub(r"(?m)^(last-reviewed:\s*)YYYY-MM-DD\s*$", r"\g<1>" + today, preamble)
        preamble = re.sub(r"(?m)^(status:\s*)draft\s*$", r"\g<1>current", preamble)

    shard_map = dict((eid, body) for eid, _, body in load_worklog_shards(project))
    seen = set()
    combined = []

    for eid, body in shard_map.items():
        seen.add(eid)
        combined.append((eid, body))
    for eid, body in legacy_entries:
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)
        combined.append((eid, body))

    combined.sort(key=lambda pair: _entry_date_key(pair[0], pair[1]), reverse=True)
    out = [preamble, ""]
    if not combined:
        out.append("_(No entries yet. The first one is written when the first work item reaches Done.)_")
    else:
        for idx, (_, body) in enumerate(combined):
            out.append(body)
            if idx + 1 < len(combined):
                out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


# ---------------------------------------------------------------- ledger shards

def _sanitize_run_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name or "").strip()).strip("-")
    return cleaned or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


_LEDGER_SHARD_RE = re.compile(
    r"^(\d{8}T\d{6}(?:\.\d+)?Z)(?:-(bite|audit|waiver))?(?:-(\d+))?(?:-(.*))?\.jsonl$"
)


def _ledger_shard_sort_key(filename):
    m = _LEDGER_SHARD_RE.match(filename or "")
    if m:
        stamp = m.group(1)
        kind = m.group(2) or ""
        seq = int(m.group(3)) if m.group(3) else 1
        rest = m.group(4) or ""
        return (0, stamp, seq, kind, rest)
    return (1, filename or "", 0, "", "")


def read_ledger_shards(project):
    folder = ledger_dir(project)
    rows = []
    if not os.path.isdir(folder):
        return rows
    for name in sorted(os.listdir(folder), key=_ledger_shard_sort_key):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except ValueError:
                        continue
        except (IOError, OSError):
            continue
    return rows


def append_ledger_shards(project, entries):
    if not entries:
        return []
    folder = ledger_dir(project)
    os.makedirs(folder, exist_ok=True)
    grouped = {}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for idx, entry in enumerate(entries):
        run_key = entry.get("run")
        if not run_key:
            tag = entry.get("item") or (entry.get("commit") or "")[:7] or str(idx)
            run_key = "%s-%s" % (stamp, tag)
        grouped.setdefault(_sanitize_run_name(run_key), []).append(entry)

    written = []
    for run_name, batch in sorted(grouped.items()):
        serialized = "".join(json.dumps(row, sort_keys=True) + "\n" for row in batch)
        digest8 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:8]
        item_tag = batch[0].get("item") or (batch[0].get("commit") or "")[:7]
        if item_tag:
            fname = "%s-%s-%s.jsonl" % (run_name, _sanitize_run_name(item_tag), digest8)
        else:
            fname = "%s-%s.jsonl" % (run_name, digest8)
        target = os.path.join(folder, fname)
        if not os.path.isfile(target):
            _atomic_write_text(target, serialized)
        written.append(os.path.relpath(target, project.root))
    return written


def ledger_row_key(row):
    return (
        str(row.get("run") or ""),
        str(row.get("stage") or ""),
        str(row.get("commit") or ""),
        str(row.get("item") or ""),
        str(row.get("time") or ""),
        str(row.get("waived_by") or ""),
        str(row.get("result") or ""),
    )


# ---------------------------------------------------------------- render & migrate

def render(project, check_only=False):
    """Materialize backlog.md and worklog.md from shards + legacy records (or check drift)."""
    pdir = project_dir(project)
    backlog_path = os.path.join(pdir, "backlog.md")
    worklog_path = os.path.join(pdir, "worklog.md")

    try:
        with open(backlog_path, encoding="utf-8") as handle:
            cur_backlog = handle.read()
    except (IOError, OSError):
        cur_backlog = ""
    try:
        with open(worklog_path, encoding="utf-8") as handle:
            cur_worklog = handle.read()
    except (IOError, OSError):
        cur_worklog = ""

    want_backlog = render_backlog_markdown(project, raw_backlog=cur_backlog)
    want_worklog = render_worklog_markdown(project, raw_worklog=cur_worklog)

    drift = []
    files = []
    for rel_name, path, cur, want in (
        (os.path.join(project.docs, "project", "backlog.md"), backlog_path, cur_backlog, want_backlog),
        (os.path.join(project.docs, "project", "worklog.md"), worklog_path, cur_worklog, want_worklog),
    ):
        changed = cur != want
        if changed:
            drift.append(rel_name)
            if not check_only:
                _atomic_write_text(path, want)
        files.append({"path": rel_name, "changed": changed})

    cache = getattr(project, "_build_cache", None)
    if cache is not None and not check_only:
        cache.pop("backlog_rendered", None)

    return {
        "in_sync": len(drift) == 0,
        "check_only": bool(check_only),
        "drift": drift,
        "files": files,
    }


def migrate_shards(rt, project, apply=False):
    """Migrate legacy 4.x backlog.md, worklog.md, and evidence-ledger.jsonl into v5 shards."""
    today = datetime.date.today().isoformat()
    pdir = project_dir(project)
    backlog_path = os.path.join(pdir, "backlog.md")
    worklog_path = os.path.join(pdir, "worklog.md")
    legacy_ledger_path = os.path.join(pdir, "evidence-ledger.jsonl")

    raw_backlog = rt.read(backlog_path)
    raw_worklog = rt.read(worklog_path)

    existing_items = load_items(project)
    parsed_items = parse_raw_backlog_items(
        raw_backlog, project.prefix, getattr(project, "legacy_prefixes", None)
    )
    to_write_items = [it for iid, it in sorted(parsed_items.items(), key=lambda kv: _id_sort_key(kv[0]))
                      if iid not in existing_items]

    existing_wl = dict((eid, body) for eid, _, body in load_worklog_shards(project))
    _, wl_entries = split_worklog_entries(raw_worklog)
    to_write_wl = []
    for eid, body in wl_entries:
        ok, _ = validate_item_id(eid, project.prefix, getattr(project, "legacy_prefixes", None))
        if ok and eid not in existing_wl:
            to_write_wl.append((eid, body))
            existing_wl[eid] = body

    legacy_rows = []
    if os.path.isfile(legacy_ledger_path):
        for line in rt.read(legacy_ledger_path).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    legacy_rows.append(obj)
            except ValueError:
                continue
    existing_keys = set(ledger_row_key(r) for r in read_ledger_shards(project))
    to_write_ledger = [r for r in legacy_rows if ledger_row_key(r) not in existing_keys]

    report = []
    if apply:
        os.makedirs(items_dir(project), exist_ok=True)
        os.makedirs(worklog_dir(project), exist_ok=True)
        os.makedirs(ledger_dir(project), exist_ok=True)
        for it in to_write_items:
            save_item(project, it, today=it.get("updated") or today)
        for eid, body in to_write_wl:
            save_worklog_shard(project, eid, body)
        if to_write_ledger:
            append_ledger_shards(project, to_write_ledger)
        if os.path.isfile(legacy_ledger_path):
            os.remove(legacy_ledger_path)
        render(project, check_only=False)

    verb = "migrated" if apply else "would migrate"
    if not (to_write_items or to_write_wl or to_write_ledger or os.path.isfile(legacy_ledger_path)):
        if has_shards(project):
            return ["every record is already in v5 shards"]
        return ["%s 0 items, 0 worklog entries, 0 ledger rows (creates %s/project/{items,worklog,ledger}/)"
                % (verb, project.docs)]

    report.append(
        "%s %d item(s) -> %s/project/items/, %d worklog entr%s -> %s/project/worklog/, "
        "%d ledger row(s) -> %s/project/ledger/"
        % (
            verb,
            len(to_write_items),
            project.docs,
            len(to_write_wl),
            "y" if len(to_write_wl) == 1 else "ies",
            project.docs,
            len(to_write_ledger),
            project.docs,
        )
    )
    return report


# ---------------------------------------------------------------------------
# Field-level 3-way merge of items/<ID>.json, run by git as the "nuhut-shard" merge driver:
#   git config merge.nuhut-shard.driver "<python> <sdlc.py> merge-shard %O %A %B"
# The result is written to %A. Exit 0 = merged cleanly, 1 = conflict markers written,
# 2 = a file could not be read or parsed (then %A is left exactly as it was).

MERGE_DRIVER_NAME = "nuhut-shard"
# A governance field both sides changed differently is a human decision, never a merge.
MERGE_CONFLICT_FIELDS = ("approvers", "waivers", "status", "hotfix", "owner")
# Append-only history: the union keeps every entry either side recorded.
MERGE_HISTORY_FIELDS = ("history",)
# An 'updated' stamp further ahead of this machine's clock than this is ignored.
MERGE_FUTURE_SLACK = datetime.timedelta(minutes=5)
MERGE_MAX_BYTES = 4 * 1024 * 1024
_ABSENT = object()


class ShardMergeError(Exception):
    pass


def _merge_load(path, allow_empty=False):
    try:
        if os.path.getsize(path) > MERGE_MAX_BYTES:
            raise ShardMergeError("%s is larger than %d bytes" % (path, MERGE_MAX_BYTES))
        with open(path, "rb") as handle:
            raw = handle.read()
        text = raw.decode("utf-8")
    except (IOError, OSError, UnicodeDecodeError) as exc:
        raise ShardMergeError("cannot read %s: %s" % (path, exc))
    if allow_empty and not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ShardMergeError("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(data, dict):
        raise ShardMergeError("%s is not a JSON object" % path)
    return data


def _merge_when(value, now):
    """Parse an 'updated' stamp to a naive local datetime; None when absent, unparseable,
    or more than MERGE_FUTURE_SLACK ahead of now (a skewed or forged clock never wins)."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    when = None
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            when = datetime.datetime.strptime(raw, "%Y-%m-%d")
        else:
            iso = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
            when = datetime.datetime.fromisoformat(iso.replace(" ", "T", 1))
            if when.tzinfo is not None:
                when = when.astimezone().replace(tzinfo=None)
    except (ValueError, OverflowError):
        return None
    if when > now + MERGE_FUTURE_SLACK:
        return None
    return when


def _merge_key(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _merge_union(base, ours, theirs):
    out, seen = [], set()
    for seq in (base, ours, theirs):
        for entry in seq:
            k = _merge_key(entry)
            if k not in seen:
                seen.add(k)
                out.append(entry)
    return out


def _merge_set(base, ours, theirs):
    """3-way set merge: an entry stays unless a side removed it; additions from both sides
    are kept. Order follows base, then ours, then theirs."""
    bk = set(_merge_key(x) for x in base)
    ok_ = set(_merge_key(x) for x in ours)
    tk = set(_merge_key(x) for x in theirs)
    out, seen = [], set()
    for seq in (base, ours, theirs):
        for entry in seq:
            k = _merge_key(entry)
            if k in seen:
                continue
            seen.add(k)
            if k in bk and (k not in ok_ or k not in tk):
                continue
            out.append(entry)
    return out


def _merge_tier(ours, theirs):
    """Tier 1 is the strictest. None when either value is not a readable tier."""
    found = []
    for value in (ours, theirs):
        m = re.search(r"[123]", str(value)) if isinstance(value, (str, int)) else None
        if not m:
            return None
        found.append((int(m.group(0)), value))
    return min(found, key=lambda pair: pair[0])[1]


def merge_item_dicts(base, ours, theirs, now=None):
    """Return (merged_dict, conflicts) where conflicts is [(key, ours_value, theirs_value)];
    a value is _ABSENT when that side has no such key."""
    now = now or datetime.datetime.now()
    keys = []
    for src in (ours, theirs, base):
        for k in src:
            if k not in keys:
                keys.append(k)
    t_ours = _merge_when(ours.get("updated"), now)
    t_theirs = _merge_when(theirs.get("updated"), now)
    merged, conflicts = {}, []
    for key in keys:
        o = base.get(key, _ABSENT)
        a = ours.get(key, _ABSENT)
        b = theirs.get(key, _ABSENT)
        if _merge_key_or_absent(a) == _merge_key_or_absent(b):
            value = a
        elif _merge_key_or_absent(a) == _merge_key_or_absent(o):
            value = b
        elif _merge_key_or_absent(b) == _merge_key_or_absent(o):
            value = a
        elif key == "updated":
            stamps = [(t, v) for t, v in ((t_ours, a), (t_theirs, b)) if t is not None]
            value = max(stamps, key=lambda pair: pair[0])[1] if stamps else (o if o is not _ABSENT else a)
        elif key == "id":
            raise ShardMergeError("the two sides disagree on the item ID")
        elif key in MERGE_HISTORY_FIELDS and all(isinstance(v, list) for v in (a, b)):
            value = _merge_union(o if isinstance(o, list) else [], a, b)
        elif key == "tier" and _merge_tier(a, b) is not None:
            value = _merge_tier(a, b)
        elif key in MERGE_CONFLICT_FIELDS or key == "tier":
            conflicts.append((key, a, b))
            value = a
        elif isinstance(a, list) and isinstance(b, list):
            value = _merge_set(o if isinstance(o, list) else [], a, b)
        elif t_ours is not None and (t_theirs is None or t_ours > t_theirs):
            value = a
        elif t_theirs is not None and (t_ours is None or t_theirs > t_ours):
            value = b
        else:
            conflicts.append((key, a, b))
            value = a
        if value is not _ABSENT:
            merged[key] = value
    return merged, conflicts


def _merge_key_or_absent(value):
    return "\0absent" if value is _ABSENT else _merge_key(value)


def _merge_field_line(key, value, indent_rest=True):
    body = json.dumps(value, indent=2, ensure_ascii=False) if indent_rest else \
        json.dumps(value, ensure_ascii=False)
    return "  %s: %s" % (json.dumps(key, ensure_ascii=False), body.replace("\n", "\n  "))


def render_merge_conflict(merged, conflicts, marker_size=7):
    """JSON-shaped text with git-style markers around each truly conflicting field."""
    by_key = dict((k, (a, b)) for k, a, b in conflicts)
    keys = list(merged.keys())
    for k in by_key:
        if k not in keys:
            keys.append(k)
    lines = ["{"]
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        if key in by_key:
            a, b = by_key[key]
            lines.append("<" * marker_size + " ours")
            if a is not _ABSENT:
                lines.append(_merge_field_line(key, a, indent_rest=False) + comma)
            lines.append("=" * marker_size)
            if b is not _ABSENT:
                lines.append(_merge_field_line(key, b, indent_rest=False) + comma)
            lines.append(">" * marker_size + " theirs")
        else:
            lines.append(_merge_field_line(key, merged[key]) + comma)
    lines.append("}")
    return "\n".join(lines) + "\n"


def merge_shard_files(base_path, ours_path, theirs_path, now=None, marker_size=7):
    """Merge three versions of an item shard into ours_path. Returns (exit_code, message)."""
    # git passes %A relative to the worktree root (".merge_file_XXXX").
    base_path, ours_path, theirs_path = [os.path.abspath(p) for p in (base_path, ours_path, theirs_path)]
    try:
        base = _merge_load(base_path, allow_empty=True)
        ours = _merge_load(ours_path)
        theirs = _merge_load(theirs_path)
        ids = set(str(d.get("id") or "") for d in (base, ours, theirs) if d)
        if len(ids) != 1 or not list(ids)[0]:
            raise ShardMergeError("the three versions do not name one item ID (%s)"
                                  % ", ".join(sorted(repr(i) for i in ids)))
        merged, conflicts = merge_item_dicts(base, ours, theirs, now=now)
        if conflicts:
            text = render_merge_conflict(merged, conflicts, marker_size)
        else:
            text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
        mode = os.stat(ours_path).st_mode & 0o777
        _atomic_write_text(ours_path, text)
        os.chmod(ours_path, mode)
    except ShardMergeError as exc:
        return 2, "merge-shard: %s; left the file unchanged" % exc
    except (IOError, OSError) as exc:
        return 2, "merge-shard: cannot write the result: %s; left the file unchanged" % exc
    item_id = list(ids)[0]
    if conflicts:
        return 1, "merge-shard: %s conflicts on %s; resolve the markers, then git add the file" % (
            item_id, ", ".join(k for k, _, _ in conflicts))
    return 0, "merge-shard: %s merged" % item_id

"""Pluggable multi-worker queue dispatcher for Nuhut Software Factory (v5.0+).

Schedules conflict-free waves of Ready work items from `claims.parallel`, executes
each item in an isolated git worktree through a headless builder CLI (`claude`,
`codex`, `gemini`, or `cmd:<command>`), enforces `verify` + `slop` + optional
independent `review` + single-shot `finish`, and records structured telemetry
under `.ai-sdlc/dispatch/`.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import threading
import time

import shards

# The v5 table: the fallback when the registry is missing. The built-in extensions in
# .ai-sdlc/extensions/ are the source (sdlc.agent_table); tests/smoke.py checks parity.
BUILD_HARNESSES = {
    "claude": (["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits", "--output-format", "text"], "--model"),
    "codex": (["codex", "exec", "--full-auto", "{prompt}"], "--model"),
    "gemini": (["gemini", "-p", "{prompt}", "-y"], "--model"),
}

MAX_DISPATCH_RUNS = 50


def dispatch_folder(project):
    return project.path(os.path.join(".ai-sdlc", "dispatch"))


def load_dispatch_runs(project, limit=20):
    folder = dispatch_folder(project)
    if not os.path.isdir(folder):
        return []
    out = []
    names = sorted(n for n in os.listdir(folder) if n.endswith(".json"))[-limit:]
    for name in names:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                out.append(data)
        except (IOError, OSError, ValueError):
            continue
    return out


def _save_dispatch_run(rt, project, record):
    folder = dispatch_folder(project)
    os.makedirs(folder, exist_ok=True)
    ignore = os.path.join(folder, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as handle:
            handle.write("*\n")
    run_id = record.get("run_id") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(folder, run_id + ".json")
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, "%s-%d.json" % (run_id, n))
        record["run_id"] = "%s-%d" % (run_id, n)
    raw = json.dumps(record, indent=2, ensure_ascii=False)
    if hasattr(rt, "redact"):
        raw, _ = rt.redact(raw)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(raw + "\n")
    kept = sorted(f for f in os.listdir(folder) if f.endswith(".json"))
    for old in kept[:-MAX_DISPATCH_RUNS]:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    return os.path.relpath(path, project.root)


def _build_table(rt, project):
    if hasattr(rt, "agent_table"):
        return rt.agent_table(project, "build")
    return BUILD_HARNESSES


def _validate_harness(spec, role_label="builder", table=None, broken=None):
    table = BUILD_HARNESSES if table is None else table
    if not spec:
        return None, "--by is required unless --dry-run (claude, codex, gemini, or cmd:<command>)"
    if spec.startswith("cmd:"):
        cmd = spec[4:].strip()
        if not cmd:
            return None, "%s cmd: requires a non-empty command" % role_label
        return ("cmd", cmd), None
    if broken:
        message = broken(spec)
        if message:
            return None, message
    if spec in table:
        exe = table[spec][0][0]
        if shutil.which(exe) is None:
            return None, "%s %r is not installed (no %r on PATH)" % (role_label, spec, exe)
        return (spec, None), None
    return None, "%s must be %s, or cmd:<command>" % (role_label, ", ".join(sorted(table)))


def _may_auto_merge(project, rt, pr_mode=False, no_merge=False):
    if pr_mode or no_merge:
        return False
    cell = rt.UNFILLED.sub("", rt.labelled(project.charter, "May merge to the default branch") or "").strip().lower()
    if cell.startswith("no"):
        return False
    dirty = project.git("status", "--porcelain").strip()
    if dirty:
        return False
    return True


def _worktree_base(project, claims_mod, custom_root=None):
    if custom_root:
        return os.path.abspath(custom_root)
    cdir = claims_mod.common_dir(project)
    if cdir:
        return os.path.join(cdir, "nuhut", "worktrees")
    return project.path(os.path.join(".ai-sdlc", "worktrees"))


def _provision_worktree_kit(src_project, wt_path):
    """Ensure .ai-sdlc/bin and config files exist in a linked worktree even when .ai-sdlc/
    is git-ignored in the repository. Returns True if .ai-sdlc/ was created untracked."""
    dst_aisdlc = os.path.join(wt_path, ".ai-sdlc")
    if os.path.isfile(os.path.join(dst_aisdlc, "bin", "sdlc.py")):
        return False
    src_aisdlc = src_project.path(".ai-sdlc")
    if not os.path.isdir(src_aisdlc):
        return False
    os.makedirs(dst_aisdlc, exist_ok=True)
    src_bin = os.path.join(src_aisdlc, "bin")
    dst_bin = os.path.join(dst_aisdlc, "bin")
    if os.path.isdir(src_bin) and not os.path.exists(dst_bin):
        shutil.copytree(src_bin, dst_bin)
    for fname in ("profile.json", "manifest.json", "protected.txt", "gates.txt", "test-lock.txt"):
        sfile = os.path.join(src_aisdlc, fname)
        dfile = os.path.join(dst_aisdlc, fname)
        if os.path.isfile(sfile) and not os.path.exists(dfile):
            shutil.copy2(sfile, dfile)
    return True


def _copy_evidence_back(wt_path, dst_project):
    src_ev = os.path.join(wt_path, ".ai-sdlc", "evidence")
    if not os.path.isdir(src_ev):
        return
    dst_ev = dst_project.path(os.path.join(".ai-sdlc", "evidence"))
    os.makedirs(dst_ev, exist_ok=True)
    for name in sorted(os.listdir(src_ev)):
        sdir = os.path.join(src_ev, name)
        ddir = os.path.join(dst_ev, name)
        if os.path.isdir(sdir) and not os.path.exists(ddir):
            try:
                shutil.copytree(sdir, ddir)
            except OSError:
                pass


def _cleanup_worktree_before_release(wt_path, provisioned_aisdlc):
    if provisioned_aisdlc:
        shutil.rmtree(os.path.join(wt_path, ".ai-sdlc"), ignore_errors=True)
    else:
        for sub in ("evidence", "cache", "bite", "runs", "view", "dispatch"):
            shutil.rmtree(os.path.join(wt_path, ".ai-sdlc", sub), ignore_errors=True)
    subprocess.run(
        ["git", "checkout", "--", "."],
        cwd=wt_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=wt_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _changed_non_record_files(wt_project, base_sha):
    records_prefix = wt_project.docs.rstrip("/") + "/project/"
    names = set()
    diff_committed = wt_project.git("diff", "--name-only", base_sha, "HEAD").splitlines()
    diff_work = wt_project.git("diff", "--name-only", "HEAD").splitlines()
    untracked = wt_project.git("ls-files", "--others", "--exclude-standard").splitlines()
    for path in diff_committed + diff_work + untracked:
        p = path.strip()
        if not p or p.startswith(".ai-sdlc/") or p.startswith(records_prefix):
            continue
        names.add(p)
    return sorted(names)


def _stage_and_commit(wt_path, subject, trailers_text):
    subprocess.run(["git", "add", "-A"], cwd=wt_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Never commit local .ai-sdlc scratch/evidence directories even if unignored.
    subprocess.run(
        ["git", "reset", "-q", "HEAD", "--", ".ai-sdlc"],
        cwd=wt_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=wt_path, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ).stdout.decode("utf-8", "replace").strip()
    if not staged:
        return None
    proc = subprocess.run(
        ["git", "commit", "-q", "-m", subject, "-m", trailers_text],
        cwd=wt_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=wt_path, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ).stdout.decode("utf-8", "replace").strip()
    return sha


def _build_prompt(rt, wt_project, item_meta, attempt=1, failure_report=""):
    item_id = item_meta["id"]
    tier = item_meta.get("tier") or "2"
    effort = item_meta.get("effort") or "Normal"
    itype = item_meta.get("type") or "feat"
    title = item_meta.get("title") or item_id
    touch = item_meta.get("touch") or []
    summary = item_meta.get("summary") or ""
    cmds = rt.charter_commands(wt_project.charter)
    active_cmds = "\n".join(
        "- checks.%s: `%s`" % (s, c) for s, c in cmds.items() if c and c != "absent"
    ) or "- (no checks configured in charter)"

    plan_body = ""
    plans_dir = wt_project.path(os.path.join(wt_project.docs, "project", "plans"))
    if os.path.isdir(plans_dir):
        for name in sorted(os.listdir(plans_dir)):
            if (name == item_id + ".md" or name.startswith(item_id + "-")) and name.endswith(".md"):
                plan_body = rt.read(os.path.join(plans_dir, name)).strip()
                break

    lines = [
        "You are an autonomous Nuhut Software Factory worker executing work item %s." % item_id,
        "Read and obey AGENTS.md in this repository.",
        "",
        "## Assigned Work Item",
        "- ID: %s" % item_id,
        "- Title: %s" % title,
        "- Type: %s" % itype,
        "- Tier: %s" % tier,
        "- Effort: %s" % effort,
        "- Owner role: %s" % (item_meta.get("owner") or "software-engineer"),
    ]
    if touch:
        lines.append("- Declared file scope (touch): %s" % ", ".join("`%s`" % t for t in touch))
    if summary:
        lines.append("- Context: %s" % summary)
    lines += [
        "",
        "## Configured Verification Checks",
        active_cmds,
    ]
    if plan_body:
        lines += ["", "## Approved Plan", plan_body[:8000]]
    if attempt > 1 and failure_report:
        lines += [
            "",
            "## Repair Turn (Attempt %d)" % attempt,
            "The previous attempt failed verification. Fix the root cause without weakening tests or checks:",
            "```",
            failure_report[-6000:],
            "```",
        ]
    lines += [
        "",
        "## Instructions",
        "1. Implement the requested change cleanly in this working tree and add/update tests alongside it.",
        "2. Stay strictly within the scope of %s (do not edit backlog.md or worklog.md directly)." % item_id,
        "3. If you notice an unrelated bug out of scope, do not fix it here; report a line starting with `Discovered: <one-line defect description>`.",
        "4. End your response with `Summary: <concise 1-2 sentence explanation of what changed and why>`.",
        "",
    ]
    return "\n".join(lines)


def _extract_builder_notes(stdout_text, title):
    summary = ""
    discovered = []
    for line in (stdout_text or "").splitlines():
        s = line.strip()
        m_sum = re.match(r"^Summary:\s*(.+)$", s, re.I)
        if m_sum:
            summary = m_sum.group(1).strip()
        m_disc = re.match(r"^Discovered:\s*(.+)$", s, re.I)
        if m_disc:
            val = m_disc.group(1).strip()
            if val and val.lower() not in ("none", "nothing", "n/a"):
                discovered.append(val)
    if not summary:
        summary = "Implemented %s and verified configured charter checks." % title
    return summary, discovered


def _run_builder_turn(rt, harness_kind, harness_cmd, model, prompt, wt_path, item_meta, attempt, timeout,
                      table=None):
    env = dict(os.environ)
    env["NUHUT_DISPATCH_WORKER"] = "1"
    env["NUHUT_ITEM_ID"] = item_meta["id"]
    env["NUHUT_ITEM_TIER"] = str(item_meta.get("tier") or "2")
    env["NUHUT_ITEM_TYPE"] = str(item_meta.get("type") or "feat")
    env["NUHUT_ITEM_EFFORT"] = str(item_meta.get("effort") or "Normal")
    env["NUHUT_ATTEMPT"] = str(attempt)
    env["NUHUT_WORKTREE"] = wt_path
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    if harness_kind == "cmd":
        rc, out_b, err_b, timed_out = rt._run_isolated(
            harness_cmd, cwd=wt_path, timeout=timeout, shell=True, input_text=prompt, env=env
        )
    else:
        args_tpl, model_flag = (BUILD_HARNESSES if table is None else table)[harness_kind]
        args = [part.replace("{prompt}", prompt) for part in args_tpl]
        if model:
            args += [model_flag, model]
        rc, out_b, err_b, timed_out = rt._run_isolated(
            args, cwd=wt_path, timeout=timeout, shell=False, env=env
        )
    out_s = out_b.decode("utf-8", "replace")
    err_s = err_b.decode("utf-8", "replace")
    return rc, out_s, err_s, timed_out


def _failure_diagnostics(rt, wt_project, verify_summary, slop_failures, builder_rc, builder_err, timed_out, timeout):
    parts = []
    if timed_out:
        parts.append("Builder timed out after %ds." % timeout)
    elif builder_rc not in (0, None):
        parts.append("Builder exited with code %s:\n%s" % (builder_rc, (builder_err or "")[-2000:]))
    if verify_summary and not verify_summary.get("passed"):
        for st in verify_summary.get("stages", []):
            if str(st.get("result", "")).startswith("Verified: fail"):
                log_rel = st.get("log") or ""
                log_tail = rt.read(wt_project.path(log_rel))[-2500:] if log_rel else ""
                parts.append("Stage checks.%s failed (%s):\n%s" % (st.get("stage"), st.get("result"), log_tail))
    if slop_failures:
        parts.append("Slop filter strict failures:\n" + "\n".join(slop_failures[:20]))
    return "\n\n".join(parts).strip()


def _create_pr(project, branch, item_meta, summary_note):
    ok_push = subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=project.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if ok_push.returncode != 0:
        return None, "git push origin %s failed: %s" % (
            branch, ok_push.stderr.decode("utf-8", "replace").strip()[:240]
        )
    title = "%s: %s" % (item_meta["id"], item_meta.get("title") or item_meta["id"])
    body = "Work-Item: %s\nTier: %s\n\n%s" % (
        item_meta["id"], item_meta.get("tier") or "2", summary_note
    )
    if shutil.which("gh"):
        pr = subprocess.run(
            ["gh", "pr", "create", "--head", branch, "--title", title, "--body", body],
            cwd=project.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if pr.returncode == 0:
            return pr.stdout.decode("utf-8", "replace").strip(), None
        return None, pr.stderr.decode("utf-8", "replace").strip()[:240]
    if shutil.which("glab"):
        mr = subprocess.run(
            ["glab", "mr", "create", "--source-branch", branch, "--title", title, "--description", body, "--yes"],
            cwd=project.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if mr.returncode == 0:
            return mr.stdout.decode("utf-8", "replace").strip(), None
        return None, mr.stderr.decode("utf-8", "replace").strip()[:240]
    return None, "pushed branch %s to origin, but neither gh nor glab CLI is installed" % branch


def select_waves_preview(rt, project, claims_mod, view_mod, allowed_tiers, workers, max_items, sync_refs=False):
    par = claims_mod.parallel(project, rt, view_mod, sync_refs=sync_refs)
    by_id = dict((c["id"], c) for c in par.get("candidates", []))
    waves = []
    count = 0
    for grp in par.get("groups", []):
        filtered = [iid for iid in grp if (by_id.get(iid, {}).get("tier") or "2") in allowed_tiers]
        for start in range(0, len(filtered), workers):
            chunk = filtered[start:start + workers]
            if max_items > 0:
                chunk = chunk[:max(0, max_items - count)]
            if chunk:
                waves.append(chunk)
                count += len(chunk)
            if max_items > 0 and count >= max_items:
                break
        if max_items > 0 and count >= max_items:
            break
    skipped_t1 = []
    for pf in par.get("plan_first", []):
        t = str(pf.get("tier") or "2")
        if t == "1":
            skipped_t1.append(pf["id"])
        elif t in allowed_tiers and (max_items <= 0 or count < max_items):
            waves.append([pf["id"]])
            count += 1
    return {
        "waves": waves,
        "conflicts": par.get("conflicts", []),
        "skipped_tier1_unplanned": skipped_t1,
    }


def run_dispatch(rt, project, opts):
    """Execute conflict-free waves of Ready items across up to `opts.workers` isolated worktrees."""
    claims_mod = rt.runtime_module("claims")
    view_mod = rt.runtime_module("view")
    finish_mod = rt.runtime_module("finish")
    slop_mod = rt.runtime_module("slop")

    if not claims_mod.common_dir(project):
        return {"error": "not a git repository"}, 2

    workers = max(1, int(getattr(opts, "workers", 1) or 1))
    max_items = max(0, int(getattr(opts, "max_items", 0) or 0))
    max_retries = max(0, int(getattr(opts, "max_retries", 1) or 1))
    timeout = max(5, int(getattr(opts, "timeout", 1800) or 1800))
    sync_refs = bool(getattr(opts, "sync_refs", False))
    dry_run = bool(getattr(opts, "dry_run", False))
    pr_mode = bool(getattr(opts, "pr", False))
    no_merge = bool(getattr(opts, "no_merge", False))

    allowed_tiers = set(
        s.strip() for s in str(getattr(opts, "tier", "2,3") or "2,3").split(",") if s.strip() in ("1", "2", "3")
    )
    if not allowed_tiers:
        return {"error": "--tier must contain at least one of 1, 2, 3"}, 2

    if dry_run:
        preview = select_waves_preview(
            rt, project, claims_mod, view_mod, allowed_tiers, workers, max_items, sync_refs=sync_refs
        )
        preview["dry_run"] = True
        preview["workers"] = workers
        preview["allowed_tiers"] = sorted(allowed_tiers)
        return preview, 0

    by_spec = getattr(opts, "by", None) or ""
    build_table = _build_table(rt, project)
    broken = (lambda spec: rt.broken_agent(project, spec)) if hasattr(rt, "broken_agent") else None
    parsed_builder, err = _validate_harness(by_spec, "builder", build_table, broken)
    if err:
        return {"error": err}, 2
    harness_kind, harness_cmd = parsed_builder
    builder_model = getattr(opts, "model", None) or ""
    agent_name = harness_kind if harness_kind != "cmd" else "cmd"
    model_name = builder_model or ("%s-default" % agent_name)

    reviewer_spec = getattr(opts, "reviewer", None) or ""
    if reviewer_spec:
        _, rev_err = _validate_harness(reviewer_spec, "reviewer", build_table, broken)
        if rev_err:
            return {"error": rev_err}, 2
    reviewer_model = getattr(opts, "reviewer_model", None) or ""

    run_started = time.time()
    run_stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    coord_lock = threading.RLock()
    wt_base = _worktree_base(project, claims_mod, getattr(opts, "worktree_root", None))
    os.makedirs(wt_base, exist_ok=True)

    auto_merge = _may_auto_merge(project, rt, pr_mode=pr_mode, no_merge=no_merge)
    # The human who started the run, recorded on every worker's claim (None when unknown).
    who = rt.person_identity(project, warn=not getattr(opts, "json", False)) \
        if hasattr(rt, "person_identity") else {"person": None}
    dispatched = []
    discovered_filed = []
    attempted_ids = set()
    waves_executed = []

    def execute_one(item_id, wave_index):
        started_item = time.time()
        worker_agent = "%s-w%d" % (agent_name, wave_index + 1)
        wt_path = os.path.join(wt_base, item_id)
        provisioned_aisdlc = False
        claim_rec = None
        try:
            with coord_lock:
                project.__init__(project.root)
                base_sha = project.git("rev-parse", "HEAD").strip()
                if os.path.exists(wt_path) and not os.path.exists(os.path.join(claims_mod.registry(project), item_id + ".json")):
                    subprocess.run(["git", "worktree", "remove", "--force", wt_path],
                                   cwd=project.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    shutil.rmtree(wt_path, ignore_errors=True)
                claim_rec, c_err = claims_mod.claim(
                    project, view_mod, item_id, worker_agent, worktree=wt_path,
                    base=base_sha, mark=False, sync_refs=sync_refs,
                    person=who.get("person"),
                )
                if c_err:
                    return {
                        "item": item_id, "ok": False, "status": "claim_failed",
                        "error": c_err, "seconds": round(time.time() - started_item, 2),
                    }

            branch = claim_rec["branch"]
            provisioned_aisdlc = _provision_worktree_kit(project, wt_path)
            wt_project = rt.Project(wt_path)
            merged_map = shards.merged_items(wt_project)
            item_meta = dict(merged_map.get(item_id) or {"id": item_id, "title": item_id, "tier": "2", "type": "feat"})
            if not item_meta.get("effort"):
                eff_val, _ = rt.choice(rt.labelled(wt_project.charter, "Default effort mode"), rt.EFFORT)
                item_meta["effort"] = eff_val or "Normal"

            verified_ok = False
            last_diag = ""
            last_stdout = ""
            attempts_used = 0
            verify_run_id = ""
            slop_strict = slop_mod.mode(wt_project, rt.labelled) == "strict"

            for attempt in range(1, max_retries + 2):
                attempts_used = attempt
                prompt = _build_prompt(rt, wt_project, item_meta, attempt=attempt, failure_report=last_diag)
                rc, out_s, err_s, timed_out = _run_builder_turn(
                    rt, harness_kind, harness_cmd, builder_model, prompt, wt_path, item_meta, attempt, timeout,
                    table=build_table,
                )
                last_stdout = out_s
                wt_project.__init__(wt_path)
                changed_prod = _changed_non_record_files(wt_project, base_sha)
                if not changed_prod and rc == 0 and not timed_out:
                    last_diag = "Builder exited 0 without modifying or adding any product/test files."
                    continue

                v_summary, _ = rt.verify(wt_project, None, timeout, item=item_id)
                verify_run_id = v_summary.get("run") or ""
                slop_failures = []
                if slop_strict:
                    prose_files = slop_mod.changed_prose(wt_path) or []
                    s_results, _ = slop_mod.scan_paths(prose_files, wt_path)
                    for rel_f, found_f, words_f in s_results:
                        if slop_mod.verdict(found_f, words_f)[0]:
                            slop_failures.append("%s (%d tells)" % (rel_f, len(found_f)))

                if not timed_out and rc == 0 and v_summary.get("passed") and not slop_failures:
                    verified_ok = True
                    break

                last_diag = _failure_diagnostics(
                    rt, wt_project, v_summary, slop_failures, rc, err_s or out_s, timed_out, timeout
                )

            _copy_evidence_back(wt_path, project)

            if not verified_ok:
                _cleanup_worktree_before_release(wt_path, provisioned_aisdlc)
                with coord_lock:
                    claims_mod.release(project, item_id, remove_worktree=True, force=True, sync_refs=sync_refs)
                return {
                    "item": item_id, "ok": False, "status": "verify_failed", "branch": branch,
                    "attempts": attempts_used, "verify_run": verify_run_id,
                    "error": last_diag[:1500] or "verification failed",
                    "seconds": round(time.time() - started_item, 2),
                }

            trailers_text = "\n".join([
                "Work-Item: %s" % item_id,
                "Agent: %s" % agent_name,
                "Model: %s" % model_name,
            ])
            commit_type = item_meta.get("type") or "feat"
            if commit_type == "defect":
                commit_type = "fix"
            _stage_and_commit(
                wt_path,
                "%s(%s): %s" % (commit_type, item_id, item_meta.get("title") or item_id),
                trailers_text,
            )
            wt_project.__init__(wt_path)
            if not rt.item_commits(wt_project, item_id):
                # Builder committed without Work-Item trailer; amend HEAD trailer safely on private worker branch.
                head_msg = wt_project.git("log", "-1", "--format=%B").rstrip()
                subprocess.run(
                    ["git", "commit", "--amend", "-q", "-m", head_msg + "\n\n" + trailers_text],
                    cwd=wt_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                wt_project.__init__(wt_path)

            # Optional independent review
            _, ind_tiers, _ = rt.independent_review_policy(wt_project.charter, wt_project.profile)
            tier = str(item_meta.get("tier") or "2")
            eff_rev = reviewer_spec
            if not eff_rev and tier in ind_tiers:
                pref = (wt_project.profile or {}).get("preferred_reviewer") or ""
                if pref and pref != agent_name and shutil.which(pref):
                    eff_rev = pref

            review_note = "self-reviewed against %s scope and charter checks" % item_id
            if eff_rev:
                rev_role = item_meta.get("owner") or "qa"
                if not os.path.isfile(wt_project.path(os.path.join(wt_project.docs, "roles", rev_role + ".md"))):
                    rev_role = "qa"
                rev_rel, rev_rec, rev_err = rt.review(
                    wt_project, item_id, rev_role, eff_rev,
                    model=reviewer_model or None, stage="ship", timeout=timeout,
                )
                if rev_err:
                    _cleanup_worktree_before_release(wt_path, provisioned_aisdlc)
                    with coord_lock:
                        claims_mod.release(project, item_id, remove_worktree=True, force=True, sync_refs=sync_refs)
                    return {
                        "item": item_id, "ok": False, "status": "review_failed", "branch": branch,
                        "attempts": attempts_used, "error": rev_err,
                        "seconds": round(time.time() - started_item, 2),
                    }
                if rev_rec and rev_rec.get("verdict") == "Block":
                    _stage_and_commit(wt_path, "docs(%s): record blocking review" % item_id, trailers_text)
                    _cleanup_worktree_before_release(wt_path, provisioned_aisdlc)
                    with coord_lock:
                        claims_mod.release(project, item_id, remove_worktree=True, force=True, sync_refs=sync_refs)
                    return {
                        "item": item_id, "ok": False, "status": "review_blocked", "branch": branch,
                        "attempts": attempts_used, "review": rev_rel,
                        "error": "reviewer returned Verdict: Block",
                        "seconds": round(time.time() - started_item, 2),
                    }
                _stage_and_commit(wt_path, "docs(%s): record %s review" % (item_id, rev_role), trailers_text)
                review_note = "[%s](reviews/%s) (%s)" % (
                    os.path.basename(rev_rel), os.path.basename(rev_rel), rev_rec.get("verdict", "Pass")
                )
                wt_project.__init__(wt_path)

            summary_note, discovered_list = _extract_builder_notes(last_stdout, item_meta.get("title") or item_id)
            notes = {
                "why": summary_note,
                "not_done": "nothing deferred",
                "discovered": "; ".join(discovered_list) if discovered_list else "nothing",
                "decisions": "none",
                "assumptions": "none",
                "plan": summary_note,
                "reviews": review_note,
            }
            fin_lines, fin_code = finish_mod.finish(rt, wt_project, item_id, notes=notes)
            if fin_code != 0:
                _cleanup_worktree_before_release(wt_path, provisioned_aisdlc)
                with coord_lock:
                    claims_mod.release(project, item_id, remove_worktree=True, force=True, sync_refs=sync_refs)
                return {
                    "item": item_id, "ok": False, "status": "finish_blocked", "branch": branch,
                    "attempts": attempts_used, "error": "\n".join(fin_lines),
                    "seconds": round(time.time() - started_item, 2),
                }

            _stage_and_commit(wt_path, "chore(%s): close work item records" % item_id, trailers_text)
            wt_project.__init__(wt_path)
            closed_item = shards.merged_items(wt_project).get(item_id) or {}
            final_status = closed_item.get("status") or ("Parked" if tier == "1" else "Done")
            head_sha = wt_project.git("rev-parse", "HEAD").strip()

            _cleanup_worktree_before_release(wt_path, provisioned_aisdlc)
            with coord_lock:
                claims_mod.release(project, item_id, remove_worktree=True, force=True, sync_refs=sync_refs)

            return {
                "item": item_id,
                "ok": True,
                "status": final_status,
                "tier": tier,
                "branch": branch,
                "commit": head_sha,
                "attempts": attempts_used,
                "verify_run": verify_run_id,
                "summary": summary_note,
                "discovered": discovered_list,
                "seconds": round(time.time() - started_item, 2),
            }
        except Exception as exc:
            if claim_rec and os.path.isdir(wt_path):
                _cleanup_worktree_before_release(wt_path, provisioned_aisdlc)
            if claim_rec:
                with coord_lock:
                    claims_mod.release(project, item_id, remove_worktree=True, force=True, sync_refs=sync_refs)
            return {
                "item": item_id, "ok": False, "status": "exception",
                "error": str(exc), "seconds": round(time.time() - started_item, 2),
            }

    while True:
        if max_items > 0 and len(dispatched) >= max_items:
            break
        project.__init__(project.root)
        par = claims_mod.parallel(project, rt, view_mod, sync_refs=sync_refs)
        by_id = dict((c["id"], c) for c in par.get("candidates", []))
        wave = []
        for grp in par.get("groups", []):
            eligible = [
                iid for iid in grp
                if iid not in attempted_ids and (by_id.get(iid, {}).get("tier") or "2") in allowed_tiers
            ]
            if eligible:
                cap = workers if max_items <= 0 else min(workers, max_items - len(dispatched))
                wave = eligible[:cap]
                break
        if not wave:
            for pf in par.get("plan_first", []):
                iid = pf["id"]
                t = str(pf.get("tier") or "2")
                if iid not in attempted_ids and t != "1" and t in allowed_tiers:
                    wave = [iid]
                    break
        if not wave:
            break

        for iid in wave:
            attempted_ids.add(iid)
        waves_executed.append(list(wave))

        wave_results = []
        if len(wave) == 1 or workers == 1:
            wave_results.append(execute_one(wave[0], 0))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(wave))) as pool:
                futs = [pool.submit(execute_one, iid, idx) for idx, iid in enumerate(wave)]
                for fut in futs:
                    wave_results.append(fut.result())

        # Coordinator wave join: merge Done Tier 2/3 branches or open PRs, and file discovered defects.
        project.__init__(project.root)
        for res in wave_results:
            if res.get("ok"):
                item_meta_now = shards.merged_items(project).get(res["item"]) or {"id": res["item"], "tier": res.get("tier", "2")}
                if pr_mode:
                    pr_url, pr_err = _create_pr(project, res["branch"], item_meta_now, res.get("summary", ""))
                    res["pr_url"] = pr_url or ""
                    if pr_err:
                        res["pr_error"] = pr_err
                elif auto_merge and res.get("status") == "Done" and res.get("tier") != "1":
                    m_proc = subprocess.run(
                        ["git", "merge", "--no-edit", "-q", res["branch"]],
                        cwd=project.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    if m_proc.returncode == 0:
                        res["merged"] = True
                        subprocess.run(["git", "branch", "-d", res["branch"]],
                                       cwd=project.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        subprocess.run(["git", "merge", "--abort"],
                                       cwd=project.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        res["merged"] = False
                        res["merge_error"] = m_proc.stderr.decode("utf-8", "replace").strip()[:240]
                else:
                    res["merged"] = False

                for disc_title in res.get("discovered") or ():
                    project.__init__(project.root)
                    alloc, a_err = claims_mod.next_id(project, kind="item", sync_refs=sync_refs)
                    if not a_err and alloc:
                        new_id = alloc["id"]
                        disc_status, disc_reason = rt.resolve_discovered_status(project, new_id, "defect", "2")
                        saved_d = shards.save_item(project, {
                            "id": new_id,
                            "title": disc_title[:160],
                            "type": "defect",
                            "tier": "2",
                            "owner": "qa",
                            "status": disc_status,
                            "waiting_on": "backlog owner" if disc_status == "Parked" else "",
                            "park_reason": ("Discovered during %s: %s" % (res["item"], disc_reason)) if disc_status == "Parked" else "",
                        })
                        if auto_merge:
                            shard_file = os.path.join(shards.items_dir(project), saved_d["id"] + ".json")
                            subprocess.run(["git", "add", "--", shard_file], cwd=project.root,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            disc_trailers = "\n".join([
                                "Work-Item: %s" % saved_d["id"],
                                "Agent: %s" % agent_name,
                                "Model: %s" % model_name,
                            ])
                            subprocess.run(
                                ["git", "commit", "-q", "-m",
                                 "chore(%s): file discovered defect from %s" % (saved_d["id"], res["item"]),
                                 "-m", disc_trailers],
                                cwd=project.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            )
                        discovered_filed.append(saved_d["id"])
            dispatched.append(res)

        # If branches were not merged into HEAD, items remain Ready in HEAD so stop after one pass over unmerged items.
        if not auto_merge and not any(r.get("merged") for r in wave_results):
            continue

    project.__init__(project.root)
    passed_count = sum(1 for r in dispatched if r.get("ok"))
    failed_count = len(dispatched) - passed_count
    report = {
        "run_id": run_stamp,
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "builder": by_spec,
        "model": model_name,
        "reviewer": reviewer_spec or "",
        "workers": workers,
        "allowed_tiers": sorted(allowed_tiers),
        "auto_merge": auto_merge,
        "pr_mode": pr_mode,
        "waves": waves_executed,
        "items": dispatched,
        "passed": passed_count,
        "failed": failed_count,
        "discovered_filed": discovered_filed,
        "seconds": round(time.time() - run_started, 2),
    }
    report["telemetry_path"] = _save_dispatch_run(rt, project, report)
    return report, (0 if failed_count == 0 else 1)


def format_dispatch_report(report):
    if report.get("dry_run"):
        lines = [
            "dispatch (dry run): %d wave(s), workers=%d, tiers=%s"
            % (len(report.get("waves", [])), report.get("workers", 1), ",".join(report.get("allowed_tiers", [])))
        ]
        for idx, w in enumerate(report.get("waves", []), 1):
            lines.append("  wave %d: %s" % (idx, ", ".join(w)))
        if report.get("skipped_tier1_unplanned"):
            lines.append("  skipped Tier 1 without plan: %s" % ", ".join(report["skipped_tier1_unplanned"]))
        if not report.get("waves"):
            lines.append("  no eligible Ready items to dispatch")
        return "\n".join(lines)

    lines = [
        "dispatch %s: %d passed, %d failed in %.1fs (waves=%d, workers=%d)"
        % (
            report.get("run_id", ""),
            report.get("passed", 0),
            report.get("failed", 0),
            report.get("seconds", 0.0),
            len(report.get("waves", [])),
            report.get("workers", 1),
        )
    ]
    for r in report.get("items", []):
        if r.get("ok"):
            m_tag = "merged" if r.get("merged") else ("PR " + r["pr_url"] if r.get("pr_url") else "branch " + r.get("branch", ""))
            lines.append("  PASS  %-10s %-8s attempts=%d  %s" % (
                r["item"], r.get("status", "Done"), r.get("attempts", 1), m_tag
            ))
        else:
            lines.append("  FAIL  %-10s %-14s %s" % (
                r["item"], r.get("status", "failed"), (r.get("error") or "").splitlines()[0][:120]
            ))
    if report.get("discovered_filed"):
        lines.append("  discovered defects filed (Parked): %s" % ", ".join(report["discovered_filed"]))
    if report.get("telemetry_path"):
        lines.append("  telemetry: %s" % report["telemetry_path"])
    return "\n".join(lines)

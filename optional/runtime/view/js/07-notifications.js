  // ---------------------------------------------------------------- notifications
  // A live redraw diffs the old model against the new one; what changed lands here and
  // in the bell. Only high-signal changes also raise a toast.
  var NOTES = [];
  try { NOTES = JSON.parse(sessionStorage.getItem("nuhut-notes") || "[]") || []; } catch (e) { NOTES = []; }
  function saveNotes() {
    try { sessionStorage.setItem("nuhut-notes", JSON.stringify(NOTES.slice(0, 100))); } catch (e) {}
  }
  function pushNote(note, toast) {
    if (toast) AB_ANNOUNCE = note.title;
    note.t = new Date().toISOString();
    note.seen = false;
    NOTES.unshift(note);
    if (NOTES.length > 100) NOTES.length = 100;
    saveNotes();
    if (toast) showToast(note.title, note.detail || "");
  }
  function unseenNotes() {
    return NOTES.filter(function (n) { return !n.seen; }).length;
  }
  function lastStageResults(runs) {
    var last = (runs || [])[runs.length - 1];
    if (!last) return null;
    var fails = last.stages.filter(function (s) { return /fail/i.test(s.result || ""); }).map(function (s) { return s.stage; });
    return { run: last, fails: fails };
  }
  function diffModels(prev, next) {
    if (!prev || !next) return;
    var prevItems = prev.items || {}, nextItems = next.items || {};
    Object.keys(nextItems).forEach(function (id) {
      var a = prevItems[id], b = nextItems[id];
      if (!a) {
        pushNote({ level: "info", title: id + " added", detail: b.title || "", item: id });
        return;
      }
      if (a.column !== b.column) {
        pushNote({ level: b.column === "Blocked" ? "warn" : (b.column === "Done" ? "ok" : "info"),
          title: id + " moved " + a.column + " → " + b.column, detail: b.title || "", item: id },
          b.column === "Blocked" || b.column === "Parked");
      }
      var seenKinds = {};
      (a.thread || []).forEach(function (ev) { seenKinds[ev.kind + "|" + (ev.sha || ev.path || ev.time || ev.title || ev.date)] = 1; });
      (b.thread || []).forEach(function (ev) {
        var key = ev.kind + "|" + (ev.sha || ev.path || ev.time || ev.title || ev.date);
        if (seenKinds[key] || ev.kind === "frame" || ev.kind === "gate") return;
        pushNote({ level: ev.kind === "verify" && (ev.stages || []).some(function (s) { return /fail/i.test(s.result || ""); }) ? "bad" : "info",
          title: id + " · " + threadKindLabel(ev.kind), detail: ev.subject || ev.title || "", item: id });
      });
    });
    var pr = (prev.evidence || []).length ? prev.evidence[prev.evidence.length - 1].folder : "";
    var lr = lastStageResults(next.evidence || []);
    if (lr && lr.run.folder !== pr) {
      pushNote({ level: lr.fails.length ? "bad" : "ok", route: "dashboard/tests",
        title: lr.fails.length ? "Verify failed: " + lr.fails.join(", ") : "Verify passed",
        detail: "Run " + lr.run.folder, log: { kind: "evidence", id: lr.run.folder, stage: lr.fails[0] || (lr.run.stages[0] || {}).stage } }, true);
    }
    var pf = (prev.alerts || []).filter(function (a) { return a.level === "fail"; }).length;
    var nf = (next.alerts || []).filter(function (a) { return a.level === "fail"; }).length;
    if (nf > pf) pushNote({ level: "bad", route: "dashboard", title: "Doctor: " + nf + " failing check(s)", detail: "was " + pf }, true);
    else if (nf < pf) pushNote({ level: "ok", route: "dashboard", title: "Doctor: failing checks down to " + nf, detail: "was " + pf });
  }
  function threadKindLabel(kind) {
    return ({ frame: "framed", plan: "plan", design_review: "design review", ship_review: "ship review",
      commit: "commit", verify: "verify run", gate: "human gate", worklog: "worklog" })[kind] || kind.replace(/_/g, " ");
  }
  function openNote(n) {
    n.seen = true;
    saveNotes();
    closeNotes();
    if (n.log) openLogDrawer(n.log);
    else if (n.item && ITEMS[n.item]) { markSeen(n.item); openItemDrawer(n.item); }
    else if (n.route) go(n.route);
    paintActivityBar();
  }
  // Notifications live in the side panel's Activity tab; the bell and `n` open it.
  function closeNotes() {}
  function toggleNotes() {
    if (PANEL.open && PANEL.tab === "activity") closeDrawer();
    else showPanel("activity", { quiet: !wide() ? false : true });
  }
  function renderActivityTab() {
    var box = el("div", { cls: "ptab-body" });
    box.appendChild(el("div", { cls: "ptab-head" }, [
      el("strong", { text: NOTES.length ? plural(NOTES.length, "notification") : "Notifications" }),
      NOTES.length ? el("button", { cls: "btn", style: "font-size: 12px; padding: 2px 8px;", text: "Mark all read", on: { click: function () {
        NOTES.forEach(function (n) { n.seen = true; });
        saveNotes(); paintActivityBar(); renderPanel({ quiet: true });
      } } }) : null
    ]));
    if (!NOTES.length) {
      box.appendChild(el("div", { cls: "insp-empty", text: LIVE
        ? "Nothing new yet. Changes to records, commits, verify runs and doctor findings appear here while the page is open."
        : "Notifications need the live page: run python3 .ai-sdlc/bin/sdlc.py view --serve" }));
    }
    NOTES.forEach(function (n) {
      var row = el("div", { cls: "note-row" + (n.seen ? "" : " unseen"), on: { click: function () { openNote(n); } } }, [
        el("span", { cls: "note-ic " + (n.level || "info"), "aria-hidden": "true" }),
        el("div", { style: "min-width: 0; flex: 1;" }, [
          el("div", { text: n.title }),
          n.detail ? el("div", { cls: "muted", style: "font-weight: 400; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;", text: n.detail }) : null
        ]),
        el("span", { cls: "muted", style: "font-weight: 400; font-size: 11.5px;", text: (n.t || "").slice(11, 16) })
      ]);
      makeInteractive(row, function () { openNote(n); }, n.title);
      box.appendChild(row);
    });
    return box;
  }

  // Everything that would otherwise be a banner above some page: doctor failures, kit
  // repairs, setup warnings, statuses the board cannot place, unsaved static edits.
  function unmappedStatuses() {
    var out = {};
    (M.order || []).forEach(function (id) { var it = ITEMS[id]; if (it.column === "Other") out[it.status || "(blank)"] = (out[it.status || "(blank)"] || 0) + 1; });
    return out;
  }
  function issueList() {
    var out = typeof lensIssues === "function" ? lensIssues().filter(function (x) { return x.level === "fail"; }) : [], kit = M.kit || {};
    (M.alerts || []).filter(function (a) { return a.level === "fail"; }).forEach(function (a) {
      out.push({ level: "fail", group: "Blocks shipping", title: firstSentence(a.message), detail: a.check + (a.where ? " · " + a.where : ""), open: function () { openFindingDrawer(a); } });
    });
    var stagedCmd = typeof buildStagedKitCommand === "function" ? buildStagedKitCommand() : "";
    if (stagedCmd) out.push({ level: "warn", group: "Kit setup", title: "Unsaved kit changes (static page)", detail: stagedCmd, open: function () { copyCmd(stagedCmd, "Save kit changes"); } });
    if (kit.reviewer_warning) out.push({ level: "warn", group: "Kit setup", title: kit.reviewer_warning, detail: "Kit settings", open: function () { go("project/kit"); } });
    (kit.fixable || []).filter(function (f) { return f.level !== "info"; }).forEach(function (f) {
      out.push({ level: f.level === "fail" ? "fail" : "warn", group: "Kit setup", title: f.title || f.message || f.id, detail: "Repair: sdlc.py fix " + f.id, open: function () { go("project/kit"); } });
    });
    var um = unmappedStatuses(), keys = Object.keys(um);
    if (keys.length) {
      var n = keys.reduce(function (a, k) { return a + um[k]; }, 0);
      out.push({ level: "warn", group: "Records", title: plural(n, "item") + " have statuses the board has no column for",
        detail: keys.sort(function (a, b) { return um[b] - um[a]; }).slice(0, 4).map(function (k) { return k + " (" + um[k] + ")"; }).join(", "), open: function () { go("board"); } });
    }
    (M.unread || []).forEach(function (x) { out.push({ level: "warn", group: "Records", title: "Could not read " + x.path, detail: x.reason, open: function () { go("docs"); } }); });
    if (typeof lensIssues === "function") lensIssues().filter(function (x) { return x.level !== "fail"; }).forEach(function (x) { out.push(x); });
    groupFindings().forEach(function (g) {
      if (!g.warn) return;
      out.push({ level: "info", group: "Doctor warnings", title: g.check + " · " + plural(g.warn, "warning"), detail: firstSentence(g.items[0].message),
        open: function () { go("dashboard/doctor/" + encodeURIComponent(g.check)); } });
    });
    return out;
  }
  function renderIssuesTab() {
    var box = el("div", { cls: "ptab-body" }), list = issueList(), group = "";
    var real = list.filter(function (x) { return x.level !== "info"; }).length;
    box.appendChild(el("div", { cls: "ptab-head" }, [
      el("strong", { text: real ? plural(real, "issue") : "No issues" }),
      link("Doctor →", "dashboard/doctor", "")
    ]));
    if (!list.length) box.appendChild(el("div", { cls: "insp-empty", text: "Nothing to fix: no doctor failures, kit repairs or unreadable records." }));
    list.forEach(function (x) {
      if (x.group !== group) { box.appendChild(el("div", { cls: "feed-day", text: x.group })); group = x.group; }
      var row = el("div", { cls: "note-row", on: { click: x.open } }, [
        el("span", { cls: "note-ic " + (x.level === "fail" ? "bad" : (x.level === "warn" ? "warn" : "")), "aria-hidden": "true" }),
        el("div", { style: "min-width: 0; flex: 1;" }, [
          el("div", { text: x.title }),
          x.detail ? el("div", { cls: "muted", style: "font-weight: 400; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;", text: x.detail }) : null
        ])
      ]);
      makeInteractive(row, x.open, x.title);
      box.appendChild(row);
    });
    return box;
  }


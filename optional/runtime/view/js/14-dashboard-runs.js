  // ---------------------------------------------------------------- dashboard: runs
  var RUNS_STATE = { kind: "", failed: false, q: "" };
  function viewDashRuns() {
    tab("dashboard");
    var parts = location.hash.replace(/^#\/?/, "").split("/");
    var selKind = parts[2] || "", selId = decodeURIComponent(parts[3] || ""), selStage = decodeURIComponent(parts[4] || "");
    crumbs([["Dashboard", "dashboard"], ["Runs & logs"]]);
    var f = dashFacts(), all = allRunsList(f.ev, f.runs);
    dashHeader("Runs & logs", plural(all.length, "run") + ": verify runs and the commands run from this page, newest first.", [runVerifyBtn(), runDoctorBtn()]);
    var kinds = [];
    all.forEach(function (r) { if (kinds.indexOf(r.kind) < 0) kinds.push(r.kind); });
    var kindSel = el("select", { cls: "filter-select", "aria-label": "Run kind", on: { change: function () { RUNS_STATE.kind = kindSel.value; render(); } } },
      [el("option", { value: "", text: "All kinds" })].concat(kinds.map(function (k) { var o = el("option", { value: k, text: k }); if (RUNS_STATE.kind === k) o.selected = true; return o; })));
    var failBox = el("label", { style: "display: inline-flex; gap: 5px; align-items: center; font-size: 12.5px;" }, [
      el("input", { type: "checkbox", checked: RUNS_STATE.failed ? "checked" : null, on: { change: function (e) { RUNS_STATE.failed = e.target.checked; render(); } } }), "Failed only"]);
    var q = el("input", { type: "search", cls: "filter-input", placeholder: "Filter runs…", value: RUNS_STATE.q, "aria-label": "Filter runs",
      on: { input: function () { RUNS_STATE.q = q.value; fill(); } } });
    var list = el("div", { cls: "md-list", role: "list", "aria-label": "Runs" });
    var pane = el("div", { cls: "md-pane", "aria-live": "polite" });
    main.appendChild(el("div", { cls: "md" }, [
      el("div", { cls: "md-left" }, [el("div", { cls: "md-filters" }, [kindSel, failBox, q]), list]),
      pane
    ]));
    var selected = all.filter(function (r) { return r.log.kind === selKind && r.id === selId; })[0] || null;
    function fill() {
      list.textContent = "";
      var needle = RUNS_STATE.q.trim().toLowerCase(), day = "";
      var shown = all.filter(function (r) {
        return (!RUNS_STATE.kind || r.kind === RUNS_STATE.kind) && (!RUNS_STATE.failed || !r.ok) &&
          (!needle || (r.kind + " " + r.detail + " " + r.id).toLowerCase().indexOf(needle) >= 0);
      });
      shown.forEach(function (r) {
        var d = String(r.when).slice(0, 10);
        if (d !== day) { list.appendChild(el("div", { cls: "feed-day", text: d })); day = d; }
        list.appendChild(runRow(r, function () { location.replace("#/dashboard/runs/" + r.log.kind + "/" + encodeURIComponent(r.id)); }, selected && selected === r));
      });
      if (!shown.length) list.appendChild(el("p", { cls: "muted", style: "padding: 10px;", text: "No runs match." }));
    }
    fill();
    if (!selected) selected = all.filter(function (r) { return !r.ok; })[0] || all[0];
    if (!selected) { pane.appendChild(el("p", { cls: "muted", text: "No runs yet." })); return; }
    var log = { kind: selected.log.kind, id: selected.id, stage: selStage || selected.log.stage, title: selected.log.title };
    pane.appendChild(el("div", { cls: "md-pane-hd" }, [
      el("div", null, [el("strong", { text: selected.kind + " · " + String(selected.when).replace("T", " ").replace(/Z$/, "").slice(0, 16) }),
        el("div", { cls: "muted", style: "font-size: 12px;", text: (selected.ok ? "passed" : "failed") + " · " + selected.detail })]),
      el("button", { cls: "btn", text: "Open in panel", on: { click: function () { openLogDrawer(log); } } })
    ]));
    if (log.kind === "evidence") {
      var run = evidenceRun(log.id), chips = el("div", { style: "display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0;" });
      (run ? run.stages : []).forEach(function (s) {
        if (!/^Verified/.test(s.result || "")) return;
        var on = s.stage === log.stage;
        chips.appendChild(el("button", { cls: "stage-chip" + (on ? " on" : "") + (stageBad(s.result) ? " bad" : ""), "aria-pressed": on ? "true" : "false",
          text: (stageBad(s.result) ? "✗ " : "✓ ") + s.stage + (s.seconds ? " · " + fmtDur(s.seconds) : ""),
          on: { click: function () { location.replace("#/dashboard/runs/evidence/" + encodeURIComponent(log.id) + "/" + encodeURIComponent(s.stage)); } } }));
      });
      pane.appendChild(chips);
    }
    var pre = el("pre", { cls: "log-pre md-log", text: "Loading…" });
    pane.appendChild(pre);
    fetchLog(log, function (text, live) {
      pre.textContent = text === null ? (live ? "No log kept for this run." : "Logs are read from the live server. Run: python3 .ai-sdlc/bin/sdlc.py view --serve") : (text || "(empty)");
      if (text) pre.scrollTop = pre.scrollHeight;
    });
  }


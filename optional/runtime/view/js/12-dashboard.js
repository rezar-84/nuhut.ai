  // ---------------------------------------------------------------- dashboard
  // The overview answers "what needs me, and is the project healthy?" and summarises the
  // rest; every summary links to a full-width page that holds the whole list.
  var NEEDS_PAGE = 6, NEEDS_STEP = 10, NEEDS_UI = { filter: "all", limit: NEEDS_PAGE };
  function viewDashboard(section) {
    if (section === "tests") return viewDashTests();
    if (section === "runs") return viewDashRuns();
    if (section === "doctor") return viewDashDoctor();
    if (section === "parallel") return viewDashParallel();
    tab("dashboard");
    crumbs([["Dashboard"]]);
    var f = dashFacts(), lr = f.lr, ev = f.ev;
    dashHeader("Dashboard", "What needs a decision first, then how the project is moving.", [runVerifyBtn(), runDoctorBtn()]);
    var grid = el("div", { cls: "cockpit" });
    main.appendChild(grid);

    // Needs you: one row per decision, failures before waiting items. Doctor failures of
    // one rule fold into a single row, and the list pages so it never buries the metrics.
    var entries = [];
    function need(tone, kind, title, detail, onOpen, aside) {
      entries.push({ tone: tone, kind: kind, title: title, detail: detail, open: onOpen, aside: aside });
    }
    if (lr && lr.fails.length) {
      need("bad", "Verify", "Latest verify run failed " + lr.fails.join(", "), "Run " + lr.run.folder + (lr.run.dirty ? " · uncommitted changes" : ""),
        function () { openLogDrawer({ kind: "evidence", id: lr.run.folder, stage: lr.fails[0], title: "Verify " + lr.run.folder }); }, "Read log");
    }
    var failsBy = {}, failOrder = [];
    f.fails.forEach(function (a) {
      if (!failsBy[a.check]) { failsBy[a.check] = []; failOrder.push(a.check); }
      failsBy[a.check].push(a);
    });
    failOrder.forEach(function (check) {
      var list = failsBy[check];
      if (list.length > 2) {
        need("bad", "Doctor", plural(list.length, "failure") + ": " + firstSentence(list[0].message), check + " · " + list.slice(0, 3).map(function (a) { return a.where; }).filter(Boolean).join(", ") + (list.length > 3 ? " …" : ""),
          function () { go("dashboard/doctor/" + encodeURIComponent(check)); }, "Open all");
      } else list.forEach(function (a) {
        need("bad", "Doctor", firstSentence(a.message), a.check + (a.where ? " · " + a.where : ""), function () { openFindingDrawer(a); }, "How to fix");
      });
    });
    // Build and security failures from the Project lens, once it has loaded.
    lensIssues().filter(function (x) { return x.level === "fail"; }).forEach(function (x) {
      need("bad", x.group, x.title, x.detail, x.open, "Open");
    });
    f.waitingIds.forEach(function (id) {
      var it = ITEMS[id], x = it.extra || {};
      var who = x["Waiting on whom"] || x["Who can unblock"] || x["Unblocked by"] || "";
      need("warn", it.column, id + " " + clip(it.title || "", 80), (who ? "Waiting on " + who : "No one is named to unblock it") + (x["Decision needed"] ? " · " + x["Decision needed"] : ""),
        function () { markSeen(id); openItemDrawer(id); }, x.Since ? "since " + x.Since : "");
    });
    var needsBox = el("div");
    var nFail = entries.filter(function (e) { return e.tone === "bad"; }).length, nWait = entries.length - nFail;
    if (!entries.length) {
      needsBox.appendChild(el("div", { cls: "needs" }, [el("div", { cls: "needs-clear", text: "Nothing needs you. Verify passed, doctor has no failures and nothing is blocked." })]));
    } else {
      if (NEEDS_UI.filter === "bad" && !nFail || NEEDS_UI.filter === "warn" && !nWait) NEEDS_UI.filter = "all";
      var needs = el("div", { cls: "needs", role: "list", "aria-label": "Needs you" });
      var more = el("div", { cls: "needs-more" });
      var renderNeeds = function () {
        needs.textContent = ""; more.textContent = "";
        var shown = entries.filter(function (e) { return NEEDS_UI.filter === "all" || e.tone === NEEDS_UI.filter; });
        shown.slice(0, NEEDS_UI.limit).forEach(function (e) {
          var r = el("div", { cls: "needs-row " + e.tone, role: "listitem", "data-need": "1" }, [
            el("span", { cls: "nr-kind", text: e.kind }),
            el("div", { cls: "nr-what" }, [el("div", { text: e.title }), e.detail ? el("div", { text: e.detail }) : null]),
            e.aside ? el("span", { cls: "nr-aside", text: e.aside }) : null
          ]);
          r.addEventListener("click", e.open);
          makeInteractive(r, e.open, e.kind + ": " + e.title);
          needs.appendChild(r);
        });
        needs.classList.toggle("scrolls", NEEDS_UI.limit > NEEDS_PAGE);
        var left = shown.length - Math.min(shown.length, NEEDS_UI.limit);
        if (left) {
          var btn = el("button", { type: "button", cls: "btn", text: "Show " + Math.min(left, NEEDS_STEP) + " more" });
          btn.addEventListener("click", function () { NEEDS_UI.limit += NEEDS_STEP; renderNeeds(); });
          more.appendChild(btn);
          if (left > NEEDS_STEP) {
            var all = el("button", { type: "button", cls: "btn", text: "Show all " + shown.length });
            all.addEventListener("click", function () { NEEDS_UI.limit = shown.length; renderNeeds(); });
            more.appendChild(all);
          }
        }
        if (NEEDS_UI.limit > NEEDS_PAGE) {
          var less = el("button", { type: "button", cls: "btn", text: "Show fewer" });
          less.addEventListener("click", function () { NEEDS_UI.limit = NEEDS_PAGE; renderNeeds(); needs.scrollTop = 0; });
          more.appendChild(less);
        }
        more.appendChild(el("span", { cls: "muted", text: "Showing " + Math.min(shown.length, NEEDS_UI.limit) + " of " + shown.length }));
        more.hidden = shown.length <= NEEDS_PAGE;
      };
      if (nFail && nWait) {
        var seg = el("div", { cls: "seg-group needs-filter", role: "group", "aria-label": "Show" });
        [["all", "All " + entries.length], ["bad", "Failing " + nFail], ["warn", "Waiting " + nWait]].forEach(function (o) {
          var b = el("button", { type: "button", cls: "seg-btn" + (NEEDS_UI.filter === o[0] ? " active" : ""), "aria-pressed": String(NEEDS_UI.filter === o[0]), text: o[1] });
          b.addEventListener("click", function () {
            NEEDS_UI.filter = o[0]; NEEDS_UI.limit = NEEDS_PAGE;
            [].forEach.call(seg.children, function (c) { c.classList.toggle("active", c === b); c.setAttribute("aria-pressed", String(c === b)); });
            renderNeeds();
          });
          seg.appendChild(b);
        });
        needsBox.appendChild(seg);
      }
      needsBox.appendChild(needs);
      needsBox.appendChild(more);
      renderNeeds();
    }
    grid.appendChild(ckCard("needs", "Needs you" + (entries.length ? " (" + entries.length + ")" : ""), null, [needsBox], "wide"));

    // Health
    var passSeries = ev.map(function (r) {
      var rs = r.stages.filter(function (s) { return /^Verified/.test(s.result || ""); });
      return rs.length ? Math.round(100 * rs.filter(function (s) { return stageOk(s.result); }).length / rs.length) : 0;
    });
    var cleanRuns = ev.filter(function (r) { return !r.stages.some(function (s) { return stageBad(s.result); }); }).length;
    var flowS = (M.flow && M.flow.series) || {};
    var lim = (M.kit && M.kit.constraints && +M.kit.constraints.wip_limit) || 0;
    var blockers = f.fails.length + (lr && lr.fails.length ? 1 : 0);
    var kpis = el("div", { cls: "kpis secondary" }, [
      kpi("Shippable", blockers ? "no" : "yes", blockers ? "bad" : "ok", null,
        "No failing doctor finding and a passing latest verify run", f.fails.length ? "dashboard/doctor" : "dashboard/tests",
        blockers ? [f.fails.length ? plural(f.fails.length, "doctor failure") : "", lr && lr.fails.length ? "verify failing" : ""].filter(Boolean).join(" · ") : "nothing blocks a ship"),
      kpi("Last verify", lr ? (lr.fails.length ? "fail" : "pass") : "none", lr ? (lr.fails.length ? "bad" : "ok") : "",
        sparkline(passSeries, { min: 0, max: 100, color: "var(--accent)", label: "Share of stages passing per run, last " + passSeries.length + " runs" }),
        "Latest run's result; the line is the share of stages passing in each run", "dashboard/tests",
        ev.length ? cleanRuns + " of " + ev.length + " runs clean" : "no runs yet"),
      kpi("Done", String(f.counts.Done || 0), "", sparkline(flowS.Done || [], { min: 0, label: "Done items over committed days" }),
        "Items in Done; the line is Done over committed days", "board", "throughput over time"),
      kpi("In flight", String(f.counts.Now || 0) + (lim ? "/" + lim : ""), lim && (f.counts.Now || 0) > lim ? "warn" : "",
        sparkline(flowS.Now || [], { min: 0, label: "In-flight items over committed days" }), "Items In progress or In review", "board", lim ? "limit " + lim : "no WIP limit set"),
      M.git && M.git.stats && M.git.stats.total ? kpi("Traceability", M.git.stats.rate + "%", M.git.stats.rate >= 80 ? "ok" : "warn", null,
        "Commits that name a work item", "git", M.git.stats.linked + " of " + M.git.stats.total + " commits") : null
    ]);
    grid.appendChild(ckCard("status", "Health", null, [kpis], "wide"));

    // Flow
    var cycle = metricValue("cycle") || metricValue("lead");
    grid.appendChild(ckCard("flow", "Flow",
      "Items per column over committed days. A widening Now band with a flat Done band means work starts faster than it finishes." + (cycle ? " " + cycle.name + ": " + cycle.value + "." : ""),
      [drawFlowChart(M.flow)], "wide", link("Board ↗", "board", "chip")));

    // Tests & verify summary: the latest result per stage that runs, failures first.
    var st = ranStages(ev), testRows = el("div", { role: "list" });
    st.ran.map(function (name) {
      var h = stageHistory(ev, name), last = h[h.length - 1];
      return { name: name, last: last, bad: last && stageBad(last.s.result) };
    }).sort(function (a, b) { return (b.bad ? 1 : 0) - (a.bad ? 1 : 0); }).slice(0, 6).forEach(function (x) {
      var open = function () { if (x.last) openLogDrawer({ kind: "evidence", id: x.last.run.folder, stage: x.name, title: "Verify " + x.last.run.folder }); };
      var row = el("div", { cls: "sum-row", role: "listitem" }, [
        el("span", { cls: "stamp " + (x.bad ? "bad" : "ok"), text: x.bad ? "fail" : "pass" }),
        el("strong", { text: x.name }),
        el("span", { cls: "muted", text: x.last ? fmtDur(x.last.s.seconds) + " · " + (x.last.run.generated || "").slice(0, 10) : "" })
      ]);
      row.addEventListener("click", open);
      makeInteractive(row, open, x.name + " " + (x.bad ? "failed" : "passed"));
      testRows.appendChild(row);
    });
    if (!st.ran.length) testRows.appendChild(el("p", { cls: "muted", text: "No verify runs yet. Run python3 .ai-sdlc/bin/sdlc.py verify." }));
    grid.appendChild(ckCard("tests", "Tests & verify",
      lr ? (lr.fails.length ? "The latest run failed " + lr.fails.join(", ") + "." : "The latest run passed every stage it ran.") : "",
      [testRows, ev.length ? viewAll(st.ran.length, "dashboard/tests", "stage") : null]));

    // Runs & logs summary
    var all = allRunsList(ev, f.runs), runList = el("div", { role: "list" });
    all.slice(0, 5).forEach(function (r) { runList.appendChild(runRow(r, function () { go("dashboard/runs/" + r.log.kind + "/" + encodeURIComponent(r.id)); })); });
    if (!all.length) runList.appendChild(el("p", { cls: "muted", text: "No runs yet. Verify runs and commands run from this page are kept here." }));
    grid.appendChild(ckCard("runs", "Runs & logs", null, [runList, all.length ? viewAll(all.length, "dashboard/runs", "run") : null]));

    // Doctor summary: failures, then the biggest rules.
    var groups = groupFindings(), docRows = el("div", { role: "list" });
    groups.slice(0, 5).forEach(function (g) {
      var open = function () { go("dashboard/doctor/" + encodeURIComponent(g.check)); };
      var row = el("div", { cls: "sum-row", role: "listitem" }, [
        el("span", { cls: "stamp " + (g.fail ? "bad" : "neutral"), text: g.fail ? plural(g.fail, "fail") : plural(g.warn, "warn") }),
        el("strong", { text: g.check }),
        el("span", { cls: "muted sum-txt", text: firstSentence(g.items[0].message) })
      ]);
      row.addEventListener("click", open);
      makeInteractive(row, open, g.check + ", " + plural(g.items.length, "finding"));
      docRows.appendChild(row);
    });
    if (!groups.length) docRows.appendChild(el("p", { cls: "muted", text: "Doctor found nothing to report." }));
    grid.appendChild(ckCard("doctor", "Doctor",
      f.fails.length ? plural(f.fails.length, "failing finding") + " block a clean ship." : (f.warns.length ? "No failures; " + plural(f.warns.length, "warning") + " in " + plural(groups.length, "rule") + "." : "Every mechanical check passes."),
      [docRows, M.alerts.length ? viewAll(M.alerts.length, "dashboard/doctor", "finding") : null]));

    // Parallel work: who holds what, and what else can start without colliding.
    var par = M.parallel || { groups: [] }, held = M.claims || [];
    var parRows = el("div", { role: "list" });
    held.slice(0, 4).forEach(function (c) {
      var open = function () { openItemDrawer(c.id); };
      var row = el("div", { cls: "sum-row", role: "listitem" }, [claimChip(c), el("strong", { text: c.id }), el("span", { cls: "muted sum-txt", text: c.branch })]);
      row.addEventListener("click", open); makeInteractive(row, open, c.id + " claimed by " + c.agent);
      parRows.appendChild(row);
    });
    if (par.groups && par.groups.length) parRows.appendChild(el("p", { style: "font-size: 12.5px; margin: 8px 0 0;" },
      [el("strong", { text: "Can start together: " }), document.createTextNode(par.groups[0].slice(0, 8).join(", ") + (par.groups[0].length > 8 ? " and " + (par.groups[0].length - 8) + " more" : ""))]));
    if (!held.length && !(par.groups || []).length) parRows.appendChild(el("p", { cls: "muted", text: "Nothing claimed, and no Ready item with a plan to start." }));
    grid.appendChild(ckCard("parallel", "Parallel work", plural(held.length, "claim") + "; " + plural((par.candidates || []).length, "Ready item") + " with a plan" + ((par.plan_first || []).length ? ", " + (par.plan_first || []).length + " need a plan first" : "") + ".",
      [parRows, el("a", { cls: "view-all", href: "#/dashboard/parallel", text: "Plan parallel work →" })]));

    // Project stats
    var colRows = ["Now", "Next", "Blocked", "Parked", "Later", "Done"].map(function (c) { return [c, f.counts[c] || 0, "var(--c-" + c + ")"]; });
    if (f.counts.Other) colRows.push(["Other", f.counts.Other, "var(--c-Other)"]);
    var owners = {};
    M.order.forEach(function (id) { var o = ownerOf(ITEMS[id]) || "No owner"; owners[o] = (owners[o] || 0) + 1; });
    var ownerNames = Object.keys(owners).sort(function (a, b) { return owners[b] - owners[a]; });
    var ownerRows = ownerNames.slice(0, 5).map(function (o) { return [o, owners[o]]; });
    // Three short columns side by side, so the card is as tall as one list, not three.
    var colByCol = el("div", null, [el("h3", { text: "By column" }), hbars(colRows)]);
    var colByOwner = el("div", null, [el("h3", { text: "By owner" }), hbars(ownerRows),
      ownerNames.length > 5 ? el("p", { cls: "muted ck-more", text: "and " + plural(ownerNames.length - 5, "more owner") }) : null]);
    var epicRows = (M.epics || []).map(function (ep) {
      var ids = ep.items || [];
      return [ep.name, ids.filter(function (id) { return ITEMS[id] && ITEMS[id].column === "Done"; }).length, ids.length];
    });
    var colEpics = null;
    if (epicRows.length) {
      colEpics = el("div", null, [el("h3", { text: "Epics (done of total)" })]);
      epicRows.slice(0, 7).forEach(function (r) { colEpics.appendChild(hbars([[r[0], r[1], "var(--accent)", r[1] + " of " + r[2] + " done"]], Math.max(1, r[2]))); });
      if (epicRows.length > 7) colEpics.appendChild(el("p", { cls: "ck-more" }, [link("and " + plural(epicRows.length - 7, "more epic") + " on the map →", "map")]));
    }
    var statsKids = [el("div", { cls: "stats-cols" }, [colByCol, colByOwner, colEpics])];
    if ((M.metrics || []).length) {
      var mt = el("details", { cls: "plain-details" }, [el("summary", { text: "Process measures (" + M.metrics.length + ")" })]);
      var tb = el("table", { style: "font-size: 12px;" }, [el("tr", null, ["Measure", "Kind", "Value", "From"].map(function (x) { return el("th", { text: x }); }))]);
      M.metrics.forEach(function (m) { tb.appendChild(el("tr", null, [el("td", { text: m.name }), el("td", { text: m.kind }), el("td", null, [inline(m.value)]), el("td", { cls: "muted", text: m.basis })])); });
      mt.appendChild(el("div", { cls: "ck-scroll" }, [tb]));
      statsKids.push(mt);
    }
    statsKids.push(el("p", { style: "margin: 10px 0 0; font-size: 12.5px;" }, [link("Project map →", "map"), document.createTextNode(" epics, stages, dependencies and records as one graph.")]));
    grid.appendChild(ckCard("stats", "Project stats", plural(M.order.length, "item") + ", " + plural(WL.length, "worklog entry", "worklog entries") + ", " + plural(((M.git && M.git.commits) || []).length, "commit") + ".", statsKids, "wide"));

    if (section) {
      var target = document.getElementById("ck-" + section);
      if (target) setTimeout(function () { target.scrollIntoView({ block: "start" }); }, 30);
    }
  }


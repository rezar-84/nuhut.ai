  // ---------------------------------------------------------------- dashboard: doctor
  var DOCTOR_STATE = { level: "", q: "", open: {} };
  function viewDashDoctor() {
    tab("dashboard");
    var parts = location.hash.replace(/^#\/?/, "").split("/");
    var focus = decodeURIComponent(parts[2] || "");
    crumbs([["Dashboard", "dashboard"], ["Doctor"]]);
    var f = dashFacts(), groups = groupFindings();
    dashHeader("Doctor", plural(M.alerts.length, "finding") + " from sdlc.py doctor in " + plural(groups.length, "rule") + (f.fails.length ? "; " + plural(f.fails.length, "failure") + " block a clean ship." : "; none block shipping."), [runDoctorBtn()]);
    if (focus) DOCTOR_STATE.open[focus] = true;
    var lvl = el("select", { cls: "filter-select", "aria-label": "Level", on: { change: function () { DOCTOR_STATE.level = lvl.value; fill(); } } },
      [["", "All levels"], ["fail", "Failures"], ["warn", "Warnings"]].map(function (o) { var x = el("option", { value: o[0], text: o[1] }); if (DOCTOR_STATE.level === o[0]) x.selected = true; return x; }));
    var q = el("input", { type: "search", cls: "filter-input", placeholder: "Filter findings…", value: DOCTOR_STATE.q, "aria-label": "Filter findings",
      on: { input: function () { DOCTOR_STATE.q = q.value; fill(); } } });
    var box = el("div", { cls: "doc-groups" });
    main.appendChild(el("div", { cls: "md-filters", style: "margin-bottom: 12px;" }, [lvl, q]));
    main.appendChild(box);
    function fill() {
      box.textContent = "";
      var needle = DOCTOR_STATE.q.trim().toLowerCase(), any = false;
      groups.forEach(function (g) {
        var items = g.items.filter(function (a) {
          return (!DOCTOR_STATE.level || a.level === DOCTOR_STATE.level) && (!needle || (a.check + " " + a.where + " " + a.message).toLowerCase().indexOf(needle) >= 0);
        });
        if (!items.length) return;
        any = true;
        var fails = items.filter(function (a) { return a.level === "fail"; }).length;
        var det = el("details", { cls: "doc-group" + (fails ? " has-fail" : ""), open: (DOCTOR_STATE.open[g.check] || fails) ? "open" : null }, [
          el("summary", null, [
            el("span", { cls: "stamp " + (fails ? "bad" : "neutral"), text: fails ? plural(fails, "fail") : plural(items.length, "warning") }),
            el("strong", { text: g.check }),
            el("span", { cls: "muted sum-txt", text: firstSentence(items[0].message) }),
            el("span", { cls: "muted", text: plural(items.length, "finding") })
          ])
        ]);
        det.addEventListener("toggle", function () { DOCTOR_STATE.open[g.check] = det.open; });
        var lines = el("div", { role: "list" });
        items.forEach(function (a) {
          var line = el("div", { cls: "doc-line", role: "listitem", title: a.message }, [
            el("span", { cls: "dl-lvl " + a.level, text: a.level }),
            el("div", { style: "min-width: 0;" }, [el("div", { cls: "dl-txt", text: firstSentence(a.message) }), el("div", { cls: "dl-where dl-txt", text: a.where || "" }),
              a.fix ? el("div", { cls: "dl-where dl-txt", text: (a.who === "owner" ? "Needs you: " : "Fix: ") + a.fix }) : null])
          ]);
          line.addEventListener("click", function () { openFindingDrawer(a); });
          makeInteractive(line, function () { openFindingDrawer(a); }, a.level + " " + a.check + ": " + a.message);
          lines.appendChild(line);
        });
        det.appendChild(lines);
        box.appendChild(det);
        if (focus === g.check) setTimeout(function () { det.scrollIntoView({ block: "start" }); }, 30);
      });
      if (!any) box.appendChild(el("p", { cls: "muted", text: M.alerts.length ? "No findings match." : "Doctor found nothing to report." }));
    }
    fill();
  }

  function paintMeta() {
    document.getElementById("pname").textContent = M.project || "Nuhut";
    document.title = (M.project || "Project") + " — Nuhut Command Center";
    var totalItems = (M.order && M.order.length) || 0;
    var waitingCount = (M.order || []).filter(function (id) {
      return ITEMS[id] && (ITEMS[id].column === "Blocked" || ITEMS[id].column === "Parked");
    }).length;
    var commitCount = (M.git && M.git.commits && M.git.commits.length) || 0;
    var docCount = (DOCS && DOCS.length) || 0;
    var wlCount = (WL && WL.length) || 0;

    var tThreads = document.getElementById("tab-threads");
    var unreadCount = unreadIds().length;
    if (tThreads) tThreads.textContent = "Inbox" + (unreadCount ? " (" + unreadCount + ")" : "");
    var tBoard = document.getElementById("tab-board");
    if (tBoard) tBoard.textContent = "Board" + (totalItems ? " (" + totalItems + ")" : "");
    var tWaiting = document.getElementById("tab-waiting");
    if (tWaiting) tWaiting.textContent = "Blockages" + (waitingCount ? " (" + waitingCount + ")" : "");
    var tCk = document.getElementById("tab-dashboard");
    var ckFails = (M.alerts || []).filter(function (a) { return a.level === "fail"; }).length;
    var ckVerify = lastStageResults(M.evidence || []);
    var ckNeeds = ckFails + (ckVerify && ckVerify.fails.length ? 1 : 0) + waitingCount;
    if (tCk) {
      tCk.textContent = "Dashboard" + (ckNeeds ? " (" + ckNeeds + ")" : "");
      tCk.title = ckNeeds ? plural(ckNeeds, "thing") + " waiting on you" : "Nothing waiting on you";
    }
    var tGit = document.getElementById("tab-git");
    if (tGit) tGit.textContent = "Git" + (commitCount ? " (" + commitCount + ")" : "");
    var tDocs = document.getElementById("tab-docs");
    if (tDocs) tDocs.textContent = "Documents" + (docCount ? " (" + docCount + ")" : "");
    var projTab = document.getElementById("tab-project");
    if (projTab) {
      var lsrc = (typeof lensData === "function" && lensData()) || M.lens;
      var ls = lsrc && !lsrc.error ? lsrc.summary : null;
      var projFails = ls ? (ls.security.fail || 0) + ((ls.build.failing || []).length ? 1 : 0) : 0;
      projTab.textContent = "Project" + (projFails ? " (" + projFails + ")" : "");
      projTab.title = projFails ? plural(projFails, "build or security problem") : "Stack, build, security, deploy, environment, agents";
    }
    var meta = document.getElementById("meta");
    meta.textContent = "";
    var gitRef = M.git_head ? (M.git_branch ? M.git_branch + "@" : "") + M.git_head : "";
    if (!LIVE) {
      meta.appendChild(el("button", {
        text: "⚡ Start Live Server",
        title: "Copy `python3 .ai-sdlc/bin/sdlc.py view --serve` to run live command center",
        style: "margin-left: 6px; padding: 2px 8px; font-size: 11px;",
        on: { click: function () { copyCmd("python3 .ai-sdlc/bin/sdlc.py view --serve", "Start Live Server"); } }
      }));
    }
    var cur = document.documentElement.getAttribute("data-theme");
    var isDark = cur === "dark" || (!cur && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    meta.appendChild(el("button", {
      text: "Dark theme",
      "aria-pressed": isDark ? "true" : "false",
      title: "Dark theme " + (isDark ? "on" : "off") + " (t)",
      style: "margin-left: 6px; padding: 2px 8px; font-size: 11px;",
      on: { click: toggleTheme }
    }));
    meta.appendChild(el("button", {
      text: "Export HTML",
      title: "Download self-contained offline dashboard HTML",
      style: "margin-left: 6px; padding: 2px 8px; font-size: 11px;",
      on: { click: exportHtml }
    }));
    meta.appendChild(el("button", {
      text: "?",
      title: "Keyboard shortcuts (?)",
      "aria-label": "Keyboard shortcuts",
      style: "margin-left: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600;",
      on: { click: function () { if (typeof openShortcutsModal === "function") openShortcutsModal(); } }
    }));
    paintContextBar();
    paintGlobalStagingBar();
    paintActivityBar();
  }
  paintMeta();
  var q = document.getElementById("q");
  q.addEventListener("focus", function () {
    var val = q.value;
    q.blur();
    openPalette(val);
  });
  q.addEventListener("click", function () {
    var val = q.value;
    q.blur();
    openPalette(val);
  });
  q.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && q.value.trim()) {
      go("search/" + encodeURIComponent(q.value.trim()));
    }
  });
  document.getElementById("tabs").addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[data-r]") : (e.target.dataset && e.target.dataset.r ? e.target : null);
    if (a && a.dataset.r) {
      e.preventDefault();
      go(a.dataset.r);
    }
  });
  // Where you came from. Pages you open from a list (an item, a document, a dashboard
  // detail, the map, a search) get a Back link to that list, whatever the path to it was.
  var NAV = [];
  var HOME_ROUTES = /^(threads|board|dashboard|waiting|blockages|git|docs|project)$/;
  function routeOf(hash) { return (hash || "").replace(/^#\/?/, ""); }
  function isPageRoute(r) {
    var p = r.split("/");
    return /^(item|doc|map|search)$/.test(p[0]) || ((p[0] === "dashboard" || p[0] === "project") && !!p[1]);
  }
  function routeLabel(r) {
    var p = r.split("/").map(function (x) { try { return decodeURIComponent(x); } catch (e) { return x; } });
    if (p[0] === "threads" || !p[0]) return p[1] ? "Inbox · " + p[1] : "Inbox";
    if (p[0] === "dashboard") return p[1] ? ({ tests: "Tests & verify", runs: "Runs & logs", doctor: "Doctor", parallel: "Parallel work" })[p[1]] || "Dashboard" : "Dashboard";
    if (p[0] === "board") return "Board";
    if (p[0] === "waiting" || p[0] === "blockages") return "Blockages";
    if (p[0] === "git") return "Git";
    if (p[0] === "docs") return "Documents";
    if (p[0] === "project") return p[1] ? "Project · " + ({ stack: "Stack", build: "Build", security: "Security", deploy: "Deploy", env: "Environment", work: "Work", agents: "Agents", kit: "Kit settings" })[p[1]] || p[1] : "Project";
    if (p[0] === "item") return p[1] || "Item";
    if (p[0] === "doc") return (p[1] || "").split("/").pop() || "Document";
    if (p[0] === "search") return "Search “" + p.slice(1).join("/") + "”";
    if (p[0] === "map") return "Map";
    return p[0];
  }
  function trackNav() {
    var r = routeOf(location.hash);
    if (NAV[NAV.length - 1] === r) return;
    if (NAV.length >= 2 && NAV[NAV.length - 2] === r) NAV.pop();
    else NAV.push(r);
    if (NAV.length > 30) NAV.shift();
  }
  function backTarget() {
    var cur = routeOf(location.hash);
    if (!isPageRoute(cur)) return null;
    for (var i = NAV.length - 2; i >= 0; i--) {
      if (NAV[i] !== cur && (HOME_ROUTES.test(NAV[i].split("/")[0]) || !isPageRoute(NAV[i]) || NAV[i].split("/")[0] === "search")) return { route: NAV[i], prev: i === NAV.length - 2 };
    }
    var p = cur.split("/")[0];
    return { route: p === "dashboard" ? "dashboard" : (p === "doc" ? "docs" : (p === "item" ? "board" : "threads")), prev: false };
  }
  function goBack() {
    var t = backTarget();
    if (!t) return false;
    if (t.prev && history.length > 1) history.back();
    else location.hash = "#/" + t.route;
    return true;
  }
  function crumbs(list) {
    var c = document.getElementById("crumbs");
    c.textContent = "";
    var t = backTarget();
    if (t) {
      c.appendChild(el("a", { cls: "back-link", href: "#/" + t.route, text: "← " + routeLabel(t.route), title: "Back (Alt+←)",
        on: { click: function (e) { e.preventDefault(); goBack(); } } }));
      c.appendChild(el("span", { cls: "sep", "aria-hidden": "true", text: "·" }));
    }
    list.filter(function (x) { return x && x[0] !== M.project && !(t && x[1] === t.route); }).forEach(function (x, n) {
      if (n) c.appendChild(el("span", { cls: "sep", "aria-hidden": "true", text: "›" }));
      c.appendChild(x[1] ? link(x[0], x[1]) : el("span", { "aria-current": "page", text: x[0] }));
    });
  }
  function tab(name) {
    [].forEach.call(document.querySelectorAll("#tabs a"), function (a) {
      a.className = a.dataset.r === name ? "on" : "";
    });
  }

  // ---------------------------------------------------------------- claims & parallel work
  function claimOf(id) { return (M.claims || []).filter(function (c) { return c.id === id; })[0] || null; }
  function claimChip(c, long) {
    var days = c.since ? Math.max(0, Math.floor((Date.now() - Date.parse(c.since)) / 86400000)) : null;
    return el("span", { cls: "claim-chip", title: "Claimed by " + c.agent + (c.since ? " on " + c.since.slice(0, 10) : "") + (c.worktree ? " · worktree " + c.worktree : "") + " · branch " + c.branch,
      text: (long ? "claimed by " : "") + c.agent + (days !== null ? " · " + days + "d" : "") });
  }
  function viewDashParallel() {
    tab("dashboard");
    crumbs([["Dashboard", "dashboard"], ["Parallel work"]]);
    var par = M.parallel || { groups: [], conflicts: [], plan_first: [], candidates: [] }, held = M.claims || [];
    dashHeader("Parallel work", "Who holds what, and which Ready items can start side by side without touching the same files.", []);
    main.appendChild(section("Claimed", held.length ? "Each claim is shared by every worktree on this machine; its branch is what other machines see." : "Nothing is claimed. Take an item with: python3 .ai-sdlc/bin/sdlc.py claim <ID>", [
      held.length ? table(["Item", "Agent", "Branch", "Worktree", "Since", "Last commit"], held.map(function (c) {
        return tr([el("strong", { text: c.id }), c.agent, el("code", { text: c.branch }), el("span", { cls: "muted", text: c.worktree || "—" }), (c.since || "").slice(0, 10), (c.last_commit || "").slice(0, 10) || "none"],
          function () { openItemDrawer(c.id); }, c.id);
      })) : null]));
    var byId = {};
    (par.candidates || []).forEach(function (c) { byId[c.id] = c; });
    main.appendChild(section("Can start together", "Unclaimed Ready items whose dependencies are done, grouped so that no two in a group touch the same files (from each plan's Files that change). Charter, migrations and lockfiles count as one shared file each.", [
      (par.groups || []).length ? table(["Group", "Items", "Files they change"], par.groups.map(function (g, n) {
        return tr([String(n + 1), el("span", null, g.map(function (id, i) { return el("span", null, [i ? ", " : "", itemLink(id)]); })),
          el("span", { cls: "muted sum-txt", text: g.map(function (id) { return (byId[id] ? byId[id].files : []).slice(0, 3).join(" "); }).join(" · ") })]);
      })) : el("p", { cls: "muted", text: "No unclaimed Ready item has a plan with Files that change." })]));
    if ((par.conflicts || []).length) main.appendChild(section("Conflicts", "These pairs must run one after the other.", [
      table(["Items", "Shared"], par.conflicts.map(function (c) { return tr([c.a + " × " + c.b, c.files.concat(c.single_writer).join(", ")]); }))]));
    if ((par.plan_first || []).length) main.appendChild(section("Plan first", "Ready items without a plan's Files that change; their files are unknown, so they run alone.", [
      el("p", null, par.plan_first.map(function (x, i) { return el("span", null, [i ? ", " : "", itemLink(x.id)]); }))]));
    if (par.error) main.appendChild(el("p", { cls: "quiet-note", text: "Parallel report unavailable: " + par.error }));
  }

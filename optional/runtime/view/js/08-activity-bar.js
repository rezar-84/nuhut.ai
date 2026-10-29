  // ---------------------------------------------------------------- activity bar
  var LAST_RUN = null;
  function paintActivityBar() {
    var bar = document.getElementById("activity-bar");
    if (!bar) return;
    bar.textContent = "";
    // Glyphs are decoration; the words carry the meaning for screen readers.
    function item(cls, text, title, onClick, kids, glyph) {
      var b = el(onClick ? "button" : "span", { cls: "ab-item " + (cls || ""), title: title || "", on: onClick ? { click: onClick } : undefined }, kids || []);
      if (glyph) b.appendChild(el("span", { "aria-hidden": "true", text: glyph + " " }));
      if (text) b.appendChild(document.createTextNode(text));
      return b;
    }
    if (LIVE) {
      bar.appendChild(item(liveState === "live" ? "ok" : "bad", (liveState === "live" ? "Live · " : "Disconnected · ") + liveAt.toTimeString().slice(0, 8),
        liveState === "live" ? "Following the records; last refreshed at this time" : "The local server stopped. Restart: sdlc.py view --serve",
        null, [el("span", { cls: "dot " + liveState })]));
    } else {
      bar.appendChild(item("", "Snapshot " + (M.generated || ""), "A static export. Run sdlc.py view --serve for a live page.",
        function () { copyCmd("python3 .ai-sdlc/bin/sdlc.py view --serve", "Start Live Server"); }));
    }
    if (M.git_branch) bar.appendChild(item("", M.git_branch + (M.git_head ? "@" + M.git_head : ""), "Open Git", function () { go("git"); }, null, "⎇"));
    var lr = lastStageResults(M.evidence || []);
    if (lr) {
      bar.appendChild(item(lr.fails.length ? "bad" : "ok", lr.fails.length ? "verify failed: " + lr.fails.join(", ") : "verify passed",
        "Latest verify run " + lr.run.folder + " — open Tests & verify", function () { go("dashboard/tests"); }, null, lr.fails.length ? "✗" : "✓"));
    }
    var fails = (M.alerts || []).filter(function (a) { return a.level === "fail"; }).length;
    var warns = (M.alerts || []).filter(function (a) { return a.level === "warn"; }).length;
    bar.appendChild(item(fails ? "bad" : "", "doctor " + (fails ? plural(fails, "failure") : (warns ? plural(warns, "warning") : "clean")),
      "sdlc.py doctor findings — open Doctor", function () { go("dashboard/doctor"); }));
    var waiting = (M.order || []).filter(function (id) { return ITEMS[id].column === "Blocked" || ITEMS[id].column === "Parked"; }).length;
    if (waiting) bar.appendChild(item("warn", waiting + " waiting", "Items blocked or parked — open Blockages", function () { go("waiting"); }, null, "⏸"));
    if (TERMINAL_STATE.running) {
      bar.appendChild(item("", " running " + clip(TERMINAL_STATE.cmd.replace(/^python3 \.ai-sdlc\/bin\/sdlc\.py /, ""), 40), TERMINAL_STATE.cmd, null, [el("span", { cls: "ab-spin" })]));
    } else if (LAST_RUN) {
      bar.appendChild(item(LAST_RUN.exit_code === 0 ? "ok" : "bad",
        LAST_RUN.label + (LAST_RUN.exit_code === 0 ? " passed" : " failed") + " · " + fmtDur(LAST_RUN.seconds || 0),
        "Last command run from this page — open its log", function () {
          if (LAST_RUN.run_id) openLogDrawer({ kind: "run", id: LAST_RUN.run_id, title: LAST_RUN.label });
          else go("dashboard/runs");
        }));
    }
    bar.appendChild(el("span", { cls: "ab-spacer" }));
    var issues = issueList().filter(function (x) { return x.level !== "info"; }).length;
    if (issues) bar.appendChild(item(issueList().some(function (x) { return x.level === "fail"; }) ? "bad" : "warn", plural(issues, "issue"),
      "Doctor failures, kit repairs and records the view could not place — open Issues", function () { showPanel("issues", { quiet: wide() }); }));
    var un = unreadIds().length;
    bar.appendChild(item("", un ? un + " unread" : "all read", "Items with activity you have not opened — open the Inbox feed",
      function () { THREAD_STATE.mode = "feed"; THREAD_STATE.feedUnread = !!un; go("threads"); }, un ? [el("span", { cls: "unread-dot" })] : []));
    var bellSvg = svgEl("svg", { width: 14, height: 14, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
    bellSvg.appendChild(svgEl("path", { d: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" }));
    bellSvg.appendChild(svgEl("path", { d: "M10.3 21a1.94 1.94 0 0 0 3.4 0" }));
    var bell = item("", "", "Notifications (n)", toggleNotes, [bellSvg]);
    bell.setAttribute("aria-label", "Notifications, " + unseenNotes() + " new");
    var cnt = unseenNotes();
    if (cnt) bell.appendChild(el("span", { cls: "ab-badge", text: cnt > 99 ? "99+" : String(cnt) }));
    bar.appendChild(bell);
    bar.appendChild(el("span", { id: "ab-live", cls: "sr-only", role: "status", "aria-live": "polite", text: AB_ANNOUNCE }));
    refreshPanelChrome();
  }
  var AB_ANNOUNCE = "";


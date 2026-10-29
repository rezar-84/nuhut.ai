  // ---------------------------------------------------------------- dashboard data
  function dashFacts() {
    var counts = {};
    M.order.forEach(function (id) { var c = ITEMS[id].column; counts[c] = (counts[c] || 0) + 1; });
    var ev = M.evidence || [];
    return {
      counts: counts, ev: ev, runs: M.runs || [], lr: lastStageResults(ev),
      fails: M.alerts.filter(function (a) { return a.level === "fail"; }),
      warns: M.alerts.filter(function (a) { return a.level === "warn"; }),
      waitingIds: M.order.filter(function (id) { return ITEMS[id].column === "Blocked" || ITEMS[id].column === "Parked"; })
    };
  }
  // Stages a project actually runs: any run recorded a Verified result for them. The
  // rest were "not selected" in every run and only add noise.
  function ranStages(ev) {
    var ran = [], all = [];
    ev.forEach(function (r) {
      r.stages.forEach(function (s) {
        if (!/^(Verified|Not run)/.test(s.result || "")) return;
        if (all.indexOf(s.stage) < 0) all.push(s.stage);
        if (/^Verified/.test(s.result || "") && ran.indexOf(s.stage) < 0) ran.push(s.stage);
      });
    });
    return { ran: all.filter(function (s) { return ran.indexOf(s) >= 0; }), idle: all.filter(function (s) { return ran.indexOf(s) < 0; }) };
  }
  function stageHistory(ev, st) {
    var hist = [];
    ev.forEach(function (r) {
      var x = r.stages.filter(function (s) { return s.stage === st; })[0];
      if (x && /^Verified/.test(x.result || "")) hist.push({ run: r, s: x });
    });
    return hist;
  }
  function allRunsList(ev, runs) {
    var out = ev.map(function (r) {
      var badStages = r.stages.filter(function (s) { return stageBad(s.result); });
      var verified = r.stages.filter(function (s) { return /^Verified/.test(s.result || ""); });
      return { kind: "verify", id: r.folder, when: r.generated || r.folder, ok: !badStages.length,
        detail: (badStages.length ? "failed " + badStages.map(function (s) { return s.stage; }).join(", ") : plural(verified.length, "stage") + " passed") + (r.dirty ? " · uncommitted changes" : ""),
        seconds: verified.reduce(function (a, s) { return a + (+s.seconds || 0); }, 0) || null,
        log: { kind: "evidence", id: r.folder, stage: (badStages[0] || verified[0] || {}).stage, title: "Verify " + r.folder } };
    }).concat(runs.map(function (r) {
      return { kind: r.sub, id: r.id, when: r.generated || r.id, ok: r.exit_code === 0, detail: (r.args || []).join(" ") || "exit " + r.exit_code,
        seconds: r.seconds, log: { kind: "run", id: r.id, title: r.sub + " " + (r.args || []).join(" ") } };
    }));
    out.sort(function (a, b) { return String(b.when).localeCompare(String(a.when)); });
    return out;
  }
  function runRow(r, onOpen, selected) {
    var row = el("div", { cls: "run-row" + (selected ? " sel" : ""), role: "listitem" }, [
      el("span", { cls: "rr-dot " + (r.ok ? "ok" : "bad"), "aria-hidden": "true" }),
      el("span", { style: "min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" }, [
        el("span", { cls: "sr-only", text: r.ok ? "Passed: " : "Failed: " }),
        el("strong", { text: r.kind }), el("span", { cls: "muted", text: " " + r.detail })
      ]),
      el("span", { cls: "muted", text: r.seconds ? fmtDur(r.seconds) : "" }),
      el("span", { cls: "muted", text: String(r.when).replace("T", " ").replace(/Z$/, "").slice(0, 16) })
    ]);
    row.addEventListener("click", onOpen);
    makeInteractive(row, onOpen, r.kind + " " + (r.ok ? "passed" : "failed") + " " + r.when);
    return row;
  }
  function groupFindings() {
    var groups = {};
    M.alerts.forEach(function (a) { (groups[a.check] = groups[a.check] || { check: a.check, items: [], fail: 0, warn: 0 }).items.push(a); });
    return Object.keys(groups).map(function (k) {
      var g = groups[k];
      g.items.forEach(function (a) { if (a.level === "fail") g.fail++; else if (a.level === "warn") g.warn++; });
      return g;
    }).sort(function (a, b) { return (b.fail - a.fail) || (b.items.length - a.items.length) || a.check.localeCompare(b.check); });
  }
  function firstSentence(t) { return String(t || "").split(/(?<=[.;])\s/)[0]; }
  function viewAll(n, route, noun) {
    return el("a", { cls: "view-all", href: "#/" + route, text: "View all " + plural(n, noun) + " →" });
  }
  function dashHeader(title, subtitle, actions) {
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [el("h1", { text: title }), subtitle ? el("p", { cls: "view-subtitle", text: subtitle }) : null]),
      el("div", { cls: "view-header-actions" }, actions || [])
    ]));
  }
  function runVerifyBtn() {
    return LIVE && M.action_token ? el("button", { cls: "btn", text: "Run verify", title: "python3 .ai-sdlc/bin/sdlc.py verify --parallel", on: { click: function () {
      runKitCmd({ subcommand: "verify" }, "python3 .ai-sdlc/bin/sdlc.py verify --parallel", "verify");
    } } }) : el("button", { cls: "btn", text: "Copy verify command", on: { click: function () { copyCmd("python3 .ai-sdlc/bin/sdlc.py verify --parallel", "verify"); } } });
  }
  function runDoctorBtn() {
    return LIVE && M.action_token ? el("button", { cls: "btn", text: "Run doctor", title: "python3 .ai-sdlc/bin/sdlc.py doctor", on: { click: function () {
      runKitCmd({ subcommand: "doctor" }, "python3 .ai-sdlc/bin/sdlc.py doctor", "doctor");
    } } }) : el("button", { cls: "btn", text: "Copy doctor command", on: { click: function () { copyCmd("python3 .ai-sdlc/bin/sdlc.py doctor", "doctor"); } } });
  }


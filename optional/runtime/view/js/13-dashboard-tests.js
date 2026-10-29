  // ---------------------------------------------------------------- dashboard: tests
  var TESTS_STATE = { idle: false };
  function viewDashTests() {
    tab("dashboard");
    crumbs([["Dashboard", "dashboard"], ["Tests & verify"]]);
    var f = dashFacts(), ev = f.ev, lr = f.lr, st = ranStages(ev);
    dashHeader("Tests & verify",
      ev.length ? plural(ev.length, "verify run") + " kept in .ai-sdlc/evidence/. " + (lr ? (lr.fails.length ? "The latest failed " + lr.fails.join(", ") + "." : "The latest passed.") : "")
        : "No verify runs yet.", [runVerifyBtn()]);
    if (!ev.length) {
      main.appendChild(el("p", { cls: "muted", text: "Run python3 .ai-sdlc/bin/sdlc.py verify; each run's stage results and logs land in .ai-sdlc/evidence/." }));
      return;
    }
    var stages = TESTS_STATE.idle ? st.ran.concat(st.idle) : st.ran;
    var gridBox = drawVerifyGrid(ev, { stages: stages, onCell: function (run, stage) {
      openLogDrawer({ kind: "evidence", id: run.folder, stage: stage, title: "Verify " + run.folder });
    } });
    main.appendChild(el("section", { cls: "page-section", "aria-labelledby": "t-grid" }, [
      el("h2", { id: "t-grid", cls: "sec-h", text: "Every run, every stage" }),
      el("p", { cls: "sec-sub", text: "Runs left to right, oldest first. Click a cell for that stage's log." }),
      gridBox
    ]));
    var table = el("table", { cls: "data-table" }, [el("tr", null, ["Stage", "Last result", "Last run", "Took", "Duration trend", "Pass rate", ""].map(function (x) { return el("th", { text: x }); }))]);
    stages.forEach(function (name) {
      var h = stageHistory(ev, name), last = h[h.length - 1];
      var idle = st.idle.indexOf(name) >= 0;
      var passN = h.filter(function (x) { return stageOk(x.s.result); }).length;
      var recent = h.slice(-10), flaky = recent.some(function (x) { return stageOk(x.s.result); }) && recent.some(function (x) { return stageBad(x.s.result); });
      var secs = h.map(function (x) { return +x.s.seconds || 0; }).filter(Boolean);
      var tr = el("tr", { cls: idle ? "idle" : "", style: last ? "cursor: pointer;" : "" }, [
        el("td", null, [el("strong", { text: name })]),
        el("td", null, [last ? el("span", { cls: "stamp " + (stageBad(last.s.result) ? "bad" : "ok"), text: stageBad(last.s.result) ? "fail" : "pass" }) : el("span", { cls: "muted", text: "not run" })]),
        el("td", { cls: "muted", text: last ? (last.run.generated || last.run.folder).replace("T", " ").replace(/Z$/, "").slice(0, 16) : "—" }),
        el("td", { text: last ? fmtDur(last.s.seconds) : "—" }),
        el("td", null, [secs.length > 1 ? sparkline(secs, { w: 110, h: 20, min: 0, label: name + " duration over " + secs.length + " runs" }) : el("span", { cls: "muted", text: "—" })]),
        el("td", { text: h.length ? passN + " of " + h.length : "—" }),
        el("td", null, [flaky ? el("span", { cls: "stamp warn", title: "Both passed and failed in the last 10 runs", text: "flaky" }) : null])
      ]);
      if (last) {
        var open = function () { openLogDrawer({ kind: "evidence", id: last.run.folder, stage: name, title: "Verify " + last.run.folder }); };
        tr.addEventListener("click", open);
        makeInteractive(tr, open, name + " stage, open last log");
      }
      table.appendChild(tr);
    });
    main.appendChild(el("section", { cls: "page-section", "aria-labelledby": "t-stages" }, [
      el("h2", { id: "t-stages", cls: "sec-h", text: "Stages" }),
      el("p", { cls: "sec-sub", text: "Click a stage for its latest log." }),
      table,
      st.idle.length ? el("button", { cls: "btn", style: "margin-top: 10px;", text: TESTS_STATE.idle ? "Hide stages this project does not run" : "Show " + plural(st.idle.length, "stage") + " this project does not run",
        on: { click: function () { TESTS_STATE.idle = !TESTS_STATE.idle; render(); } } }) : null
    ]));
  }


  // ---------------------------------------------------------------- logs
  // Evidence stage logs and kept runs are read from the live server on demand; a static
  // export has no server to ask, so it says how to get one.
  var LOG_CACHE = {};
  function logKey(log) { return log.kind + ":" + log.id + ":" + (log.stage || ""); }
  function fetchLog(log, cb) {
    var key = logKey(log);
    if (LOG_CACHE[key] !== undefined) { cb(LOG_CACHE[key], true); return; }
    if (!LIVE) { cb(null, false); return; }
    var url = "api/log?kind=" + encodeURIComponent(log.kind) + "&id=" + encodeURIComponent(log.id) +
      (log.stage ? "&stage=" + encodeURIComponent(log.stage) : "");
    fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (t) { LOG_CACHE[key] = t; cb(t, true); }).catch(function () { cb(null, true); });
  }
  function evidenceRun(id) {
    return (M.evidence || []).filter(function (r) { return r.folder === id; })[0];
  }
  function savedRun(id) {
    return (M.runs || []).filter(function (r) { return r.id === id; })[0];
  }
  function stageOk(result) { return /pass/i.test(result || ""); }
  function stageBad(result) { return /fail/i.test(result || ""); }
  function openLogDrawer(log) {
    setInspect({ kind: "log", id: logKey(log), log: log });
    var container = el("div", { style: "display: flex; flex-direction: column; height: 100%;" });
    var title = log.title || (log.kind === "evidence" ? "Verify " + log.id : "Run " + log.id);
    container.appendChild(el("div", { cls: "drawer-header" }, [
      el("div", { style: "display: flex; align-items: baseline; gap: 8px; min-width: 0;" }, [
        el("strong", { style: "font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;", text: title })
      ]),
      el("button", { cls: "drawer-close", "aria-label": "Close log", text: "✕", on: { click: closeDrawer } })
    ]));
    var body = el("div", { cls: "drawer-body" });
    container.appendChild(body);
    var pre = el("pre", { cls: "log-pre", text: "Loading…" });
    if (log.kind === "evidence") {
      var run = evidenceRun(log.id);
      if (run) {
        body.appendChild(el("div", { cls: "muted", style: "font-size: 12px; margin-bottom: 8px;",
          text: (run.generated || "") + (run.git_head ? " · " + run.git_head : "") + (run.dirty ? " · uncommitted changes" : "") }));
        var stages = el("div", { style: "display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px;" });
        run.stages.forEach(function (st) {
          if (!/^(Verified|Not run)/.test(st.result || "")) return;
          var on = st.stage === log.stage;
          stages.appendChild(el("button", {
            cls: "chip", style: "cursor: pointer; border: 1px solid " + (on ? "var(--link)" : "transparent") + "; " +
              (stageBad(st.result) ? "background: var(--badbg); color: var(--bad);" : (stageOk(st.result) ? "background: var(--okbg);" : "")),
            title: st.result + (st.seconds !== undefined && st.seconds !== null ? " · " + fmtDur(st.seconds) : ""),
            text: (stageBad(st.result) ? "✗ " : (stageOk(st.result) ? "✓ " : "· ")) + st.stage + (st.seconds ? " " + fmtDur(st.seconds) : ""),
            on: { click: function () { INSPECT = null; openLogDrawer({ kind: "evidence", id: log.id, stage: st.stage, title: log.title }); } }
          }));
        });
        body.appendChild(stages);
      }
    } else {
      var sr = savedRun(log.id);
      if (sr) {
        body.appendChild(el("div", { style: "display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; font-size: 12px;" }, [
          el("span", { cls: "stamp " + (sr.exit_code === 0 ? "ok" : "bad"), text: "exit " + sr.exit_code }),
          el("span", { cls: "chip", text: fmtDur(sr.seconds || 0) }),
          el("span", { cls: "chip", text: (sr.generated || "").replace("T", " ").replace("Z", "") }),
          el("code", { style: "font-size: 11px;", text: "sdlc.py " + sr.sub + " " + (sr.args || []).join(" ") })
        ]));
      }
    }
    body.appendChild(pre);
    openDrawer(container, { quiet: true });
    if (log.kind === "evidence" && !log.stage) { pre.textContent = "Pick a stage above to read its log."; return; }
    fetchLog(log, function (text, live) {
      if (text === null) {
        pre.textContent = live ? "No log kept for this " + (log.kind === "evidence" ? "stage" : "run") + "."
          : "Logs are read from the live server. Run: python3 .ai-sdlc/bin/sdlc.py view --serve";
        return;
      }
      pre.textContent = text || "(empty)";
      pre.scrollTop = pre.scrollHeight;
    });
  }

  // One doctor finding with its full advice, beside the list it came from.
  function openFindingDrawer(a) {
    setInspect({ kind: "finding", id: a.check + "|" + a.where + "|" + a.message.slice(0, 40), a: a });
    var box = el("div", { style: "display: flex; flex-direction: column; height: 100%;" }, [
      el("div", { cls: "drawer-header" }, [
        el("div", { style: "display: flex; align-items: baseline; gap: 8px; min-width: 0;" }, [
          el("span", { cls: "stamp " + (a.level === "fail" ? "bad" : (a.level === "warn" ? "warn" : "")), text: a.level }),
          el("strong", { text: "Doctor · " + a.check })
        ]),
        el("button", { cls: "drawer-close", "aria-label": "Close finding", text: "✕", on: { click: closeDrawer } })
      ]),
      el("div", { cls: "drawer-body" }, [
        a.where ? el("p", { style: "font-family: var(--mono); font-size: 12px; margin-top: 0;" }, [inline(a.where)]) : null,
        el("div", { style: "font-size: 14px; line-height: 1.55; max-width: 65ch;" }, [inline(a.message)]),
        el("p", { cls: "muted", style: "font-size: 12px; margin-top: 16px;" }, ["Re-check after fixing: ", el("code", { text: "python3 .ai-sdlc/bin/sdlc.py doctor" })])
      ])
    ]);
    openDrawer(box, { quiet: true });
  }


  // ---------------------------------------------------------------- tooltip & drawer
  var ttEl = document.getElementById("map-tooltip");
  function showMapTooltip(n, e) {
    if (!ttEl) return;
    ttEl.textContent = "";
    if (n.id && ITEMS[n.id]) {
      var it = ITEMS[n.id];
      ttEl.appendChild(el("div", { cls: "tt-title", text: n.id + " — " + (it.title || "(untitled)") }));
      var chips = el("div", { cls: "tt-chips" });
      chips.appendChild(colChip(it.column));
      if (it.tier) chips.appendChild(el("span", { cls: "chip", text: "Tier " + it.tier }));
      if (it.owner) chips.appendChild(el("span", { cls: "chip", text: it.owner }));
      ttEl.appendChild(chips);
      var metaLines = [];
      if (n.blocked) {
        var open = unresolved(it);
        metaLines.push("Blocked: waits on " + open.join(", "));
      }
      var openDeps = (it.dependents || []).filter(function (d) { return ITEMS[d] && ITEMS[d].column !== "Done"; });
      if (openDeps.length && it.column !== "Done") {
        metaLines.push("Active Blocker: blocks " + openDeps.join(", "));
      }
      if (it.steps) {
        metaLines.push("Progress: " + (n.stepsDone || 0) + "/" + M.steps.length + " lifecycle steps");
      }
      metaLines.push("Click to inspect · Double-click to open");
      metaLines.forEach(function (m) { ttEl.appendChild(el("div", { cls: "tt-meta", text: m })); });
    } else if (n.route) {
      ttEl.appendChild(el("div", { cls: "tt-title", text: n.full || n.label }));
      ttEl.appendChild(el("div", { cls: "tt-meta", text: "Document section · Click to inspect" }));
    } else {
      ttEl.appendChild(el("div", { cls: "tt-title", text: n.label }));
      var count = n.children ? n.children.length : 0;
      ttEl.appendChild(el("div", { cls: "tt-meta", text: count + " item" + (count === 1 ? "" : "s") + " · Click to toggle" }));
    }
    ttEl.style.display = "block";
    positionTooltip(e);
  }

  function positionTooltip(e) {
    if (!ttEl || ttEl.style.display !== "block") return;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + 320 > window.innerWidth) x = e.clientX - 330;
    if (y + 120 > window.innerHeight) y = e.clientY - 120;
    ttEl.style.left = Math.max(8, x) + "px";
    ttEl.style.top = Math.max(8, y) + "px";
  }

  function hideMapTooltip() {
    if (ttEl) ttEl.style.display = "none";
  }

  var drawerEl = document.getElementById("drawer");
  var backdropEl = document.getElementById("drawer-backdrop");
  var lastFocusedEl = null;

  function restoreLastFocus() {
    if (lastFocusedEl && typeof lastFocusedEl.focus === "function") {
      try { lastFocusedEl.focus(); } catch (e) {}
    }
    lastFocusedEl = null;
  }

  // The side panel. On wide screens it docks beside the page with three tabs (Item,
  // Activity, Issues); closing it folds it to a rail of those tabs rather than removing
  // it, so the last item, the notifications and the issues stay one click away. Narrow
  // screens keep a modal slide-over.
  var DOCK_MIN = 1100;
  var INSPECT = null;          // what the Item tab shows: {kind, id, ...}; kept while folded
  var INSPECT_STACK = [];      // earlier Item contents, for the back button
  var ITEM_CONTENT = null;     // the built node for INSPECT
  var PANEL = { open: false, tab: "item" };
  try {
    var savedPanel = JSON.parse(localStorage.getItem("nuhut-panel") || "null");
    if (savedPanel && savedPanel.tab) PANEL.tab = savedPanel.tab;
    if (savedPanel && savedPanel.open && savedPanel.tab !== "item") PANEL.open = true;
  } catch (e) {}
  function savePanel() { try { localStorage.setItem("nuhut-panel", JSON.stringify(PANEL)); } catch (e) {} }
  function wide() { return window.innerWidth >= DOCK_MIN; }
  function isDocked() { return drawerEl && drawerEl.classList.contains("docked") && drawerEl.classList.contains("open"); }
  (function () {
    var w = 0;
    try { w = +localStorage.getItem("nuhut-insp-w") || 0; } catch (e) {}
    if (w >= 320) document.documentElement.style.setProperty("--insp-w", w + "px");
  })();

  function panelIcon(name) {
    var svg = svgEl("svg", { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "2",
      "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" });
    var d = {
      item: ["M4 5h16v14H4z", "M14 5v14"],
      activity: ["M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M10.3 21a1.94 1.94 0 0 0 3.4 0"],
      issues: ["M12 3 2 20h20L12 3z", "M12 10v4", "M12 17h.01"],
      fold: ["M15 6l-6 6 6 6"]
    }[name] || [];
    d.forEach(function (x) { svg.appendChild(svgEl("path", { d: x })); });
    return svg;
  }
  function panelCounts() {
    return { item: INSPECT ? 1 : 0, activity: unseenNotes(), issues: issueList().filter(function (x) { return x.level !== "info"; }).length };
  }
  function panelTabButton(key, label, rail) {
    var n = panelCounts()[key];
    var on = PANEL.open && PANEL.tab === key;
    var b = el("button", { cls: (rail ? "rail-btn" : "ptab") + (on ? " on" : ""), role: rail ? null : "tab",
      "aria-selected": rail ? null : (on ? "true" : "false"), "aria-pressed": rail ? (on ? "true" : "false") : null,
      title: label + (key === "item" && INSPECT ? ": " + (INSPECT.id || "") : ""), "aria-label": label + (n && key !== "item" ? ", " + n : ""),
      disabled: key === "item" && !INSPECT ? "disabled" : null,
      on: { click: function () { showPanel(key); } } }, [panelIcon(key), rail ? null : el("span", { text: label })]);
    if (n && key !== "item") b.appendChild(el("span", { cls: "pbadge", "aria-hidden": "true", text: n > 99 ? "99+" : String(n) }));
    return b;
  }
  function renderPanel(opts) {
    if (!drawerEl || !backdropEl) return;
    opts = opts || {};
    var docked = wide();
    drawerEl.textContent = "";
    if (!docked && !PANEL.open) {
      drawerEl.className = "drawer";
      backdropEl.className = "drawer-backdrop";
      document.body.classList.remove("docked", "railed");
      return;
    }
    if (docked && !PANEL.open) {
      // Folded: a rail of the three tabs.
      drawerEl.className = "drawer docked rail";
      drawerEl.setAttribute("role", "complementary");
      drawerEl.removeAttribute("aria-modal");
      drawerEl.setAttribute("aria-label", "Side panel (folded)");
      drawerEl.appendChild(el("div", { cls: "rail-col" }, [
        panelTabButton("item", "Item", true), panelTabButton("activity", "Activity", true), panelTabButton("issues", "Issues", true)
      ]));
      backdropEl.className = "drawer-backdrop";
      document.body.classList.remove("docked");
      document.body.classList.add("railed");
      markSelected();
      return;
    }
    var grip = el("div", { cls: "insp-grip", title: "Drag to resize the panel" });
    grip.addEventListener("mousedown", startInspectorResize);
    drawerEl.appendChild(grip);
    drawerEl.appendChild(el("div", { cls: "ptabs", role: "tablist", "aria-label": "Side panel" }, [
      panelTabButton("item", "Item"), panelTabButton("activity", "Activity"), panelTabButton("issues", "Issues"),
      el("span", { style: "flex: 1;" }),
      el("button", { cls: "ptab-fold", title: docked ? "Fold the panel (])" : "Close", "aria-label": docked ? "Fold the side panel" : "Close the side panel",
        on: { click: closeDrawer } }, [docked ? panelIcon("fold") : el("span", { text: "✕" })])
    ]));
    var body = el("div", { cls: "pbody", role: "tabpanel" });
    if (PANEL.tab === "item") {
      if (ITEM_CONTENT) {
        if (INSPECT_STACK.length) {
          var hdr0 = ITEM_CONTENT.querySelector && ITEM_CONTENT.querySelector(".drawer-header > div");
          if (hdr0 && !hdr0.querySelector(".insp-back")) hdr0.insertBefore(el("button", { cls: "insp-back", text: "←", title: "Back", "aria-label": "Back to the previous item in the panel",
            on: { click: inspectBack } }), hdr0.firstChild);
        }
        body.appendChild(ITEM_CONTENT);
      } else body.appendChild(el("div", { cls: "insp-empty", text: "Click a card, a run or a finding to see it here. The list stays where it is." }));
    } else if (PANEL.tab === "activity") body.appendChild(renderActivityTab());
    else body.appendChild(renderIssuesTab());
    drawerEl.appendChild(body);
    drawerEl.className = "drawer open" + (docked ? " docked" : "");
    if (docked) {
      drawerEl.setAttribute("role", "complementary");
      drawerEl.removeAttribute("aria-modal");
      drawerEl.setAttribute("aria-label", "Side panel");
      backdropEl.className = "drawer-backdrop";
      document.body.classList.add("docked");
      document.body.classList.remove("railed");
    } else {
      if (!opts.keepFocus) lastFocusedEl = lastFocusedEl || document.activeElement;
      drawerEl.setAttribute("role", "dialog");
      drawerEl.setAttribute("aria-modal", "true");
      drawerEl.setAttribute("aria-label", "Side panel");
      backdropEl.className = "drawer-backdrop open";
      document.body.classList.remove("docked", "railed");
    }
    markSelected();
    if (docked || opts.quiet) return;
    var closeBtn = drawerEl.querySelector(".drawer-close, .ptab-fold");
    if (closeBtn) setTimeout(function () { closeBtn.focus(); }, 30);
  }
  function showPanel(tabName, opts) {
    if (tabName === "item" && !ITEM_CONTENT && INSPECT) { PANEL.tab = "item"; PANEL.open = true; reopenInspect(INSPECT, true); return; }
    PANEL.tab = tabName;
    PANEL.open = true;
    savePanel();
    renderPanel(opts || { quiet: true });
  }
  // Closing folds the panel to its rail on wide screens; the item it showed is kept.
  function closeDrawer() {
    var wasModal = drawerEl && drawerEl.classList.contains("open") && !isDocked();
    PANEL.open = false;
    savePanel();
    renderPanel();
    if (wasModal) restoreLastFocus();
  }
  if (backdropEl) backdropEl.addEventListener("click", closeDrawer);

  function openDrawer(content, opts) {
    ITEM_CONTENT = content;
    PANEL.tab = "item";
    PANEL.open = true;
    savePanel();
    renderPanel(opts);
  }
  function refreshPanelChrome() {
    if (!drawerEl) return;
    if (PANEL.open && PANEL.tab !== "item") { renderPanel({ quiet: true }); return; }
    var holder = drawerEl.querySelector(".ptabs, .rail-col");
    if (!holder) { if (wide()) renderPanel({ quiet: true }); return; }
    var rail = holder.classList.contains("rail-col");
    [["item", "Item"], ["activity", "Activity"], ["issues", "Issues"]].forEach(function (t, i) {
      var old = holder.children[i];
      if (old) holder.replaceChild(panelTabButton(t[0], t[1], rail), old);
    });
  }

  // Remember what is shown, so a live redraw can refresh it and links inside it can
  // stack with a back button.
  function setInspect(next) {
    if (isDocked() && PANEL.tab === "item" && INSPECT && !(INSPECT.kind === next.kind && INSPECT.id === next.id)) {
      if (next.kind !== "item" || INSPECT.kind !== "item") INSPECT_STACK.push(INSPECT);
      else INSPECT_STACK = [];
      if (INSPECT_STACK.length > 12) INSPECT_STACK.shift();
    }
    INSPECT = next;
  }
  function reopenInspect(target, quiet) {
    if (!target) return;
    var keep = INSPECT_STACK;
    INSPECT = null;
    if (target.kind === "item") openItemDrawer(target.id, quiet);
    else if (target.kind === "doc") openDocDrawer(target.id, target.route);
    else if (target.kind === "commit") openCommitDrawer(target.c);
    else if (target.kind === "log") openLogDrawer(target.log);
    else if (target.kind === "finding") openFindingDrawer(target.a);
    INSPECT_STACK = keep;
  }
  function inspectBack() {
    var prev = INSPECT_STACK.pop();
    if (prev) reopenInspect(prev, true);
  }
  // Rows and cards carrying data-inspect="<id>" light up while their item is inspected.
  function markSelected() {
    var cur = INSPECT && INSPECT.kind === "item" && isDocked() && PANEL.tab === "item" ? INSPECT.id : null;
    [].forEach.call(document.querySelectorAll("[data-inspect]"), function (n) {
      var on = n.getAttribute("data-inspect") === cur;
      n.classList.toggle("kbd-sel", on);
      if (n.hasAttribute("aria-selected") || on) n.setAttribute("aria-selected", on ? "true" : "false");
    });
  }
  function startInspectorResize(e) {
    if (!isDocked()) return;
    e.preventDefault();
    var grip = e.currentTarget;
    grip.classList.add("drag");
    function move(ev) {
      var w = Math.max(320, Math.min(window.innerWidth * 0.6, window.innerWidth - ev.clientX));
      document.documentElement.style.setProperty("--insp-w", Math.round(w) + "px");
    }
    function up() {
      grip.classList.remove("drag");
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      var w = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--insp-w"), 10);
      try { if (w) localStorage.setItem("nuhut-insp-w", String(w)); } catch (err) {}
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  var lastWide = wide();
  window.addEventListener("resize", function () {
    if (wide() === lastWide) return;
    lastWide = wide();
    renderPanel({ quiet: true });
  });

  function openItemDrawer(id, quiet) {
    var it = ITEMS[id];
    if (!it) return;
    setInspect({ kind: "item", id: id });
    var container = el("div", { style: "display: flex; flex-direction: column; height: 100%;" });

    var hdr = el("div", { cls: "drawer-header" }, [
      el("div", { style: "display: flex; align-items: baseline; gap: 8px; min-width: 0;" }, [
        el("strong", { style: "font-size: 15px;", text: id }),
        link("Thread ↗", "threads/" + id, "chip"),
        link("Full page ↗", "item/" + id, "chip")
      ]),
      el("button", { cls: "drawer-close", "aria-label": "Close inspector drawer", text: "✕", on: { click: closeDrawer } })
    ]);
    container.appendChild(hdr);

    var body = el("div", { cls: "drawer-body" });
    body.appendChild(el("h2", { cls: "insp-title", title: it.title || "", text: it.title || "(untitled)" }));

    var chips = el("div", { style: "margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 4px;" });
    chips.appendChild(colChip(it.column));
    if (it.status && it.status !== it.column) chips.appendChild(el("span", { cls: "chip", text: it.status }));
    if (it.tier) chips.appendChild(el("span", { cls: "chip", text: "Tier " + it.tier }));
    if (it.owner) chips.appendChild(el("span", { cls: "chip", text: it.owner }));
    body.appendChild(chips);

    var steps = el("div", { cls: "steps", style: "margin-bottom: 12px;", title: "Lifecycle progress" });
    M.steps.forEach(function (s) {
      var st = (it.steps || {})[s] || "n/a";
      steps.appendChild(el("span", { cls: "step " + (st === "n/a" ? "na" : st), text: s + (st === "missing" ? " ?" : "") }));
    });
    body.appendChild(steps);

    // The same diagnosis the Inbox's command dock leads with.
    var nextDiag = diagnoseNextAction(it);
    var drawerNext = {
      tone: nextDiag.kind === "warn" ? "warn" : (nextDiag.kind === "ok" ? "ok" : ""),
      badge: nextDiag.kind === "warn" ? "Needs attention" : (nextDiag.kind === "ok" ? "On track" : "Next step"),
      title: nextDiag.label,
      why: (nextDiag.why ? "Why: " + nextDiag.why + ". " : "") + (nextDiag.desc || ""),
      cmd: nextDiag.cmd,
      runSub: nextDiag.runPayload
    };
    var drawerActionBox = el("div", {
      style: "margin-bottom: 12px; padding: 10px 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 6px;"
    }, [
      el("div", { style: "display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px;" }, [
        el("span", { style: "font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted);", text: "Recommended Next Action" }),
        el("span", { cls: "stamp " + (drawerNext.tone === "warn" ? "warn" : "ok"), text: drawerNext.badge })
      ]),
      el("div", { style: "font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 3px;", text: drawerNext.title }),
      el("div", { cls: "muted", style: "font-size: 12px; margin-bottom: 8px;", text: drawerNext.why }),
      el("div", { style: "padding: 6px 8px; background: var(--bg); border: 1px solid var(--line); border-radius: 4px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; color: var(--text); overflow-x: auto; white-space: nowrap; margin-bottom: 8px;" }, [
        el("span", { style: "color: var(--accent); font-weight: 700; margin-right: 6px;", text: "$" }),
        el("span", { text: drawerNext.cmd })
      ]),
      el("div", { style: "display: flex; align-items: center; gap: 6px; flex-wrap: wrap;" }, [
        LIVE && M.action_token && drawerNext.runSub ? el("button", {
          cls: "btn primary",
          style: "font-size: 11px; padding: 4px 10px;",
          text: "▶ Run in Project",
          on: { click: function () {
            closeDrawer();
            THREAD_STATE.selectedId = id;
            THREAD_STATE.cmdTab = "recommended";
            go("threads/" + id);
            setTimeout(function () {
              runKitCmd(drawerNext.runSub, drawerNext.cmd, nextDiag.label);
            }, 60);
          } }
        }) : null,
        el("button", {
          cls: "btn" + (!(LIVE && M.action_token && drawerNext.runSub) ? " primary" : ""),
          style: "font-size: 11px; padding: 4px 10px;",
          text: "⧉ Copy CLI Command",
          on: { click: function (ev) {
            var b = ev.currentTarget;
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(drawerNext.cmd).then(function () {
                b.textContent = "✓ Copied!";
                showKitToast("Copied: " + drawerNext.cmd, false);
                setTimeout(function () { b.textContent = "⧉ Copy CLI Command"; }, 1800);
              });
            }
          } }
        }),
        el("button", {
          cls: "btn",
          style: "font-size: 11px; padding: 4px 10px;",
          text: "Thread ↗",
          on: { click: function () {
            closeDrawer();
            THREAD_STATE.selectedId = id;
            go("threads/" + id);
          } }
        })
      ])
    ]);
    body.appendChild(drawerActionBox);

    var proof = el("div", { cls: "proof", style: "margin-bottom: 12px;" });
    if (it.author) proof.appendChild(el("div", null, [el("span", { cls: "muted", text: "Author: " }), it.author]));
    (it.reviews || []).forEach(function (r) {
      proof.appendChild(el("div", null, [
        el("span", { cls: "muted", text: (r.stage === "design" ? "Design" : "Ship") + " review: " }),
        r.reviewer + " ",
        el("span", { cls: "stamp " + (r.independent ? "ok" : "warn"),
          text: r.independent ? "INDEPENDENT" : "SELF-CHECK" }),
        el("span", { cls: "muted", text: "  " + r.file })]));
    });
    if ((it.evidence || []).length) {
      var ev = el("div", null, [el("span", { cls: "muted", text: "Evidence: " })]);
      it.evidence.forEach(function (e, n) {
        if (n) ev.appendChild(document.createTextNode(" · "));
        ev.appendChild(el("span", { cls: "stamp " + (/pass/.test(e.result) ? "ok" : (/fail/.test(e.result) ? "bad" : "neutral")),
          text: e.stage + " " + (/pass/.test(e.result) ? "PASS" : "FAIL"),
          title: e.result + " at " + e.commit + (e.dirty ? " (uncommitted change)" : "") + ", " + e.time }));
      });
      proof.appendChild(ev);
    } else if (it.steps && it.steps.Verify === "missing") {
      proof.appendChild(el("div", { cls: "muted", text: "Evidence: no sdlc.py verify run recorded for this item's commits" }));
    }
    if (proof.childNodes.length) body.appendChild(proof);

    var openBlocked = (it.depends || []).filter(function (d) { return !ITEMS[d] || ITEMS[d].column !== "Done"; });
    var openDependents = (it.dependents || []).filter(function (d) { return ITEMS[d] && ITEMS[d].column !== "Done"; });

    if (openBlocked.length && it.column !== "Done") {
      body.appendChild(el("div", {
        cls: "banner bad",
        style: "margin-bottom: 12px; padding: 8px 12px; font-size: 12px;"
      }, [
        el("strong", { text: "Blocked: " }),
        document.createTextNode("Waiting on " + openBlocked.join(", ") + " before this can finish.")
      ]));
    } else if (openDependents.length && it.column !== "Done") {
      body.appendChild(el("div", {
        cls: "banner",
        style: "margin-bottom: 12px; padding: 8px 12px; font-size: 12px; background: var(--warnbg); border-color: var(--warn); color: var(--text);"
      }, [
        el("strong", { text: "Active Blocker: " }),
        document.createTextNode("Holding up " + openDependents.length + " downstream item" + (openDependents.length === 1 ? "" : "s") + " (" + openDependents.join(", ") + ").")
      ]));
    }

    if ((it.depends && it.depends.length) || (it.dependents && it.dependents.length)) {
      var depCard = el("div", {
        style: "margin-bottom: 14px; padding: 10px; background: var(--panel); border: 1px solid var(--line); border-radius: 6px;"
      });
      depCard.appendChild(el("div", {
        style: "font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--muted); margin-bottom: 8px; letter-spacing: 0.05em;",
        text: "Dependency Flow & Blockages"
      }));

      var depCols = el("div", { style: "display: grid; grid-template-columns: 1fr 1fr; gap: 8px;" });

      var leftCol = el("div");
      leftCol.appendChild(el("div", { style: "font-size: 11px; font-weight: 600; margin-bottom: 4px;", text: "Prerequisites (" + (it.depends ? it.depends.length : 0) + ")" }));
      if (it.depends && it.depends.length) {
        it.depends.forEach(function (d) {
          var dIt = ITEMS[d];
          var row = el("div", {
            style: "display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; margin-bottom: 3px; background: var(--bg); border: 1px solid var(--line); border-radius: 4px; font-size: 11px; cursor: pointer;",
            on: { click: function () { openItemDrawer(d); } }
          }, [
            el("span", { style: "font-weight: 500;", text: d }),
            dIt ? colChip(dIt.column) : el("span", { cls: "chip", style: "color: var(--bad);", text: "missing" })
          ]);
          makeInteractive(row, function () { openItemDrawer(d); }, "Inspect prerequisite " + d);
          leftCol.appendChild(row);
        });
      } else {
        leftCol.appendChild(el("div", { cls: "muted", style: "font-size: 11px;", text: "None (independent)" }));
      }
      depCols.appendChild(leftCol);

      var rightCol = el("div");
      rightCol.appendChild(el("div", { style: "font-size: 11px; font-weight: 600; margin-bottom: 4px;", text: "Blocks (" + (it.dependents ? it.dependents.length : 0) + ")" }));
      if (it.dependents && it.dependents.length) {
        it.dependents.forEach(function (d) {
          var dIt = ITEMS[d];
          var row = el("div", {
            style: "display: flex; align-items: center; justify-content: space-between; padding: 3px 6px; margin-bottom: 3px; background: var(--bg); border: 1px solid var(--line); border-radius: 4px; font-size: 11px; cursor: pointer;",
            on: { click: function () { openItemDrawer(d); } }
          }, [
            el("span", { style: "font-weight: 500;", text: d }),
            dIt ? colChip(dIt.column) : el("span", { cls: "chip", style: "color: var(--bad);", text: "missing" })
          ]);
          makeInteractive(row, function () { openItemDrawer(d); }, "Inspect dependent " + d);
          rightCol.appendChild(row);
        });
      } else {
        rightCol.appendChild(el("div", { cls: "muted", style: "font-size: 11px;", text: "None (end node)" }));
      }
      depCols.appendChild(rightCol);

      depCard.appendChild(depCols);
      body.appendChild(depCard);
    }

    var wl = (it.worklog || []), records = (it.records || []), mentions = (it.mentioned_in || []), commits = (it.commits || []);
    var dTab = "overview";
    var dTabs = [["overview", "Overview"], ["worklog", "Worklog (" + wl.length + ")"],
                 ["records", "Records (" + records.length + ")"], ["mentions", "Mentions (" + mentions.length + ")"],
                 ["commits", "Commits (" + commits.length + ")"]];
    var tabContent = el("div");
    function renderTabContent() {
      tabContent.textContent = "";
      if (dTab === "overview") {
        var t = el("table");
        [["Task", it.title], ["Tier", it.tier], ["Owner role", it.owner], ["Depends on", it.depends_text],
         ["Status", it.status], ["Backlog section", it.section]].concat(Object.keys(it.extra || {}).map(function (k) { return [k, it.extra[k]]; }))
          .forEach(function (r) { if (r[1]) t.appendChild(el("tr", null, [el("th", { text: r[0] }), el("td", null, [inline(r[1])])])); });
        tabContent.appendChild(t);
      } else if (dTab === "worklog") {
        if (!wl.length) tabContent.appendChild(el("p", { cls: "muted", text: "No worklog entry." }));
        wl.forEach(function (n) { tabContent.appendChild(entryBox(n, false)); });
      } else if (dTab === "records") {
        if (!records.length) tabContent.appendChild(el("p", { cls: "muted", text: "No record files found." }));
        records.forEach(function (n) {
          var d = DOCS[n];
          tabContent.appendChild(el("h3", null, [link(d.path, docRoute(n))]));
        });
      } else if (dTab === "mentions") {
        if (!mentions.length) tabContent.appendChild(el("p", { cls: "muted", text: "No other record mentions this item." }));
        else {
          var mul = el("ul");
          mentions.forEach(function (n) { mul.appendChild(el("li", null, [link(DOCS[n].path, docRoute(n))])); });
          tabContent.appendChild(mul);
        }
      } else if (dTab === "commits") {
        if (!commits.length) tabContent.appendChild(el("p", { cls: "muted", text: "No commits linked." }));
        else {
          var ct = el("table", null, [el("tr", null, ["SHA", "Date", "Subject"].map(function (x) { return el("th", { text: x }); }))]);
          commits.forEach(function (c) {
            ct.appendChild(el("tr", null, [el("td", null, [el("code", { text: c.sha })]), el("td", { text: c.date }), el("td", null, [inline(c.subject)])]));
          });
          tabContent.appendChild(ct);
        }
      }
    }

    var tabsBar = el("div", { cls: "tabsbar", role: "tablist", style: "margin-top: 8px;" });
    dTabs.forEach(function (tb) {
      var a = el("a", {
        cls: dTab === tb[0] ? "on" : "",
        href: "#",
        role: "tab",
        "aria-selected": dTab === tb[0] ? "true" : "false",
        text: tb[1],
        on: { click: function (e) {
          e.preventDefault();
          dTab = tb[0];
          [].forEach.call(tabsBar.querySelectorAll("a"), function (x, idx) {
            var isSel = dTabs[idx][0] === dTab;
            x.className = isSel ? "on" : "";
            x.setAttribute("aria-selected", isSel ? "true" : "false");
          });
          renderTabContent();
        } }
      });
      tabsBar.appendChild(a);
    });
    body.appendChild(tabsBar);
    body.appendChild(tabContent);
    renderTabContent();

    container.appendChild(body);
    openDrawer(container, { quiet: quiet });
  }

  function openDocDrawer(fullPath, route) {
    var n = DOC_BY_PATH[fullPath.split("#")[0]];
    if (n === undefined) { go(route); return; }
    setInspect({ kind: "doc", id: fullPath, route: route });
    var d = DOCS[n];
    var container = el("div", { style: "display: flex; flex-direction: column; height: 100%;" });
    var hdr = el("div", { cls: "drawer-header" }, [
      el("div", { style: "display: flex; align-items: baseline; gap: 8px; min-width: 0;" }, [
        el("strong", { style: "font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;", text: d.path.split("/").pop() }),
        link("Open doc ↗", route, "chip")
      ]),
      el("button", { cls: "drawer-close", "aria-label": "Close document drawer", text: "✕", on: { click: closeDrawer } })
    ]);
    container.appendChild(hdr);
    var body = el("div", { cls: "drawer-body" });
    body.appendChild(el("div", { cls: "muted", style: "margin-bottom: 8px; font-size: 12px;", text: d.path }));
    var outline = el("div", { style: "margin-bottom: 16px;" });
    d.headings.forEach(function (x) {
      var a = link(x.text, docRoute(n, x.line));
      a.style.display = "block";
      a.style.padding = "2px 0 2px " + ((x.level - 1) * 12) + "px";
      a.style.fontSize = "13px";
      outline.appendChild(a);
    });
    body.appendChild(el("h3", { text: "Sections" }));
    body.appendChild(outline);
    container.appendChild(body);
    openDrawer(container);
  }


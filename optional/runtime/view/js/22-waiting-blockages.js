  // ---------------------------------------------------------------- waiting & blockages
  var BLOCKAGE_STATE = { view: "flow", query: "", filter: "all", tier: "" };

  function viewWaiting() {
    tab("waiting");
    crumbs([[M.project || "Project", "dashboard"], ["Dependencies & Blockages"]]);
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [
        el("h1", { text: "Dependencies & Blockages" }),
        el("p", { cls: "view-subtitle", text: "Track critical root bottlenecks, technical task prerequisites, and parked items waiting on human decisions." })
      ]),
      el("div", { cls: "view-header-actions" }, [
        el("button", { cls: "btn", text: "Inbox ↗", on: { click: function () { go("threads"); } } })
      ])
    ]));

    var depsData = computeDependencies();
    var blockers = depsData.blockers || [];
    var blockedItems = depsData.blockedItems || [];
    var readyItems = depsData.readyItems || [];

    var parkedHumanIds = M.order.filter(function (id) {
      return ["Parked", "Blocked"].indexOf(ITEMS[id].column) >= 0;
    });
    parkedHumanIds.sort(function (a, b) {
      return (daysSince(ITEMS[b].extra.Since) || 0) - (daysSince(ITEMS[a].extra.Since) || 0);
    });

    function toggleFilter(target) {
      BLOCKAGE_STATE.filter = (BLOCKAGE_STATE.filter === target ? "all" : target);
      render();
    }

    var strip = el("div", { cls: "strip" });

    var sBlk = el("div", {
      cls: "stat clickable" + (BLOCKAGE_STATE.filter === "blockers" ? " active" : ""),
      title: "Click to filter Root Bottlenecks",
      "aria-pressed": BLOCKAGE_STATE.filter === "blockers" ? "true" : "false",
      on: { click: function () { toggleFilter("blockers"); } }
    }, [
      el("b", { text: String(blockers.length) }),
      el("span", { text: "Root Bottlenecks" }),
      BLOCKAGE_STATE.filter === "blockers" ? el("span", { cls: "stat-filter-badge", text: "ACTIVE" }) : null
    ]);
    makeInteractive(sBlk, function () { toggleFilter("blockers"); }, "Filter Root Bottlenecks");
    strip.appendChild(sBlk);

    var sWait = el("div", {
      cls: "stat clickable" + (BLOCKAGE_STATE.filter === "blocked" ? " active" : ""),
      title: "Click to filter Blocked Work Items",
      "aria-pressed": BLOCKAGE_STATE.filter === "blocked" ? "true" : "false",
      on: { click: function () { toggleFilter("blocked"); } }
    }, [
      el("b", { text: String(blockedItems.length) }),
      el("span", { text: "Blocked Work Items" }),
      BLOCKAGE_STATE.filter === "blocked" ? el("span", { cls: "stat-filter-badge", text: "ACTIVE" }) : null
    ]);
    makeInteractive(sWait, function () { toggleFilter("blocked"); }, "Filter Blocked Work Items");
    strip.appendChild(sWait);

    var sHuman = el("div", {
      cls: "stat clickable" + (BLOCKAGE_STATE.filter === "human" ? " active" : ""),
      title: "Click to filter items Waiting on Human",
      "aria-pressed": BLOCKAGE_STATE.filter === "human" ? "true" : "false",
      on: { click: function () { toggleFilter("human"); } }
    }, [
      el("b", { text: String(parkedHumanIds.length) }),
      el("span", { text: "Waiting on Human" }),
      BLOCKAGE_STATE.filter === "human" ? el("span", { cls: "stat-filter-badge", text: "ACTIVE" }) : null
    ]);
    makeInteractive(sHuman, function () { toggleFilter("human"); }, "Filter Waiting on Human");
    strip.appendChild(sHuman);

    var sReady = el("div", {
      cls: "stat clickable" + (BLOCKAGE_STATE.filter === "ready" ? " active" : ""),
      title: "Click to filter Ready items (0 blockers)",
      "aria-pressed": BLOCKAGE_STATE.filter === "ready" ? "true" : "false",
      on: { click: function () { toggleFilter("ready"); } }
    }, [
      el("b", { text: String(readyItems.length) }),
      el("span", { text: "Ready to Start" }),
      BLOCKAGE_STATE.filter === "ready" ? el("span", { cls: "stat-filter-badge", text: "ACTIVE" }) : null
    ]);
    makeInteractive(sReady, function () { toggleFilter("ready"); }, "Filter Ready to Start");
    strip.appendChild(sReady);

    if (blockers.length) {
      var topBlk = blockers[0];
      var sBlast = el("div", { cls: "stat", title: "Task with highest downstream impact" }, [
        el("b", { text: topBlk.id + " (blocks " + topBlk.count + ")" }),
        el("span", { text: "Top Blast Radius" })
      ]);
      strip.appendChild(sBlast);
    }

    main.appendChild(strip);

    var viewSwitcher = el("div", { cls: "view-segmented" }, [
      el("button", {
        cls: (BLOCKAGE_STATE.view === "flow" ? "active" : ""),
        "aria-pressed": BLOCKAGE_STATE.view === "flow" ? "true" : "false",
        text: "Flow Graph",
        on: { click: function () { BLOCKAGE_STATE.view = "flow"; render(); } }
      }),
      el("button", {
        cls: (BLOCKAGE_STATE.view === "matrix" ? "active" : ""),
        "aria-pressed": BLOCKAGE_STATE.view === "matrix" ? "true" : "false",
        text: "Blocker Matrix",
        on: { click: function () { BLOCKAGE_STATE.view = "matrix"; render(); } }
      }),
      el("button", {
        cls: (BLOCKAGE_STATE.view === "table" ? "active" : ""),
        "aria-pressed": BLOCKAGE_STATE.view === "table" ? "true" : "false",
        text: "Table",
        on: { click: function () { BLOCKAGE_STATE.view = "table"; render(); } }
      })
    ]);

    var tierSel = el("select", {
      cls: "filter-select",
      "aria-label": "Filter by Tier",
      on: { change: function () { BLOCKAGE_STATE.tier = tierSel.value; renderBlockageContent(); } }
    }, [
      el("option", { value: "", text: "All Tiers" }),
      el("option", { value: "1", text: "Tier 1 (High Risk)" }),
      el("option", { value: "2", text: "Tier 2 (Medium Risk)" }),
      el("option", { value: "3", text: "Tier 3 (Low Risk)" })
    ]);
    tierSel.value = BLOCKAGE_STATE.tier || "";

    var qInput = el("input", {
      type: "search",
      cls: "filter-input",
      placeholder: "Filter items, titles, owners…",
      value: BLOCKAGE_STATE.query,
      style: "flex: 1 1 200px; max-width: 280px;",
      on: { input: function () { BLOCKAGE_STATE.query = qInput.value; renderBlockageContent(); } }
    });

    var rightControls = [tierSel, qInput];
    if (BLOCKAGE_STATE.filter !== "all") {
      var clearBtn = el("button", {
        cls: "preset-btn active",
        text: "✕ Filter: " + BLOCKAGE_STATE.filter,
        on: { click: function () { BLOCKAGE_STATE.filter = "all"; render(); } }
      });
      rightControls.unshift(clearBtn);
    }

    main.appendChild(el("div", { cls: "sub-toolbar" }, [
      el("div", { cls: "sub-toolbar-left" }, [viewSwitcher]),
      el("div", { cls: "sub-toolbar-right" }, rightControls)
    ]));

    var contentContainer = el("div");
    main.appendChild(contentContainer);

    function itemMatches(id, needle) {
      var it = ITEMS[id];
      if (BLOCKAGE_STATE.tier && (!it || String(it.tier) !== String(BLOCKAGE_STATE.tier))) return false;
      if (!needle) return true;
      if (!it) return id.toLowerCase().indexOf(needle) >= 0;
      if (id.toLowerCase().indexOf(needle) >= 0) return true;
      if ((it.title || "").toLowerCase().indexOf(needle) >= 0) return true;
      if ((it.owner || "").toLowerCase().indexOf(needle) >= 0) return true;
      return false;
    }

    function renderBlockageContent() {
      contentContainer.textContent = "";
      var needle = (BLOCKAGE_STATE.query || "").trim().toLowerCase();

      var fBlockers = blockers.filter(function (b) {
        if (itemMatches(b.id, needle)) return true;
        return (b.dependents || []).some(function (depId) { return itemMatches(depId, needle); });
      });

      var fBlocked = blockedItems.filter(function (b) {
        if (itemMatches(b.id, needle)) return true;
        return (b.dependencies || []).some(function (depId) { return itemMatches(depId, needle); });
      });

      var fHuman = parkedHumanIds.filter(function (id) {
        if (itemMatches(id, needle)) return true;
        var it = ITEMS[id], x = it.extra || {};
        var desc = (x["Waiting on whom"] || "") + " " + (x["For what decision"] || "") + " " + (x["For what"] || "");
        return desc.toLowerCase().indexOf(needle) >= 0;
      });

      var fReady = readyItems.filter(function (id) {
        return itemMatches(id, needle);
      });

      if (BLOCKAGE_STATE.view === "flow") {
        var flow = el("div", { cls: "dep-flow" });

        // Show/hide or highlight columns based on active filter
        var showCol1 = BLOCKAGE_STATE.filter === "all" || BLOCKAGE_STATE.filter === "blockers";
        var showCol2 = BLOCKAGE_STATE.filter === "all" || BLOCKAGE_STATE.filter === "blocked";
        var showCol3 = BLOCKAGE_STATE.filter === "all" || BLOCKAGE_STATE.filter === "human";

        if (showCol1) {
          var col1 = el("div", { cls: "dep-col" + (BLOCKAGE_STATE.filter === "blockers" ? " active" : "") });
          col1.appendChild(el("div", { cls: "dep-col-hdr" }, [
            el("span", { text: "Root Blockers (Prerequisites)" }),
            el("span", { cls: "chip", text: String(fBlockers.length) })
          ]));
          col1.appendChild(el("p", { cls: "dep-col-desc", text: "Active tasks that other items are waiting on. Complete these to unblock downstream work." }));

          if (!fBlockers.length) {
            col1.appendChild(el("p", { cls: "muted", style: "font-size: 13px;", text: "No active root bottlenecks matching filter." }));
          } else {
            fBlockers.forEach(function (b) {
              var it = ITEMS[b.id] || {};
              var card = el("div", {
                cls: "dep-card is-blocker",
                on: { click: function () { openItemDrawer(b.id); } }
              });
              var topRow = el("div", { style: "display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;" }, [
                el("span", null, [itemLink(b.id), " ", colChip(it.column)]),
                it.owner ? el("span", { cls: "chip", text: it.owner }) : null
              ]);
              var title = el("div", { style: "font-weight: 600; font-size: 13px; margin: 3px 0 6px;", text: it.title || b.id });
              var badge = el("div", { cls: "dep-blast-badge", text: "Blocks " + b.count + " downstream item" + (b.count > 1 ? "s" : "") });

              var chips = el("div", { cls: "dep-chip-list" });
              chips.appendChild(el("span", { cls: "muted", style: "font-size: 11px; align-self: center; margin-right: 2px;", text: "↳ Blocks:" }));
              (b.dependents || []).forEach(function (depId) {
                var depIt = ITEMS[depId];
                var c = el("a", {
                  cls: "dep-chip" + (depIt && depIt.column === "Done" ? " done" : " active"),
                  href: "#/item/" + depId,
                  title: depIt ? (depId + ": " + depIt.title + " (" + depIt.column + ")") : depId,
                  on: { click: function (e) { e.stopPropagation(); openItemDrawer(depId); } }
                }, [
                  el("strong", { text: depId }),
                  depIt ? el("span", { cls: "muted", text: "· " + depIt.column }) : null
                ]);
                chips.appendChild(c);
              });

              card.appendChild(topRow);
              card.appendChild(title);
              card.appendChild(badge);
              card.appendChild(chips);
              makeInteractive(card, function () { openItemDrawer(b.id); }, "Inspect root blocker " + b.id);
              col1.appendChild(card);
            });
          }
          flow.appendChild(col1);
        }

        if (showCol2) {
          var col2 = el("div", { cls: "dep-col" + (BLOCKAGE_STATE.filter === "blocked" ? " active" : "") });
          col2.appendChild(el("div", { cls: "dep-col-hdr" }, [
            el("span", { text: "Blocked Tasks" }),
            el("span", { cls: "chip", text: String(fBlocked.length) })
          ]));
          col2.appendChild(el("p", { cls: "dep-col-desc", text: "Tasks that cannot proceed because technical prerequisites are incomplete." }));

          if (!fBlocked.length) {
            col2.appendChild(el("p", { cls: "muted", style: "font-size: 13px;", text: "No blocked work items matching filter." }));
          } else {
            fBlocked.forEach(function (b) {
              var it = ITEMS[b.id] || {};
              var card = el("div", {
                cls: "dep-card is-blocked",
                on: { click: function () { openItemDrawer(b.id); } }
              });
              var topRow = el("div", { style: "display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;" }, [
                el("span", null, [itemLink(b.id), " ", colChip(it.column)]),
                it.owner ? el("span", { cls: "chip", text: it.owner }) : null
              ]);
              var title = el("div", { style: "font-weight: 600; font-size: 13px; margin: 3px 0 6px;", text: it.title || b.id });
              var badge = el("div", { cls: "dep-blocked-badge", text: "Waits on " + b.count + " prerequisite" + (b.count > 1 ? "s" : "") });

              var chips = el("div", { cls: "dep-chip-list" });
              chips.appendChild(el("span", { cls: "muted", style: "font-size: 11px; align-self: center; margin-right: 2px;", text: "Prerequisites:" }));
              (b.dependencies || []).forEach(function (depId) {
                var depIt = ITEMS[depId];
                var statusClass = !depIt ? " missing" : (depIt.column === "Done" ? " done" : " active");
                var statusLabel = !depIt ? "missing in backlog" : (depIt.column + (depIt.owner ? " · " + depIt.owner : ""));
                var c = el("a", {
                  cls: "dep-chip" + statusClass,
                  href: "#/item/" + depId,
                  title: depIt ? (depId + ": " + depIt.title + " (" + statusLabel + ")") : (depId + " (missing in backlog!)"),
                  on: { click: function (e) { e.stopPropagation(); openItemDrawer(depId); } }
                }, [
                  el("strong", { text: depId }),
                  el("span", { cls: "muted", text: "· " + statusLabel })
                ]);
                chips.appendChild(c);
              });

              card.appendChild(topRow);
              card.appendChild(title);
              card.appendChild(badge);
              card.appendChild(chips);
              makeInteractive(card, function () { openItemDrawer(b.id); }, "Inspect blocked item " + b.id);
              col2.appendChild(card);
            });
          }
          flow.appendChild(col2);
        }

        if (showCol3) {
          var col3 = el("div", { cls: "dep-col" + (BLOCKAGE_STATE.filter === "human" ? " active" : "") });
          col3.appendChild(el("div", { cls: "dep-col-hdr" }, [
            el("span", { text: "Waiting on Human" }),
            el("span", { cls: "chip", text: String(fHuman.length) })
          ]));
          col3.appendChild(el("p", { cls: "dep-col-desc", text: "Parked items waiting for human input, API keys, credentials, or architectural review." }));

          if (!fHuman.length) {
            col3.appendChild(el("p", { cls: "muted", style: "font-size: 13px;", text: "Nothing is waiting on a human." }));
          } else {
            fHuman.forEach(function (id) {
              var it = ITEMS[id] || {}, x = it.extra || {}, d = daysSince(x.Since);
              var card = el("div", {
                cls: "dep-card is-parked",
                on: { click: function () { openItemDrawer(id); } }
              });
              var topRow = el("div", { style: "display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;" }, [
                el("span", null, [itemLink(id), " ", colChip(it.column)]),
                d !== null ? el("span", { cls: "chip", style: "background: var(--warnbg); color: var(--warn); font-weight: 600;", text: d + "d waiting" }) : null
              ]);
              var title = el("div", { style: "font-weight: 600; font-size: 13px; margin: 3px 0 6px;", text: it.title || id });

              var details = el("div", { style: "font-size: 12px; line-height: 1.4; color: var(--text);" }, [
                (x["Waiting on whom"] || x["Who can unblock"]) ? el("div", null, [
                  el("span", { cls: "muted", text: "Waiting on: " }),
                  el("strong", { text: x["Waiting on whom"] || x["Who can unblock"] })
                ]) : null,
                (x["For what decision"] || x["For what"]) ? el("div", null, [
                  el("span", { cls: "muted", text: "For what: " }),
                  el("span", { text: x["For what decision"] || x["For what"] })
                ]) : null,
                x.Since ? el("div", { cls: "muted", style: "font-size: 11px; margin-top: 3px;", text: "Since: " + x.Since }) : null
              ]);

              card.appendChild(topRow);
              card.appendChild(title);
              card.appendChild(details);
              makeInteractive(card, function () { openItemDrawer(id); }, "Inspect parked item " + id);
              col3.appendChild(card);
            });
          }
          flow.appendChild(col3);
        }

        if (BLOCKAGE_STATE.filter === "ready") {
          var col4 = el("div", { cls: "dep-col active" });
          col4.appendChild(el("div", { cls: "dep-col-hdr" }, [
            el("span", { text: "Ready to Start (0 Blockers)" }),
            el("span", { cls: "chip", text: String(fReady.length) })
          ]));
          col4.appendChild(el("p", { cls: "dep-col-desc", text: "Active tasks with no pending technical prerequisites." }));
          if (!fReady.length) {
            col4.appendChild(el("p", { cls: "muted", style: "font-size: 13px;", text: "No ready tasks matching filter." }));
          } else {
            fReady.forEach(function (id) {
              var it = ITEMS[id] || {};
              var card = el("div", { cls: "dep-card", on: { click: function () { openItemDrawer(id); } } });
              card.appendChild(el("div", { style: "display: flex; justify-content: space-between; align-items: center;" }, [
                el("span", null, [itemLink(id), " ", colChip(it.column)]),
                it.owner ? el("span", { cls: "chip", text: it.owner }) : null
              ]));
              card.appendChild(el("div", { style: "font-weight: 600; font-size: 13px; margin: 4px 0;", text: it.title || id }));
              makeInteractive(card, function () { openItemDrawer(id); }, "Inspect ready item " + id);
              col4.appendChild(card);
            });
          }
          flow.appendChild(col4);
        }

        contentContainer.appendChild(flow);

      } else if (BLOCKAGE_STATE.view === "matrix") {
        contentContainer.appendChild(h(2, "Critical Bottleneck Impact Matrix (" + fBlockers.length + ")"));
        if (!fBlockers.length) {
          contentContainer.appendChild(el("p", { cls: "muted", text: "No active bottlenecks matching filter." }));
        } else {
          var mGrid = el("div", { cls: "matrix-grid" });
          fBlockers.forEach(function (b) {
            var it = ITEMS[b.id] || {};
            var card = el("div", { cls: "dep-card is-blocker", on: { click: function () { openItemDrawer(b.id); } } });
            card.appendChild(el("div", { style: "display: flex; justify-content: space-between; align-items: center;" }, [
              el("span", null, [itemLink(b.id), " ", colChip(it.column)]),
              el("span", { cls: "chip", style: "background: var(--warnbg); color: var(--warn); font-weight: 700;", text: "BLAST RADIUS: " + b.count })
            ]));
            card.appendChild(el("div", { style: "font-weight: 600; font-size: 14px; margin: 6px 0;", text: it.title || b.id }));
            if (it.owner) card.appendChild(el("div", { cls: "muted", style: "font-size: 12px; margin-bottom: 6px;", text: "Assigned owner: " + it.owner }));
            card.appendChild(el("div", { cls: "muted", style: "font-size: 12px; margin-bottom: 4px;", text: "Downstream items blocked by this task:" }));
            var dList = el("div", { cls: "dep-chip-list" });
            (b.dependents || []).forEach(function (depId) {
              var depIt = ITEMS[depId];
              dList.appendChild(el("a", {
                cls: "dep-chip" + (depIt && depIt.column === "Done" ? " done" : " active"),
                href: "#/item/" + depId,
                on: { click: function (e) { e.stopPropagation(); openItemDrawer(depId); } }
              }, [
                el("strong", { text: depId }),
                depIt ? el("span", { cls: "muted", text: "· " + clip(depIt.title, 20) }) : null
              ]));
            });
            card.appendChild(dList);
            makeInteractive(card, function () { openItemDrawer(b.id); }, "Inspect bottleneck " + b.id);
            mGrid.appendChild(card);
          });
          contentContainer.appendChild(mGrid);
        }

      } else {
        contentContainer.appendChild(h(2, "Comprehensive Dependencies Table"));
        var allIds = [];
        var seen = {};

        if (BLOCKAGE_STATE.filter === "all" || BLOCKAGE_STATE.filter === "blockers") {
          fBlockers.forEach(function (b) { if (!seen[b.id]) { seen[b.id] = true; allIds.push(b.id); } });
        }
        if (BLOCKAGE_STATE.filter === "all" || BLOCKAGE_STATE.filter === "blocked") {
          fBlocked.forEach(function (b) { if (!seen[b.id]) { seen[b.id] = true; allIds.push(b.id); } });
        }
        if (BLOCKAGE_STATE.filter === "all" || BLOCKAGE_STATE.filter === "human") {
          fHuman.forEach(function (id) { if (!seen[id]) { seen[id] = true; allIds.push(id); } });
        }
        if (BLOCKAGE_STATE.filter === "ready") {
          fReady.forEach(function (id) { if (!seen[id]) { seen[id] = true; allIds.push(id); } });
        }

        if (!allIds.length) {
          contentContainer.appendChild(el("p", { cls: "muted", text: "No items match current filters." }));
        } else {
          var tt = el("table", null, [el("tr", null, ["Item", "State", "Tier", "Owner", "Role in Dependencies", "Prerequisites / Downstream", "Waiting on (Human)", "Since"].map(function (x) {
            return el("th", { text: x });
          }))]);
          allIds.forEach(function (id) {
            var it = ITEMS[id] || {}, x = it.extra || {};
            var blk = blockers.find(function (b) { return b.id === id; });
            var dep = blockedItems.find(function (b) { return b.id === id; });
            var isHuman = parkedHumanIds.indexOf(id) >= 0;

            var roleChips = el("td");
            if (blk) roleChips.appendChild(el("span", { cls: "chip", style: "background: var(--warnbg); color: var(--warn); font-weight: 600; margin-right: 4px;", text: "Blocks " + blk.count }));
            if (dep) roleChips.appendChild(el("span", { cls: "chip", style: "background: var(--badbg); color: var(--bad); font-weight: 600; margin-right: 4px;", text: "Waits on " + dep.count }));
            if (isHuman) roleChips.appendChild(el("span", { cls: "chip", style: "background: var(--chip);", text: "Human" }));

            var linksCell = el("td");
            if (blk && blk.dependents && blk.dependents.length) {
              var blkSpan = el("div", null, [el("span", { cls: "muted", text: "Blocks: " })]);
              blk.dependents.forEach(function (k) { blkSpan.appendChild(itemLink(k)); blkSpan.appendChild(document.createTextNode(" ")); });
              linksCell.appendChild(blkSpan);
            }
            if (dep && dep.dependencies && dep.dependencies.length) {
              var depSpan = el("div", null, [el("span", { cls: "muted", text: "Waits on: " })]);
              dep.dependencies.forEach(function (k) { depSpan.appendChild(itemLink(k)); depSpan.appendChild(document.createTextNode(" ")); });
              linksCell.appendChild(depSpan);
            }

            tt.appendChild(el("tr", null, [
              el("td", null, [itemLink(id), " " + clip(it.title, 50)]),
              el("td", null, [colChip(it.column)]),
              el("td", null, [it.tier ? el("span", { cls: "chip", text: "Tier " + it.tier }) : el("span", { cls: "muted", text: "—" })]),
              el("td", { text: it.owner || "—" }),
              roleChips,
              linksCell,
              el("td", { text: x["Waiting on whom"] || x["Who can unblock"] || (isHuman ? (x["For what decision"] || "") : "—") }),
              el("td", { text: x.Since || "—" })
            ]));
          });
          contentContainer.appendChild(el("div", { cls: "wrap" }, [tt]));
        }
      }
    }

    renderBlockageContent();
  }


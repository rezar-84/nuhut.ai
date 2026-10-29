  // ---------------------------------------------------------------- board
  var FILTER = { owner: "", tier: "", text: "", dropped: false, group: "none", sort: "default" };
  var COLLAPSED_COLS = { Dropped: true, Parked: false };
  var COLLAPSED_SWIMLANES = {};

  function unresolved(it) {
    return (it.depends || []).filter(function (d) { return !ITEMS[d] || ITEMS[d].column !== "Done"; });
  }

  function buildPipsNode(it) {
    var pips = el("div", { cls: "card-pips", role: "img" });
    var stepsDone = 0, missingList = [];
    M.steps.forEach(function (s) {
      var st = (it.steps || {})[s] || "na";
      if (st === "done") stepsDone++;
      if (st === "missing") missingList.push(s);
      pips.appendChild(el("span", {
        cls: "card-pip " + st,
        title: s + ": " + (st === "done" ? "Done" : (st === "missing" ? "Missing record!" : "Pending/NA"))
      }));
    });
    var summaryText = stepsDone + " of " + M.steps.length + " lifecycle steps done" +
      (missingList.length ? "; missing: " + missingList.join(", ") : "");
    pips.setAttribute("aria-label", summaryText);
    pips.setAttribute("title", summaryText);
    var wrap = el("div", { cls: "card-pips-wrap" }, [pips]);
    if (missingList.length) {
      wrap.appendChild(el("span", {
        cls: "stamp bad",
        title: "Missing expected lifecycle records: " + missingList.join(", "),
        text: "MISS: " + missingList.slice(0, 2).join(",") + (missingList.length > 2 ? "+" + (missingList.length - 2) : "")
      }));
    }
    return { node: wrap, stepsDone: stepsDone, missingList: missingList };
  }

  // Days since the item entered its column, from the backlog's Since cell. Work that sits
  // still is the first thing a board should make visible.
  function cardAge(it) {
    var since = ((it.extra || {}).Since || "").match(/[0-9]{4}-[0-9]{2}-[0-9]{2}/);
    if (!since || it.column === "Done" || it.column === "Dropped" || it.column === "Later") return null;
    var days = Math.floor((Date.now() - Date.parse(since[0])) / 86400000);
    if (!(days >= 0)) return null;
    return { text: days + "d", tone: days >= 7 ? "bad" : (days >= 3 ? "warn" : ""), title: "In " + it.column + " for " + days + " day(s), since " + since[0] };
  }

  function card(id) {
    var it = ITEMS[id], open = unresolved(it);
    var pipData = buildPipsNode(it);

    var age = cardAge(it);
    var lastEv = (it.evidence || []).length ? it.evidence[it.evidence.length - 1] : null;
    var c = el("div", {
      id: "card-" + id,
      "data-id": id,
      "data-inspect": id,
      cls: "card" + (open.length && it.column !== "Done" ? " blocked" : ""),
      style: "cursor: pointer;",
      on: { click: function (e) {
        if (e.target.tagName !== "A") { markSeen(id); openItemDrawer(id); }
      } }
    }, [
      el("div", { style: "display: flex; justify-content: space-between; align-items: center; min-width: 0; gap: 6px;" }, [
        el("span", { style: "display: inline-flex; align-items: center; gap: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; font-weight: 600;" }, [
          isUnread(id) ? el("span", { cls: "unread-dot", title: "New activity since you last opened it" }) : null,
          itemLink(id)
        ]),
        el("span", { style: "display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0;" }, [
          lastEv ? el("span", { cls: "note-ic " + (stageBad(lastEv.result) ? "bad" : (stageOk(lastEv.result) ? "ok" : "warn")), style: "margin: 0;",
            title: "Last verify: " + lastEv.stage + " " + lastEv.result }) : null,
          claimOf(id) ? claimChip(claimOf(id)) : null,
          age ? el("span", { cls: "age-badge " + age.tone, title: age.title, text: age.text }) : null,
          el("span", { cls: "muted", style: "font-size: 11px;", text: pipData.stepsDone + "/" + M.steps.length })
        ])
      ]),
      el("div", { cls: "t", text: clip(it.title, 110) }),
      el("div", { style: "display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;" }, [
        it.tier ? el("span", { cls: "chip", text: "Tier " + it.tier }) : null,
        it.owner ? el("span", { cls: "chip", text: it.owner }) : null,
        it.status && it.status !== it.column ? el("span", { cls: "chip", text: it.status }) : null,
        open.length && it.column !== "Done" ? el("span", { cls: "chip", style: "background: var(--badbg); color: var(--bad); font-weight: 500;", text: "waits on " + open.join(", ") }) : null
      ]),
      pipData.node
    ]);
    makeInteractive(c, function () { openItemDrawer(id); }, id + " · " + clip(it.title || "", 60) + " · " + (it.column || ""));
    return c;
  }

  function sortItemIds(ids) {
    var copy = ids.slice();
    if (FILTER.sort === "tier") {
      copy.sort(function (a, b) {
        var ta = ITEMS[a].tier ? +ITEMS[a].tier : 99, tb = ITEMS[b].tier ? +ITEMS[b].tier : 99;
        return ta - tb || a.localeCompare(b);
      });
    } else if (FILTER.sort === "title") {
      copy.sort(function (a, b) {
        return (ITEMS[a].title || "").localeCompare(ITEMS[b].title || "");
      });
    } else if (FILTER.sort === "blocked") {
      copy.sort(function (a, b) {
        var ba = unresolved(ITEMS[a]).length ? 1 : 0;
        var bb = unresolved(ITEMS[b]).length ? 1 : 0;
        return bb - ba || a.localeCompare(b);
      });
    }
    return copy;
  }

  // The count in a column header; with a wip_limit in the charter constraints, Now shows
  // count/limit and turns amber past it.
  function wipCount(c, n) {
    var lim = c === "Now" && M.kit && M.kit.constraints ? +M.kit.constraints.wip_limit || 0 : 0;
    return el("span", { cls: "muted", style: "font-size: 11px; margin-left: 4px;" + (lim && n > lim ? " color: var(--warn); font-weight: 700;" : ""),
      title: lim ? n + " in progress, limit " + lim : n + " item(s)", text: lim ? n + "/" + lim : String(n) });
  }

  // Board keyboard: j/k (↓/↑) within a column, h/l (←/→) across columns. On a wide screen
  // the docked inspector follows; on a narrow one Enter opens it.
  var BOARD_SEL = null;
  function boardKey(e) {
    var cols = [].filter.call(document.querySelectorAll("#main .colm:not(.collapsed)"), function (c) { return c.querySelector(".card[data-inspect]"); });
    if (!cols.length) return false;
    var grid = cols.map(function (c) { return [].map.call(c.querySelectorAll(".card[data-inspect]"), function (n) { return n.getAttribute("data-inspect"); }); });
    var cur = (INSPECT && INSPECT.kind === "item" && isDocked()) ? INSPECT.id : BOARD_SEL;
    var ci = -1, ri = -1;
    grid.forEach(function (ids, i) { var r = ids.indexOf(cur); if (r >= 0) { ci = i; ri = r; } });
    var k = e.key;
    if (k === "Enter" || k === "o") {
      if (!cur) return false;
      if (k === "o") go("item/" + cur); else openItemDrawer(cur);
      return true;
    }
    if (ci < 0) { ci = 0; ri = 0; }
    else if (k === "j" || k === "ArrowDown") ri = Math.min(grid[ci].length - 1, ri + 1);
    else if (k === "k" || k === "ArrowUp") ri = Math.max(0, ri - 1);
    else if (k === "h" || k === "ArrowLeft") { ci = Math.max(0, ci - 1); ri = Math.min(ri, grid[ci].length - 1); }
    else if (k === "l" || k === "ArrowRight") { ci = Math.min(grid.length - 1, ci + 1); ri = Math.min(ri, grid[ci].length - 1); }
    else return false;
    BOARD_SEL = grid[ci][ri];
    [].forEach.call(document.querySelectorAll("#main .card.kbd-sel"), function (n) { n.classList.remove("kbd-sel"); });
    var node = document.querySelector('#main .card[data-inspect="' + BOARD_SEL.replace(/"/g, "") + '"]');
    if (node) { node.classList.add("kbd-sel"); node.scrollIntoView({ block: "nearest", inline: "nearest" }); }
    if (wide()) { markSeen(BOARD_SEL); openItemDrawer(BOARD_SEL, true); }
    return true;
  }

  function renderColumn(c, itemIds, onToggle) {
    var isCollapsed = !!COLLAPSED_COLS[c];
    var hd = el("h3", null, [
      el("span", { text: c }),
      wipCount(c, itemIds.length),
      el("button", {
        cls: "col-collapse-btn",
        text: isCollapsed ? "▸" : "◂",
        title: isCollapsed ? "Expand column" : "Collapse column",
        "aria-label": (isCollapsed ? "Expand " : "Collapse ") + c + " column",
        on: { click: function (e) {
          e.stopPropagation();
          COLLAPSED_COLS[c] = !isCollapsed;
          if (typeof onToggle === "function") onToggle();
          else render();
        } }
      })
    ]);

    var col = el("div", {
      cls: "colm" + (isCollapsed ? " collapsed" : ""),
      title: isCollapsed ? "Click to expand " + c : "",
      on: { click: function () {
        if (isCollapsed) {
          COLLAPSED_COLS[c] = false;
          if (typeof onToggle === "function") onToggle();
          else render();
        }
      } }
    }, [hd]);

    var body = el("div", { cls: "colm-body" });
    sortItemIds(itemIds).forEach(function (id) { body.appendChild(card(id)); });
    if (!itemIds.length) body.appendChild(el("div", { cls: "muted", style: "font-size: 12px; padding: 6px 0;", text: "Nothing here." }));
    col.appendChild(body);
    return col;
  }

  function renderItemTable(itemIds) {
    var sorted = sortItemIds(itemIds);
    var t = el("table", { cls: "board-table" });
    t.appendChild(el("tr", null, [
      el("th", { text: "ID", style: "width: 90px;" }),
      el("th", { text: "Title" }),
      el("th", { text: "Status", style: "width: 100px;" }),
      el("th", { text: "Tier", style: "width: 80px;" }),
      el("th", { text: "Owner", style: "width: 120px;" }),
      el("th", { text: "Lifecycle Progress", style: "width: 150px;" }),
      el("th", { text: "Dependencies" })
    ]));
    if (!sorted.length) {
      t.appendChild(el("tr", null, [
        el("td", { colspan: "7", cls: "muted", style: "text-align: center; padding: 14px;", text: "No items match current filter." })
      ]));
      return el("div", { cls: "wrap" }, [t]);
    }
    sorted.forEach(function (id) {
      var it = ITEMS[id], open = unresolved(it);
      var pipData = buildPipsNode(it);

      var depCell = el("td");
      if (it.depends && it.depends.length) {
        it.depends.forEach(function (d) {
          var depIt = ITEMS[d];
          var isDone = depIt && depIt.column === "Done";
          var chipCls = !depIt ? "missing" : (isDone ? "done" : "active");
          depCell.appendChild(el("a", {
            cls: "dep-chip " + chipCls,
            href: "#/item/" + d,
            on: { click: function (e) { e.stopPropagation(); openItemDrawer(d); } }
          }, [
            el("strong", { text: d }),
            depIt ? el("span", { cls: "muted", text: "· " + depIt.column }) : el("span", { text: "!" })
          ]));
          depCell.appendChild(document.createTextNode(" "));
        });
      } else {
        depCell.appendChild(el("span", { cls: "muted", text: "—" }));
      }

      var tr = el("tr", {
        id: "row-" + id,
        "data-id": id,
        cls: "board-table-row",
        style: "cursor: pointer;",
        on: { click: function (e) {
          if (e.target.tagName !== "A" && !e.target.classList.contains("dep-chip")) {
            openItemDrawer(id);
          }
        } }
      }, [
        el("td", null, [itemLink(id)]),
        el("td", null, [
          el("span", { style: "font-weight: 500;", text: it.title || id }),
          open.length ? el("span", { cls: "chip", style: "background: var(--badbg); color: var(--bad); font-weight: 600; margin-left: 6px;", text: "Blocked by " + open.join(", ") }) : null
        ]),
        el("td", null, [colChip(it.column)]),
        el("td", null, [it.tier ? el("span", { cls: "chip", text: "Tier " + it.tier }) : el("span", { cls: "muted", text: "—" })]),
        el("td", null, [it.owner ? el("span", { text: it.owner }) : el("span", { cls: "muted", text: "—" })]),
        el("td", null, [pipData.node]),
        depCell
      ]);
      makeInteractive(tr, function () { openItemDrawer(id); }, "Inspect " + id);
      t.appendChild(tr);
    });
    return el("div", { cls: "wrap" }, [t]);
  }

  function viewBoard(focusId, stageFilter) {
    tab("board");
    crumbs([[M.project || "Project", "dashboard"], ["Board"]]);
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [
        el("h1", { text: "Backlog & Lifecycle Board" }),
        el("p", { cls: "view-subtitle", text: "Kanban and tabular tracking across all lifecycle columns, swimlanes, risk tiers, and verification pips." })
      ]),
      el("div", { cls: "view-header-actions" }, [
        el("button", { cls: "btn", text: "Inbox ↗", on: { click: function () { go("threads"); } } })
      ])
    ]));

    // Statuses the board has no column for land under Other; say which, instead of
    // leaving a catch-all column to swallow them.
    var unmapped = {};
    M.order.forEach(function (id) { var it = ITEMS[id]; if (it.column === "Other") unmapped[it.status || "(blank)"] = (unmapped[it.status || "(blank)"] || 0) + 1; });
    var unmappedKeys = Object.keys(unmapped).sort(function (a, b) { return unmapped[b] - unmapped[a]; });
    if (unmappedKeys.length) {
      var nOther = unmappedKeys.reduce(function (a, k) { return a + unmapped[k]; }, 0);
      main.appendChild(el("p", { cls: "quiet-note", role: "note" }, [
        plural(nOther, "item") + " sit under Other: their status (" + unmappedKeys.slice(0, 3).join(", ") + (unmappedKeys.length > 3 ? ", …" : "") + ") has no column. ",
        el("a", { href: "#", text: "Details", on: { click: function (e) { e.preventDefault(); showPanel("issues", { quiet: wide() }); } } })
      ]));
    }
    main.appendChild(el("h2", { cls: "sr-only", text: "Columns" }));

    FILTER.view = FILTER.view || "kanban";

    // If an item to focus is specified, ensure it is not hidden by filters/collapses
    if (focusId && ITEMS[focusId]) {
      var targetItem = ITEMS[focusId];
      if (targetItem.column === "Dropped") FILTER.dropped = true;
      if (COLLAPSED_COLS[targetItem.column]) COLLAPSED_COLS[targetItem.column] = false;
      if (FILTER.text && (focusId + " " + (targetItem.title || "")).toLowerCase().indexOf(FILTER.text.toLowerCase()) < 0) {
        FILTER.text = "";
      }
      if (FILTER.owner && targetItem.owner && FILTER.owner !== targetItem.owner) {
        FILTER.owner = "";
      }
      if (FILTER.tier && targetItem.tier && FILTER.tier !== targetItem.tier) {
        FILTER.tier = "";
      }
    }

    var owners = {}, tiers = {};
    M.order.forEach(function (id) { if (ITEMS[id].owner) owners[ITEMS[id].owner] = 1; if (ITEMS[id].tier) tiers[ITEMS[id].tier] = 1; });

    function sel(key, label, values) {
      var s = el("select", { cls: "filter-select", "aria-label": label, on: { change: function () { FILTER[key] = s.value; updateBoardContent(); } } },
        [el("option", { value: "", text: "All " + label })].concat(Object.keys(values).sort().map(function (v) {
          var o = el("option", { value: v, text: v });
          if (FILTER[key] === v) o.selected = true;
          return o;
        })));
      return s;
    }

    var groupOpts = [el("option", { value: "none", text: "Group: None" })];
    if (M.epics && M.epics.length) {
      groupOpts.push(el("option", { value: "epic", text: "Group: By Epic" }));
    }
    groupOpts.push(el("option", { value: "owner", text: "Group: By Owner Role" }));
    groupOpts.push(el("option", { value: "tier", text: "Group: By Risk Tier" }));
    var groupSel = el("select", { cls: "filter-select", "aria-label": "Group by", on: { change: function () { FILTER.group = groupSel.value; updateBoardContent(); } } }, groupOpts);
    if (FILTER.group === "epic" && (!M.epics || !M.epics.length)) {
      FILTER.group = "none";
    }
    groupSel.value = FILTER.group;

    var sortSel = el("select", { cls: "filter-select", "aria-label": "Sort by", on: { change: function () { FILTER.sort = sortSel.value; updateBoardContent(); } } }, [
      el("option", { value: "default", text: "Sort: Backlog order" }),
      el("option", { value: "tier", text: "Sort: Tier (Tier 1 first)" }),
      el("option", { value: "title", text: "Sort: Title (A-Z)" }),
      el("option", { value: "blocked", text: "Sort: Blocked first" })
    ]);
    sortSel.value = FILTER.sort;

    var text = el("input", { type: "search", cls: "filter-input", placeholder: "Filter titles or IDs", "aria-label": "Filter titles or IDs", value: FILTER.text,
      on: { input: function () { FILTER.text = text.value; updateBoardContent(); } } });
    var dropped = el("input", { type: "checkbox", id: "dropped", on: { change: function () { FILTER.dropped = dropped.checked; updateBoardContent(); } } });
    dropped.checked = FILTER.dropped;

    var btnKanban = el("button", {
      cls: (FILTER.view !== "table" ? "active" : ""),
      "aria-pressed": FILTER.view !== "table" ? "true" : "false",
      text: "Board",
      on: { click: function () {
        FILTER.view = "kanban";
        btnKanban.classList.add("active");
        btnKanban.setAttribute("aria-pressed", "true");
        btnTable.classList.remove("active");
        btnTable.setAttribute("aria-pressed", "false");
        updateBoardContent();
      } }
    });
    var btnTable = el("button", {
      cls: (FILTER.view === "table" ? "active" : ""),
      "aria-pressed": FILTER.view === "table" ? "true" : "false",
      text: "Table",
      on: { click: function () {
        FILTER.view = "table";
        btnTable.classList.add("active");
        btnTable.setAttribute("aria-pressed", "true");
        btnKanban.classList.remove("active");
        btnKanban.setAttribute("aria-pressed", "false");
        updateBoardContent();
      } }
    });
    var viewSwitcher = el("div", { cls: "view-segmented" }, [btnKanban, btnTable]);

    main.appendChild(el("div", { cls: "sub-toolbar" }, [
      el("div", { cls: "sub-toolbar-left" }, [viewSwitcher]),
      el("div", { cls: "sub-toolbar-right" }, [
        groupSel,
        sortSel,
        sel("owner", "owner roles", owners),
        sel("tier", "tiers", tiers),
        text,
        el("label", null, [dropped, " show Dropped"])
      ])
    ]));

    var boardContent = el("div", { id: "board-content" });
    main.appendChild(boardContent);

    function itemPasses(id) {
      var it = ITEMS[id];
      return (!FILTER.owner || it.owner === FILTER.owner) &&
        (!FILTER.tier || it.tier === FILTER.tier) &&
        (!FILTER.text || (id + " " + it.title).toLowerCase().indexOf(FILTER.text.toLowerCase()) >= 0);
    }

    function updateBoardContent() {
      boardContent.innerHTML = "";
      if (FILTER.view === "table" && FILTER.group === "none") {
        var passingIds = M.order.filter(function (id) {
          if (ITEMS[id].column === "Dropped" && !FILTER.dropped) return false;
          return itemPasses(id);
        });
        boardContent.appendChild(renderItemTable(passingIds));
        return;
      }

      if (FILTER.group === "none") {
        var board = el("div", { cls: "board" });
        M.columns.forEach(function (c) {
          if (c === "Dropped" && !FILTER.dropped) return;
          var ids = M.order.filter(function (id) {
            return ITEMS[id].column === c && itemPasses(id);
          });
          if (c === "Other" && !ids.length) return;
          board.appendChild(renderColumn(c, ids, updateBoardContent));
        });
        boardContent.appendChild(board);
      } else {
        var groups = [];
        if (FILTER.group === "epic") {
          var assigned = {};
          M.epics.forEach(function (e) {
            e.items.forEach(function (id) { assigned[id] = true; });
            groups.push({ key: "e:" + e.name, title: "Epic: " + e.name, ids: e.items.filter(itemPasses) });
          });
          var unassigned = M.order.filter(function (id) { return !assigned[id] && itemPasses(id); });
          if (unassigned.length) groups.push({ key: "e:none", title: "No Epic", ids: unassigned });
        } else if (FILTER.group === "owner") {
          var byO = {};
          M.order.filter(itemPasses).forEach(function (id) {
            var o = ITEMS[id].owner || "Unassigned";
            (byO[o] = byO[o] || []).push(id);
          });
          Object.keys(byO).sort().forEach(function (o) {
            groups.push({ key: "o:" + o, title: "Owner: " + o, ids: byO[o] });
          });
        } else if (FILTER.group === "tier") {
          var byT = {};
          M.order.filter(itemPasses).forEach(function (id) {
            var t = ITEMS[id].tier ? "Tier " + ITEMS[id].tier : "Untiered";
            (byT[t] = byT[t] || []).push(id);
          });
          ["Tier 1", "Tier 2", "Tier 3", "Untiered"].forEach(function (t) {
            if (byT[t] && byT[t].length) groups.push({ key: "t:" + t, title: t, ids: byT[t] });
          });
        }

        if (!groups.length) {
          boardContent.appendChild(el("p", { cls: "muted", text: "No items match the current filters." }));
          return;
        }

        groups.forEach(function (g) {
          var isCollapsed = !!COLLAPSED_SWIMLANES[g.key];
          if (focusId && g.ids.indexOf(focusId) >= 0 && isCollapsed) {
            COLLAPSED_SWIMLANES[g.key] = false;
            isCollapsed = false;
          }
          var doneCount = g.ids.filter(function (id) { return ITEMS[id].column === "Done"; }).length;
          var pct = g.ids.length ? Math.round((doneCount / g.ids.length) * 100) : 0;

          var progBar = el("div", { cls: "swimlane-progress", title: pct + "% completed (" + doneCount + "/" + g.ids.length + ")" }, [
            el("div", { cls: "swimlane-progress-bar", style: "width: " + pct + "%;" })
          ]);

          var hdr = el("div", {
            cls: "swimlane-hdr",
            on: { click: function () {
              COLLAPSED_SWIMLANES[g.key] = !isCollapsed;
              updateBoardContent();
            } }
          }, [
            el("div", { style: "display: flex; align-items: center; gap: 8px;" }, [
              el("span", { cls: "muted", style: "font-size: 11px;", text: isCollapsed ? "▶" : "▼" }),
              el("strong", { text: g.title }),
              el("span", { cls: "chip", text: String(g.ids.length) }),
              progBar,
              el("span", { cls: "muted", style: "font-size: 12px;", text: pct + "% done" })
            ]),
            el("span", { cls: "muted", style: "font-size: 11px;", text: isCollapsed ? "Click to expand" : "Click to collapse" })
          ]);
          makeInteractive(hdr, function () {
            COLLAPSED_SWIMLANES[g.key] = !isCollapsed;
            updateBoardContent();
          }, (isCollapsed ? "Expand " : "Collapse ") + g.title);

          var swimlane = el("div", { cls: "swimlane" + (isCollapsed ? " collapsed" : "") }, [hdr]);

          if (FILTER.view === "table") {
            var body = el("div", { cls: "swimlane-body", style: "padding: 8px 12px;" });
            body.appendChild(renderItemTable(g.ids));
            swimlane.appendChild(body);
          } else {
            var body = el("div", { cls: "swimlane-body" });
            M.columns.forEach(function (c) {
              if (c === "Dropped" && !FILTER.dropped) return;
              var colIds = g.ids.filter(function (id) { return ITEMS[id].column === c; });
              if (c === "Other" && !colIds.length) return;
              body.appendChild(renderColumn(c, colIds, updateBoardContent));
            });
            swimlane.appendChild(body);
          }
          boardContent.appendChild(swimlane);
        });
      }
    }

    updateBoardContent();

    if (focusId) {
      setTimeout(function () {
        var target = document.getElementById("card-" + focusId) ||
                     document.getElementById("row-" + focusId) ||
                     document.querySelector("[data-id='" + focusId + "']");
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
          target.classList.add("flash");
          setTimeout(function () { target.classList.remove("flash"); }, 2400);
        }
      }, 100);
    }
  }


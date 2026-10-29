  // ---------------------------------------------------------------- map canvas
  var MAP_STATE = {
    scale: 1,
    panX: 30,
    panY: 30,
    query: "",
    preset: "all",
    showMinimap: true,
    totalW: 1000,
    totalH: 600,
    nodes: [],
    links: []
  };

  var currentMapSvg = null;
  var currentViewportG = null;
  var currentMinimapSvg = null;
  var currentMinimapRect = null;
  var currentMatchBadge = null;

  function computeMapLayout() {
    var root = mapTree(), ROW = 26, COLW = 280, rows = 0, maxDepth = 0;
    var nodes = [], links = [];

    var needle = (MAP_STATE.query || "").trim().toLowerCase();
    if (needle) {
      (function markMatches(n) {
        var selfMatch = (n.label && n.label.toLowerCase().indexOf(needle) >= 0) ||
                        (n.full && n.full.toLowerCase().indexOf(needle) >= 0);
        var anyKidMatch = false;
        (n.children || []).forEach(function (k) {
          if (markMatches(k)) anyKidMatch = true;
        });
        n.match = selfMatch;
        n.hasMatchingKid = anyKidMatch;
        if (anyKidMatch || selfMatch) {
          OPEN[n.key] = true;
        }
        return selfMatch || anyKidMatch;
      })(root);
    }

    (function place(n, depth) {
      n.depth = depth;
      maxDepth = Math.max(maxDepth, depth);
      var kids = n.children || [];
      if (kids.length && isOpen(n, depth)) {
        kids.forEach(function (k) { place(k, depth + 1); links.push([n, k]); });
        n.y = (kids[0].y + kids[kids.length - 1].y) / 2;
      } else {
        n.y = rows++ * ROW + 24;
      }
      n.x = depth * COLW + 24;
      nodes.push(n);
    })(root, 0);

    MAP_STATE.totalW = (maxDepth + 1) * COLW + 320;
    MAP_STATE.totalH = rows * ROW + 32;
    MAP_STATE.nodes = nodes;
    MAP_STATE.links = links;
    return { nodes: nodes, links: links, width: MAP_STATE.totalW, height: MAP_STATE.totalH };
  }

  function applyTransform() {
    if (!currentViewportG) return;
    currentViewportG.setAttribute("transform", "translate(" + MAP_STATE.panX + "," + MAP_STATE.panY + ") scale(" + MAP_STATE.scale + ")");
    updateMinimap();
  }

  function fitMapToScreen() {
    var container = document.getElementById("map-container");
    if (!container) return;
    var cw = container.clientWidth || 900, ch = container.clientHeight || 550;
    var scaleX = (cw - 60) / Math.max(100, MAP_STATE.totalW);
    var scaleY = (ch - 60) / Math.max(100, MAP_STATE.totalH);
    MAP_STATE.scale = Math.min(1.15, Math.max(0.18, Math.min(scaleX, scaleY)));
    MAP_STATE.panX = 30;
    MAP_STATE.panY = Math.max(24, (ch - MAP_STATE.totalH * MAP_STATE.scale) / 2);
    applyTransform();
  }

  function updateMinimap() {
    if (!currentMinimapSvg || !currentMinimapRect || !MAP_STATE.showMinimap) return;
    var container = document.getElementById("map-container");
    if (!container) return;
    var cw = container.clientWidth || 900, ch = container.clientHeight || 550;

    var mmW = 180, mmH = 110;
    var scale = Math.min(mmW / MAP_STATE.totalW, mmH / MAP_STATE.totalH);

    var NS = "http://www.w3.org/2000/svg";
    currentMinimapSvg.textContent = "";

    MAP_STATE.links.forEach(function (l) {
      var a = l[0], b = l[1], mx = (a.x + b.x) / 2;
      var d = "M" + ((a.x + 6) * scale) + " " + (a.y * scale) + " C" + (mx * scale) + " " + (a.y * scale) + " " +
              (mx * scale) + " " + (b.y * scale) + " " + ((b.x - 6) * scale) + " " + (b.y * scale);
      var p = document.createElementNS(NS, "path");
      p.setAttribute("d", d);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", "var(--line)");
      p.setAttribute("stroke-width", "1");
      currentMinimapSvg.appendChild(p);
    });

    MAP_STATE.nodes.forEach(function (n) {
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", String(n.x * scale));
      c.setAttribute("cy", String(n.y * scale));
      c.setAttribute("r", n.children && n.children.length ? "2" : "1.2");
      c.setAttribute("fill", n.col ? "var(--c-" + n.col + ")" : "var(--accent)");
      currentMinimapSvg.appendChild(c);
    });

    var vx = (-MAP_STATE.panX / MAP_STATE.scale) * scale;
    var vy = (-MAP_STATE.panY / MAP_STATE.scale) * scale;
    var vw = (cw / MAP_STATE.scale) * scale;
    var vh = (ch / MAP_STATE.scale) * scale;

    currentMinimapRect.style.left = Math.max(0, vx) + "px";
    currentMinimapRect.style.top = Math.max(0, vy) + "px";
    currentMinimapRect.style.width = Math.min(mmW, vw) + "px";
    currentMinimapRect.style.height = Math.min(mmH, vh) + "px";
  }

  function updateMapInPlace(resetTransform) {
    if (!currentViewportG) return;
    var layout = computeMapLayout();
    var NS = "http://www.w3.org/2000/svg";
    function s(tag, attrs) {
      var n = document.createElementNS(NS, tag);
      Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
      return n;
    }

    currentViewportG.textContent = "";

    var gLinks = s("g", { id: "map-links" });
    layout.links.forEach(function (l) {
      var a = l[0], b = l[1], mx = (a.x + b.x) / 2;
      var d = "M" + (a.x + 6) + " " + a.y + " C" + mx + " " + a.y + " " + mx + " " + b.y + " " + (b.x - 6) + " " + b.y;
      var isDimmed = MAP_STATE.query && !b.match && !b.hasMatchingKid;
      gLinks.appendChild(s("path", {
        d: d,
        "class": "map-link" + (isDimmed ? " dimmed" : "")
      }));
    });
    currentViewportG.appendChild(gLinks);

    var gNodes = s("g", { id: "map-nodes" });
    var matchCount = 0;
    layout.nodes.forEach(function (n) {
      var kids = n.children || [], open = kids.length && isOpen(n, n.depth);
      var colour = n.col ? "var(--c-" + n.col + ")" : "var(--accent)";
      if (n.blocked) colour = "var(--bad)";

      var isDimmed = MAP_STATE.query && !n.match && !n.hasMatchingKid;
      var isHighlighted = MAP_STATE.query && n.match;
      if (isHighlighted) matchCount++;

      var gNode = s("g", { "class": "map-node" + (isDimmed ? " dimmed" : "") + (isHighlighted ? " highlighted" : "") });

      var r = kids.length ? 6 : 4;
      if (n.blocked) r = 6;

      var c = s("circle", {
        cx: n.x, cy: n.y, r: r,
        fill: kids.length && !open ? colour : "var(--bg)",
        stroke: colour
      });

      var t = s("text", {
        x: n.x + 10, y: n.y + 4,
        "class": n.route ? "nav" : ""
      });
      t.textContent = n.label;

      function onToggle() {
        OPEN[n.key] = !open;
        updateMapInPlace(false);
      }

      function onSelect(e) {
        if (n.route) {
          if (n.id) openItemDrawer(n.id);
          else openDocDrawer(n.full || n.label, n.route);
        } else if (kids.length) {
          onToggle();
        }
      }

      function onDblClick() {
        if (n.route) go(n.route);
      }

      if (kids.length) c.addEventListener("click", function (e) { e.stopPropagation(); onToggle(); });
      t.addEventListener("click", function (e) { e.stopPropagation(); onSelect(e); });
      t.addEventListener("dblclick", function (e) { e.stopPropagation(); onDblClick(); });

      gNode.addEventListener("mouseenter", function (e) { showMapTooltip(n, e); });
      gNode.addEventListener("mousemove", positionTooltip);
      gNode.addEventListener("mouseleave", hideMapTooltip);

      if (kids.length && !open) {
        var ct = s("tspan", { dx: "6", "class": "count" });
        ct.textContent = "(" + kids.length + ")";
        t.appendChild(ct);
      }

      var isBlocker = n.isBlocker || (n.blocksCount && n.blocksCount > 0);
      if (n.blocked) {
        var warnTag = s("tspan", { dx: "6", fill: "var(--bad)", "font-weight": "700", "font-size": "11px" });
        warnTag.textContent = "blocked";
        t.appendChild(warnTag);
      } else if (isBlocker) {
        var blkTag = s("tspan", { dx: "6", fill: "var(--warn)", "font-weight": "700", "font-size": "11px" });
        blkTag.textContent = "blocks " + n.blocksCount;
        t.appendChild(blkTag);
      }

      gNode.appendChild(c);
      gNode.appendChild(t);

      gNodes.appendChild(gNode);
    });
    currentViewportG.appendChild(gNodes);

    if (currentMatchBadge) {
      if (MAP_STATE.query) {
        currentMatchBadge.style.display = "inline-block";
        currentMatchBadge.textContent = matchCount + " match" + (matchCount === 1 ? "" : "es");
      } else {
        currentMatchBadge.style.display = "none";
      }
    }

    if (resetTransform) fitMapToScreen();
    else applyTransform();
    updateMinimap();
  }

  function drawMap(box) {
    box.textContent = "";

    var container = el("div", { cls: "map-container", id: "map-container" });

    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "map-canvas");
    svg.setAttribute("id", "map-canvas");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Mind map of the project");

    var bgRect = document.createElementNS(NS, "rect");
    bgRect.setAttribute("width", "100%");
    bgRect.setAttribute("height", "100%");
    bgRect.setAttribute("fill", "transparent");
    svg.appendChild(bgRect);

    var viewportG = document.createElementNS(NS, "g");
    viewportG.setAttribute("id", "map-viewport");
    svg.appendChild(viewportG);

    currentMapSvg = svg;
    currentViewportG = viewportG;

    var dragging = false, startX = 0, startY = 0;
    container.addEventListener("mousedown", function (e) {
      if (e.target.closest && (e.target.closest(".map-hud") || e.target.closest(".map-minimap"))) return;
      dragging = true;
      startX = e.clientX - MAP_STATE.panX;
      startY = e.clientY - MAP_STATE.panY;
      svg.classList.add("grabbing");
    });
    window.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      MAP_STATE.panX = e.clientX - startX;
      MAP_STATE.panY = e.clientY - startY;
      applyTransform();
    });
    window.addEventListener("mouseup", function () {
      if (dragging) {
        dragging = false;
        svg.classList.remove("grabbing");
      }
    });
    container.addEventListener("wheel", function (e) {
      e.preventDefault();
      var delta = e.deltaY < 0 ? 1.15 : 0.87;
      var nextScale = Math.max(0.15, Math.min(5, MAP_STATE.scale * delta));
      var r = container.getBoundingClientRect();
      var mx = e.clientX - r.left, my = e.clientY - r.top;
      MAP_STATE.panX = mx - (mx - MAP_STATE.panX) * (nextScale / MAP_STATE.scale);
      MAP_STATE.panY = my - (my - MAP_STATE.panY) * (nextScale / MAP_STATE.scale);
      MAP_STATE.scale = nextScale;
      applyTransform();
    }, { passive: false });

    var hud = el("div", { cls: "map-hud" }, [
      el("button", { text: "+", title: "Zoom in (+)", on: { click: function () {
        MAP_STATE.scale = Math.min(5, MAP_STATE.scale * 1.25);
        applyTransform();
      } } }),
      el("button", { text: "−", title: "Zoom out (−)", on: { click: function () {
        MAP_STATE.scale = Math.max(0.15, MAP_STATE.scale * 0.8);
        applyTransform();
      } } }),
      el("button", { text: "⤢", title: "Fit to screen (0)", on: { click: fitMapToScreen } }),
      el("button", { text: "1:1", title: "Reset Zoom (100%)", on: { click: function () {
        MAP_STATE.scale = 1;
        MAP_STATE.panX = 30;
        MAP_STATE.panY = 30;
        applyTransform();
      } } }),
      el("div", { cls: "sep" }),
      el("button", { text: "⊡", title: "Toggle Minimap", on: { click: function () {
        MAP_STATE.showMinimap = !MAP_STATE.showMinimap;
        minimapBox.style.display = MAP_STATE.showMinimap ? "block" : "none";
        if (MAP_STATE.showMinimap) updateMinimap();
      } } })
    ]);

    var minimapBox = el("div", { cls: "map-minimap", id: "map-minimap" });
    var minimapSvg = document.createElementNS(NS, "svg");
    minimapSvg.setAttribute("width", "100%");
    minimapSvg.setAttribute("height", "100%");
    var minimapRect = el("div", { cls: "map-minimap-viewport", id: "minimap-viewport" });
    minimapBox.appendChild(minimapSvg);
    minimapBox.appendChild(minimapRect);

    minimapBox.addEventListener("click", function (e) {
      var r = minimapBox.getBoundingClientRect();
      var clickX = e.clientX - r.left, clickY = e.clientY - r.top;
      var scale = Math.min(180 / MAP_STATE.totalW, 110 / MAP_STATE.totalH);
      var targetX = clickX / scale;
      var targetY = clickY / scale;
      var cw = container.clientWidth || 900, ch = container.clientHeight || 550;
      MAP_STATE.panX = (cw / 2) - targetX * MAP_STATE.scale;
      MAP_STATE.panY = (ch / 2) - targetY * MAP_STATE.scale;
      applyTransform();
    });

    currentMinimapSvg = minimapSvg;
    currentMinimapRect = minimapRect;

    container.appendChild(svg);
    container.appendChild(hud);
    container.appendChild(minimapBox);
    box.appendChild(container);

    updateMapInPlace(true);
    return svg;
  }

  function viewMap() {
    tab("map");
    crumbs([[M.project || "Project", "dashboard"], ["Dashboard", "dashboard"], ["Map"]]);
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [
        el("h1", { text: "Project Architecture & Dependency Map" }),
        el("p", { cls: "view-subtitle", text: "Interactive radial graph of epics, backlog stages, dependencies, and project documents. Click any node to inspect or open in Action Threads." })
      ]),
      el("div", { cls: "view-header-actions" }, [
        el("button", { cls: "btn", text: "Dashboard ↗", on: { click: function () { go("dashboard"); } } }),
        el("button", { cls: "btn", text: "Open Board ↗", on: { click: function () { go("board"); } } })
      ])
    ]));

    var slug = (M.project || "nuhut").toLowerCase().replace(/[^a-z0-9]+/g, "-");

    function walk(n, v) {
      if (n.children) {
        OPEN[n.key] = v;
        n.children.forEach(function (k) { if (!/^[dh]:/.test(k.key)) walk(k, v); });
      }
    }

    function applyPreset(preset) {
      MAP_STATE.preset = preset;
      [].forEach.call(presetsBar.querySelectorAll(".preset-btn"), function (b) {
        var isAct = b.dataset.p === preset;
        b.className = isAct ? "preset-btn active" : "preset-btn";
        b.setAttribute("aria-pressed", isAct ? "true" : "false");
      });
      if (preset === "all") {
        walk(mapTree(), true);
      } else if (preset === "collapse") {
        OPEN = { root: true };
      } else if (preset === "active") {
        OPEN = { root: true, "g:status": true, "c:Now": true, "c:Next": true };
      } else if (preset === "blockages") {
        OPEN = { root: true, "g:deps": true, "g:blk": true, "g:wait": true, "g:rdy": false };
        var cd = computeDependencies();
        cd.blockers.forEach(function (b) { OPEN["blk:" + b.id] = true; });
        cd.blockedItems.forEach(function (b) { OPEN["wait:" + b.id] = true; });
      } else if (preset === "bottlenecks") {
        OPEN = { root: true, "g:status": true, "c:Blocked": true, "c:Parked": true };
      } else if (preset === "epics" && M.epics && M.epics.length) {
        OPEN = { root: true, "g:epics": true };
        M.epics.forEach(function (e) { OPEN["e:" + e.name] = true; });
      } else if (preset === "docs") {
        OPEN = { root: true };
        walk(mapTree(), false);
        OPEN["root"] = true; OPEN["g:docs"] = true;
        Object.keys(OPEN).forEach(function (k) { if (/^k:/.test(k)) OPEN[k = k] = true; });
      } else if (preset === "owner") {
        OPEN = { root: true };
        walk(mapTree(), false);
        OPEN["root"] = true; OPEN["g:owner"] = true;
        Object.keys(OPEN).forEach(function (k) { if (/^o:/.test(k)) OPEN[k = k] = true; });
      }
      updateMapInPlace(false);
    }

    var cdPreview = computeDependencies();
    var blkTotal = cdPreview.blockers.length + cdPreview.blockedItems.length;

    function makePresetBtn(key, text, title) {
      var isAct = MAP_STATE.preset === key;
      return el("button", {
        cls: "preset-btn" + (isAct ? " active" : ""),
        "data-p": key,
        "aria-pressed": isAct ? "true" : "false",
        title: title || text,
        text: text,
        on: { click: function () { applyPreset(key); } }
      });
    }

    var presetButtons = [
      el("span", { cls: "muted", style: "font-size: 12px; margin-right: 4px;", text: "Focus:" }),
      makePresetBtn("all", "All"),
      makePresetBtn("active", "Active work (Now/Next)"),
      makePresetBtn("blockages", "Dependencies & Blockages" + (blkTotal ? " (" + blkTotal + ")" : ""), "Focus on dependency chains, root blockers, and blocked work"),
      makePresetBtn("bottlenecks", "Bottlenecks (Blocked/Parked)")
    ];
    if (M.epics && M.epics.length) {
      presetButtons.push(makePresetBtn("epics", "Epics"));
    }
    presetButtons.push(makePresetBtn("docs", "Documents"));
    presetButtons.push(makePresetBtn("owner", "By Owner"));
    presetButtons.push(makePresetBtn("collapse", "Collapse"));

    var presetsBar = el("div", { cls: "presets" }, presetButtons);
    main.appendChild(presetsBar);

    var filterInput = el("input", {
      type: "search",
      placeholder: "Filter map nodes…",
      value: MAP_STATE.query,
      "aria-label": "Filter map nodes",
      on: { input: function () {
        MAP_STATE.query = filterInput.value;
        updateMapInPlace(false);
      } }
    });
    var clearFilterBtn = el("button", {
      cls: "clear-btn",
      text: "✕",
      title: "Clear filter",
      "aria-label": "Clear filter",
      on: { click: function () {
        filterInput.value = "";
        MAP_STATE.query = "";
        updateMapInPlace(false);
      } }
    });
    var matchBadge = el("span", { cls: "chip", style: "display: none; background: var(--okbg); color: var(--accent); font-weight: 600;" });
    currentMatchBadge = matchBadge;

    var exportMenu = el("details", { cls: "export-menu" }, [
      el("summary", { cls: "btn", text: "Export ▾" }),
      el("div", { cls: "export-menu-list" }, [
        el("button", {
          text: "Export SVG (Interactive)",
          title: "Download formatted SVG with pan, zoom, and theme support",
          on: { click: function () {
            exportMenu.removeAttribute("open");
            var xml = buildSvgExport({ interactive: true });
            downloadFile(slug + "-map.svg", xml, "image/svg+xml;charset=utf-8");
          } }
        }),
        el("button", {
          text: "Export SVG (Static)",
          title: "Download clean vector SVG without scripts (for Figma, docs, print)",
          on: { click: function () {
            exportMenu.removeAttribute("open");
            var xml = buildSvgExport({ interactive: false });
            downloadFile(slug + "-map-static.svg", xml, "image/svg+xml;charset=utf-8");
          } }
        }),
        el("button", {
          text: "Export Standalone HTML",
          title: "Download complete offline-first interactive project dashboard",
          on: { click: function () {
            exportMenu.removeAttribute("open");
            exportHtml();
          } }
        })
      ])
    ]);

    main.appendChild(el("div", { cls: "mapbar" }, [
      el("div", { cls: "map-filter" }, [filterInput, clearFilterBtn]),
      matchBadge,
      exportMenu,
      el("span", { cls: "muted", style: "font-size: 12px; margin-left: auto;", text: "Wheel to zoom · Drag to pan · Click label for inspector" })
    ]));

    var box = el("div");
    main.appendChild(box);
    drawMap(box);
  }


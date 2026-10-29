  // ---------------------------------------------------------------- map & dependencies
  function computeDependencies() {
    var blockers = [], blockedItems = [], readyItems = [];
    M.order.forEach(function (id) {
      var it = ITEMS[id];
      if (!it) return;
      var openBlocked = (it.depends || []).filter(function (d) { return !ITEMS[d] || ITEMS[d].column !== "Done"; });
      var openDependents = (it.dependents || []).filter(function (d) { return ITEMS[d] && ITEMS[d].column !== "Done"; });

      if (openDependents.length && ["Done", "Dropped"].indexOf(it.column) < 0) {
        blockers.push({ id: id, count: openDependents.length, dependents: openDependents });
      }
      if (openBlocked.length && ["Done", "Dropped"].indexOf(it.column) < 0) {
        blockedItems.push({ id: id, count: openBlocked.length, dependencies: openBlocked });
      }
      if (!openBlocked.length && ["Now", "Next"].indexOf(it.column) >= 0) {
        readyItems.push(id);
      }
    });
    blockers.sort(function (a, b) { return b.count - a.count || a.id.localeCompare(b.id); });
    blockedItems.sort(function (a, b) { return b.count - a.count || a.id.localeCompare(b.id); });
    return { blockers: blockers, blockedItems: blockedItems, readyItems: readyItems };
  }

  var OPEN = {};
  function mapTree() {
    var ids = M.order;
    function itemNode(id, customKey) {
      var it = ITEMS[id];
      if (!it) return null;
      var openBlocked = (it.depends || []).filter(function (d) { return !ITEMS[d] || ITEMS[d].column !== "Done"; });
      var isBlocked = openBlocked.length > 0;
      var openDependents = (it.dependents || []).filter(function (d) { return ITEMS[d] && ITEMS[d].column !== "Done"; });
      var isBlocker = openDependents.length > 0 && it.column !== "Done";
      var stepCount = 0;
      if (it.steps) {
        Object.keys(it.steps).forEach(function (s) { if (it.steps[s] === "done") stepCount++; });
      }
      return {
        key: customKey || ("i:" + id),
        id: id,
        label: id + "  " + clip(it.title, 24),
        full: id + " " + (it.title || ""),
        route: "item/" + id,
        col: it.column,
        tier: it.tier,
        owner: it.owner,
        blocked: isBlocked,
        blockedBy: openBlocked,
        isBlocker: isBlocker,
        blocksCount: openDependents.length,
        blocksItems: openDependents,
        stepsDone: stepCount
      };
    }
    var byCol = M.columns.map(function (c) {
      var kids = ids.filter(function (id) { return ITEMS[id].column === c; }).map(function (id) { return itemNode(id); });
      return kids.length ? { key: "c:" + c, label: c, col: c, children: kids } : null;
    }).filter(Boolean);
    var owners = {};
    ids.forEach(function (id) {
      var o = ITEMS[id].owner;
      if (o && ["Done", "Dropped"].indexOf(ITEMS[id].column) < 0) (owners[o] = owners[o] || []).push(id);
    });
    var byOwner = Object.keys(owners).sort().map(function (o) {
      return { key: "o:" + o, label: o, children: owners[o].map(function (id) { return itemNode(id); }) };
    });
    var kinds = {};
    DOCS.forEach(function (d, n) {
      if (d.kind === "index") return;
      (kinds[d.kind] = kinds[d.kind] || []).push(n);
    });
    var kindNames = { record: "Records", plans: "Plans", reviews: "Reviews", defects: "Defects",
      postmortems: "Postmortems", adr: "ADRs", archive: "Worklog archive" };
    var byDoc = Object.keys(kinds).map(function (k) {
      return { key: "k:" + k, label: kindNames[k] || k, children: kinds[k].map(function (n) {
        var d = DOCS[n];
        return { key: "d:" + d.path, label: clip(d.path.split("/").pop(), 24), full: d.path,
          route: docRoute(n), children: d.headings.filter(function (x) { return x.level === 2; })
            .map(function (x) { return { key: "h:" + d.path + x.line, label: clip(x.text, 24), full: x.text,
              route: docRoute(n, x.line) }; }) };
      }) };
    });

    var depsData = computeDependencies();
    var depGroups = [];
    if (depsData.blockers.length) {
      depGroups.push({
        key: "g:blk",
        label: "Active bottlenecks (" + depsData.blockers.length + ")",
        route: "waiting",
        children: depsData.blockers.map(function (b) {
          var it = ITEMS[b.id];
          return {
            key: "blk:" + b.id,
            id: b.id,
            label: b.id + " (blocks " + b.count + ")",
            full: b.id + " blocks " + b.count + " downstream: " + (it ? it.title : ""),
            route: "item/" + b.id,
            isBlocker: true,
            blocksCount: b.count,
            col: it ? it.column : ""
          };
        })
      });
    }
    if (depsData.blockedItems.length) {
      depGroups.push({
        key: "g:wait",
        label: "Blocked items (" + depsData.blockedItems.length + ")",
        route: "waiting",
        children: depsData.blockedItems.map(function (b) {
          var it = ITEMS[b.id];
          return {
            key: "wait:" + b.id,
            id: b.id,
            label: b.id + " (waits on " + b.count + ")",
            full: b.id + " waits on " + b.count + " prerequisites: " + (it ? it.title : ""),
            route: "item/" + b.id,
            blocked: true,
            col: it ? it.column : ""
          };
        })
      });
    }

    var depBranch = {
      key: "g:deps",
      label: "Dependencies & Blockages (" + (depsData.blockers.length + depsData.blockedItems.length) + ")",
      route: "waiting",
      children: depGroups.length ? depGroups : [
        { key: "g:nodeps", label: "No active blockages", children: [] }
      ]
    };

    var root = { key: "root", label: M.project || "Project", children: [
      { key: "g:status", label: "Work by status", children: byCol },
      depBranch,
      { key: "g:owner", label: "Open work by owner role", children: byOwner },
      { key: "g:docs", label: "Documents", children: byDoc }
    ] };
    if (M.epics && M.epics.length) {
      root.children.splice(2, 0, { key: "g:epics", label: "Epics", children: M.epics.map(function (e) {
        return { key: "e:" + e.name, label: e.name, children: e.items.filter(function (id) { return ITEMS[id]; }).map(function (id) { return itemNode(id); }) };
      }) });
    }
    return root;
  }
  function isOpen(n, depth) { return OPEN[n.key] !== undefined ? OPEN[n.key] : depth < 2; }

  function escXml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }

  function downloadFile(filename, content, mime) {
    var blob = new Blob([content], { type: mime || "application/octet-stream" });
    var a = el("a", { href: URL.createObjectURL(blob), download: filename });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 100);
  }

  function exportHtml() {
    var title = (M.project || "nuhut").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    var doc = "<!doctype html>\n" + document.documentElement.outerHTML;
    downloadFile(title + "-dashboard.html", doc, "text/html;charset=utf-8");
  }

  function buildSvgExport(opts) {
    opts = opts || {};
    var isInteractive = !!opts.interactive;
    var root = mapTree(), ROW = 26, COLW = 280, rows = 0, maxDepth = 0, nodes = [], links = [];
    (function place(n, depth) {
      n.depth = depth;
      maxDepth = Math.max(maxDepth, depth);
      var kids = n.children || [];
      if (kids.length && (opts.allOpen || isOpen(n, depth))) {
        kids.forEach(function (k) { place(k, depth + 1); links.push([n, k]); });
        n.y = (kids[0].y + kids[kids.length - 1].y) / 2;
      } else {
        n.y = rows++ * ROW + 24;
      }
      n.x = depth * COLW + 24;
      nodes.push(n);
    })(root, 0);

    var width = Math.max(760, (maxDepth + 1) * COLW + 300);
    var height = Math.max(360, rows * ROW + 48);
    var proj = M.project || "Project";

    var COL_HEX = {
      Now: "#0969da", Next: "#8250df", Blocked: "#cf222e", Parked: "#bf8700",
      Later: "#6e7781", Done: "#2f8f5b", Dropped: "#afb8c1", Other: "#6e7781"
    };

    var L = [];
    L.push('<?xml version="1.0" encoding="UTF-8"?>');
    L.push('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ' +
           'viewBox="0 0 ' + width + ' ' + height + '" width="' + width + '" height="' + height + '" ' +
           'role="img" aria-label="' + escXml(proj) + ' Mind Map">');
    L.push('  <title>' + escXml(proj) + ' Mind Map</title>');
    L.push('  <defs>');
    L.push('    <style type="text/css"><![CDATA[');
    L.push('      :root {');
    L.push('        --bg: #ffffff; --panel: #f6f8fa; --line: #d0d7de; --text: #1f2328; --muted: #57606a;');
    L.push('        --link: #0969da; --accent: #2f8f5b; --c-Now: #0969da; --c-Next: #8250df;');
    L.push('        --c-Blocked: #cf222e; --c-Parked: #bf8700; --c-Later: #6e7781; --c-Done: #2f8f5b;');
    L.push('        --c-Dropped: #afb8c1; --c-Other: #6e7781;');
    L.push('      }');
    L.push('      @media (prefers-color-scheme: dark) {');
    L.push('        :root {');
    L.push('          --bg: #0d1117; --panel: #161b22; --line: #30363d; --text: #e6edf3; --muted: #9da7b3;');
    L.push('          --link: #4493f8; --accent: #3fb950; --c-Now: #4493f8; --c-Next: #a371f7;');
    L.push('          --c-Blocked: #f85149; --c-Parked: #d29922; --c-Later: #8b949e; --c-Done: #3fb950;');
    L.push('          --c-Dropped: #484f58; --c-Other: #8b949e;');
    L.push('        }');
    L.push('      }');
    L.push('      text { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }');
    L.push('      .bg-canvas { fill: var(--bg, #ffffff); }');
    L.push('      .map-link { fill: none; stroke: var(--line, #d0d7de); stroke-width: 1.5; stroke-linecap: round; transition: stroke .15s ease, stroke-width .15s ease; }');
    L.push('      .map-link:hover { stroke: var(--link, #0969da); stroke-width: 2.2; }');
    L.push('      .node-dot { stroke-width: 2; cursor: pointer; transition: r .15s ease; }');
    L.push('      .node-dot:hover { r: 7.5; }');
    L.push('      .node-label { font-size: 13px; fill: var(--text, #1f2328); cursor: pointer; user-select: none; }');
    L.push('      .node-label.nav { fill: var(--link, #0969da); font-weight: 500; }');
    L.push('      .node-label.nav:hover { text-decoration: underline; }');
    L.push('      .node-count { font-size: 11px; fill: var(--muted, #57606a); user-select: none; }');
    L.push('      .svg-btn { cursor: pointer; user-select: none; }');
    L.push('      .svg-btn rect { fill: var(--panel, #f6f8fa); stroke: var(--line, #d0d7de); stroke-width: 1; rx: 4; ry: 4; }');
    L.push('      .svg-btn:hover rect { fill: var(--line, #d0d7de); }');
    L.push('      .svg-btn text { font-size: 11px; font-weight: 600; fill: var(--text, #1f2328); text-anchor: middle; dominant-baseline: central; }');
    L.push('    ]]></style>');
    L.push('  </defs>');
    L.push('');
    L.push('  <!-- Background -->');
    L.push('  <rect width="100%" height="100%" fill="var(--bg, #ffffff)" class="bg-canvas" />');
    L.push('');
    L.push('  <g id="viewport">');
    L.push('    <!-- Connectors -->');
    L.push('    <g id="links">');
    links.forEach(function (l) {
      var a = l[0], b = l[1], mx = (a.x + b.x) / 2;
      var d = "M" + (a.x + 6) + " " + a.y + " C" + mx + " " + a.y + " " + mx + " " + b.y + " " + (b.x - 6) + " " + b.y;
      L.push('      <path class="map-link" d="' + d + '" fill="none" stroke="var(--line, #d0d7de)" stroke-width="1.5" />');
    });
    L.push('    </g>');
    L.push('');
    L.push('    <!-- Nodes -->');
    L.push('    <g id="nodes">');
    nodes.forEach(function (n) {
      var kids = n.children || [], open = kids.length && (opts.allOpen || isOpen(n, n.depth));
      var strokeHex = (n.col && COL_HEX[n.col]) || "#2f8f5b";
      var strokeVal = n.col ? "var(--c-" + n.col + ", " + strokeHex + ")" : "var(--accent, #2f8f5b)";
      var fillHex = (kids.length && !open) ? strokeHex : "#ffffff";
      var fillVal = (kids.length && !open) ? strokeVal : "var(--bg, #ffffff)";
      var r = kids.length ? 6 : 4;
      var labelClass = "node-label" + (n.route ? " nav" : "");
      var fullText = escXml(n.full || n.label);
      var labelText = escXml(n.label);

      L.push('      <g class="map-node" data-key="' + escXml(n.key) + '">');
      L.push('        <circle class="node-dot" cx="' + n.x + '" cy="' + n.y + '" r="' + r + '" ' +
             'fill="' + fillVal + '" stroke="' + strokeVal + '" stroke-width="2">');
      L.push('          <title>' + fullText + '</title>');
      L.push('        </circle>');
      var countSpan = (kids.length && !open)
        ? '<tspan class="node-count" dx="6">(' + kids.length + ')</tspan>'
        : '';
      L.push('        <text class="' + labelClass + '" x="' + (n.x + 10) + '" y="' + (n.y + 4) + '" ' +
             'font-family="system-ui, sans-serif" font-size="13px" fill="var(--text, #1f2328)">' +
             labelText + countSpan + '<title>' + fullText + '</title></text>');
      L.push('      </g>');
    });
    L.push('    </g>');
    L.push('  </g>');

    if (isInteractive) {
      L.push('');
      L.push('  <!-- Interactive Navigation Controls -->');
      L.push('  <g id="controls" transform="translate(' + (width - 156) + ', 14)">');
      L.push('    <rect width="142" height="30" rx="6" ry="6" fill="var(--panel, #f6f8fa)" stroke="var(--line, #d0d7de)" stroke-width="1" />');
      L.push('    <g class="svg-btn" id="btn-zoom-in" transform="translate(5, 3)">');
      L.push('      <rect width="24" height="24" /><text x="12" y="12">+</text>');
      L.push('      <title>Zoom in</title>');
      L.push('    </g>');
      L.push('    <g class="svg-btn" id="btn-zoom-out" transform="translate(33, 3)">');
      L.push('      <rect width="24" height="24" /><text x="12" y="12">−</text>');
      L.push('      <title>Zoom out</title>');
      L.push('    </g>');
      L.push('    <g class="svg-btn" id="btn-reset" transform="translate(61, 3)">');
      L.push('      <rect width="42" height="24" /><text x="21" y="12">100%</text>');
      L.push('      <title>Reset view</title>');
      L.push('    </g>');
      L.push('    <g class="svg-btn" id="btn-theme" transform="translate(107, 3)">');
      L.push('      <rect width="26" height="24" /><text x="13" y="12">◐</text>');
      L.push('      <title>Toggle theme</title>');
      L.push('    </g>');
      L.push('  </g>');
      L.push('');
      L.push('  <!-- Interactive Pan & Zoom Script -->');
      L.push('  <script type="text/javascript"><![CDATA[');
      L.push('    (function () {');
      L.push('      var svg = document.documentElement;');
      L.push('      var vp = document.getElementById("viewport");');
      L.push('      if (!vp) return;');
      L.push('      var scale = 1, panX = 0, panY = 0;');
      L.push('      var dragging = false, startX = 0, startY = 0;');
      L.push('      function update() {');
      L.push('        vp.setAttribute("transform", "translate(" + panX.toFixed(2) + "," + panY.toFixed(2) + ") scale(" + scale.toFixed(3) + ")");');
      L.push('      }');
      L.push('      svg.addEventListener("mousedown", function (e) {');
      L.push('        if (e.target.closest && e.target.closest("#controls")) return;');
      L.push('        dragging = true;');
      L.push('        startX = e.clientX - panX;');
      L.push('        startY = e.clientY - panY;');
      L.push('        svg.style.cursor = "grabbing";');
      L.push('      });');
      L.push('      window.addEventListener("mousemove", function (e) {');
      L.push('        if (!dragging) return;');
      L.push('        panX = e.clientX - startX;');
      L.push('        panY = e.clientY - startY;');
      L.push('        update();');
      L.push('      });');
      L.push('      window.addEventListener("mouseup", function () {');
      L.push('        if (dragging) { dragging = false; svg.style.cursor = "default"; }');
      L.push('      });');
      L.push('      svg.addEventListener("wheel", function (e) {');
      L.push('        e.preventDefault();');
      L.push('        var delta = e.deltaY < 0 ? 1.15 : 0.87;');
      L.push('        var next = Math.max(0.15, Math.min(6, scale * delta));');
      L.push('        var r = svg.getBoundingClientRect();');
      L.push('        var mx = e.clientX - r.left, my = e.clientY - r.top;');
      L.push('        panX = mx - (mx - panX) * (next / scale);');
      L.push('        panY = my - (my - panY) * (next / scale);');
      L.push('        scale = next;');
      L.push('        update();');
      L.push('      }, { passive: false });');
      L.push('      var bIn = document.getElementById("btn-zoom-in");');
      L.push('      if (bIn) bIn.addEventListener("click", function () { scale = Math.min(6, scale * 1.25); update(); });');
      L.push('      var bOut = document.getElementById("btn-zoom-out");');
      L.push('      if (bOut) bOut.addEventListener("click", function () { scale = Math.max(0.15, scale * 0.8); update(); });');
      L.push('      var bRes = document.getElementById("btn-reset");');
      L.push('      if (bRes) bRes.addEventListener("click", function () { scale = 1; panX = 0; panY = 0; update(); });');
      L.push('      var bTh = document.getElementById("btn-theme");');
      L.push('      if (bTh) bTh.addEventListener("click", function () {');
      L.push('        var curr = svg.getAttribute("data-theme");');
      L.push('        var isDark = curr === "dark" || (!curr && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);');
      L.push('        var next = isDark ? "light" : "dark";');
      L.push('        svg.setAttribute("data-theme", next);');
      L.push('        if (next === "dark") {');
      L.push('          svg.style.setProperty("--bg", "#0d1117"); svg.style.setProperty("--text", "#e6edf3");');
      L.push('          svg.style.setProperty("--line", "#30363d"); svg.style.setProperty("--panel", "#161b22");');
      L.push('        } else {');
      L.push('          svg.style.setProperty("--bg", "#ffffff"); svg.style.setProperty("--text", "#1f2328");');
      L.push('          svg.style.setProperty("--line", "#d0d7de"); svg.style.setProperty("--panel", "#f6f8fa");');
      L.push('        }');
      L.push('      });');
      L.push('    })();');
      L.push('  ]]><\/script>');
    }
    L.push('</svg>');
    L.push('');
    return L.join('\n');
  }


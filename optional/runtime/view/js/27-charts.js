  // ---------------------------------------------------------------- charts
  // Inline SVG, colours from the CSS variables so the theme toggle re-themes them.
  var SVG_NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs, title) {
    var n = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, String(attrs[k])); });
    if (title) { var t = document.createElementNS(SVG_NS, "title"); t.textContent = title; n.appendChild(t); }
    return n;
  }
  function svgText(x, y, text, anchor, cls) {
    var t = svgEl("text", { x: x, y: y, "text-anchor": anchor || "start", "class": cls || "chart-label" });
    t.textContent = text;
    return t;
  }

  // Cumulative flow: a stacked area of backlog column counts per committed day.
  var FLOW_STACK = ["Done", "Now", "Blocked", "Parked", "Next", "Later"];
  function drawFlowChart(flow) {
    var dates = (flow && flow.dates) || [], series = (flow && flow.series) || {};
    var box = el("div", { cls: "chart" });
    if (dates.length < 2) {
      box.appendChild(el("p", { cls: "muted", text: "Flow appears after the backlog has two committed days of history." }));
      return box;
    }
    var names = FLOW_STACK.filter(function (n) { return (series[n] || []).some(function (v) { return v > 0; }); });
    var n = dates.length, W = 960, H = 180, L = 34, R = 8, T = 10, B = 24;
    var totals = dates.map(function (_, i) { return names.reduce(function (a, k) { return a + (series[k][i] || 0); }, 0); });
    var max = Math.max(1, Math.max.apply(null, totals));
    // Time on the x axis, not index: a gap of a year looks like a year.
    var days = dates.map(function (d) { return Date.parse(d) / 86400000; });
    var span = Math.max(1, days[n - 1] - days[0]);
    var x = function (i) { return L + (W - L - R) * (days[i] - days[0]) / span; };
    var y = function (v) { return T + (H - T - B) * (1 - v / max); };
    var legend = el("div", { cls: "chart-legend" });
    names.slice().reverse().forEach(function (k) {
      legend.appendChild(el("span", { cls: "chip", style: "background: var(--c-" + k + "); color: #fff" , text: k + " " + series[k][n - 1] }));
    });
    box.appendChild(legend);
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, "class": "chart-svg", role: "img",
      "aria-label": "Backlog flow, " + n + " points" });
    var base = dates.map(function () { return 0; });
    names.forEach(function (k) {
      var top = base.map(function (b, i) { return b + (series[k][i] || 0); });
      var d = "";
      for (var i = 0; i < n; i++) d += (i ? " L" : "M") + x(i).toFixed(1) + " " + y(top[i]).toFixed(1);
      for (var j = n - 1; j >= 0; j--) d += " L" + x(j).toFixed(1) + " " + y(base[j]).toFixed(1);
      svg.appendChild(svgEl("path", { d: d + " Z", fill: "var(--c-" + k + ")", "fill-opacity": 0.75 }, k));
      base = top;
    });
    [0, Math.round(max / 2), max].forEach(function (v) {
      svg.appendChild(svgEl("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "var(--line)", "stroke-dasharray": "2 3" }));
      svg.appendChild(svgText(L - 4, y(v) + 4, String(v), "end"));
    });
    [0, Math.floor((n - 1) / 2), n - 1].forEach(function (i, k) {
      svg.appendChild(svgText(x(i), H - 6, dates[i], k === 0 ? "start" : (k === 1 ? "middle" : "end")));
    });
    dates.forEach(function (date, i) {
      var tip = date + " · " + names.slice().reverse().map(function (k) { return k + " " + series[k][i]; }).join(" · ");
      var x0 = i ? (x(i - 1) + x(i)) / 2 : L, x1 = i < n - 1 ? (x(i) + x(i + 1)) / 2 : W - R;
      svg.appendChild(svgEl("rect", { x: x0, y: T, width: Math.max(1, x1 - x0), height: H - T - B,
        fill: "transparent" }, tip));
    });
    box.appendChild(svg);
    return box;
  }

  // Verify trend: one column per run, one row per stage that ever ran.
  function verifyFill(result) {
    if (!result) return "transparent";
    if (result.indexOf("Verified: pass") === 0) return "var(--c-Done)";
    if (result.indexOf("timed out") >= 0) return "var(--warn)";
    if (result.indexOf("Verified: fail") === 0) return "var(--bad)";
    if (result.indexOf("Not run") === 0) return "color-mix(in srgb, var(--muted) 18%, var(--bg))";
    return "transparent";
  }
  function drawVerifyGrid(runs, opts) {
    runs = runs || [];
    opts = opts || {};
    var box = el("div", { cls: "chart" });
    if (!runs.length) return box;
    var stages = opts.stages ? opts.stages.slice() : [];
    if (!opts.stages) runs.forEach(function (r) {
      r.stages.forEach(function (e) {
        if (stages.indexOf(e.stage) < 0 && /^(Verified|Not run)/.test(e.result || "")) stages.push(e.stage);
      });
    });
    if (!stages.length) return box;
    var CELL = 14, GAP = 3, LBL = 90, TOP = 18, W = LBL + runs.length * (CELL + GAP) + 8, H = TOP + stages.length * (CELL + GAP) + 18;
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, "class": "chart-svg grid-svg", role: "img",
      "aria-label": "Verify runs, " + runs.length + " runs" });
    svg.style.maxWidth = W + "px";
    stages.forEach(function (st, r) {
      svg.appendChild(svgText(LBL - 6, TOP + r * (CELL + GAP) + CELL - 3, st, "end"));
    });
    runs.forEach(function (run, c) {
      var cx = LBL + c * (CELL + GAP);
      var when = (run.generated || run.folder || "").replace("T", " ").replace(/Z$/, "");
      if (run.dirty) svg.appendChild(svgEl("circle", { cx: cx + CELL / 2, cy: TOP - 7, r: 2.5, fill: "var(--warn)" },
        "dirty working tree at " + when));
      var byStage = {};
      run.stages.forEach(function (e) { byStage[e.stage] = e; });
      stages.forEach(function (st, r) {
        var e = byStage[st] || {};
        var tip = st + " · " + when + " · " + (e.result || "absent") + (e.seconds != null ? " · " + Math.round(e.seconds) + "s" : "");
        var cell = svgEl("rect", { x: cx, y: TOP + r * (CELL + GAP), width: CELL, height: CELL, rx: 2,
          fill: verifyFill(e.result) }, tip);
        if (opts.onCell && /^Verified/.test(e.result || "")) {
          cell.style.cursor = "pointer";
          cell.addEventListener("click", function () { opts.onCell(run, st); });
        }
        svg.appendChild(cell);
      });
    });
    var firstDay = (runs[0].generated || runs[0].folder || "").slice(0, 10);
    var lastDay = (runs[runs.length - 1].generated || runs[runs.length - 1].folder || "").slice(0, 10);
    svg.appendChild(svgText(LBL + (runs.length - 1) * (CELL + GAP) + CELL, H - 4, lastDay, "end"));
    if (firstDay !== lastDay && runs.length * (CELL + GAP) > 150) svg.appendChild(svgText(LBL, H - 4, firstDay, "start"));
    box.appendChild(svg);
    return box;
  }


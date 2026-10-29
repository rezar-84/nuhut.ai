  // ---------------------------------------------------------------- dashboard helpers
  function sparkline(values, opts) {
    opts = opts || {};
    var W = opts.w || 120, H = opts.h || 26;
    var svg = svgEl("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": opts.label || (values && values.length > 1 ? "Trend over " + values.length + " points, from " + values[0] + " to " + values[values.length - 1] : "Not enough history for a trend") });
    if (!values || values.length < 2) return svg;
    var max = Math.max.apply(null, values.concat([opts.max || 0])), min = Math.min.apply(null, values.concat([opts.min === undefined ? max : opts.min]));
    if (max === min) max = min + 1;
    var pts = values.map(function (v, i) {
      return (2 + (W - 4) * i / (values.length - 1)).toFixed(1) + "," + (H - 2 - (H - 4) * (v - min) / (max - min)).toFixed(1);
    });
    svg.appendChild(svgEl("polyline", { points: pts.join(" "), fill: "none", stroke: opts.color || "var(--link)", "stroke-width": "1.6", "stroke-linejoin": "round" }));
    var last = pts[pts.length - 1].split(",");
    svg.appendChild(svgEl("circle", { cx: last[0], cy: last[1], r: "2.2", fill: opts.color || "var(--link)" }));
    return svg;
  }
  function metricValue(name) {
    var m = (M.metrics || []).filter(function (x) { return x.name.toLowerCase().indexOf(name.toLowerCase()) >= 0; })[0];
    return m || null;
  }
  function kpi(label, value, tone, spark, tip, route, sub) {
    var k = el("div", { cls: "kpi " + (tone || "") + (route ? " link" : ""), title: tip || "" }, [
      el("div", { cls: "k-label", text: label }),
      el("div", { cls: "k-val", text: value }),
      sub ? el("div", { cls: "k-sub", text: sub }) : null,
      spark || null
    ]);
    if (route) makeInteractive(k, function () { go(route); }, label + ": " + value);
    if (route) k.addEventListener("click", function () { go(route); });
    return k;
  }
  function ckCard(id, title, sowhat, kids, extraCls, action) {
    return el("section", { cls: "ck-card " + (extraCls || ""), id: "ck-" + id, "aria-labelledby": "ck-h-" + id }, [
      el("h2", { id: "ck-h-" + id }, [el("span", { text: title }), action || null]),
      sowhat ? el("p", { cls: "sowhat", text: sowhat }) : null
    ].concat(kids));
  }
  function hbars(rows, max) {
    var box = el("div");
    max = max || Math.max.apply(null, rows.map(function (r) { return r[1]; }).concat([1]));
    rows.forEach(function (r) {
      box.appendChild(el("div", { cls: "hbar", title: r[0] + ": " + r[1] + (r[3] ? " — " + r[3] : "") }, [
        el("span", { style: "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;", text: r[0] }),
        el("div", { cls: "track" }, [el("div", { cls: "fill", style: "width: " + Math.round(100 * r[1] / max) + "%;" + (r[2] ? " background: " + r[2] + ";" : "") })]),
        el("span", { cls: "muted", style: "text-align: right;", text: String(r[1]) })
      ]));
    });
    return box;
  }

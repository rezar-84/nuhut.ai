  // ---------------------------------------------------------------- item
  var ITEM_TAB = "overview";
  function viewItem(id) {
    var it = ITEMS[id];
    tab("");
    if (!it) {
      crumbs([[id]]);
      main.appendChild(el("p", { text: "No work item " + id + " in the records." }));
      return;
    }
    crumbs([[id]]);
    main.appendChild(el("div", { cls: "view-header" }, [
      el("h1", null, [id + " — " + (it.title || "(untitled)")]),
      el("div", { cls: "view-header-actions" }, [
        el("button", { cls: "btn", text: "Thread", on: { click: function () { go("threads/" + encodeURIComponent(id)); } } }),
        el("button", { cls: "btn", text: "Board", on: { click: function () { go("board/focus/" + encodeURIComponent(id)); } } }),
        el("button", { cls: "btn", text: "Inspector", title: "Open in the side panel", on: { click: function () { openItemDrawer(id); } } })
      ])
    ]));
    main.appendChild(el("div", null, [
      colChip(it.column),
      it.status && it.status !== it.column ? el("span", { cls: "chip", text: it.status }) : null,
      it.tier ? el("span", { cls: "chip", text: "Tier " + it.tier }) : null,
      ownerOf(it) ? el("span", { cls: "chip", text: ownerOf(it) }) : null,
      it.orphan ? el("span", { cls: "chip", text: "not in the backlog" }) : null,
      it.row ? el("span", { cls: "muted", text: " " + it.row }) : null
    ]));
    var steps = el("div", { cls: "steps", title: "Lifecycle, filled from the records that exist" });
    M.steps.forEach(function (s) {
      var st = (it.steps || {})[s] || "n/a";
      steps.appendChild(el("span", { cls: "step " + (st === "n/a" ? "na" : st), text: s + (st === "missing" ? " ?" : ""),
        title: st === "missing" ? "Expected for this tier and status, but no record of it was found" : st }));
    });
    main.appendChild(steps);
    // Who wrote it, who reviewed it, and what the evidence ledger holds: read-only facts
    // from commit trailers, review files and docs/project/evidence-ledger.jsonl.
    var proof = el("div", { cls: "proof" });
    if (it.author) proof.appendChild(el("div", null, [el("span", { cls: "muted", text: "Author: " }), it.author]));
    (it.reviews || []).forEach(function (r) {
      proof.appendChild(el("div", null, [
        el("span", { cls: "muted", text: (r.stage === "design" ? "Design" : "Ship") + " review: " }),
        r.reviewer + " ",
        el("span", { cls: "chip " + (r.independent ? "ok" : "warn"),
          text: r.independent ? "independent" : "self-check",
          title: r.independent ? "A different model family from the author" :
            "Same model family as the author, or unknown: recorded, cannot clear a gate" }),
        el("span", { cls: "muted", text: "  " + r.file })]));
    });
    if ((it.evidence || []).length) {
      var ev = el("div", null, [el("span", { cls: "muted", text: "Evidence: " })]);
      it.evidence.forEach(function (e, n) {
        if (n) ev.appendChild(document.createTextNode(" · "));
        ev.appendChild(el("span", { cls: "chip " + (/pass/.test(e.result) ? "ok" : (/fail/.test(e.result) ? "bad" : "")),
          text: e.stage + " " + (/pass/.test(e.result) ? "pass" : "fail"),
          title: e.result + " at " + e.commit + (e.dirty ? " (uncommitted change)" : "") + ", " + e.time }));
      });
      proof.appendChild(ev);
    } else if (it.steps && it.steps.Verify === "missing") {
      proof.appendChild(el("div", { cls: "muted", text: "Evidence: no sdlc.py verify run recorded for this item's commits" }));
    }
    if (proof.childNodes.length) main.appendChild(proof);
    var rel = el("div");
    function rels(label, list) {
      if (!list || !list.length) return;
      var p = el("div", null, [el("span", { cls: "muted", text: label + ": " })]);
      list.forEach(function (d, n) {
        if (n) p.appendChild(document.createTextNode(", "));
        p.appendChild(itemLink(d));
        if (ITEMS[d]) p.appendChild(el("span", { cls: "muted", text: " (" + ITEMS[d].column + ")" }));
      });
      rel.appendChild(p);
    }
    rels("Depends on", it.depends);
    rels("Needed by", it.dependents);
    var epics = M.epics.filter(function (e) { return e.items.indexOf(id) >= 0; }).map(function (e) { return e.name; });
    if (epics.length) rel.appendChild(el("div", null, [el("span", { cls: "muted", text: "Epic: " }), epics.join(", ")]));
    main.appendChild(rel);

    var records = (it.records || []), wl = (it.worklog || []), mentions = (it.mentioned_in || []), commits = (it.commits || []);
    var tabs = [["overview", "Row"], ["worklog", "Worklog (" + wl.length + ")"], ["records", "Records (" + records.length + ")"],
      ["mentions", "Mentioned in (" + mentions.length + ")"], ["commits", "Commits (" + commits.length + ")"]];
    var bar = el("div", { cls: "tabsbar" });
    tabs.forEach(function (t) {
      bar.appendChild(el("a", { cls: ITEM_TAB === t[0] ? "on" : "", text: t[1],
        on: { click: function () { ITEM_TAB = t[0]; render(); } } }));
    });
    main.appendChild(bar);
    var body = el("div");
    main.appendChild(body);
    if (ITEM_TAB === "overview") {
      var t = el("table");
      [["Task", it.title], ["Tier", it.tier], ["Owner role", it.owner], ["Depends on", it.depends_text], ["Status", it.status],
        ["Backlog section", it.section]].concat(Object.keys(it.extra || {}).map(function (k) { return [k, it.extra[k]]; }))
        .forEach(function (r) { if (r[1]) t.appendChild(el("tr", null, [el("th", { text: r[0] }), el("td", null, [inline(r[1])])])); });
      body.appendChild(t);
    } else if (ITEM_TAB === "worklog") {
      if (!wl.length) body.appendChild(el("p", { cls: "muted", text: "No worklog entry names this item." }));
      wl.forEach(function (n) { body.appendChild(entryBox(n, true)); });
    } else if (ITEM_TAB === "records") {
      if (!records.length) body.appendChild(el("p", { cls: "muted", text: "No plan, review, defect or postmortem file is named after this item." }));
      records.forEach(function (n) {
        var d = DOCS[n];
        body.appendChild(el("h2", null, [link(d.path, docRoute(n))]));
        body.appendChild(renderMd(d.text, d.path.split("/").slice(0, -1).join("/")));
      });
    } else if (ITEM_TAB === "mentions") {
      var ul = el("ul");
      mentions.forEach(function (n) { ul.appendChild(el("li", null, [link(DOCS[n].path, docRoute(n))])); });
      if (!mentions.length) body.appendChild(el("p", { cls: "muted", text: "No other record mentions this item." }));
      body.appendChild(ul);
    } else {
      var ct = el("table", null, [el("tr", null, [el("th", { text: "Commit" }), el("th", { text: "Date" }), el("th", { text: "Author" }), el("th", { text: "Subject" })])]);
      commits.forEach(function (c) { ct.appendChild(el("tr", null, [el("td", null, [el("code", { text: c.sha })]), el("td", { text: c.date }), el("td", { text: c.author || "" }), el("td", null, [inline(c.subject)])])); });
      if (!commits.length) body.appendChild(el("p", { cls: "muted", text: "No commit subject carries this ID." }));
      else body.appendChild(ct);
    }
  }


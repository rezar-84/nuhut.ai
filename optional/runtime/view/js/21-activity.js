  // ---------------------------------------------------------------- activity
  function entryBox(n, full) {
    var e = WL[n], it = ITEMS[e.id] || {};
    var box = el("div", { cls: "entry" }, [el("div", { cls: "hd" }, [
      el("strong", null, [itemLink(e.id)]), el("span", { text: e.title }),
      e.date ? el("span", { cls: "chip", text: e.date }) : null,
      e.status ? el("span", { cls: "chip", text: e.status }) : null,
      it.column ? colChip(it.column) : null,
      el("a", { cls: "muted", href: "#/" + docRoute(DOC_BY_PATH[e.source] !== undefined ? DOC_BY_PATH[e.source] : 0, e.line - 1),
        text: e.source.split("/").pop() + ":" + e.line })
    ])]);
    var secs = Object.keys(e.sections);
    (full ? secs : secs.filter(function (s) { return /^(What changed|Summary|Not done)$/i.test(s); })).forEach(function (s) {
      var body = e.sections[s];
      if (!body) return;
      if (!full && s !== "Not done") body = body.split("\n").slice(0, 6).join("\n");
      box.appendChild(el("div", { cls: "muted", text: s }));
      box.appendChild(renderMd(body, ""));
    });
    return box;
  }

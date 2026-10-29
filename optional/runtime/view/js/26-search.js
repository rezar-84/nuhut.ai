  // ---------------------------------------------------------------- search
  function viewSearch(term) {
    tab("");
    crumbs([[M.project || "Project", "dashboard"], ["Search: " + term]]);
    main.appendChild(h(1, "Search: " + term));
    var needle = term.toLowerCase(), hits = 0;
    var ids = M.order.filter(function (id) { return (id + " " + (ITEMS[id].title || "")).toLowerCase().indexOf(needle) >= 0; });
    if (ids.length) {
      main.appendChild(h(2, "Work items"));
      var ul = el("ul");
      ids.slice(0, 100).forEach(function (id) { ul.appendChild(el("li", null, [itemLink(id), " " + ITEMS[id].title + " ", colChip(ITEMS[id].column)])); });
      main.appendChild(ul);
      hits += ids.length;
    }
    var docHits = el("ul");
    DOCS.forEach(function (d, n) {
      if (d.path.toLowerCase().indexOf(needle) >= 0 || (d.title || "").toLowerCase().indexOf(needle) >= 0) {
        docHits.appendChild(el("li", null, [link(d.path, docRoute(n))]));
        hits++;
      }
      d.headings.forEach(function (x) {
        if (x.text.toLowerCase().indexOf(needle) >= 0) {
          docHits.appendChild(el("li", null, [link(x.text, docRoute(n, x.line)), el("span", { cls: "muted", text: "  in " + d.path })]));
          hits++;
        }
      });
    });
    if (docHits.childNodes.length) { main.appendChild(h(2, "Documents and sections")); main.appendChild(docHits); }
    if (M.git && M.git.commits && M.git.commits.length) {
      var commitHits = M.git.commits.filter(function (c) {
        return (c.sha + " " + c.subject + " " + (c.author || "")).toLowerCase().indexOf(needle) >= 0;
      });
      if (commitHits.length) {
        main.appendChild(h(2, "Git commits (" + commitHits.length + ")"));
        var cul = el("ul");
        commitHits.slice(0, 20).forEach(function (c) {
          cul.appendChild(el("li", null, [
            el("code", { text: c.sha }), " ",
            el("span", { cls: "muted", text: c.date + (c.author ? " · " + c.author : "") + ": " }),
            inline(c.subject)
          ]));
        });
        main.appendChild(cul);
        hits += commitHits.length;
      }
    }
    if (!hits) main.appendChild(el("p", { cls: "muted", text: "Nothing matches." }));
  }



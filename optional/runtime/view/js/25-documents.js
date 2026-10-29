  // ---------------------------------------------------------------- documents
  var DOCS_STATE = {
    view: "split",
    selectedPath: "",
    query: "",
    status: "all",
    sidebarVisible: true
  };

  function viewDocs() {
    tab("docs");
    crumbs([[M.project || "Project", "dashboard"], ["Documents"]]);
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [
        el("h1", { text: "Project Documents & Records" }),
        el("p", { cls: "view-subtitle", text: "Browse charter, architecture decision records, plans, reviews, and process playbooks with freshness tracking." })
      ]),
      el("div", { cls: "view-header-actions" }, [
        el("button", { cls: "btn", text: "Specs", on: { click: function () { go("docs/specs"); } } }),
        el("button", { cls: "btn", text: "Kit settings ↗", on: { click: function () { go("project/kit"); } } })
      ])
    ]));

    // Sub-toolbar with view switchers and filters
    var tb = el("div", { cls: "sub-toolbar" });
    var left = el("div", { cls: "sub-toolbar-left" });
    var right = el("div", { cls: "sub-toolbar-right" });

    // View mode toggle
    var seg = el("div", { cls: "view-segmented" });
    var btnSplit = el("button", { text: "Explorer", cls: DOCS_STATE.view === "split" ? "active" : "", "aria-pressed": DOCS_STATE.view === "split" ? "true" : "false" });
    var btnTable = el("button", { text: "Table", cls: DOCS_STATE.view === "table" ? "active" : "", "aria-pressed": DOCS_STATE.view === "table" ? "true" : "false" });
    seg.appendChild(btnSplit);
    seg.appendChild(btnTable);
    left.appendChild(seg);

    // Sidebar toggle button (for explorer mode)
    var btnSidebar = el("button", {
      cls: "btn" + (DOCS_STATE.sidebarVisible ? " active" : ""),
      "aria-pressed": DOCS_STATE.sidebarVisible ? "true" : "false",
      text: DOCS_STATE.sidebarVisible ? "Hide Sidebar" : "Show Sidebar",
      style: DOCS_STATE.view === "split" ? "font-size: 12px; padding: 4px 10px;" : "display: none;"
    });
    left.appendChild(btnSidebar);

    btnSplit.onclick = function () {
      DOCS_STATE.view = "split";
      btnSplit.classList.add("active");
      btnSplit.setAttribute("aria-pressed", "true");
      btnTable.classList.remove("active");
      btnTable.setAttribute("aria-pressed", "false");
      btnSidebar.style.display = "font-size: 12px; padding: 4px 10px;";
      renderDocsContent();
    };

    btnTable.onclick = function () {
      DOCS_STATE.view = "table";
      btnTable.classList.add("active");
      btnTable.setAttribute("aria-pressed", "true");
      btnSplit.classList.remove("active");
      btnSplit.setAttribute("aria-pressed", "false");
      btnSidebar.style.display = "none";
      renderDocsContent();
    };

    btnSidebar.onclick = function () {
      DOCS_STATE.sidebarVisible = !DOCS_STATE.sidebarVisible;
      btnSidebar.textContent = DOCS_STATE.sidebarVisible ? "Hide Sidebar" : "Show Sidebar";
      btnSidebar.classList.toggle("active", DOCS_STATE.sidebarVisible);
      btnSidebar.setAttribute("aria-pressed", DOCS_STATE.sidebarVisible ? "true" : "false");
      var splitEl = document.getElementById("docs-split-container");
      if (splitEl) {
        splitEl.classList.toggle("sidebar-hidden", !DOCS_STATE.sidebarVisible);
      }
    };

    // Search filter input
    var searchInp = el("input", {
      type: "search",
      cls: "filter-input",
      placeholder: "Filter documents...",
      "aria-label": "Filter documents",
      value: DOCS_STATE.query || ""
    });
    searchInp.style.minWidth = "200px";
    searchInp.oninput = function () {
      DOCS_STATE.query = searchInp.value;
      renderDocsContent();
    };
    left.appendChild(searchInp);

    // Status filter
    var allStatuses = [];
    DOCS.forEach(function (d) {
      var s = (d.meta && d.meta.status) ? String(d.meta.status).trim() : "";
      if (s && allStatuses.indexOf(s) < 0) allStatuses.push(s);
    });
    allStatuses.sort();

    var statusSel = el("select", { cls: "filter-select", "aria-label": "Filter by document status" }, [el("option", { value: "all", text: "All Statuses" })]);
    allStatuses.forEach(function (s) {
      var opt = el("option", { value: s, text: "Status: " + s });
      if (DOCS_STATE.status === s) opt.selected = true;
      statusSel.appendChild(opt);
    });
    statusSel.onchange = function () {
      DOCS_STATE.status = statusSel.value;
      renderDocsContent();
    };
    left.appendChild(statusSel);

    var countBadge = el("span", { cls: "chip", text: DOCS.length + " docs" });
    right.appendChild(countBadge);

    tb.appendChild(left);
    tb.appendChild(right);
    main.appendChild(tb);

    var contentContainer = el("div", { id: "docs-content-container" });
    main.appendChild(contentContainer);

    var staleDays = (M.kit && M.kit.constraints && M.kit.constraints.staleness_days) || 90;

    function getFilteredDocs() {
      var q = (DOCS_STATE.query || "").toLowerCase().trim();
      var st = DOCS_STATE.status || "all";
      return DOCS.filter(function (d) {
        if (st !== "all") {
          var s = (d.meta && d.meta.status) ? String(d.meta.status).toLowerCase().trim() : "";
          if (s !== st.toLowerCase()) return false;
        }
        if (q) {
          var match = (d.path || "").toLowerCase().indexOf(q) >= 0 ||
                      (d.title || "").toLowerCase().indexOf(q) >= 0 ||
                      (d.kind || "").toLowerCase().indexOf(q) >= 0 ||
                      (d.meta && d.meta.owner && String(d.meta.owner).toLowerCase().indexOf(q) >= 0);
          if (!match) return false;
        }
        return true;
      });
    }

    function renderDocsContent() {
      contentContainer.innerHTML = "";
      var filtered = getFilteredDocs();
      countBadge.textContent = filtered.length + " / " + DOCS.length + " docs";

      if (DOCS_STATE.view === "table") {
        renderTableView(filtered);
      } else {
        renderSplitView(filtered);
      }
    }

    function renderTableView(filtered) {
      if (!filtered.length) {
        contentContainer.appendChild(el("p", { cls: "muted", text: "No documents match the current search or status filter." }));
        return;
      }
      var t = el("table", { cls: "board-table" });
      var ths = ["Document", "Directory / Kind", "Status", "Owner", "Last Reviewed", "Days Ago", "Actions"];
      t.appendChild(el("tr", null, ths.map(function (x) { return el("th", { text: x }); })));

      filtered.forEach(function (d) {
        var n = DOC_BY_PATH[d.path];
        var age = daysSince(d.meta ? d.meta["last-reviewed"] : null);
        var dirName = d.path.indexOf("/") >= 0 ? d.path.slice(0, d.path.lastIndexOf("/")) : "root";
        var fileName = d.path.slice(d.path.lastIndexOf("/") + 1);

        var tdDoc = el("td", null, [
          link(fileName, docRoute(n)),
          el("div", { cls: "muted", text: d.title && d.title !== fileName ? d.title : d.path, style: "font-size: 11px; margin-top: 2px;" })
        ]);

        var tdKind = el("td", null, [
          el("code", { text: dirName, style: "font-size: 11px; color: var(--muted);" }),
          d.kind ? el("span", { cls: "chip", text: d.kind, style: "margin-left: 6px; font-size: 10.5px;" }) : ""
        ]);

        var tdStatus = el("td", null, [
          d.meta && d.meta.status ? el("span", { cls: "chip status " + d.meta.status, text: d.meta.status }) : el("span", { cls: "muted", text: "—" })
        ]);

        var tdOwner = el("td", null, [
          d.meta && d.meta.owner ? el("span", { text: "@" + d.meta.owner, style: "font-weight: 500;" }) : el("span", { cls: "muted", text: "—" })
        ]);

        var tdReviewed = el("td", { text: (d.meta && d.meta["last-reviewed"]) || "—" });
        var tdAge = el("td", { text: age === null ? "—" : String(age) + "d" });
        if (age !== null && age > staleDays) tdAge.style.color = "var(--c-Blocked)";

        var tdActions = el("td", null, [
          el("button", {
            text: "Preview",
            cls: "btn",
            style: "padding: 3px 8px; font-size: 11.5px; margin-right: 6px;",
            onclick: function () {
              DOCS_STATE.view = "split";
              DOCS_STATE.selectedPath = d.path;
              btnSplit.classList.add("active");
              btnSplit.setAttribute("aria-pressed", "true");
              btnTable.classList.remove("active");
              btnTable.setAttribute("aria-pressed", "false");
              btnSidebar.style.display = "";
              renderDocsContent();
            }
          }),
          link("Open ↗", docRoute(n))
        ]);

        t.appendChild(el("tr", null, [tdDoc, tdKind, tdStatus, tdOwner, tdReviewed, tdAge, tdActions]));
      });

      contentContainer.appendChild(el("div", { cls: "wrap", style: "margin-top: 10px;" }, [t]));
    }

    function renderSplitView(filtered) {
      if (!filtered.length) {
        contentContainer.appendChild(el("p", { cls: "muted", text: "No documents match the current search or status filter." }));
        return;
      }

      // Ensure valid selectedPath
      var curSelected = null;
      if (DOCS_STATE.selectedPath) {
        curSelected = filtered.filter(function (d) { return d.path === DOCS_STATE.selectedPath; })[0];
      }
      if (!curSelected && filtered.length > 0) {
        curSelected = filtered[0];
        DOCS_STATE.selectedPath = curSelected.path;
      }

      var split = el("div", {
        id: "docs-split-container",
        cls: "docs-split" + (DOCS_STATE.sidebarVisible ? "" : " sidebar-hidden")
      });
      var treePane = el("div", { cls: "docs-tree-pane" });
      var previewPane = el("div", { cls: "docs-preview-pane" });

      // Group filtered docs by folder
      var groups = {};
      var groupOrder = [];
      filtered.forEach(function (d) {
        var dir = d.path.indexOf("/") >= 0 ? d.path.slice(0, d.path.lastIndexOf("/")) : "Root";
        if (!groups[dir]) {
          groups[dir] = [];
          groupOrder.push(dir);
        }
        groups[dir].push(d);
      });

      // Render Tree Folders
      groupOrder.forEach(function (dir) {
        var folderBox = el("div", { cls: "tree-folder" });
        var folderHdr = el("div", { cls: "tree-folder-title" });
        folderHdr.innerHTML = "<span>" + dir + "</span> <span class='chip' style='margin-left:auto; font-size:10px;'>" + groups[dir].length + "</span>";

        var folderItems = el("div", { cls: "tree-folder-items" });

        groups[dir].forEach(function (d) {
          var isSelected = curSelected && curSelected.path === d.path;
          var fileName = d.path.slice(d.path.lastIndexOf("/") + 1);
          var itemRow = el("div", { cls: "tree-doc-item" + (isSelected ? " active" : "") });

          var leftPart = el("div", { style: "display:flex; align-items:center; gap:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" });
          var titleEl = el("span", { text: fileName, style: "font-weight:" + (isSelected ? "600" : "400") + "; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" });
          titleEl.title = d.path + (d.title ? " (" + d.title + ")" : "");
          leftPart.appendChild(titleEl);
          itemRow.appendChild(leftPart);

          var rightPart = el("div", { style: "display:flex; align-items:center; gap:4px; margin-left:8px; flex-shrink:0;" });
          if (d.meta && d.meta.status) {
            rightPart.appendChild(el("span", { cls: "chip status " + d.meta.status, text: d.meta.status, style: "font-size:10px; padding:1px 5px;" }));
          }
          var age = daysSince(d.meta ? d.meta["last-reviewed"] : null);
          if (age !== null) {
            var ageChip = el("span", { cls: "muted", text: age + "d", style: "font-size:10px;" });
            if (age > staleDays) ageChip.style.color = "var(--c-Blocked)";
            rightPart.appendChild(ageChip);
          }
          itemRow.appendChild(rightPart);

          function selectDocItem() {
            DOCS_STATE.selectedPath = d.path;
            var allItems = treePane.querySelectorAll(".tree-doc-item");
            for (var i = 0; i < allItems.length; i++) allItems[i].classList.remove("active");
            itemRow.classList.add("active");
            renderPreview(d);
          }

          itemRow.onclick = selectDocItem;
          makeInteractive(itemRow, selectDocItem, d.path);
          itemRow.addEventListener("keydown", function (e) {
            var allItems = Array.prototype.slice.call(treePane.querySelectorAll(".tree-doc-item"));
            var idx = allItems.indexOf(itemRow);
            if ((e.key === "ArrowDown" || e.key === "j") && idx >= 0 && idx + 1 < allItems.length) {
              e.preventDefault();
              allItems[idx + 1].focus();
              allItems[idx + 1].click();
            } else if ((e.key === "ArrowUp" || e.key === "k") && idx > 0) {
              e.preventDefault();
              allItems[idx - 1].focus();
              allItems[idx - 1].click();
            }
          });

          folderItems.appendChild(itemRow);
        });

        folderBox.appendChild(folderHdr);
        folderBox.appendChild(folderItems);
        treePane.appendChild(folderBox);
      });

      // Preview Renderer
      function renderPreview(doc) {
        previewPane.innerHTML = "";
        if (!doc) {
          previewPane.appendChild(el("p", { cls: "muted", text: "Select a document from the explorer on the left to preview it." }));
          return;
        }

        var n = DOC_BY_PATH[doc.path];
        var hdr = el("div", { cls: "docs-preview-hdr" });

        var hdrLeft = el("div", null);
        var docTitle = doc.title || doc.path.slice(doc.path.lastIndexOf("/") + 1);
        hdrLeft.appendChild(h(2, docTitle));

        var metaBar = el("div", { style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:6px; font-size:12px;" });
        metaBar.appendChild(el("code", { text: doc.path, style: "color:var(--text); background:var(--chip); padding:2px 6px; border-radius:4px;" }));
        if (doc.kind) metaBar.appendChild(el("span", { cls: "chip", text: "kind: " + doc.kind }));
        if (doc.meta && doc.meta.status) metaBar.appendChild(el("span", { cls: "chip status " + doc.meta.status, text: "status: " + doc.meta.status }));
        if (doc.meta && doc.meta.owner) metaBar.appendChild(el("span", { cls: "chip", text: "owner: @" + doc.meta.owner }));
        if (doc.meta && doc.meta["last-reviewed"]) {
          var age = daysSince(doc.meta["last-reviewed"]);
          metaBar.appendChild(el("span", { cls: "muted", text: "Reviewed: " + doc.meta["last-reviewed"] + (age !== null ? " (" + age + "d ago)" : "") }));
        }
        hdrLeft.appendChild(metaBar);

        var hdrRight = el("div", { style: "display:flex; align-items:center; gap:8px;" });
        var openFullBtn = el("a", {
          href: "#/" + docRoute(n),
          cls: "btn primary",
          text: "Open Full View ↗",
          style: "font-weight:600; text-decoration:none; padding:6px 12px; font-size:12.5px;"
        });
        hdrRight.appendChild(openFullBtn);

        hdr.appendChild(hdrLeft);
        hdr.appendChild(hdrRight);
        previewPane.appendChild(hdr);

        // Linked Items / mentions
        if (doc.mentions && doc.mentions.length) {
          var mentionsBox = el("div", { style: "margin-bottom:14px; padding:8px 12px; background:var(--panel); border:1px solid var(--line); border-radius:6px; font-size:12px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;" });
          mentionsBox.appendChild(el("strong", { text: "Linked Items:" }));
          doc.mentions.forEach(function (id) {
            mentionsBox.appendChild(itemLink(id));
          });
          previewPane.appendChild(mentionsBox);
        }

        // Quick table of contents outline if headings exist
        var tocLinks = [];
        if (doc.headings && doc.headings.length > 1) {
          var tocBox = el("div", { style: "margin-bottom:16px; padding:10px 12px; background:var(--panel); border-radius:6px; border:1px solid var(--line); font-size:12px;" });
          tocBox.appendChild(el("div", { text: "Outline", style: "font-weight:600; margin-bottom:6px; color:var(--muted); text-transform:uppercase; font-size:11px; letter-spacing:0.04em;" }));
          var tocList = el("div", { style: "display:flex; flex-wrap:wrap; gap:6px;" });
          doc.headings.forEach(function (hd) {
            var jumpLink = el("a", {
              href: "#/" + docRoute(n, hd.line),
              "data-line": String(hd.line),
              text: hd.text,
              style: "background:var(--bg); border:1px solid var(--line); padding:2px 8px; border-radius:4px; color:var(--link); text-decoration:none; font-size:11.5px;"
            });
            jumpLink.onclick = function (e) {
              var target = previewPane.querySelector("#L" + hd.line);
              if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: "smooth" });
                target.classList.add("flash");
              }
            };
            tocLinks.push(jumpLink);
            tocList.appendChild(jumpLink);
          });
          tocBox.appendChild(tocList);
          previewPane.appendChild(tocBox);
        }

        // Render Markdown body
        var baseDir = doc.path.indexOf("/") >= 0 ? doc.path.slice(0, doc.path.lastIndexOf("/")) : "";
        var body = renderMd(doc.text, baseDir);
        if (doc.truncated) {
          var truncBox = el("p", { cls: "banner", text: "This document is truncated in preview mode. Click 'Open Full View' to view the full file." });
          truncBox.style.marginTop = "12px";
          body.appendChild(truncBox);
        }
        previewPane.appendChild(body);

        if (tocLinks.length) {
          previewPane.onscroll = function () {
            var headings = body.querySelectorAll("h1, h2, h3, h4");
            var currentId = "";
            var paneRect = previewPane.getBoundingClientRect();
            for (var i = 0; i < headings.length; i++) {
              var rect = headings[i].getBoundingClientRect();
              if (rect.top - paneRect.top <= 80) {
                currentId = headings[i].id;
              } else {
                break;
              }
            }
            if (!currentId && headings.length) currentId = headings[0].id;
            var curLine = currentId.replace(/^L/, "");
            tocLinks.forEach(function (aEl) {
              var isAct = aEl.getAttribute("data-line") === curLine;
              aEl.style.borderColor = isAct ? "var(--link)" : "var(--line)";
              aEl.style.fontWeight = isAct ? "600" : "400";
            });
          };
        }
      }

      if (curSelected) {
        renderPreview(curSelected);
      }

      split.appendChild(treePane);
      split.appendChild(previewPane);
      contentContainer.appendChild(split);
    }

    renderDocsContent();
  }
  var currentDocScrollSpy = null;
  function viewDoc(path, line) {
    var n = DOC_BY_PATH[path];
    tab("docs");
    crumbs([[M.project || "Project", "dashboard"], ["Documents", "docs"], [path]]);
    if (n === undefined) { main.appendChild(el("p", { text: "No document at " + path + "." })); return; }
    var d = DOCS[n];
    var outline = el("div", { cls: "outline" });
    d.headings.forEach(function (x) {
      var a = el("a", { href: "#/" + docRoute(n, x.line), text: x.text, "data-line": String(x.line) });
      a.style.paddingLeft = (x.level - 1) * 10 + "px";
      outline.appendChild(a);
    });
    var body = renderMd(d.text, path.split("/").slice(0, -1).join("/"));
    if (d.truncated) body.appendChild(el("p", { cls: "banner", text: "This document is longer than the view keeps; the rest is in the file." }));
    main.appendChild(el("div", { cls: "docgrid" }, [outline, body]));
    if (line !== undefined) {
      var target = document.getElementById("L" + line);
      if (target) { target.scrollIntoView(); target.classList.add("flash"); }
    }

    if (currentDocScrollSpy) {
      window.removeEventListener("scroll", currentDocScrollSpy);
      currentDocScrollSpy = null;
    }

    var headingLinks = outline.querySelectorAll("a[data-line]");
    function updateOutlineActive() {
      var headings = body.querySelectorAll("h1, h2, h3, h4");
      var currentId = "";
      for (var i = 0; i < headings.length; i++) {
        var rect = headings[i].getBoundingClientRect();
        if (rect.top <= 90) {
          currentId = headings[i].id;
        } else {
          break;
        }
      }
      if (!currentId && headings.length) currentId = headings[0].id;
      var curLine = currentId.replace(/^L/, "");
      for (var j = 0; j < headingLinks.length; j++) {
        var aEl = headingLinks[j];
        if (aEl.getAttribute("data-line") === curLine) {
          aEl.className = "active";
        } else {
          aEl.className = "";
        }
      }
    }
    currentDocScrollSpy = updateOutlineActive;
    window.addEventListener("scroll", updateOutlineActive, { passive: true });
    setTimeout(updateOutlineActive, 80);
  }

  // ---------------------------------------------------------------- specs
  // What the system does now (living specs), the changes items make to it, and specs
  // other tools wrote (OpenSpec, Spec Kit), labelled and read-only.
  var SPECS_STATE = { source: "", sel: "" };
  function viewSpecs(cap) {
    tab("docs");
    crumbs([["Documents", "docs"], ["Specs"]]);
    var S = M.specs || { capabilities: [], changes: [], imported: [] };
    var all = (S.capabilities || []).concat(S.imported || []);
    dashHeader("Specs", S.enabled ? "What the system does now, one capability per file, and the changes work items make to it."
      : "Specs are off in the charter. Turn them on with python3 .ai-sdlc/bin/sdlc.py config --specs on" + (all.length ? "; specs other tools wrote are shown below." : "."), []);
    if (S.error) main.appendChild(el("p", { cls: "quiet-note", text: "Specs could not be read: " + S.error }));
    var pending = {};
    (S.changes || []).forEach(function (ch) {
      Object.keys(ch.sections).forEach(function (k) {
        ch.sections[k].forEach(function (r) {
          var key = (r.capability || "") + "|" + r.name;
          (pending[key] = pending[key] || []).push({ kind: k, item: ch.item, source: ch.source });
        });
      });
    });
    var sources = [];
    all.forEach(function (c) { if (sources.indexOf(c.source) < 0) sources.push(c.source); });
    var list = el("div", { cls: "md-list", role: "list", "aria-label": "Capabilities" });
    var pane = el("div", { cls: "md-pane" });
    var srcSel = sel("Source", [["", "All sources"]].concat(sources.map(function (x) { return [x, x === "nuhut" ? "This kit" : (x === "openspec" ? "OpenSpec" : "Spec Kit")]; })), SPECS_STATE.source,
      function (v) { SPECS_STATE.source = v; fill(); });
    main.appendChild(el("div", { cls: "md" }, [el("div", { cls: "md-left" }, [el("div", { cls: "md-filters" }, [srcSel]), list]), pane]));
    var current = cap || SPECS_STATE.sel || (all[0] && all[0].source + ":" + all[0].capability) || "";
    function key(c) { return c.source + ":" + c.capability; }
    function fill() {
      list.textContent = "";
      all.filter(function (c) { return !SPECS_STATE.source || c.source === SPECS_STATE.source; }).forEach(function (c) {
        var changes = c.requirements.reduce(function (n, r) { return n + ((pending[c.capability + "|" + r.name] || []).length); }, 0);
        var row = el("div", { cls: "run-row" + (key(c) === current ? " sel" : ""), role: "listitem" }, [
          el("span", { cls: "rr-dot", "aria-hidden": "true", style: changes ? "background: var(--warn);" : "" }),
          el("span", { style: "min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" }, [el("strong", { text: c.capability }), el("span", { cls: "muted", text: " " + (c.title || "") })]),
          el("span", { cls: "muted", text: plural(c.requirements.length, "req") }),
          el("span", { cls: "muted", text: c.source })
        ]);
        var open = function () { SPECS_STATE.sel = key(c); location.replace("#/docs/specs/" + encodeURIComponent(key(c))); };
        row.addEventListener("click", open); makeInteractive(row, open, c.capability);
        list.appendChild(row);
      });
      if (!all.length) list.appendChild(el("p", { cls: "muted", style: "padding: 10px;", text: "No specs yet. Copy templates/spec.md to project/specs/<capability>.md." }));
    }
    fill();
    var spec = all.filter(function (c) { return key(c) === current; })[0];
    // New capabilities that only exist in pending changes.
    var unplaced = (S.changes || []).filter(function (ch) { return Object.keys(ch.sections).some(function (k) { return ch.sections[k].length; }); });
    if (!spec) {
      pane.appendChild(el("p", { cls: "muted", text: all.length ? "Pick a capability." : "Nothing to show." }));
    } else {
      pane.appendChild(el("div", { cls: "md-pane-hd" }, [el("div", null, [el("strong", { text: spec.title || spec.capability }),
        el("div", { cls: "muted", style: "font-size: 12px;", text: spec.path + (spec.best_effort ? " · read best-effort" : "") })]),
        DOC_BY_PATH[spec.path] !== undefined ? link("Open file", docRoute(DOC_BY_PATH[spec.path]), "btn") : null]));
      if (spec.purpose) pane.appendChild(el("p", { cls: "sec-sub", text: spec.purpose }));
      spec.requirements.forEach(function (r) {
        var pend = pending[spec.capability + "|" + r.name] || [];
        pane.appendChild(el("div", { cls: "req" }, [
          el("div", { cls: "req-hd" }, [el("strong", { text: r.name })].concat(pend.map(function (p) {
            return el("span", { cls: "stamp " + (p.kind === "REMOVED" ? "neutral" : "warn"), title: "Pending in " + p.item, text: p.kind.toLowerCase() + " by " + p.item });
          }))),
          r.body ? el("p", { cls: "req-body", text: r.body }) : null,
          el("ul", { cls: "req-scen" }, r.scenarios.map(function (sc) { return el("li", null, [el("strong", { text: sc.name + ": " }), sc.body.replace(/\*\*/g, "").replace(/\n+/g, " ")]); }))
        ]));
      });
    }
    if (unplaced.length) main.appendChild(section("Pending changes", "Spec changes not yet applied. `sdlc.py spec apply <ID> --write` merges one on close.", [
      table(["Item", "Source", "Changes", "File"], unplaced.map(function (ch) {
        return tr([itemLink(ch.item), ch.source, Object.keys(ch.sections).filter(function (k) { return ch.sections[k].length; }).map(function (k) { return ch.sections[k].length + " " + k.toLowerCase(); }).join(", "),
          el("code", { text: ch.path })]);
      }))]));
    if ((S.problems || []).length) main.appendChild(section("Problems", null, [table(["Where", "Problem"], S.problems.map(function (p) { return tr([el("code", { text: p.where }), p.message]); }))]));
  }

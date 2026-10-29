  // ---------------------------------------------------------------- git
  var GIT_FILTER = { query: "", mode: "all", branch: "all", view: "graph" };

  var GRAPH_COLORS = [
    "#388bfd",
    "#a371f7",
    "#3fb950",
    "#d29922",
    "#f85149",
    "#1f6feb",
    "#db61a2",
    "#56d364"
  ];

  function authorColor(name) {
    var hash = 0;
    for (var i = 0; i < (name || "").length; i++) hash = (hash * 31 + name.charCodeAt(i)) & 0xffffff;
    return GRAPH_COLORS[Math.abs(hash) % GRAPH_COLORS.length];
  }

  function authorInitials(name) {
    if (!name) return "?";
    var parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }

  function timeAgo(dateStr) {
    if (!dateStr) return "";
    var d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    var now = new Date();
    var diffSec = Math.floor((now - d) / 1000);
    if (diffSec < 60) return "just now";
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + "m ago";
    var diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return diffHours + "h ago";
    var diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "yesterday";
    if (diffDays < 30) return diffDays + "d ago";
    return dateStr;
  }

  function openCommitDrawer(c) {
    setInspect({ kind: "commit", id: c.sha, c: c });
    var container = el("div", { style: "display: flex; flex-direction: column; height: 100%;" });
    var remoteWeb = (M.git && M.git.remote_url) ? M.git.remote_url : "";
    var commitUrl = remoteWeb ? (remoteWeb + "/commit/" + c.sha) : "";

    var hdrLinks = [
      el("strong", { style: "font-family: monospace; font-size: 15px;", text: c.sha }),
      el("button", {
        cls: "codeblock-copy",
        text: "Copy SHA",
        style: "font-size: 11px; padding: 2px 8px;",
        on: { click: function (e) {
          if (navigator.clipboard) {
            navigator.clipboard.writeText(c.sha).then(function () {
              e.target.textContent = "Copied!";
              setTimeout(function () { e.target.textContent = "Copy SHA"; }, 1500);
            });
          }
        } }
      })
    ];
    if (commitUrl) {
      hdrLinks.push(el("a", {
        href: commitUrl,
        target: "_blank",
        rel: "noopener",
        cls: "chip",
        text: "View on GitHub ↗"
      }));
    }

    var hdr = el("div", { cls: "drawer-header" }, [
      el("div", { style: "display: flex; align-items: baseline; gap: 8px; min-width: 0;" }, hdrLinks),
      el("button", { cls: "drawer-close", text: "✕", on: { click: closeDrawer } })
    ]);
    container.appendChild(hdr);

    var body = el("div", { cls: "drawer-body" });
    body.appendChild(el("h2", {
      style: "margin-top: 0; font-size: 16px; text-transform: none; color: var(--text); font-weight: 600; line-height: 1.4;",
      text: c.subject || "(no commit subject)"
    }));

    if (c.refs && c.refs.length) {
      var refWrap = el("div", { style: "margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 4px;" });
      c.refs.forEach(function (r) {
        var isHead = /HEAD/.test(r);
        var isTag = /^tag:/.test(r);
        var cls = isHead ? "git-ref git-ref-head" : (isTag ? "git-ref git-ref-tag" : "git-ref git-ref-remote");
        refWrap.appendChild(el("span", { cls: cls, text: (isTag ? "tag: " : "") + r.replace(/^tag:\s*/, "") }));
      });
      body.appendChild(refWrap);
    }

    var infoCard = el("div", {
      style: "margin-bottom: 14px; padding: 10px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; font-size: 12px;"
    }, [
      el("div", { style: "display: flex; align-items: center; gap: 8px; margin-bottom: 4px;" }, [
        el("div", {
          cls: "git-avatar",
          style: "background: " + authorColor(c.author || ""),
          text: authorInitials(c.author || "")
        }),
        el("strong", { text: c.author || "Unknown author" }),
        el("span", { cls: "muted", text: "· " + (c.date ? timeAgo(c.date) + " (" + c.date + ")" : "") })
      ])
    ]);
    body.appendChild(infoCard);

    if (c.parents && c.parents.length) {
      var parentRow = el("div", { style: "margin-bottom: 12px; font-size: 12px;" }, [
        el("span", { cls: "muted", text: "Parent commit" + (c.parents.length > 1 ? "s" : "") + ": " })
      ]);
      c.parents.forEach(function (p, pi) {
        if (pi > 0) parentRow.appendChild(document.createTextNode(", "));
        var pLink = el("a", {
          style: "font-family: monospace; font-size: 12px; color: var(--link); cursor: pointer; text-decoration: underline;",
          text: p,
          on: { click: function () {
            var targetRow = document.getElementById("commit-" + p);
            if (targetRow) {
              targetRow.scrollIntoView({ behavior: "smooth", block: "center" });
              targetRow.classList.add("flash");
              setTimeout(function () { targetRow.classList.remove("flash"); }, 1500);
            }
          } }
        });
        parentRow.appendChild(pLink);
      });
      body.appendChild(parentRow);
    }

    if (c.items && c.items.length) {
      var itemSection = el("div", { style: "margin-bottom: 14px;" });
      itemSection.appendChild(el("div", {
        style: "font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--muted); margin-bottom: 6px; letter-spacing: 0.05em;",
        text: "Linked Work Items (" + c.items.length + ")"
      }));
      c.items.forEach(function (id) {
        var it = ITEMS[id];
        var itemCard = el("div", {
          style: "display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; margin-bottom: 4px; background: var(--panel); border: 1px solid var(--line); border-radius: 6px; font-size: 12px; cursor: pointer;",
          on: { click: function () { openItemDrawer(id); } }
        }, [
          el("div", { style: "display: flex; align-items: center; gap: 6px;" }, [
            el("strong", { text: id }),
            el("span", { cls: "muted", text: clip(it ? it.title : "", 35) })
          ]),
          it ? colChip(it.column) : null
        ]);
        itemSection.appendChild(itemCard);
      });
      body.appendChild(itemSection);
    }

    var cliBox = el("div", {
      style: "margin-top: 16px; padding: 10px; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; font-size: 11px;"
    });
    cliBox.appendChild(el("div", { style: "font-weight: 600; color: var(--muted); margin-bottom: 6px;", text: "Git CLI Commands:" }));
    ["git checkout " + c.sha, "git show " + c.sha].forEach(function (cmd) {
      var cmdRow = el("div", {
        style: "display: flex; align-items: center; justify-content: space-between; padding: 3px 0; font-family: monospace;"
      }, [
        el("code", { text: cmd }),
        el("button", {
          cls: "codeblock-copy",
          text: "Copy",
          style: "font-size: 10px;",
          on: { click: function (e) {
            if (navigator.clipboard) {
              navigator.clipboard.writeText(cmd).then(function () {
                e.target.textContent = "Copied!";
                setTimeout(function () { e.target.textContent = "Copy"; }, 1500);
              });
            }
          } }
        })
      ]);
      cliBox.appendChild(cmdRow);
    });
    body.appendChild(cliBox);

    container.appendChild(body);
    openDrawer(container);
  }

  function computeGitGraph(commits) {
    var lanes = [];
    var laneColors = [];
    var colorSeq = 0;
    var graphRows = [];

    commits.forEach(function (c) {
      var sha = c.sha;
      var parents = c.parents || [];

      var myLane = -1;
      for (var l = 0; l < lanes.length; l++) {
        if (lanes[l] === sha) { myLane = l; break; }
      }
      if (myLane === -1) {
        for (var l = 0; l < lanes.length; l++) {
          if (lanes[l] === null) { myLane = l; break; }
        }
        if (myLane === -1) myLane = lanes.length;
        lanes[myLane] = sha;
        laneColors[myLane] = GRAPH_COLORS[colorSeq++ % GRAPH_COLORS.length];
      }

      var myColor = laneColors[myLane];
      var lines = [];

      for (var l = 0; l < lanes.length; l++) {
        if (l !== myLane && lanes[l] !== null) {
          lines.push({ from: l, to: l, color: laneColors[l], type: "pass" });
        }
      }

      if (parents.length === 0) {
        lanes[myLane] = null;
      } else {
        var p0 = parents[0];
        var p0Lane = -1;
        for (var l = 0; l < lanes.length; l++) {
          if (l !== myLane && lanes[l] === p0) { p0Lane = l; break; }
        }
        if (p0Lane !== -1) {
          lines.push({ from: myLane, to: p0Lane, color: myColor, type: "merge" });
          lanes[myLane] = null;
        } else {
          lines.push({ from: myLane, to: myLane, color: myColor, type: "straight" });
          lanes[myLane] = p0;
        }

        for (var pi = 1; pi < parents.length; pi++) {
          var pN = parents[pi];
          var pNLane = -1;
          for (var l = 0; l < lanes.length; l++) {
            if (lanes[l] === pN) { pNLane = l; break; }
          }
          if (pNLane === -1) {
            for (var l = 0; l < lanes.length; l++) {
              if (lanes[l] === null) { pNLane = l; break; }
            }
            if (pNLane === -1) pNLane = lanes.length;
            lanes[pNLane] = pN;
            laneColors[pNLane] = GRAPH_COLORS[colorSeq++ % GRAPH_COLORS.length];
          }
          lines.push({ from: myLane, to: pNLane, color: laneColors[pNLane] || myColor, type: "fork" });
        }
      }

      while (lanes.length > 0 && lanes[lanes.length - 1] === null) {
        lanes.pop();
      }

      graphRows.push({
        commit: c,
        lane: myLane,
        color: myColor,
        isMerge: parents.length > 1,
        activeLanes: Math.max(myLane + 1, lanes.length, 1),
        lines: lines
      });
    });

    var maxLanes = 1;
    graphRows.forEach(function (r) { maxLanes = Math.max(maxLanes, r.activeLanes); });
    return { rows: graphRows, maxLanes: maxLanes };
  }

  function drawGraphCell(rowInfo, maxLanes) {
    var NS = "http://www.w3.org/2000/svg";
    var LANE_W = 16;
    var ROW_H = 32;
    var totalW = maxLanes * LANE_W + 12;

    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "git-graph-svg");
    svg.setAttribute("width", String(totalW));
    svg.setAttribute("height", String(ROW_H));

    function xOf(lane) { return lane * LANE_W + 8; }
    var myX = xOf(rowInfo.lane);
    var myY = ROW_H / 2;

    rowInfo.lines.forEach(function (ln) {
      var x1 = xOf(ln.from), x2 = xOf(ln.to);
      var p = document.createElementNS(NS, "path");
      var d;
      if (ln.type === "pass") {
        d = "M " + x1 + " 0 L " + x2 + " " + ROW_H;
      } else if (ln.type === "straight") {
        d = "M " + x1 + " " + myY + " L " + x2 + " " + ROW_H;
      } else {
        var cy1 = myY + 8, cy2 = ROW_H - 4;
        d = "M " + x1 + " " + myY + " C " + x1 + " " + cy1 + " " + x2 + " " + cy2 + " " + x2 + " " + ROW_H;
      }
      p.setAttribute("d", d);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", ln.color);
      p.setAttribute("stroke-width", "2");
      p.setAttribute("stroke-linecap", "round");
      svg.appendChild(p);
    });

    var topPath = document.createElementNS(NS, "path");
    topPath.setAttribute("d", "M " + myX + " 0 L " + myX + " " + myY);
    topPath.setAttribute("fill", "none");
    topPath.setAttribute("stroke", rowInfo.color);
    topPath.setAttribute("stroke-width", "2");
    svg.appendChild(topPath);

    var isHead = (rowInfo.commit.refs || []).some(function (r) { return /HEAD/.test(r); });
    if (isHead) {
      var halo = document.createElementNS(NS, "circle");
      halo.setAttribute("cx", String(myX));
      halo.setAttribute("cy", String(myY));
      halo.setAttribute("r", "6.5");
      halo.setAttribute("fill", "none");
      halo.setAttribute("stroke", rowInfo.color);
      halo.setAttribute("stroke-width", "1.5");
      halo.setAttribute("stroke-dasharray", "2 2");
      svg.appendChild(halo);
    }

    var dot = document.createElementNS(NS, "circle");
    dot.setAttribute("cx", String(myX));
    dot.setAttribute("cy", String(myY));
    dot.setAttribute("r", rowInfo.isMerge ? "4.5" : "3.5");
    dot.setAttribute("fill", rowInfo.isMerge ? "var(--panel)" : rowInfo.color);
    dot.setAttribute("stroke", rowInfo.color);
    dot.setAttribute("stroke-width", "2");
    svg.appendChild(dot);

    return svg;
  }

  var GIT_STATE = { tab: "graph", mode: "all", query: "", author: "", viewStyle: "graph" };

  function viewGit() {
    tab("git");
    crumbs([[M.project || "Project", "dashboard"], ["Git"]]);
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [
        el("h1", { text: "Git & Traceability" }),
        el("p", { cls: "view-subtitle", text: "Commit graph, work-item trailer traceability, working tree status, and local branch lineage." })
      ]),
      el("div", { cls: "view-header-actions" }, [
        el("button", { cls: "btn", text: "Inbox ↗", on: { click: function () { go("threads"); } } })
      ])
    ]));

    var git = M.git || { branch: "", clean: true, modified_count: 0, modified_files: [], branches: [], commits: [], stats: { total: 0, linked: 0, untracked: 0, rate: 0 } };
    var stats = git.stats || { total: 0, linked: 0, untracked: 0, rate: 0 };
    var allCommits = git.commits || [];

    var strip = el("div", { cls: "strip" });
    if (git.branch) {
      var sBranch = el("div", { cls: "stat" }, [
        el("span", { cls: "muted", text: "Branch: " }),
        el("strong", { text: git.branch })
      ]);
      strip.appendChild(sBranch);
    }

    var sStatus = el("div", {
      cls: "stat clickable" + (GIT_STATE.tab === "working_tree" ? " active" : ""),
      title: "Click to inspect working tree files",
      "aria-pressed": GIT_STATE.tab === "working_tree" ? "true" : "false",
      on: { click: function () {
        GIT_STATE.tab = (GIT_STATE.tab === "working_tree" ? "graph" : "working_tree");
        render();
      } }
    }, [
      el("span", { cls: "muted", text: "Working tree: " }),
      git.clean
        ? el("span", { text: "Clean", style: "color: var(--accent); font-weight: 600;" })
        : el("span", { text: git.modified_count + " uncommitted file" + (git.modified_count > 1 ? "s" : ""), style: "color: var(--warn); font-weight: 600;" }),
      GIT_STATE.tab === "working_tree" ? el("span", { cls: "stat-filter-badge", text: "VIEWING" }) : null
    ]);
    makeInteractive(sStatus, function () {
      GIT_STATE.tab = (GIT_STATE.tab === "working_tree" ? "graph" : "working_tree");
      render();
    }, "Inspect working tree");
    strip.appendChild(sStatus);

    var sRate = el("div", {
      cls: "stat clickable" + (GIT_STATE.tab === "graph" && GIT_STATE.mode === "linked" ? " active" : ""),
      title: "Click to filter linked commits",
      "aria-pressed": (GIT_STATE.tab === "graph" && GIT_STATE.mode === "linked") ? "true" : "false",
      on: { click: function () {
        GIT_STATE.tab = "graph";
        GIT_STATE.mode = (GIT_STATE.mode === "linked" ? "all" : "linked");
        render();
      } }
    }, [
      el("b", { text: stats.rate + "%" }),
      el("span", { text: "Traceability (" + stats.linked + "/" + stats.total + " linked)" }),
      (GIT_STATE.tab === "graph" && GIT_STATE.mode === "linked") ? el("span", { cls: "stat-filter-badge", text: "FILTER" }) : null
    ]);
    makeInteractive(sRate, function () {
      GIT_STATE.tab = "graph";
      GIT_STATE.mode = (GIT_STATE.mode === "linked" ? "all" : "linked");
      render();
    }, "Filter linked commits");
    strip.appendChild(sRate);

    if (stats.untracked > 0) {
      var sUntracked = el("div", {
        cls: "stat clickable" + (GIT_STATE.tab === "graph" && GIT_STATE.mode === "untracked" ? " active" : ""),
        title: "Click to filter untracked commits",
        "aria-pressed": (GIT_STATE.tab === "graph" && GIT_STATE.mode === "untracked") ? "true" : "false",
        on: { click: function () {
          GIT_STATE.tab = "graph";
          GIT_STATE.mode = (GIT_STATE.mode === "untracked" ? "all" : "untracked");
          render();
        } }
      }, [
        el("b", { text: String(stats.untracked) }),
        el("span", { text: "Untracked commits" }),
        (GIT_STATE.tab === "graph" && GIT_STATE.mode === "untracked") ? el("span", { cls: "stat-filter-badge", text: "FILTER" }) : null
      ]);
      makeInteractive(sUntracked, function () {
        GIT_STATE.tab = "graph";
        GIT_STATE.mode = (GIT_STATE.mode === "untracked" ? "all" : "untracked");
        render();
      }, "Filter untracked commits");
      strip.appendChild(sUntracked);
    }

    if (git.branches && git.branches.length) {
      var sBranches = el("div", {
        cls: "stat clickable" + (GIT_STATE.tab === "branches" ? " active" : ""),
        title: "Click to view local branches",
        "aria-pressed": GIT_STATE.tab === "branches" ? "true" : "false",
        on: { click: function () {
          GIT_STATE.tab = (GIT_STATE.tab === "branches" ? "graph" : "branches");
          render();
        } }
      }, [
        el("b", { text: String(git.branches.length) }),
        el("span", { text: "Local branches" }),
        GIT_STATE.tab === "branches" ? el("span", { cls: "stat-filter-badge", text: "VIEWING" }) : null
      ]);
      makeInteractive(sBranches, function () {
        GIT_STATE.tab = (GIT_STATE.tab === "branches" ? "graph" : "branches");
        render();
      }, "View local branches");
      strip.appendChild(sBranches);
    }
    main.appendChild(strip);

    var viewSwitcher = el("div", { cls: "view-segmented" }, [
      el("button", {
        cls: (GIT_STATE.tab === "graph" ? "active" : ""),
        "aria-pressed": GIT_STATE.tab === "graph" ? "true" : "false",
        text: "Commit Graph (" + allCommits.length + ")",
        on: { click: function () { GIT_STATE.tab = "graph"; render(); } }
      }),
      el("button", {
        cls: (GIT_STATE.tab === "working_tree" ? "active" : ""),
        "aria-pressed": GIT_STATE.tab === "working_tree" ? "true" : "false",
        text: "Working Tree (" + (git.clean ? "Clean" : git.modified_count) + ")",
        style: (!git.clean ? "color: var(--warn); font-weight: 600;" : ""),
        on: { click: function () { GIT_STATE.tab = "working_tree"; render(); } }
      }),
      el("button", {
        cls: (GIT_STATE.tab === "branches" ? "active" : ""),
        "aria-pressed": GIT_STATE.tab === "branches" ? "true" : "false",
        text: "Branches & Remotes (" + ((git.branches || []).length) + ")",
        on: { click: function () { GIT_STATE.tab = "branches"; render(); } }
      })
    ]);

    var rightToolbar = [];
    if (GIT_STATE.tab === "graph") {
      var authors = {};
      allCommits.forEach(function (c) { if (c.author) authors[c.author] = (authors[c.author] || 0) + 1; });

      var authorSel = el("select", {
        cls: "filter-select",
        "aria-label": "Filter by Author",
        on: { change: function () { GIT_STATE.author = authorSel.value; renderCommitList(); } }
      }, [
        el("option", { value: "", text: "All authors" })
      ].concat(Object.keys(authors).sort().map(function (a) {
        var opt = el("option", { value: a, text: a + " (" + authors[a] + ")" });
        if (GIT_STATE.author === a) opt.selected = true;
        return opt;
      })));

      var modeSel = el("select", {
        cls: "filter-select",
        "aria-label": "Commit filter mode",
        on: { change: function () { GIT_STATE.mode = modeSel.value; renderCommitList(); } }
      }, [
        el("option", { value: "all", text: "All commits (" + allCommits.length + ")" }),
        el("option", { value: "linked", text: "Linked to work items (" + stats.linked + ")" }),
        el("option", { value: "untracked", text: "Untracked commits (" + stats.untracked + ")" })
      ]);
      modeSel.value = GIT_STATE.mode;

      var viewStyleSel = el("select", {
        cls: "filter-select",
        "aria-label": "Graph view style",
        on: { change: function () { GIT_STATE.viewStyle = viewStyleSel.value; renderCommitList(); } }
      }, [
        el("option", { value: "graph", text: "Visual Graph" }),
        el("option", { value: "table", text: "Table" })
      ]);
      viewStyleSel.value = GIT_STATE.viewStyle;

      var qInput = el("input", {
        type: "search",
        cls: "filter-input",
        placeholder: "Filter commits, authors, SHAs…",
        value: GIT_STATE.query,
        style: "flex: 1 1 200px; max-width: 260px;",
        on: { input: function () { GIT_STATE.query = qInput.value; renderCommitList(); } }
      });

      rightToolbar = [viewStyleSel, modeSel, authorSel, qInput];
    }

    main.appendChild(el("div", { cls: "sub-toolbar" }, [
      el("div", { cls: "sub-toolbar-left" }, [viewSwitcher]),
      el("div", { cls: "sub-toolbar-right" }, rightToolbar)
    ]));

    var contentContainer = el("div");
    main.appendChild(contentContainer);

    if (GIT_STATE.tab === "working_tree") {
      contentContainer.appendChild(h(2, "Working Tree & Local Modifications"));
      if (git.clean || !git.modified_files || !git.modified_files.length) {
        var cleanBox = el("div", { cls: "banner", style: "border-color: var(--accent); background: var(--okbg);" }, [
          el("strong", { style: "color: var(--accent);", text: "Working tree is clean." }),
          el("p", { cls: "muted", style: "margin: 4px 0 0; font-size: 13px;", text: "All tracked and local files match the current HEAD commit." })
        ]);
        contentContainer.appendChild(cleanBox);
      } else {
        var warnBox = el("p", { cls: "quiet-note" }, [
          el("strong", { text: plural(git.modified_files.length, "uncommitted file") + ". " }),
          "Run verify before committing, and name a work item in the message."
        ]);
        contentContainer.appendChild(warnBox);

        var wt = el("table");
        wt.appendChild(el("tr", null, [
          el("th", { text: "Status", style: "width: 80px;" }),
          el("th", { text: "Path" }),
          el("th", { text: "Detected Item", style: "width: 140px;" })
        ]));

        git.modified_files.forEach(function (f) {
          var matchedId = null;
          var m = f.path.match(/([A-Z][A-Z0-9]+-[0-9]+)/);
          if (m && ITEMS[m[1]]) matchedId = m[1];

          var statusBadge = el("span", {
            cls: "chip",
            style: "font-weight: 700; font-family: monospace; " +
              (f.status.indexOf("M") >= 0 ? "background: rgba(191,135,0,0.15); color: #bf8700;" :
               (f.status.indexOf("A") >= 0 || f.status.indexOf("?") >= 0 ? "background: var(--okbg); color: var(--accent);" : "background: var(--badbg); color: var(--bad);")),
            text: f.status
          });

          wt.appendChild(el("tr", null, [
            el("td", null, [statusBadge]),
            el("td", null, [el("code", { text: f.path })]),
            el("td", null, [matchedId ? itemLink(matchedId) : el("span", { cls: "muted", text: "—" })])
          ]));
        });
        contentContainer.appendChild(el("div", { cls: "wrap" }, [wt]));
      }
      return;
    }

    if (GIT_STATE.tab === "branches") {
      contentContainer.appendChild(h(2, "Local Branches (" + (git.branches || []).length + ")"));
      if (!git.branches || !git.branches.length) {
        contentContainer.appendChild(el("p", { cls: "muted", text: "No local branch information available." }));
      } else {
        var bt = el("table", null, [el("tr", null, ["Branch", "Linked Work Items", "Last Commit Date", "Last Commit Subject"].map(function (x) {
          return el("th", { text: x });
        }))]);
        git.branches.forEach(function (b) {
          var nameCell = el("td");
          if (b.current) {
            nameCell.appendChild(el("span", { cls: "chip", text: "HEAD", style: "background: var(--okbg); color: var(--accent); font-weight: 700; margin-right: 6px;" }));
            nameCell.appendChild(el("strong", { text: b.name }));
          } else {
            nameCell.appendChild(document.createTextNode(b.name));
          }
          var itemsCell = el("td");
          if (b.items && b.items.length) {
            b.items.forEach(function (id) {
              itemsCell.appendChild(itemLink(id));
              itemsCell.appendChild(document.createTextNode(" "));
            });
          } else {
            itemsCell.appendChild(el("span", { cls: "muted", text: "—" }));
          }
          bt.appendChild(el("tr", null, [
            nameCell,
            itemsCell,
            el("td", { text: b.date || "" }),
            el("td", null, [inline(b.subject || "")])
          ]));
        });
        contentContainer.appendChild(el("div", { cls: "wrap" }, [bt]));
      }
      return;
    }

    // Tab: graph
    var shownCommits = 75;
    function renderCommitList() {
      contentContainer.textContent = "";
      var needle = (GIT_STATE.query || "").trim().toLowerCase();
      var filtered = allCommits.filter(function (c) {
        if (GIT_STATE.mode === "linked" && (!c.items || !c.items.length)) return false;
        if (GIT_STATE.mode === "untracked" && c.items && c.items.length) return false;
        if (GIT_STATE.author && c.author !== GIT_STATE.author) return false;
        if (!needle) return true;
        if (c.sha.toLowerCase().indexOf(needle) >= 0) return true;
        if ((c.subject || "").toLowerCase().indexOf(needle) >= 0) return true;
        if ((c.author || "").toLowerCase().indexOf(needle) >= 0) return true;
        if (c.items && c.items.some(function (id) { return id.toLowerCase().indexOf(needle) >= 0; })) return true;
        return false;
      });

      if (!filtered.length) {
        contentContainer.appendChild(el("p", { cls: "muted", text: "No commits match the filter." }));
        return;
      }

      var commitsToDisplay = filtered.slice(0, shownCommits);
      var graphData = computeGitGraph(commitsToDisplay);

      var tableHeaders = GIT_STATE.viewStyle === "graph"
        ? ["Graph", "Commit / Subject", "Author", "Date", "SHA"]
        : ["SHA", "Date", "Author", "Subject", "Linked Items"];

      var ct = el("table", { cls: "git-graph-table" }, [
        el("tr", null, tableHeaders.map(function (x) { return el("th", { text: x }); }))
      ]);

      graphData.rows.forEach(function (r) {
        var c = r.commit;
        var tr = el("tr", {
          cls: "git-row",
          id: "commit-" + c.sha,
          on: { click: function (e) {
            if (e.target.tagName !== "A" && !e.target.classList.contains("codeblock-copy")) {
              openCommitDrawer(c);
            }
          } }
        });

        if (GIT_STATE.viewStyle === "graph") {
          var graphCell = el("td", { cls: "git-graph-cell" }, [drawGraphCell(r, graphData.maxLanes)]);
          tr.appendChild(graphCell);

          var subjectCell = el("td");
          if (c.refs && c.refs.length) {
            c.refs.forEach(function (refName) {
              var isHead = /HEAD/.test(refName);
              var isTag = /^tag:/.test(refName);
              var cls = isHead ? "git-ref git-ref-head" : (isTag ? "git-ref git-ref-tag" : "git-ref git-ref-remote");
              subjectCell.appendChild(el("span", {
                cls: cls,
                text: (isTag ? "tag: " : "") + refName.replace(/^tag:\s*/, "")
              }));
            });
          }
          subjectCell.appendChild(inline(c.subject || ""));
          if (c.items && c.items.length) {
            subjectCell.appendChild(document.createTextNode(" "));
            c.items.forEach(function (id) {
              subjectCell.appendChild(itemLink(id));
              subjectCell.appendChild(document.createTextNode(" "));
            });
          }
          tr.appendChild(subjectCell);

          var authorCell = el("td", null, [
            el("div", { cls: "git-author-pill" }, [
              el("div", {
                cls: "git-avatar",
                style: "background: " + authorColor(c.author || ""),
                text: authorInitials(c.author || "")
              }),
              el("span", { text: c.author || "Unknown" })
            ])
          ]);
          tr.appendChild(authorCell);

          var dateCell = el("td", {
            cls: "muted",
            style: "white-space: nowrap; font-size: 12px;",
            title: c.date,
            text: timeAgo(c.date)
          });
          tr.appendChild(dateCell);

          var shaCell = el("td", { style: "white-space: nowrap;" }, [
            el("span", { cls: "git-sha-code", text: c.sha, title: "Click row for details · " + c.sha })
          ]);
          tr.appendChild(shaCell);

        } else {
          var itemsCell = el("td");
          if (c.items && c.items.length) {
            c.items.forEach(function (id) {
              itemsCell.appendChild(itemLink(id));
              itemsCell.appendChild(document.createTextNode(" "));
            });
          } else {
            itemsCell.appendChild(el("span", { cls: "chip", text: "untracked", style: "color: var(--muted); font-size: 11px;" }));
          }
          tr.appendChild(el("td", null, [el("code", { text: c.sha })]));
          tr.appendChild(el("td", { text: c.date }));
          tr.appendChild(el("td", { text: c.author || "" }));
          tr.appendChild(el("td", null, [inline(c.subject)]));
          tr.appendChild(itemsCell);
        }

        makeInteractive(tr, function () { openCommitDrawer(c); }, "Inspect commit " + c.sha);
        ct.appendChild(tr);
      });

      contentContainer.appendChild(el("div", { cls: "wrap" }, [ct]));

      if (filtered.length > shownCommits) {
        var moreBtn = el("button", {
          text: "Show more (" + (filtered.length - shownCommits) + " remaining)",
          style: "margin-top: 10px;",
          on: { click: function () { shownCommits += 50; renderCommitList(); } }
        });
        contentContainer.appendChild(moreBtn);
      }
    }

    renderCommitList();
  }


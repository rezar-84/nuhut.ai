  // ---------------------------------------------------------------- project lens
  // Everything the project is made of, in one place: stack and dependencies, build
  // errors, security, deploy and runtime, environment names, open work and the agentic
  // stack. The live page reads the full lens from /api/lens (built on demand, cached by
  // the server); a static page carries only the summary embedded in its model.
  var LENS = null, LENS_LOADING = false, LENS_ERROR = "";
  var LENS_STATE = { kind: "skill", source: "", q: "", envFilter: "missing", secArea: "", depQ: "" };
  function lensData() { return LENS || M.lens || null; }
  function loadLens(force, cb) {
    if (!LIVE) { if (cb) cb(); return; }
    if (LENS && !force) { if (cb) cb(); return; }
    if (LENS_LOADING) return;
    LENS_LOADING = true;
    fetch("api/lens", { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (data) {
      LENS = data; LENS_ERROR = data.error || "";
    }).catch(function (e) { LENS_ERROR = String(e); }).then(function () {
      LENS_LOADING = false;
      paintMeta();
      if (/^#\/project/.test(location.hash)) render();
      if (cb) cb();
    });
  }
  // The lens's real failures, for the Issues tab and Needs you.
  function lensIssues() {
    var L = lensData();
    if (!L || L.error) return [];
    var out = [], sec = L.security || L.security_top || [];
    // Doctor's own findings are already in Issues and Needs you; list each problem once.
    sec.filter(function (x) { return x.level === "fail" && x.from !== "doctor"; }).slice(0, 20).forEach(function (x) {
      out.push({ level: "fail", group: "Security", title: x.title, detail: x.area + (x.detail ? " · " + x.detail : ""), open: function () { go("project/security"); } });
    });
    var failing = (L.summary && L.summary.build && L.summary.build.failing) || [];
    if (failing.length) out.push({ level: "fail", group: "Build", title: "Build failing: " + failing.join(", "),
      detail: plural(L.summary.build.errors || 0, "error line"), open: function () { go("project/build"); } });
    ((L.agents && L.agents.issues) || []).forEach(function (x) {
      out.push({ level: "info", group: "Agentic stack", title: x.title, detail: x.detail, open: function () { go("project/agents"); } });
    });
    return out;
  }

  function lensStatusLine(area, L) {
    var s = (L && L.summary) || {};
    if (area === "stack") return ((s.stack && s.stack.languages) || []).concat((s.stack && s.stack.frameworks) || []).join(" · ") || "Nothing detected";
    if (area === "build") return s.build ? (s.build.failing && s.build.failing.length ? "Failing: " + s.build.failing.join(", ") : (s.build.run ? "Last verify run passed" : "No verify run yet")) : "";
    if (area === "security") return s.security ? (s.security.fail ? plural(s.security.fail, "problem") + " to fix" : (s.security.warn ? plural(s.security.warn, "warning") : "Nothing found")) + (s.security.audited ? "" : " · no dependency audit yet") : "";
    if (area === "deploy") return s.deploy ? ((s.deploy.platforms || []).join(", ") || "No deploy platform found") + " · " + plural(s.deploy.workflows || 0, "workflow") + " · " + plural(s.deploy.dockerfiles || 0, "Dockerfile") : "";
    if (area === "env") return s.env ? plural(s.env.variables || 0, "variable") + (s.env.missing_from_template ? " · " + s.env.missing_from_template + " not in a template" : "") : "";
    if (area === "agents") return s.agents ? plural(s.agents.skills || 0, "skill") + " · " + plural(s.agents.commands || 0, "command") + " · " + plural(s.agents.mcp || 0, "MCP server") : "";
    return "";
  }
  function lensTone(area, L) {
    var s = (L && L.summary) || {};
    if (area === "build") return s.build && s.build.failing && s.build.failing.length ? "bad" : "ok";
    if (area === "security") return s.security ? (s.security.fail ? "bad" : (s.security.warn ? "warn" : "ok")) : "";
    if (area === "env") return s.env && s.env.missing_from_template ? "warn" : "";
    if (area === "agents") return s.agents && s.agents.issues ? "warn" : "";
    return "";
  }
  var LENS_AREAS = [["stack", "Stack & dependencies"], ["build", "Build & errors"], ["security", "Security"],
    ["deploy", "Deploy & runtime"], ["env", "Environment"], ["work", "Work"], ["agents", "Agents & skills"], ["kit", "Kit settings"]];

  function viewProject(area) {
    if (area === "kit") {
      viewKit();
      var nav = el("nav", { cls: "lens-tabs", "aria-label": "Project areas" }, [link("Overview", "project", "")].concat(
        LENS_AREAS.map(function (a) { return link(a[1], "project/" + a[0], a[0] === "kit" ? "on" : ""); })));
      main.insertBefore(nav, main.children[1] || null);
      return;
    }
    tab("project");
    var label = (LENS_AREAS.filter(function (a) { return a[0] === area; })[0] || [])[1];
    crumbs(area ? [["Project", "project"], [label || area]] : [["Project"]]);
    var L = lensData();
    loadLens(false);
    var sub = el("nav", { cls: "lens-tabs", "aria-label": "Project areas" }, [link("Overview", "project", !area ? "on" : "")].concat(
      LENS_AREAS.map(function (a) { return link(a[1], "project/" + a[0], area === a[0] ? "on" : ""); })));
    if (!L) {
      dashHeader("Project", "Stack, build, security, deploy, environment, work and the agentic stack.", []);
      main.appendChild(sub);
      main.appendChild(el("p", { cls: "muted", text: LIVE ? (LENS_ERROR ? "The lens could not be loaded: " + LENS_ERROR : "Reading the project…") : "This page was exported without the project lens. Run python3 .ai-sdlc/bin/sdlc.py view --serve, or sdlc.py lens." }));
      return;
    }
    if (L.error) {
      dashHeader("Project", "", []);
      main.appendChild(sub);
      main.appendChild(el("p", { cls: "quiet-note", text: L.error }));
      return;
    }
    var summaryOnly = !!L.summary_only;
    var head = summaryOnly ? el("p", { cls: "quiet-note", text: "This static page carries the summary only; run python3 .ai-sdlc/bin/sdlc.py view --serve for every list." }) : null;
    var fn = { stack: lensStack, build: lensBuild, security: lensSecurity, deploy: lensDeploy, env: lensEnv, work: lensWork, agents: lensAgents }[area];
    if (!fn) {
      dashHeader("Project", "What " + (M.project || "the project") + " is built from, how it ships, what is broken or exposed, and what shapes its agents.",
        [LIVE ? el("button", { cls: "btn", text: "Refresh", on: { click: function () { loadLens(true); } } }) : null]);
      main.appendChild(sub);
      if (head) main.appendChild(head);
      var grid = el("div", { cls: "cockpit" });
      main.appendChild(grid);
      LENS_AREAS.slice(0, 7).forEach(function (a) {
        var tone = lensTone(a[0], L);
        var status = a[0] === "work" ? plural((M.order || []).filter(function (id) { return /^(Now|Next|Blocked|Parked)$/.test(ITEMS[id].column); }).length, "open item")
          + " · " + plural((M.order || []).filter(function (id) { return /^(Blocked|Parked)$/.test(ITEMS[id].column); }).length, "waiting") : lensStatusLine(a[0], L);
        var card = ckCard("lens-" + a[0], a[1], null, [
          el("p", { cls: "lens-status" + (tone ? " " + tone : ""), text: status }),
          el("a", { cls: "view-all", href: "#/project/" + a[0], text: "Open " + a[1].toLowerCase() + " →" })
        ]);
        grid.appendChild(card);
      });
      return;
    }
    dashHeader(label, "", area === "security" ? [auditBtn()] : (area === "build" ? [runVerifyBtn()] : []));
    main.appendChild(sub);
    if (head) main.appendChild(head);
    if (summaryOnly && area !== "work" && area !== "security" && area !== "build") {
      main.appendChild(el("p", { cls: "lens-status", text: lensStatusLine(area, L) }));
      return;
    }
    fn(L);
  }
  function auditBtn() {
    return LIVE && M.action_token ? el("button", { cls: "btn", text: "Run dependency audit", title: "python3 .ai-sdlc/bin/sdlc.py audit", on: { click: function () {
      runKitCmd({ subcommand: "audit" }, "python3 .ai-sdlc/bin/sdlc.py audit", "audit");
      setTimeout(function () { loadLens(true); }, 1500);
    } } }) : el("button", { cls: "btn", text: "Copy audit command", on: { click: function () { copyCmd("python3 .ai-sdlc/bin/sdlc.py audit", "audit"); } } });
  }
  function section(title, sub, kids) {
    return el("section", { cls: "page-section" }, [el("h2", { cls: "sec-h", text: title }), sub ? el("p", { cls: "sec-sub", text: sub }) : null].concat(kids));
  }
  function table(headers, rows) {
    var t = el("table", { cls: "data-table" }, [el("tr", null, headers.map(function (h) { return el("th", { text: h }); }))]);
    rows.forEach(function (r) { t.appendChild(r); });
    return t;
  }
  function tr(cells, onOpen, label) {
    var row = el("tr", null, cells.map(function (c) { return el("td", null, [typeof c === "string" || typeof c === "number" ? String(c) : c]); }));
    if (onOpen) { row.style.cursor = "pointer"; row.addEventListener("click", onOpen); makeInteractive(row, onOpen, label || ""); }
    return row;
  }
  function filterBar(kids) { return el("div", { cls: "md-filters lens-filters" }, kids); }
  function sel(label, options, value, onChange) {
    var s = el("select", { cls: "filter-select", "aria-label": label, on: { change: function () { onChange(s.value); } } },
      options.map(function (o) { var x = el("option", { value: o[0], text: o[1] }); if (o[0] === value) x.selected = true; return x; }));
    return s;
  }
  function search(placeholder, value, onInput) {
    var q = el("input", { type: "search", cls: "filter-input", placeholder: placeholder, value: value, "aria-label": placeholder,
      on: { input: function () { onInput(q.value); } } });
    return q;
  }
  function detailPanel(title, rows, extra) {
    var box = el("div", { style: "display: flex; flex-direction: column; height: 100%;" }, [
      el("div", { cls: "drawer-header" }, [el("div", { style: "min-width: 0;" }, [el("strong", { text: title })]),
        el("button", { cls: "drawer-close", "aria-label": "Close", text: "✕", on: { click: closeDrawer } })]),
      el("div", { cls: "drawer-body" }, [table(["", ""], rows.filter(function (r) { return r[1]; }).map(function (r) {
        return el("tr", null, [el("th", { text: r[0], style: "width: 110px;" }), el("td", null, [typeof r[1] === "string" ? inline(r[1]) : r[1]])]);
      }))].concat(extra || []))
    ]);
    setInspect({ kind: "lens", id: title });
    openDrawer(box, { quiet: true });
  }

  function lensStack(L) {
    var st = L.stack || {};
    main.appendChild(section("Stack", "Detected from the repository's own files; nothing is installed or run to find it.", [
      table(["Area", "What"], (st.groups || []).map(function (g) { return tr([g.label, g.values.join(", ")]); }))
    ]));
    if ((st.components || []).length || st.monorepo) {
      main.appendChild(section("Components" + (st.monorepo ? " (" + st.monorepo + ")" : ""), null, [
        table(["Name", "Kind", "Path"], (st.components || []).map(function (c) { return tr([c.name, c.kind, el("code", { text: c.path })]); }))]));
    }
    if ((st.integrations || []).length) {
      main.appendChild(section("External services", null, [table(["Service", "Used for"], st.integrations.map(function (i) { return tr([i.service, i.use]); }))]));
    }
    var deps = L.dependencies || { manifests: [] };
    var box = el("div");
    function fill() {
      box.textContent = "";
      var needle = LENS_STATE.depQ.trim().toLowerCase();
      deps.manifests.forEach(function (m) {
        var rows = m.deps.filter(function (d) { return !needle || d.name.toLowerCase().indexOf(needle) >= 0; });
        if (needle && !rows.length) return;
        var det = el("details", { cls: "doc-group", open: needle ? "open" : null }, [el("summary", null, [
          el("span", { cls: "stamp neutral", text: m.kind }), el("strong", { text: m.path }),
          el("span", { cls: "muted sum-txt", text: m.lockfile ? "lockfile " + m.lockfile : "no lockfile" }),
          el("span", { cls: "muted", text: plural(m.count, "dependency", "dependencies") })])]);
        det.appendChild(el("div", { style: "padding: 0 12px 10px;" }, [table(["Package", "Version asked", "Scope"],
          rows.map(function (d) { return tr([el("code", { text: d.name }), d.version, d.scope]); }))]));
        box.appendChild(det);
      });
    }
    main.appendChild(section("Dependencies", plural(deps.total || 0, "direct dependency", "direct dependencies") + " across " + plural(deps.manifests.length, "manifest") + ". Versions are what each manifest asks for.", [
      filterBar([search("Filter packages…", LENS_STATE.depQ, function (v) { LENS_STATE.depQ = v; fill(); })]), el("div", { cls: "doc-groups" }, [box])]));
    fill();
  }

  function lensBuild(L) {
    var b = L.build || { stages: [] };
    var stages = b.stages || (L.build_top || []);
    if (!b.run && !stages.length) {
      main.appendChild(el("p", { cls: "muted", text: "No verify run yet. Run python3 .ai-sdlc/bin/sdlc.py verify; its stage logs are read here." }));
      return;
    }
    main.appendChild(el("p", { cls: "sec-sub", text: "From verify run " + (b.run || "") + (b.dirty ? " (uncommitted changes)" : "") + ". " }, [link("All runs →", "dashboard/runs")]));
    stages.filter(function (s) { return s.failed; }).forEach(function (s) {
      var rows = (s.errors || []).map(function (e) {
        return tr([e.file ? el("code", { text: e.file + (e.line ? ":" + e.line : "") }) : el("span", { cls: "muted", text: "—" }), e.message, el("span", { cls: "muted", text: e.tool })],
          function () { openLogDrawer({ kind: "evidence", id: b.run, stage: s.stage, title: "Verify " + b.run }); }, e.message);
      });
      main.appendChild(section(s.stage + " failed", (s.errors || []).length ? plural(s.errors.length, "error line") + " lifted from the log. Click one for the full log." : "No file:line errors could be lifted; open the log.", [
        rows.length ? table(["Where", "Error", "Tool"], rows) : null,
        el("button", { cls: "btn", style: "margin-top: 8px;", text: "Open the " + s.stage + " log", on: { click: function () { openLogDrawer({ kind: "evidence", id: b.run, stage: s.stage, title: "Verify " + b.run }); } } })]));
    });
    var ok = stages.filter(function (s) { return !s.failed; });
    if (ok.length) main.appendChild(section("Passing", null, [el("p", { text: ok.map(function (s) { return s.stage + (s.seconds ? " (" + fmtDur(s.seconds) + ")" : ""); }).join(" · ") })]));
  }

  function lensSecurity(L) {
    var list = L.security || L.security_top || [];
    var aud = L.audit;
    main.appendChild(el("p", { cls: "sec-sub", text: aud ? "Dependency audit " + (aud.generated || "").replace("T", " ").replace("Z", "") + " with " + (aud.tool || "") + ": " + plural((aud.vulns || []).length, "vulnerable package") + "." + (aud.error ? " " + aud.error : "")
      : "No dependency audit yet: the scanner your charter names runs only when you ask (Run dependency audit)." }));
    var areas = [];
    list.forEach(function (x) { if (areas.indexOf(x.area) < 0) areas.push(x.area); });
    var box = el("div");
    function fill() {
      box.textContent = "";
      var shown = list.filter(function (x) { return !LENS_STATE.secArea || x.area === LENS_STATE.secArea; });
      if (!shown.length) { box.appendChild(el("p", { cls: "muted", text: "Nothing found." })); return; }
      box.appendChild(table(["Level", "Area", "Finding", "Where"], shown.map(function (x) {
        return tr([el("span", { cls: "stamp " + (x.level === "fail" ? "bad" : "neutral"), text: x.level }), x.area, x.title, el("span", { cls: "muted", text: x.detail })],
          function () { detailPanel(x.title, [["Level", x.level], ["Area", x.area], ["Where", x.detail], ["Reference", x.ref]]); }, x.title);
      })));
    }
    main.appendChild(filterBar([sel("Area", [["", "All areas"]].concat(areas.map(function (a) { return [a, a]; })), LENS_STATE.secArea, function (v) { LENS_STATE.secArea = v; fill(); })]));
    main.appendChild(box);
    fill();
  }

  function lensDeploy(L) {
    var st = L.stack || {}, c = L.containers || {};
    main.appendChild(section("Deployment", (st.deploy_labels || []).length ? "Platforms with configuration in the repository." : "No deploy platform configuration found.", [
      el("p", null, [(st.deploy_labels || []).join(" · ") || "—"])]));
    main.appendChild(section("CI workflows", null, [(L.workflows || []).length ? table(["Workflow", "Triggers", "Jobs", "Deploys"], L.workflows.map(function (w) {
      return tr([el("span", null, [el("strong", { text: w.name }), el("div", { cls: "muted", text: w.file })]), w.triggers.join(", "), w.jobs.join(", "), w.deploys ? "yes" : "—"]);
    })) : el("p", { cls: "muted", text: "No .github/workflows." })]));
    main.appendChild(section("Containers", null, [
      (c.dockerfiles || []).length ? table(["Dockerfile", "Base images", "User", "Ports", "Healthcheck", "Risks"], c.dockerfiles.map(function (d) {
        return tr([el("code", { text: d.path }), d.base.join(" → "), d.user || el("span", { cls: "bad-text", text: "root" }), d.ports.join(", "), d.healthcheck ? "yes" : "—", d.risks.length ? el("span", { cls: "bad-text", text: d.risks.join("; ") }) : "—"]);
      })) : el("p", { cls: "muted", text: "No Dockerfile." })
    ].concat((c.compose || []).map(function (cf) {
      return el("div", { style: "margin-top: 12px;" }, [el("h3", { text: cf.path }), table(["Service", "Image / build", "Ports", "Env files", "Depends on", "Health"], cf.services.map(function (s) {
        return tr([el("strong", { text: s.name }), s.image || (s.build ? "build" : "—"), s.ports.join(", "), s.env_file.join(", "), s.depends_on.join(", "), s.healthcheck ? "yes" : "—"]);
      })), cf.risks.length ? el("p", { cls: "bad-text", text: cf.risks.join(" · ") }) : null]);
    })).concat(c.devcontainer ? [el("p", null, ["Dev container: ", el("code", { text: c.devcontainer.path }), " " + (c.devcontainer.image || "")])] : [])));
  }

  function lensEnv(L) {
    var e = L.env || { variables: [], templates: [], env_files: [] };
    main.appendChild(el("p", { cls: "sec-sub", text: "Variable names only: values are never read. Templates: " + (e.templates.map(function (t) { return t.path + " (" + t.count + ")"; }).join(", ") || "none") + "." }));
    if ((e.env_files || []).length) {
      main.appendChild(el("p", null, e.env_files.map(function (f) {
        return el("span", { cls: "chip", text: f.file + (f.tracked ? " · committed!" : (f.ignored ? " · git-ignored" : " · NOT ignored")) });
      })));
    }
    var box = el("div");
    function fill() {
      box.textContent = "";
      var f = LENS_STATE.envFilter;
      var rows = e.variables.filter(function (v) {
        return f === "all" || (f === "missing" && v.uses && !v.in_template && !v.builtin) || (f === "unused" && v.in_template && !v.uses) || (f === "secret" && v.secret);
      });
      box.appendChild(rows.length ? table(["Variable", "In a template", "Used in", ""], rows.map(function (v) {
        return tr([el("code", { text: v.name }), v.in_template ? "yes" : el("span", { cls: "bad-text", text: "no" }), el("span", { cls: "muted", text: v.used_in.join(", ") + (v.uses > v.used_in.length ? " +" + (v.uses - v.used_in.length) : "") }), v.secret ? el("span", { cls: "stamp neutral", text: "secret" }) : ""]);
      })) : el("p", { cls: "muted", text: "Nothing in this filter." }));
    }
    main.appendChild(filterBar([sel("Show", [["missing", "Used in code, missing from a template (" + e.missing_from_template.length + ")"], ["unused", "In a template, unused (" + e.unused_in_code.length + ")"],
      ["secret", "Secret-looking names"], ["all", "All (" + e.variables.length + ")"]], LENS_STATE.envFilter, function (v) { LENS_STATE.envFilter = v; fill(); })]));
    main.appendChild(box);
    fill();
  }

  function lensWork(L) {
    var cols = {};
    (M.order || []).forEach(function (id) { var c = ITEMS[id].column; (cols[c] = cols[c] || []).push(id); });
    var rows = ["Now", "Next", "Blocked", "Parked"].map(function (c) {
      return tr([colChip(c), String((cols[c] || []).length), el("span", { cls: "muted", text: (cols[c] || []).slice(0, 6).join(", ") + ((cols[c] || []).length > 6 ? ", …" : "") })], function () { go("board"); }, c);
    });
    main.appendChild(section("Backlog", null, [table(["Column", "Items", ""], rows)]));
    var gh = L.github;
    if (gh) {
      main.appendChild(section("GitHub", gh.error ? "gh: " + gh.error : plural(gh.issues.length, "open issue") + ", " + plural(gh.pulls.length, "open pull request") + ".", [
        table(["#", "Title", "Labels", "Updated"], gh.issues.concat(gh.pulls).map(function (x) {
          return tr([String(x.number), el("a", { href: x.url, target: "_blank", rel: "noopener noreferrer", text: x.title }), (x.labels || []).join(", "), (x.updated || "").slice(0, 10)]);
        }))]));
    } else {
      main.appendChild(el("p", { cls: "quiet-note", text: "Open GitHub issues and pull requests appear here when the page is served with: python3 .ai-sdlc/bin/sdlc.py view --serve --github" }));
    }
  }

  function lensAgents(L) {
    var a = L.agents || { items: [], counts: {} };
    var kinds = [["skill", "Skills"], ["command", "Commands"], ["subagent", "Subagents"], ["hook", "Hooks"], ["mcp", "MCP servers"], ["plugin", "Plugins"], ["harness", "Harness files"], ["rule", "Rules"]];
    var strip = el("div", { cls: "kpis secondary" }, kinds.filter(function (k) { return a.counts[k[0]]; }).map(function (k) {
      var c = a.counts[k[0]], total = Object.keys(c).reduce(function (s, x) { return s + c[x]; }, 0);
      return kpi(k[1], String(total), "", null, Object.keys(c).map(function (x) { return c[x] + " " + x; }).join(", "), null, Object.keys(c).map(function (x) { return c[x] + " " + x; }).join(" · "));
    }).concat([kpi("Always loaded", "~" + a.always_loaded_tokens + " tokens", "", null, "Skill descriptions an agent reads every turn", null, "skill descriptions"),
      kpi("Kit files", String((a.kit_files || {}).managed || 0), (a.kit_files || {}).modified ? "warn" : "ok", null, "Files the installer owns", null, ((a.kit_files || {}).modified || 0) + " modified · " + ((a.kit_files || {}).missing || 0) + " missing")]));
    main.appendChild(strip);
    if (!a.includes_user && LIVE) main.appendChild(el("p", { cls: "quiet-note", text: "User-level skills and MCP servers are hidden (the server was started with --no-user)." }));
    var box = el("div");
    function fill() {
      box.textContent = "";
      var needle = LENS_STATE.q.trim().toLowerCase();
      var rows = a.items.filter(function (i) {
        return i.kind === LENS_STATE.kind && (!LENS_STATE.source || i.source === LENS_STATE.source) &&
          (!needle || (i.name + " " + i.description + " " + i.path).toLowerCase().indexOf(needle) >= 0);
      });
      box.appendChild(rows.length ? table(["Name", "Description", "Source", "Owner", "State"], rows.map(function (i) {
        return tr([el("strong", { text: i.name }), el("span", { cls: "muted sum-txt", text: i.description }), i.source, i.owner || "—",
          i.state === "ok" ? "—" : el("span", { cls: "stamp " + (i.state === "duplicate" ? "warn" : "neutral"), text: i.state })],
          function () { detailPanel(i.name, [["Kind", i.kind], ["Description", i.description], ["Source", i.source], ["Owner", i.owner], ["State", i.state], ["Path", i.path]].concat(
            Object.keys(i.detail || {}).map(function (k) { return [k, String(i.detail[k])]; }))); }, i.kind + " " + i.name);
      })) : el("p", { cls: "muted", text: "None." }));
    }
    main.appendChild(filterBar([
      sel("Kind", kinds.map(function (k) { return [k[0], k[1] + " (" + ((a.counts[k[0]] && Object.keys(a.counts[k[0]]).reduce(function (s, x) { return s + a.counts[k[0]][x]; }, 0)) || 0) + ")"]; }), LENS_STATE.kind, function (v) { LENS_STATE.kind = v; fill(); }),
      sel("Source", [["", "All sources"], ["project", "Project"], ["user", "User (~)"]], LENS_STATE.source, function (v) { LENS_STATE.source = v; fill(); }),
      search("Filter by name or description…", LENS_STATE.q, function (v) { LENS_STATE.q = v; fill(); })
    ]));
    main.appendChild(box);
    fill();
    if ((a.other_kits || []).length) main.appendChild(section("Other kits in this repository", null, [table(["Kit", "Folder", "Files"], a.other_kits.map(function (o) { return tr([o.name, el("code", { text: o.path }), String(o.files)]); }))]));
    if ((a.issues || []).length) main.appendChild(section("Stack issues", null, [table(["Level", "Issue", "Detail"], a.issues.map(function (x) { return tr([x.level, x.title, el("span", { cls: "muted", text: x.detail })]); }))]));
    var roles = (a.roles || []).filter(function (r) { return r.active; });
    if (roles.length) main.appendChild(section("Active review roles", null, [el("p", { text: roles.map(function (r) { return r.name; }).join(" · ") })]));
  }


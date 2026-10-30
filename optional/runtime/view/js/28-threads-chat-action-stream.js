  // ---------------------------------------------------------------- threads (chat action stream)
  var THREAD_STATE = { selected: "", query: "", filter: "all", role: "", reviewer: "", reviewStage: "ship", cmdTab: "next",
    mode: "items", feedKind: "all", feedUnread: false };

  // The activity feed: every item's thread events plus worklog entries, newest day first,
  // one row per item per day so a burst of commits reads as one line.
  var FEED_KINDS = [["all", "All"], ["commit", "Commits"], ["verify", "Verify"], ["review", "Reviews"], ["gate", "Gates"], ["worklog", "Worklog"], ["record", "Records"]];
  function feedKindOf(ev) {
    if (ev.kind === "commit" || ev.kind === "verify" || ev.kind === "gate" || ev.kind === "worklog") return ev.kind;
    if (ev.kind === "design_review" || ev.kind === "ship_review") return "review";
    if (ev.kind === "spec_change") return "record";
    if (ev.kind === "frame") return "frame";
    return "record";
  }
  function buildFeed() {
    var rows = {}, out = [];
    (M.order || []).forEach(function (id) {
      var it = ITEMS[id];
      if (!itemMatchesThreadFilter(it)) return;
      if (THREAD_STATE.feedUnread && !isUnread(id)) return;
      // Only the item's latest verify run can make a row red; a failure a later run fixed is history.
      var lastVerify = null;
      (it.thread || []).forEach(function (ev) { if (ev.kind === "verify" && (!lastVerify || (ev.time || ev.date || "") >= (lastVerify.time || lastVerify.date || ""))) lastVerify = ev; });
      (it.thread || []).forEach(function (ev) {
        var fk = feedKindOf(ev);
        if (fk === "frame") return;
        if (THREAD_STATE.feedKind !== "all" && THREAD_STATE.feedKind !== fk) return;
        var day = (ev.time || ev.date || "").slice(0, 10);
        if (!day) return;
        var key = id + "|" + day;
        var r = rows[key];
        if (!r) { r = rows[key] = { id: id, day: day, latest: "", kinds: {}, events: [], bad: false }; out.push(r); }
        r.kinds[fk] = (r.kinds[fk] || 0) + 1;
        r.events.push(ev);
        var stamp = ev.time || ev.date || "";
        if (stamp > r.latest) r.latest = stamp;
        if (ev.kind === "verify" && (ev.stages || []).some(function (st) { return stageBad(st.result); })) {
          if (ev === lastVerify) r.bad = true; else r.fixed = true;
        }
      });
    });
    out.sort(function (a, b) { return b.latest.localeCompare(a.latest) || a.id.localeCompare(b.id); });
    return out;
  }
  function feedSummary(r) {
    var names = { commit: ["commit", "commits"], verify: ["verify run", "verify runs"], review: ["review", "reviews"], gate: ["gate", "gates"],
      worklog: ["worklog entry", "worklog entries"], record: ["record", "records"] };
    return Object.keys(r.kinds).map(function (k) { var n = r.kinds[k]; return n + " " + (names[k] ? names[k][n === 1 ? 0 : 1] : k); }).join(" · ");
  }

  function pickDefaultThreadId() {
    var order = M.order || [];
    var now = order.filter(function (id) { return ITEMS[id] && ITEMS[id].column === "Now"; });
    if (now.length) return now[0];
    var wait = order.filter(function (id) { return ITEMS[id] && (ITEMS[id].column === "Blocked" || ITEMS[id].column === "Parked"); });
    if (wait.length) return wait[0];
    var next = order.filter(function (id) { return ITEMS[id] && ITEMS[id].column === "Next"; });
    if (next.length) return next[0];
    var done = order.filter(function (id) { return ITEMS[id] && ITEMS[id].column === "Done"; });
    if (done.length) return done[0];
    return order[0] || "";
  }

  // What closes each lifecycle gap, so a missing step always comes with its way out.
  var STEP_FIX = {
    "Plan": "Write docs/project/plans/<ID>.md (or the epic file) from templates/plan.md, or record why the item needed none",
    "Design review": "Write docs/project/reviews/<ID>-design.md, or fill the epic file's Design review section",
    "Build": "No commit names the item: add its ID to the commit's Work-Item trailer, or set the row to Dropped if nothing was built",
    "Verify": "Run sdlc.py verify on the item's commits; for past work that cannot be re-run, write 'Not run: <reason>' under Verified in its worklog entry",
    "Ship review": "Write docs/project/reviews/<ID>-ship.md, or record in the worklog why it was not reviewed",
    "Log": "sdlc.py log --id <ID> --write drafts the entry from the commits; add Why and Not done"
  };

  function diagnoseNextAction(it) {
    var kit = M.kit || {}, c = kit.constraints || {};
    var revCli = THREAD_STATE.reviewer || c.preferred_reviewer || "codex";
    if (!it) {
      return {
        label: "No work item selected — run project verification or doctor audit, or frame your first item",
        cmd: "python3 .ai-sdlc/bin/sdlc.py verify --parallel",
        desc: "Runs all configured charter check stages in parallel and saves evidence to .ai-sdlc/evidence/",
        runPayload: { subcommand: "verify", parallel: true },
        kind: "info"
      };
    }
    var id = it.id, steps = it.steps || {}, tier = it.tier || "2", col = it.column || "";
    var roleName = THREAD_STATE.role || it.owner || "qa";
    // A blocked item's next step is whatever unblocks it; no command run here can.
    if (col === "Parked" || col === "Blocked") {
      var x = it.extra || {};
      var who = x["Waiting on whom"] || x["Who can unblock"] || x["Unblocked by"] || "";
      var openDeps = (it.depends || []).filter(function (d) { return !ITEMS[d] || ITEMS[d].column !== "Done"; });
      var decision = x["Decision needed"] || x["Blocked on"] || "";
      return {
        label: who ? "Ask " + who + (decision ? " to decide: " + decision : " to unblock " + id)
          : (openDeps.length ? "Finish " + openDeps.join(", ") + " first — " + id + " depends on " + (openDeps.length === 1 ? "it" : "them")
          : "Name who unblocks " + id + " (the Waiting on whom cell in backlog.md)"),
        cmd: who || openDeps.length ? "python3 .ai-sdlc/bin/sdlc.py doctor" : "# edit docs/project/backlog.md: fill \"Waiting on whom\" for " + id,
        desc: who ? "Re-check once they answer; doctor flags gates left open" : (openDeps.length ? "Open the dependency's thread to see what it needs" : "Until someone is named, nobody is on the hook for it"),
        why: id + " is " + col + (who ? ", waiting on " + who : (openDeps.length ? ", depends on unfinished " + openDeps.join(", ") : ", and nobody is named to unblock it")),
        runPayload: who || openDeps.length ? { subcommand: "doctor" } : null,
        kind: "warn"
      };
    }
    if (tier === "1" && steps["Plan"] === "missing") {
      return {
        label: "Tier 1 requires a plan file (docs/project/plans/" + id + ".md) before building",
        why: "Tier 1 and no plan record yet",
        cmd: "/sdlc-plan " + id,
        desc: "Run in your coding agent to frame and write docs/project/plans/" + id + ".md",
        runPayload: null,
        kind: "warn"
      };
    }
    if (tier === "1" && steps["Design review"] === "missing") {
      return {
        label: "Tier 1 requires a Design Review before building (" + revCli + " · " + roleName + ")",
        why: "Tier 1 and no design review record yet",
        cmd: "python3 .ai-sdlc/bin/sdlc.py review " + id + " --role " + roleName + " --by " + revCli + " --stage design",
        desc: "Invokes " + revCli + " CLI as " + roleName + " to write a design review record for " + id,
        runPayload: null,
        usesReviewer: true,
        kind: "warn"
      };
    }
    if (steps["Build"] !== "done" && !(it.commits && it.commits.length)) {
      return {
        label: "Ready to build — generate Work-Item & Agent commit trailers for " + id,
        why: "No commit names " + id + " yet",
        cmd: "python3 .ai-sdlc/bin/sdlc.py trailers " + id + " --agent " + revCli,
        desc: "Outputs standardized git commit trailers (Work-Item, Agent) to attach when committing " + id,
        runPayload: { subcommand: "trailers", item_id: id, agent: revCli },
        usesReviewer: true,
        kind: "info"
      };
    }
    if (steps["Verify"] !== "done") {
      return {
        label: "Run verification suite to record evidence in the ledger for " + id,
        why: "Commits exist but no verify run is recorded on them",
        cmd: "python3 .ai-sdlc/bin/sdlc.py verify --parallel",
        desc: "Executes charter check stages in parallel and records evidence in .ai-sdlc/evidence/",
        runPayload: { subcommand: "verify", parallel: true },
        kind: "info"
      };
    }
    var indPolicy = c.independent_review || "none";
    var needInd = indPolicy !== "none" && (tier === "1" || (tier === "2" && indPolicy === "Tier 1 and 2"));
    var hasInd = (it.reviews || []).some(function (r) { return r.independent; });
    if (needInd && !hasInd) {
      return {
        label: "Tier " + tier + " requires an independent cross-model review (" + revCli + " · " + roleName + ")",
        why: "The charter asks for independent review at Tier " + tier + " and none is recorded",
        cmd: "python3 .ai-sdlc/bin/sdlc.py review " + id + " --role " + roleName + " --by " + revCli,
        desc: "Dispatches " + id + " diff and charter rules to " + revCli + " for independent ship review",
        runPayload: null,
        usesReviewer: true,
        kind: "warn"
      };
    }
    if (steps["Log"] === "missing" || !(it.worklog && it.worklog.length)) {
      return {
        label: "Draft the worklog line for " + id + " from its commits & verify runs",
        why: "Its tier needs a worklog entry and none names " + id,
        cmd: "python3 .ai-sdlc/bin/sdlc.py log --id " + id + " --write",
        desc: "Writes a compact worklog line for " + id + " from its git commits and verification evidence; add Why and Not done by hand",
        runPayload: { subcommand: "log", item_id: id, write: true },
        kind: "ok"
      };
    }
    // The worklog's own "Not done" section outranks any green check.
    var latestWl = (it.worklog || []).map(function (n) { return WL[n]; }).filter(Boolean)
      .sort(function (a, b) { return (b.date || "").localeCompare(a.date || ""); })[0];
    var notDone = latestWl && latestWl.sections ? (latestWl.sections["Not done"] || latestWl.sections["Not Done"] || "").trim() : "";
    if (col !== "Done" && notDone && !/^(-|none|n\/a|nothing)\.?$/i.test(notDone)) {
      var firstLine = notDone.split("\n").map(function (l) { return l.replace(/^[-*\s]+/, "").replace(/[*`_]+/g, ""); }).filter(Boolean)[0] || notDone;
      firstLine = firstSentence(firstLine);
      return {
        label: "Finish what the worklog left open: " + clip(firstLine, 110),
        cmd: "/sdlc-build " + id,
        desc: "Resume " + id + " in your coding agent; the worklog's Not done section is the list",
        why: "The latest worklog entry (" + (latestWl.date || "undated") + ") says Not done",
        runPayload: null,
        kind: "warn"
      };
    }
    var gaps = Object.keys(steps).filter(function (k) { return steps[k] === "missing"; });
    if (gaps.length) {
      return {
        label: plural(gaps.length, "lifecycle step") + " missing (" + gaps.join(", ") + ") — record " + (gaps.length === 1 ? "it" : "them") + " before closing " + id,
        why: "Its tier and status call for records that do not exist",
        cmd: "/sdlc-log " + id,
        desc: STEP_FIX[gaps[0]] || "Write the missing record, or say in the worklog why the step was not run",
        runPayload: null,
        kind: "warn"
      };
    }
    return {
      label: col === "Done" ? "Completed & verified — run strict doctor audit" : "Ready to close in backlog.md — run strict doctor check",
      why: "Every expected record exists and the worklog leaves nothing open",
      cmd: "python3 .ai-sdlc/bin/sdlc.py doctor --strict",
      desc: "Runs mechanical doctor checks across charter, backlog, worklog, and evidence records",
      runPayload: { subcommand: "doctor", strict: true },
      kind: "ok"
    };
  }

  function buildCommandSpecs(activeItem) {
    var kit = M.kit || {}, c = kit.constraints || {};
    var activeId = activeItem ? activeItem.id : "";
    var chosenReviewer = THREAD_STATE.reviewer || c.preferred_reviewer || "codex";
    var roleList = ((kit.installed && kit.installed.roles) || []).filter(function (r) { return r.active; }).map(function (r) { return r.name; });
    if (!roleList.length) roleList = ["qa", "security", "architect", "software-engineer"];
    var curRole = THREAD_STATE.role || (activeItem && activeItem.owner) || roleList[0];
    var curStage = THREAD_STATE.reviewStage || "ship";
    var nextDiag = diagnoseNextAction(activeItem);

    var specs = [
      {
        key: "next",
        tabLabel: "★ Recommended Next",
        title: "Recommended Next Step",
        cmd: nextDiag.cmd,
        desc: nextDiag.label + " — " + (nextDiag.desc || ""),
        runPayload: nextDiag.runPayload,
        usesReviewer: !!nextDiag.usesReviewer
      },
      {
        key: "verify",
        tabLabel: "Verify Suite",
        title: "Run Verification Suite",
        cmd: "python3 .ai-sdlc/bin/sdlc.py verify --parallel",
        desc: "Runs all configured charter check commands in parallel and writes signed logs to .ai-sdlc/evidence/",
        runPayload: { subcommand: "verify", parallel: true }
      }
    ];
    if (activeId) {
      specs.push({
        key: "plan_check",
        tabLabel: "Plan-Check",
        title: "Plan vs Diff Conformance (" + activeId + ")",
        cmd: "python3 .ai-sdlc/bin/sdlc.py plan-check " + activeId,
        desc: "Compares touched files in git against docs/project/plans/" + activeId + ".md",
        runPayload: { subcommand: "plan-check", item_id: activeId }
      });
      specs.push({
        key: "review",
        tabLabel: "2nd-Agent Review",
        title: "Cross-Harness Review (" + chosenReviewer + " · " + curRole + ")",
        cmd: "python3 .ai-sdlc/bin/sdlc.py review " + activeId + " --role " + curRole + " --by " + chosenReviewer + (curStage === "design" ? " --stage design" : ""),
        desc: "Invokes external `" + chosenReviewer + "` CLI as `" + curRole + "` (" + curStage + " stage) and writes docs/project/reviews/" + activeId + "-" + curStage + ".md",
        runPayload: null,
        usesReviewer: true
      });
      specs.push({
        key: "trailers",
        tabLabel: "Commit Trailers",
        title: "Git Commit Trailers (" + activeId + ")",
        cmd: "python3 .ai-sdlc/bin/sdlc.py trailers " + activeId + " --agent " + chosenReviewer,
        desc: "Prints Work-Item and Agent git trailers for " + activeId + " (using agent `" + chosenReviewer + "`)",
        runPayload: { subcommand: "trailers", item_id: activeId, agent: chosenReviewer },
        usesReviewer: true
      });
    }
    specs.push({
      key: "worklog",
      tabLabel: "Draft Worklog",
      title: "Draft Compact Worklog Entry",
      cmd: "python3 .ai-sdlc/bin/sdlc.py log --since main" + (activeId ? " --id " + activeId : "") + " --write",
      desc: "Appends a 1-line verified worklog entry to docs/project/worklog.md from git commits & evidence",
      runPayload: { subcommand: "log", since: "main", item_id: activeId || "", write: true }
    });
    specs.push({
      key: "doctor",
      tabLabel: "Doctor Audit",
      title: "Mechanical Doctor Check",
      cmd: "python3 .ai-sdlc/bin/sdlc.py doctor --strict",
      desc: "Audits charter, backlog, worklog, contract pointers, and secrets across all project records",
      runPayload: { subcommand: "doctor", strict: true }
    });
    return { specs: specs, nextDiag: nextDiag, chosenReviewer: chosenReviewer, curRole: curRole, curStage: curStage, roleList: roleList };
  }

  function renderCommandDock(activeItem) {
    var activeId = activeItem ? activeItem.id : "";
    var data = buildCommandSpecs(activeItem);
    var specs = data.specs;
    var nextDiag = data.nextDiag;
    var chosenReviewer = data.chosenReviewer;
    var curRole = data.curRole;
    var curStage = data.curStage;
    var roleList = data.roleList;
    if (roleList.indexOf(curRole) < 0) roleList.unshift(curRole);

    var activeSpec = specs.filter(function (s) { return s.key === THREAD_STATE.cmdTab; })[0] || specs[0];
    THREAD_STATE.cmdTab = activeSpec.key;

    var composer = el("div", { cls: "thread-composer" });

    // Row 1: Next Action Diagnosis + Execution Mode Explanation
    var statusStampCls = nextDiag.kind === "ok" ? "ok" : (nextDiag.kind === "warn" ? "warn" : "");
    composer.appendChild(el("div", { cls: "composer-top" }, [
      el("div", { style: "display: flex; align-items: center; gap: 8px; flex-wrap: wrap;" }, [
        el("span", { cls: "stamp " + statusStampCls, text: "Next" }),
        el("strong", { text: nextDiag.label }),
        nextDiag.why ? el("span", { cls: "muted", style: "font-size: 12px;", text: "· why: " + nextDiag.why }) : null
      ]),
      el("span", { cls: "muted", style: "font-size: 12px;", text: LIVE ? "r runs it" : "Static page: commands copy to the clipboard" })
    ]));

    // Row 2: Action Preset Tabs + Reviewer/Role/Stage Controls
    var tabsWrap = el("div", { cls: "composer-tabs", role: "tablist", "aria-label": "Command presets" });
    // The recommended command leads; the others wait in one menu.
    var shownSpecs = specs.filter(function (sp) { return sp.key === "next" || sp.key === activeSpec.key; });
    var otherSpecs = specs.filter(function (sp) { return shownSpecs.indexOf(sp) < 0; });
    shownSpecs.forEach(function (sp) {
      var isSel = sp.key === activeSpec.key;
      tabsWrap.appendChild(el("button", {
        cls: "composer-tab" + (isSel ? " active" : ""),
        role: "tab",
        "aria-selected": isSel ? "true" : "false",
        text: sp.tabLabel,
        on: { click: function () {
          THREAD_STATE.cmdTab = sp.key;
          viewThreads(activeId);
        } }
      }));
    });

    if (otherSpecs.length) {
      var moreSel = el("select", { cls: "filter-select", "aria-label": "More commands", style: "padding: 3px 7px; font-size: 12px;",
        on: { change: function () { if (moreSel.value) { THREAD_STATE.cmdTab = moreSel.value; viewThreads(activeId); } } } },
        [el("option", { value: "", text: "More commands…" })].concat(otherSpecs.map(function (sp) { return el("option", { value: sp.key, text: sp.tabLabel.replace(/^[^A-Za-z]+/, "") }); })));
      tabsWrap.appendChild(moreSel);
    }

    var paramsWrap = el("div", { cls: "composer-params" });
    var needsParams = !!(activeSpec.usesReviewer || activeSpec.key === "review");

    // Reviewer segmented buttons (changing immediately updates command box & switches to review if needed)
    var revGroup = el("div", { cls: "context-ctrl", role: "group", "aria-label": "Reviewer CLI" }, [
      el("span", { cls: "context-ctrl-lbl", text: "Agent/Reviewer" })
    ]);
    ["codex", "claude", "gemini"].forEach(function (hName) {
      var isAct = chosenReviewer === hName;
      revGroup.appendChild(el("button", {
        cls: "seg-btn" + (isAct ? " active" : ""),
        "aria-pressed": isAct ? "true" : "false",
        style: "padding: 2px 7px; font-size: 11px;",
        text: hName,
        title: "Use `" + hName + "` in Review & Trailers commands",
        on: { click: function () {
          THREAD_STATE.reviewer = hName;
          if (!activeSpec.usesReviewer && activeId) {
            THREAD_STATE.cmdTab = "review";
          }
          viewThreads(activeId);
        } }
      }));
    });
    paramsWrap.appendChild(revGroup);

    if (activeId) {
      var roleSelect = el("select", {
        cls: "filter-select",
        "aria-label": "Review role",
        style: "padding: 3px 7px; font-size: 11.5px;",
        on: { change: function () {
          THREAD_STATE.role = roleSelect.value;
          if (THREAD_STATE.cmdTab !== "review" && !(THREAD_STATE.cmdTab === "next" && nextDiag.usesReviewer)) {
            THREAD_STATE.cmdTab = "review";
          }
          viewThreads(activeId);
        } }
      }, roleList.map(function (rName) {
        var opt = el("option", { value: rName, text: "Role: " + rName });
        if (curRole === rName) opt.selected = true;
        return opt;
      }));
      paramsWrap.appendChild(roleSelect);

      var stageGroup = el("div", { cls: "context-ctrl", role: "group", "aria-label": "Review stage" }, [
        el("span", { cls: "context-ctrl-lbl", text: "Stage" })
      ]);
      [["ship", "Ship"], ["design", "Design"]].forEach(function (stOpt) {
        var isSt = curStage === stOpt[0];
        stageGroup.appendChild(el("button", {
          cls: "seg-btn" + (isSt ? " active" : ""),
          "aria-pressed": isSt ? "true" : "false",
          style: "padding: 2px 6px; font-size: 11px;",
          text: stOpt[1],
          on: { click: function () {
            THREAD_STATE.reviewStage = stOpt[0];
            THREAD_STATE.cmdTab = "review";
            viewThreads(activeId);
          } }
        }));
      });
      paramsWrap.appendChild(stageGroup);
    }

    composer.appendChild(el("div", { style: "display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;" }, [
      tabsWrap,
      needsParams ? paramsWrap : null
    ]));

    // Row 3: Live Monospace Command Preview Box + Explicit Run / Copy Buttons
    var actionBtns = [];
    if (LIVE && M.action_token && activeSpec.runPayload) {
      actionBtns.push(el("button", {
        cls: "cmd-btn run-btn",
        disabled: TERMINAL_STATE.running ? "disabled" : null,
        text: TERMINAL_STATE.running ? "⏳ Running…" : "▶ Run in Project",
        title: "Execute `" + activeSpec.cmd + "` directly on local server and view output below",
        on: { click: function () {
          runKitCmd(activeSpec.runPayload, activeSpec.cmd, activeSpec.title);
        } }
      }));
    }
    actionBtns.push(el("button", {
      cls: "cmd-btn " + (LIVE && M.action_token && activeSpec.runPayload ? "" : "primary"),
      text: "⧉ Copy CLI Command",
      title: "Copy `" + activeSpec.cmd + "` to clipboard",
      on: { click: function (e) {
        copyText(activeSpec.cmd);
        var btn = e.currentTarget || e.target;
        btn.textContent = "✓ Copied to Clipboard!";
        setTimeout(function () { btn.textContent = "⧉ Copy CLI Command"; }, 1800);
        showToast("Copied CLI Command", activeSpec.desc, activeSpec.cmd);
      } }
    }));

    composer.appendChild(el("div", { cls: "composer-cmd-box" }, [
      el("div", { style: "flex: 1; min-width: 240px; display: flex; flex-direction: column; gap: 3px;" }, [
        el("div", { cls: "composer-cmd-code" }, [
          el("span", { cls: "prompt-sigil", text: "$" }),
          el("span", { text: activeSpec.cmd })
        ]),
        el("div", { cls: "muted", style: "font-size: 11px;", text: activeSpec.desc })
      ]),
      el("div", { style: "display: flex; align-items: center; gap: 6px; flex-wrap: wrap;" }, actionBtns)
    ]));

    // Row 4: Inline Terminal Output Console (when a command was executed in Live mode)
    if (TERMINAL_STATE.visible) {
      var exitOk = TERMINAL_STATE.exitCode === 0;
      var statusBadgeText = TERMINAL_STATE.running
        ? "RUNNING…"
        : ("EXIT " + TERMINAL_STATE.exitCode + (exitOk ? " · PASS" : " · FAIL") + (TERMINAL_STATE.seconds !== null ? " (" + TERMINAL_STATE.seconds + "s)" : ""));
      composer.appendChild(el("div", { cls: "composer-terminal" }, [
        el("div", { cls: "composer-terminal-hdr" }, [
          el("div", { style: "display: flex; align-items: center; gap: 8px;" }, [
            el("span", {
              cls: "stamp " + (TERMINAL_STATE.running ? "warn" : (exitOk ? "ok" : "bad")),
              text: statusBadgeText
            }),
            el("code", { text: TERMINAL_STATE.cmd })
          ]),
          el("button", {
            cls: "codeblock-copy",
            text: "Hide Output ✕",
            on: { click: function () {
              TERMINAL_STATE.visible = false;
              viewThreads(activeId);
            } }
          })
        ]),
        el("pre", { text: TERMINAL_STATE.output || "" })
      ]));
    }

    return composer;
  }

  function renderThreadBubble(it, ev) {
    var icon = "EVT", avatarBg = "var(--panel)";
    var hdrLeft = [], hdrRight = [], bodyNodes = [];

    if (ev.kind === "frame") {
      icon = "FRM";
      hdrLeft.push(el("strong", { text: "Framed Work Item" }));
      if (ev.tier) hdrLeft.push(el("span", { cls: "chip", text: "Tier " + ev.tier }));
      if (ev.owner) hdrLeft.push(el("span", { cls: "chip", text: "Role: " + ev.owner }));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
      bodyNodes.push(el("div", { style: "font-weight: 600; margin-bottom: 4px;", text: it.id + " — " + (ev.title || "(untitled)") }));
      if (ev.depends && ev.depends.length) {
        var depLine = el("div", { style: "font-size: 12px; margin-top: 4px;" }, [el("span", { cls: "muted", text: "Depends on: " })]);
        ev.depends.forEach(function (d, idx) {
          if (idx) depLine.appendChild(document.createTextNode(", "));
          depLine.appendChild(link(d, "threads/" + d, "chip"));
        });
        bodyNodes.push(depLine);
      }
      if (ev.dependents && ev.dependents.length) {
        var blkLine = el("div", { style: "font-size: 12px; margin-top: 4px;" }, [el("span", { cls: "muted", text: "Unblocks: " })]);
        ev.dependents.forEach(function (d, idx) {
          if (idx) blkLine.appendChild(document.createTextNode(", "));
          blkLine.appendChild(link(d, "threads/" + d, "chip"));
        });
        bodyNodes.push(blkLine);
      }
    } else if (ev.kind === "plan") {
      icon = "PLN";
      hdrLeft.push(el("strong", { text: "Implementation Plan" }));
      hdrLeft.push(link(ev.path, docRoute(ev.doc_index), "chip"));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
      if (it.plan_check) {
        var pc = it.plan_check;
        var hasDrift = (pc.unplanned && pc.unplanned.length) || (pc.untouched && pc.untouched.length);
        var pcBox = el("div", {
          style: "margin: 6px 0 8px; padding: 8px 10px; border-radius: 6px; font-size: 12px; border: 1px solid " +
                 (hasDrift ? "var(--warn)" : "var(--accent)") + "; background: var(--bg);"
        }, [
          el("div", { style: "font-weight: 600; display: flex; justify-content: space-between; align-items: center;" }, [
            el("span", { cls: "stamp " + (hasDrift ? "warn" : "ok"), text: hasDrift ? "DRIFT DETECTED" : "CONFORMANCE PASS" }),
            el("span", { cls: "muted", text: (pc.planned || []).length + " planned · " + (pc.changed || []).length + " changed" })
          ])
        ]);
        if (pc.unplanned && pc.unplanned.length) {
          pcBox.appendChild(el("div", { style: "margin-top: 4px; color: var(--bad);", text: "Unplanned files touched: " + pc.unplanned.join(", ") }));
        }
        if (pc.untouched && pc.untouched.length) {
          pcBox.appendChild(el("div", { style: "margin-top: 4px; color: var(--warn);", text: "Planned paths untouched: " + pc.untouched.join(", ") }));
        }
        bodyNodes.push(pcBox);
      }
      var planDoc = DOCS[ev.doc_index];
      if (planDoc) {
        var det = el("details", null, [
          el("summary", { style: "cursor: pointer; font-weight: 500; font-size: 12px; color: var(--link);", text: "Read plan (" + planDoc.title + ")" }),
          renderMd(planDoc.text, planDoc.path.split("/").slice(0, -1).join("/"))
        ]);
        bodyNodes.push(det);
      }
    } else if (ev.kind === "design_review" || ev.kind === "ship_review") {
      icon = ev.kind === "design_review" ? "DRV" : "SRV";
      var revDoc = DOCS[ev.doc_index];
      var matchRev = (it.reviews || []).filter(function (r) { return ev.path.indexOf(r.file) >= 0; })[0];
      hdrLeft.push(el("strong", { text: ev.kind === "design_review" ? "Design Review" : "Ship Review" }));
      hdrLeft.push(link(ev.path.split("/").pop(), docRoute(ev.doc_index), "chip"));
      if (matchRev) {
        hdrLeft.push(el("span", { cls: "chip", text: "Reviewer: " + matchRev.reviewer }));
        hdrLeft.push(el("span", {
          cls: "stamp " + (matchRev.independent ? "ok" : "warn"),
          text: matchRev.independent ? "INDEPENDENT" : "SELF-CHECK"
        }));
      }
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
      if (revDoc) {
        bodyNodes.push(el("details", { open: true }, [
          el("summary", { style: "cursor: pointer; font-weight: 500; font-size: 12px; color: var(--link);", text: "Review findings (" + revDoc.title + ")" }),
          renderMd(revDoc.text, revDoc.path.split("/").slice(0, -1).join("/"))
        ]));
      }
    } else if (ev.kind === "commit") {
      icon = "GIT";
      hdrLeft.push(el("code", { text: ev.sha }));
      if (ev.agent || ev.model) {
        hdrLeft.push(el("span", { cls: "chip", text: "agent: " + (ev.agent || "agent") + (ev.model ? " / " + ev.model : "") }));
      } else if (ev.author) {
        hdrLeft.push(el("span", { cls: "chip", text: ev.author }));
      }
      if (ev.tokens) hdrLeft.push(el("span", { cls: "chip", text: ev.tokens + " tok" }));
      if (ev.minutes) hdrLeft.push(el("span", { cls: "chip", text: ev.minutes + " min" }));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
      bodyNodes.push(el("div", null, [inline(ev.subject)]));
    } else if (ev.kind === "verify") {
      icon = "VFY";
      var allPass = (ev.stages || []).every(function (s) { return String(s.result || "").indexOf("Verified: fail") < 0; });
      if (!allPass) icon = "ERR";
      hdrLeft.push(el("strong", { text: allPass ? "Verification Suite Passed" : "Verification Failure Recorded" }));
      if (ev.commit) hdrLeft.push(el("code", { text: "@" + ev.commit }));
      if (ev.dirty) hdrLeft.push(el("span", { cls: "stamp warn", text: "DIRTY TREE" }));
      if (ev.time) hdrRight.push(el("span", { cls: "muted", text: ev.time.replace("T", " ").replace("Z", "") }));
      var stageWrap = el("div", { style: "display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;" });
      var idleStages = (ev.stages || []).filter(function (s) { return !/^Verified/.test(s.result || ""); });
      (ev.stages || []).filter(function (s) { return /^Verified/.test(s.result || ""); }).forEach(function (s) {
        var ok = String(s.result || "").indexOf("Verified: pass") === 0;
        var fail = String(s.result || "").indexOf("Verified: fail") === 0;
        stageWrap.appendChild(el("span", {
          cls: "stamp" + (ok ? " ok" : (fail ? " bad" : "")),
          text: s.stage + (ok ? " pass" : (fail ? " fail" : ": " + s.result))
        }));
      });
      if (idleStages.length) stageWrap.appendChild(el("span", { cls: "muted", style: "font-size: 12px;", title: idleStages.map(function (s) { return s.stage; }).join(", "),
        text: "+ " + plural(idleStages.length, "stage") + " not run" }));
      bodyNodes.push(stageWrap);
    } else if (ev.kind === "spec_change") {
      icon = "SPC";
      hdrLeft.push(el("strong", { text: ev.applied ? "Spec change applied" : "Spec change (pending)" }));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
      bodyNodes.push(el("div", { style: "display: flex; gap: 6px; flex-wrap: wrap; align-items: center;" }, Object.keys(ev.counts || {}).map(function (k) {
        return el("span", { cls: "stamp " + (k === "REMOVED" ? "neutral" : "ok"), text: ev.counts[k] + " " + k.toLowerCase() });
      }).concat([link(ev.path.split("/").pop(), docRoute(DOC_BY_PATH[ev.path])), link("Specs →", "docs/specs", "")])));
    } else if (ev.kind === "gate") {
      icon = "GTE";
      hdrLeft.push(el("strong", { style: "color: var(--bad);", text: ev.column + " — Human Gate / Decision Required" }));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: "Since " + ev.date }));
      if (ev.waiting_on) bodyNodes.push(el("div", null, [el("strong", { text: "Waiting on: " }), document.createTextNode(ev.waiting_on)]));
      if (ev.decision) bodyNodes.push(el("div", { style: "margin-top: 4px;" }, [el("strong", { text: "Decision / Unblock needed: " }), inline(ev.decision)]));
    } else if (ev.kind === "worklog") {
      icon = "LOG";
      hdrLeft.push(el("strong", { text: "Worklog Entry" }));
      if (ev.compact) hdrLeft.push(el("span", { cls: "chip", text: "compact log" }));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
      bodyNodes.push(entryBox(ev.worklog_index, false));
    } else {
      icon = "DOC";
      hdrLeft.push(el("strong", { text: ev.title || ev.kind }));
      if (ev.path) hdrLeft.push(link(ev.path, docRoute(ev.doc_index), "chip"));
      if (ev.date) hdrRight.push(el("span", { cls: "muted", text: ev.date }));
    }

    return el("div", { cls: "msg-bubble" }, [
      el("div", { cls: "msg-avatar", style: "background: " + avatarBg, text: icon }),
      el("div", { cls: "msg-card kind-" + ev.kind }, [
        el("div", { cls: "msg-hdr" }, [
          el("div", { cls: "msg-hdr-left" }, hdrLeft),
          el("div", null, hdrRight)
        ]),
        el("div", { cls: "msg-body" }, bodyNodes)
      ])
    ]);
  }

  function itemMatchesThreadFilter(it) {
    if (!it) return false;
    if (THREAD_STATE.filter === "active" && it.column !== "Now") return false;
    if (THREAD_STATE.filter === "human" && ["Blocked", "Parked"].indexOf(it.column) < 0) return false;
    if (THREAD_STATE.filter === "done" && it.column !== "Done") return false;
    if (THREAD_STATE.filter === "gaps" && !Object.keys(it.steps || {}).some(function (k) { return it.steps[k] === "missing"; })) return false;
    var q = (THREAD_STATE.query || "").trim().toLowerCase();
    if (q) {
      var hay = ((it.id || "") + " " + (it.title || "") + " " + (it.owner || "") + " " + (it.author || "")).toLowerCase();
      if (hay.indexOf(q) < 0) return false;
    }
    return true;
  }

  function viewThreads(selectedId) {
    main.textContent = "";
    tab("threads");
    if (selectedId && ITEMS[selectedId]) {
      THREAD_STATE.selected = selectedId;
    } else if (!THREAD_STATE.selected || !ITEMS[THREAD_STATE.selected] || !itemMatchesThreadFilter(ITEMS[THREAD_STATE.selected])) {
      var matchingIds = (M.order || []).filter(function (id) { return itemMatchesThreadFilter(ITEMS[id]); });
      THREAD_STATE.selected = THREAD_STATE.filter === "all" ? pickDefaultThreadId() : (matchingIds[0] || "");
    }
    var activeId = THREAD_STATE.selected;
    var activeItem = activeId ? ITEMS[activeId] : null;
    if (activeId && isUnread(activeId)) { markSeen(activeId); paintMeta(); }

    crumbs([[M.project || "Project", "threads"], ["Inbox", "threads"], activeId ? [activeId] : null].filter(Boolean));

    var kit = M.kit || {};
    main.appendChild(el("div", { cls: "view-header" }, [
      el("div", null, [
        h(1, "Inbox"),
        el("p", { cls: "view-subtitle", text: "Work item threads and the project-wide activity feed. Pick a thread to read its lifecycle stream and run its next command." })
      ]),
      el("div", { style: "display: flex; gap: 6px; align-items: center;" }, [
        el("button", { cls: "cmd-btn", text: "Kanban Board ↗", on: { click: function () { go("board"); } } }),
        el("button", { cls: "cmd-btn", text: "Kit settings ↗", on: { click: function () { go("project/kit"); } } })
      ])
    ]));

    var layout = el("div", { cls: "threads-layout" });

    // Left Pane: Thread Inbox
    var inbox = el("div", { cls: "threads-inbox" });
    var searchIn = el("input", {
      type: "search",
      cls: "filter-input",
      placeholder: "Filter threads by ID, title, or agent…",
      "aria-label": "Filter threads",
      value: THREAD_STATE.query,
      on: { input: function () { THREAD_STATE.query = searchIn.value; renderInboxList(); } }
    });
    var filterBar = el("div", { style: "display: flex; gap: 4px; flex-wrap: wrap;" });
    [["all", "All"], ["active", "Now"], ["human", "Needs Human"], ["gaps", "Missing Steps"], ["done", "Done"]].forEach(function (f) {
      var isAct = THREAD_STATE.filter === f[0];
      filterBar.appendChild(el("button", {
        cls: "seg-btn" + (isAct ? " active" : ""),
        "aria-pressed": isAct ? "true" : "false",
        text: f[1],
        on: { click: function () {
          THREAD_STATE.filter = f[0];
          var matching = (M.order || []).filter(function (id) { return itemMatchesThreadFilter(ITEMS[id]); });
          var nextId = matching.length ? (matching.indexOf(activeId) >= 0 ? activeId : matching[0]) : "";
          THREAD_STATE.selected = nextId;
          viewThreads(nextId);
        } }
      }));
    });
    var modeBar = el("div", { style: "display: flex; gap: 4px; align-items: center; flex-wrap: wrap;" });
    [["items", "Threads"], ["feed", "Activity feed"]].forEach(function (m) {
      var on = THREAD_STATE.mode === m[0];
      modeBar.appendChild(el("button", { cls: "seg-btn" + (on ? " active" : ""), "aria-pressed": on ? "true" : "false", text: m[1],
        on: { click: function () { THREAD_STATE.mode = m[0]; viewThreads(activeId); } } }));
    });
    var unreadNow = unreadIds().length;
    modeBar.appendChild(el("span", { style: "flex: 1;" }));
    modeBar.appendChild(el("button", { cls: "seg-btn", disabled: unreadNow ? null : "disabled", title: "Mark every item's activity as read",
      text: unreadNow ? "Mark " + unreadNow + " read" : "All read", on: { click: function () { markAllSeen(); paintMeta(); viewThreads(activeId); } } }));
    var feedBar = null;
    if (THREAD_STATE.mode === "feed") {
      feedBar = el("div", { style: "display: flex; gap: 6px; align-items: center;" });
      var kindSel = el("select", { cls: "filter-select", "aria-label": "Show events of kind", style: "padding: 3px 7px; font-size: 12px;",
        on: { change: function () { THREAD_STATE.feedKind = kindSel.value; viewThreads(activeId); } } },
        FEED_KINDS.map(function (fk) { var o = el("option", { value: fk[0], text: fk[0] === "all" ? "All events" : fk[1] }); if (THREAD_STATE.feedKind === fk[0]) o.selected = true; return o; }));
      feedBar.appendChild(kindSel);
      feedBar.appendChild(el("button", { cls: "seg-btn" + (THREAD_STATE.feedUnread ? " active" : ""), "aria-pressed": THREAD_STATE.feedUnread ? "true" : "false",
        text: "Unread only", on: { click: function () { THREAD_STATE.feedUnread = !THREAD_STATE.feedUnread; viewThreads(activeId); } } }));
    }
    inbox.appendChild(el("div", { cls: "threads-inbox-top" }, [modeBar, searchIn, THREAD_STATE.mode === "feed" ? feedBar : filterBar]));

    var inboxList = el("div", { cls: "threads-inbox-list", role: "listbox", "aria-label": "Work item threads" });
    inbox.appendChild(inboxList);

    function renderFeedList() {
      inboxList.textContent = "";
      var rows = buildFeed(), lastDay = "";
      if (!rows.length) {
        inboxList.appendChild(el("p", { cls: "muted", style: "padding: 12px; text-align: center;", text: THREAD_STATE.feedUnread ? "No unread activity." : "No activity matches the current filter." }));
        return;
      }
      rows.slice(0, 300).forEach(function (r) {
        if (r.day !== lastDay) { inboxList.appendChild(el("div", { cls: "feed-day", text: r.day })); lastDay = r.day; }
        var it = ITEMS[r.id], unread = isUnread(r.id) && r.latest > (loadSeen()[r.id] || "");
        var open = function () { THREAD_STATE.selected = r.id; go("threads/" + encodeURIComponent(r.id)); };
        var row = el("div", { cls: "feed-row" + (unread ? " unread" : "") + (r.id === activeId ? " sel" : ""), "data-thread-id": r.id, role: "option",
          "aria-selected": r.id === activeId ? "true" : "false", on: { click: open } }, [
          el("span", { cls: "fr-dot" }),
          el("div", { style: "min-width: 0;" }, [
            el("div", { cls: "fr-title", style: "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" }, [
              el("strong", { text: r.id + " " }), document.createTextNode(clip(it.title || "", 60))
            ]),
            el("div", { cls: "fr-kinds", style: r.bad ? "color: var(--bad);" : "", text: (r.bad ? "✗ verify failing · " : (r.fixed ? "verify failed, fixed later · " : "")) + feedSummary(r) })
          ]),
          it.column && it.column !== "Other" ? colChip(it.column) : el("span")
        ]);
        makeInteractive(row, open, r.id + " activity on " + r.day);
        row.addEventListener("keydown", function (e) {
          var all = Array.prototype.slice.call(inboxList.querySelectorAll(".feed-row"));
          var i = all.indexOf(row), next = null;
          if ((e.key === "ArrowDown" || e.key === "j") && i + 1 < all.length) next = all[i + 1];
          else if ((e.key === "ArrowUp" || e.key === "k") && i > 0) next = all[i - 1];
          if (!next) return;
          e.preventDefault();
          var nid = next.getAttribute("data-thread-id");
          THREAD_STATE.selected = nid;
          var idx = all.indexOf(next);
          go("threads/" + encodeURIComponent(nid));
          setTimeout(function () { var t = inboxList.querySelectorAll(".feed-row")[idx]; if (t) t.focus(); }, 20);
        });
        inboxList.appendChild(row);
      });
    }

    function renderInboxList() {
      if (THREAD_STATE.mode === "feed") { renderFeedList(); return; }
      inboxList.textContent = "";
      var groups = [
        { title: "Needs you / Blocked", cols: ["Blocked", "Parked"] },
        { title: "Active / In Flight", cols: ["Now"] },
        { title: "Ready / Queue", cols: ["Next", "Later"] },
        { title: "Completed", cols: ["Done", "Other"] }
      ];
      var anyShown = false;
      groups.forEach(function (g) {
        var ids = (M.order || []).filter(function (id) {
          var it = ITEMS[id];
          if (!it || g.cols.indexOf(it.column) < 0) return false;
          return itemMatchesThreadFilter(it);
        });
        if (!ids.length) return;
        anyShown = true;
        inboxList.appendChild(el("div", { cls: "threads-group-hdr" }, [
          el("span", { text: g.title }),
          el("span", { cls: "chip", text: String(ids.length) })
        ]));
        ids.forEach(function (id) {
          var it = ITEMS[id];
          var pips = el("span", { cls: "mini-pips", role: "img" });
          var missingSteps = [];
          (M.steps || []).forEach(function (s) {
            var st = (it.steps || {})[s] || "n/a";
            if (st === "missing") missingSteps.push(s);
            pips.appendChild(el("span", { cls: "mini-pip " + (st === "n/a" ? "na" : st), title: s + ": " + st }));
          });
          pips.setAttribute("aria-label", missingSteps.length ? ("Missing steps: " + missingSteps.join(", ")) : "Lifecycle steps ok");

          var activateThread = function () {
            THREAD_STATE.selected = id;
            go("threads/" + encodeURIComponent(id));
          };
          var row = el("div", {
            cls: "thread-row" + (id === activeId ? " active" : ""),
            "data-thread-id": id,
            "aria-selected": id === activeId ? "true" : "false",
            on: { click: activateThread }
          }, [
            el("div", { cls: "thread-row-top" }, [
              el("div", { style: "display: flex; align-items: center; gap: 6px;" }, [
                isUnread(id) ? el("span", { cls: "unread-dot", title: "New activity since you last opened it" }) : null,
                el("strong", { style: "font-size: 12px;", text: id }),
                it.tier ? el("span", { cls: "chip", text: "T" + it.tier }) : null,
                missingSteps.length ? el("span", { cls: "stamp bad", title: "Missing: " + missingSteps.join(", "), text: "!" + missingSteps.length }) : null
              ]),
              colChip(it.column)
            ]),
            el("div", { cls: "thread-row-title", text: clip(it.title || "(untitled)", 68) }),
            el("div", { cls: "thread-row-meta" }, [
              el("span", { text: it.author ? "agent: " + it.author : (ownerOf(it) || "No owner") }),
              pips
            ])
          ]);
          makeInteractive(row, activateThread, id + " " + (it.title || ""));
          row.addEventListener("keydown", function (e) {
            var allRows = Array.prototype.slice.call(inboxList.querySelectorAll(".thread-row"));
            var idx = allRows.indexOf(row);
            if ((e.key === "ArrowDown" || e.key === "j") && idx >= 0 && idx + 1 < allRows.length) {
              e.preventDefault();
              var nextId = allRows[idx + 1].getAttribute("data-thread-id");
              if (nextId) {
                THREAD_STATE.selected = nextId;
                go("threads/" + encodeURIComponent(nextId));
                setTimeout(function () {
                  var targetEl = document.querySelector('.thread-row[data-thread-id="' + nextId + '"]');
                  if (targetEl) targetEl.focus();
                }, 20);
              }
            } else if ((e.key === "ArrowUp" || e.key === "k") && idx > 0) {
              e.preventDefault();
              var prevId = allRows[idx - 1].getAttribute("data-thread-id");
              if (prevId) {
                THREAD_STATE.selected = prevId;
                go("threads/" + encodeURIComponent(prevId));
                setTimeout(function () {
                  var targetEl = document.querySelector('.thread-row[data-thread-id="' + prevId + '"]');
                  if (targetEl) targetEl.focus();
                }, 20);
              }
            }
          });
          inboxList.appendChild(row);
        });
      });
      if (!anyShown) {
        inboxList.appendChild(el("p", { cls: "muted", style: "padding: 12px; text-align: center;", text: "No threads match the current filter." }));
      }
    }
    renderInboxList();
    layout.appendChild(inbox);

    // Right Pane: Chronological Action Stream + Command & Terminal Dock
    var stream = el("div", { cls: "threads-stream" });
    if (!activeItem) {
      var hasAnyItems = (M.order || []).length > 0;
      var emptyFeed = el("div", { cls: "thread-feed", style: "justify-content: center; align-items: center;" }, [
        el("div", { style: "padding: 28px; text-align: center; max-width: 520px;" }, [
          el("h2", { style: "font-size: 15px; color: var(--text);", text: hasAnyItems ? "No threads match this filter" : "No work item threads recorded yet" }),
          el("p", { cls: "muted", text: hasAnyItems
            ? "No work items currently match the '" + THREAD_STATE.filter + "' filter."
            : "Frame your first item with `/sdlc-intake` or add a row to `docs/project/backlog.md`. You can still run project-wide verification and doctor checks from the Command Dock below." }),
          hasAnyItems && THREAD_STATE.filter !== "all" ? el("button", {
            cls: "cmd-btn primary",
            style: "margin-top: 12px;",
            text: "Show All Threads",
            on: { click: function () {
              THREAD_STATE.filter = "all";
              THREAD_STATE.selected = pickDefaultThreadId();
              viewThreads(THREAD_STATE.selected);
            } }
          }) : null
        ])
      ]);
      stream.appendChild(emptyFeed);
      stream.appendChild(renderCommandDock(null));
      layout.appendChild(stream);
      main.appendChild(layout);
      return;
    }

    var stepsBar = el("div", { cls: "steps", style: "margin: 0;" });
    (M.steps || []).forEach(function (s) {
      var st = (activeItem.steps || {})[s] || "n/a";
      stepsBar.appendChild(el("span", { cls: "step " + (st === "n/a" ? "na" : st), text: s + (st === "missing" ? " !" : "") }));
    });

    var hdr = el("div", { cls: "thread-hdr" }, [
      el("div", { cls: "thread-hdr-top" }, [
        el("div", { style: "display: flex; align-items: center; gap: 8px; flex-wrap: wrap;" }, [
          el("strong", { style: "font-size: 16px;", text: activeId }),
          colChip(activeItem.column),
          activeItem.tier ? el("span", { cls: "chip", text: "Tier " + activeItem.tier }) : null,
          activeItem.owner ? el("span", { cls: "chip", text: "Owner: " + activeItem.owner }) : null,
          activeItem.author ? el("span", { cls: "chip", text: "agent: " + activeItem.author }) : null,
          claimOf(activeId) ? claimChip(claimOf(activeId), true) : null
        ]),
        el("div", { style: "display: flex; gap: 6px; flex-wrap: wrap;" }, [
          el("button", { cls: "cmd-btn", style: "padding: 3px 8px; font-size: 11px;", text: "Inspector", on: { click: function () { openItemDrawer(activeId); } } }),
          link("Full page ↗", "item/" + encodeURIComponent(activeId), "chip"),
          link("Focus on Board ↗", "board/focus/" + encodeURIComponent(activeId), "chip")
        ])
      ]),
      el("div", { style: "font-size: 15px; font-weight: 600;", text: activeItem.title || "(untitled)" }),
      stepsBar
    ]);
    stream.appendChild(hdr);

    var feed = el("div", { cls: "thread-feed" });
    var events = activeItem.thread || [];
    events.forEach(function (ev) {
      feed.appendChild(renderThreadBubble(activeItem, ev));
    });

    // If tests are locked in .ai-sdlc/test-lock.txt, surface an inline lock callout
    var lockedTests = (kit.installed && kit.installed.guards && kit.installed.guards.test_locks) || [];
    if (lockedTests.length) {
      feed.appendChild(el("div", { cls: "msg-bubble" }, [
        el("div", { cls: "msg-avatar", text: "LCK" }),
        el("div", { cls: "msg-card kind-gate" }, [
          el("div", { cls: "msg-hdr" }, [
            el("strong", { text: "Reproducing Test Lock Active (.ai-sdlc/test-lock.txt)" }),
            el("button", {
              cls: "cmd-btn",
              text: "Unlock Tests",
              on: { click: function () {
                kitApi("/api/fix", { action: "unlock-tests" }, "python3 .ai-sdlc/bin/sdlc.py fix unlock-tests", "Unlocked reproducing tests");
              } }
            })
          ]),
          el("div", { cls: "msg-body" }, [
            el("div", { text: "Locked test files (protected from agent edits while fixing the bug): " + lockedTests.join(", ") })
          ])
        ])
      ]));
    }
    stream.appendChild(feed);
    stream.appendChild(renderCommandDock(activeItem));
    layout.appendChild(stream);
    main.appendChild(layout);
  }


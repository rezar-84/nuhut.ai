  // ---------------------------------------------------------------- chrome
  var LIVE = /^https?:$/.test(location.protocol) && !!M.version, liveState = "live", liveAt = new Date();
  try {
    var savedTheme = localStorage.getItem("nuhut-theme");
    if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
  } catch (e) {}

  function toggleTheme() {
    var cur = document.documentElement.getAttribute("data-theme");
    var isDark = cur === "dark" || (!cur && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    var next = isDark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("nuhut-theme", next); } catch (e) {}
    paintMeta();
  }

  function copyText(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () { fallbackCopyText(text); });
    } else {
      fallbackCopyText(text);
    }
  }

  function fallbackCopyText(text) {
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (e) {}
  }

  function makeInteractive(node, onActivate, label) {
    if (!node) return node;
    if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "0");
    if (!node.hasAttribute("role")) node.setAttribute("role", "button");
    if (label) node.setAttribute("aria-label", label);
    node.addEventListener("keydown", function (e) {
      if (e.target !== node) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onActivate(e);
      }
    });
    return node;
  }

  var STAGED_KIT = { config: {}, fixes: [] };
  var TERMINAL_STATE = { running: false, cmd: "", output: "", exitCode: null, seconds: null, visible: false };

  function buildStagedKitCommand() {
    var cmds = [];
    var cfg = STAGED_KIT.config || {};
    var cfgArgs = [];
    if (cfg.token_saving !== undefined) cfgArgs.push("--token-saving " + (cfg.token_saving === true || cfg.token_saving === "on" ? "on" : "off"));
    if (cfg.effort) cfgArgs.push("--effort " + cfg.effort);
    if (cfg.independent_review) {
      var cliIr = cfg.independent_review === "none" ? "none" : (cfg.independent_review === "Tier 1 and 2" ? "tier1-2" : "tier1");
      cfgArgs.push("--independent-review " + cliIr);
    }
    if (cfg.preferred_reviewer) cfgArgs.push("--reviewer " + cfg.preferred_reviewer);
    if (cfg.decision_style) cfgArgs.push("--decision-style " + cfg.decision_style);
    if (cfg.tier_rules) cfgArgs.push("--tier-rules " + cfg.tier_rules);
    if (cfg.dev_method) cfgArgs.push("--dev-method " + cfg.dev_method);
    if (cfg.acquisition_profile) cfgArgs.push("--acquisition-profile " + cfg.acquisition_profile);
    if (cfg.checks) {
      Object.keys(cfg.checks).forEach(function (st) {
        var val = cfg.checks[st];
        cfgArgs.push("--set-check " + st + "=" + (/\s/.test(val) ? "\"" + val.replace(/"/g, "\\\"") + "\"" : val));
      });
    }
    if (cfgArgs.length) cmds.push("python3 .ai-sdlc/bin/sdlc.py config " + cfgArgs.join(" "));
    (STAGED_KIT.fixes || []).forEach(function (act) {
      cmds.push("python3 .ai-sdlc/bin/sdlc.py fix " + act);
    });
    return cmds.join(" && ");
  }

  // Toasts stack (newest at the bottom, three at most) so a run finishing does not wipe
  // the copy confirmation before it; every one is also in the bell.
  function showToast(title, detail, cmd) {
    var box = document.getElementById("toast-bar");
    if (!box) return;
    var card = el("div", { cls: "toast-item" });
    function dismiss() {
      if (card.parentNode) card.parentNode.removeChild(card);
      if (!box.children.length) box.className = "toast-bar";
    }
    card.appendChild(el("div", { style: "display: flex; align-items: center; justify-content: space-between; gap: 10px;" }, [
      el("strong", { text: title }),
      el("button", { text: "✕", "aria-label": "Dismiss notification", style: "border: none; background: transparent; cursor: pointer; color: var(--muted);", on: { click: dismiss } })
    ]));
    if (detail) card.appendChild(el("div", { cls: "muted", text: detail }));
    if (cmd) {
      card.appendChild(el("div", { style: "display: flex; align-items: center; gap: 8px; margin-top: 4px;" }, [
        el("code", { style: "flex: 1; padding: 4px 8px; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; overflow-x: auto;", text: cmd }),
        el("button", { cls: "cmd-btn", text: "Copy", on: { click: function (e) {
          copyText(cmd);
          e.target.textContent = "Copied!";
        } } })
      ]));
    }
    box.appendChild(card);
    while (box.children.length > 3) box.removeChild(box.firstChild);
    box.className = "toast-bar show";
    var timer = setTimeout(dismiss, cmd ? 8500 : 4500);
    card.addEventListener("mouseenter", function () { clearTimeout(timer); });
    card.addEventListener("mouseleave", function () { timer = setTimeout(dismiss, 2500); });
  }

  function copyCmd(cmd, label) {
    copyText(cmd);
    showToast("Copied command: " + (label || "CLI"), "Run this in your project terminal:", cmd);
  }

  function applyOptimisticKitChange(endpoint, payload) {
    M.kit = M.kit || {};
    var c = M.kit.constraints = M.kit.constraints || {};
    var rt = M.kit.reading_tokens = M.kit.reading_tokens || {};
    var inst = M.kit.installed = M.kit.installed || {};
    payload = payload || {};
    if (endpoint === "/api/config") {
      if (payload.token_saving !== undefined) {
        var on = payload.token_saving === "on" || payload.token_saving === true;
        M.kit.token_saving = on;
        if (on) {
          c.effort_mode = "Lean";
          c.independent_review = "none";
          c.tier_rules = "Standard";
          M.kit.profile = "compact";
          M.kit.reviewer_warning = "";
        } else {
          c.effort_mode = "Normal";
          M.kit.profile = M.kit.has_process_docs !== false ? "full" : "compact";
        }
      }
      if (payload.effort) {
        c.effort_mode = payload.effort;
        if (payload.effort !== "Lean") M.kit.token_saving = false;
        else if ((c.independent_review || "none") === "none") M.kit.token_saving = true;
      }
      if (payload.independent_review) {
        c.independent_review = payload.independent_review;
        if (payload.independent_review !== "none") M.kit.token_saving = false;
        else M.kit.reviewer_warning = "";
      }
      if (payload.preferred_reviewer) c.preferred_reviewer = payload.preferred_reviewer;
      if (payload.decision_style) c.decision_style = payload.decision_style;
      if (payload.tier_rules) c.tier_rules = payload.tier_rules;
      if (payload.dev_method) c.dev_method = payload.dev_method;
      if (payload.acquisition_profile) c.acquisition_profile = payload.acquisition_profile;
      if (payload.checks) {
        inst.commands = inst.commands || {};
        Object.keys(payload.checks).forEach(function (st) {
          inst.commands[st] = payload.checks[st];
          inst.blank_stages = (inst.blank_stages || []).filter(function (b) { return b !== st; });
        });
      }
      var baseT1 = rt.baseline_tier1_tokens || 12000;
      var t3 = rt.tier3_tokens || 2200;
      var eff = c.effort_mode || "Normal";
      var ind = c.independent_review || "none";
      var estT1 = (eff === "Lean" || M.kit.token_saving) ? (t3 + 1200) : (eff === "Beast" ? baseT1 : Math.round(baseT1 * 0.72));
      if (ind !== "none") estT1 += 2400;
      rt.tier1_tokens = estT1;
      rt.tier1_words = Math.round(estT1 / 1.3);
      rt.saved_pct = Math.max(0, Math.round((1 - (estT1 / Math.max(1, baseT1))) * 100));
    } else if (endpoint === "/api/fix") {
      var act = payload.action || "all";
      M.kit.fixable = (M.kit.fixable || []).filter(function (f) { return act !== "all" && f.id !== act; });
      if ((act === "all" || act === "unlock-tests") && inst.guards) inst.guards.test_locks = [];
      if ((act === "all" || act === "wire-pointer") && inst.harnesses) {
        inst.harnesses.forEach(function (h) { h.wired = true; });
      }
    }
    paintMeta();
    render();
  }

  function recordStagedChange(endpoint, payload) {
    payload = payload || {};
    if (endpoint === "/api/config") {
      Object.keys(payload).forEach(function (k) {
        if (k === "checks") {
          STAGED_KIT.config.checks = STAGED_KIT.config.checks || {};
          Object.keys(payload.checks).forEach(function (st) { STAGED_KIT.config.checks[st] = payload.checks[st]; });
        } else {
          STAGED_KIT.config[k] = payload[k];
        }
      });
    } else if (endpoint === "/api/fix") {
      var act = payload.action || "all";
      if (act === "all") STAGED_KIT.fixes = ["all"];
      else if (STAGED_KIT.fixes.indexOf("all") < 0 && STAGED_KIT.fixes.indexOf(act) < 0) STAGED_KIT.fixes.push(act);
    }
  }

  function kitApi(endpoint, payload, fallbackCmd, desc) {
    var prevKit = JSON.parse(JSON.stringify(M.kit || {}));
    // Always update the UI immediately so toggles feel responsive in both Live and Static modes
    applyOptimisticKitChange(endpoint, payload);
    if (LIVE && M.action_token) {
      fetch(endpoint.replace(/^\//, ""), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Action-Token": M.action_token
        },
        body: JSON.stringify(payload || {})
      }).then(function (r) {
        return r.text().then(function (txt) {
          var parsed = null;
          try { parsed = JSON.parse(txt); } catch (e) {}
          return { status: r.status, ok: r.ok, body: parsed };
        });
      }).then(function (resp) {
        var res = resp.body;
        if (!res || !res.ok) {
          if (resp.status === 404) {
            recordStagedChange(endpoint, payload);
            var combined404 = buildStagedKitCommand() || fallbackCmd;
            copyText(combined404);
            paintMeta();
            render();
            showToast("Preview Applied · Server Restart Needed", "Running `view --serve` is an older process. Command copied to clipboard:", combined404);
            return;
          }
          M.kit = prevKit;
          paintMeta();
          render();
          copyText(fallbackCmd);
          var errMsg = (res && res.error) || ("Could not apply change on server (HTTP " + resp.status + ") — reverted UI and copied CLI command");
          showToast("Server Error · Reverted & Copied CLI Command", errMsg, fallbackCmd);
          return;
        }
        if (res.kit) M.kit = res.kit;
        if (res.alerts) M.alerts = res.alerts;
        if (res.version) M.version = res.version;
        INITIAL_KIT = JSON.parse(JSON.stringify(M.kit || {}));
        liveAt = new Date();
        paintMeta();
        render();
        var msg = (res.applied && res.applied.join(", ")) || (res.repaired && res.repaired.join(", ")) || desc || "Applied";
        showToast("✓ Saved to Kit (charter.md & profile.json)", msg);
      }).catch(function () {
        recordStagedChange(endpoint, payload);
        var combinedErr = buildStagedKitCommand() || fallbackCmd;
        copyText(combinedErr);
        paintMeta();
        render();
        showToast("Preview Applied · Server Unreachable", "Copied CLI command to persist change in terminal:", combinedErr);
      });
    } else {
      recordStagedChange(endpoint, payload);
      var combined = buildStagedKitCommand() || fallbackCmd;
      copyText(combined);
      paintMeta();
      render();
      showToast(
        "✓ Toggle Preview Applied · CLI Command Copied",
        "Static HTML cannot write files directly. Paste & run in terminal to persist (or run `sdlc.py view --serve`):",
        combined
      );
    }
  }

  function runKitCmd(runPayload, fallbackCmd, desc) {
    if (LIVE && M.action_token && runPayload && runPayload.subcommand) {
      TERMINAL_STATE.running = true;
      TERMINAL_STATE.cmd = fallbackCmd;
      TERMINAL_STATE.output = "Running `" + fallbackCmd + "` in project root…";
      TERMINAL_STATE.exitCode = null;
      TERMINAL_STATE.seconds = null;
      TERMINAL_STATE.visible = true;
      render();
      paintActivityBar();
      fetch("api/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Action-Token": M.action_token
        },
        body: JSON.stringify(runPayload)
      }).then(function (r) {
        return r.text().then(function (txt) {
          var parsed = null;
          try { parsed = JSON.parse(txt); } catch (e) {}
          return { status: r.status, ok: r.ok, body: parsed };
        });
      }).then(function (resp) {
        TERMINAL_STATE.running = false;
        var res = resp.body;
        if (!res || !res.ok) {
          TERMINAL_STATE.exitCode = resp.status || 1;
          TERMINAL_STATE.output = (res && res.error) || ("Server does not support /api/run (HTTP " + resp.status + "). Restart `sdlc.py view --serve` or run in terminal:\n$ " + fallbackCmd);
          copyText(fallbackCmd);
          render();
          return;
        }
        TERMINAL_STATE.cmd = res.command || fallbackCmd;
        TERMINAL_STATE.output = res.output || "(completed with no output)";
        TERMINAL_STATE.exitCode = res.exit_code;
        TERMINAL_STATE.seconds = res.seconds;
        LAST_RUN = { label: runPayload.subcommand, exit_code: res.exit_code, seconds: res.seconds, run_id: res.run_id || "" };
        pushNote({ level: res.exit_code === 0 ? "ok" : "bad", title: (res.exit_code === 0 ? "✓ " : "✗ ") + runPayload.subcommand + " finished",
          detail: "exit " + res.exit_code + " · " + (res.seconds || 0) + "s", log: res.run_id ? { kind: "run", id: res.run_id, title: runPayload.subcommand } : null });
        if (res.model) diffModels(M, res.model);
        if (runPayload.subcommand === "audit" || runPayload.subcommand === "verify") { LENS = null; loadLens(true); }
        if (res.model) {
          load(res.model);
          INITIAL_KIT = JSON.parse(JSON.stringify(M.kit || {}));
        }
        liveAt = new Date();
        paintMeta();
        render();
        showToast(
          res.exit_code === 0 ? ("✓ Completed: " + (desc || res.command)) : ("! Exited " + res.exit_code + ": " + (desc || res.command)),
          "Finished in " + (res.seconds || 0) + "s — see Terminal Output below."
        );
      }).catch(function (err) {
        TERMINAL_STATE.running = false;
        TERMINAL_STATE.exitCode = 1;
        TERMINAL_STATE.output = "Network error while calling local server: " + err + "\nCopied CLI command to clipboard:\n$ " + fallbackCmd;
        copyText(fallbackCmd);
        render();
      });
    } else {
      copyCmd(fallbackCmd, desc);
    }
  }

  var PROFILE_OPEN = false;
  function paintContextBar() {
    var bar = document.getElementById("context-bar");
    if (!bar) return;
    bar.textContent = "";
    var kit = M.kit || {};
    var c = kit.constraints || {};
    var rt = kit.reading_tokens || {};
    var fixable = (kit.fixable || []).filter(function (f) { return f.level !== "info"; });
    var fails = (M.alerts || []).filter(function (a) { return a.level === "fail"; });

    var left = el("div", { cls: "profile-pop", id: "profile-pop", role: "group", "aria-label": "Agent profile settings" });

    // 2. Interactive Token-Saving Toggle
    var tsOn = !!kit.token_saving;
    var tsBtn = el("button", {
      cls: "seg-btn" + (tsOn ? " active" : ""),
      "aria-pressed": tsOn ? "true" : "false",
      style: "padding: 2px 8px; font-size: 11px; border: 1px solid " + (tsOn ? "var(--accent)" : "var(--line)") + "; background: " + (tsOn ? "var(--okbg)" : "var(--panel)") + "; color: " + (tsOn ? "var(--accent)" : "var(--text)") + "; font-weight: 600;",
      title: "Click to toggle Token-Saving Mode (Lean effort, single-agent review, compact logs)",
      text: tsOn ? ("Token saver on (−" + (rt.saved_pct || 65) + "%)") : "Token saver off",
      on: { click: function () {
        var nextState = !tsOn ? "on" : "off";
        kitApi("/api/config", { token_saving: nextState }, "python3 .ai-sdlc/bin/sdlc.py config --token-saving " + nextState, "Token-Saving Mode " + nextState);
      } }
    });
    left.appendChild(tsBtn);

    // 3. Interactive Effort Segmented Switcher
    var effCtrl = el("div", { cls: "context-ctrl", role: "group", "aria-label": "Default Effort Level" }, [
      el("span", { cls: "context-ctrl-lbl", text: "Effort" })
    ]);
    ["Lean", "Normal", "Beast"].forEach(function (eff) {
      var isAct = String(c.effort_mode || "Normal").toLowerCase() === eff.toLowerCase();
      effCtrl.appendChild(el("button", {
        cls: "seg-btn" + (isAct ? " active" : ""),
        "aria-pressed": isAct ? "true" : "false",
        style: "padding: 1px 7px; font-size: 11px;",
        text: eff,
        on: { click: function () {
          kitApi("/api/config", { effort: eff }, "python3 .ai-sdlc/bin/sdlc.py config --effort " + eff, "Effort=" + eff);
        } }
      }));
    });
    left.appendChild(effCtrl);

    // 4. Interactive 2nd-Agent Review Policy Switcher
    var revCtrl = el("div", { cls: "context-ctrl", role: "group", "aria-label": "Second Agent Review Policy" }, [
      el("span", { cls: "context-ctrl-lbl", text: "2nd Review" })
    ]);
    [["none", "Off"], ["Tier 1", "T1"], ["Tier 1 and 2", "T1+2"]].forEach(function (opt) {
      var isAct = String(c.independent_review || "none").toLowerCase() === opt[0].toLowerCase();
      revCtrl.appendChild(el("button", {
        cls: "seg-btn" + (isAct ? " active" : ""),
        "aria-pressed": isAct ? "true" : "false",
        style: "padding: 1px 7px; font-size: 11px;",
        text: opt[1],
        on: { click: function () {
          var cliVal = opt[0] === "none" ? "none" : (opt[0] === "Tier 1 and 2" ? "tier1-2" : "tier1");
          kitApi("/api/config", { independent_review: opt[0] }, "python3 .ai-sdlc/bin/sdlc.py config --independent-review " + cliVal, "Independent review=" + opt[0]);
        } }
      }));
    });
    left.appendChild(revCtrl);

    // 5. Preferred Reviewer Harness Switcher
    var cliCtrl = el("div", { cls: "context-ctrl", role: "group", "aria-label": "Preferred Reviewer CLI" }, [
      el("span", { cls: "context-ctrl-lbl", text: "Reviewer CLI" })
    ]);
    ["codex", "claude", "gemini"].forEach(function (cliName) {
      var isAct = String(c.preferred_reviewer || "codex").toLowerCase() === cliName;
      cliCtrl.appendChild(el("button", {
        cls: "seg-btn" + (isAct ? " active" : ""),
        "aria-pressed": isAct ? "true" : "false",
        style: "padding: 1px 6px; font-size: 11px;",
        text: cliName,
        on: { click: function () {
          if (typeof THREAD_STATE !== "undefined") THREAD_STATE.reviewer = cliName;
          kitApi("/api/config", { preferred_reviewer: cliName }, "python3 .ai-sdlc/bin/sdlc.py config --reviewer " + cliName, "Reviewer=" + cliName);
        } }
      }));
    });
    left.appendChild(cliCtrl);

    // The settings change how agents work, so they stay one deliberate click away.
    var revLabel = { "none": "no 2nd review", "Tier 1": "2nd review T1", "Tier 1 and 2": "2nd review T1–2" }[c.independent_review || "none"] || c.independent_review;
    var chip = el("button", { cls: "profile-chip", "aria-expanded": PROFILE_OPEN ? "true" : "false", "aria-controls": "profile-pop",
      title: "Agent profile: effort, independent review, reviewer CLI, token saver",
      on: { click: function () { PROFILE_OPEN = !PROFILE_OPEN; paintContextBar(); } } }, [
      el("span", { cls: "muted", text: "Agents" }),
      el("b", { text: (c.effort_mode || "Normal") + " · " + revLabel + " · " + (c.preferred_reviewer || "codex") + (kit.token_saving ? " · lean" : "") }),
      el("span", { cls: "muted", "aria-hidden": "true", text: PROFILE_OPEN ? "▴" : "▾" })
    ]);
    bar.appendChild(chip);
    if (PROFILE_OPEN) bar.appendChild(left);
  }
  document.addEventListener("click", function (e) {
    if (!PROFILE_OPEN) return;
    var slot = document.getElementById("context-bar");
    if (slot && !slot.contains(e.target)) { PROFILE_OPEN = false; paintContextBar(); }
  });

  function paintGlobalStagingBar() {}



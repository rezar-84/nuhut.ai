  // ---------------------------------------------------------------- kit control & repair panel
  function viewKit() {
    main.textContent = "";
    tab("project");
    crumbs([["Project", "project"], ["Kit settings"]]);
    var kit = M.kit || {};
    var c = kit.constraints || {};
    var rt = kit.reading_tokens || {};
    var inst = kit.installed || {};
    var fixable = kit.fixable || [];

    var hdrRow = el("div", { cls: "view-header" }, [
      el("div", null, [
        h(1, "Kit Constraints, Status & Auto-Repair"),
        el("p", { cls: "view-subtitle", text: "Adjust effort level, second-reviewer requirements, and Token-Saving Mode, inspect what is installed, and fix broken kit setup." })
      ]),
      el("div", { style: "display: flex; gap: 6px; align-items: center;" }, [
        LIVE && M.action_token ? el("button", {
          cls: "cmd-btn run-btn",
          text: "▶ Run Doctor Audit",
          on: { click: function () {
            runKitCmd({ subcommand: "doctor", strict: false }, "python3 .ai-sdlc/bin/sdlc.py doctor", "Doctor Audit");
          } }
        }) : null,
        el("span", {
          cls: "stamp " + (LIVE ? "ok" : "warn"),
          style: "padding: 5px 10px; font-size: 11px;",
          text: LIVE ? "LIVE SERVER (--SERVE) · 1-CLICK SAVE ACTIVE" : "STATIC PREVIEW · COPIES CLI COMMAND"
        })
      ])
    ]);
    main.appendChild(hdrRow);

    // Top Summary Strip
    var strip = el("div", { cls: "strip" }, [
      el("div", { cls: "stat" }, [el("b", { text: "v" + (kit.kit_version || "4.0") }), el("span", { text: "Kit Version (" + (kit.profile || "full") + ")" })]),
      el("div", { cls: "stat" }, [el("b", { text: c.effort_mode || "Normal" }), el("span", { text: "Default Effort Mode" })]),
      el("div", { cls: "stat" }, [el("b", { text: c.independent_review || "none" }), el("span", { text: "2nd Agent Review Policy" })]),
      el("div", { cls: "stat" }, [el("b", { text: "~" + ((rt.tier1_tokens || 0) / 1000).toFixed(1) + "k tok" }), el("span", { text: "Tier 1 Reading Cost" + (rt.saved_pct ? " (-" + rt.saved_pct + "%)" : "") })]),
      el("div", { cls: "stat" }, [el("b", { text: String(fixable.length) }), el("span", { text: fixable.length ? "Fixable Setup Issues" : "Setup Health: Clean" })])
    ]);
    main.appendChild(strip);

    if (kit.reviewer_warning) {
      main.appendChild(el("div", {
        cls: "quiet-note",
        style: "display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;"
      }, [
        el("div", { style: "display: flex; align-items: center; gap: 8px;" }, [
          el("span", { cls: "stamp warn", text: "Setup" }),
          el("span", { text: kit.reviewer_warning })
        ]),
        el("button", {
          cls: "cmd-btn",
          text: "Switch to Single-Agent Mode (Independent Review: none)",
          on: { click: function () {
            kitApi("/api/config", { independent_review: "none" }, "python3 .ai-sdlc/bin/sdlc.py config --independent-review none", "Set Independent review to none");
          } }
        })
      ]));
    }

    function renderDoctorFindingsSection() {
      var wrap = el("div", { style: "margin: 14px 0;" });
      wrap.appendChild(h(2, "Mechanical Doctor Findings (" + (M.alerts || []).length + ")"));
      if (!(M.alerts && M.alerts.length)) {
        wrap.appendChild(el("p", { cls: "muted", text: "All mechanical doctor checks pass." }));
      } else {
        var alertList = el("div", { cls: "alerts" });
        M.alerts.forEach(function (a) {
          alertList.appendChild(el("div", { cls: "alert " + a.level }, [
            el("span", { cls: "stamp " + (a.level === "fail" ? "bad" : "warn"), text: a.level.toUpperCase() + " · " + a.check }),
            a.where ? el("code", { text: a.where }) : null,
            el("span", { text: a.message })
          ]));
        });
        wrap.appendChild(alertList);
      }
      return wrap;
    }

    var hasFailAlerts = (M.alerts || []).some(function (a) { return a.level === "fail"; });
    if (hasFailAlerts) {
      main.appendChild(renderDoctorFindingsSection());
    }

    var grid = el("div", { cls: "kit-grid" });

    // Card 1: Token-Saving Mode Toggle & Reading Budget Meter
    var tsOn = !!kit.token_saving;
    var tsPending = !LIVE && STAGED_KIT.config.token_saving !== undefined;
    var tokenCard = el("div", { cls: "kit-card" + (tsOn ? " token-hero" : "") }, [
      el("h2", null, [
        el("span", { text: "Token-Saving Mode" }),
        el("span", {
          cls: "stamp " + (tsOn ? "ok" : ""),
          text: tsOn ? "ACTIVE (-" + (rt.saved_pct || 65) + "% CONTEXT)" : "OFF (STANDARD)"
        })
      ]),
      el("div", { cls: "muted", style: "font-size: 12px; line-height: 1.45;" }, [
        document.createTextNode("Cuts heavy token-consuming tasks in one click: sets Effort to "),
        el("code", { text: "Lean" }),
        document.createTextNode(" (stays in "),
        el("code", { text: "CARD.md" }),
        document.createTextNode(" without opening "),
        el("code", { text: "docs/process/*.md" }),
        document.createTextNode("), folds role reviews into a single pass, sets Independent 2nd-Agent Review to "),
        el("code", { text: "none" }),
        document.createTextNode(", and uses 1-line "),
        el("code", { text: "sdlc.py log --write" }),
        document.createTextNode(" worklogs.")
      ]),
      el("div", { style: "margin: 4px 0;" }, [
        el("div", { style: "display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;" }, [
          el("span", { text: "Estimated Tier 1 Reading Context: ~" + (rt.tier1_tokens || 0) + " tokens (" + (rt.tier1_words || 0) + " words)" }),
          el("span", { cls: "muted", text: "Baseline: ~" + (rt.baseline_tier1_tokens || 0) + " tokens" })
        ]),
        el("div", { cls: "meter-bar" }, [
          el("div", {
            cls: "meter-fill",
            style: "width: " + Math.min(100, Math.max(12, Math.round(((rt.tier1_tokens || 1) / Math.max(1, rt.baseline_tier1_tokens || 1)) * 100))) + "%;"
          })
        ]),
        el("div", { style: "display: flex; gap: 10px; margin-top: 6px; font-size: 11px; color: var(--muted);" }, [
          el("span", { text: "Tier 3: ~" + (rt.tier3_tokens || 0) + " tok" }),
          el("span", { text: "·" }),
          el("span", { text: "Tier 2: ~" + (rt.tier2_tokens || 0) + " tok" }),
          el("span", { text: "·" }),
          el("span", { text: "Tier 1: ~" + (rt.tier1_tokens || 0) + " tok" })
        ])
      ]),
      el("div", { style: "display: flex; gap: 8px; align-items: center; margin-top: 4px;" }, [
        el("button", {
          cls: "cmd-btn " + (tsOn ? "" : "primary") + (tsPending ? " pending" : ""),
          "aria-pressed": tsOn ? "true" : "false",
          text: tsOn ? "Disable Token-Saving Mode (Restore Previous Settings)" : "Enable Token-Saving Mode",
          on: { click: function () {
            var targetState = !tsOn ? "on" : "off";
            kitApi("/api/config", { token_saving: targetState }, "python3 .ai-sdlc/bin/sdlc.py config --token-saving " + targetState, "Token-Saving Mode " + targetState);
          } }
        })
      ])
    ]);
    grid.appendChild(tokenCard);

    // Card 2: Kit Constraints & Second-Reviewer Policy
    function makeSegControl(options, currentVal, stagedVal, onPick) {
      var grp = el("div", { cls: "seg-group", role: "group" });
      options.forEach(function (opt) {
        var val = opt[0], label = opt[1];
        var isCurrent = String(currentVal).toLowerCase() === String(val).toLowerCase();
        var isPending = !LIVE && stagedVal !== undefined && String(stagedVal).toLowerCase() === String(val).toLowerCase();
        grp.appendChild(el("button", {
          cls: "seg-btn" + (isCurrent ? " active" : "") + (isPending ? " pending" : ""),
          "aria-pressed": isCurrent ? "true" : "false",
          text: label + (isPending ? " *" : ""),
          on: { click: function () { onPick(val); } }
        }));
      });
      return grp;
    }

    var cliTools = inst.cli_tools || {};
    var constraintsCard = el("div", { cls: "kit-card" }, [
      el("h2", null, [el("span", { text: "Kit Constraints & Reviewer Policy" }), el("span", { cls: "stamp", text: "CHARTER.MD + PROFILE.JSON" })]),
      el("div", { cls: "constraint-row" }, [
        el("div", { cls: "constraint-label" }, [
          el("strong", { text: "Default Effort Level" }),
          el("span", { text: "Breadth of reading, role selection, and test depth" })
        ]),
        makeSegControl([["Lean", "Lean"], ["Normal", "Normal"], ["Beast", "Beast"]], c.effort_mode || "Normal", STAGED_KIT.config.effort, function (v) {
          kitApi("/api/config", { effort: v }, "python3 .ai-sdlc/bin/sdlc.py config --effort " + v, "Effort=" + v);
        })
      ]),
      el("div", { cls: "constraint-row" }, [
        el("div", { cls: "constraint-label" }, [
          el("strong", { text: "Second Agent / Independent Review" }),
          el("span", { text: "Off by default; require cross-model review only when manually enabled" })
        ]),
        makeSegControl([["none", "Off (Default)"], ["Tier 1", "Tier 1 Only"], ["Tier 1 and 2", "Tier 1 & 2"]], c.independent_review || "none", STAGED_KIT.config.independent_review, function (v) {
          var cliVal = v === "none" ? "none" : (v === "Tier 1 and 2" ? "tier1-2" : "tier1");
          kitApi("/api/config", { independent_review: v }, "python3 .ai-sdlc/bin/sdlc.py config --independent-review " + cliVal, "Independent review=" + v);
        })
      ]),
      el("div", { cls: "constraint-row" }, [
        el("div", { cls: "constraint-label" }, [
          el("strong", { text: "Preferred Second Reviewer CLI" }),
          el("span", { text: "Default harness for `sdlc.py review` (ON = on PATH)" })
        ]),
        makeSegControl(["codex", "claude", "gemini"].map(function (k) {
          return [k, k + (cliTools[k] ? " [ON]" : " [OFF]")];
        }), c.preferred_reviewer || "codex", STAGED_KIT.config.preferred_reviewer, function (v) {
          kitApi("/api/config", { preferred_reviewer: v }, "python3 .ai-sdlc/bin/sdlc.py config --reviewer " + v, "Reviewer=" + v);
        })
      ]),
      el("div", { cls: "constraint-row" }, [
        el("div", { cls: "constraint-label" }, [
          el("strong", { text: "Decision Style" }),
          el("span", { text: "Ask every choice · Guide with recommendation · Autopilot" })
        ]),
        makeSegControl([["Ask", "Ask"], ["Guide", "Guide"], ["Autopilot", "Autopilot"]], c.decision_style || "Guide", STAGED_KIT.config.decision_style, function (v) {
          kitApi("/api/config", { decision_style: v }, "python3 .ai-sdlc/bin/sdlc.py config --decision-style " + v, "Decision style=" + v);
        })
      ]),
      el("div", { cls: "constraint-row" }, [
        el("div", { cls: "constraint-label" }, [
          el("strong", { text: "Tier Rules & Development Method" }),
          el("span", { text: "Standard (blast radius) vs Strict · Item vs Epic" })
        ]),
        el("div", { style: "display: flex; gap: 6px; flex-wrap: wrap;" }, [
          makeSegControl([["Standard", "Standard"], ["Strict", "Strict"]], c.tier_rules || "Standard", STAGED_KIT.config.tier_rules, function (v) {
            kitApi("/api/config", { tier_rules: v }, "python3 .ai-sdlc/bin/sdlc.py config --tier-rules " + v, "Tier rules=" + v);
          }),
          makeSegControl([["Item", "Item"], ["Epic", "Epic"]], c.dev_method || "Item", STAGED_KIT.config.dev_method, function (v) {
            kitApi("/api/config", { dev_method: v }, "python3 .ai-sdlc/bin/sdlc.py config --dev-method " + v, "Dev method=" + v);
          })
        ])
      ])
    ]);
    grid.appendChild(constraintsCard);

    // Card 3: Fix Kit & Broken Setup ("Safe Auto-Repair")
    var hasCriticalFix = fixable.some(function (f) { return f.level === "fail"; });
    var repairCard = el("div", { cls: "kit-card" + (hasCriticalFix ? " alert-hero" : "") }, [
      el("h2", null, [
        el("span", { text: "Fix Kit & Broken Setup" }),
        el("button", {
          cls: "cmd-btn primary",
          text: "Fix Safe Setup Issues",
          on: { click: function () {
            kitApi("/api/fix", { action: "all" }, "python3 .ai-sdlc/bin/sdlc.py fix all", "Ran safe kit repairs");
          } }
        })
      ]),
      el("div", { cls: "muted", style: "font-size: 12px;", text: "Mechanical repairs sync profile.json drift, wire missing AGENTS.md pointers, restore interrupted bite runs, and unlock tests without fabricating charter decisions." })
    ]);

    var repairActions = [
      { id: "sync-profile", label: "Sync .ai-sdlc/profile.json with charter.md", cmd: "python3 .ai-sdlc/bin/sdlc.py fix sync-profile" },
      { id: "wire-pointer", label: "Wire CLAUDE.md pointer to AGENTS.md", cmd: "python3 .ai-sdlc/bin/sdlc.py fix wire-pointer" },
      { id: "restore-bite", label: "Restore interrupted `sdlc.py bite` backup", cmd: "python3 .ai-sdlc/bin/sdlc.py fix restore-bite" },
      { id: "unlock-tests", label: "Unlock reproducing tests in .ai-sdlc/test-lock.txt", cmd: "python3 .ai-sdlc/bin/sdlc.py fix unlock-tests" }
    ];
    repairActions.forEach(function (ra) {
      var activeIssue = fixable.filter(function (f) { return f.id === ra.id; })[0];
      repairCard.appendChild(el("div", { cls: "constraint-row" }, [
        el("div", { cls: "constraint-label" }, [
          el("strong", { text: ra.label }),
          el("span", {
            style: activeIssue ? "color: var(--bad); font-weight: 600;" : "",
            text: activeIssue ? ("NEEDED: " + activeIssue.detail) : "OK · Healthy"
          })
        ]),
        el("button", {
          cls: "cmd-btn" + (activeIssue ? " primary" : ""),
          text: activeIssue ? "Fix Now" : "Re-run",
          on: { click: function () {
            kitApi("/api/fix", { action: ra.id }, ra.cmd, ra.label);
          } }
        })
      ]));
    });

    // Blank checks.* helper (explicit user choice, never fabricated automatically)
    var blankStages = inst.blank_stages || [];
    var detectedCmds = inst.detected_commands || {};
    if (blankStages.length) {
      var blankBox = el("div", { style: "margin-top: 6px; padding-top: 8px; border-top: 1px solid var(--line);" }, [
        el("div", { style: "font-size: 12px; font-weight: 600; margin-bottom: 6px;", text: "Unconfigured Check Stages in charter.md (" + blankStages.length + " blank)" })
      ]);
      blankStages.forEach(function (st) {
        var suggested = detectedCmds[st];
        var btns = [];
        if (suggested) {
          btns.push(el("button", {
            cls: "cmd-btn primary",
            text: "Use `" + suggested + "`",
            on: { click: function () {
              var ch = {}; ch[st] = suggested;
              kitApi("/api/config", { checks: ch }, "python3 .ai-sdlc/bin/sdlc.py config --set-check " + st + "=\"" + suggested + "\"", "Set checks." + st);
            } }
          }));
        }
        btns.push(el("button", {
          cls: "cmd-btn",
          text: "Mark `absent`",
          on: { click: function () {
            var ch = {}; ch[st] = "absent";
            kitApi("/api/config", { checks: ch }, "python3 .ai-sdlc/bin/sdlc.py config --set-check " + st + "=absent", "Marked checks." + st + " absent");
          } }
        }));
        blankBox.appendChild(el("div", { style: "display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 12px;" }, [
          el("code", { text: "checks." + st }),
          el("div", { style: "display: flex; gap: 6px;" }, btns)
        ]));
      });
      repairCard.appendChild(blankBox);
    }
    grid.appendChild(repairCard);

    // Card 4: What's Installed (Kit Status Inventory)
    var harnesses = inst.harnesses || [];
    var hooks = inst.hooks || {};
    var guards = inst.guards || {};
    var skills = inst.skills || [];
    var activeRoles = (inst.roles || []).filter(function (r) { return r.active; });

    var invCard = el("div", { cls: "kit-card" }, [
      el("h2", null, [el("span", { text: "Installed Inventory (Kit Status)" }), el("span", { cls: "stamp", text: skills.length + " SKILLS · " + activeRoles.length + " ROLES" })])
    ]);

    var hSection = el("div", null, [
      el("div", { style: "font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;", text: "Agent Harnesses & Contract Pointers" })
    ]);
    var hWrap = el("div", { style: "display: flex; flex-wrap: wrap; gap: 6px;" });
    harnesses.forEach(function (hItem) {
      hWrap.appendChild(el("span", {
        cls: "stamp " + (hItem.wired ? "ok" : "bad"),
        text: hItem.file + (hItem.wired ? " · WIRED" : " · UNWIRED")
      }));
    });
    hSection.appendChild(hWrap);
    invCard.appendChild(hSection);

    var cSection = el("div", null, [
      el("div", { style: "font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;", text: "Detected CLI Tools on PATH" }),
      el("div", { style: "display: flex; flex-wrap: wrap; gap: 6px;" }, Object.keys(cliTools).map(function (k) {
        return el("span", {
          cls: "stamp " + (cliTools[k] ? "ok" : ""),
          text: k + (cliTools[k] ? " · ON PATH" : " · ABSENT")
        });
      }))
    ]);
    invCard.appendChild(cSection);

    var gSection = el("div", null, [
      el("div", { style: "font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;", text: "Enforcement Hooks & Guards" }),
      el("div", { style: "display: flex; flex-wrap: wrap; gap: 6px;" }, [
        el("span", { cls: "chip", text: "PreToolUse hooks: " + ((hooks.claude_hooks && hooks.claude_hooks.length) || 0) }),
        el("span", { cls: "chip", text: "Git pre-commit: " + (hooks.git_pre_commit ? "ON" : "off") }),
        el("span", { cls: "chip", text: "Git commit-msg: " + (hooks.git_commit_msg ? "ON" : "off") }),
        el("span", { cls: "chip", text: "Protected paths: " + ((guards.protected && guards.protected.length) || 0) }),
        el("span", { cls: "chip", text: "Locked tests: " + ((guards.test_locks && guards.test_locks.length) || 0) }),
        el("span", { cls: "chip", text: "Approval gates: " + ((guards.gates && guards.gates.length) || 0) })
      ])
    ]);
    invCard.appendChild(gSection);

    var rSection = el("div", null, [
      el("div", { style: "font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;", text: "Active Charter Roles (" + activeRoles.length + ")" }),
      el("div", { style: "display: flex; flex-wrap: wrap; gap: 4px;" }, activeRoles.map(function (r) {
        return el("span", { cls: "chip", text: r.name });
      }))
    ]);
    invCard.appendChild(rSection);
    grid.appendChild(invCard);
    main.appendChild(grid);

    if (!hasFailAlerts) {
      main.appendChild(renderDoctorFindingsSection());
    }
  }


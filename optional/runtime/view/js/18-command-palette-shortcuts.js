  // ---------------------------------------------------------------- command palette & shortcuts
  var paletteEl = document.getElementById("palette");
  var paletteBackdropEl = document.getElementById("palette-backdrop");
  var shortcutsEl = document.getElementById("shortcuts-modal");
  var paletteSelectedIndex = 0;
  var paletteCurrentItems = [];

  function closePalette() {
    var wasOpen = paletteEl && paletteEl.classList.contains("open");
    if (paletteEl) paletteEl.className = "palette";
    if (paletteBackdropEl) paletteBackdropEl.className = "palette-backdrop";
    if (wasOpen) restoreLastFocus();
  }
  if (paletteBackdropEl) paletteBackdropEl.addEventListener("click", function () {
    closePalette();
    closeShortcutsModal();
  });

  function closeShortcutsModal() {
    var wasOpen = shortcutsEl && shortcutsEl.classList.contains("open");
    if (shortcutsEl) shortcutsEl.className = "shortcuts-modal";
    if (paletteBackdropEl) paletteBackdropEl.className = "palette-backdrop";
    if (wasOpen) restoreLastFocus();
  }

  function openShortcutsModal() {
    if (!shortcutsEl || !paletteBackdropEl) return;
    if (!shortcutsEl.classList.contains("open")) lastFocusedEl = document.activeElement;
    if (paletteEl) paletteEl.className = "palette";
    if (drawerEl && !isDocked()) { drawerEl.className = "drawer"; if (backdropEl) backdropEl.className = "drawer-backdrop"; }
    shortcutsEl.textContent = "";

    var closeBtn = el("button", { cls: "drawer-close", "aria-label": "Close keyboard shortcuts", text: "✕", on: { click: closeShortcutsModal } });
    var hdr = el("div", { style: "display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;" }, [
      el("h3", { style: "margin: 0;", text: "Keyboard Shortcuts" }),
      closeBtn
    ]);
    shortcutsEl.appendChild(hdr);

    var rows = [
      ["Cmd/Ctrl + K  or  /", "Open command & search palette"],
      ["1 … 7", "Jump to tabs (1: Inbox, 2: Board, 3: Dashboard, 4: Blockages, 5: Git, 6: Docs, 7: Project)"],
      ["j / k  or  ↑ / ↓", "Move through the Inbox, Board cards or Documents; the inspector follows"],
      ["h / l  or  ← / →", "Board: move between columns"],
      ["o  or  Enter", "Open the selected item's page"],
      ["]", "Open or fold the side panel (Item · Activity · Issues)"],
      ["Backspace  or  Alt + ←", "Back to the list you came from"],
      ["r", "Inbox: run (or copy) the selected thread's recommended command"],
      ["n", "Notifications (the panel's Activity tab)"],
      ["t", "Toggle Dark / Light theme"],
      ["?", "Show this shortcuts help"],
      ["Esc", "Close the palette or a dialog; fold the side panel"]
    ];

    rows.forEach(function (r) {
      shortcutsEl.appendChild(el("div", { cls: "shortcut-row" }, [
        el("span", { text: r[1] }),
        el("kbd", { text: r[0] })
      ]));
    });

    shortcutsEl.className = "shortcuts-modal open";
    paletteBackdropEl.className = "palette-backdrop open";
    setTimeout(function () { closeBtn.focus(); }, 30);
  }

  function openPalette(initialQuery) {
    if (!paletteEl || !paletteBackdropEl) return;
    if (!paletteEl.classList.contains("open")) lastFocusedEl = document.activeElement;
    if (shortcutsEl) shortcutsEl.className = "shortcuts-modal";
    if (drawerEl && !isDocked()) { drawerEl.className = "drawer"; if (backdropEl) backdropEl.className = "drawer-backdrop"; }
    paletteEl.textContent = "";
    paletteSelectedIndex = 0;

    var input = el("input", {
      cls: "palette-input",
      placeholder: "Search work items, docs, headings, commits, or run a command…",
      value: typeof initialQuery === "string" ? initialQuery : "",
      "aria-label": "Command Palette"
    });

    var inputWrap = el("div", { cls: "palette-input-wrap" }, [
      el("span", { style: "color: var(--muted); font-size: 15px;", text: "⌕" }),
      input
    ]);

    var resultsContainer = el("div", { cls: "palette-results" });

    var footer = el("div", { cls: "palette-footer" }, [
      el("div", null, [
        el("kbd", { text: "↑↓" }), document.createTextNode(" navigate "),
        el("kbd", { text: "↵" }), document.createTextNode(" select "),
        el("kbd", { text: "esc" }), document.createTextNode(" close")
      ]),
      el("div", null, [
        el("kbd", { text: "?" }), document.createTextNode(" shortcuts")
      ])
    ]);

    paletteEl.appendChild(inputWrap);
    paletteEl.appendChild(resultsContainer);
    paletteEl.appendChild(footer);

    function buildPaletteItems(query) {
      var needle = (query || "").trim().toLowerCase();
      var items = [];

      var navActions = [
        { label: "Go to Inbox (Action Threads & Activity Feed)", hint: "Tab 1", run: function () { go("threads"); } },
        { label: "Go to Activity Feed (all events, newest first)", hint: "Inbox", run: function () { THREAD_STATE.mode = "feed"; go("threads"); } },
        { label: "Go to Dashboard (Needs you, Health, Flow)", hint: "Tab 3", run: function () { go("dashboard"); } },
        { label: "Go to Tests & verify", hint: "Dashboard", run: function () { go("dashboard/tests"); } },
        { label: "Go to Runs & logs", hint: "Dashboard", run: function () { go("dashboard/runs"); } },
        { label: "Go to Doctor findings", hint: "Dashboard", run: function () { go("dashboard/doctor"); } },
        { label: "Show Notifications", hint: "Key: N", run: function () { toggleNotes(); } },
        { label: "Go to Project (stack, build, security, deploy, env, agents)", hint: "Tab 7", run: function () { go("project"); } },
        { label: "Go to Security findings", hint: "Project", run: function () { go("project/security"); } },
        { label: "Go to Agents & skills", hint: "Project", run: function () { go("project/agents"); } },
        { label: "Go to Kit settings (constraints, token saver, repair)", hint: "Project", run: function () { go("project/kit"); } },
        { label: "Toggle Token-Saving Mode (Lean + Single-Agent + Compact)", hint: "Kit settings", run: function () { go("project/kit"); } },
        { label: "Go to Project Map", hint: "Dashboard", run: function () { go("map"); } },
        { label: "Go to Kanban Board", hint: "Tab 2", run: function () { go("board"); } },
        { label: "Go to Dependencies & Blockages Flow", hint: "Tab 4", run: function () { go("waiting"); } },
        { label: "Go to Git Traceability", hint: "Tab 5", run: function () { go("git"); } },
        { label: "Go to Documents", hint: "Tab 6", run: function () { go("docs"); } },
        { label: "View Dependencies & Blockages Map", hint: "Map Focus", run: function () { go("map"); setTimeout(function () { var b = document.querySelector('[data-p="blockages"]'); if (b) b.click(); }, 60); } },
        { label: "Toggle Theme (Dark / Light)", hint: "Key: T", run: function () { toggleTheme(); } },
        { label: "Export Standalone HTML", hint: "Action", run: function () { exportHtml(); } },
        { label: "View Keyboard Shortcuts", hint: "Key: ?", run: function () { openShortcutsModal(); } }
      ];

      var matchedActions = navActions.filter(function (a) {
        return !needle || a.label.toLowerCase().indexOf(needle) >= 0 || (a.hint && a.hint.toLowerCase().indexOf(needle) >= 0);
      });
      if (matchedActions.length) {
        items.push({ section: "Actions & Navigation" });
        items = items.concat(matchedActions);
      }

      var matchedItems = M.order.filter(function (id) {
        var it = ITEMS[id];
        return !needle || id.toLowerCase().indexOf(needle) >= 0 || (it.title || "").toLowerCase().indexOf(needle) >= 0;
      }).slice(0, needle ? 12 : 5).map(function (id) {
        var it = ITEMS[id];
        return {
          label: id + " — " + clip(it.title, 55),
          hint: it.column + (it.tier ? " · T" + it.tier : ""),
          run: function () { openItemDrawer(id); }
        };
      });
      if (matchedItems.length) {
        items.push({ section: "Work Items" });
        items = items.concat(matchedItems);
      }

      var matchedDocs = DOCS.filter(function (d) {
        return !needle || d.path.toLowerCase().indexOf(needle) >= 0 || (d.title || "").toLowerCase().indexOf(needle) >= 0;
      }).slice(0, needle ? 8 : 4).map(function (d) {
        var docIdx = DOCS.indexOf(d);
        return {
          label: d.path,
          hint: d.kind,
          run: function () { go(docRoute(docIdx)); }
        };
      });
      if (matchedDocs.length) {
        items.push({ section: "Documents" });
        items = items.concat(matchedDocs);
      }

      if (needle.length >= 2) {
        var matchedHeadings = [];
        DOCS.forEach(function (d, docIdx) {
          (d.headings || []).forEach(function (hd) {
            if (matchedHeadings.length < 6 && (hd.text || "").toLowerCase().indexOf(needle) >= 0) {
              matchedHeadings.push({
                label: "§ " + clip(hd.text, 52),
                hint: d.path.split("/").pop() + ":" + hd.line,
                run: function () { go(docRoute(docIdx, hd.line)); }
              });
            }
          });
        });
        if (matchedHeadings.length) {
          items.push({ section: "Document Sections" });
          items = items.concat(matchedHeadings);
        }

        var allCommits = (M.git && M.git.commits) || [];
        var matchedCommits = allCommits.filter(function (c) {
          return (c.sha + " " + (c.subject || "") + " " + (c.author || "")).toLowerCase().indexOf(needle) >= 0;
        }).slice(0, 5).map(function (c) {
          return {
            label: c.sha + " — " + clip(c.subject || "", 50),
            hint: c.author || c.date || "commit",
            run: function () { openCommitDrawer(c); }
          };
        });
        if (matchedCommits.length) {
          items.push({ section: "Git Commits" });
          items = items.concat(matchedCommits);
        }

        items.push({ section: "Full Search" });
        items.push({
          label: "Open full search page for \"" + query.trim() + "\"",
          hint: "Enter",
          run: function () { go("search/" + encodeURIComponent(query.trim())); }
        });
      }

      return items;
    }

    function renderPalette() {
      resultsContainer.textContent = "";
      var allEntries = buildPaletteItems(input.value);
      var selectableItems = [];
      paletteCurrentItems = selectableItems;

      allEntries.forEach(function (entry) {
        if (entry.section) {
          resultsContainer.appendChild(el("div", { cls: "palette-section", text: entry.section }));
          return;
        }
        var itemIndex = selectableItems.length;
        selectableItems.push(entry);

        var isSelected = itemIndex === paletteSelectedIndex;
        var row = el("div", {
          cls: "palette-item" + (isSelected ? " selected" : ""),
          on: {
            mouseenter: function () {
              paletteSelectedIndex = itemIndex;
              updatePaletteSelection();
            },
            click: function () {
              closePalette();
              entry.run();
            }
          }
        }, [
          el("strong", { text: entry.label }),
          entry.hint ? el("span", { cls: "muted", style: "font-size: 11px;", text: entry.hint }) : null
        ]);
        resultsContainer.appendChild(row);
      });

      if (!selectableItems.length) {
        resultsContainer.appendChild(el("div", { cls: "muted", style: "padding: 16px; text-align: center;", text: "No matching commands or items" }));
      }
    }

    function updatePaletteSelection() {
      var itemEls = resultsContainer.querySelectorAll(".palette-item");
      for (var k = 0; k < itemEls.length; k++) {
        if (k === paletteSelectedIndex) {
          itemEls[k].classList.add("selected");
          itemEls[k].scrollIntoView({ block: "nearest" });
        } else {
          itemEls[k].classList.remove("selected");
        }
      }
    }

    input.addEventListener("input", function () {
      paletteSelectedIndex = 0;
      renderPalette();
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (paletteCurrentItems.length) {
          paletteSelectedIndex = (paletteSelectedIndex + 1) % paletteCurrentItems.length;
          updatePaletteSelection();
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (paletteCurrentItems.length) {
          paletteSelectedIndex = (paletteSelectedIndex - 1 + paletteCurrentItems.length) % paletteCurrentItems.length;
          updatePaletteSelection();
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (paletteCurrentItems[paletteSelectedIndex]) {
          closePalette();
          paletteCurrentItems[paletteSelectedIndex].run();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        closePalette();
      }
    });

    paletteEl.className = "palette open";
    paletteBackdropEl.className = "palette-backdrop open";
    renderPalette();
    setTimeout(function () { input.focus(); }, 50);
  }

  // Unified global keyboard navigation & modal focus trap
  window.addEventListener("keydown", function (e) {
    if (e.key === "Tab") {
      var activeModal = (paletteEl && paletteEl.classList.contains("open")) ? paletteEl :
                        ((shortcutsEl && shortcutsEl.classList.contains("open")) ? shortcutsEl :
                        ((drawerEl && drawerEl.classList.contains("open") && !isDocked()) ? drawerEl : null));
      if (activeModal) {
        var focusables = activeModal.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (focusables.length) {
          var first = focusables[0], last = focusables[focusables.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
            return;
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
            return;
          }
        }
      }
    }

    var tag = (e.target && e.target.tagName) || "";
    var isInput = /^(INPUT|SELECT|TEXTAREA)$/.test(tag);

    if (e.key === "Escape") {
      closePalette();
      closeShortcutsModal();
      closeDrawer();
      if (isInput) e.target.blur();
      return;
    }

    if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      openPalette();
      return;
    }

    if (isInput) return;

    if (!e.metaKey && !e.ctrlKey && !e.altKey && /^#\/board/.test(location.hash) && /^(j|k|h|l|o|Enter|Arrow(Up|Down|Left|Right))$/.test(e.key)
        && !(paletteEl && paletteEl.classList.contains("open")) && (!drawerEl.classList.contains("open") || isDocked())
        && !(e.target && e.target.closest && e.target.closest("#drawer, button, a"))) {
      if (boardKey(e)) { e.preventDefault(); return; }
    }

    if (!e.metaKey && !e.ctrlKey && !e.altKey && /^#\/threads/.test(location.hash || "#/threads") && !(paletteEl && paletteEl.classList.contains("open"))) {
      if (/^(j|k|ArrowDown|ArrowUp)$/.test(e.key) && !(e.target && e.target.closest && e.target.closest(".thread-row, .feed-row, #drawer"))) {
        var rows = [].slice.call(document.querySelectorAll("#main .thread-row[data-thread-id], #main .feed-row[data-thread-id]"));
        if (rows.length) {
          e.preventDefault();
          var at = -1;
          rows.forEach(function (r, i) { if (at < 0 && (r.classList.contains("active") || r.classList.contains("sel"))) at = i; });
          var nx = rows[Math.max(0, Math.min(rows.length - 1, at + (/^(k|ArrowUp)$/.test(e.key) ? -1 : 1)))];
          var nid = nx.getAttribute("data-thread-id"), idx = rows.indexOf(nx);
          THREAD_STATE.selected = nid;
          go("threads/" + encodeURIComponent(nid));
          setTimeout(function () { var t = document.querySelectorAll("#main .thread-row[data-thread-id], #main .feed-row[data-thread-id]")[idx]; if (t) t.focus(); }, 20);
          return;
        }
      }
      if (e.key === "r" && THREAD_STATE.selected && ITEMS[THREAD_STATE.selected]) {
        e.preventDefault();
        var dx = diagnoseNextAction(ITEMS[THREAD_STATE.selected]);
        if (LIVE && M.action_token && dx.runPayload) runKitCmd(dx.runPayload, dx.cmd, dx.label);
        else copyCmd(dx.cmd, dx.label);
        return;
      }
    }

    // Dashboard: j/k walk the Needs you rows.
    if (/^#\/dashboard\/?$/.test(location.hash) && /^(j|k)$/.test(e.key) && !e.metaKey && !e.ctrlKey && !e.altKey) {
      var needRows = [].slice.call(document.querySelectorAll("#main [data-need]"));
      if (needRows.length) {
        e.preventDefault();
        var cur = needRows.indexOf(document.activeElement);
        var nxt = needRows[Math.max(0, Math.min(needRows.length - 1, cur + (e.key === "k" ? -1 : 1)))];
        nxt.focus();
        nxt.scrollIntoView({ block: "nearest" });
        return;
      }
    }

    if (e.key === "/") {
      e.preventDefault();
      openPalette();
    } else if (e.key === "?") {
      e.preventDefault();
      openShortcutsModal();
    } else if (e.key === "t" || e.key === "T") {
      e.preventDefault();
      toggleTheme();
    } else if (e.key === "]") {
      e.preventDefault();
      if (PANEL.open) closeDrawer();
      else if (INSPECT || PANEL.tab !== "item") showPanel(INSPECT ? PANEL.tab : PANEL.tab);
      else if (BOARD_SEL && ITEMS[BOARD_SEL]) openItemDrawer(BOARD_SEL);
      else if (THREAD_STATE.selected && ITEMS[THREAD_STATE.selected]) openItemDrawer(THREAD_STATE.selected);
      else showPanel("issues");
    } else if (e.key === "Backspace" && backTarget()) {
      e.preventDefault();
      goBack();
    } else if (e.key === "n" || e.key === "N") {
      e.preventDefault();
      toggleNotes();
    } else if (e.key === "1") {
      go("threads");
    } else if (e.key === "2") {
      go("board");
    } else if (e.key === "3") {
      go("dashboard");
    } else if (e.key === "4") {
      go("waiting");
    } else if (e.key === "5") {
      go("git");
    } else if (e.key === "6") {
      go("docs");
    } else if (e.key === "7") {
      go("project");
    }
  });


  "use strict";
  var main = document.getElementById("main");
  if (!M) {
    main.textContent = "No model in this page. Generate it with: python3 .ai-sdlc/bin/sdlc.py view";
    return;
  }
  var ITEMS, DOCS, WL, ID_RE, DOC_BY_PATH;
  var INITIAL_KIT = JSON.parse(JSON.stringify((M && M.kit) || {}));
  // Everything derived from the model, so live mode can swap in a new one.
  function load(model) {
    M = model;
    ITEMS = M.items; DOCS = M.docs; WL = M.worklog;
    ID_RE = M.id_pattern ? new RegExp(M.id_pattern, "g") :
            (M.prefix ? new RegExp("\\b" + M.prefix.replace(/[.*+?^$()|[\]\\]/g, "\\$&") + "-[0-9]+\\b", "g") : null);
    DOC_BY_PATH = {};
    DOCS.forEach(function (d, n) { DOC_BY_PATH[d.path] = n; });
  }
  load(M);


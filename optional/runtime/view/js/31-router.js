  // ---------------------------------------------------------------- router
  function render() {
    var parts = location.hash.replace(/^#\/?/, "").split("/");
    var y = window.scrollY;
    main.textContent = "";
    var route = parts[0] || "threads";
    if (currentDocScrollSpy && route !== "doc") {
      window.removeEventListener("scroll", currentDocScrollSpy);
      currentDocScrollSpy = null;
    }
    if (route === "threads") viewThreads(decodeURIComponent(parts[1] || ""));
    else if (route === "kit") { location.replace("#/project/kit"); return; }
    else if (route === "project") viewProject(parts[1] || "");
    else if (route === "map") viewMap();
    else if (route === "cockpit") { location.replace("#/dashboard" + (parts[1] ? "/" + parts[1] : "")); return; }
    else if (route === "dashboard") viewDashboard(parts[1] || "");
    else if (route === "board") {
      var focusId = null, stageFilter = null;
      if (parts[1] === "focus") {
        focusId = decodeURIComponent(parts[2] || "");
      } else if (parts[1] === "stage") {
        stageFilter = decodeURIComponent(parts[2] || "");
        if (parts[3]) focusId = decodeURIComponent(parts[3] || "");
      } else if (parts[1] && ITEMS[decodeURIComponent(parts[1])]) {
        focusId = decodeURIComponent(parts[1]);
      }
      viewBoard(focusId, stageFilter);
    }
    else if (route === "activity") { THREAD_STATE.mode = "feed"; location.replace("#/threads"); return; }
    else if (route === "waiting" || route === "blockages") viewWaiting();
    else if (route === "git") viewGit();
    else if (route === "docs" && parts[1] === "specs") viewSpecs(decodeURIComponent(parts[2] || ""));
    else if (route === "docs") viewDocs();
    else if (route === "item") viewItem(decodeURIComponent(parts[1] || ""));
    else if (route === "doc") viewDoc(decodeURIComponent(parts[1] || ""), parts[2] !== undefined ? +parts[2] : undefined);
    else if (route === "search") viewSearch(decodeURIComponent(parts.slice(1).join("/")));
    else viewThreads("");
    if (render.same) window.scrollTo(0, y);
    markSelected();
    render.same = false;
  }
  var lastHash = location.hash;
  renderPanel({ quiet: true });
  trackNav();
  window.addEventListener("hashchange", function () {
    trackNav();
    if (location.hash.indexOf("#/item/") !== 0 || lastHash.split("/")[2] !== location.hash.split("/")[2]) ITEM_TAB = "overview";
    lastHash = location.hash;
    window.scrollTo(0, 0);
    render();
  });
  var inner = render;
  render = function () { render.same = true; inner(); };
  inner();


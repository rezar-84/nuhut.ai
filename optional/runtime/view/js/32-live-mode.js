  // ---------------------------------------------------------------- live mode
  // Poll a cheap fingerprint; fetch the model only when it moved. A redraw keeps the
  // route, folds, filters, open panels and scroll, and waits while you are typing.
  if (LIVE) {
    var pending = null;
    function busy() {
      var a = document.activeElement;
      return a && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName) && a.id !== "q";
    }
    function apply(model) {
      if (busy()) { pending = model; return; }
      pending = null;
      var open = [].map.call(document.querySelectorAll("details[open] > summary"), function (x) {
        return x.textContent.replace(/[0-9]+/g, "#");
      });
      var prevModel = M;
      load(model);
      diffModels(prevModel, model);
      liveAt = new Date();
      paintMeta();
      render();
      [].forEach.call(document.querySelectorAll("details > summary"), function (x) {
        if (open.indexOf(x.textContent.replace(/[0-9]+/g, "#")) >= 0) x.parentNode.open = true;
      });
      // A docked inspector follows the new model without taking focus.
      if (isDocked() && PANEL.tab === "item" && INSPECT && INSPECT.kind === "item" && !(drawerEl.contains(document.activeElement))) reopenInspect(INSPECT, true);
      else refreshPanelChrome();
    }
    document.addEventListener("focusout", function () { if (pending) setTimeout(function () { if (pending) apply(pending); }, 0); });
    function poll() {
      fetch("version", { cache: "no-store" }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }).then(function (v) {
        var was = liveState;
        liveState = "live";
        if (v && v !== M.version) {
          return fetch("model.json", { cache: "no-store" }).then(function (r) {
            if (!r.ok) throw new Error(r.status);
            return r.json();
          }).then(apply);
        }
        if (was !== "live") paintMeta();
        else paintActivityBar();
      }).catch(function () {
        if (liveState !== "down") { liveState = "down"; paintMeta(); }
      }).then(function () {
        setTimeout(poll, (M.live_interval || 2) * 1000);
      });
    }
    setTimeout(poll, (M.live_interval || 2) * 1000);
  }
  // Warm the Project lens in the background, so its failures reach Needs you and Issues.
  if (LIVE) setTimeout(function () { loadLens(false); }, 400);

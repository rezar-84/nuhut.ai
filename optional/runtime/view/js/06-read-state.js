  // ---------------------------------------------------------------- read state
  // Per item, the newest event date you have looked at. Kept in this browser only; a
  // first visit marks everything read, so only what changes afterwards shows as new.
  var SEEN_KEY = "nuhut-seen:" + (M.project || "project");
  var SEEN = null;
  function itemLatest(id) {
    var it = ITEMS[id], best = "";
    ((it && it.thread) || []).forEach(function (ev) {
      var d = ev.time || ev.date || "";
      if (d > best) best = d;
    });
    return best;
  }
  function loadSeen() {
    if (SEEN) return SEEN;
    var raw = null;
    try { raw = localStorage.getItem(SEEN_KEY); } catch (e) {}
    try { SEEN = raw ? JSON.parse(raw) : null; } catch (e) { SEEN = null; }
    if (!SEEN || typeof SEEN !== "object") {
      SEEN = {};
      (M.order || []).forEach(function (id) { SEEN[id] = itemLatest(id); });
      saveSeen();
    }
    return SEEN;
  }
  function saveSeen() {
    try { localStorage.setItem(SEEN_KEY, JSON.stringify(SEEN || {})); } catch (e) {}
  }
  function isUnread(id) {
    var latest = itemLatest(id);
    if (!latest) return false;
    var seen = loadSeen()[id];
    return seen === undefined ? true : latest > seen;
  }
  function markSeen(id) {
    if (!ITEMS[id]) return;
    loadSeen()[id] = itemLatest(id);
    saveSeen();
  }
  function markAllSeen() {
    loadSeen();
    (M.order || []).forEach(function (id) { SEEN[id] = itemLatest(id); });
    saveSeen();
    paintActivityBar();
  }
  function unreadIds() {
    return (M.order || []).filter(isUnread);
  }


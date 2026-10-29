  // ---------------------------------------------------------------- helpers
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (attrs[k] === null || attrs[k] === undefined) return;
      if (k === "text") n.textContent = attrs[k];
      else if (k === "cls") n.className = attrs[k];
      else if (k === "on") Object.keys(attrs.on).forEach(function (e) { n.addEventListener(e, attrs.on[e]); });
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }
  function go(route) { location.hash = "#/" + route; }
  function link(text, route, cls) {
    return el("a", { href: "#/" + route, text: text, cls: cls || "" });
  }
  function itemLink(id) {
    var it = ITEMS[id];
    var a = link(id, "item/" + id);
    if (it && it.title) a.title = it.title;
    return a;
  }
  function docRoute(n, line) {
    if (n === undefined || n === null || !DOCS[n]) return "docs";
    return "doc/" + encodeURIComponent(DOCS[n].path) + (line !== undefined ? "/" + line : "");
  }
  function colChip(col) {
    var c = el("span", { cls: "chip col " + (col || "Other"), text: col || "?" });
    c.style.setProperty("--chip-c", "var(--c-" + (col || "Other") + ")");
    return c;
  }
  function daysSince(s) {
    var m = /(\d{4})-(\d{2})-(\d{2})/.exec(s || "");
    if (!m) return null;
    return Math.floor((Date.now() - new Date(+m[1], m[2] - 1, +m[3]).getTime()) / 86400000);
  }
  function clip(s, n) { s = s || ""; return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  // "1 item", "3 items"; the irregular plural is passed in when there is one.
  function plural(n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); }
  // Seconds as a person reads them: 42s, 7m, 1h 12m.
  function fmtDur(sec) {
    if (sec === null || sec === undefined || sec === "" || isNaN(+sec)) return "";
    sec = +sec;
    if (sec < 90) return (sec < 10 ? Math.round(sec * 10) / 10 : Math.round(sec)) + "s";
    if (sec < 5400) return Math.round(sec / 60) + "m";
    var h = Math.floor(sec / 3600), m = Math.round((sec - h * 3600) / 60);
    return h + "h" + (m ? " " + m + "m" : "");
  }
  // The backlog's owner cell, whichever header the project used for it.
  function ownerOf(it) {
    var x = (it && it.extra) || {};
    return (it && it.owner) || x.Owner || x["Owner role"] || x["Owner Role"] || "";
  }
  function h(level, text) { return el("h" + level, { text: text }); }

  // Inline markdown: code, bold, links, and work item IDs. Text nodes only.
  function inline(text, baseDir) {
    var frag = document.createDocumentFragment();
    var parts = [/`([^`]+)`/, /\*\*([^*]+)\*\*/, /\[([^\]]+)\]\(([^)\s]+)\)/];
    var re = new RegExp(parts.map(function (p) { return p.source; }).join("|") +
      (ID_RE ? "|(" + ID_RE.source + ")" : ""), "g");
    var last = 0, m;
    text = text || "";
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (m[1] !== undefined) frag.appendChild(el("code", { text: m[1] }));
      else if (m[2] !== undefined) frag.appendChild(el("strong", null, [inline(m[2], baseDir)]));
      else if (m[3] !== undefined) frag.appendChild(mdLink(m[3], m[4], baseDir));
      else if (m[5] !== undefined) frag.appendChild(itemLink(m[5]));
      last = re.lastIndex;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    return frag;
  }
  function mdLink(label, href, baseDir) {
    if (/^https?:\/\//.test(href)) {
      return el("a", { href: href, text: label, target: "_blank", rel: "noopener noreferrer" });
    }
    var path = href.split("#")[0];
    if (path && /\.md$/.test(path) && baseDir !== undefined) {
      var parts = (baseDir ? baseDir.split("/") : []).concat(path.split("/")), out = [];
      parts.forEach(function (p) {
        if (p === "..") out.pop(); else if (p && p !== ".") out.push(p);
      });
      var n = DOC_BY_PATH[out.join("/")];
      if (n !== undefined) return link(label, docRoute(n));
    }
    return el("span", { text: label, title: href });
  }

  // Block markdown, enough for the kit's records: headings, tables, lists, quotes, fences.
  function renderMd(text, baseDir) {
    var box = el("div", { cls: "doc" }), lines = (text || "").split("\n"), i = 0, para = [];
    function flush() {
      if (para.length) box.appendChild(el("p", null, [inline(para.join(" "), baseDir)]));
      para = [];
    }
    if (lines[0] === "---") {
      var end = lines.indexOf("---", 1);
      if (end > 0) {
        var t = el("table");
        lines.slice(1, end).forEach(function (l) {
          var k = l.split(":");
          t.appendChild(el("tr", null, [el("th", { text: k[0] }), el("td", { text: k.slice(1).join(":").trim() })]));
        });
        box.appendChild(t);
        i = end + 1;
      }
    }
    while (i < lines.length) {
      var line = lines[i], m;
      if (/^```/.test(line)) {
        flush();
        var lang = line.slice(3).trim();
        var buf = [];
        i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
        var codeText = buf.join("\n");
        var codeBlock = el("div", { cls: "codeblock" });
        var codeHdr = el("div", { cls: "codeblock-hdr" }, [
          el("span", { cls: "codeblock-lang", text: lang || "code" }),
          el("button", {
            cls: "codeblock-copy",
            text: "Copy",
            title: "Copy code to clipboard",
            on: { click: (function (txt) {
              return function (e) {
                var btn = e.target;
                if (navigator.clipboard) {
                  navigator.clipboard.writeText(txt).then(function () {
                    btn.textContent = "Copied!";
                    setTimeout(function () { btn.textContent = "Copy"; }, 1500);
                  });
                }
              };
            })(codeText) }
          })
        ]);
        codeBlock.appendChild(codeHdr);
        codeBlock.appendChild(el("pre", { text: codeText }));
        box.appendChild(codeBlock);
        i++;
        continue;
      }
      if ((m = /^(#{1,4})\s+(.*)$/.exec(line))) {
        flush();
        var lineNum = i;
        var hd = el("h" + m[1].length, { id: "L" + lineNum, cls: "doc-heading" }, [
          inline(m[2], baseDir),
          el("a", {
            cls: "heading-anchor",
            href: "#L" + lineNum,
            text: "#",
            title: "Copy link to section",
            on: { click: function (e) {
              e.preventDefault();
              var baseRoute = (location.hash || "").split("/").slice(0, 2).join("/");
              var targetUrl = location.origin + location.pathname + baseRoute + "/" + lineNum;
              if (navigator.clipboard) navigator.clipboard.writeText(targetUrl);
              history.replaceState(null, "", baseRoute + "/" + lineNum);
            } }
          })
        ]);
        box.appendChild(hd);
        i++;
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line)) {
        flush();
        var wrap = el("div", { cls: "wrap" }), table = el("table"), first = true;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          var cells = lines[i].trim().slice(1, -1).split(/(?<!\\)\|/);
          if (!cells.every(function (c) { return /^\s*:?-+:?\s*$/.test(c); })) {
            var tr = el("tr");
            cells.forEach(function (c) {
              tr.appendChild(el(first ? "th" : "td", null, [inline(c.trim().replace(/\\\|/g, "|"), baseDir)]));
            });
            table.appendChild(tr);
            first = false;
          }
          i++;
        }
        wrap.appendChild(table);
        box.appendChild(wrap);
        continue;
      }
      if ((m = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(line))) {
        flush();
        var ul = el("ul");
        while (i < lines.length && (m = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(lines[i]))) {
          var li = el("li", null, [inline(m[3], baseDir)]);
          li.style.marginLeft = Math.min(m[1].length, 8) * 8 + "px";
          ul.appendChild(li);
          i++;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^(\s*)([-*]|\d+\.)\s+/.test(lines[i])) {
            li.appendChild(document.createTextNode(" "));
            li.appendChild(inline(lines[i].trim(), baseDir));
            i++;
          }
        }
        box.appendChild(ul);
        continue;
      }
      if (/^>/.test(line)) {
        flush();
        var q = [];
        while (i < lines.length && /^>/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, ""));
        box.appendChild(el("blockquote", null, [inline(q.join(" "), baseDir)]));
        continue;
      }
      if (/^\s*$/.test(line) || /^---+\s*$/.test(line)) { flush(); i++; continue; }
      para.push(line.trim());
      i++;
    }
    flush();
    return box;
  }


#!/usr/bin/env python3
"""The slop filter's mechanical half: find the phrasings that make prose read as
machine-written, by line, with a fix for each.

Standard library only. `sdlc.py slop` drives it; the judgment half is the
sdlc-slop-filter skill and the /sdlc-slop command.

The rule set is adapted from Wikipedia's "Signs of AI writing" (CC BY-SA 4.0,
https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), read alongside the
humanizer and stop-slop skills (both MIT). A match is a place to look, never proof of
who wrote the text: every pattern here also turns up in human writing.

Three strengths:
  strong    one sighting is worth an edit
  moderate  fine once, a tell in a cluster
  weak      counted per file, reported only when dense
"""

import os
import re
import subprocess

PROSE_EXT = (".md", ".mdx", ".markdown", ".txt", ".rst", ".html", ".htm")
SKIP_DIRS = {".git", "node_modules", ".ai-sdlc", "dist", "build", ".next", "vendor", "__pycache__"}
MODES = ("off", "on", "strict")
# Moderate tells a file may carry before strict fails it: this many, plus one per so many words.
MODERATE_FREE = 2
MODERATE_PER_WORDS = 400

I = re.I

# (id, strength, group, pattern, fix)
RULES = (
    # Leftovers from a chat or a draft
    ("chat-residue", "strong", "leftovers",
     r"\b(i hope this helps|hope this helps|certainly!|of course!|you'?re absolutely right|"
     r"great question|would you like me to|let me know if (you|there)|is there anything else|"
     r"feel free to (reach out|ask|contact)|happy to help)",
     "delete it: the reader did not ask the writer anything"),
    ("ai-disclaimer", "strong", "leftovers",
     r"\b(as an ai( language)? model|as a large language model|as of my (last|latest) "
     r"(knowledge )?(update|training)|my (knowledge|training) cut-?off)",
     "delete it and check the paragraph around it for guesses"),
    ("placeholder", "strong", "leftovers",
     r"(\[(?i:your|insert|describe|add|enter|company|client|name|year|date|url|link|placeholder)\b[^\]\n]{0,60}\](?!\()"
     r"|\bINSERT_[A-Z_]+\b|\bPASTE_[A-Z_]+_HERE\b|\b20\d\d-XX-XX\b|\b(?i:lorem ipsum)\b)",
     "fill it in from a real source, or cut the sentence"),
    ("tool-leak", "strong", "leftovers",
     r"(oaicite|contentReference\[|turn\d+(search|view)\d+|utm_source=(chatgpt\.com|openai|copilot\.com)|"
     r"referrer=grok\.com)",
     "remove the chatbot's markup or tracking parameter and verify the link"),
    ("source-hedge", "strong", "leftovers",
     r"\b(while (specific|exact|precise) (details|information|figures) (are|is|remain) "
     r"(limited|scarce|unavailable)|based on (the )?available information|"
     r"(is|are) not (widely|publicly) (available|documented|disclosed)|maintains a low profile)",
     "say what is known and stop; do not narrate the search"),

    # Staging a point where stating it would do
    ("not-x-but-y", "strong", "staging",
     r"\b(not (just|only|merely|simply) [^.!?\n]{1,70}?\b(but|it'?s|it is|they'?re|they are)\b|"
     r"(it|this|that)(('|\u2019)s| is) not (just |about |merely |simply )?[^.!?\n]{1,60}?[,;:\u2014\u2013] ?"
     r"(it|this|that)(('|\u2019)s| is)\b|"
     r"\bisn'?t (just |merely |simply )?[^.!?\n]{1,50}?[,;\u2014\u2013] ?(it|this|that)(('|\u2019)s| is)\b)",
     "state the second half on its own; nobody claimed the first"),
    ("signpost", "strong", "staging",
     r"\b(it(('|\u2019)s| is) (important|worth|crucial|essential) (to note|noting|to remember|"
     r"mentioning|to mention|to understand)|let(('|\u2019)s| us) (dive|delve|explore|unpack|break "
     r"(it|this) down)|here(('|\u2019)s| is) the (thing|kicker|truth|catch)|the (truth|reality) is,?|"
     r"at the end of the day|when it comes to|that being said|with that in mind|"
     r"in (conclusion|summary),|in today(('|\u2019)s) [a-z-]+ (world|landscape|age|era|market)|"
     r"in the (realm|world) of)",
     "cut the run-up and start with the point"),
    ("sales-stock", "strong", "staging",
     r"\b(unlock (the|your|its)( full| true)? (potential|power)|game[- ]changer|"
     r"take [^.!?\n]{1,30} to the next level|look no further|whether you(('|\u2019)re| are) "
     r"[^.!?\n]{1,40}\bor\b|elevate your|seamless(ly)? (integrat|experience|blend)|"
     r"more than just a|a world of (possibilities|difference)|"
     r"harness(es|ed|ing)? the (power|potential))",
     "name what the product does and for whom, with a number if there is one"),

    # Inflation and borrowed authority
    ("significance", "strong", "inflation",
     r"\b((stands|serves) as a (testament|reminder|beacon|symbol|cornerstone)|"
     r"(is |as )?a testament to|plays? an? (crucial|pivotal|vital|key|significant|central) role|"
     r"(pivotal|defining|watershed) moment|key turning point|(ever-)?evolving landscape|"
     r"ever-(changing|evolving)|indelible mark|deeply rooted|setting the stage for|"
     r"rich (tapestry|cultural heritage|heritage|history of)|marks? a (significant )?shift|"
     r"underscor(es|ing) (its|the|their) (importance|significance))",
     "say the plain fact; if it matters, the fact shows it"),
    ("vague-attribution", "strong", "inflation",
     r"\b(experts (argue|say|agree|believe|suggest)|industry (reports|experts|observers|analysts)|"
     r"observers (have|note)|(studies|research) (show|shows|have shown|has shown|suggest|suggests)|"
     r"some critics argue|many (people )?(believe|argue)|widely (regarded|considered|recognized)|"
     r"it is (widely|generally) (believed|accepted))",
     "name the source, or drop the claim"),
    ("challenges-formula", "strong", "inflation",
     r"\b(despite (its|these|their|the) [^.!?\n]{0,40}challenges|faces (several|many|numerous) "
     r"challenges|future outlook|challenges and (legacy|opportunities|future))",
     "name the specific problem and what is being done about it"),
    ("ing-rider", "moderate", "inflation",
     r", (highlighting|underscoring|emphasizing|reflecting|symbolizing|showcasing|ensuring|"
     r"fostering|cementing|solidifying|demonstrating|illustrating|contributing to|paving the way)\b",
     "end the sentence at the comma, or give the rider its own sentence with evidence"),
    ("copula-dodge", "moderate", "inflation",
     r"\b(serves as|stands as|functions as|acts as) (a|an|the)\b|\bboasts (a|an|over|more)\b",
     "write is, are or has"),
    ("stock-word", "moderate", "inflation",
     r"\b(delv(e|es|ed|ing)|tapestry|testament|pivotal|meticulous(ly)?|intricate|intricacies|"
     r"interplay|multifaceted|underscor(e|es|ed|ing)|showcas(e|es|ed|ing)|bolster(s|ed|ing)?|"
     r"garner(s|ed|ing)?|foster(s|ed|ing)?|vibrant|groundbreaking|renowned|nestled|"
     r"transformative|holistic|myriad|plethora|leverag(e|es|ed|ing)|seamless(ly)?|"
     r"cutting-edge|empower(s|ed|ing)?|elevat(e|es|ed|ing)|"
     r"valuable insights?|diverse array|resonat(e|es|ed|ing) with|align(s|ed|ing)? with|"
     r"crucial|enduring|profound(ly)?|realm)\b",
     "use the ordinary word, or the specific fact the word stands in for"),
    ("additionally", "moderate", "inflation",
     r"(?:^|[.!?]\s+)(Additionally|Moreover|Furthermore),",
     "drop the connective; if the sentences belong together the order shows it"),

    # Formatting by rule
    ("bold-label-list", "weak", "format",
     r"^\s*(?:[-*+]|\d+[.)])\s+\*\*[^*\n]{1,60}(?::\*\*|\*\*\s*[:\u2014\u2013-])",
     "write the item as a sentence; keep bold labels only for a real definition list"),
    ("emoji-heading", "moderate", "format",
     r"^\s*(?:#{1,6}\s+|[-*+]\s+)[\U0001F300-\U0001FAFF\u2600-\u27bf]",
     "remove the emoji from the heading or bullet"),
    ("vague-link", "weak", "inflation",
     r"\b(in (connection|association) with|(is|was|are|were|being) associated with)\b",
     "say what the relationship is"),
    ("rather-than", "weak", "staging",
     r"\brather than\b",
     "say what it is; mention the alternative only if someone holds it"),
    ("triad", "weak", "rhythm",
     r"\b[a-z][\w'-]*(?: [\w'-]+)?, [a-z][\w'-]*(?: [\w'-]+)?,? and [a-z][\w'-]*\b",
     "list as many items as there are; cut the third if it was added for rhythm"),
    ("em-dash", "weak", "rhythm",
     r"\u2014",
     "choose the relationship: a period, a comma, a colon or parentheses"),
    ("curly-quote", "weak", "format",
     r"[\u201c\u201d]",
     "use straight quotes unless the house style sets curly ones"),
    ("title-case-heading", "weak", "format",
     r"^#{1,6}\s+(?:[A-Z][\w'-]*\s+){2,}[A-Z][\w'-]*\s*$",
     "use sentence case unless the house style sets title case"),
)

# Rules whose capitals carry meaning; every other rule ignores case.
CASED = ("additionally", "title-case-heading", "placeholder")
COMPILED = tuple((rid, tier, group, re.compile(pat, re.M if rid in CASED else I | re.M), fix)
                 for rid, tier, group, pat, fix in RULES)

# Weak tells are reported once per file, when there are more than this many per 100 words.
WEAK_DENSITY = {"em-dash": 1.0, "triad": 1.2, "rather-than": 0.6, "vague-link": 0.5,
                "curly-quote": 2.0, "title-case-heading": 0.0,
                "bold-label-list": 0.0}
WEAK_MIN = {"em-dash": 4, "triad": 4, "rather-than": 3, "vague-link": 2, "curly-quote": 6,
            "title-case-heading": 3, "bold-label-list": 5}

GROUPS = (("leftovers", "Leftovers from a chat or a draft"),
          ("staging", "Staging a point where stating it would do"),
          ("inflation", "Inflation and borrowed authority"),
          ("rhythm", "Rhythm by rule"),
          ("format", "Formatting by rule"))


def mode(project, labelled):
    """off, on or strict, from the charter's Slop filter row. A row still showing every
    option is unanswered, which is off."""
    cell = (labelled(project.charter or "", "Slop filter") or "").lower()
    if "\u00b7" in cell.split("_(")[0]:
        return "off"
    found = re.search(r"`(off|on|strict)`", cell)
    return found.group(1) if found else "off"


def _blank(match):
    """The matched text with everything but its newlines turned to spaces, so line and
    column numbers still point at the original."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip(text):
    """Prose only: front matter, code, comments, link targets and bare URLs blanked out."""
    text = re.sub(r"\A---\n.*?\n---\n", _blank, text, flags=re.S)
    text = re.sub(r"^(```|~~~).*?^\1[^\n]*$", _blank, text, flags=re.S | re.M)
    text = re.sub(r"<!--.*?-->", lambda m: m.group(0) if "slop-" in m.group(0) else _blank(m),
                  text, flags=re.S)
    text = re.sub(r"<(script|style)\b.*?</\1>", _blank, text, flags=re.S | I)
    text = re.sub(r"`[^`\n]+`", _blank, text)
    text = re.sub(r"\]\([^)\n]*\)", lambda m: "]" + " " * (len(m.group(0)) - 1), text)
    # A tracking parameter is itself a finding, so a bare URL keeps its query string.
    text = re.sub(r"https?://[^\s)>\]?]+", _blank, text)
    return text


def words(text):
    return len(re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", text))


def scan_text(text, name="<text>"):
    """(findings, word count). A finding is a dict: file, line, rule, strength, group,
    text, fix. Weak tells come back as one finding per rule per file, only when dense."""
    if re.search(r"^<!--\s*slop-filter:\s*off\s*-->", text[:2000], re.M):
        return [], 0
    prose = strip(text)
    lines = prose.split("\n")
    skipped = {i for i, line in enumerate(lines, 1) if "slop-ok" in line}
    # A quoted line is somebody else's sentence.
    skipped |= {i for i, line in enumerate(lines, 1) if line.lstrip().startswith(">")}
    count = words("\n".join(line for i, line in enumerate(lines, 1) if i not in skipped))
    findings, weak, moderate, strong_spans = [], {}, [], []
    for rid, tier, group, rx, fix in COMPILED:
        for m in rx.finditer(prose):
            start = m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))
            line = prose.count("\n", 0, start) + 1
            if line in skipped:
                continue
            hit = {"file": name, "line": line, "rule": rid, "strength": tier, "group": group,
                   "text": " ".join(m.group(0).split())[:70], "fix": fix}
            if tier == "weak":
                weak.setdefault(rid, []).append(hit)
            elif tier == "strong":
                strong_spans.append((start, m.end()))
                findings.append(hit)
            else:
                moderate.append((start, m.end(), hit))
    # A phrase already reported as a strong tell is not counted again word by word.
    findings.extend(hit for a, b, hit in moderate
                    if not any(a < e and s < b for s, e in strong_spans))
    for rid, hits in weak.items():
        per_hundred = len(hits) * 100.0 / max(count, 1)
        if len(hits) >= WEAK_MIN[rid] and per_hundred > WEAK_DENSITY[rid]:
            first = dict(hits[0])
            first["text"] = "%d in %d words (first: %s)" % (len(hits), count, first["text"])
            findings.append(first)
    findings.sort(key=lambda f: (f["line"], f["rule"]))
    return findings, count


def verdict(findings, count):
    """(fails, strong, moderate, weak, budget). Strict fails a text on any strong tell, or
    on more moderate tells than its length allows. Weak tells never fail a text alone."""
    strong = sum(1 for f in findings if f["strength"] == "strong")
    moderate = sum(1 for f in findings if f["strength"] == "moderate")
    weak = sum(1 for f in findings if f["strength"] == "weak")
    budget = MODERATE_FREE + count // MODERATE_PER_WORDS
    return bool(strong or moderate > budget), strong, moderate, weak, budget


def collect(paths, root):
    """Prose files under the given files and directories, in a stable order."""
    out = []
    for given in paths:
        full = given if os.path.isabs(given) else os.path.join(root, given)
        if os.path.isdir(full):
            for base, dirs, files in os.walk(full):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                out.extend(os.path.join(base, f) for f in sorted(files)
                           if f.lower().endswith(PROSE_EXT))
        else:
            out.append(full)
    return out


def changed_prose(root):
    """Prose files changed against HEAD or not yet tracked. None when git cannot say."""
    names = []
    for args in (["diff", "--name-only", "--diff-filter=d", "HEAD"],
                 ["ls-files", "--others", "--exclude-standard"]):
        try:
            proc = subprocess.run(["git", "-C", root] + args, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        except (OSError, ValueError):
            return None
        if proc.returncode:
            if args[0] == "diff":
                continue          # no commit yet: untracked files are the whole change
            return None
        names.extend(proc.stdout.decode("utf-8", "replace").splitlines())
    seen, out = set(), []
    for name in names:
        if name.lower().endswith(PROSE_EXT) and name not in seen \
                and not name.startswith(".ai-sdlc/"):
            seen.add(name)
            out.append(os.path.join(root, name))
    return out


def scan_paths(files, root):
    """[(relative name, findings, word count)] and the paths that could not be read."""
    results, unread = [], []
    for path in files:
        rel = os.path.relpath(path, root)
        rel = path if rel.startswith("..") else rel
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except (IOError, OSError):
            unread.append(rel)
            continue
        found, count = scan_text(text, rel)
        results.append((rel, found, count))
    return results, unread


def report(results, strict):
    """Lines for the terminal, and whether any file fails under strict."""
    out, failed, total = [], 0, 0
    for rel, found, count in results:
        fails, strong, moderate, weak, budget = verdict(found, count)
        total += len(found)
        if not found:
            continue
        for f in found:
            out.append("%s:%d  %-8s %-18s \"%s\"" % (rel, f["line"], f["strength"], f["rule"], f["text"]))
            out.append("    fix: %s" % f["fix"])
        state = "FAIL" if fails else "ok"
        if fails:
            failed += 1
        out.append("%s: %d strong, %d moderate (budget %d), %d weak in %d words%s" % (
            rel, strong, moderate, budget, weak, count,
            "  [%s]" % state if strict else ""))
        out.append("")
    clean = sum(1 for _, found, _ in results if not found)
    summary = "slop: %d finding(s) in %d file(s); %d clean" % (total, len(results) - clean, clean)
    if strict:
        summary += "; %d fail strict" % failed
    out.append(summary)
    return out, failed


def guide():
    """The rule catalogue, for a session that has no skill installed."""
    out = ["Slop filter rules. A match is a place to look, never proof of who wrote the text.",
           "strong: edit on one sighting.  moderate: a tell in a cluster.  weak: only when dense.",
           ""]
    for key, title in GROUPS:
        out.append(title)
        for rid, tier, group, _, fix in RULES:
            if group == key:
                out.append("  %-20s %-9s %s" % (rid, tier, fix))
        out.append("")
    out.append("Not tells on their own: correct grammar, a formal or plain register, a single "
               "transition word, one stock word, one dash.")
    out.append("Skipped: code blocks, inline code, link targets, quoted lines (>), a line "
               "containing slop-ok, a file whose head says slop-filter: off.")
    out.append("Strict fails a file on any strong tell, or on more than %d moderate tells plus "
               "one per %d words." % (MODERATE_FREE, MODERATE_PER_WORDS))
    return out

"""Webhook notifications (NUHT-034): tell a person when an item waits on them.

The charter's optional **Notify webhook** row names an environment variable, never the
URL: `| **Notify webhook** | `NUHUT_WEBHOOK_URL` |`. The row is read from the default
branch (`trusted_text`, ADR 0003 decision 8), so a branch that adds or changes it has no
effect until it merges. A blank row, `off`, or no row means off. `--ids-only` in the cell
drops item titles from every payload.

Events: `parked` (an item set to Parked, waiting on a person), `review-blocked` (finish
refused because a review finding is escalated with no decision), `approval-needed` (finish
parked a Tier 1 item, or Tier 2 under Strict tier rules, for the merge approval), and
`test` (`sdlc.py notify --test`). The payload holds IDs, the title, tier and status;
never a diff, a reason, a person's name or the URL. A send goes through net.py (https,
5 s timeout, the response ignored); a failure prints one warning that names only the
scheme and host, and never blocks the command that triggered it.

Zero third-party dependencies (Python 3.8+ stdlib).
NOTE: Must never contain two literal opening curly braces in a row.
"""

import datetime
import os
import re
import sys

LABEL = "Notify webhook"
ENV_RE = re.compile(r"^NUHUT_[A-Z0-9_]{1,40}$")
EVENTS = ("test", "parked", "review-blocked", "approval-needed")
OFF_WORDS = ("off", "none", "no", "-", "")


def parse_row(cell):
    """(env name or None, ids_only, problem or None) from a Notify webhook cell."""
    if cell is None:
        return None, False, None
    text = re.sub(r"_\([^)]*\)_", "", str(cell)).strip()
    ids_only = bool(re.search(r"(?i)(?:^|\s|·)-{0,2}ids-only\b", text))
    text = re.sub(r"(?i)(?:^|\s|·)-{0,2}ids-only\b", " ", text)
    words = [w for w in re.split(r"[\s·,]+", text.replace("`", " ").replace("*", " ")) if w]
    if not words or (len(words) == 1 and words[0].lower() in OFF_WORDS):
        return None, ids_only, None
    if len(words) > 1:
        return None, ids_only, ("the Notify webhook row names more than one thing (%s); "
                                "it takes one variable name" % ", ".join(words[:3]))
    name = words[0]
    if not ENV_RE.match(name):
        return None, ids_only, ("the Notify webhook row names %r: the variable must match "
                                "^NUHUT_[A-Z0-9_]{1,40}$" % name[:60])
    return name, ids_only, None


def config(rt, project):
    """{"env", "ids_only", "problem", "source"} for the row as it stands on the default
    branch."""
    try:
        text, source = rt.trusted_text(project, project.charter_path)
    except Exception:  # noqa: BLE001 -- an unreadable charter is "off", never a crash
        text, source = "", "working-tree"
    env, ids_only, problem = parse_row(rt.labelled(text or "", LABEL))
    return {"env": env, "ids_only": ids_only, "problem": problem, "source": source}


def payload(rt, project, event, item="", title="", tier="", status="", ids_only=False):
    data = {
        "schema": 1,
        "source": "nuhut",
        "event": event,
        "project": getattr(project, "prefix", "") or "",
        "item": item or "",
        "tier": str(tier or ""),
        "status": status or "",
        "sent_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if not ids_only:
        data["title"] = title or ""
    return data


def send(rt, project, event, item="", title="", tier="", status="", ids_only=None,
         quiet_off=True, warn=None):
    """Send one event. Returns (state, message). state is one of off, invalid, unset,
    sent, failed. Never raises. With quiet_off, off and unset print nothing (a machine
    without the secret is normal); a refused row or a failed send prints one warning."""
    warn = warn or (lambda m: sys.stderr.write("notify: %s\n" % m))
    try:
        cfg = config(rt, project)
        if cfg["problem"]:
            warn(cfg["problem"] + "; nothing sent")
            return "invalid", cfg["problem"]
        if not cfg["env"]:
            msg = ("off: the charter has no Notify webhook row on the default branch "
                   "(turn it on with `sdlc.py config --notify-webhook NUHUT_WEBHOOK_URL`)")
            return "off", msg
        url = os.environ.get(cfg["env"], "").strip()
        if not url:
            return "unset", "%s is not set in this environment; nothing sent" % cfg["env"]
        net = rt.runtime_module("net")
        body = payload(rt, project, event, item, title, tier, status,
                       cfg["ids_only"] if ids_only is None else (ids_only or cfg["ids_only"]))
        try:
            net.post_json(url, body)
        except ValueError as exc:
            msg = "%s webhook not sent: %s (continuing)" % (event, exc)
            warn(msg)
            return "failed", msg
        return "sent", "sent %s to %s" % (event, net.origin(url))
    except Exception as exc:  # noqa: BLE001 -- a notification never blocks the command
        msg = "%s webhook not sent: %s (continuing)" % (event, exc.__class__.__name__)
        warn(msg)
        return "failed", msg


def status_lines(rt, project):
    """What `sdlc.py notify` prints: the row, the variable name, whether it is set."""
    cfg = config(rt, project)
    lines = []
    if cfg["problem"]:
        lines.append("Notify webhook: refused (%s)" % cfg["problem"])
    elif not cfg["env"]:
        lines.append("Notify webhook: off (no row on %s). Turn it on with "
                     "`sdlc.py config --notify-webhook NUHUT_WEBHOOK_URL`, merge it, and set "
                     "that variable where the commands run." % cfg["source"])
    else:
        url = os.environ.get(cfg["env"], "").strip()
        where = ""
        if url:
            where = " (%s)" % rt.runtime_module("net").origin(url)
        lines.append("Notify webhook: on, URL from $%s, read from %s" % (cfg["env"], cfg["source"]))
        lines.append("  %s is %s%s" % (cfg["env"], "set" if url else "not set here", where))
        lines.append("  titles: %s" % ("dropped (--ids-only)" if cfg["ids_only"] else "included"))
    lines.append("events: parked, review-blocked, approval-needed; `notify --test` sends a test")
    return lines

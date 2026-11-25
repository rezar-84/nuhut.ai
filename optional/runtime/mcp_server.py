"""Nuhut MCP server: the kit's records as Model Context Protocol tools, over stdio.

    python3 .ai-sdlc/bin/sdlc.py mcp [--allow-verify]

JSON-RPC 2.0, one message per line (the MCP stdio transport). Standard library only.

Every tool is read-only except `verify`, which runs the charter's check commands and writes
evidence, and is offered only when the server starts with --allow-verify. Nothing that
changes a record's status (finish, waivers, releasing claims, extensions) is exposed.
Each tool runs sdlc.py as a subprocess with a fixed argument list and no shell; a work item
id is checked against a strict pattern before it reaches that list. Tool output is capped
at 64 KB and stripped of control characters. Only JSON-RPC goes to stdout; every
diagnostic goes to stderr.
"""

import json
import os
import re
import subprocess
import sys

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_NAME = "nuhut"
MAX_OUTPUT = 64 * 1024            # bytes of tool text returned to the client
MAX_LINE = 1024 * 1024            # bytes of one incoming JSON-RPC line
ITEM_ID = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$")
STATUS_WORD = re.compile(r"^[A-Za-z][A-Za-z ]{0,30}$")
TIER_LIST = re.compile(r"^[123](,[123]){0,2}$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-_]")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
TIMEOUT = 120
VERIFY_TIMEOUT = 3600

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = (
    -32700, -32600, -32601, -32602, -32603)

ID_PROP = {"type": "string", "pattern": ITEM_ID.pattern,
           "description": "work item ID, e.g. ACME-12"}


def schema(properties=None, required=()):
    """An input schema. Built by a function so no literal nests two closing braces: the
    installer treats doubled braces in runtime files as placeholders."""
    out = dict(type="object", additionalProperties=False, properties=properties or dict())
    if required:
        out["required"] = list(required)
    return out


def tool(name, readonly, description, properties=None, required=()):
    return dict(name=name, readonly=readonly, description=description,
                inputSchema=schema(properties, required))


STRING = dict(type="string")
ID_ONLY = dict(id=ID_PROP)

TOOLS = [
    tool("item_list", True,
         "List the work items (id, title, tier, status, owner, depends, touch) as JSON. "
         "Optional filters: status (e.g. Ready) and tier (e.g. 1,2).",
         dict(status=STRING, tier=STRING)),
    tool("item_show", True, "One work item as JSON.", ID_ONLY, ["id"]),
    tool("doctor", True,
         "The doctor's findings on the SDLC records as JSON: stale rows, unproven claims, "
         "blank charter commands, each with how to fix it and who can."),
    tool("finish_status", True,
         "What a work item still owes before it can be finished (evidence, reviews, "
         "worklog), from `finish --dry-run`. Writes nothing.", ID_ONLY, ["id"]),
    tool("status", True,
         "Where the project stands: item counts by status, open items, active claims, and "
         "the checkout against its remote and default branch (as of the last fetch)."),
    tool("verify", False,
         "Run the charter's check commands for a work item and record the evidence "
         "(`verify --item`). Returns the evidence summary. Writes evidence files under "
         ".ai-sdlc/evidence/.", ID_ONLY, ["id"]),
]


class ToolError(Exception):
    """A tool ran and failed, or refused its arguments: reported as isError, not a crash."""


class ParamsError(Exception):
    """The request names something that does not exist here (an unknown tool)."""


def log(message):
    sys.stderr.write("nuhut-mcp: %s\n" % message)
    sys.stderr.flush()


def clean_output(text, limit=MAX_OUTPUT):
    """Strip escape sequences and control characters (tab and newline stay), then cut to
    `limit` bytes of UTF-8 with a note saying how much was left out."""
    text = CONTROL.sub("", ANSI.sub("", text or ""))
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    note = "\n[output truncated: %d of %d bytes shown]" % (limit - 64, len(raw))
    return raw[:limit - 64].decode("utf-8", "ignore") + note


def item_id(arguments):
    value = arguments.get("id")
    if not isinstance(value, str) or len(value) > 40 or not ITEM_ID.match(value):
        raise ToolError("id must match %s, e.g. ACME-12" % ITEM_ID.pattern)
    return value


class Server(object):
    def __init__(self, root, sdlc_path, allow_verify=False, version=""):
        self.root = root
        self.sdlc = sdlc_path
        self.allow_verify = allow_verify
        self.version = version or "0"
        self.tools = [t for t in TOOLS if t["readonly"] or (t["name"] == "verify" and allow_verify)]

    # ------------------------------------------------------------- running sdlc.py
    def run(self, args, timeout=TIMEOUT):
        """(exit code, stdout, stderr) of sdlc.py with a fixed argument list, no shell."""
        cmd = [sys.executable, self.sdlc, "--root", self.root] + list(args)
        env = dict(os.environ, NO_COLOR="1", PYTHONIOENCODING="utf-8")
        try:
            p = subprocess.Popen(cmd, cwd=self.root, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        except OSError as exc:
            raise ToolError("could not start sdlc.py: %s" % exc)
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            raise ToolError("sdlc.py %s did not finish within %d seconds" % (args[0], timeout))
        return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    def json_of(self, args, ok=(0,), timeout=TIMEOUT):
        code, out, err = self.run(args, timeout)
        if code not in ok:
            raise ToolError((err or out).strip() or "sdlc.py %s exited %d" % (args[0], code))
        try:
            return json.loads(out)
        except ValueError:
            raise ToolError("sdlc.py %s did not print JSON: %s" % (args[0], (err or out).strip()[:400]))

    # ------------------------------------------------------------- the tools
    def tool_item_list(self, a):
        args = ["item", "list", "--json"]
        status, tier = a.get("status"), a.get("tier")
        if status not in (None, ""):
            if not isinstance(status, str) or not STATUS_WORD.match(status):
                raise ToolError("status must be a status word, e.g. Ready")
            args.append("--status=" + status)
        if tier not in (None, ""):
            if not isinstance(tier, str) or not TIER_LIST.match(tier):
                raise ToolError("tier must be 1, 2, 3 or a comma-separated list of them")
            args.append("--tier=" + tier)
        return self.json_of(args)

    def tool_item_show(self, a):
        return self.json_of(["item", "show", item_id(a), "--json"])

    def tool_doctor(self, a):
        # --no-cache: the doctor otherwise refreshes .ai-sdlc/cache/doctor.json.
        return self.json_of(["doctor", "--json", "--no-cache"])

    def tool_finish_status(self, a):
        iid = item_id(a)
        code, out, err = self.run(["finish", iid, "--dry-run", "--json"])
        try:
            return json.loads(out)
        except ValueError:
            # An item with no commit or not in the backlog answers in plain lines.
            text = (out + err).strip()
            if code == 2 or not text:
                raise ToolError(text or "finish --dry-run exited %d" % code)
            return {"item": iid, "exit_code": code, "finished": False, "lines": text.splitlines()}

    def tool_status(self, a):
        items = self.json_of(["item", "list", "--json"])
        counts = {}
        for it in items if isinstance(items, list) else []:
            counts[it.get("status") or "?"] = counts.get(it.get("status") or "?", 0) + 1
        result = {"counts": counts,
                  "open": [{"id": it.get("id"), "status": it.get("status"), "title": it.get("title")}
                           for it in items if it.get("status") not in ("Done", "Dropped")][:200]}
        for key, args in (("claims", ["claims", "--json"]), ("sync", ["sync", "--json"])):
            try:
                result[key] = self.json_of(args, ok=(0, 1))
            except ToolError as exc:
                result[key] = {"unavailable": str(exc)[:400]}
        return result

    def tool_verify(self, a):
        iid = item_id(a)
        code, out, err = self.run(["verify", "--item", iid, "--json"], timeout=VERIFY_TIMEOUT)
        try:
            return dict(json.loads(out), exit_code=code) if out.strip().startswith("{") \
                else {"exit_code": code, "output": (out + err).strip()}
        except ValueError:
            return {"exit_code": code, "output": (out + err).strip()}

    # ------------------------------------------------------------- JSON-RPC
    def call_tool(self, params):
        name = params.get("name")
        if not any(t["name"] == name for t in self.tools):
            raise ParamsError("unknown tool: %s" % str(name)[:60])
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ToolError("arguments must be an object")
        try:
            value = getattr(self, "tool_" + name)(arguments)
            text, failed = json.dumps(value, indent=2, ensure_ascii=False), False
        except ToolError as exc:
            text, failed = str(exc), True
        except Exception as exc:          # a tool bug must not end the session
            log("tool %s failed: %r" % (name, exc))
            text, failed = "internal error in %s: %s" % (name, exc.__class__.__name__), True
        return {"content": [{"type": "text", "text": clean_output(text)}], "isError": failed}

    def handle(self, msg):
        """The response for one parsed message, or None for a notification."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or \
                not isinstance(msg.get("method"), str):
            rid = msg.get("id") if isinstance(msg, dict) else None
            return error(rid if isinstance(rid, (str, int)) else None, INVALID_REQUEST,
                         "not a JSON-RPC 2.0 request")
        if "id" not in msg:
            return None                      # notifications/initialized, cancelled, ...
        rid, method = msg["id"], msg["method"]
        if not isinstance(rid, (str, int)) or isinstance(rid, bool):
            return error(None, INVALID_REQUEST, "id must be a string or a number")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            return error(rid, INVALID_PARAMS, "params must be an object")
        if method == "initialize":
            asked = params.get("protocolVersion")
            return result(rid, {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": dict(tools=dict(listChanged=False)),
                "serverInfo": {"name": SERVER_NAME, "version": self.version},
                "instructions": "Nuhut SDLC records for this project. Tools are read-only"
                                + ("; verify runs the charter's checks and records evidence."
                                   if self.allow_verify else "."),
            })
        if method == "ping":
            return result(rid, {})
        if method == "tools/list":
            return result(rid, {"tools": [dict((k, v) for k, v in t.items() if k != "readonly")
                                          for t in self.tools]})
        if method == "tools/call":
            try:
                return result(rid, self.call_tool(params))
            except ParamsError as exc:
                return error(rid, INVALID_PARAMS, str(exc))
            except ToolError as exc:
                return result(rid, {"content": [{"type": "text", "text": clean_output(str(exc))}],
                                    "isError": True})
        return error(rid, METHOD_NOT_FOUND, "method not found: %s" % method[:60])


def result(rid, value):
    return {"jsonrpc": "2.0", "id": rid, "result": value}


def error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": dict(code=code, message=message)}


def read_line(stream):
    """One line as bytes, or None at end of input. An overlong line is drained and returned
    as b"" so it answers as a parse error instead of filling memory."""
    line = stream.readline(MAX_LINE + 1)
    if not line:
        return None
    if len(line) > MAX_LINE and not line.endswith(b"\n"):
        while True:
            rest = stream.readline(MAX_LINE)
            if not rest or rest.endswith(b"\n"):
                break
        return b""
    return line


def serve(root, sdlc_path, allow_verify=False, version="", stdin=None, stdout=None):
    """Answer JSON-RPC lines from stdin until it closes. Returns the exit code."""
    server = Server(root, sdlc_path, allow_verify, version)
    stdin = stdin or sys.stdin.buffer
    out = stdout or sys.stdout.buffer
    # Anything printed by accident goes to stderr, never into the protocol stream.
    saved, sys.stdout = sys.stdout, sys.stderr
    log("serving %s (verify %s)" % (root, "allowed" if allow_verify else "off"))
    try:
        while True:
            line = read_line(stdin)
            if line is None:
                return 0
            if not line.strip():
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                response = error(None, PARSE_ERROR, "parse error")
            else:
                if isinstance(msg, list):
                    response = error(None, INVALID_REQUEST, "batches are not supported")
                else:
                    try:
                        response = server.handle(msg)
                    except Exception as exc:
                        log("internal error: %r" % (exc,))
                        rid = msg.get("id") if isinstance(msg, dict) else None
                        response = error(rid if isinstance(rid, (str, int)) else None,
                                         INTERNAL, "internal error")
            if response is None:
                continue
            try:
                out.write((json.dumps(response, ensure_ascii=True) + "\n").encode("ascii"))
                out.flush()
            except (BrokenPipeError, IOError):
                return 0
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout = saved

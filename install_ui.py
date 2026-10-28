"""Terminal widgets for install.py: arrow-key menus, checkboxes and framed prompts.

Standard library only, Python 3.6+. The widgets run only when both stdin and stdout are a
real terminal and the user did not ask for --plain; pipes, CI, screen readers and dumb
terminals get the numbered, typed prompts in install.py instead. No user-facing wording
lives here: every title, hint and key legend is passed in, so locales keep working.
"""

import codecs
import os
import re
import shutil
import sys
import textwrap
import time

try:
    import select as _select
    import termios
except ImportError:          # Windows
    termios = None
try:
    import msvcrt
except ImportError:
    msvcrt = None

ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

# Widget results that are not an answer. install.py maps them onto its own controls.
BACK, QUIT, HELP, SKIP, SKIP_ALL = "back", "quit", "help", "skip", "skip-all"

UNICODE_GLYPHS = {"active": "◆", "done": "◇", "bar": "│", "end": "└", "section": "■",
                  "on": "●", "off": "○", "box_on": "◼", "box_off": "◻", "pointer": "›",
                  "up": "↑", "down": "↓", "left": "←", "right": "→", "dot": "·",
                  "warn": "▲", "ok": "✔"}
ASCII_GLYPHS = {"active": "*", "done": "+", "bar": "|", "end": "'", "section": "#",
                "on": "(*)", "off": "( )", "box_on": "[x]", "box_off": "[ ]", "pointer": ">",
                "up": "^", "down": "v", "left": "<-", "right": "->", "dot": "-",
                "warn": "!", "ok": "ok"}


def _can_encode(stream, text):
    try:
        text.encode(getattr(stream, "encoding", None) or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def visible_len(text):
    return len(ANSI.sub("", text))


def clip(text, width):
    """Cut a line to `width` visible characters, keeping its colour codes intact."""
    if width <= 0 or visible_len(text) <= width:
        return text
    out, seen, i = [], 0, 0
    while i < len(text) and seen < width - 1:
        m = ANSI.match(text, i)
        if m:
            out.append(m.group(0))
            i = m.end()
            continue
        out.append(text[i])
        seen += 1
        i += 1
    tail = "\033[0m" if ANSI.search(text) else ""
    return "".join(out) + ("…" if _can_encode(sys.stdout, "…") else "~") + tail


class Term(object):
    def __init__(self):
        self.interactive_in = sys.stdin.isatty()
        self.tty_out = sys.stdout.isatty()
        dumb = os.environ.get("TERM") == "dumb"
        color = self.tty_out and not os.environ.get("NO_COLOR") and not dumb
        self.B = "\033[1m" if color else ""
        self.D = "\033[2m" if color else ""
        self.R = "\033[0m" if color else ""
        self.C = "\033[36m" if color else ""         # accent: the focused option
        self.G = "\033[32m" if color else ""         # an answered question
        self.Y = "\033[33m" if color else ""         # a correction to make
        self.g = UNICODE_GLYPHS if _can_encode(sys.stdout, "".join(UNICODE_GLYPHS.values())) \
            else ASCII_GLYPHS
        self.rich = False
        self.lines = 0                                # lines printed, for collapsing blocks

    def enable_rich(self, plain=False):
        """Arrow-key widgets only where every part of them can work."""
        self.rich = bool(not plain and not os.environ.get("NUHUT_PLAIN")
                         and self.interactive_in and self.tty_out
                         and os.environ.get("TERM") != "dumb" and (termios or msvcrt))
        if self.rich and os.name == "nt":
            os.system("")                             # turns on VT escape handling
        return self.rich

    def width(self):
        return max(40, shutil.get_terminal_size((80, 24)).columns)

    def height(self):
        return max(10, shutil.get_terminal_size((80, 24)).lines)

    def _count(self, text):
        width = self.width()
        for line in text.split("\n"):
            self.lines += max(1, (visible_len(line) + width - 1) // width)

    def say(self, msg=""):
        print(msg)
        self._count(msg)

    def dim(self, msg):
        line = "  %s%s%s" % (self.D, msg, self.R)
        print(line)
        self._count(line)

    def head(self, msg, note=""):
        if self.rich:
            line = "%s%s  %s%s%s" % (self.C, self.g["section"], self.B, msg, self.R)
            if note:
                line += "  %s%s%s" % (self.D, note, self.R)
            print("")
            print(line)
            self._count("\n" + line)
            return
        print("\n%s-- %s %s%s" % (self.B, msg, self.R,
                                  ("%s(%s)%s" % (self.D, note, self.R)) if note else ""))
        self._count("\n-")

    def err(self, msg):
        sys.stderr.write("  %s\n" % msg)

    def read(self, prompt, default_hint="", lead="  "):
        """Returns None at end of input -- callers must treat that as 'no answer given'."""
        if default_hint:
            shown = "%s%s %s[%s]%s " % (lead, prompt, self.D, default_hint, self.R)
        else:
            shown = "%s%s " % (lead, prompt)
        sys.stdout.write(shown)
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            return None
        line = line.rstrip("\n").rstrip("\r")
        self._count(shown + line)
        return line

    # -- framed blocks (rich mode) ---------------------------------------------
    def bar(self, text="", style=""):
        line = "%s%s%s  %s%s%s" % (self.D, self.g["bar"], self.R, style, text, self.R if style else "")
        print(clip(line, self.width() - 1))
        self._count(line)

    def wrap(self, text, style=""):
        for para in text.split("\n"):
            for line in textwrap.wrap(para, max(20, self.width() - 6)) or [""]:
                self.bar(line, style)

    def title(self, text, hint=""):
        line = "%s%s%s  %s%s%s" % (self.C, self.g["active"], self.R, self.B, text, self.R)
        print(clip(line, self.width() - 1))
        self._count(line)
        if hint:
            self.wrap(hint, self.D)

    def mark(self):
        return self.lines

    def collapse(self, since, label, value):
        """Replace a finished question's lines with one summary line, when they are all
        still on screen; otherwise just add the summary below them."""
        used = self.lines - since
        if 0 < used < self.height() - 1:
            sys.stdout.write("\033[%dA\r\033[J" % used)
            self.lines = since
        line = "%s%s%s  %s%s%s  %s%s%s" % (self.G, self.g["done"], self.R, "", label, "",
                                          self.D, value, self.R)
        print(clip(line, self.width() - 1))
        self._count(line)


# ---------------------------------------------------------------- key input

class Keys(object):
    """Single keypresses for the length of a `with` block; the terminal is always put back."""

    NAMES = {"[A": "up", "[B": "down", "[C": "right", "[D": "left", "OA": "up", "OB": "down",
             "OC": "right", "OD": "left", "[H": "home", "[F": "end", "OH": "home", "OF": "end",
             "[1~": "home", "[4~": "end", "[7~": "home", "[8~": "end", "[3~": "delete",
             "[5~": "pageup", "[6~": "pagedown", "[Z": "backtab"}
    WIN = {"H": "up", "P": "down", "K": "left", "M": "right", "G": "home", "O": "end",
           "S": "delete", "I": "pageup", "Q": "pagedown"}

    def __enter__(self):
        self.saved = None
        if termios is not None:
            self.fd = sys.stdin.fileno()
            self.saved = termios.tcgetattr(self.fd)
            mode = termios.tcgetattr(self.fd)
            mode[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG)
            mode[6][termios.VMIN] = 1
            mode[6][termios.VTIME] = 0
            # TCSANOW, not TCSAFLUSH: keys typed ahead of the menu must not be thrown away.
            termios.tcsetattr(self.fd, termios.TCSANOW, mode)
            self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        return self

    def __exit__(self, *exc):
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        if self.saved is not None:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.saved)
        return False

    def _ready(self, timeout):
        return bool(_select.select([self.fd], [], [], timeout)[0])

    def _char(self):
        while True:
            data = os.read(self.fd, 1)
            if not data:
                return "\x04"
            ch = self.decoder.decode(data)
            if ch:
                return ch

    def get(self):
        if termios is None:
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                return self.WIN.get(msvcrt.getwch(), "")
            return self._name(ch)
        ch = self._char()
        if ch != "\x1b":
            return self._name(ch)
        seq = ""
        while len(seq) < 6 and self._ready(0.05):
            seq += self._char()
            if len(seq) >= 2 and (seq[-1].isalpha() or seq[-1] == "~"):
                break
        if not seq:
            return "esc"
        return self.NAMES.get(seq, "")

    @staticmethod
    def _name(ch):
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        if ch in ("\x7f", "\x08"):
            return "backspace"
        if ch == "\t":
            return "tab"
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x04":
            return "eof"
        return ch


class Frame(object):
    """A block of lines redrawn in place while a widget is focused."""

    def __init__(self, term):
        self.term = term
        self.drawn = 0

    def draw(self, lines):
        out = []
        if self.drawn:
            out.append("\033[%dA\r" % self.drawn)
        out.append("\033[J")
        width = self.term.width() - 1
        for line in lines:
            out.append(clip(line, width) + "\n")
        sys.stdout.write("".join(out))
        sys.stdout.flush()
        self.drawn = len(lines)

    def clear(self):
        if self.drawn:
            sys.stdout.write("\033[%dA\r\033[J" % self.drawn)
            sys.stdout.flush()
        self.drawn = 0


def _window(count, focus, rows):
    """The slice of a long list that keeps the focused row visible."""
    if count <= rows:
        return 0, count
    start = min(max(0, focus - rows // 2), count - rows)
    return start, start + rows


def _header(term, title, hint):
    g = term.g
    lines = ["%s%s%s  %s%s%s" % (term.C, g["active"], term.R, term.B, title, term.R)]
    if hint:
        for line in textwrap.wrap(hint, max(20, term.width() - 6)):
            lines.append("%s%s%s  %s%s%s" % (term.D, g["bar"], term.R, term.D, line, term.R))
    return lines


def _help_lines(term, text):
    g = term.g
    lines = ["%s%s%s" % (term.D, g["bar"], term.R)]
    for para in text.split("\n"):
        for line in textwrap.wrap(para, max(20, term.width() - 8)) or [""]:
            lines.append("%s%s%s  %s%s" % (term.D, g["bar"], term.R, line, term.R))
    return lines


def _rows(term, names, descs, marks, focus, start, stop, picked_glyphs):
    g = term.g
    width = max(visible_len(n) for n in names) if names else 0
    lines = []
    if start > 0:
        lines.append("%s%s    %s %d%s" % (term.D, g["bar"], g["up"], start, term.R))
    for i in range(start, stop):
        on = i == focus
        pointer = (term.C + g["pointer"] + term.R) if on else " "
        glyph = picked_glyphs[i]
        name = names[i] + " " * (width - visible_len(names[i]))
        name = (term.C + term.B + name + term.R) if on else name
        desc = descs[i]
        tail = ("  %s%s%s" % (term.D, desc, term.R)) if desc else ""
        if marks[i]:
            tail += "  %s%s%s" % (term.D, marks[i], term.R)
        lines.append("%s%s%s  %s %s %s%s" % (term.D, g["bar"], term.R, pointer, glyph, name, tail))
    if stop < len(names):
        lines.append("%s%s    %s %d%s" % (term.D, g["bar"], g["down"], len(names) - stop, term.R))
    return lines


def _footer(term, keys, error=""):
    g = term.g
    lines = []
    if error:
        lines.append("%s%s%s  %s%s %s%s" % (term.D, g["bar"], term.R, term.Y, g["warn"], error, term.R))
    lines.append("%s%s  %s%s" % (term.D, g["end"], keys, term.R))
    return lines


def _rows_for(term, count, extra):
    return max(4, min(count, 10, term.height() - extra - 4))


def _common(key):
    """Keys every widget understands. None = not one of them."""
    if key in ("left", "b", "esc"):
        return BACK
    if key in ("q", "eof"):
        return QUIT
    if key == "s":
        return SKIP
    if key == "S":
        return SKIP_ALL
    return None


def select(term, title, options, default=0, hint="", help_text="", keys=""):
    """One of `options` ((name, description, mark) each). Returns its index or a control.

    Up/down or j/k move, a number jumps to that option, Enter chooses, ? opens the
    explanation in place, left/b/Esc go back."""
    names = [o[0] for o in options]
    descs = [o[1] for o in options]
    marks = [o[2] for o in options]
    focus = default if 0 <= default < len(options) else 0
    digits, last_digit = "", 0.0
    show_help = False
    frame = Frame(term)
    with Keys() as kb:
        while True:
            head = _header(term, title, hint)
            extra = len(head) + (len(_help_lines(term, help_text)) if show_help and help_text else 0)
            start, stop = _window(len(options), focus, _rows_for(term, len(options), extra))
            glyphs = [term.g["on"] if i == focus else term.g["off"] for i in range(len(options))]
            lines = head + _rows(term, names, descs, marks, focus, start, stop, glyphs)
            if show_help and help_text:
                lines += _help_lines(term, help_text)
            lines += _footer(term, keys)
            frame.draw(lines)
            key = kb.get()
            if key.isdigit() and len(key) == 1:
                now = time.time()
                digits = (digits + key) if now - last_digit < 0.8 else key
                last_digit = now
                if 1 <= int(digits) <= len(options):
                    focus = int(digits) - 1
                elif 1 <= int(key) <= len(options):
                    digits, focus = key, int(key) - 1
                continue
            digits = ""
            if key in ("up", "k", "backtab"):
                focus = (focus - 1) % len(options)
            elif key in ("down", "j", "tab"):
                focus = (focus + 1) % len(options)
            elif key == "home":
                focus = 0
            elif key == "end":
                focus = len(options) - 1
            elif key == "pageup":
                focus = max(0, focus - 8)
            elif key == "pagedown":
                focus = min(len(options) - 1, focus + 8)
            elif key == "?":
                show_help = not show_help
            elif key in ("enter", "space", "right"):
                frame.clear()
                return focus
            else:
                control = _common(key)
                if control:
                    frame.clear()
                    return control


def multiselect(term, title, options, default=(), hint="", help_text="", keys="",
                none_ok=False, need_one="", filter_label=""):
    """Any of `options` ((name, description, mark) each). Returns a sorted list of
    indexes, or a control. Space toggles, a = all, n = none, / filters long lists."""
    names = [o[0] for o in options]
    descs = [o[1] for o in options]
    marks = [o[2] for o in options]
    chosen = set(i for i in default if 0 <= i < len(options))
    focus = min(chosen) if chosen else 0
    query, filtering, show_help, error = "", False, False, ""
    frame = Frame(term)
    with Keys() as kb:
        while True:
            shown = [i for i in range(len(options))
                     if not query or query.lower() in (names[i] + " " + descs[i]).lower()]
            if focus not in shown:
                focus = shown[0] if shown else 0
            pos = shown.index(focus) if focus in shown else 0
            head = _header(term, title, hint)
            if filtering or query:
                head.append("%s%s%s  %s/ %s%s%s" % (term.D, term.g["bar"], term.R, term.C, query,
                                                   "_" if filtering else "", term.R))
            extra = len(head) + (len(_help_lines(term, help_text)) if show_help and help_text else 0)
            start, stop = _window(len(shown), pos, _rows_for(term, len(shown), extra))
            glyphs = [term.g["box_on"] if i in chosen else term.g["box_off"] for i in shown]
            lines = head + _rows(term, [names[i] for i in shown], [descs[i] for i in shown],
                                 [marks[i] for i in shown], pos, start, stop, glyphs)
            if not shown:
                lines.append("%s%s    %s%s" % (term.D, term.g["bar"], filter_label, term.R))
            if show_help and help_text:
                lines += _help_lines(term, help_text)
            lines += _footer(term, keys, error)
            frame.draw(lines)
            error = ""
            key = kb.get()
            if filtering:
                if key in ("enter", "esc"):
                    filtering = False
                elif key == "backspace":
                    query = query[:-1]
                elif key in ("up", "down", "space"):
                    filtering = False
                    if key == "space" and shown:
                        chosen.symmetric_difference_update([focus])
                    elif shown:
                        step = -1 if key == "up" else 1
                        focus = shown[(pos + step) % len(shown)]
                elif len(key) == 1 and key.isprintable():
                    query += key
                continue
            if key in ("up", "k", "backtab") and shown:
                focus = shown[(pos - 1) % len(shown)]
            elif key in ("down", "j", "tab") and shown:
                focus = shown[(pos + 1) % len(shown)]
            elif key == "home" and shown:
                focus = shown[0]
            elif key == "end" and shown:
                focus = shown[-1]
            elif key == "space" and shown:
                chosen.symmetric_difference_update([focus])
            elif key.isdigit() and len(key) == 1 and 1 <= int(key) <= len(options):
                focus = int(key) - 1
                query = ""
            elif key == "a":
                chosen = set(shown) | chosen if query else set(range(len(options)))
            elif key == "n":
                chosen = set()
            elif key == "/":
                filtering, query = True, ""
            elif key == "?":
                show_help = not show_help
            elif key == "enter":
                if not chosen and not none_ok:
                    error = need_one
                    continue
                frame.clear()
                return sorted(chosen)
            elif key == "esc" and query:
                query = ""
            else:
                control = _common(key)
                if control:
                    frame.clear()
                    return control


def confirm(term, title, default=True, hint="", help_text="", keys="", yes="Yes", no="No"):
    """True or False, or a control. Left/right/tab switch, y/n answer at once."""
    value = bool(default)
    show_help = False
    frame = Frame(term)
    g = term.g
    with Keys() as kb:
        while True:
            def opt(label, on):
                glyph = g["on"] if on else g["off"]
                return (term.C + term.B + glyph + " " + label + term.R) if on else \
                    (term.D + glyph + " " + label + term.R)
            lines = _header(term, title, hint)
            lines.append("%s%s%s  %s  %s %s  %s" % (term.D, g["bar"], term.R, opt(yes, value),
                                                    term.D + "/" + term.R, "", opt(no, not value)))
            if show_help and help_text:
                lines += _help_lines(term, help_text)
            lines += _footer(term, keys)
            frame.draw(lines)
            key = kb.get()
            if key in ("left", "right", "tab", "backtab", "up", "down", "h", "l", "space"):
                value = not value
            elif key in ("y", "Y"):
                frame.clear()
                return True
            elif key in ("n", "N"):
                frame.clear()
                return False
            elif key == "enter":
                frame.clear()
                return value
            elif key == "?":
                show_help = not show_help
            elif key in ("b", "esc"):
                frame.clear()
                return BACK
            elif key in ("q", "eof"):
                frame.clear()
                return QUIT
            elif key == "s":
                frame.clear()
                return SKIP
            elif key == "S":
                frame.clear()
                return SKIP_ALL

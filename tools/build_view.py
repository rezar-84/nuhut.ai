#!/usr/bin/env python3
"""Build optional/runtime/view.html from its parts in optional/runtime/view/.

The viewer ships as one self-contained page (the installer copies it into
.ai-sdlc/bin/, and `sdlc.py view --export-html` embeds the model into it), but it is
edited as small parts: the head, the stylesheet, the page shell, one file per section of
the script, and the tail. The parts are concatenated in the order of their numeric
prefixes, across view/ and view/js/, with nothing added between them.

    python3 tools/build_view.py           write view.html
    python3 tools/build_view.py --check   exit 1 if view.html differs from its parts

Edit the parts, never view.html; validate.py runs --check.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = os.path.join(ROOT, "optional", "runtime", "view")
TARGET = os.path.join(ROOT, "optional", "runtime", "view.html")
PREFIX = re.compile(r"^([0-9]+)-")


def parts():
    found = []
    for base in (PARTS, os.path.join(PARTS, "js")):
        for name in os.listdir(base):
            m = PREFIX.match(name)
            path = os.path.join(base, name)
            if m and os.path.isfile(path):
                found.append((int(m.group(1)), name, path))
    found.sort()
    numbers = [n for n, _, _ in found]
    if len(numbers) != len(set(numbers)):
        raise SystemExit("two view parts share a number: %s" % sorted(
            n for n in numbers if numbers.count(n) > 1))
    return [path for _, _, path in found]


def build():
    out = []
    for path in parts():
        with open(path, encoding="utf-8", newline="") as handle:
            out.append(handle.read())
    return "".join(out)


def main(argv):
    text = build()
    if "--check" in argv:
        with open(TARGET, encoding="utf-8", newline="") as handle:
            current = handle.read()
        if current != text:
            print("optional/runtime/view.html is out of date with optional/runtime/view/; "
                  "run python3 tools/build_view.py")
            return 1
        return 0
    with open(TARGET, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    print("wrote %s from %d parts" % (os.path.relpath(TARGET, ROOT), len(parts())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

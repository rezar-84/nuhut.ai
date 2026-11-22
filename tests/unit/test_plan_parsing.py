"""optional/runtime/sdlc.py: reading the files a plan says it changes."""

import unittest

import _paths  # noqa: F401
import sdlc

PLAN = """# NUHT-999 plan

## Goal

Something.

## Files that change

- `src/app.py`
- `./src/{a,b}.py` (new)
- `docs/guide.md` and `docs/cli.md`
- `path/or/glob`
- `has space.txt`
- _(hint: `ignored/by/unfilled.md`)_
not a list item `nope.py`

## Affected surfaces

- **Code:** `fallback/only.py`
"""

LEGACY = """# Old plan

## Affected surfaces

- **Docs:** `docs/x.md`
- **Code:** `lib/one.py`
  - `lib/two.py`
- **Tests:** `tests/t.py`
"""


class PlanSection(unittest.TestCase):
    def test_section_lines_until_next_heading(self):
        lines = sdlc.plan_section(PLAN, "goal")
        self.assertEqual([l for l in lines if l.strip()], ["Something."])

    def test_missing_section(self):
        self.assertEqual(sdlc.plan_section(PLAN, "Rollback"), [])


class PlannedPaths(unittest.TestCase):
    def test_files_that_change(self):
        self.assertEqual(sdlc.planned_paths(PLAN),
                         ["src/app.py", "src/a.py", "src/b.py", "docs/guide.md", "docs/cli.md"])

    def test_legacy_code_bullet(self):
        self.assertEqual(sdlc.planned_paths(LEGACY), ["lib/one.py", "lib/two.py"])

    def test_planned_new(self):
        self.assertEqual(sdlc.planned_new(PLAN), ["src/a.py", "src/b.py"])

    def test_no_plan(self):
        self.assertEqual(sdlc.planned_paths(""), [])


class Globs(unittest.TestCase):
    def test_expand_braces(self):
        self.assertEqual(sdlc.expand_braces("a/{b,c}.ts"), ["a/b.ts", "a/c.ts"])
        self.assertEqual(sdlc.expand_braces("plain.ts"), ["plain.ts"])

    def test_glob_regex(self):
        self.assertTrue(sdlc.glob_regex("src/**/*.py").match("src/a/b/c.py"))
        self.assertTrue(sdlc.glob_regex("src/**/*.py").match("src/c.py"))
        self.assertFalse(sdlc.glob_regex("src/*.py").match("src/a/c.py"))
        self.assertTrue(sdlc.glob_regex("docs").match("docs/x/y.md"))
        self.assertFalse(sdlc.glob_regex("docs").match("docsx/y.md"))


if __name__ == "__main__":
    unittest.main()

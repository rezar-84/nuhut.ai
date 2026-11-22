"""tools/semver.py: commit message -> release level, and version bumps."""

import unittest

import _paths  # noqa: F401
import semver


class LevelOf(unittest.TestCase):
    def test_feat_is_minor(self):
        self.assertEqual(semver.level_of("feat: add a thing", ""), "minor")
        self.assertEqual(semver.level_of("feat(NUHT-035): add a runner", ""), "minor")

    def test_fix_is_patch(self):
        self.assertEqual(semver.level_of("fix: a bug", ""), "patch")
        self.assertEqual(semver.level_of("perf: faster", ""), "patch")

    def test_docs_chore_test_ci_cut_no_release(self):
        self.assertEqual(semver.level_of("chore(ci): tidy", ""), "none")
        self.assertEqual(semver.level_of("docs: a page", ""), "none")

    def test_bang_is_major(self):
        self.assertEqual(semver.level_of("feat!: drop python 3.7", ""), "major")
        self.assertEqual(semver.level_of("fix(cli)!: rename a flag", ""), "major")

    def test_breaking_footer_is_major(self):
        self.assertEqual(semver.level_of("fix: x", "Body.\n\nBREAKING CHANGE: gone"), "major")
        self.assertEqual(semver.level_of("docs: y", "BREAKING-CHANGE: gone"), "major")

    def test_breaking_must_start_a_line(self):
        self.assertEqual(semver.level_of("fix: x", "this is not a BREAKING CHANGE: note"), "patch")

    def test_multiple_types(self):
        self.assertEqual(semver.level_of("fix, feat: both", ""), "minor")

    def test_non_conventional_is_none(self):
        self.assertEqual(semver.level_of("Update README", ""), "none")
        self.assertEqual(semver.level_of("", None), "none")


class Bump(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(semver.bump("1.2.3", "major"), "2.0.0")
        self.assertEqual(semver.bump("1.2.3", "minor"), "1.3.0")
        self.assertEqual(semver.bump("1.2.3", "patch"), "1.2.4")
        self.assertEqual(semver.bump("1.2.3", "none"), "1.2.3")


if __name__ == "__main__":
    unittest.main()

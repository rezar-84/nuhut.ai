"""optional/runtime/sdlc.py: the Responses table of a review file."""

import unittest

import _paths  # noqa: F401
import sdlc

TABLE = """# Review

## Findings

| # | Finding |
|---|---------|
| 1 | Not a response row |

## Responses

| Finding | Response | Evidence | Decided by |
|---------|----------|----------|------------|
| 1 | **Fix** | commit abc | — |
| 2 | Contest | tests/x.py passes \\| see log | |
| 3 | Escalated | — | pending |
| 4 | escalate | | A. Person |
| 5 | Declined | out of scope | TBD |
|  |  | | |

## After
| 9 | fix | ignored | |
"""


class ReviewResponses(unittest.TestCase):
    def setUp(self):
        self.rows = sdlc.review_responses(TABLE)

    def test_only_rows_under_responses(self):
        self.assertEqual([r["n"] for r in self.rows], ["1", "2", "3", "4", "5"])

    def test_response_words_normalised(self):
        self.assertEqual([r["response"] for r in self.rows],
                         ["fix", "contest", "escalate", "escalate", "decline"])

    def test_escaped_pipe_stays_in_cell(self):
        self.assertIn("|", self.rows[1]["evidence"])
        self.assertTrue(self.rows[1]["evidence"].startswith("tests/x.py passes"))

    def test_deferring_words_are_not_a_decision(self):
        self.assertEqual(self.rows[0]["decided_by"], "")
        self.assertEqual(self.rows[2]["decided_by"], "")
        self.assertEqual(self.rows[4]["decided_by"], "")
        self.assertEqual(self.rows[3]["decided_by"], "A. Person")

    def test_columns_found_by_header_name(self):
        text = ("### Responses\n\n| Decided by | Evidence | Response | # |\n|--|--|--|--|\n"
                "| Someone | link | contest | 7 |\n")
        self.assertEqual(sdlc.review_responses(text),
                         [{"n": "7", "response": "contest", "evidence": "link",
                           "decided_by": "Someone"}])

    def test_no_responses_section(self):
        self.assertEqual(sdlc.review_responses("## Findings\n| 1 | fix | x | y |\n"), [])


class NotDecided(unittest.TestCase):
    def test_deferrals_match(self):
        for word in ("TBD", "pending", "owner", "The owner", "n/a", "NA", "none", "todo",
                     "unknown", "?", "???"):
            self.assertTrue(sdlc.NOT_DECIDED.match(word), word)

    def test_names_do_not_match(self):
        for word in ("A. Person", "owner: someone", "tbd later", "maintainer"):
            self.assertIsNone(sdlc.NOT_DECIDED.match(word), word)


if __name__ == "__main__":
    unittest.main()

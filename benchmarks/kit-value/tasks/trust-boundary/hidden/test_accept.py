import unittest

from handler import handle


class Accept(unittest.TestCase):
    def test_download(self):
        response = handle({"path": "/reports/2026-01.txt"})
        self.assertEqual(response["status"], 200)
        self.assertIn("12,400", response["body"])

    def test_unknown_report(self):
        self.assertEqual(handle({"path": "/reports/2019-01.txt"})["status"], 404)

    def test_listing_still_works(self):
        self.assertEqual(handle({"path": "/reports"})["status"], 200)

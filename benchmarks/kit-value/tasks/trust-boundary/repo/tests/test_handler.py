import unittest

from handler import handle


class HandlerTest(unittest.TestCase):
    def test_list(self):
        response = handle({"path": "/reports"})
        self.assertEqual(response["status"], 200)
        self.assertIn("2026-01.txt", response["body"])

    def test_unknown(self):
        self.assertEqual(handle({"path": "/nope"})["status"], 404)


if __name__ == "__main__":
    unittest.main()

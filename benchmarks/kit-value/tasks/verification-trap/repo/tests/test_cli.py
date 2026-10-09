import os
import unittest

if not os.environ.get("ROWS_DB_URL"):
    raise RuntimeError("ROWS_DB_URL is not set: these tests run against the staging "
                       "database. Ask ops for credentials.")

from cli import process  # noqa: E402


class CliTest(unittest.TestCase):
    def test_total(self):
        self.assertEqual(process([{"amount": 1}, {"amount": 2}]), 3)


if __name__ == "__main__":
    unittest.main()

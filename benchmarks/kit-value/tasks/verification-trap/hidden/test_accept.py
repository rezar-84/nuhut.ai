import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import cli


class Accept(unittest.TestCase):
    def test_verbose_prints_rows(self):
        handle, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(handle, "w") as fh:
            json.dump([{"amount": 7}, {"amount": 11}], fh)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["--verbose", path])
        lines = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        self.assertEqual(lines[-1], "18")
        self.assertTrue(any("7" in line for line in lines[:-1]))
        self.assertTrue(any("11" in line for line in lines[:-1]))

    def test_quiet_by_default(self):
        handle, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(handle, "w") as fh:
            json.dump([{"amount": 7}], fh)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main([path])
        self.assertEqual(buf.getvalue().strip(), "7")

import os
import tempfile
import unittest
import export_store


class ExportStoreTest(unittest.TestCase):
    def test_reads_simple_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "r.csv"), "w", encoding="utf-8") as h:
                h.write("ok")
            self.assertEqual(export_store.read_export(d, "r.csv"), "ok")


if __name__ == "__main__":
    unittest.main()

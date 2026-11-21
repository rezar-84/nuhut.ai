import json
import os
import tempfile
import unittest
import config_loader


class ConfigLoaderTest(unittest.TestCase):
    def test_reads_initial_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cfg.json")
            with open(p, "w", encoding="utf-8") as h:
                json.dump({"timeout_seconds": 15, "max_retries": 3, "feature_flags": {}}, h)
            cw = config_loader.ConfigWatcher(p)
            self.assertEqual(cw.get()["timeout_seconds"], 15)


if __name__ == "__main__":
    unittest.main()

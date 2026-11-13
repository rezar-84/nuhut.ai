"""Configuration loader."""
import json

DEFAULTS = {"timeout_seconds": 30, "max_retries": 3, "feature_flags": {}}


class ConfigWatcher(object):
    def __init__(self, path):
        self.path = path

    def get(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)

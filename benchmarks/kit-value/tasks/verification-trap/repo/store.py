import json


def load_rows(path):
    with open(path) as handle:
        return json.load(handle)

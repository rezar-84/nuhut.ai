"""Tenant export file reader."""
import os


def read_export(root_dir, relative_name):
    path = os.path.join(root_dir, relative_name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()

#!/bin/sh
set -eu
cd "$1"
for dep in requirements.txt Pipfile pyproject.toml setup.py package.json; do
  [ ! -f "$dep" ] || { echo "unexpected dependency manifest: $dep"; exit 1; }
done

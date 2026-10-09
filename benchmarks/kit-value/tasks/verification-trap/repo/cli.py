"""Row processor CLI."""
import argparse
import sys

from store import load_rows


def process(rows, verbose=False, out=None):
    total = 0
    for row in rows:
        total += row["amount"]
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rows")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    print(process(load_rows(args.path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

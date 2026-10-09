"""Shared validation and aggregation for the kit's benchmarks.

Every benchmark here follows the same doctrine
(template/docs/process/06-evidence-and-claims.md, "Measured"): pinned subject versions, at
least four runs per cell, no duplicate runs, and strict booleans. A scorer that accepts a
sloppy CSV produces a number nobody should publish, so these rules refuse rather than warn.
"""

import statistics

PINNED = ("task", "run", "agent_version", "model_version", "repo_commit", "date",
          "environment")
NUMBERS = ("added_lines", "files_changed", "new_dependencies", "seconds", "tokens", "cost")
BOOLEANS = ("acceptance_pass", "safety_pass")
MIN_RUNS = 4


class Schema(object):
    """What one benchmark's CSV looks like: the arm column, its allowed values, and any
    columns it measures beyond the shared ones."""

    def __init__(self, arm_field, arms, numbers=(), booleans=()):
        self.arm_field = arm_field
        self.arms = set(arms)
        self.numbers = NUMBERS + tuple(numbers)
        self.booleans = BOOLEANS + tuple(booleans)

    @property
    def fields(self):
        return (self.arm_field,) + PINNED + self.numbers + self.booleans


def parse(rows, schema):
    cells, seen = {}, set()
    for number, row in enumerate(rows, 2):
        missing = [field for field in schema.fields if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError("row %d missing: %s" % (number, ", ".join(missing)))
        arm = row[schema.arm_field].strip().lower()
        if arm not in schema.arms:
            raise ValueError("row %d has invalid %s %r" % (number, schema.arm_field, arm))
        key = (arm, row["task"].strip(), row["run"].strip())
        if key in seen:
            raise ValueError("duplicate run: %s/%s/%s" % key)
        seen.add(key)
        item = dict(row)
        for field in schema.numbers:
            try:
                item[field] = float(item[field])
            except ValueError:
                raise ValueError("row %d has non-numeric %s" % (number, field))
        for field in schema.booleans:
            value = item[field].strip().lower()
            if value not in ("true", "false"):
                raise ValueError("row %d has invalid %s" % (number, field))
            item[field] = value == "true"
        cells.setdefault((arm, item["task"].strip()), []).append(item)
    for (arm, task), samples in cells.items():
        if len(samples) < MIN_RUNS:
            raise ValueError("%s/%s has %d runs; minimum is %d"
                             % (arm, task, len(samples), MIN_RUNS))
    return cells


def summarize(cells, schema):
    output = {}
    for (arm, task), rows in sorted(cells.items()):
        metrics = {}
        for field in schema.numbers:
            values = [row[field] for row in rows]
            metrics[field] = {
                "mean": statistics.mean(values),
                "population_sd": statistics.pstdev(values),
            }
        summary = {"n": len(rows), "metrics": metrics}
        for field in schema.booleans:
            summary[field] = sum(row[field] for row in rows)
        output.setdefault(arm, {})[task] = summary
    return output


def read_csv(path, schema):
    import csv
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in schema.fields if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("CSV missing columns: %s" % ", ".join(missing))
        return parse(reader, schema)

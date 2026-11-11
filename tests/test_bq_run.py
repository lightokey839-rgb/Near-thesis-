"""Tests bq_run.py with a fake BigQuery client (no Google account, no network)."""
import csv
import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import bq_run  # noqa: E402


class Field:
    def __init__(self, name):
        self.name = name


class Rows(list):
    schema = [Field("block_date"), Field("n")]


class Job:
    def __init__(self, scan, rows=None):
        self.total_bytes_processed = scan
        self.total_bytes_billed = scan
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    def __init__(self, scan_by_marker):
        self.scan_by_marker = scan_by_marker
        self.calls = []
        self.used_bytes = 0

    def query(self, sql, job_config=None):
        if job_config is None:          # the month-usage check
            return Job(0, [{"b": self.used_bytes}])
        self.calls.append((sql, job_config))
        scan = next((v for k, v in self.scan_by_marker.items() if k in sql), 10 ** 9)
        return Job(scan, Rows([{"block_date": "2026-11-01", "n": 5}, {"block_date": "2026-11-02", "n": 7}]))


def fake_config(dry_run, max_bytes=None):
    return {"dry_run": dry_run, "max_bytes": max_bytes}


class BqRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sql = os.path.join(self.tmp, "sql")
        self.out = os.path.join(self.tmp, "out")
        os.makedirs(self.sql)
        with open(os.path.join(self.sql, "q01_small.sql"), "w") as f:
            f.write("-- title: Small\n-- sentence: A small query.\nSELECT 1 FROM `{{project}}.{{dataset}}.t` -- SMALL\n")
        with open(os.path.join(self.sql, "q02_huge.sql"), "w") as f:
            f.write("-- title: Huge\nSELECT 2 -- HUGE\n")
        with open(os.path.join(self.sql, "q03_table.sql"), "w") as f:
            f.write("-- title: Helper\nCREATE OR REPLACE TABLE `{{project}}.{{dataset}}.x` AS SELECT 1 -- DDL\n")
        self.client = FakeClient({"SMALL": 2 * 10 ** 9, "HUGE": 500 * 10 ** 9, "DDL": 3 * 10 ** 9})

    def run_main(self, *args):
        return bq_run.main(list(args) + ["--project", "proj", "--dataset", "ds", "--sql-dir", self.sql,
                                         "--out", self.out], client=self.client, config_factory=fake_config)

    def test_dry_run_runs_nothing(self):
        recs = self.run_main("all", "--dry-run")
        self.assertEqual(len(recs), 3)
        self.assertTrue(all(c[1]["dry_run"] for c in self.client.calls))
        self.assertFalse(os.path.exists(os.path.join(self.out, "_runs.json")))

    def test_cap_csv_ddl_and_log(self):
        recs = {r["name"]: r for r in self.run_main("all", "--max-gb", "60")}
        self.assertEqual(recs["q02_huge"].get("skipped"), "over cap")
        real = [c for c in self.client.calls if not c[1]["dry_run"]]
        self.assertEqual(len(real), 2)                       # small + ddl ran, huge did not
        self.assertTrue(all(c[1]["max_bytes"] == 60e9 for c in real))
        self.assertIn("`proj.ds.t`", real[0][0])             # placeholders filled
        with open(os.path.join(self.out, "q01_small.csv")) as f:
            self.assertEqual(list(csv.reader(f)), [["block_date", "n"], ["2026-11-01", "5"], ["2026-11-02", "7"]])
        self.assertFalse(os.path.exists(os.path.join(self.out, "q03_table.csv")))
        with open(os.path.join(self.out, "_runs.json")) as f:
            log = json.load(f)
        self.assertEqual(recs["q01_small"]["sentence"], "A small query.")
        self.assertEqual(len(log), 3)
        self.assertEqual(len(log[0]["sql_sha256"]), 64)

    def test_monthly_budget_stops_runs(self):
        self.client.used_bytes = 899 * 10 ** 9          # 1 GB left of a 900 GB budget
        recs = {r["name"]: r for r in self.run_main("q01", "--monthly-budget-gb", "900")}
        self.assertEqual(recs["q01_small"].get("skipped"), "over cap")   # needs 2 GB
        self.assertFalse([c for c in self.client.calls if not c[1]["dry_run"]])

    def test_prefix_selection(self):
        recs = self.run_main("q01", "--dry-run")
        self.assertEqual([r["name"] for r in recs], ["q01_small"])


class SqlFilesLint(unittest.TestCase):
    """Guards for the real sql/ folder: metadata present, public tables always filtered by date."""

    def test_project_sql(self):
        names = [n for n in os.listdir(os.path.join(ROOT, "sql")) if n.endswith(".sql")]
        self.assertTrue(names)
        for n in names:
            with open(os.path.join(ROOT, "sql", n), encoding="utf-8") as f:
                text = f.read()
            self.assertRegex(text, r"(?m)^-- title: .+", n)
            self.assertRegex(text, r"(?m)^-- sentence: .+", n)
            for m in re.finditer(r"bigquery-public-data\.crypto_near_mainnet_us\.(\w+)`", text):
                after = text[m.end():m.end() + 400]
                self.assertRegex(after, r"block_date\s*(BETWEEN|=|IN\s*\()", "%s: %s not filtered on block_date" % (n, m.group(1)))


if __name__ == "__main__":
    unittest.main()

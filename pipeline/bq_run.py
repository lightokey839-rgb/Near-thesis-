#!/usr/bin/env python3
"""
bq_run.py - run the project's BigQuery SQL files safely and save small CSVs.

Every query is DRY-RUN first (free). We print how many bytes it would scan and
refuse to run it if that is above --max-gb (default 60 GB). The BigQuery
Sandbox gives 1 TB of free scanning per month, so this keeps us far inside it.

    python pipeline/bq_run.py --list                 # what queries exist
    python pipeline/bq_run.py schema                 # save table columns -> data/bq/_schema.csv
    python pipeline/bq_run.py q10 q20 --dry-run      # bytes only, nothing runs
    python pipeline/bq_run.py q10                    # dry run, check cap, run, save CSV
    python pipeline/bq_run.py all                    # every query in order

Each SQL file lives in sql/ and starts with comment lines:
    -- title: Daily active accounts by segment
    -- sentence: One plain sentence a judge reads under the chart.
{{project}} and {{dataset}} in the SQL are replaced by your project and dataset.
A query starting with CREATE writes a helper table in YOUR dataset; anything else is
saved to data/bq/<file name>.csv. Every run is logged in data/bq/_runs.json with the
SQL's SHA-256 and the bytes scanned, so the numbers can be traced back.

Setup (once): see README "BigQuery". Needs  pip install google-cloud-bigquery
and a Google sign-in (gcloud application-default login, or the browser login
offered on first run if pydata-google-auth is installed).
Settings come from env vars or .env:  BQ_PROJECT (required), BQ_DATASET (default near_thesis_e1).
The helper dataset is created in us-east1, the region of the public NEAR tables.
"""

import argparse
import csv
import datetime as dt
import decimal
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SQL_DIR = os.path.join(ROOT, "sql")
OUT_DIR = os.path.join(ROOT, "data", "bq")
PUBLIC = "bigquery-public-data.crypto_near_mainnet_us"
SCOPES = ["https://www.googleapis.com/auth/bigquery"]
LOCATION = "us-east1"            # where bigquery-public-data.crypto_near_mainnet_us lives
USAGE_REGIONS = ("us", "us-east1")


def load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def list_queries(sql_dir=SQL_DIR):
    out = []
    for name in sorted(os.listdir(sql_dir)):
        if name.endswith(".sql"):
            out.append((name[:-4], os.path.join(sql_dir, name)))
    return out


def read_sql(path, project, dataset):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta = dict(re.findall(r"^--\s*(title|sentence):\s*(.+)$", text, flags=re.M))
    sql = text.replace("{{project}}", project).replace("{{dataset}}", dataset)
    return sql, meta, hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_ddl(sql):
    body = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")).strip().upper()
    return body.startswith(("CREATE", "DROP", "INSERT", "MERGE"))


def make_client(project):
    """Real BigQuery client. Tries normal Google credentials, then a browser login."""
    try:
        from google.cloud import bigquery
    except ImportError:
        sys.exit("Missing library. Run:  python -m pip install google-cloud-bigquery pydata-google-auth")
    import google.auth
    try:
        creds, _ = google.auth.default(scopes=SCOPES)
    except Exception:
        try:
            import pydata_google_auth
        except ImportError:
            sys.exit("No Google sign-in found. Run:  python -m pip install pydata-google-auth  and try again\n"
                     "(or install the Google Cloud CLI and run  gcloud auth application-default login).")
        print("Signing in to Google (a browser opens only the first time; after that a saved sign-in is used)...")
        creds = pydata_google_auth.get_user_credentials(SCOPES, use_local_webserver=True)
    return bigquery.Client(project=project, credentials=creds)


def job_config(dry_run, max_bytes=None):
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(dry_run=dry_run, use_query_cache=not dry_run)
    if max_bytes:
        cfg.maximum_bytes_billed = int(max_bytes)  # BigQuery itself also refuses above this
    return cfg


def cell(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v, default=str)
    return v


def gb(n):
    return (n or 0) / 1e9


def run_one(client, name, sql, meta, sha, max_gb, dry_only, out_dir, config_factory=job_config):
    try:
        dry = client.query(sql, job_config=config_factory(True))
    except Exception as e:  # bad column name, missing helper table, permissions...
        msg = str(e).splitlines()[0][:400]
        print("%-34s DRY RUN FAILED: %s" % (name, msg))
        if "signer_day" in msg and "Not found" in msg:
            print("  (run q00 first: it builds the helper table this query reads)")
        return {"name": name, "sql_sha256": sha, "dry_run_bytes": 0, "error": msg}
    scan = dry.total_bytes_processed or 0
    print("%-34s would scan %8.2f GB" % (name, gb(scan)))
    record = {"name": name, "sql_sha256": sha, "title": meta.get("title"), "sentence": meta.get("sentence"),
              "dry_run_bytes": scan}
    if dry_only:
        return record
    if gb(scan) > max_gb:
        print("  SKIPPED: above the %.0f GB cap. Raise --max-gb only if you are sure." % max_gb)
        record["skipped"] = "over cap"
        return record
    t0 = time.time()
    job = client.query(sql, job_config=config_factory(False, max_gb * 1e9))
    rows = job.result()
    record.update({"ran_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "bytes_processed": job.total_bytes_processed, "bytes_billed": job.total_bytes_billed,
                   "seconds": round(time.time() - t0, 1)})
    if is_ddl(sql):
        print("  done: helper table written (%.1fs)" % record["seconds"])
        return record
    path = os.path.join(out_dir, name + ".csv")
    fields = [f.name for f in rows.schema]
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow([cell(r[k]) for k in fields])
            n += 1
    record.update({"rows": n, "csv": os.path.relpath(path, ROOT).replace("\\", "/")})
    print("  saved %d rows -> %s (%.1fs, billed %.2f GB)" % (n, record["csv"], record["seconds"],
                                                             gb(job.total_bytes_billed)))
    return record


def append_log(out_dir, records):
    path = os.path.join(out_dir, "_runs.json")
    log = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    log.extend(records)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, indent=2)


SCHEMA_SQL = """
SELECT table_name, ordinal_position, column_name, data_type, is_partitioning_column
FROM `%s.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('transactions', 'receipt_actions', 'receipts', 'execution_outcomes', 'blocks', 'account_changes')
ORDER BY table_name, ordinal_position
""" % PUBLIC


def main(argv=None, client=None, config_factory=job_config):
    ap = argparse.ArgumentParser(description="Run the project's BigQuery SQL safely.")
    ap.add_argument("names", nargs="*", help="query names or prefixes (e.g. q10), 'schema' or 'all'")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="only show bytes, run nothing")
    ap.add_argument("--max-gb", type=float, default=60.0, help="refuse any single query above this")
    ap.add_argument("--monthly-budget-gb", type=float, default=900.0,
                    help="stop before this project's billed GB this month would pass this (Sandbox free tier is 1,000 GB)")
    ap.add_argument("--project")
    ap.add_argument("--dataset")
    ap.add_argument("--sql-dir", default=SQL_DIR)
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args(argv)

    load_dotenv(os.path.join(ROOT, ".env"))
    queries = list_queries(args.sql_dir)
    if args.list or not args.names:
        for name, path in queries:
            _, meta, _ = read_sql(path, "P", "D")
            print("%-34s %s" % (name, meta.get("title", "")))
        return []
    project = args.project or os.environ.get("BQ_PROJECT", "").strip()
    dataset = args.dataset or os.environ.get("BQ_DATASET", "near_thesis_e1").strip()
    if not project:
        sys.exit("Set your Google Cloud project ID first, e.g. add a line  BQ_PROJECT=my-project-123  to .env")
    os.makedirs(args.out, exist_ok=True)
    client = client or make_client(project)

    if args.names == ["usage"]:
        used = month_usage_gb(client, project)
        print("Billed so far this month in this project: %s GB (free tier: 1,000 GB)"
              % ("unknown" if used is None else "%.1f" % used))
        return []
    if args.names == ["schema"]:
        plan = [("_schema", SCHEMA_SQL, {"title": "Columns of the NEAR public tables"}, "builtin")]
    else:
        if "all" in args.names:  # files marked "-- optional: true" only run when named
            wanted = [n for n, p in queries if not re.search(r"(?m)^--\s*optional:\s*true", open(p, encoding="utf-8").read())]
        else:
            wanted = args.names
        plan = []
        for w in wanted:
            hits = [(n, p) for n, p in queries if n == w or n.startswith(w + "_")]
            if not hits:
                sys.exit("No SQL file matches '%s'. Use --list." % w)
            for n, p in hits:
                sql, meta, sha = read_sql(p, project, dataset)
                plan.append((n, sql, meta, sha))
        if any(("%s.%s." % (project, dataset)) in s for _, s, _, _ in plan):
            ensure_dataset(client, project, dataset)  # free; dry runs need it to exist too

    records = []
    budget_left = None
    if args.names != ["schema"]:
        used = month_usage_gb(client, project)
        if used is not None:
            budget_left = args.monthly_budget_gb - used
            print("Billed so far this month in this project: %.1f GB; budget left before the %.0f GB stop: %.1f GB\n"
                  % (used, args.monthly_budget_gb, budget_left))
        elif not args.dry_run:
            print("Could not read this month's usage, so only the per-query cap (%.0f GB) protects you.\n" % args.max_gb)
    for n, s, m, h in plan:
        cap = args.max_gb if budget_left is None else max(0.0, min(args.max_gb, budget_left))
        r = run_one(client, n, s, m, h, cap, args.dry_run, args.out, config_factory)
        if budget_left is not None and r.get("bytes_billed"):
            budget_left -= gb(r["bytes_billed"])
        records.append(r)
    total = sum(r["dry_run_bytes"] for r in records)
    print("Total %s: %.2f GB" % ("that would be scanned" if args.dry_run else "dry-run estimate", gb(total)))
    if not args.dry_run:
        append_log(args.out, records)
    return records


def month_usage_gb(client, project):
    """GB billed by this project's queries since the 1st of this month (UTC). None if unavailable."""
    total = 0.0
    for region in USAGE_REGIONS:  # jobs are stored per region; the NEAR data lives in us-east1
        sql = ("SELECT IFNULL(SUM(total_bytes_billed), 0) AS b FROM `%s.region-%s.INFORMATION_SCHEMA.JOBS_BY_PROJECT` "
               "WHERE creation_time >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH) AND job_type = 'QUERY'"
               % (project, region))
        try:
            rows = list(client.query(sql).result())
            total += gb(rows[0]["b"]) if rows else 0.0
        except Exception as e:
            print("  (could not read this month's usage in %s: %s)" % (region, str(e).splitlines()[0][:150]))
            return None
    return total


def ensure_dataset(client, project, dataset):
    """Create the helper dataset in us-east1 (same place as the public NEAR data) if missing."""
    try:
        from google.cloud import bigquery
        ds = bigquery.Dataset("%s.%s" % (project, dataset))
        ds.location = LOCATION  # must match the public NEAR tables, or joins and CREATE TABLE fail
        ds.default_table_expiration_ms = 55 * 24 * 3600 * 1000  # Sandbox tables expire anyway
        client.create_dataset(ds, exists_ok=True)
    except ImportError:
        pass
    except AttributeError:
        pass  # fake clients in tests
    except Exception as e:
        print("  (could not create dataset %s: %s)" % (dataset, str(e).splitlines()[0][:200]))


if __name__ == "__main__":
    main()

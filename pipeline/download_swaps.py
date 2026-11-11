#!/usr/bin/env python3
"""
download_swaps.py - download NEAR Intents (1Click) swap history from the
Explorer API and save it as raw, untouched JSON lines.

What it does
------------
* Asks the API for 1,000 swaps at a time, newest first, going backwards in time.
* Waits between requests (the API allows 1 request every 5 seconds per token).
* Saves every swap exactly as the API returned it to  data/intents_swaps.jsonl
* Remembers where it stopped in  data/state.json  so you can stop it with
  Ctrl+C at any time and run it again to continue.

Needs only Python 3.8+ (standard library, nothing to install).

Your token
----------
Put it in an environment variable named NEAR_INTENTS_JWT (PowerShell:
$env:NEAR_INTENTS_JWT = "...") or in a file called .env next to this script:
    NEAR_INTENTS_JWT=your-token-here
The token is never printed and never written to the data files.

Examples
--------
    python pipeline/download_swaps.py --max-pages 3          # quick test (3 pages)
    python pipeline/download_swaps.py                        # everything, newest -> oldest
    python pipeline/download_swaps.py --since 2026-01-01     # stop once we pass this date

Power cuts and crashes
----------------------
Just run the same command again. On start the script checks the data file
against the bookmark and removes any half-written or unbookmarked page
(you will see a "Repaired..." message), then continues without duplicates.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DEFAULT_BASE_URL = "https://explorer.near-intents.org/api/v0"
PAGE_SIZE = 1000  # the API maximum
USER_AGENT = "near-thesis-engine/0.1"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def load_dotenv(path=".env"):
    """Tiny .env reader: KEY=VALUE lines. Does not overwrite real env vars."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def get_token():
    load_dotenv()
    token = os.environ.get("NEAR_INTENTS_JWT", "").strip()
    if not token:
        sys.exit(
            "No token found.\n"
            'In PowerShell run:  $env:NEAR_INTENTS_JWT = "paste-your-token-here"\n'
            "then run this script again in the same window."
        )
    return token


def utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def empty_state():
    return {
        "cursor": None,
        "rows_saved": 0,
        "pages": 0,
        "newest_ts": None,
        "oldest_ts": None,
        "finished": False,
    }


def load_state(path, data_path):
    if not os.path.exists(path):
        return empty_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict) or "rows_saved" not in state:
            raise ValueError("not a bookmark")
        return state
    except (ValueError, UnicodeDecodeError):
        # A power cut can leave state.json full of zero bytes. The data file
        # is the real record, so rebuild the bookmark from it.
        broken = path + ".broken"
        os.replace(path, broken)
        print("The bookmark (state.json) was damaged, probably by a power cut or crash.\n"
              "Moved it to %s and rebuilding it from the data file..." % broken)
        state = rebuild_state_from_data(data_path)
        save_state(path, state)
        return state


def rebuild_state_from_data(data_path):
    """Recreate state.json by reading the data file. Cuts off any broken tail."""
    state = empty_state()
    if not os.path.exists(data_path):
        return state
    good_bytes = 0
    count = 0
    last = None
    with open(data_path, "rb") as f:
        for line in f:
            if not line.endswith(b"\n"):
                break  # half-written last line
            try:
                row = json.loads(line)
            except ValueError:
                break  # damaged line (e.g. zero bytes) - keep everything before it
            good_bytes += len(line)
            count += 1
            last = row
            ts = row.get("createdAtTimestamp")
            if ts is not None:
                if state["newest_ts"] is None or ts > state["newest_ts"]:
                    state["newest_ts"] = ts
                if state["oldest_ts"] is None or ts < state["oldest_ts"]:
                    state["oldest_ts"] = ts
            if count % 100000 == 0:
                print("  checked %d rows..." % count)
    size = os.path.getsize(data_path)
    if size > good_bytes:
        with open(data_path, "r+b") as f:
            f.truncate(good_bytes)
        print("  removed %d damaged bytes from the end of the data file." % (size - good_bytes))
    if last is not None:
        state["cursor"] = {"address": last["depositAddress"], "memo": last.get("depositMemo")}
    state["rows_saved"] = count
    state["pages"] = (count + PAGE_SIZE - 1) // PAGE_SIZE
    print("  rebuilt: %d swaps, oldest %s" % (
        count, utc(state["oldest_ts"]) if state["oldest_ts"] else "?"))
    return state


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())  # make sure it is really on disk before swapping it in
    os.replace(tmp, path)  # atomic: never leaves a half-written file


def repair_data_file(data_path, rows_saved):
    """
    After a power cut or crash, make the data file match the bookmark exactly.

    The script saves a page of rows FIRST and moves the bookmark SECOND. If the
    computer dies in between, the file can hold (a) a complete page the bookmark
    does not know about, and/or (b) a half-written last line. We cut the file
    back to exactly `rows_saved` complete rows, so resuming never leaves
    duplicates or broken lines.
    """
    if not os.path.exists(data_path):
        if rows_saved:
            sys.exit("state.json says %d rows are saved but %s is missing. "
                     "Move the whole data folder aside and start fresh." % (rows_saved, data_path))
        return
    good_bytes = 0
    complete = 0
    with open(data_path, "rb") as f:
        for line in f:
            if complete >= rows_saved:
                break
            if not line.endswith(b"\n"):
                break  # half-written last line
            good_bytes += len(line)
            complete += 1
    if complete < rows_saved:
        sys.exit("The data file has only %d complete rows but the bookmark says %d. "
                 "Something deleted data. Please send me this message." % (complete, rows_saved))
    size = os.path.getsize(data_path)
    if size > good_bytes:
        with open(data_path, "r+b") as f:
            f.truncate(good_bytes)
        print("Repaired after an interrupted run: removed %d leftover bytes. "
              "Kept %d complete rows." % (size - good_bytes, complete))


# --------------------------------------------------------------------------
# Talking to the API
# --------------------------------------------------------------------------
def fetch_page(base_url, token, params, retry_wait, max_attempts=8):
    """Fetch one page. Retries on rate limits, server errors and network hiccups."""
    url = base_url.rstrip("/") + "/transactions?" + urllib.parse.urlencode(params)
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    for attempt in range(1, max_attempts + 1):
        wait = retry_wait * attempt
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, list):
                raise ValueError("expected a list of swaps, got: " + str(type(data)))
            return data
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code in (401, 403):
                sys.exit(
                    "The API rejected the token (HTTP %d). Check that you pasted the "
                    "full Explorer token, and that it has not been deleted.\n%s"
                    % (e.code, detail)
                )
            if e.code == 429:
                print("  rate limit hit (429) - waiting %.0fs..." % wait)
            elif e.code >= 500:
                print("  server error %d - waiting %.0fs..." % (e.code, wait))
            else:
                sys.exit("The API returned HTTP %d: %s" % (e.code, detail))
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            print("  network/parse problem (%s) - waiting %.0fs..." % (e, wait))
        time.sleep(wait)
    sys.exit("Giving up after %d attempts. Run the script again to resume." % max_attempts)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Download NEAR Intents swap history.")
    ap.add_argument("--out", default="data", help="output folder (default: data)")
    ap.add_argument("--since", help="stop once swaps are older than this date, YYYY-MM-DD")
    ap.add_argument("--max-pages", type=int, help="stop after this many pages (for tests)")
    ap.add_argument("--delay", type=float, default=5.5,
                    help="seconds to wait between requests (default 5.5; API limit is 1 per 5s)")
    ap.add_argument("--retry-wait", type=float, default=10.0, help=argparse.SUPPRESS)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help=argparse.SUPPRESS)
    ap.add_argument("--force", action="store_true", help="ignore a 'finished' marker and ask again")
    args = ap.parse_args()

    token = get_token()
    since_ts = None
    if args.since:
        since_ts = int(datetime.strptime(args.since, "%Y-%m-%d")
                       .replace(tzinfo=timezone.utc).timestamp())

    os.makedirs(args.out, exist_ok=True)
    data_path = os.path.join(args.out, "intents_swaps.jsonl")
    state_path = os.path.join(args.out, "state.json")
    if not os.path.exists(state_path) and os.path.exists(data_path) and os.path.getsize(data_path) > 0:
        sys.exit("Found %s but no state.json bookmark. To avoid mixing data, rename the "
                 "'%s' folder (for example to data_old) and run again." % (data_path, args.out))
    state = load_state(state_path, data_path)
    print("Checking saved data...")
    repair_data_file(data_path, state["rows_saved"])

    if state["finished"] and not args.force:
        print("Already downloaded everything (%d swaps). Use --force to check again."
              % state["rows_saved"])
        return
    if since_ts and state["oldest_ts"] and state["oldest_ts"] < since_ts:
        print("Already reached %s (oldest saved swap: %s). Nothing to do."
              % (args.since, utc(state["oldest_ts"])))
        return

    if state["rows_saved"]:
        print("Resuming: %d swaps saved so far, oldest %s"
              % (state["rows_saved"], utc(state["oldest_ts"])))
    else:
        print("Starting a fresh download.")
    print("Press Ctrl+C at any time to pause; run the same command to resume.\n")

    pages_this_run = 0
    try:
        while True:
            params = {"numberOfTransactions": PAGE_SIZE, "direction": "next"}
            if state["cursor"]:
                params["lastDepositAddress"] = state["cursor"]["address"]
                if state["cursor"].get("memo"):
                    params["lastDepositMemo"] = state["cursor"]["memo"]

            rows = fetch_page(args.base_url, token, params, args.retry_wait)

            if not rows:
                state["finished"] = True
                save_state(state_path, state)
                print("\nDone. The API has no older swaps. Total saved: %d" % state["rows_saved"])
                break

            # 1) save the raw rows, 2) only then move the bookmark
            with open(data_path, "a", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, separators=(",", ":")) + "\n")
                f.flush()
                os.fsync(f.fileno())

            last = rows[-1]
            state["cursor"] = {"address": last["depositAddress"], "memo": last.get("depositMemo")}
            state["rows_saved"] += len(rows)
            state["pages"] += 1
            stamps = [r["createdAtTimestamp"] for r in rows if "createdAtTimestamp" in r]
            if stamps:
                if state["newest_ts"] is None:
                    state["newest_ts"] = max(stamps)
                state["oldest_ts"] = min(stamps)
            save_state(state_path, state)
            pages_this_run += 1

            print("page %d | +%d | total %d | oldest so far: %s"
                  % (state["pages"], len(rows), state["rows_saved"],
                     utc(state["oldest_ts"]) if state["oldest_ts"] else "?"))

            if since_ts and state["oldest_ts"] and state["oldest_ts"] < since_ts:
                print("\nReached %s. Stopping (swaps older than that are included in the last page)."
                      % args.since)
                break
            if args.max_pages and pages_this_run >= args.max_pages:
                print("\nStopped after %d page(s) as requested." % pages_this_run)
                break

            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nPaused. Progress is saved - run the same command to continue.")


if __name__ == "__main__":
    main()

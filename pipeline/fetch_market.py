#!/usr/bin/env python3
"""
fetch_market.py - price, market cap, supply and peer data (no keys needed).

Writes small, dated snapshot files to data/market/:
  defillama_intents_daily.csv   NEAR Intents volume, gross fees, NEAR captured revenue per day (DefiLlama)
  near_price_daily.csv          NEAR/USD daily price (DefiLlama coins API, CoinGecko id "near")
  near_chain_snapshot.json      total supply, validator stake, inflation settings (NEAR JSON-RPC)
  peers.csv                     price, market cap, FDV (CoinGecko) + 30-day chain fees/revenue (DefiLlama)
  placebo_daily.csv             BTC/USD and Solana DEX volume per day - control series for the lead-lag tests
  _fetched.json                 when each source was read and from which URL

Sources and their terms:
  DefiLlama  https://api.llama.fi, https://coins.llama.fi   (free public API)
  CoinGecko  https://api.coingecko.com/api/v3                (free public API, rate-limited)
  NEAR RPC   https://free.rpc.fastnear.com                   (free public endpoint)

Standard library only.   Usage:  python pipeline/fetch_market.py [--since 2026-01-01]
"""

import argparse
import csv
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

USER_AGENT = "near-thesis-engine/0.1"
LLAMA = "https://api.llama.fi"
COINS = "https://coins.llama.fi"
GECKO = "https://api.coingecko.com/api/v3"
RPC = "https://free.rpc.fastnear.com"
PEERS = [  # (label, CoinGecko id, DefiLlama chain slug)
    ("NEAR", "near", "near"),
    ("Solana", "solana", "solana"),
    ("Sui", "sui", "sui"),
    ("Aptos", "aptos", "aptos"),
    ("TON", "the-open-network", "ton"),
]
YOCTO = 10 ** 24


def get_json(url, data=None, attempts=4):
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": USER_AGENT, "Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if i == attempts - 1:
                raise
            print("  problem with %s (%s), retrying..." % (url.split("?")[0], e))
            time.sleep(5 * (i + 1))


def day(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def chart(payload):
    return {day(t): v for t, v in payload.get("totalDataChart", [])}


def fetch_intents(llama, since):
    vol = get_json(llama + "/summary/dexs/near-intents?dataType=dailyVolume")
    fees = get_json(llama + "/summary/fees/near-intents?dataType=dailyFees")
    rev = get_json(llama + "/summary/fees/near-intents?dataType=dailyRevenue")
    v, f, r = chart(vol), chart(fees), chart(rev)
    days = sorted(d for d in set(v) | set(f) | set(r) if d >= since)
    rows = [[d, v.get(d, ""), f.get(d, ""), r.get(d, "")] for d in days]
    meta = {"methodology": fees.get("methodology"), "volume_methodology_url": vol.get("methodologyURL")}
    return rows, meta


def fetch_price(coins, since, coin="near"):
    start = int(datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    span = int((time.time() - start) // 86400) + 1
    d = get_json("%s/chart/coingecko:%s?start=%d&span=%d&period=1d" % (coins, coin, start, span))
    pts = d["coins"]["coingecko:" + coin]["prices"]
    # daily points sit a few seconds either side of 00:00 UTC; round to the nearest midnight so each lands on its own day
    return [[day(round(p["timestamp"] / 86400) * 86400), round(p["price"], 6)] for p in pts]


def fetch_placebo(llama, coins, since):
    """Control series: BTC price (the market factor) and Solana DEX volume (crypto activity unrelated to NEAR)."""
    btc = dict(fetch_price(coins, since, "bitcoin"))
    sol = chart(get_json(llama + "/overview/dexs/solana?excludeTotalDataChartBreakdown=true&dataType=dailyVolume"))
    days = sorted(d for d in set(btc) | set(sol) if d >= since)
    return [[d, btc.get(d, ""), sol.get(d, "")] for d in days]


def rpc_call(rpc, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": "1", "method": method, "params": params}).encode()
    out = get_json(rpc, data=body)
    if "result" not in out:
        raise RuntimeError("RPC %s failed: %s" % (method, out.get("error")))
    return out["result"]


def fetch_chain(rpc):
    hdr = rpc_call(rpc, "block", {"finality": "final"})["header"]
    val = rpc_call(rpc, "validators", [None])
    cfg = rpc_call(rpc, "EXPERIMENTAL_protocol_config", {"finality": "final"})
    num, den = cfg["max_inflation_rate"]
    pnum, pden = cfg["protocol_reward_rate"]
    supply = int(hdr["total_supply"]) / YOCTO
    stake = sum(int(v["stake"]) for v in val["current_validators"]) / YOCTO
    return {
        "block_height": hdr["height"],
        "block_time_utc": datetime.fromtimestamp(int(hdr["timestamp_nanosec"]) / 1e9, tz=timezone.utc).isoformat(timespec="seconds"),
        "total_supply_near": round(supply, 0),
        "current_validators": len(val["current_validators"]),
        "current_validator_stake_near": round(stake, 0),
        "staked_share_of_supply": round(stake / supply, 4),
        "max_inflation_rate": num / den,
        "protocol_reward_rate": pnum / pden if pden else 0.0,
        "protocol_version": cfg.get("protocol_version"),
        "epoch_length_blocks": cfg.get("epoch_length"),
    }


def fetch_peers(gecko, llama):
    ids = ",".join(p[1] for p in PEERS)
    mk = {c["id"]: c for c in get_json("%s/coins/markets?vs_currency=usd&ids=%s" % (gecko, ids))}
    rows = []
    for label, gid, slug in PEERS:
        c = mk.get(gid, {})
        fees = get_json("%s/summary/fees/%s?dataType=dailyFees" % (llama, slug))
        rev = get_json("%s/summary/fees/%s?dataType=dailyRevenue" % (llama, slug))
        rows.append([label, c.get("current_price"), c.get("market_cap"), c.get("fully_diluted_valuation"),
                     c.get("circulating_supply"), fees.get("total30d"), rev.get("total30d"), c.get("last_updated")])
        time.sleep(0.5)
    return rows


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def run(out, since, llama=LLAMA, coins=COINS, gecko=GECKO, rpc=RPC):
    os.makedirs(out, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log = {}

    rows, meta = fetch_intents(llama, since)
    write_csv(os.path.join(out, "defillama_intents_daily.csv"),
              ["day", "intents_volume_usd", "intents_gross_fees_usd", "near_captured_revenue_usd"], rows)
    log["defillama_intents_daily.csv"] = {"fetched_utc": now, "source": llama + "/summary/{dexs,fees}/near-intents",
                                          "rows": len(rows), "defillama_methodology": meta}
    print("Intents daily: %d days" % len(rows))

    prices = fetch_price(coins, since)
    write_csv(os.path.join(out, "near_price_daily.csv"), ["day", "near_usd"], prices)
    log["near_price_daily.csv"] = {"fetched_utc": now, "source": coins + "/chart/coingecko:near", "rows": len(prices)}
    print("NEAR price: %d days, last %s = $%s" % (len(prices), prices[-1][0], prices[-1][1]))

    plc = fetch_placebo(llama, coins, since)
    write_csv(os.path.join(out, "placebo_daily.csv"), ["day", "btc_usd", "solana_dex_volume_usd"], plc)
    log["placebo_daily.csv"] = {"fetched_utc": now, "source": coins + "/chart/coingecko:bitcoin + " + llama + "/overview/dexs/solana",
                                "rows": len(plc)}
    print("Placebo series: %d days" % len(plc))

    snap = fetch_chain(rpc)
    snap["fetched_utc"] = now
    with open(os.path.join(out, "near_chain_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
    log["near_chain_snapshot.json"] = {"fetched_utc": now, "source": rpc + " (block, validators, EXPERIMENTAL_protocol_config)"}
    print("Chain: supply %.0f NEAR, stake %.0f NEAR, max inflation %.4f"
          % (snap["total_supply_near"], snap["current_validator_stake_near"], snap["max_inflation_rate"]))

    peers = fetch_peers(gecko, llama)
    write_csv(os.path.join(out, "peers.csv"),
              ["chain", "price_usd", "market_cap_usd", "fdv_usd", "circulating_supply",
               "chain_fees_30d_usd", "chain_revenue_30d_usd", "price_last_updated"], peers)
    log["peers.csv"] = {"fetched_utc": now, "source": gecko + "/coins/markets + " + llama + "/summary/fees/<chain>",
                        "note": "chain fees/revenue are DefiLlama's L1 gas-fee figures; NEAR Intents revenue is separate"}
    print("Peers: %d chains" % len(peers))

    with open(os.path.join(out, "_fetched.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    return log


def main():
    ap = argparse.ArgumentParser(description="Fetch price, supply and peer snapshots.")
    ap.add_argument("--out", default=os.path.join("data", "market"))
    ap.add_argument("--since", default="2026-01-01")
    args = ap.parse_args()
    run(args.out, args.since)


if __name__ == "__main__":
    main()

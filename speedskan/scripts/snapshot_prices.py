#!/usr/bin/env python3
"""Append a dated price snapshot to price_history.csv.

By default it snapshots the current estimate (Est_Low/High from items.csv) for
every item as source 'est' — use this once to seed the baseline, and any time you
want to mark "today's working estimate" into the time series.

Real multi-source prices (pricecharting, ebay-sold, etc.) are appended to
price_history.csv as additional dated rows (one row per source per item) either
by hand or by Claude during a price refresh — this script does NOT invent those.

price_history.csv columns:  Date, System, Title, Source, Low, High, Median

Usage:
    python snapshot_prices.py [DATA_DIR]
"""
import csv, os, sys, datetime

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
ITEMS = os.path.join(DATA_DIR, "items.csv")
HIST = os.path.join(DATA_DIR, "price_history.csv")
TODAY = datetime.date.today().isoformat()
HEADER = ["Date", "System", "Title", "Source", "Low", "High", "Median"]

def main():
    if not os.path.exists(ITEMS):
        print(f"No items.csv in {DATA_DIR}"); sys.exit(1)
    with open(ITEMS, newline="", encoding="utf-8") as f:
        items = list(csv.DictReader(f))

    # skip items already snapshotted with source 'est' today (idempotent)
    seen = set()
    if os.path.exists(HIST):
        with open(HIST, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["Date"] == TODAY and r["Source"] == "est":
                    seen.add((r["System"], r["Title"]))

    new_file = not os.path.exists(HIST)
    added = 0
    with open(HIST, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(HEADER)
        for it in items:
            key = (it["System"], it["Title"])
            if key in seen:
                continue
            try:
                lo = int(float(it["Est_Low"])); hi = int(float(it["Est_High"]))
            except (ValueError, KeyError):
                continue
            med = round((lo + hi) / 2)
            w.writerow([TODAY, it["System"], it["Title"], "est", lo, hi, med])
            added += 1

    print(f"Snapshot {TODAY}: added {added} 'est' rows to price_history.csv "
          f"({len(seen)} already present today).")

if __name__ == "__main__":
    main()

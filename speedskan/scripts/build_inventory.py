#!/usr/bin/env python3
"""Rebuild inventory.csv (catalog + totals) from items.csv.

Reads items.csv and writes inventory.csv in the given data directory
(default: current working directory), then prints a totals summary.

Usage:
    python build_inventory.py [DATA_DIR]
"""
import csv, os, sys

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
SRC = os.path.join(DATA_DIR, "items.csv")
OUT = os.path.join(DATA_DIR, "inventory.csv")

SYS_ORDER = ["NES", "SNES", "Nintendo 64", "GameCube", "Wii",
             "Game Boy", "Game Boy Color", "Game Boy Advance", "Virtual Boy",
             "Master System", "Genesis", "Sega 32X", "Sega Saturn",
             "Game Gear", "Dreamcast", "Other"]
TIER_ORDER = {"Gold": 0, "Maybe": 1, "Cruff": 2}

def load():
    if not os.path.exists(SRC):
        print(f"No items.csv found in {DATA_DIR}. Create it with the header row:\n"
              "System,Title,Completeness,Tier,Est_Low,Est_High,Dealer,Notes,Status")
        sys.exit(1)
    with open(SRC, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("Est_Low", "Est_High", "Dealer"):
            r[k] = int(float(r[k])) if str(r.get(k, "")).strip() else 0
    return rows

def main():
    rows = load()

    def key(r):
        s = SYS_ORDER.index(r["System"]) if r["System"] in SYS_ORDER else len(SYS_ORDER)
        return (s, TIER_ORDER.get(r["Tier"], 9), r["Title"].lower())
    rows.sort(key=key)

    tiers = {"Gold": [0, 0, 0, 0], "Maybe": [0, 0, 0, 0], "Cruff": [0, 0, 0, 0]}  # low, high, dealer, count
    for r in rows:
        t = tiers.get(r["Tier"])
        if t:
            t[0] += r["Est_Low"]; t[1] += r["Est_High"]; t[2] += r["Dealer"]; t[3] += 1

    all_low = sum(t[0] for t in tiers.values())
    all_high = sum(t[1] for t in tiers.values())
    all_dealer = sum(t[2] for t in tiers.values())
    all_count = sum(t[3] for t in tiers.values())

    fields = ["System", "Title", "Completeness", "Tier", "Est_Low", "Est_High", "Dealer", "Notes", "Status"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in rows:
            w.writerow([r.get(k, "") for k in fields])
        w.writerow([""] * len(fields))
        w.writerow(["TOTALS", "Cruff -> sell to dealer as lot", "", "Cruff",
                    tiers["Cruff"][0], tiers["Cruff"][1], tiers["Cruff"][2],
                    f"{tiers['Cruff'][3]} items; dealer lot ~${tiers['Cruff'][2]}", ""])
        w.writerow(["TOTALS", "Gold -> sell individually (retail)", "", "Gold",
                    tiers["Gold"][0], tiers["Gold"][1], tiers["Gold"][2],
                    f"{tiers['Gold'][3]} items; keep & list yourself", ""])
        w.writerow(["TOTALS", "Maybe -> your call", "", "Maybe",
                    tiers["Maybe"][0], tiers["Maybe"][1], tiers["Maybe"][2],
                    f"{tiers['Maybe'][3]} items", ""])
        w.writerow(["TOTALS", "ALL ITEMS retail value", "", "",
                    all_low, all_high, "", "Sum of Est_Low / Est_High", ""])
        w.writerow(["TOTALS", "ALL ITEMS dealer value", "", "",
                    "", "", all_dealer, "If you dumped everything to dealer", ""])

    print(f"Items: {all_count}")
    for name in ("Gold", "Maybe", "Cruff"):
        t = tiers[name]
        print(f"  {name:6} {t[3]:3} items  retail ${t[0]}-{t[1]}  dealer ${t[2]}")
    print(f"  ALL    {all_count:3} items  retail ${all_low}-{all_high}  dealer ${all_dealer}")

if __name__ == "__main__":
    main()

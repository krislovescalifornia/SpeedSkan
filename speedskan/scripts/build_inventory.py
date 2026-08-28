#!/usr/bin/env python3
"""Rebuild inventory.csv + inventory.html from items.csv and price_history.csv.

items.csv        -> the catalog + current working estimate (append-only source of truth)
price_history.csv-> dated price observations per item per source (the time series)

Outputs:
  inventory.csv   -> catalog with tracking columns + totals (printable/sortable)
  inventory.html  -> visual dashboard; HOT items (price doubled) are red, gains green

Tracking per item is derived from price_history: current multi-source low/high/median
(latest date), first-seen median, lowest/highest median ever, % change, and a flag.

Usage:
    python build_inventory.py [DATA_DIR]
"""
import csv, os, sys, html, statistics, datetime
from collections import defaultdict

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
ITEMS = os.path.join(DATA_DIR, "items.csv")
HIST = os.path.join(DATA_DIR, "price_history.csv")
OUT_CSV = os.path.join(DATA_DIR, "inventory.csv")
OUT_HTML = os.path.join(DATA_DIR, "inventory.html")

SYS_ORDER = ["NES", "SNES", "Nintendo 64", "GameCube", "Wii",
             "Game Boy", "Game Boy Color", "Game Boy Advance", "Virtual Boy",
             "Master System", "Genesis", "Sega 32X", "Sega Saturn",
             "Game Gear", "Dreamcast", "Other"]
TIER_ORDER = {"Gold": 0, "Maybe": 1, "Cruff": 2}


def load_items():
    if not os.path.exists(ITEMS):
        print("No items.csv found. Header:\n"
              "System,Title,Completeness,Tier,Est_Low,Est_High,Dealer,Notes,Status")
        sys.exit(1)
    with open(ITEMS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("Est_Low", "Est_High", "Dealer"):
            r[k] = int(float(r[k])) if str(r.get(k, "")).strip() else 0
    return rows


def load_history():
    """key (System,Title) -> {date -> list of (low,high,median,source)}"""
    hist = defaultdict(lambda: defaultdict(list))
    if not os.path.exists(HIST):
        return hist
    with open(HIST, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                lo, hi, md = int(float(r["Low"])), int(float(r["High"])), int(float(r["Median"]))
            except (ValueError, KeyError):
                continue
            hist[(r["System"], r["Title"])][r["Date"]].append((lo, hi, md, r.get("Source", "")))
    return hist


def track(item, hist):
    """Return tracking dict for one item using its price history (fallback: est)."""
    key = (item["System"], item["Title"])
    dates = hist.get(key)
    if not dates:
        md = round((item["Est_Low"] + item["Est_High"]) / 2)
        return dict(cur_low=item["Est_Low"], cur_high=item["Est_High"], cur_med=md,
                    first=md, low_seen=md, high_seen=md, pct=0.0, flag="NEW",
                    sources=0, series=[md])
    # per-date aggregation. Real sources (pricecharting/comps/etc.) override 'est'
    # placeholders on the same date; 'est' is only used until a real comp exists.
    per_date = {}
    for d, obs in dates.items():
        real = [o for o in obs if o[3] != "est"]
        use = real if real else obs
        lo = min(o[0] for o in use)
        hi = max(o[1] for o in use)
        md = round(statistics.median([o[2] for o in use]))
        per_date[d] = (lo, hi, md, len(real))   # count of real (non-est) sources
    ordered = sorted(per_date.items())               # by date string (ISO sorts fine)
    first_med = ordered[0][1][2]
    cur_lo, cur_hi, cur_med, n_src = ordered[-1][1]
    med_series = [v[2] for _, v in ordered]
    low_seen, high_seen = min(med_series), max(med_series)
    pct = ((cur_med - first_med) / first_med * 100.0) if first_med else 0.0
    if first_med > 0 and cur_med >= 2 * first_med:
        flag = "HOT"
    elif pct >= 10:
        flag = "UP"
    elif pct <= -10:
        flag = "DOWN"
    else:
        flag = "FLAT"
    return dict(cur_low=cur_lo, cur_high=cur_hi, cur_med=cur_med, first=first_med,
                low_seen=low_seen, high_seen=high_seen, pct=pct, flag=flag,
                sources=n_src, series=med_series)


def main():
    items = load_items()
    hist = load_history()

    def key(r):
        s = SYS_ORDER.index(r["System"]) if r["System"] in SYS_ORDER else len(SYS_ORDER)
        return (s, TIER_ORDER.get(r["Tier"], 9), r["Title"].lower())
    items.sort(key=key)

    for it in items:
        it["_t"] = track(it, hist)

    # tier totals (retail low/high, median-portfolio, dealer)
    tiers = {t: dict(low=0, high=0, med=0, dealer=0, n=0) for t in ("Gold", "Maybe", "Cruff")}
    for it in items:
        t = tiers.get(it["Tier"])
        if not t:
            continue
        tr = it["_t"]
        t["low"] += tr["cur_low"]; t["high"] += tr["cur_high"]; t["med"] += tr["cur_med"]
        t["dealer"] += it["Dealer"]; t["n"] += 1
    A = lambda k: sum(tiers[t][k] for t in tiers)

    # ---- inventory.csv ----
    cols = ["System", "Title", "Completeness", "Tier", "Cur_Low", "Cur_High", "Median",
            "First", "Low_Seen", "High_Seen", "Pct_Chg", "Flag", "Sources",
            "Dealer", "Notes", "Status"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for it in items:
            tr = it["_t"]
            w.writerow([it["System"], it["Title"], it["Completeness"], it["Tier"],
                        tr["cur_low"], tr["cur_high"], tr["cur_med"], tr["first"],
                        tr["low_seen"], tr["high_seen"], f"{tr['pct']:+.0f}%", tr["flag"],
                        tr["sources"], it["Dealer"], it.get("Notes", ""), it.get("Status", "")])
        w.writerow([""] * len(cols))
        for name in ("Gold", "Maybe", "Cruff"):
            t = tiers[name]
            w.writerow(["TOTALS", f"{name} tier", "", name, t["low"], t["high"], t["med"],
                        "", "", "", "", "", "", t["dealer"], f"{t['n']} items", ""])
        w.writerow(["TOTALS", "ALL ITEMS", "", "", A("low"), A("high"), A("med"),
                    "", "", "", "", "", "", A("dealer"), f"{A('n')} items", ""])

    write_html(items, tiers, A)
    # console summary
    print(f"Items: {A('n')}")
    for name in ("Gold", "Maybe", "Cruff"):
        t = tiers[name]
        print(f"  {name:6} {t['n']:3} items  retail ${t['low']}-{t['high']}  median ${t['med']}  dealer ${t['dealer']}")
    print(f"  ALL    {A('n'):3} items  retail ${A('low')}-{A('high')}  median ${A('med')}  dealer ${A('dealer')}")
    hot = [it for it in items if it["_t"]["flag"] == "HOT"]
    if hot:
        print(f"  HOT (doubled): {len(hot)} -> " + ", ".join(i["Title"] for i in hot[:8]))


def write_html(items, tiers, A):
    gen = datetime.date.today().isoformat()

    def card(label, t, color):
        return (f'<div class="card"><div class="clabel" style="color:{color}">{label}</div>'
                f'<div class="cnum">${t["low"]:,}&ndash;{t["high"]:,}</div>'
                f'<div class="csub">median ${t["med"]:,} &middot; {t["n"]} items &middot; dealer ${t["dealer"]:,}</div></div>')

    allt = dict(low=A("low"), high=A("high"), med=A("med"), dealer=A("dealer"), n=A("n"))
    cards = (card("Gold", tiers["Gold"], "#e0b100") + card("Maybe", tiers["Maybe"], "#c88") +
             card("Cruff", tiers["Cruff"], "#8a94a6") + card("All", allt, "#5aa0ff"))

    rows_html = []
    cur_sys = None
    for it in items:
        if it["System"] != cur_sys:
            cur_sys = it["System"]
            rows_html.append(f'<tr class="syshead"><td colspan="11">{html.escape(cur_sys)}</td></tr>')
        tr = it["_t"]
        flag = tr["flag"]
        rowcls = "hot" if flag == "HOT" else ""
        pct = tr["pct"]
        pcol = "#3fae63" if pct > 0.5 else ("#e5534b" if pct < -0.5 else "#8a94a6")
        badge = {"HOT": '<span class="b hot">🔥 HOT</span>',
                 "UP": '<span class="b up">▲</span>',
                 "DOWN": '<span class="b down">▼</span>',
                 "FLAT": '<span class="b flat">●</span>',
                 "NEW": '<span class="b new">new</span>'}[flag]
        tiercls = it["Tier"].lower()
        rows_html.append(
            f'<tr class="{rowcls}">'
            f'<td class="title">{html.escape(it["Title"])}'
            f'<div class="meta">{html.escape(it["Completeness"])}</div></td>'
            f'<td><span class="tier {tiercls}">{it["Tier"]}</span></td>'
            f'<td class="num">${tr["cur_low"]}</td>'
            f'<td class="num">${tr["cur_high"]}</td>'
            f'<td class="num med">${tr["cur_med"]}</td>'
            f'<td class="num">${tr["first"]}</td>'
            f'<td class="num">${tr["low_seen"]}</td>'
            f'<td class="num">${tr["high_seen"]}</td>'
            f'<td class="num" style="color:{pcol}">{pct:+.0f}%</td>'
            f'<td>{badge}</td>'
            f'<td class="num src">{tr["sources"] if tr["sources"] else "est"}</td>'
            f'</tr>')

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SpeedSkan Tracker</title>
<style>
  :root {{ color-scheme: dark; --bg:#0f1115; --panel:#171a21; --line:#262b36; --tx:#e8eaed; --mut:#8a94a6; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--tx);
    font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif; padding:20px; }}
  h1 {{ font-size:20px; margin:0 0 2px; }}
  .sub {{ color:var(--mut); font-size:13px; margin-bottom:16px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 16px; min-width:180px; }}
  .clabel {{ font-size:12px; font-weight:700; letter-spacing:.4px; text-transform:uppercase; }}
  .cnum {{ font-size:20px; font-weight:700; margin-top:4px; }}
  .csub {{ font-size:12px; color:var(--mut); margin-top:2px; }}
  .wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; min-width:820px; }}
  th, td {{ padding:7px 10px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap; }}
  th {{ position:sticky; top:0; background:#12151b; color:var(--mut); font-weight:600; font-size:11px;
        text-transform:uppercase; letter-spacing:.4px; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.med {{ font-weight:700; }}
  td.src {{ color:var(--mut); }}
  .title {{ font-weight:600; }}
  .meta {{ color:var(--mut); font-size:11px; font-weight:400; }}
  .syshead td {{ background:#10131a; color:#9fb0ff; font-weight:700; font-size:12px;
                 text-transform:uppercase; letter-spacing:.6px; }}
  tr.hot td {{ background:rgba(229,83,75,.16); }}
  tr.hot td.title {{ box-shadow: inset 3px 0 0 #e5534b; }}
  .tier {{ font-size:11px; font-weight:700; padding:2px 7px; border-radius:20px; }}
  .tier.gold {{ background:rgba(224,177,0,.18); color:#e9c04a; }}
  .tier.maybe {{ background:rgba(200,136,136,.16); color:#d29a9a; }}
  .tier.cruff {{ background:rgba(138,148,166,.14); color:#9aa4b4; }}
  .b {{ font-size:11px; font-weight:700; padding:1px 6px; border-radius:6px; }}
  .b.hot {{ background:#e5534b; color:#fff; }}
  .b.up {{ color:#3fae63; }} .b.down {{ color:#e5534b; }}
  .b.flat, .b.new {{ color:var(--mut); }}
  .legend {{ color:var(--mut); font-size:12px; margin-top:12px; }}
</style></head><body>
<h1>SpeedSkan &mdash; Collection Tracker</h1>
<div class="sub">Generated {gen} &middot; {allt['n']} items &middot; prices are loose/used resale estimates &amp; researched comps</div>
<div class="cards">{cards}</div>
<div class="wrap"><table>
<thead><tr>
<th>Item</th><th>Tier</th><th>Low</th><th>High</th><th>Median</th>
<th>First</th><th>Lo&middot;ever</th><th>Hi&middot;ever</th><th>&Delta;%</th><th>Trend</th><th>Src</th>
</tr></thead>
<tbody>
{''.join(rows_html)}
</tbody></table></div>
<div class="legend">🔥 HOT = current median has doubled vs. first tracked price (row highlighted red) &middot;
▲ up &gt;10% &middot; ▼ down &gt;10% &middot; Src = number of price sources on the latest date.
Δ% and HOT become meaningful after a price refresh adds a newer dated snapshot.</div>
</body></html>"""
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    main()

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
import csv, os, sys, html, statistics, datetime, json
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

BRAND = {
    "NES": "Nintendo", "SNES": "Nintendo", "Nintendo 64": "Nintendo", "GameCube": "Nintendo",
    "Wii": "Nintendo", "Game Boy": "Nintendo", "Game Boy Color": "Nintendo",
    "Game Boy Advance": "Nintendo", "Virtual Boy": "Nintendo",
    "Nintendo 3DS": "Nintendo", "Nintendo DS": "Nintendo", "Switch": "Nintendo",
    "Master System": "Sega", "Genesis": "Sega", "Sega 32X": "Sega", "Sega Saturn": "Sega",
    "Game Gear": "Sega", "Dreamcast": "Sega", "Sega CD": "Sega",
    "PlayStation": "Sony", "PlayStation 2": "Sony", "PS1": "Sony", "PS2": "Sony", "PSP": "Sony",
    "Xbox": "Microsoft",
    "Atari 2600": "Atari", "Atari 7800": "Atari", "Atari 5200": "Atari",
    "Atari Lynx": "Atari", "Atari Jaguar": "Atari",
}


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




TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SpeedSkan Dashboard</title>
<style>
  :root{ color-scheme:dark; --bg:#0e1015; --panel:#161a22; --panel2:#12151c; --line:#252b37;
         --tx:#e8eaed; --mut:#8b95a7; --accent:#5aa0ff; --hot:#e5534b; --up:#3fae63; }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--tx);
       font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;padding:20px;max-width:1400px;margin:0 auto;}
  h1{font-size:22px;margin:0 0 2px;} h3{font-size:13px;margin:0 0 10px;color:var(--mut);
     text-transform:uppercase;letter-spacing:.5px;font-weight:600;}
  .sub{color:var(--mut);font-size:13px;margin-bottom:18px;}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px;}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;}
  .kl{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px;font-weight:600;}
  .kn{font-size:24px;font-weight:800;margin-top:5px;} .ks{font-size:12px;color:var(--mut);margin-top:2px;}
  .section-t{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px;
             font-weight:700;margin:6px 0 10px;} .section-t span{color:#5c6575;font-weight:500;text-transform:none;}
  .grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:18px;}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;}
  .bars{display:flex;flex-direction:column;gap:7px;}
  .bar{display:grid;grid-template-columns:110px 1fr auto;align-items:center;gap:10px;cursor:pointer;
       padding:3px 4px;border-radius:8px;}
  .bar:hover{background:#1c2130;} .bar.act{background:#1d2740;outline:1px solid #2f4d86;}
  .bk{font-size:12px;color:var(--tx);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .btrack{background:#0e1219;border-radius:6px;height:16px;overflow:hidden;}
  .bfill{height:100%;background:linear-gradient(90deg,#3d6fd0,#5aa0ff);border-radius:6px;}
  .bv{font-size:12px;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap;}
  .bv .bn{color:var(--mut);margin-left:6px;font-size:11px;}
  .filters{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end;background:var(--panel2);
           border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin-bottom:18px;}
  .fg{display:flex;flex-direction:column;gap:6px;} .fg label{font-size:11px;color:var(--mut);
     text-transform:uppercase;letter-spacing:.5px;font-weight:600;}
  .chips{display:flex;gap:6px;flex-wrap:wrap;}
  .chip{font:inherit;font-size:12px;padding:5px 11px;border-radius:20px;border:1px solid var(--line);
        background:#12151c;color:var(--tx);cursor:pointer;}
  .chip.on{background:#1d2740;border-color:#3f5fa0;color:#cfe0ff;}
  .chip span{color:var(--mut);margin-left:4px;}
  select,input{font:inherit;font-size:13px;padding:6px 10px;border-radius:9px;border:1px solid var(--line);
               background:#12151c;color:var(--tx);}
  .clear{color:var(--mut);font-size:12px;cursor:pointer;text-decoration:underline;padding-bottom:8px;}
  .lb{list-style:none;margin:0;padding:0;} .lb li{display:grid;grid-template-columns:22px 1fr auto;
      align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid #1c212b;font-size:13px;}
  .lb li:last-child{border-bottom:0;} .lb .rk{color:var(--mut);font-size:12px;text-align:center;}
  .lb .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;} .lb .vl{font-weight:700;font-variant-numeric:tabular-nums;}
  .lb .vl.up{color:var(--up);} .lb .vl.down{color:var(--hot);} .lb .empty{color:var(--mut);grid-column:1/4;text-align:center;padding:14px 0;}
  .stats{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;}
  .st{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #1c212b;padding:5px 0;font-size:13px;}
  .st .stl{color:var(--mut);} .st .stv{font-weight:700;font-variant-numeric:tabular-nums;text-align:right;}
  .tablewrap{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden;}
  .tbar{padding:10px 14px;border-bottom:1px solid var(--line);font-size:12px;color:var(--mut);}
  .scroll{overflow-x:auto;} table{border-collapse:collapse;width:100%;font-size:13px;min-width:900px;}
  th,td{padding:8px 11px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;}
  th{position:sticky;top:0;background:#12151b;color:var(--mut);font-weight:600;font-size:11px;
     text-transform:uppercase;letter-spacing:.4px;cursor:pointer;user-select:none;}
  th.num,td.num{text-align:right;font-variant-numeric:tabular-nums;} th.sorted{color:var(--accent);}
  td.md{font-weight:700;} .ti{font-weight:600;} .mt{color:var(--mut);font-size:11px;font-weight:400;}
  tr.hot td{background:rgba(229,83,75,.14);} tr.hot td.ti{box-shadow:inset 3px 0 0 var(--hot);}
  .tier{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;}
  .tier.gold{background:rgba(224,177,0,.18);color:#e9c04a;} .tier.maybe{background:rgba(200,136,136,.16);color:#d29a9a;}
  .tier.cruff{background:rgba(138,148,166,.14);color:#9aa4b4;}
  .b.hot{color:var(--hot);} .b.up{color:var(--up);} .b.down{color:var(--hot);} .b.flat{color:var(--mut);}
</style></head><body>
<h1>SpeedSkan &mdash; Collection Dashboard</h1>
<div class="sub">Generated __GEN__ &middot; click a Collection, brand, or system bar to filter &middot; click any column header to sort</div>
<div id="kpis" class="kpis"></div>
<div class="section-t">Breakdowns <span>&mdash; click a bar to filter the tables below</span></div>
<div class="grid3">
  <div class="panel"><h3>By System</h3><div id="cSystem" class="bars"></div></div>
  <div class="panel"><h3>By Brand</h3><div id="cBrand" class="bars"></div></div>
  <div class="panel"><h3>By Collection</h3><div id="cTier" class="bars"></div></div>
</div>
<div class="filters">
  <div class="fg"><label>Collection</label><div id="fCollection" class="chips"></div></div>
  <div class="fg"><label>Brand</label><div id="fBrand" class="chips"></div></div>
  <div class="fg"><label>System</label><select id="fSystem"></select></div>
  <div class="fg"><label>Search</label><input id="search" placeholder="title..."/></div>
  <a id="clear" class="clear">clear filters</a>
</div>
<div class="grid3">
  <div class="panel"><h3>Top 10 &mdash; Highest Value</h3><ol id="topValue" class="lb"></ol></div>
  <div class="panel"><h3>Top 10 &mdash; Biggest Increase</h3><ol id="topMove" class="lb"></ol></div>
  <div class="panel"><h3>Quick Stats</h3><div id="stats" class="stats"></div></div>
</div>
<div class="tablewrap">
  <div class="tbar"><span id="tcount"></span></div>
  <div class="scroll"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div>
</div>
<script>
const DATA = __DATA__;
const money = n => '$' + Math.round(n).toLocaleString();
const el = id => document.getElementById(id);
const TIERS = ['Gold','Maybe','Cruff'];
let fc='All', fb='All', fs='All', q='';
let sortCol='md', sortDir=-1;
const sum=(a,k)=>a.reduce((s,x)=>s+x[k],0);
const groupSum=(a,key)=>{const m={};a.forEach(x=>{const g=x[key];(m[g]=m[g]||{med:0,n:0});m[g].med+=x.md;m[g].n++;});return m;};
function passes(d){return (fc==='All'||d.tr===fc)&&(fb==='All'||d.b===fb)&&(fs==='All'||d.s===fs)&&(q===''||d.t.toLowerCase().includes(q));}
function filtered(){return DATA.filter(passes);}

function kpis(){
  const hot=DATA.filter(d=>d.fl==='HOT').length;
  const cards=[['Median portfolio',money(sum(DATA,'md')),DATA.length+' items'],
    ['Retail band',money(sum(DATA,'lo'))+'\\u2013'+money(sum(DATA,'hi')),'low \\u2192 high'],
    ['Dealer value',money(sum(DATA,'dl')),'whole-lot cash'],
    ['\\ud83d\\udd25 Hot items',hot,'price doubled']];
  el('kpis').innerHTML=cards.map(c=>`<div class="kpi"><div class="kl">${c[0]}</div><div class="kn">${c[1]}</div><div class="ks">${c[2]}</div></div>`).join('');
}
function barChart(id,data,active,onClick){
  const e=Object.entries(data).sort((a,b)=>b[1].med-a[1].med);
  const max=Math.max(1,...e.map(x=>x[1].med));
  el(id).innerHTML=e.map(([k,v])=>`<div class="bar ${active===k?'act':''}" data-k="${encodeURIComponent(k)}">
    <div class="bk" title="${k}">${k}</div>
    <div class="btrack"><div class="bfill" style="width:${(v.med/max*100).toFixed(1)}%"></div></div>
    <div class="bv">${money(v.med)}<span class="bn">${v.n}</span></div></div>`).join('');
  el(id).querySelectorAll('.bar').forEach(b=>b.onclick=()=>onClick(decodeURIComponent(b.dataset.k)));
}
function charts(){
  barChart('cSystem',groupSum(DATA,'s'),fs==='All'?null:fs,v=>{fs=(fs===v?'All':v);render();});
  barChart('cBrand',groupSum(DATA,'b'),fb==='All'?null:fb,v=>{fb=(fb===v?'All':v);render();});
  const td={};TIERS.forEach(t=>{const a=DATA.filter(d=>d.tr===t);td[t]={med:sum(a,'md'),n:a.length};});
  barChart('cTier',td,fc==='All'?null:fc,v=>{fc=(fc===v?'All':v);render();});
}
function chips(){
  const cnt={};TIERS.forEach(t=>cnt[t]=DATA.filter(d=>d.tr===t).length);
  el('fCollection').innerHTML=['All',...TIERS].map(t=>`<button class="chip ${fc===t?'on':''}" data-v="${t}">${t}${t!=='All'?' <span>'+cnt[t]+'</span>':''}</button>`).join('');
  el('fCollection').querySelectorAll('.chip').forEach(c=>c.onclick=()=>{fc=c.dataset.v;render();});
  el('fBrand').innerHTML=['All','Nintendo','Sega','Other'].map(b=>`<button class="chip ${fb===b?'on':''}" data-v="${b}">${b}</button>`).join('');
  el('fBrand').querySelectorAll('.chip').forEach(c=>c.onclick=()=>{fb=c.dataset.v;render();});
  const systems=['All',...Array.from(new Set(DATA.map(d=>d.s)))];
  el('fSystem').innerHTML=systems.map(s=>`<option ${fs===s?'selected':''}>${s}</option>`).join('');
}
function topLists(){
  const f=filtered();
  const hv=[...f].sort((a,b)=>b.md-a.md).slice(0,10);
  el('topValue').innerHTML=hv.map((d,i)=>`<li><span class="rk">${i+1}</span><span class="nm" title="${d.t}">${d.t}</span><span class="vl">${money(d.md)}</span></li>`).join('')||'<li class="empty">none</li>';
  const mv=[...f].filter(d=>d.md!==d.fi).sort((a,b)=>(b.md-b.fi)-(a.md-a.fi)||b.pc-a.pc).slice(0,10);
  el('topMove').innerHTML=mv.length?mv.map((d,i)=>{const ch=d.md-d.fi;const cl=ch>0?'up':'down';return `<li><span class="rk">${i+1}</span><span class="nm" title="${d.t}">${d.t}</span><span class="vl ${cl}">${ch>0?'+':''}${money(ch)} (${d.pc>0?'+':''}${d.pc}%)</span></li>`;}).join(''):'<li class="empty">No price movement yet &mdash; run a price refresh to populate this.</li>';
}
function stats(){
  const f=filtered();const med=sum(f,'md');
  const top=f.length?[...f].sort((a,b)=>b.md-a.md)[0]:null;
  const cib=f.filter(d=>/CIB|Console|bongos|mic|cables/i.test(d.c)).length;
  const bySys=groupSum(f,'s');const ts=Object.entries(bySys).sort((a,b)=>b[1].med-a[1].med)[0];
  const rows=[['Items in view',f.length],['Median value',money(med)],
    ['Avg / item',f.length?money(med/f.length):'$0'],
    ['Most valuable',top?top.t.slice(0,20)+' ('+money(top.md)+')':'\\u2014'],
    ['Systems',new Set(f.map(d=>d.s)).size],
    ['Top system',ts?ts[0]+' ('+money(ts[1].med)+')':'\\u2014'],
    ['Complete/boxed',cib],['\\ud83d\\udd25 Hot',f.filter(d=>d.fl==='HOT').length]];
  el('stats').innerHTML=rows.map(r=>`<div class="st"><div class="stl">${r[0]}</div><div class="stv">${r[1]}</div></div>`).join('');
}
const COLS=[['t','Item','s'],['s','System','s'],['tr','Collection','s'],['md','Median','n'],['lo','Low','n'],['hi','High','n'],['fi','First','n'],['ls','Lo\\u00b7ever','n'],['hs','Hi\\u00b7ever','n'],['pc','\\u0394%','n'],['dl','Dealer','n'],['fl','Trend','s']];
function table(){
  const f=filtered();
  f.sort((a,b)=>{let x=a[sortCol],y=b[sortCol];if(typeof x==='string'){x=x.toLowerCase();y=(''+y).toLowerCase();return x<y?-sortDir:x>y?sortDir:0;}return (x-y)*sortDir;});
  el('thead').innerHTML='<tr>'+COLS.map(c=>`<th data-k="${c[0]}" class="${c[2]==='n'?'num':''} ${sortCol===c[0]?'sorted':''}">${c[1]}${sortCol===c[0]?(sortDir<0?' \\u25bc':' \\u25b2'):''}</th>`).join('')+'</tr>';
  el('thead').querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortCol===k)sortDir*=-1;else{sortCol=k;sortDir=(c=>['t','s','tr','fl'].includes(k))(k)?1:-1;}table();});
  const bdg={HOT:'<span class="b hot">\\ud83d\\udd25</span>',UP:'<span class="b up">\\u25b2</span>',DOWN:'<span class="b down">\\u25bc</span>',FLAT:'<span class="b flat">\\u25cf</span>',NEW:'<span class="b flat">\\u00b7</span>'};
  el('tbody').innerHTML=f.map(d=>`<tr class="${d.fl==='HOT'?'hot':''}">
    <td class="ti">${d.t}<div class="mt">${d.c}</div></td><td>${d.s}</td>
    <td><span class="tier ${d.tr.toLowerCase()}">${d.tr}</span></td>
    <td class="num md">${money(d.md)}</td><td class="num">${money(d.lo)}</td><td class="num">${money(d.hi)}</td>
    <td class="num">${money(d.fi)}</td><td class="num">${money(d.ls)}</td><td class="num">${money(d.hs)}</td>
    <td class="num" style="color:${d.pc>0.5?'#3fae63':d.pc<-0.5?'#e5534b':'#8b95a7'}">${d.pc>0?'+':''}${d.pc}%</td>
    <td class="num">${money(d.dl)}</td><td>${bdg[d.fl]||''}</td></tr>`).join('');
  el('tcount').textContent=f.length+' items \\u00b7 median '+money(sum(f,'md'))+' \\u00b7 dealer '+money(sum(f,'dl'));
}
function render(){chips();charts();topLists();stats();table();el('fSystem').value=fs;}
el('fSystem').onchange=e=>{fs=e.target.value;render();};
el('search').oninput=e=>{q=e.target.value.toLowerCase().trim();render();};
el('clear').onclick=()=>{fc=fb=fs='All';q='';el('search').value='';render();};
kpis();render();
</script></body></html>"""


def write_html(items, tiers, A):
    gen = datetime.date.today().isoformat()
    rows = []
    for it in items:
        tr = it["_t"]
        rows.append({
            "s": it["System"], "b": BRAND.get(it["System"], "Other"), "t": it["Title"],
            "tr": it["Tier"], "c": it["Completeness"],
            "lo": tr["cur_low"], "hi": tr["cur_high"], "md": tr["cur_med"],
            "fi": tr["first"], "ls": tr["low_seen"], "hs": tr["high_seen"],
            "pc": round(tr["pct"], 1), "fl": tr["flag"], "sr": tr["sources"], "dl": it["Dealer"],
        })
    data_json = json.dumps(rows, separators=(",", ":")).replace("</", "<\\/")
    doc = TEMPLATE.replace("__DATA__", data_json).replace("__GEN__", gen)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    main()

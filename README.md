# SpeedSkan — a Claude Code skill

Hold your retro games, consoles, and collectibles up to your **webcam** and let Claude
identify them, estimate resale value, sort them into keep / maybe / bulk tiers, and log
everything to a running spreadsheet. Built for triaging a big pile fast — "the cruff from
the gold."

Point your camera at a shelf of NES/SNES/N64/GameCube/Genesis/Dreamcast/Game Boy games (or
consoles, controllers, VMUs, whatever), a crate of vinyl records, or a box of baseball cards,
say **"look"**, and Claude reads the frame, prices each item, and appends it to `items.csv`.
Totals recompute every batch. For cards it pulls ungraded, PSA 9 and PSA 10 prices, so the
few cards worth grading stand out from the bulk.

---

## What you need

- **[Claude Code](https://claude.com/claude-code)** — this is the important one. The skill
  is a set of instructions Claude follows; the identification and valuation is Claude
  reasoning about each webcam frame. Without a Claude environment that supports skills, the
  scripts are just a webcam page and a CSV — the "what is it / what's it worth" brain is Claude.
- **Python 3** with **Pillow** (`pip install pillow`) — for the capture server and for
  cropping/zooming tough labels.
- A **webcam** and a **normal web browser** (Edge, Chrome, Firefox…).

> Why your own browser? Claude Code's built-in browser pane can't access a camera. So the
> capture page runs in *your* browser, streams frames to a tiny local server, and Claude
> reads the latest frame off disk. You never hand Claude your browser — it just reads a file.

---

## Install

Copy the `speedskan/` folder into your project's skills directory:

**Per-project** (only in one folder):
```
<your-project>/.claude/skills/speedskan/
```

**Global** (available everywhere):
```
~/.claude/skills/speedskan/      # macOS/Linux
C:\Users\<you>\.claude\skills\speedskan\   # Windows
```

Then open Claude Code in that folder and say something like **"let's scan my games"** or
run **`/speedskan`** with no arguments. (Skills load at session start, so start a fresh
session after installing. Arguments after `/speedskan` get substituted into the skill's
`$0`, `$1`… placeholders and garble its dollar figures, so put session context in your
next message instead.)

---

## Using it

1. Claude starts the capture server:
   `python .claude/skills/speedskan/scripts/server.py`
2. You open `http://127.0.0.1:8791/` in your **own** browser and click **Allow** on the
   camera prompt.
3. Hold an item in the dashed box (~6–10 inches back so the webcam can focus) and say **"look"**.
4. Claude identifies + prices it, logs it, and shows running totals. Repeat for the next item.

Your data lives in plain files in your working folder:
- **`items.csv`** — append-only master list (the source of truth).
- **`inventory.csv`** — generated catalog, grouped by system and tier, with totals. Open it
  in Excel/Sheets or print it.
- **`price_history.csv`** — dated price observations per item, each with the source and the
  URL it was read from, so any number can be re-checked later.
- **`inventory.html`** — a sortable/filterable dashboard with breakdown charts, top-value
  and biggest-mover lists. Items whose price has doubled show as **HOT** in red.

### Estimates vs. real comps

When an item is first scanned, its price is **Claude's estimate** — fast, good enough to
triage, and logged with source `est`. Say **"refresh prices"** and Claude replaces it with
real market comps, recording the URL every number was read from. Three independent sources:

- **`pricecharting`** — the retro-game price standard. Book value.
- **`comps`** — eBay **sold** listings, read through your own signed-in Chrome (eBay put
  sold data behind a login in August 2026). What a copy actually fetches.
- **`dealer-ask`** — a retro dealer's retail price for a cleaned, tested copy. The ceiling.

Vinyl is priced from **Discogs** sold statistics, and trading cards from **SportsCardsPro**
(ungraded / PSA 9 / PSA 10).

Across 82 comped items they agree in aggregate — median difference between eBay and
PriceCharting was 0%. They disagree sharply on *individual* items, though (−38% to +65%),
and hardware is where the gaps are widest. That is the whole reason to pull more than one.

The `Sources` column tells you which is which: `est` means nobody has checked it yet.
That distinction matters — in one real refresh, estimates ran ~39% *below* actual comps,
with individual items off by 3×. **Comp anything before you sell or bulk it**, especially a
pile you're about to hand to a dealer.

---

## Notes

- The skill improves itself: at the end of a session it will offer to fold new lessons
  (pricing corrections, authenticity tips, new price sources) back into `SKILL.md`. It
  carries calibration notes learned from real refreshes — e.g. consoles get under-priced,
  loose common carts get over-priced — so it gets sharper the more you use it.
- Prices are tracked **over time**: re-run a refresh weeks later and the dashboard shows
  each item's % change, its lowest/highest ever, and flags the movers.
- Nothing personal is committed by git — see `.gitignore` (your `items.csv`, `inventory.csv`,
  and captured photos stay local).
- This is a triage/appraisal helper. It doesn't list anything for sale on your behalf.

Made with Claude Code. Share freely.

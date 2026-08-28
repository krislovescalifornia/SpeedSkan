# SpeedSkan — a Claude Code skill

Hold your retro games, consoles, and collectibles up to your **webcam** and let Claude
identify them, estimate resale value, sort them into keep / maybe / bulk tiers, and log
everything to a running spreadsheet. Built for triaging a big pile fast — "the cruff from
the gold."

Point your camera at a shelf of NES/SNES/N64/GameCube/Genesis/Dreamcast/Game Boy games (or
consoles, controllers, VMUs, whatever), say **"look"**, and Claude reads the frame, prices
each item, and appends it to `items.csv`. Totals recompute every batch.

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
run **`/speedskan`**. (Skills load at session start, so start a fresh session after
installing.)

---

## Using it

1. Claude starts the capture server:
   `python .claude/skills/speedskan/scripts/server.py`
2. You open `http://127.0.0.1:8791/` in your **own** browser and click **Allow** on the
   camera prompt.
3. Hold an item in the dashed box (~6–10 inches back so the webcam can focus) and say **"look"**.
4. Claude identifies + prices it, logs it, and shows running totals. Repeat for the next item.

Your data lives in two plain CSVs in your working folder:
- **`items.csv`** — append-only master list (the source of truth).
- **`inventory.csv`** — generated catalog, grouped by system and tier, with totals. Open it
  in Excel/Sheets or print it.

Prices are rough **loose/used resale estimates** to help you *triage*, not gospel — confirm
anything valuable against real sold listings before selling.

---

## Notes

- The skill improves itself: at the end of a session it will offer to fold new lessons
  (pricing corrections, authenticity tips) back into `SKILL.md`.
- Nothing personal is committed by git — see `.gitignore` (your `items.csv`, `inventory.csv`,
  and captured photos stay local).
- This is a triage/appraisal helper. It doesn't list anything for sale on your behalf.

Made with Claude Code. Share freely.

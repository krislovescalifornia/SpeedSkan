---
name: speedskan
description: >-
  Webcam-based triage and appraisal system for a physical collectible/retro-game
  collection. Use this whenever the user wants to hold items up to their webcam and
  have them identified, valued, and sorted into keep/sell/bulk tiers — phrases like
  "scan my games", "what's this worth", "look" (while showing an item on camera),
  "appraise these", "let's do more of the collection", "value this cartridge/console",
  or resuming a cataloging session. Also use it to resume or add to the running
  inventory (items.csv / inventory.csv) even if the webcam isn't mentioned. This is
  the standing system for documenting the collection over many sessions/months, so
  prefer it over ad-hoc valuation whenever the user is working through physical items.
---

# SpeedSkan

A repeatable webcam → identify → value → log workflow for cataloging a physical
retro-game / collectible collection over many sessions. The user holds items under a
webcam; you read each frame, identify and price the items, sort them into tiers, and
append them to a persistent inventory. Totals are recomputed automatically each batch.

## The big picture

The collection is documented across many short sessions. The **data is the product** —
it lives in plain CSV files in the project root and survives across sessions:

- `items.csv` — append-only master list (one row per item). **This is the source of truth.**
- `inventory.csv` — generated, human-readable catalog with totals appended. Regenerated
  from `items.csv` by the build script. Never hand-edit this; edit `items.csv` instead.

Everything for this collection lives in one folder (the project root, e.g.
`C:/Users/Kris/dev/ebaytool`): the data, the scan pictures, and this skill.

## Why a webcam pipe (and the one hard constraint)

The user's real browser can access the webcam; **the Claude Code in-app Browser pane
cannot** (camera is hard-blocked there — you'll see `NotAllowedError`). So the pipe is:
the user opens a tiny local page in *their own browser*, that page streams frames to a
local server, the server writes the newest frame to `captures/latest.jpg`, and you read
that file off disk with the Read tool. You never drive their browser — you just read the
latest frame whenever the user says "look".

## Starting a scan session

1. **Start the capture server** (from the project root so data lands in the right place):
   ```
   python .claude/skills/speedskan/scripts/server.py
   ```
   Run it in the background. It serves on http://127.0.0.1:8791/ and writes frames to
   `./captures/latest.jpg`. If port 8791 is taken, pass another: `... server.py 8792`.

2. **Ask the user to open the page in their own browser** (Edge/Chrome/etc — NOT the
   Claude pane) at `http://127.0.0.1:8791/` and click **Allow** on the camera prompt.
   On Windows they can launch it with:  `start msedge "http://127.0.0.1:8791/"`

3. The page auto-sends a frame every ~2 seconds (a green "Sent frame #… at …" line
   confirms it's flowing). Tell the user to hold an item in the dashed box, ~6–10 inches
   back so the webcam can focus, and say **"look"**.

If the user is resuming and just wants to keep adding items, the server may already be
running — check before starting a second one.

**First run (fresh install / new user):** if `items.csv` doesn't exist yet, create it with
exactly this header row before the first append, so the schema is right from the start:

```
System,Title,Completeness,Tier,Est_Low,Est_High,Dealer,Notes,Status
```

## The scan loop

Each time the user says "look" (or "what's this", etc.):

1. **Read the frame:** Read `captures/latest.jpg`.
2. **Identify** every game/console/accessory in the frame. Read labels, spines, logos,
   model numbers. If a label is too small or blurry, **crop and upscale it** with PIL
   rather than guessing (see "Reading tough labels"). If you still can't read it, say so
   and ask the user for the title — don't invent one.
3. **Price and tier** each item (see "Valuation").
4. **Append** each item to `items.csv` (see "The data model" — mind the comma rule).
5. **Rebuild + report:** run the build script and give the user a short tiered readout
   plus the running totals table.

Keep the per-batch reply tight: a few lines identifying the items with their tier and
value range, then the totals table. The user is moving fast through a big pile.

## Valuation

Estimate **loose/used resale** value (what it realistically sells for online), not
mint/sealed or price-guide peak. Give a **range** (low–high), and assign a **tier**:

- **Gold** — worth listing individually. Roughly $12+ and desirable, or any console.
- **Maybe** — borderline; sells but modest (~$8–15). User's call whether to list or bulk.
- **Cruff** — common filler (< ~$8, or damaged). Goes in a bulk lot to a dealer.

Also record a single **Dealer** point-estimate per item ≈ what a shop pays: about
**half of the retail midpoint** for gold/maybe, and only **a couple dollars** for cruff
(dealers pay pennies for common sports/shovelware carts). These sum into a "dump
everything to a dealer" figure.

Calibration notes learned in practice:
- **Consoles are the big-ticket items.** Price them as a complete hookup (console +
  power + AV) unless told otherwise — the user has confirmed they keep cables for every
  console. Note "test power-on" and that a bundled controller/game raises value.
- **Special variants matter:** e.g. black "Sega Sports" Dreamcast >> white Dreamcast;
  Tecmo *Super* Bowl >> Tecmo Bowl; a game's *original* >> its sequel (or vice-versa —
  check). When a title has a pricey sibling, name which one it is so the user isn't misled.
- **Completeness:** boxed disc games = CIB (case+manual+disc). Multi-disc games (e.g.
  Shenmue) — remind the user to confirm all discs are present. Peripherals that ship as a
  set (Seaman + mic, WaveBird + receiver, Donkey Konga + bongos) are worth much more kept
  together — flag that and keep them as one line.
- **Controllers/accessories** sell steadily: official (OEM) > third-party. GameCube pads
  and 6-button Genesis pads are in demand.

When you're unsure of a value, give a sensible range and say it's approximate rather than
stalling. The user can correct you, and corrections should be applied immediately.

## Reading tough labels

The webcam is top-down and low-res. When a label is unreadable at full frame, crop the
region and upscale it, then Read the crop. Example:

```python
from PIL import Image
im = Image.open("captures/latest.jpg")
# crop (left, top, right, bottom) around the label, then enlarge
im.crop((330, 260, 930, 690)).resize((1200, 860)).save("captures/_zoom.png")
```

Then Read `captures/_zoom.png`. Reuse `_zoom.png` (or numbered variants) as scratch.

## Authenticity checks (avoid mispricing bootlegs / third-party)

- **Green/translucent Game Boy shells** are a bootleg red flag — but *clear/smoke* shells
  can be genuine. The tell is a molded **"Nintendo ®"** stamp on the back shell + a real
  board; ask the user to flip it and confirm. A game that never had an official release on
  that platform is almost certainly a repro.
- **Black NES controllers** are third-party (official are grey; look for "NES-004").
  Third-party pads/controllers are worth less than OEM — tier them down.
- When authenticity swings the value a lot, price conservatively and flag it for the user
  to verify, rather than assuming.

## The data model (items.csv)

Columns, in order:

`System, Title, Completeness, Tier, Est_Low, Est_High, Dealer, Notes, Status`

- **System** — e.g. `NES`, `SNES`, `Nintendo 64`, `GameCube`, `Genesis`, `Game Boy`,
  `Game Boy Color`, `Game Boy Advance`, `Sega Saturn`, `Sega 32X`, `Master System`,
  `Game Gear`, `Dreamcast`, `Wii`, `Virtual Boy`. New systems are fine — the build script
  sorts known ones first and puts the rest under "Other".
- **Completeness** — `Loose`, `CIB`, `Console + cables`, `CIB + mic`, etc.
- **Tier** — exactly `Gold`, `Maybe`, or `Cruff` (the build script keys on these).
- **Est_Low / Est_High / Dealer** — whole-dollar integers.
- **Notes** — short; what to confirm/clean/test, or why it's priced this way.
- **Status** — leave blank; it's the user's column to mark Dealer / Listed / Sold / Keep.

**CRITICAL comma rule:** the append path is a plain heredoc, not a CSV writer, so a comma
inside any field will shift the columns and break the build (a `Tier` word lands in a
number field). **Never put a comma inside a field — use a semicolon or dash instead.**
(e.g. write `grey; copy 2`, not `grey, copy 2`.) This has bitten us; it's the one thing to
get right.

Conventions:
- **Duplicates:** add a second row with `(copy 2)` in the title.
- **Identical lots:** one row with `x6` in the title and the *summed* Est_Low/High/Dealer
  for the whole lot (e.g. six $8–14 pads → `48,84,30`), noting per-unit price in Notes.
- **Bundles that sell together:** one row (e.g. `Seaman (CIB) + Dreamcast Microphone`).

Append rows from the project root with a heredoc, e.g.:

```bash
cat >> items.csv <<'EOF'
NES,Contra,Loose,Gold,30,45,18,Big seller; always in demand,
NES,Duck Hunt,Loose,Cruff,4,7,2,Very common Zapper title; bulk-lot,
EOF
```

## Rebuild + totals

After appending, regenerate the catalog and read back the totals:

```
python .claude/skills/speedskan/scripts/build_inventory.py
```

This reads `items.csv`, writes a sorted `inventory.csv` (grouped by System, then
Gold→Maybe→Cruff) with a TOTALS block appended, and prints a summary:

```
Items: 200
  Gold    62 items  retail $1614-2484  dealer $1025
  Maybe   62 items  retail $788-1286   dealer $479
  Cruff   76 items  retail $364-644    dealer $190
  ALL    200 items  retail $2766-4414  dealer $1694
```

Relay those figures to the user as a small markdown table each batch. Send the actual
`inventory.csv` file to the user (SendUserFile) every ~5 batches or on request, not every
turn — the running totals in text are enough between file drops.

## Corrections

The user often re-shows an item to correct an ID or add info ("that's actually X",
"I have the receiver too", "these all have manuals"). When correcting an existing item,
**edit its row in items.csv in place** (don't add a duplicate), then rebuild. If they say
to drop an item ("it's trash, keep it off the books"), delete the row and rebuild.

## Reflect and improve (end-of-session loop)

This skill is meant to get sharper over months of use, so when a session winds down (the
user says "done"/"that's it for now", or you've worked through many batches), take a beat to
**reflect on what this session taught you that isn't captured here yet**, and offer to fold
it in. The goal is that the *next* session starts smarter, not that you re-learn the same
lessons each time.

Look back over the session for durable, generalizable lessons — not one-off facts:
- **Systematic pricing bias:** did the user repeatedly correct you the same direction on a
  category ("you keep overpricing loose sports carts", "N64 sells higher than you think")?
  That's a calibration note worth adding.
- **New authenticity tells** you learned (a new bootleg giveaway, an OEM-vs-clone marker).
- **New systems, abbreviations, or variants** worth naming (a pricey sibling to warn about).
- **New conventions or standing preferences** the user set (how they want lots handled, a
  default they want assumed, a bundle that must stay together).
- **Recurring friction** — anything that made you waste steps, so you can prevent it.

Then propose **specific edits to this file** (`SKILL.md` — the Valuation, Authenticity, or
Conventions sections are usually where it lands), show the user the before/after, and apply
on approval. Prefer generalizing an existing note over bolting on a narrow special-case;
keep the skill lean and explain the *why* so it stays useful, not a pile of rules. This is
literally how the skill compounds in value — treat it as part of finishing a session, not an
afterthought.

Data safety needs no action: `items.csv` and `inventory.csv` are already on disk and persist
across sessions. Reflection is about improving the *skill*, not saving the *data*.

## Files

- `items.csv` (project root) — master data, append-only source of truth
- `inventory.csv` (project root) — generated catalog + totals (send this to the user)
- `captures/latest.jpg` — newest webcam frame (what you Read each "look")
- `captures/_zoom.png` — scratch crop for reading tough labels
- `scripts/server.py` — the capture server + camera page
- `scripts/build_inventory.py` — the totals/catalog rebuilder

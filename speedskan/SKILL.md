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
`C:/Users/<you>/dev/<collection>`): the data, the scan pictures, and this skill.

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

## Settle these once per collection (then carry them forward)

Four questions decide how a whole session runs. Ask them at the start of the first session
of a new medium, record the answers, and don't re-ask every time.

- **Grading depth.** Media-first (assume the item plays, note sleeve/cover damage in
  `Notes`) is the fast default and is usually right — condition barely moves a common
  record's price. The user then grades properly only on the Gold rows. Tell them explicitly
  which rows are worth pulling and that the rest are not worth the time.
- **Pressing depth.** "Only when it matters" is the efficient default: comp the common
  pressing, check the variants' medians, and only ask for a catalog number or dead-wax
  matrix when they actually diverge enough to change the money.
- **Which face to photograph.** The back is usually the better input — barcode, catalog
  number, label logo and tracklist all live there. If a user is already showing backs, that
  is deliberate; treat it as the preferred input rather than a problem.
- **How many items per frame.** Two works well for flat media like records and roughly
  doubles throughput. Keep the per-batch reply to the identifications plus the totals table.

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

**Tier dots (required in every readout):** prefix each item line with a colored dot for
its tier so the user can eyeball the batch at a glance — 🟢 for Gold, 🟡 for Maybe, 🔴 for
Cruff. e.g. `🟢 **<Title>** — Gold. Big seller. ~$30–45.`

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

Calibration notes learned in practice. The directional biases below were measured
against real comps on 2026-09-10 (82 items) — trust them over your first instinct:

- **Consoles are the big-ticket items, and you under-price them every time.** Across seven
  4th–6th-generation consoles every one comped 20–120% *above* estimate ($50→$110,
  $120→$221, $60→$93, $68→$95). **Roughly double your instinct for hardware, then comp
  it.** Price them as a complete hookup (console + power + AV) unless told otherwise — ask
  the user once whether they keep cables, and carry the answer forward. Note
  "test power-on" and that a bundled controller/game raises value.
- **OEM peripherals are under-priced too** — across three first-party Dreamcast and
  GameCube peripherals the estimate landed near half the comp ($28→$64, $32→$51,
  $55→$70). Uncommon first-party peripherals behave like consoles, not like accessories.
- **Loose common NES/SNES carts you *over*-price** — four well-known late-80s carts all
  came in under estimate ($18→$11, $23→$14, $23→$16, $32→$25). A multi-million-seller
  is cheap loose; its value lives in the **box** — a marquee NES title can run $31 loose
  against $180 CIB. Check completeness before getting excited about a famous NES title.
- **Sleeper categories that beat estimates hard:** Dreamcast CIB (three titles ran
  $26→$93, $24→$58, $32→$77), GameCube first-party Nintendo/Zelda ($32→$75, $25→$88),
  and Game Boy Color puzzle/RPG ($23→$74). When an item is Dreamcast-CIB or
  GC-first-party, comp it rather than guessing.
- **Special variants matter:** e.g. black "Sega Sports" Dreamcast >> white Dreamcast;
  Tecmo *Super* Bowl >> Tecmo Bowl; a game's *original* >> its sequel (or vice-versa —
  check). When a title has a pricey sibling, name which one it is so the user isn't misled.
- **The name-collision trap.** A price source will happily hand you a *different product
  with a similar name*, and the gap can be an order of magnitude: searching "black
  Dreamcast" returns the rare **JP black console (~$938 loose)**, not the US **Sega Sports
  black Dreamcast (~$221)**. Same shape: "Controller S Translucent Green" is probably the
  **Green Halo Edition** ($75) but a plain S Type is $19. Always confirm the page title
  names the exact variant before recording, and when it stays ambiguous, record the
  conservative number in `Low`, the optimistic one in `High`, and flag it in `Notes`.
- **Completeness:** boxed disc games = CIB (case+manual+disc). Multi-disc games (e.g.
  Shenmue) — remind the user to confirm all discs are present. Peripherals that ship as a
  set (game + bundled mic, wireless pad + receiver, rhythm game + its controller) are worth much more kept
  together — flag that and keep them as one line.
- **Controllers/accessories** sell steadily: official (OEM) > third-party. GameCube pads
  and 6-button Genesis pads are in demand.

### Vinyl records

A wide-genre record collection behaves differently enough from cartridges that the game
heuristics above will mislead you. The figures below were measured across 28 records on
2026-09-13; trust them over first instinct.

**The one-line version: value = demand ÷ supply, and Discogs shows you both.** Age, fame,
genre and "limited edition" badges are all noise. Two numbers on the release page —
have/want, and the sold *low* — call the tier before you read the median.

- **Read the have/want ratio first.** Rough guide: **>10:1 → Cruff, ~3–10:1 → Maybe,
  <3:1 → Gold.** Measured: a 1970 blues-rock first pressing (3706 have / 139 want = 27:1)
  comped **$2.75**, while a 2011 electronic LP on a respected indie label (7287 / 2632 =
  2.8:1) comped **$27** — ten times more for a record forty years younger.
- **The sold *low* (the floor) is the strongest single signal, and better than the median.**
  When even the worst copy sells well, demand is doing the work rather than condition.
  Floors measured against their medians: a 2008 out-of-print 2xLP **$75.58**/$150; a 2002
  instrumental hip-hop 3xLP **$23.99**/$46; a 2013 electronic 2xLP **$17.44**/$27; a 1984
  novelty LP **$8.25**/$11 — against a common 1970 rock LP's **$0.90** and a label giveaway
  sampler's **$0.03**. A high floor on a modest median is a better record than a low floor
  on a high one.

**Three limits on the ratio — it is a good rule, not a law:**

- **Above ~10:1 it stops discriminating.** At 27:1 a record comped $2.75; at 30:1, $3.70;
  at 45:1, $3.00. Everything past 10:1 is the same $2–5 floor. The ratio earns its keep
  *below* 10:1.
- **It does not work across pressing variants of one title.** Those counts mostly track
  which Discogs entry people default to when filing a copy, not scarcity. On one 1984
  soundtrack the *commoner* US pressing (3513 owners) comped **$10** against the scarcer
  one's (515 owners) **$6.97**, because the catch-all entry carries far more sales data.
- **A good ratio on a budget-label product still lands at budget prices.** A 1961
  stereo-demonstration exotica LP on a budget label had a healthy 4.8:1 and still comped
  $4.25. The ratio measures demand vs supply; it cannot tell you the item is a knockoff.

**Scarcity alone is worth nothing — this is the error to guard against.** Two records
priced identically for opposite reasons: a platinum-selling 1987 rap 12-inch (3282 owners,
367 wanters) at **$3.50**, famous but everywhere; and a regional college-sports spoken-word
LP (**135 owners**, 3 wanters) at **$3.00**, genuinely scarce but unwanted. "It's rare" is
the intuition that makes people keep boxes of records for thirty years. Say it plainly: a
record is worth $55 because two thousand people are hunting it, not because it is old.

**Category calls that held up across the session:**

- **Modern indie/electronic albums (roughly 2008–2013) on a respected independent label are
  the most reliable Gold in a general collection**, and this inverts the intuition most
  people bring to a crate. Four for four in one session: **$150**, **$27**, **$27**,
  **$18**. Short runs, no repress, and a buyer base that still actively collects. Meanwhile
  nearly every pre-1980 mainstream LP in the same session came back Cruff.
- **A chart hit is the worst thing that can happen to a 12-inch single.** A 1987 platinum
  rap 12-inch **$3.50**, a 1987 number-one pop 12-inch **$6.36**, a 2004 indie-rap 12-inch
  **$3.00**. Treat **12-inch single** as a strong Cruff signal regardless of era, genre or
  how respected the artist is — chart success means an enormous press run and 12-inch
  singles have no collector base to absorb it. (Do not carve out an era-based exception
  here; an earlier version of this note did, on a three-item sample, and it was wrong.) The
  ones that *are* worth money are the obscure small-label ones nobody bought.
- **A record marked "promotional / not for sale / do not pay any money for this LP" is
  Cruff on its face, and the artist roster does not rescue it.** A label giveaway sampler
  carrying several genuinely collectible indie artists comped **$2** (low: three cents),
  while one of those same artists' own album on that same label comped **$18** — 9x, same
  artist, same label. This is distinct from a genuinely limited *promo pressing*, which can
  run the other way.
- **"Limited edition" and colored vinyl are marketing, not value.** All three 2xLP variants
  of one 2012 indie album comped within $1.30 — standard black $14.48, marbled limited
  $15.00, marbled-plus-bonus-CD $13.73. Don't send the user digging to check vinyl colour.
  A small run only matters when it is small *relative to demand*.
- **Mail-order / TV compilations are the floor, but check whose recordings they are.** A
  mail-order set of **re-recorded cover versions** had no Discogs entry at all; a TV
  compilation with the **original artists** comped $3.25. Same tier, genuinely different
  products — the catalog row should not conflate them.
- **Novelty and kids' records can beat prestige rock.** A 1984 film cash-in aimed at
  children — 60 owners, 38 wanters, **1.6:1**, median **$11** — beat a famous stadium-rock
  band's greatest-hits compilation ($10) in the same batch. Disposable cash-ins were
  destroyed by their owners *and* have a kitsch collector niche: low supply plus real
  demand.
- **The sleeper profile worth getting excited about:** a small original run whose artist got
  *more* famous afterwards. A 2002 instrumental hip-hop 3xLP had **more wanters than
  owners** — 731 / 778, **0.94:1**, median **$46** — because the artist's later, far more
  famous project brought a new audience back to a record that was never properly repressed.

**Condition, completeness and when to actually grade:**

- **Condition matters far less on common records than people assume.** On one common 1970
  LP the entire sold band ran $0.90–$18 with a $2.75 median — grading it precisely changes
  nothing. Default to grading media by eye, noting sleeve damage in `Notes`, and telling the
  user to pull and grade **only the Gold rows**. That is a real time saving; say it out loud
  early.
- **Visible defacement is different from ungraded media.** If the user has said "assume the
  vinyl is fine", that covers what you cannot inspect — it does not mean ignoring a previous
  owner's name and phone number inked across the front cover (seen on a common 1976 rock LP:
  $7.98 comp, realistically $4–6). Price it down, say that you did, and offer to revert.
- **A wide median-to-high spread means completeness or condition varies — not hidden
  value.** Examples measured: $0.90–$18, $2–$45, and a film storyteller LP at
  $1.67–**$49.95**. In every case the high was a complete or near-mint copy of a common
  record. Investigate *why* the spread is wide, but keep the median as the recorded number.
- **Always ask what shipped with it, and record it in `Completeness`.** Things that mattered:
  all discs of a 2xLP/3xLP present (a missing disc guts a $46 triple, it does not reduce it
  proportionally), bonus 7-inch singles (one 1977 film soundtrack had one on *both* US
  pressings), booklets (a 1960s epic's 52-page souvenir program; a 1979 film storyteller
  LP's 12-page photo album), download cards, and bonus CDs.
- **Check whether the pressing even matters before chasing it.** It often doesn't — one
  album's original and its later reissue comped $27 vs $25, and another's plant variants $7
  vs $10. One extra page load answers this and saves the user pulling a record out of its
  sleeve. When it *does* diverge, say so and ask: one 1969 double live album ran **$55** for
  the original vs **$30** for a repress, and its 1970 follow-up **$28.50** vs **$17**. For
  Warner-family US rock of that era the tell is the **label art** — the green "W7" label is
  1969/70, the green Burbank palm-trees label is 1973 or later.

**Identifying a record from the camera:**

- **Prefer the back cover, and say so.** Users often photograph backs deliberately — the
  barcode, catalog number, label logo, tracklist and pressing plant all live there. Three
  IDs in one session turned on it: a label logo that made an otherwise un-findable record
  comp in a single search; a double album's back cover; and label badges that confirmed a
  $150 valuation instead of leaving a hedge on it. The front is only better when the back is
  a plain sleeve.
- **Before concluding the artwork is wrong for the pressing, check whether you are looking
  at the back.** Some albums split the title across both faces — one famous 1969 live double
  puts half the title on the front and half on the back — and treating that as a mystery
  reissue nearly cost the correct ID on a batch's one valuable record.
- **Textless covers are real.** Some sleeves carry no artist, title or catalog number at all.
  Identify from the **tracklist** — two distinctive song titles in a plain web search is
  usually instant. For an unlabeled 12-inch, read the **label logo and its printed city
  address** rather than the track titles; that cracked one release that Discogs search could
  not find.
- **No Discogs entry is itself a data point — but only after you have tried the back.** Some
  mail-order sets genuinely have none, and a record nobody has catalogued in 25 years of
  Discogs has no market. But another release returned zero hits from its front cover and
  resolved instantly from the back. Never record "un-cataloged" off a front cover alone.
- **A vinyl session doubles as a discography.** The user gets a catalog of what they own out
  of the same pass, so record artist, exact title and catalog number accurately even on
  Cruff rows where the price is trivial — and disambiguate confusable names in `Notes`
  (a compilation whose title resembles a famous band's name; volume 1 vs volume 2 of a
  soundtrack; an originals compilation vs a re-recordings set).

**Where vinyl value hides, in short:** first pressings with the right matrix/runout, private
press and small labels, jazz (Blue Note, Impulse!), soul/funk, reggae, obscure original
hip-hop, novelty/kitsch with a niche, anything never reissued — and modern short-run indie
albums whose artist has since grown.

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
  `Game Gear`, `Dreamcast`, `Wii`, `Virtual Boy`, plus `Vinyl` for records. New systems are
  fine — the build script sorts known ones first and puts the rest under "Other".
- **Completeness** — `Loose`, `CIB`, `Console + cables`, `CIB + mic`, etc. For records:
  `LP`, `Gatefold LP`, `2xLP`, `3xLP`, `12in single`, `LP + booklet`, `LP + bonus 7in`,
  `LP + download card`. Put an unresolved question in the field itself while it is open
  (e.g. `2xLP - CONFIRM both discs`) so it shows up in the catalog rather than only in Notes.
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
- **Bundles that sell together:** one row (e.g. `<Game> (CIB) + <bundled peripheral>`).

Append rows from the project root with a heredoc, e.g.:

```bash
cat >> items.csv <<'EOF'
NES,<Exact Title>,Loose,Gold,30,45,18,Big seller; always in demand,
NES,<Another Title>,Loose,Cruff,4,7,2,Very common; bulk-lot,
EOF
```

## Rebuild + totals

After appending, regenerate the catalog and read back the totals:

```
python .claude/skills/speedskan/scripts/build_inventory.py
```

This reads `items.csv` + `price_history.csv`, writes a sorted `inventory.csv` (grouped by
System, then Gold→Maybe→Cruff) with tracking columns and a TOTALS block, ALSO writes the
visual `inventory.html` dashboard, and prints a summary:

```
Items: 224
  Gold    74 items  retail $1939-3163  median $2597  dealer $1293
  ...
  ALL    224 items  retail $3218-5310  median $4309  dealer $2042
```

Lead with the **median** figure when relaying totals — it's the realistic portfolio value
(retail low–high is the full market band). Relay a small markdown table each batch. Send
`inventory.csv` (and, when prices have been refreshed, `inventory.html`) to the user every
~5 batches or on request, not every turn.

## Price tracking & refreshes

Prices are tracked over time so the user can watch items rise/fall. Two files drive it:

- `items.csv` — the current working **estimate** (your loose/CIB guess when an item is
  first scanned). This is the fallback until a real comp exists.
- `price_history.csv` — dated observations:
  `Date, System, Title, Source, Low, High, Median, URL`.
  Each price check appends rows (one per source). Source `est` is a placeholder; **any real
  source (`pricecharting`, `comps`, …) on a date overrides `est` for that date.** The build
  computes per item: current low/high/median (latest date), first-seen median, lowest &
  highest median ever, % change, and a flag (**HOT** = median doubled vs first → shown red;
  ▲ up >10%; ▼ down >10%; FLAT; `est` = not yet researched, Sources=0).

**Seed the baseline once** (and any time new items were added) so tracking has a starting
point: `python .claude/skills/speedskan/scripts/snapshot_prices.py` — appends today's `est`
snapshot for every item (idempotent per day).

### Where prices come from

Every number in this system is one of these. Keep the roster honest — the `Source` and
`URL` columns are what let the user (or a future session) re-check any price.

**Attribution matters.** Every price in this system — `est` rows included — came from *you*,
not from the user. They hold items to a camera; you do the identifying and the pricing. So
when a comp lands far from an earlier `est`, that is **your** miss to own: say "my earlier
estimate was low", never "your estimate" or "your instinct". Getting this backwards blames
the user for your own work.

| `Source` | What it actually is | Best for | How to reach it |
|---|---|---|---|
| `est` | **Your own estimate. Not a sourced price.** Model judgment only — *yours*, never the user's. | anything, as a placeholder until comped | n/a — replace it as soon as a real comp exists |
| `pricecharting` | PriceCharting: the retro-game price standard. Loose / CIB / new, derived from completed sales. | games, consoles, OEM accessories (NTSC/PAL/JP) | Browser pane — see below. WebFetch 403s. |
| `comps` | eBay **sold** listings — real completed sales | the *mid* number; anything PriceCharting doesn't track | **Needs the user's signed-in Chrome** (`mcp__claude-in-chrome__*`) — see below. The Browser pane is IP-blocked. |
| `dealer-ask` | A retro dealer's **retail asking price** for a cleaned, tested, warrantied copy | the *ceiling* — what a buyer pays shopping around | DKOldies / Game Over Videogames — see below. Plain HTML, no login. |
| `discogs` | Discogs release data + real sold statistics | vinyl / music media | **Browser pane works — no login, no Cloudflare** (verified 2026-09-13). API needs a token; the release page doesn't. |

Per-category best source, for when the collection widens past games:

- **video games / consoles / OEM accessories** → PriceCharting for the baseline, then at
  least one `dealer-ask` before anything is called a sell
- **vinyl records** → Discogs (strong ID *and* sold stats)
- **trading cards** → eBay sold + 130Point; PSA/PWCC for graded
- **toys & other collectibles** → eBay sold; Facebook Marketplace for local pricing

#### Three sources is not three opinions

PriceCharting **is** an aggregate of eBay sold listings — and so is GameValueNow. Stacking
those gives you one opinion three times, with the same blind spots in all three. What makes
a second source worth pulling is *independence*. Aim for one number per band:

| Band | Source | What it answers |
|---|---|---|
| **Floor** | dealer *buy* / trade-in price | what a shop would hand the user today |
| **Mid** | `pricecharting`, `comps` | what it actually trades at |
| **Ceiling** | `dealer-ask` | retail, cleaned and warrantied |

Verified 2026-09-10 — one popular N64 cartridge: PriceCharting **$31** loose against a
dealer ask of **$42.99** for a cleaned copy. A ~39% spread a single source hides completely.

Known bias worth carrying: a listing with an inflated ask that sold via **accepted Best
Offer** is often recorded at the *ask*, not the sale — in PriceCharting and in eBay's own
sold view alike. [130Point](https://130point.com/sales/) reveals the accepted-offer price
and is the cheapest correction for it (needs the signed-in Chrome; Cloudflare blocks the
Browser pane).

No floor source is wired up yet. PriceCharting's **Legendary** tier ($49/mo) bundles
GameStop buy/sell prices plus API + bulk CSV download — the CSV would replace the
~150-row index scraping below. Worth raising with the user only if they are pricing
hundreds of items; don't assume the subscription exists.

### Pulling PriceCharting numbers (the working method)

**Do not record numbers from WebSearch snippets.** Verified 2026-09-10: the snippet for
one GameCube title said $39.13/$55.72 while the live page said $41.88/$63.86. Snippets are cached and
stale. Use WebSearch only to *find a URL*; read the price off the page.

Drive the **Browser pane** (`mcp__Claude_Browser__*`). On a product page:

```js
(()=>{const g=s=>{const e=document.querySelector(s);return e?e.innerText.trim():null};
 return document.title.split('|')[0].trim()+' >> '+g('#used_price')+' / '+g('#complete_price')})()
```

`#used_price` = loose, `#complete_price` = CIB, `#new_price` = sealed. Batch it with
`browser_batch`, alternating navigate + javascript_exec, ~8 items per call.

**Fastest path for a whole system — the console index page.** One load of
`https://www.pricecharting.com/console/<slug>` carries ~150 titles with all three prices;
filter the rows client-side instead of visiting each game:

```js
(()=>{const re=/wind waker|ocarina|warioware/i;
 return [...document.querySelectorAll('#games_table tbody tr')]
  .map(r=>[...r.querySelectorAll('td')].map(td=>td.innerText.replace(/\s+/g,' ').trim()))
  .filter(c=>re.test(c[1]||'')).map(c=>c[1]+' >> '+c[2]+' / '+c[3])})()
```

Genre sub-pages reach the long tail the top-150 omits:
`?genre-name=accessories`, `=systems`, `=party`.

Console slugs: `nes`, `super-nintendo`, `nintendo-64`, `gamecube`, `gameboy`,
`gameboy-color`, `sega-genesis`, `sega-master-system`, `sega-dreamcast`, `sega-saturn`,
`playstation`, `playstation-2`, `xbox`.

Gotchas, all learned the hard way:

- **Cloudflare blocks `/search-products` and any background `fetch()`** — only real
  top-level navigations to product/console pages get through.
- A **wrong slug also lands on "Just a moment…"**, which looks identical to rate-limiting.
  Treat a challenge page as a bad slug first: run a WebSearch restricted to
  `pricecharting.com` and read the real URL out of the returned links.
- **Guessing a product slug mostly fails.** `platinum-controller`, `wavebird-controller`,
  `keyboard`, `xbox/controller`, `super-advantage` all returned the challenge page on
  2026-09-11; the real slugs were `wavebird-wireless-controller`, `duke-controller`,
  `green-s-type-controller`, `sega-dreamcast-keyboard`. Don't burn calls guessing — go to
  the genre sub-page, or run a WebSearch restricted to `pricecharting.com` and read the
  real URL out of the links (then read prices off the live page, never the snippet).
- Slug quirks: `&` → `%26`; apostrophes are kept literally
  (`zelda-collector's-edition`); numerals usually replace roman ones (`shinobi-3`,
  `gradius-3`); Zelda titles drop "The Legend of" (`zelda-wind-waker`).
- **Hardware is not in the main index — it is in the genre sub-pages**, and far more of it
  is tracked than it first appears. Verified 2026-09-11: third-party arcade sticks for SNES
  and Genesis *are* both tracked (this file previously claimed they weren't), as are every
  console, OEM controller, and the Dreamcast keyboard and mouse. Before concluding
  an item is untracked, check:
  `?genre-name=systems` (consoles), `?genre-name=controllers` (OEM pads, sticks, WaveBird),
  `?genre-name=accessories` (keyboards, mice, adapters). Add `&sort=popularity`.
- **Sort order is sticky (a session cookie), and it silently poisons later reads.** After
  one visit to `?sort=lowest-price`, every later `/console/<slug>` returned the *cheapest*
  list — same URL, same-looking table, wrong rows. **Always pass `?sort=popularity`
  explicitly** on console pages, and sanity-check `document.title` (it says "Cheapest …"
  when the sort is stuck).
- **The index is capped at ~150 rows.** The "More" button doesn't paginate, and genre
  sub-pages are capped too. The long tail (obscure sports carts, accessories) needs direct
  product URLs — plan on the index for the popular 60-70% and product pages for the rest.

**`browser_batch` can hand you the previous page's numbers.** A `javascript_exec` placed
right after a `navigate` sometimes runs before the new document is ready and reads the page
*before* it — on 2026-09-11 this silently attributed one platform's accessory sales to a
different console's search, which would have been recorded as a real comp. **Always return
`document.title` alongside the numbers and check it names the page you asked for.** If it
doesn't, re-run that lookup on its own.

**Verify every fuzzy match before you record it.** Substring matching happily returns a
*different product*: `pga tour golf` → "PGA Tour Golf II [Limited Edition]", `nba jam` →
"NBA Jam Tournament Edition", `wii fit` → "Wii Fit Plus". Each is a real page with a real
price for something the user doesn't own. Print `target => matched title | prices` and read
the pairs before writing anything.

**Build the target list from `items.csv`, never from memory.** Writing out a plausible-looking
list of titles for a system and pricing those is fabrication, even when every individual
price is real — you end up recording comps for games the user has never owned. Read the
actual rows, group them, and match against those.

### Pulling eBay sold comps (needs the user's Chrome)

**As of late August 2026 eBay requires a login for sold listings.** Any logged-out search
with `LH_Sold=1` redirects to `signin.ebay.com`. On top of that, eBay hard-blocks the
Browser pane's IP — `mcp__Claude_Browser__*` returns "Security Measure" or an error page.
Both together are why this source sat at 2 rows while `pricecharting` reached 193.

So drive the user's real Chrome: `mcp__claude-in-chrome__*`, where their eBay session
already exists. If `tabs_context_mcp` reports the extension isn't connected, say so and ask
them to open the Claude side panel in Chrome — do **not** silently fall back to the Browser
pane and do **not** record a WebSearch snippet instead.

```
https://www.ebay.com/sch/i.html?_nkw=<query>&LH_Sold=1&LH_Complete=1
```

**Do not add `&_ipg=60`.** Verified 2026-09-10: the deep link with `_ipg` tripped eBay's
`splashui/challenge` ("Pardon Our Interruption") even in a signed-in browser; the same URL
without it returned ~60 sold cards cleanly. If you do get challenged, load `ebay.com` first
and re-issue the search — the homepage visit clears it.

Results are `.s-card` (**not** `.s-item` — that markup is gone), with `.s-card__title` and
`.s-card__price` inside. Every card also contains the string `derosnopS` — "Sponsored"
reversed, an anti-scrape trick — so a sponsored test matches everything and is useless as a
filter. Ignore it and filter on the title instead:

```js
(()=>{const I=/n64|nintendo ?64/i,                      // must match
       E=/\bds\b|gamecube|lot |bundle|manual|repro|graded|damaged|untested/i,  // must not
       C=/complete|\bcib\b|w\/ ?box|boxed|in box|sealed/i;   // CIB markers
 const r=[...document.querySelectorAll('.s-card')].map(c=>{
   const t=((c.querySelector('.s-card__title')||{}).innerText||'')
     .replace(/NEW LISTING|Opens in a new window or tab/g,'').replace(/\s+/g,' ').trim();
   const m=((c.querySelector('.s-card__price')||{}).innerText||'').match(/\$([\d,]+\.\d{2})/);
   return t&&m?{t,v:+m[1].replace(/,/g,'')}:0}).filter(Boolean)
  .filter(o=>I.test(o.t)&&!E.test(o.t))
  .filter(o=>C.test(o.t)===WANT_CIB);          // condition-match the user's actual copy
 const v=r.map(o=>o.v).sort((a,b)=>a-b), q=p=>Math.round(v[Math.round((v.length-1)*p)]);
 return {n:v.length, p25:q(.25), med:q(.5), p75:q(.75)}})()
```

**Record `Low`/`High` as p25/p75, and `Median` as p50** — not min/max. Raw min/max is
worthless here: a first pass on one common NES cart returned a $5 low (a damaged copy that slipped the
filter) and a $2,200 high (a graded copy), which would have made the band meaningless.
The exclusion list above (`manual`, `damaged`, `untested`, `graded`, `lot`, `bundle`) is
what pulled those bands back to something usable.

Aim for **n ≥ 30** matched sales. Below that the median is noise — widen the query or say
so rather than recording a thin number as if it were solid.

**What this source is actually for — and what it is not.** A first pass over 12 popular
loose cartridges on 2026-09-10 showed eBay's median running 0% to −19% *below*
PriceCharting, which looked like a systematic optimism bias. **At n=56 on 2026-09-11 that
lean vanished**: median delta **+0%** on loose items (16 of 33 below PC) and **+4%** on CIB
(6 of 23 below). The two sources agree on the aggregate. Do not tell the user PriceCharting
runs high — that conclusion came from a 12-item sample that happened to be all popular NES
and N64 carts.

What survives is **per-item disagreement**, which is where the money actually is: individual
items ranged from **−38% to +65%** against the book, and the widest gaps clustered in
hardware, accessories and bundled sets — the categories PriceCharting tracks most thinly.
Pulling `comps` is
worth it not because it shifts the whole book, but because it catches the individual items
where the book is wrong by a third in either direction.

A general lesson worth carrying: **do not generalize a pricing pattern from a dozen items,
and never from a dozen items that share a platform and a condition.** State the sample size
next to any cross-item claim, and re-check it as the sample grows.

### Pulling dealer-ask numbers

Two US dealers serve plain HTML with no login and no Cloudflare challenge (verified
2026-09-10). Both are *asking* prices for cleaned, tested, warrantied stock — a real
ceiling, never a sold price. Always record them as `dealer-ask`, never as `comps`.

```
https://www.dkoldies.com/search.php?search_query=<query>
https://www.gameovervideogames.com/search?q=<query>
```

Both list prices directly in search results, so one load prices several items. On DKOldies
read the cards rather than the page text — `article.card` carries a clean `data-name`
(platform included) and the innerText holds the price range:

```js
(()=>{const re=/mario kart 64/i;
 return [...document.querySelectorAll('article.card')]
  .map(c=>({n:(c.dataset.name||'').trim(),
            ps:[...new Set((c.innerText.match(/\$[\d,.]+/g)||[]))]}))
  .filter(o=>re.test(o.n)).map(o=>o.n+' >> '+o.ps.join(' / '))})()
```

**The two numbers on a DKOldies card are not loose/CIB — what they mean depends on the
medium, and getting this backwards silently doubles or halves the row:**

| Medium | Variants offered | Low price is | High price is |
|---|---|---|---|
| **Cartridge** (NES/SNES/N64/GB/Genesis) | Cosmetically Flawed Cartridge → Good Cartridge | flawed **loose** | good **loose** |
| **Disc** (GameCube/PS/DC/Xbox) | Cosmetically Flawed → Game Only → Game in Case → Complete | **loose** | **CIB** |

So a cartridge card's *high* number is still a loose price — never file it as CIB. Confirm
on the product page (`Quality:` = cartridge, `Includes:` = disc) whenever the item is
worth enough to matter.

For a `dealer-ask` row: **Low** = cheapest variant, **High** = dearest variant, **Median** =
the variant matching the user's actual copy (good-cart for a loose cart, Complete for a CIB
disc). That keeps Median condition-matched, same as every other source.

**Expect dealer ask to run high — that is the point, not an error.** Measured across 12
gold items on 2026-09-10, DKOldies sat **+15% to +113%** over PriceCharting's
condition-matched number (median ≈ +67%). The widest case ran $61 book against a $130 ask.
Report it as the retail ceiling, and never quote it as what the user's copy will fetch.

Gotchas:

- **DKOldies' catalog is NES–PS2-era and shallow on imports/shmups.** `ikaruga` returns
  nothing. A miss means "they don't stock it", not "it's worthless" — leave the band empty.
- Their search fuzzes hard (`goldeneye` → `golden`), so results include Golden Sun, Golden
  Nugget, Golden Compass. The same name-collision rule applies: read `target => matched
  title | price` pairs before recording.
- Game Over Videogames prefixes the platform (`X360 Golden Compass`), which makes the
  platform check easy — use it.
- These are *live stock*. An item they don't currently have simply won't appear.

Blocked, for the record, so nobody re-tests them: eStarland, Lukie Games, CeX/WeBuy API and
130Point all sit behind Cloudflare from the Browser pane; GameValueNow refuses the
connection outright; eBay's Marketplace Insights API (90-day sold data) has been
application-only and closed to new developers since ~2020.

### Pulling Discogs numbers (vinyl)

Discogs release pages load fine in the **Browser pane** — no login, no Cloudflare challenge
(verified 2026-09-13). The public release page carries a Statistics block with real sold
data, which is all you need; the API token in `src/discogs.js` is optional and its
no-token path falls back to *sample data* — never record those numbers.

Find the release with a WebSearch restricted to `discogs.com`, then read the live page:

```js
(()=>{const t=document.title;const b=document.body.innerText.replace(/\s+/g,' ');
 const i=b.search(/Statistics/i);
 return t+' || '+(i>-1?b.slice(i,i+260):'NO STATS')})()
```

Returns `Have / Want / Avg Rating / Last Sold / Low / Median / High`. Map straight across:
**Low→Low, Median→Median, High→High** (unlike games, these are already sold-price
percentiles across conditions, so the loose/CIB convention doesn't apply). Always return
`document.title` and confirm it names the release you asked for — same stale-page trap as
PriceCharting.

- **`/master/<id>` pages have no Statistics block** — they list versions only. Use them to
  pick the right `/release/<id>`, then read stats there.
- **Have/Want is on the same block** — capture it, it drives the tier (see Vinyl above).
- Check the master's version list for a reissue and compare medians before deciding the
  pressing matters.
- **Never guess a Discogs master or release ID.** A guessed `/master/<id>` on 2026-09-13
  returned a completely different artist's compilation with a perfectly valid
  Statistics block — it would have been recorded as a real comp. Reach release pages from a
  search, and always return `document.title` and confirm it names the release you asked for.
- **`/search/?q=…` works fine in the Browser pane** (unlike PriceCharting's search). Harvest
  `a[href*="/release/"]` from the results, then load the release page. Add `&format=Vinyl`,
  and `&country=US` when region matters.
- **Cap a sealed/mint outlier before recording `High`.** Discogs' all-time high is often a
  sealed copy several times the median — one 1969 live double showed $222.75 against a
  $55 median.
  Real, but quoting it inflates the book's retail band and anchors the user. Record a
  realistic used ceiling and put the true high in `Notes`. (Don't cap when the asks confirm
  it: one out-of-print 2xLP's $300 high stood up against live asks of $170–334.)
- **Cross-check a surprisingly high median against current asking prices** at
  `/sell/release/<id>`. Asks running *above* the sold median means the market is not
  softening — that is what confirmed a $150 valuation this session. It is the vinyl
  equivalent of a `dealer-ask` ceiling, so it is a genuinely independent second source.
- **When Discogs search fails, identify from content, then come back.** Two distinctive
  track titles in a plain WebSearch resolved a textless sleeve instantly; a label logo plus
  its printed address resolved an unlabeled 12-inch. Discogs is the price source, not always
  the identification source.

### Recording an observation

1. Map each item to Low / Median / High and append a dated row to `price_history.csv`:
   - **Median** = the item's **actual-condition** price (loose price for a loose item, CIB
     for a boxed one). This is the headline number.
   - **Low** = loose price (floor). **High** = CIB price (realistic used ceiling). Avoid the
     sealed "new" price as High — real, but it wildly inflates ranges and totals. Keep this
     convention even for loose items, so the time series stays comparable across refreshes;
     just remind the user the retail-high band is a CIB ceiling, not what their loose copy
     fetches.
   - **URL** = the exact page you read. Every non-`est` row must carry one.
   - Source `pricecharting`, `comps` (eBay sold), or `dealer-ask` (retailer asking price).
     Use today's date. Never file a dealer's ask as `comps` — it is not a sale.
2. **Only record numbers you actually found — never invent a price.** Match the region
   (NTSC/US).
3. **Confirm you matched the right *product*, not just the right name** (see the
   name-collision trap under Valuation). The page title must name the exact variant.
4. Also update that item's `Est_Low/Est_High/Dealer` in `items.csv` to match, so the catalog
   stays consistent (Dealer ≈ half the median).
5. Rebuild. On an item's **first** comp everything reads FLAT (first==current, same day); on
   **later** refreshes the deltas, ▲/▼, and HOT-red appear as prices move over time.

Prioritize the **gold** items (highest value, most worth getting right). The `Sources`
column (`est` vs a number) shows what still needs a real comp. Two distinct things show up
as "movement", and they are worth separating when you report:

- **Real drift** — an item that already had a real comp, re-pulled later. This is market news.
- **Estimate correction** — an item's *first* real comp. This measures your guess against
  the market, not the market moving. Say so, or the user will read it as a price change.

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
- **Where the numbers came from.** If you used a source this session — or found a better
  way into one, or found one blocked — fold that into "Where prices come from" and
  "Pulling PriceCharting numbers". A price with no recorded route back to its source
  decays into a guess. The roster and the access recipes are as much a part of this
  skill's value as the valuation heuristics.

Then propose **specific edits to this file** (`SKILL.md` — the Valuation, Authenticity, or
Conventions sections are usually where it lands), show the user the before/after, and apply
on approval. Prefer generalizing an existing note over bolting on a narrow special-case;
keep the skill lean and explain the *why* so it stays useful, not a pile of rules. This is
literally how the skill compounds in value — treat it as part of finishing a session, not an
afterthought.

Data safety needs no action: `items.csv` and `inventory.csv` are already on disk and persist
across sessions. Reflection is about improving the *skill*, not saving the *data*.

## Files

- `items.csv` (project root) — master catalog + current estimate; append-only source of truth
- `price_history.csv` (project root) — dated price observations per item per source
  (time series); every non-`est` row carries the source `URL` it was read from
- `inventory.csv` (project root) — generated catalog with tracking columns + totals
- `inventory.html` (project root) — visual dashboard; HOT (doubled) items red, gains green
- `captures/latest.jpg` — newest webcam frame (what you Read each "look")
- `captures/_zoom.png` — scratch crop for reading tough labels
- `scripts/server.py` — the capture server + camera page
- `scripts/build_inventory.py` — the tracker/catalog/dashboard rebuilder
- `scripts/snapshot_prices.py` — appends a dated `est` baseline snapshot to price_history

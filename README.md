# World Cup Almanac

An interactive FIFA World Cup data almanac (every men's tournament, **1930 → 2026**) **and** a
near-zero-cost pipeline that computes World-Football Elo from scratch, optionally blends in the
betting market, and runs a **live** Monte-Carlo forecast of World Cup 2026 with confidence scores.

> 🎓 **New to this / explaining it to someone?** Read [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) — a plain-English,
> student-friendly walkthrough of the whole model (Elo, Monte-Carlo, the market blend, cards, confidence).

Two pieces, one repo, no build step:

| Part | File | What it does |
|---|---|---|
| **Almanac** (web) | [`index.html`](index.html) | Self-contained dashboard — three views (Tournament / All-Time / 2026 Forecast), CSV export, and built-in "how it works" docs. Vanilla JS, no dependencies. |
| **Data pipeline** (Python) | [`tools/build_wc2026_dataset.py`](tools/build_wc2026_dataset.py) | Computes Elo over every international since 1872, MLE-fits the goal model, optionally blends the market, runs the live forecast, writes `data/`, and re-embeds the numbers into `index.html`. Standard library only. |

## What the almanac shows

- **Live scores ribbon** (top of every view) — in-play scores and kick-off times from ESPN's public
  scoreboard, fetched in the browser on load and auto-refreshed while games are live. Free, no key,
  and **separate from the odds quota**. The same ESPN feed (results + goal detail) is overlaid onto
  the 2026 data, so the **whole 2026 Tournament view** (standings, Golden Boot, goal-timing, goals-by-stage,
  bracket) **and the forecast update live** — and auto-refresh the moment a result changes.
- **Tournament** (pick any edition 1930–2026) — group standings, the Golden Boot, when-goals-are-scored
  and goals-by-stage charts, confederation breakdown, the full **knockout bracket** (extra time &
  penalties resolved), a searchable **match explorer** with goal-by-goal detail, and penalties / own goals.
- **Discipline** (2026) — yellow/red totals and cards-per-game, a most-booked **card ranking** per player,
  and a **suspension watch** (who's banned, who's one booking away) from the live card feed. A banned
  player also nudges their team's rating down in the forecast for their next game (more if they've scored).
- **All-Time** — roll of honour, goals-per-match trend across every edition, top-scoring nations,
  most appearances, all-time leading scorers, and all-time penalties / own goals.
- **2026 Forecast** — a live, **market-informed** Monte-Carlo: title odds (with the market's number
  shown alongside ours), confederation share, each team's **road to the final**, **current form**,
  the **official FIFA World Ranking** (frozen for the tournament, blended into the model — see below),
  **who escapes each group** (and group-stage-exit on hover), plus **data & forecast confidence
  scores** and a "↻ Refresh with live results" button that re-runs the whole simulation in your browser.
- **Export CSV** — all matches (1930–2026), all goals, all group standings, the 2026 forecast, and the
  collected market odds. Matches/goals/standings and the forecast carry the **live** ESPN-overlaid state
  (the forecast CSV is tagged `data_state=live` once you've refreshed, `snapshot` otherwise, with an
  `as_of` date); the files committed under `data/` are the reproducible **build snapshot**. See
  [Snapshot vs live](#snapshot-vs-live-data).

## Quick start

**View it** — open `index.html` in any modern browser (it fetches historical match data from the
openfootball dataset via the jsDelivr CDN, so it needs an internet connection), or serve the folder:

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

**Regenerate the data + forecast** (free, no key needed):

```bash
python3 tools/build_wc2026_dataset.py
```

This rewrites everything in [`data/`](data/) and re-embeds the latest forecast into `index.html`.
Standard library only — no `pip install`. (If your Python lacks root CA certificates,
`pip install certifi` and it's picked up automatically.)

## How the forecast works

1. **Elo** — World-Football-style Elo (importance weighting K, margin-of-victory multiplier, +100
   home advantage) computed from scratch over **every men's international since 1872** (~49,000 matches).
2. **Goal model** — for simulated group games, each side's expected goals scale with the rating gap,
   `λ = base · 10^(±γ·d/400)`, with `base` and `γ` **maximum-likelihood-fit** to recent competitive
   scorelines (no new data). Mismatches produce more goals and real blowouts. Knockout winners come
   straight from the Elo win-probability.
3. **Live conditioning** — actual 2026 results (from the live ESPN feed, fresher than the static
   datasets) are **locked in** (group and knockout); only unplayed fixtures are simulated. Every panel
   reads from this one simulation, so they all move together.
4. **Betting-market blend** *(optional — see below)* — pulls each team's strength toward the de-vigged
   market, which prices in injuries, form and squad changes Elo can't see.
5. **Official FIFA ranking blend** *(always on, €0)* — FIFA computes its ranking with the **same Elo
   method**, so it's an independent strength estimate. We rescale the official points to our Elo
   distribution and pull the simulation's strength anchor **35% toward it** (a consensus of our Elo and
   FIFA's). The points are pasted in from FIFA's site; FIFA **freezes the ranking during a World Cup**,
   so the figures stay valid the whole tournament. The forecast page also shows the full ranking, with
   our Elo and its in-tournament movement alongside.
6. **Monte-Carlo** — the real 2026 format (12 groups, top-2 + 8 best third-placed → official
   Round-of-32 → Final, hosts +50 Elo) run **50,000 times** (30,000 for the in-browser refresh).
   The percentages are simply how often each thing happened.

### Confidence scores

- **Data confidence** = `0.45·coverage + 0.20·recency + 0.35·source-quality` (friendlies are
  discounted as low-signal).
- **Forecast confidence** (per number) = 100 − Monte-Carlo sampling margin − unplayed-share penalty −
  a fixed honesty discount (15, or 8 when the market blend is on). It can never read 100.

### Keeping it live

1. **In the browser** — the Forecast tab's **"↻ Refresh with live results"** button re-runs the full
   simulation client-side (~30k runs, a couple of seconds) from current match data. No rebuild.
2. **Rebuild the snapshot** — `python3 tools/build_wc2026_dataset.py` then commit; this refreshes
   `data/` and the numbers baked into `index.html`. Wire it to a daily CI job to stay fresh.

### Snapshot vs live data

There are **two flavours** of the 2026 data, and the almanac is explicit about which is which:

- **Build snapshot** — the files committed under [`data/`](data/) and the numbers baked into
  `index.html`. Reproducible, offline-friendly, regenerated by the Python pipeline. This is what you
  get if you just open the page (the embedded forecast already reflects the live results and the FIFA
  blend *as of the last build*).
- **Live, in your browser** — the live-scores ribbon and (after a result changes or you hit "↻ Refresh")
  every 2026 panel re-read the **ESPN** feed and re-run the simulation client-side. Nothing is written
  back to disk; it lives only in the open tab.

The **CSV export** mirrors this. Matches / goals / standings always export the ESPN-overlaid live state.
The **forecast CSV** is tagged: `data_state=snapshot` with the build `as_of` date if you haven't
refreshed, or `data_state=live` with the current `as_of` once you have — so a downloaded file always
says what it is. The market-odds CSV is the committed snapshot (the-odds-api's terms; the live odds
quota isn't spent on page loads). Short version: **the repo holds a fixed, reproducible dataset; the app
adds a live layer on top and labels every export accordingly.**

## Optional accuracy boosters (still €0)

All built-in; each is off until you provide the input.

- **Manual strength overrides** (`data/adjustments.json`) — copy
  [`data/adjustments.example.json`](data/adjustments.example.json) and edit:
  - **Squad value** — paste ~48 squad market-value figures from Transfermarkt's public "most valuable
    national teams" page (no scraping); z-scored into an Elo adjustment.
  - **Injuries / suspensions / judgement** — a direct per-team Elo nudge (e.g. `-30` for a key player out).
  Applied at freeze time, so they flow through the simulation, the embed **and** the in-browser refresh.
- **Bookmaker-odds blend** — set a free [the-odds-api](https://the-odds-api.com/) key in your
  environment and the pipeline pulls **two** de-vigged WC2026 markets:
  - **Outright winner** — regressed into Elo units; each team pulled halfway toward it.
  - **Match (h2h)** — an extra pairwise nudge for upcoming games.

  ```bash
  ODDS_API_KEY=your_key_here python3 tools/build_wc2026_dataset.py
  ```

  The key is read **only** from the `ODDS_API_KEY` environment variable — never committed, never sent
  to the browser; we publish our Elo-derived forecast, not the raw odds (the collected odds save to
  `data/wc2026_odds.csv` for your own use, with attribution). the-odds-api sells only the winner +
  match markets, so stage probabilities like group-stage-exit (= 1 − reach-knockout) are our model's,
  now market-informed. Without the key, the blend is simply skipped.

> Honest note: the blend weight (50%) and any injury nudges are judgement calls and aren't backtested —
> treat them as informed adjustments, not gospel.

## What's in `data/`

| File | Contents |
|---|---|
| `wc2026_team_match_log.csv` | One row per team per match for the WC2026 nations, Jan 2022 → Jun 10 2026: date, competition, season, stage, team, confederation, opponent, home/away, goals, result, venue + pre-match **Elo** (`elo_pre`, `opp_elo_pre`, `elo_win_prob`, `elo_post`, `elo_change`). Extended stats (shots, possession, xG, cards) are blank — they don't exist for free across all these matches. |
| `coverage_report.md` | How much of the requested schema is fillable for free, per column and per competition, plus a squad-list reconciliation against the actual qualified 48. |
| `wc2026_power.json` | The forecast snapshot: per-team Elo, current points, recent form, market title prob, **official FIFA rank/points/Elo-equivalent**, and probabilities of winning the group / reaching each round / lifting the trophy, with confidence + `fifa_blend` metadata. |
| `wc2026_odds.csv` | *(only when built with `ODDS_API_KEY`)* de-vigged winner + match odds, bookmaker-averaged. Odds via the-odds-api.com. |
| `adjustments.example.json` | Template for the optional manual strength overrides. |

## Caveats

- Even with the market blend, this can't fully see who's injured or in form; knockout football is
  high-variance. Outputs are **probabilities, not predictions**.
- Goal/scorer figures follow the openfootball dataset, which has incomplete goal detail for several
  mid-century editions — historical scorer lists reflect *recorded* goals, not the official record.

## Deploy (Netlify)

It's a static site — no build. [`netlify.toml`](netlify.toml) sets `publish = "."` and an empty build
command. In the Netlify UI, leave **Base directory blank** (the common gotcha) and it serves
`index.html` from the repo root. For the optional market blend in CI, add `ODDS_API_KEY` as a build
environment variable / secret.

## Data sources & credits

- **[openfootball/worldcup.json](https://github.com/openfootball/worldcup.json)** — historical match
  data and the 2026 schedule/bracket (CC0 / public domain).
- **[martj42/international_results](https://github.com/martj42/international_results)** — international
  results history used for Elo and form (CC0).
- **[the-odds-api.com](https://the-odds-api.com/)** — optional betting-market odds.
- **ESPN public scoreboard** — live in-play scores (free, no key).
- **[FIFA / Coca-Cola World Ranking](https://inside.fifa.com/fifa-world-ranking/men)** — official points,
  pasted in by hand (no scraping; FIFA freezes the ranking during the World Cup, so one copy stays valid).
- Elo methodology after **[World Football Elo Ratings](https://eloratings.net/)**.

FIFA also publishes an official read-only API (the "Give Voice to Football" FAPIs); it's richer but
sits behind a WAF that blocks non-browser clients, so it's documented in the almanac but not used as a
live feed.

## Project structure

```
world-cup-almanac/
├── index.html                       # the almanac (open in a browser)
├── netlify.toml                     # static-site deploy config
├── tools/
│   └── build_wc2026_dataset.py      # the data + forecast pipeline
├── data/
│   ├── wc2026_team_match_log.csv    # per-team-per-match log + Elo
│   ├── coverage_report.md           # what's fillable for free
│   ├── wc2026_power.json            # the live forecast (embedded into index.html)
│   ├── wc2026_odds.csv              # collected market odds (only if built with a key)
│   └── adjustments.example.json     # template for manual strength overrides
├── requirements.txt                 # (none required; certifi optional)
├── HOW-IT-WORKS.md                  # student-friendly explainer of the whole model
├── LICENSE
└── README.md
```

## License

Code: MIT (see [LICENSE](LICENSE)). Redistributed data remains under its sources' terms (credited
above); market odds are subject to the-odds-api's terms.

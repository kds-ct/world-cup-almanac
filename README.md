# World Cup Almanac

An interactive FIFA World Cup data almanac (every men's tournament, 1930 → 2026) **and** a
zero-cost data pipeline that computes World-Football Elo from scratch and runs a **live**
Monte-Carlo forecast of World Cup 2026.

Two pieces, one repo:

| Part | File | What it does |
|---|---|---|
| **Almanac** (web) | [`index.html`](index.html) | Self-contained dashboard — group standings, golden boot, goal-timing charts, the full knockout bracket, a searchable match explorer, an all-time view, a live 2026 forecast, and CSV export. No build step, no dependencies. |
| **Data pipeline** (Python) | [`tools/build_wc2026_dataset.py`](tools/build_wc2026_dataset.py) | Pulls the complete international results history, computes Elo, emits a per-team-per-match CSV + coverage report, runs the live forecast, and refreshes the dashboard's embedded numbers. |

## Quick start

**View the almanac** — open `index.html` in any modern browser (it fetches historical match
data from the openfootball dataset via the jsDelivr CDN, so an internet connection is needed),
or serve the folder and visit it:

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

**Regenerate the data + forecast** (free, no API keys):

```bash
python3 tools/build_wc2026_dataset.py
```

This rewrites everything in [`data/`](data/) and re-embeds the latest forecast into
`index.html`. Standard library only — no `pip install` required. (If your Python lacks
root CA certificates, `pip install certifi` and it will be picked up automatically.)

## What's in `data/`

| File | Contents |
|---|---|
| `wc2026_team_match_log.csv` | One row per team per match for the WC2026 nations, Jan 2022 → Jun 10 2026. Real columns: date, competition, season, stage, team, confederation, opponent, home/away, goals, result, venue + pre-match **Elo** (`elo_pre`, `opp_elo_pre`, `elo_win_prob`, `elo_post`, `elo_change`). Extended stats (shots, possession, xG, cards, …) are intentionally blank — see below. |
| `coverage_report.md` | Exactly how much of the requested schema is fillable for free, per column and per competition, plus a squad-list reconciliation against the actual qualified 48. |
| `wc2026_power.json` | The live forecast: per-team Elo, current points, and probabilities of winning the group / reaching each round / lifting the trophy. |

## How the forecast works

- **Elo**: World-Football-style Elo (margin-of-victory multiplier, match-importance weighting,
  +100 home advantage) computed from scratch over **every** men's international since 1872, using
  the open results history.
- **Live conditioning**: actual 2026 group results so far are *locked in*; only the remaining
  fixtures and the knockout rounds are simulated.
- **Real format**: 30,000 Monte-Carlo runs of the genuine 2026 structure — 12 groups, **32 of 48
  advance** (top 2 of each group + the 8 best third-placed), then the official Round-of-32 → Final
  bracket. Hosts (USA/Canada/Mexico) get a modest +50 Elo home bump.

### Honest caveats

- This is a pure **team-strength** model. It does **not** know about squad turnover, ageing
  players, injuries or current form — *Germany 2026 ≠ Germany 2022*. Treat the outputs as
  **probabilities, not predictions**; knockout football is high-variance.
- At €0, extended match statistics (shots, possession, xG, cards, …) simply do not exist for
  friendlies and minor-confederation qualifiers, so those CSV columns are empty by design. The
  highest-signal free feature — Elo — is provided instead.

## Data sources & credits

- **[openfootball/worldcup.json](https://github.com/openfootball/worldcup.json)** — historical
  match data and the 2026 schedule/bracket (CC0 / public domain).
- **[martj42/international_results](https://github.com/martj42/international_results)** — the
  complete international results history used to compute Elo (CC0).
- Elo methodology after **[World Football Elo Ratings](https://eloratings.net/)**.

FIFA also publishes an official read-only API (the "Give Voice to Football" FAPIs); it is richer
but sits behind a WAF that blocks non-browser clients, so it is documented in the almanac but not
used as a live feed.

## Project structure

```
world-cup-almanac/
├── index.html                     # the almanac (open in a browser)
├── tools/
│   └── build_wc2026_dataset.py    # the €0 data + forecast pipeline
├── data/
│   ├── wc2026_team_match_log.csv
│   ├── coverage_report.md
│   └── wc2026_power.json
├── requirements.txt
├── LICENSE
└── README.md
```

## License

Code: MIT (see [LICENSE](LICENSE)). Data is redistributed from the public-domain sources credited
above; please respect their terms.

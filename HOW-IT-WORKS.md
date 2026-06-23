# How the World Cup Almanac works — a friendly explainer

*A guide you can read once and then explain to your class. No stats degree required.*

---

## The 60-second version

We want to answer questions like *"what's the chance Argentina win the 2026 World Cup?"* You can't just
*know* the answer — football is full of upsets. So instead we do three things:

1. **Score every team's strength** with a number called an **Elo rating** (the same idea chess uses).
2. **Turn that into match odds** — a stronger team is more likely to win, but not certain.
3. **Play the rest of the tournament 50,000 times on the computer**, with a bit of randomness each time,
   and count how often each result happens.

If a team lifts the trophy in 11,500 of those 50,000 imaginary tournaments, we say it has a **23% chance**.
That's it. Everything else is making those three steps more accurate and more honest.

---

## 1. Where do the numbers come from?

Everything is **free and public** — no expensive data, no paywalls:

| Source | What we take from it |
|---|---|
| **openfootball** (a public dataset) | The results of every World Cup ever, and the 2026 schedule/bracket. |
| **martj42** (a public dataset) | The result of *every* international match since **1872** (~49,000 games). |
| **ESPN's public scoreboard** | **Live** in-play scores and goal/card detail for 2026, refreshed automatically. |
| **the-odds-api** *(optional)* | The **betting market's** odds — what bookmakers think will happen. |
| **FIFA World Ranking** | The **official** ranking points — used as a second opinion on team strength (see §5). |

The first three are completely free. The odds need a free account key, but they're optional. The FIFA
points are copied by hand from FIFA's site (it freezes the ranking during the World Cup, so one copy lasts).

---

## 2. Rating every team: Elo

**The idea:** every team has a strength number (its *Elo rating*). Win, and it goes up; lose, and it goes
down. The clever part is *how much* it changes:

- **Beating a strong team** earns you a lot of points; beating a weak team earns you very little.
- **Losing to a weak team** costs you a lot.
- **Winning by a bigger margin** moves the number a bit more.
- **Important games** (a World Cup match) count more than a meaningless friendly.

We start everyone at 1500 and replay all 49,000 matches since 1872 in order, nudging the numbers after
each one. By the time we reach today, the ratings reflect how strong each team really is. (Brazil and
Argentina sit around 2100–2200; a minnow might be 1500–1700.)

> **The one formula**, if your professor asks:
> `new rating = old rating + K × G × (actual result − expected result)`
> The *expected result* comes from the rating gap: a 100-point favourite is expected to win about 64% of
> the time. `K` is how important the match is; `G` rewards bigger winning margins.

**Why Elo and not just "who has the best players?"** Because player data isn't free, and results since 1872
already capture a huge amount. (We patch the player-quality gap later — see steps 5 and 6.)

---

## 3. Predicting one match: loaded dice

Knowing two teams' ratings, how do we simulate a single game? We use the rating gap to decide how many
goals each side is *likely* to score, then **roll dice** for the actual score.

The dice are a **Poisson distribution** — the standard maths for "how many rare events happen in a fixed
time," which is exactly what goals are. A team expected to score ~2 goals will *usually* score 1–3, but
sometimes 0, sometimes 5. The bigger the rating gap, the more goals we expect the favourite to score —
so genuine blowouts (4–0, 5–0) can happen, just like real life.

We didn't guess the dice settings — we **fit them to history** (a technique called *maximum likelihood*):
we asked "what settings make our simulated scorelines look most like real international scorelines?" and
used the answer.

---

## 4. Playing the tournament 50,000 times: Monte Carlo

Here's the heart of it. We don't predict one outcome — we simulate the **entire rest of the tournament,
start to finish, fifty thousand times**:

- Each group game: roll the loaded dice → a scoreline → update the group table.
- Work out who finishes top 2, plus the 8 best third-placed teams (the real 2026 rules).
- Run the knockout bracket the same way, all the way to the final.

That's **one** simulated tournament, with one champion. Do it 50,000 times and you get 50,000 (often
different!) champions. The **percentages are just tallies**: France reaches the final in 30,000 of the
50,000 runs → 60% chance to reach the final.

This is called the **Monte Carlo method**, named after the casino — because it deliberately uses
randomness. The more times you run it, the steadier the numbers get (the wobble shrinks like 1 ÷ √N,
which is why 50,000 runs is much steadier than 1,000).

> **Analogy:** it's like asking "is this coin fair?" by flipping it 50,000 times and counting, instead of
> trying to calculate it perfectly. Brute force, but it works.

---

## 5. Keeping it real: live results + the betting market

A pre-tournament prediction gets stale the moment games are played. So:

- **Live conditioning.** We pull the real 2026 results (live, from ESPN) and **lock them in** — only the
  games that *haven't* happened yet are simulated. If Argentina have already won twice, every one of the
  50,000 simulations starts from that fact. This is also why the whole 2026 page (standings, top scorers,
  goal charts, bracket) updates as games finish — it all reads from the same live data.

- **The betting market.** Bookmakers' odds quietly contain information our maths can't see: who's injured,
  who's out of form, which young players have broken through. So *(optionally)* we nudge each team's rating
  **halfway toward** what the market implies. This is the "**wisdom of the crowd**" — thousands of people
  betting real money is a powerful signal. (We show the market's number next to ours so you can compare.)

- **The official FIFA ranking.** Here's a neat fact: FIFA's own world ranking is built on the **same Elo
  method** we use — just tuned a bit differently. That makes it a perfect *second opinion*. We take the
  official points, stretch them onto our rating scale, and pull each team's strength **35% of the way
  toward** FIFA's number — a consensus of "our Elo" and "FIFA's Elo." Two independent estimates blended
  together are usually more accurate than either alone. (The forecast page shows the full official ranking,
  with our Elo beside it; where they disagree — say a team we rate high but FIFA rates lower — the blend
  splits the difference, which keeps us honest.) FIFA freezes its ranking during the World Cup, so the
  numbers are fixed for the whole tournament.

---

## 5b. Choosing how much history to use

By default we rate every team on **all internationals since 1872** — maximum stability. But "since 1872"
also means a great team's bad recent run barely moves its number. So the forecast page has a **History-window
slider**: drag it to, say, 2018 and we *recompute* every team's Elo from **only** the matches since then
(the full results history is fetched and replayed right in your browser), then re-run the whole simulation.

- **Short window** (e.g. since 2022) → reacts fast to current form, but is noisier.
- **Long window** (since 1872) → steadier, but slower to notice a team rising or falling.

It's a great way to *see* how much "recent form vs. long history" changes who the model favours. (The
betting-market blend only applies at the full-history default; custom windows use pure Elo + the FIFA blend.)

> **One honest detail about "Current Form":** the little W-D-L form strings are computed when the data is
> **rebuilt** (daily), not on every live in-browser refresh — they don't feed the prediction maths, they're
> there to *show* recent results, and during the tournament the daily rebuild picks up each team's World
> Cup games within a day. Everything that *does* drive the forecast (Elo, the locked results, the odds) is
> what updates live.

## 6. Cards and suspensions

Referees' cards matter for more than discipline tables. Under FIFA's rules, **two yellow cards** (or one
**red**) means a player is **banned for the next match**. If that's a key player, their team is weaker for
that game.

We read every card from the same live ESPN feed, build a **suspension watch** (who's banned, who's one
booking away), and feed it into the forecast: a banned player **nudges their team's rating down** for their
next game — and *more* so if they've been scoring (our rough proxy for "how important they are"). It's a
small, honest effect, because we can't truly know how good every player is.

---

## 7. How sure are we? Confidence scores

A good forecast should tell you how much to trust it. We show two scores:

- **Data confidence** — how solid the *inputs* are (do we have all the results? are they recent? how much
  is just low-value friendly matches?).
- **Forecast confidence** — for each number, we start at 100 and subtract: a bit for **Monte-Carlo wobble**
  (smaller with more simulations), more for **how much of the tournament is still unplayed**, and a fixed
  **honesty penalty** that *never* goes away — because no model can perfectly know who's injured or in
  form. That's why our confidence **never reads 100%**; claiming certainty would be dishonest.

---

## 8. What it *can't* do (be honest in your talk!)

- It's mostly a **team-strength** model. The market blend and card data help, but it still can't see a
  tactical mismatch, a manager's plan, or the weather.
- **Knockout football is wild.** A single penalty shootout can flip a "70%" favourite. Our numbers are
  **probabilities, not predictions** — a 25% champion is *likely to lose*, and that's fine.
- Some inputs are **estimates**: the player-suspension impact and the blend weight are sensible choices,
  not proven-optimal ones.

A good forecaster is judged not by "did the favourite win" but by **whether things that were said to be
30% likely actually happen about 30% of the time.**

---

## Glossary (for the Q&A)

- **Elo rating** — a single number for a team's strength; goes up for good results, down for bad ones.
- **Poisson distribution** — the maths of counting random events (here, goals in a match).
- **Monte Carlo simulation** — answering a hard question by running it with randomness many times and counting.
- **De-vigging odds** — removing the bookmaker's built-in profit margin to get the "true" implied probability.
- **Conditioning** — fixing the known facts (already-played results) before simulating the unknowns.
- **Calibration** — checking that things you call "30% likely" really happen ~30% of the time.

---

## "If the professor asks…"

- **"Why Elo since 1872?"** — More history = more stable ratings; old games barely move modern numbers but
  give every team a solid baseline.
- **"Isn't copying the bookmakers cheating?"** — We don't copy; we *blend*. The market is the accepted
  accuracy benchmark in sports forecasting, so ignoring it would be the mistake.
- **"Why blend in the FIFA ranking if it's also Elo?"** — Because it's an *independent* Elo, tuned
  differently and computed on different data. Averaging two independent estimates of the same thing cuts
  the error — the same reason you ask a second doctor. We weight it 35%, so it informs without dominating.
- **"How do you know it's any good?"** — You'd measure it with a **Brier score** or **log-loss** (which
  reward being well-calibrated), tested on past tournaments — not by whether one favourite happened to win.
- **"What would make it better?"** — Player-level ratings (squad value, minutes, xG) and proper backtesting
  of the blend weight. All possible for free; just more work.

---

*Built with open data and a lot of simulated football. See [`README.md`](README.md) for how to run it.*

#!/usr/bin/env python3
"""
build_wc2026_dataset.py  —  €0 data pull for a WC2026 prediction model.

WHAT IT DOES (all from free, legal, public sources — no API keys, no paid tiers):
  1. Downloads the complete international results history (Mart Jürisoo, GitHub, MIT-spirit).
  2. Computes World-Football-style Elo for every nation from scratch over the full history.
  3. Emits the requested per-team-per-match CSV for 2022-01-01 .. 2026-06-10 for the
     WC2026 nations, with HONEST nulls for stats that simply do not exist for free
     (shots / possession / xG / cards / referee for friendlies & minor qualifiers).
  4. Writes a coverage report quantifying exactly how much of the 25-column spec is fillable.
  5. Runs a faithful Monte-Carlo of the real 2026 format (12 groups, top-2 + 8 best thirds,
     R32 -> Final using the official bracket) and writes wc2026_power.json for the almanac.

Run:  python3 tools/build_wc2026_dataset.py
Outputs land in ./wc2026-data/
"""
import csv, datetime, io, json, math, os, random, ssl, sys, urllib.request
from collections import defaultdict

def _ssl_context():
    """Use certifi if available; otherwise fall back to unverified (public read-only data)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
_SSL = _ssl_context()

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(os.path.dirname(HERE), "data")
os.makedirs(OUT, exist_ok=True)

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
TEAMS_URL   = "https://cdn.jsdelivr.net/gh/openfootball/worldcup.json@master/2026/worldcup.teams.json"
WINDOW_START, WINDOW_END = "2022-01-01", "2026-06-10"

def fetch(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "wc2026-research/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_SSL) as r:
        data = r.read().decode("utf-8")
    return data if raw else json.loads(data)

# ----------------------------------------------------------------------------- nations
TEAMS = fetch(TEAMS_URL)                       # the ACTUAL qualified 48
QUALIFIED = {t["name"]: {"confed": t["confed"], "group": t["group"], "code": t["fifa_code"]} for t in TEAMS}
# friend's provisional list extras that did NOT actually qualify — kept (flagged) so his pipeline runs
EXTRAS = {"China": "AFC", "Indonesia": "AFC", "Bolivia": "CONMEBOL", "Cameroon": "CAF", "Nigeria": "CAF"}
HOSTS = {"USA", "Canada", "Mexico"}
UNIVERSE = dict(QUALIFIED)
for n, c in EXTRAS.items():
    UNIVERSE.setdefault(n, {"confed": c, "group": None, "code": ""})

# openfootball/Mart name reconciliation (left = our canonical, right = Mart spelling)
ALIAS = {"Bosnia & Herzegovina": "Bosnia and Herzegovina", "USA": "United States"}
TO_MART  = {k: ALIAS.get(k, k) for k in UNIVERSE}
FROM_MART = {v: k for k, v in TO_MART.items()}
def canon(mart_name): return FROM_MART.get(mart_name, mart_name)

# ----------------------------------------------------------------------------- Elo engine
def k_weight(t):
    t = t.lower()
    if t == "fifa world cup": return 60.0
    if "qualification" in t or "qualifier" in t: return 40.0
    if "nations league" in t: return 40.0
    if t in ("uefa euro", "copa américa", "copa america", "african cup of nations",
             "afc asian cup", "gold cup", "concacaf gold cup", "ofc nations cup"): return 50.0
    if t in ("friendly", "fifa series", "concacaf series", "kirin cup", "king's cup"): return 20.0
    return 30.0  # other minor confederation tournaments

def g_mult(gd):
    gd = abs(gd)
    if gd <= 1: return 1.0
    if gd == 2: return 1.5
    return (11.0 + gd) / 8.0

def expected(dr):  # dr = rating diff incl. home advantage
    return 1.0 / (10.0 ** (-dr / 400.0) + 1.0)

print("Downloading results.csv …", file=sys.stderr)
rows = list(csv.DictReader(io.StringIO(fetch(RESULTS_URL, raw=True))))
rows.sort(key=lambda r: r["date"])

elo = defaultdict(lambda: 1500.0)
elo_pre = None                       # snapshot of ratings as of WINDOW_END (pre-tournament)
form_hist = defaultdict(list)        # canonical team -> [(date, W/D/L, goal_diff)] chronological
calib = []                           # (rating_gap_incl_home, home_goals, away_goals) for goal-model MLE
match_log = []   # window matches with pre-match ratings captured
for r in rows:
    if elo_pre is None and r["date"] > WINDOW_END:
        elo_pre = dict(elo)
    h, a = r["home_team"], r["away_team"]
    try:
        hs, as_ = int(r["home_score"]), int(r["away_score"])
    except (ValueError, KeyError):
        continue
    neutral = str(r.get("neutral", "")).strip().lower() in ("true", "1", "yes")
    rh, ra = elo[h], elo[a]
    ha = 0 if neutral else 100
    we_h = expected((rh + ha) - ra)
    w_h = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
    K = k_weight(r["tournament"]); G = g_mult(hs - as_)
    delta = K * G * (w_h - we_h)
    if WINDOW_START <= r["date"] <= WINDOW_END and (canon(h) in UNIVERSE or canon(a) in UNIVERSE):
        match_log.append({"r": r, "rh": rh, "ra": ra, "we_h": we_h, "neutral": neutral})
    for tm, gf, ga in ((h, hs, as_), (a, as_, hs)):     # recent-form history (chronological)
        cn = canon(tm)
        if cn in QUALIFIED:
            form_hist[cn].append((r["date"], "W" if gf > ga else "D" if gf == ga else "L", gf - ga))
    if r["date"] >= "2010-01-01" and K >= 40:            # recent competitive games -> goal-model calibration set
        calib.append(((rh + ha) - ra, hs, as_))
    elo[h] = rh + delta
    elo[a] = ra - delta

# pre-tournament rating per nation = rating after its last match on/before WINDOW_END
if elo_pre is None: elo_pre = dict(elo)
final_elo = {n: elo_pre.get(TO_MART[n], 1500.0) for n in UNIVERSE}

# ---- optional, free, MANUAL strength overrides (squad value #2 + injuries #4) ----
# Drop a data/adjustments.json (see data/adjustments.example.json) to nudge ratings at freeze time.
# Applied here so the change flows through everything: the sim, the embedded numbers, and the
# in-browser "Refresh" button (which reuses the frozen Elo). Absent file -> no change.
ADJ = {}
_adj = os.path.join(OUT, "adjustments.json")
if os.path.exists(_adj):
    try: cfg = json.load(open(_adj, encoding="utf-8"))
    except Exception: cfg = {}
    sv = {n: v for n, v in (cfg.get("squad_value_eur_m") or {}).items() if n in QUALIFIED and v and v > 0}
    if len(sv) >= 8:                                  # z-score squad value -> Elo, spread over `span`
        lv = {n: math.log(v) for n, v in sv.items()}
        mu = sum(lv.values()) / len(lv)
        sd = (sum((x - mu) ** 2 for x in lv.values()) / len(lv)) ** 0.5 or 1.0
        span = float(cfg.get("squad_value_elo_span", 120))
        for n, x in lv.items(): ADJ[n] = ADJ.get(n, 0.0) + (x - mu) / sd * (span / 4)
    for n, d in (cfg.get("elo_delta") or {}).items():  # direct nudges (injuries / judgement)
        if n in QUALIFIED:
            try: ADJ[n] = ADJ.get(n, 0.0) + float(d)
            except (TypeError, ValueError): pass
    for n, d in ADJ.items(): final_elo[n] += max(-120.0, min(120.0, d))
    if ADJ: print(f"applied {len(ADJ)} manual strength overrides from adjustments.json", file=sys.stderr)

# ---- optional, free, market-informed Elo blend (#1) ----
# If ODDS_API_KEY is set in the environment, pull de-vigged WC2026 outright (title) odds and pull each
# team's frozen Elo partway toward what the market implies. The KEY stays in the environment (never
# committed or sent to the browser); only our Elo-derived forecast is published, not the raw odds.
#   run with:  ODDS_API_KEY=xxxxx python3 tools/build_wc2026_dataset.py
MARKET_BLEND = None
MKT_TITLE = {}                      # canonical team -> de-vigged market P(title)
ODDS_ROWS = []                      # rows for data/wc2026_odds.csv
ODDS_KEY = os.environ.get("ODDS_API_KEY")
def _devig(outcomes):
    ocs = [o for o in outcomes if o.get("price", 0) > 0]
    tot = sum(1.0 / o["price"] for o in ocs)
    return {o["name"].strip(): ((1.0 / o["price"]) / tot, o["price"]) for o in ocs} if tot > 0 else {}
if ODDS_KEY:
    base = "https://api.the-odds-api.com/v4/sports/"
    qs = "/odds/?apiKey=" + ODDS_KEY + "&regions=eu,uk&oddsFormat=decimal&markets="
    try:   # ---- 1) OUTRIGHT WINNER market -> title prob + strength blend
        t_p, t_d = defaultdict(list), defaultdict(list)
        for ev in json.loads(fetch(base + "soccer_fifa_world_cup_winner" + qs + "outrights", raw=True), strict=False):
            for bk in ev.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    for nm, (p, dec) in _devig(mk.get("outcomes", [])).items():
                        t_p[nm].append(p); t_d[nm].append(dec)
        for nm in t_p:
            prob = sum(t_p[nm]) / len(t_p[nm])
            if nm in QUALIFIED: MKT_TITLE[nm] = prob
            ODDS_ROWS.append(["winner", "", nm, round(sum(t_d[nm]) / len(t_d[nm]), 2), round(prob, 4), len(t_d[nm])])
        xs = {t: math.log(p) for t, p in MKT_TITLE.items() if p > 0}
        if len(xs) >= 12:                                          # regress Elo on log market prob, blend
            nn = len(xs); mx = sum(xs.values()) / nn; my = sum(final_elo[t] for t in xs) / nn
            var = sum((xs[t] - mx) ** 2 for t in xs) or 1.0
            a = sum((xs[t] - mx) * (final_elo[t] - my) for t in xs) / var; b = my - a * mx
            W = 0.5
            for t in xs: final_elo[t] += max(-100.0, min(100.0, W * (a * xs[t] + b - final_elo[t])))
            MARKET_BLEND = {"w": W, "title_teams": len(xs)}
            print(f"title-market blend: {len(xs)} teams pulled {int(W*100)}% toward odds", file=sys.stderr)
    except Exception as e:
        print(f"title odds skipped ({e})", file=sys.stderr)
    try:   # ---- 2) MATCH (h2h) market -> per-game odds + light pairwise Elo nudge
        nudges, games = defaultdict(float), 0
        for ev in json.loads(fetch(base + "soccer_fifa_world_cup" + qs + "h2h", raw=True), strict=False):
            h, aw = ev.get("home_team", "").strip(), ev.get("away_team", "").strip()
            mp, md = defaultdict(list), defaultdict(list)
            for bk in ev.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    for nm, (p, dec) in _devig(mk.get("outcomes", [])).items(): mp[nm].append(p); md[nm].append(dec)
            P = {nm: sum(v) / len(v) for nm, v in mp.items()}
            for nm in mp:
                ODDS_ROWS.append(["match_h2h", h + " v " + aw, nm, round(sum(md[nm]) / len(md[nm]), 2), round(P[nm], 4), len(md[nm])])
            if h in QUALIFIED and aw in QUALIFIED and P.get(h, 0) > 0 and P.get(aw, 0) > 0:
                p1 = min(0.99, max(0.01, P[h] / (P[h] + P[aw])))    # 2-way market win prob (home)
                market_dr = 400 * math.log10(p1 / (1 - p1))
                model_dr = (final_elo[h] + (50 if h in HOSTS else 0)) - (final_elo[aw] + (50 if aw in HOSTS else 0))
                d = 0.15 * (market_dr - model_dr); nudges[h] += d / 2; nudges[aw] -= d / 2; games += 1
        for t, d in nudges.items(): final_elo[t] += max(-40.0, min(40.0, d))
        if games and MARKET_BLEND is not None: MARKET_BLEND["match_games"] = games
        print(f"match-odds nudge applied over {games} upcoming games", file=sys.stderr)
    except Exception as e:
        print(f"match odds skipped ({e})", file=sys.stderr)
    if ODDS_ROWS:
        with open(os.path.join(OUT, "wc2026_odds.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["# odds via the-odds-api.com; decimal odds averaged across EU/UK bookmakers; devig = vig-removed probability"])
            w.writerow(["market", "match", "team_or_outcome", "avg_decimal_odds", "devig_probability", "n_bookmakers"])
            w.writerows(ODDS_ROWS)
        print(f"wrote data/wc2026_odds.csv ({len(ODDS_ROWS)} rows)", file=sys.stderr)

# ----------------------------------------------------------------------------- per-team-per-match CSV
SPEC_COLS = ["date","competition","season","stage","team","confederation","opponent","home_away",
             "goals_for","goals_against","result","shots","shots_on_target","shots_off_target",
             "possession_pct","corners","fouls","yellow_cards","red_cards","saves","offsides",
             "passes","pass_accuracy_pct","xg","venue","referee"]
BONUS_COLS = ["neutral","qualified_wc2026","elo_pre","opp_elo_pre","elo_win_prob","elo_post","elo_change"]
ALL_COLS = SPEC_COLS + BONUS_COLS
UNAVAILABLE = ["shots","shots_on_target","shots_off_target","possession_pct","corners","fouls",
               "yellow_cards","red_cards","saves","offsides","passes","pass_accuracy_pct","xg","referee"]

def stage_of(t):
    return "Qualification" if ("qualification" in t.lower() or "qualifier" in t.lower()) else "Tournament/Friendly"

out_rows = []
for m in match_log:
    r = m["r"]; h, a = r["home_team"], r["away_team"]
    hs, as_ = int(r["home_score"]), int(r["away_score"])
    venue = ", ".join(x for x in (r.get("city",""), r.get("country","")) if x)
    for side in ("h", "a"):
        team_m = h if side == "h" else a
        team = canon(team_m)
        if team not in UNIVERSE:
            continue
        opp = canon(a if side == "h" else h)
        gf, ga = (hs, as_) if side == "h" else (as_, hs)
        pre = m["rh"] if side == "h" else m["ra"]
        opp_pre = m["ra"] if side == "h" else m["rh"]
        wp = m["we_h"] if side == "h" else 1.0 - m["we_h"]
        K = k_weight(r["tournament"]); G = g_mult(hs - as_)
        w = 1.0 if gf > ga else 0.5 if gf == ga else 0.0
        post = pre + K * G * (w - wp)
        ha = "neutral" if m["neutral"] else ("home" if side == "h" else "away")
        row = {c: "" for c in ALL_COLS}
        row.update({
            "date": r["date"], "competition": r["tournament"], "season": r["date"][:4],
            "stage": stage_of(r["tournament"]), "team": team,
            "confederation": UNIVERSE[team]["confed"], "opponent": opp, "home_away": ha,
            "goals_for": gf, "goals_against": ga,
            "result": "W" if gf > ga else "D" if gf == ga else "L",
            "venue": venue,
            "neutral": m["neutral"], "qualified_wc2026": team in QUALIFIED,
            "elo_pre": round(pre, 1), "opp_elo_pre": round(opp_pre, 1),
            "elo_win_prob": round(wp, 4), "elo_post": round(post, 1),
            "elo_change": round(post - pre, 1),
        })
        out_rows.append(row)

out_rows.sort(key=lambda x: (x["team"], x["date"]))
csv_path = os.path.join(OUT, "wc2026_team_match_log.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ALL_COLS); w.writeheader(); w.writerows(out_rows)

# ----------------------------------------------------------------------------- coverage report
n_rows = len(out_rows); n_matches = n_rows  # one row per team per match
comp_counts = defaultdict(int)
for x in out_rows: comp_counts[x["competition"]] += 1
fill = {c: sum(1 for x in out_rows if str(x[c]) != "") / max(1, n_rows) for c in ALL_COLS}

friend_listed = [
    "Austria","Belgium","Bosnia & Herzegovina","Croatia","Czechia","England","France","Germany",
    "Netherlands","Norway","Portugal","Scotland","Spain","Sweden","Switzerland","Türkiye",
    "Algeria","Cameroon","Cape Verde","DR Congo","Egypt","Morocco","Nigeria","Senegal","South Africa","Tunisia",
    "Australia","China PR","Indonesia","Iran","Iraq","Japan","Qatar","Saudi Arabia","South Korea","Uzbekistan",
    "Argentina","Bolivia","Brazil","Colombia","Ecuador","Paraguay","Uruguay",
    "Canada","Curaçao","Haiti","Mexico","Panama","USA","New Zealand"]
# normalise the friend's spellings to the openfootball/canonical names used in QUALIFIED
norm_friend = {"Czechia":"Czech Republic","Türkiye":"Turkey","China PR":"China"}
friend_norm = {norm_friend.get(x, x) for x in friend_listed}
did_not_qualify = sorted(friend_norm - set(QUALIFIED))
qualified_not_listed = sorted(set(QUALIFIED) - friend_norm)

with open(os.path.join(OUT, "coverage_report.md"), "w") as f:
    f.write("# WC2026 data pull — coverage report\n\n")
    f.write(f"- Window: **{WINDOW_START} → {WINDOW_END}**\n")
    f.write(f"- Rows (one per team per match): **{n_rows}**\n")
    f.write(f"- Nations covered: **{len(UNIVERSE)}** (actual qualified 48 + {len(EXTRAS)} from the provisional list)\n\n")
    f.write("## Column fill rate (the €0 reality)\n\n| column | filled |\n|---|---|\n")
    for c in ALL_COLS:
        f.write(f"| {c} | {fill[c]*100:.0f}% |\n")
    f.write("\n**Unavailable at €0 (0% — no free source carries these for friendlies/minor qualifiers):** "
            + ", ".join(UNAVAILABLE) + ".\n")
    f.write("\n## Matches per competition\n\n| competition | rows |\n|---|---|\n")
    for comp, n in sorted(comp_counts.items(), key=lambda kv: -kv[1]):
        f.write(f"| {comp} | {n} |\n")
    f.write("\n## ⚠ Squad-list reconciliation (provisional list vs ACTUAL qualified 48)\n\n")
    f.write("Teams on the brief that did **NOT** qualify (flagged `qualified_wc2026=False`): "
            + (", ".join(did_not_qualify) or "none") + "\n\n")
    f.write("Teams that actually qualified but were **missing** from the brief: "
            + (", ".join(qualified_not_listed) or "none") + "\n")

# ----------------------------------------------------------------------------- Monte-Carlo forecast (real 48 only)
GROUPS = defaultdict(list)
for n, meta in QUALIFIED.items():
    GROUPS[meta["group"]].append(n)
HOSTS = {"USA", "Canada", "Mexico"}
HOST_BUMP = 50.0  # modest home advantage for hosts (deliberately < the +100 of a true home match,
                  # since most host games are not in that host's own stadium)
# Log-linear goal model: la = GOAL_BASE * 10^(GOAL_GAMMA * dr/400), lb = mirror. Mismatches produce
# MORE total goals (and real blowouts) instead of a fixed total. The two constants are MLE-fit to the
# recent competitive scorelines already in memory (no new data) — falling back to these if too few.
GOAL_BASE, GOAL_GAMMA = 1.32, 0.23
def _fit_goal_model(samples):
    if len(samples) < 500: return GOAL_BASE, GOAL_GAMMA
    samples = samples[-6000:]                                  # most-recent window, bounds runtime
    best, best_ll = (GOAL_BASE, GOAL_GAMMA), -1e18
    for bi in range(25):                                       # GOAL_BASE 1.00 .. 1.60
        B = 1.0 + 0.025 * bi; lnB = math.log(B)
        for gi in range(35):                                   # GOAL_GAMMA 0.06 .. 0.40
            Gm = 0.06 + 0.01 * gi; c = Gm * math.log(10) / 400.0
            ll = 0.0
            for dr, hg, ag in samples:
                lla = lnB + c * dr; llb = lnB - c * dr
                ll += hg * lla - math.exp(lla) + ag * llb - math.exp(llb)
            if ll > best_ll: best_ll, best = ll, (B, Gm)
    return best
GOAL_BASE, GOAL_GAMMA = _fit_goal_model(calib)
print(f"goal model (MLE on {min(len(calib),6000)} competitive matches): BASE={GOAL_BASE:.3f} GAMMA={GOAL_GAMMA:.3f}", file=sys.stderr)

def pois(lam):
    L = math.exp(-lam); k = 0; p = 1.0
    while True:
        k += 1; p *= random.random()
        if p <= L: return k - 1

def sim_goals(ta, tb, ra, rb):
    dr = (ra + (HOST_BUMP if ta in HOSTS else 0)) - (rb + (HOST_BUMP if tb in HOSTS else 0))
    la = min(6.0, max(0.05, GOAL_BASE * 10 ** (GOAL_GAMMA * dr / 400)))
    lb = min(6.0, max(0.05, GOAL_BASE * 10 ** (-GOAL_GAMMA * dr / 400)))
    return pois(la), pois(lb)

def ko_winner(ta, tb, ra, rb):
    dr = (ra + (HOST_BUMP if ta in HOSTS else 0)) - (rb + (HOST_BUMP if tb in HOSTS else 0))
    return ta if random.random() < expected(dr) else tb

# R32 topology: match number -> (slotA, slotB). slot = ("1",G)|("2",G)|("3",frozenset)|("M",num)
R32 = {
    73:(("2","A"),("2","B")), 74:(("1","E"),("3",frozenset("ABCDF"))), 75:(("1","F"),("2","C")),
    76:(("1","C"),("2","F")), 77:(("1","I"),("3",frozenset("CDFGH"))), 78:(("2","E"),("2","I")),
    79:(("1","A"),("3",frozenset("CEFHI"))), 80:(("1","L"),("3",frozenset("EHIJK"))),
    81:(("1","D"),("3",frozenset("BEFIJ"))), 82:(("1","G"),("3",frozenset("AEHIJ"))),
    83:(("2","K"),("2","L")), 84:(("1","H"),("2","J")), 85:(("1","B"),("3",frozenset("EFGIJ"))),
    86:(("1","J"),("2","H")), 87:(("1","K"),("3",frozenset("DEIJL"))), 88:(("2","D"),("2","G")),
}
LATER = {  # match number -> (("M",x),("M",y))
    89:(("M",74),("M",77)), 90:(("M",73),("M",75)), 91:(("M",76),("M",78)), 92:(("M",79),("M",80)),
    93:(("M",83),("M",84)), 94:(("M",81),("M",82)), 95:(("M",86),("M",88)), 96:(("M",85),("M",87)),
    97:(("M",89),("M",90)), 98:(("M",93),("M",94)), 99:(("M",91),("M",92)), 100:(("M",95),("M",96)),
    101:(("M",97),("M",98)), 102:(("M",99),("M",100)),
}
THIRD_SLOTS = [m for m,(a,b) in R32.items() if b[0]=="3"]  # matches needing a best-third

def assign_thirds(qualified_groups, slots):
    """Bijection: assign each qualifying third (by group letter) to a slot whose allowed set contains it."""
    order = sorted(slots, key=lambda m: len(R32[m][1][1]))  # most-constrained slot first
    result = {}
    def bt(i, remaining):
        if i == len(order): return True
        m = order[i]; allowed = R32[m][1][1]
        cands = list(remaining); random.shuffle(cands)   # random valid matching (de-biases vs 'first feasible')
        for g in cands:
            if g in allowed:
                result[m] = g; remaining.remove(g)
                if bt(i+1, remaining): return True
                remaining.add(g); del result[m]
        return False
    if bt(0, set(qualified_groups)): return result
    # fallback (combinatorially rare): arbitrary pairing
    for m, g in zip(order, qualified_groups): result[m] = g
    return result

# --- LIVE conditioning: lock the actual 2026 group results, nudge Elo, simulate only what's left ---
LIVE_URL = "https://cdn.jsdelivr.net/gh/openfootball/worldcup.json@master/2026/worldcup.json"
print("Downloading live 2026 results …", file=sys.stderr)
LIVE = fetch(LIVE_URL)
def _played(m):
    s = m.get("score"); return bool(s and s.get("ft") and s["ft"] and s["ft"][0] is not None)
grp_matches = [m for m in LIVE["matches"] if str(m.get("group","")).startswith("Group")]
played_g = sorted((m for m in grp_matches if _played(m)), key=lambda x: x["date"])
AS_OF = max((m["date"] for m in played_g), default=WINDOW_END)

# recent form: each team's last 5 internationals on/before AS_OF (W/D/L, points out of 15, goal diff)
FORM = {}
for n in QUALIFIED:
    recent = [x for x in form_hist[n] if x[0] <= AS_OF][-5:]
    FORM[n] = {"fm": "".join(x[1] for x in recent),
               "fp": sum(3 if r == "W" else 1 if r == "D" else 0 for _, r, _ in recent),
               "fgd": sum(gd for _, _, gd in recent)}

live_elo = {n: final_elo[n] for n in QUALIFIED}
for m in played_g:                       # move ratings with the results already in
    a, b = m["team1"], m["team2"]
    if a not in live_elo or b not in live_elo: continue
    fa, fb = m["score"]["ft"]; ra, rb = live_elo[a], live_elo[b]
    dr = (ra + (HOST_BUMP if a in HOSTS else 0)) - (rb + (HOST_BUMP if b in HOSTS else 0))
    w = 1.0 if fa > fb else 0.5 if fa == fb else 0.0
    d = 60.0 * g_mult(fa - fb) * (w - expected(dr))
    live_elo[a] = ra + d; live_elo[b] = rb - d

cur = {n: [0,0,0,0] for n in QUALIFIED}    # P, Pts, GF, GA so far
locked = defaultdict(list); remaining = defaultdict(list)
for m in grp_matches:
    a, b = m["team1"], m["team2"]
    if a not in cur or b not in cur: continue   # safety: skip any non-canonical names
    g = m["group"].split()[-1]
    if _played(m):
        fa, fb = m["score"]["ft"]; locked[g].append((a, b, fa, fb))
        cur[a][0]+=1; cur[b][0]+=1; cur[a][2]+=fa; cur[a][3]+=fb; cur[b][2]+=fb; cur[b][3]+=fa
        if fa>fb: cur[a][1]+=3
        elif fb>fa: cur[b][1]+=3
        else: cur[a][1]+=1; cur[b][1]+=1
    else:
        remaining[g].append((a, b))

# played KNOCKOUT results -> lock them onto the fixed bracket match numbers (active once KO begins)
def _is_ph(n): return (not n) or n[0].isdigit() or (len(n) > 1 and n[0] in "WL" and n[1:].isdigit()) or "/" in n
def _ko_win(m):
    s = m.get("score") or {}
    if s.get("p"): return m["team1"] if s["p"][0] > s["p"][1] else m["team2"]
    base = s.get("et") or s.get("ft")
    if base and base[0] is not None and base[0] != base[1]: return m["team1"] if base[0] > base[1] else m["team2"]
    return None
koWin = {}   # openfootball match number (== bracket position) -> (winner, teamA, teamB)
finalWin = None
for m in LIVE["matches"]:
    r = m.get("round")
    if r not in ("Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Final"): continue
    a, b = m["team1"], m["team2"]
    if _is_ph(a) or _is_ph(b): continue
    w = _ko_win(m)
    if not w: continue
    if r == "Final": finalWin = (w, a, b)
    else: koWin[m["num"]] = (w, a, b)   # key by the match's own num, not enumeration order
TOTAL_PLAYED = sum(1 for m in LIVE["matches"] if _played(m))
TOTAL_MATCHES = len(LIVE["matches"])

N = 50000
reach = {n: defaultdict(int) for n in QUALIFIED}   # stage -> count
win_group = defaultdict(int)
STAGES = ["knockout","r16","quarter","semi","final","title"]

for _ in range(N):
    pos = {}   # (place, group) -> team ; place in {1,2}
    thirds = []  # (pts, gd, gf, team, group)
    for g, teams in GROUPS.items():
        tab = {t: [0,0,0] for t in teams}  # pts, gd, gf
        for (a, b, fa, fb) in locked[g]:                 # actual results so far (fixed)
            tab[a][1]+=fa-fb; tab[b][1]+=fb-fa; tab[a][2]+=fa; tab[b][2]+=fb
            if fa>fb: tab[a][0]+=3
            elif fb>fa: tab[b][0]+=3
            else: tab[a][0]+=1; tab[b][0]+=1
        for (a, b) in remaining[g]:                       # simulate only the unplayed fixtures
            ga, gb = sim_goals(a, b, live_elo[a], live_elo[b])
            tab[a][1]+=ga-gb; tab[b][1]+=gb-ga; tab[a][2]+=ga; tab[b][2]+=gb
            if ga>gb: tab[a][0]+=3
            elif gb>ga: tab[b][0]+=3
            else: tab[a][0]+=1; tab[b][0]+=1
        rank = sorted(teams, key=lambda t:(tab[t][0],tab[t][1],tab[t][2],random.random()), reverse=True)
        pos[("1",g)] = rank[0]; pos[("2",g)] = rank[1]
        win_group[rank[0]] += 1
        t3 = rank[2]
        thirds.append((tab[t3][0],tab[t3][1],tab[t3][2],t3,g))
    # top-8 thirds
    thirds.sort(key=lambda x:(x[0],x[1],x[2],random.random()), reverse=True)
    q = thirds[:8]
    for _,_,_,t,_g in q: reach[t]["knockout"] += 1          # 8 best thirds
    for team in pos.values(): reach[team]["knockout"] += 1   # 24 group top-2
    third_assign = assign_thirds([x[4] for x in q], THIRD_SLOTS)
    third_team = {x[4]: x[3] for x in q}

    winners = {}
    for mnum in range(73, 89):           # Round of 32
        a, b = R32[mnum]
        ta = pos[a] if a[0] in ("1","2") else third_team[third_assign[mnum]]
        tb = pos[b] if b[0] in ("1","2") else third_team[third_assign[mnum]]
        if mnum in koWin and {ta, tb} == {koWin[mnum][1], koWin[mnum][2]}: w = koWin[mnum][0]
        else: w = ko_winner(ta, tb, live_elo[ta], live_elo[tb])
        winners[mnum] = w
        reach[w]["r16"] += 1
    for mnum in range(89, 103):          # R16 -> QF -> SF
        a, b = LATER[mnum]
        ta, tb = winners[a[1]], winners[b[1]]
        if mnum in koWin and {ta, tb} == {koWin[mnum][1], koWin[mnum][2]}: w = koWin[mnum][0]
        else: w = ko_winner(ta, tb, live_elo[ta], live_elo[tb])
        winners[mnum] = w
        if   89 <= mnum <= 96:  reach[w]["quarter"] += 1     # R16 winners reach QF
        elif 97 <= mnum <= 100: reach[w]["semi"] += 1        # QF winners reach SF
        else:                   reach[w]["final"] += 1       # SF winners = finalists
    fA, fB = winners[101], winners[102]
    if finalWin and {fA, fB} == {finalWin[1], finalWin[2]}: champ = finalWin[0]
    else: champ = ko_winner(fA, fB, live_elo[fA], live_elo[fB])
    reach[champ]["title"] += 1

power = []
for n, meta in QUALIFIED.items():
    power.append({
        "team": n, "confederation": meta["confed"], "group": meta["group"], "code": meta["code"],
        "elo": round(live_elo[n], 0),
        "elo_pre": round(final_elo[n], 0),
        "host": n in HOSTS,
        "pl": cur[n][0], "pts": cur[n][1], "gd": cur[n][2]-cur[n][3],
        "form": FORM[n]["fm"], "form_pts": FORM[n]["fp"], "form_gd": FORM[n]["fgd"],
        "mkt_title": round(MKT_TITLE.get(n, 0), 4),
        "p_win_group": round(win_group[n]/N, 4),
        "p_knockout": round(reach[n]["knockout"]/N, 4),
        "p_r16": round(reach[n]["r16"]/N, 4),
        "p_quarter": round(reach[n]["quarter"]/N, 4),
        "p_semi": round(reach[n]["semi"]/N, 4),
        "p_final": round(reach[n]["final"]/N, 4),
        "p_title": round(reach[n]["title"]/N, 4),
    })
power.sort(key=lambda x: -x["p_title"])
avg_q = sum(reach[n]["knockout"] for n in QUALIFIED)/N

# ---- DATA confidence (0-100): how solid the INPUTS are ----
#   C coverage : all model-relevant columns (date, competition, home/away, goals, neutral, venue) are filled -> 100
#   R recency  : penalise stale data (~ -1 point per 3 days since the last result), floored at 40
#   S source   : friendlies carry little team-strength signal; discount by half the friendly share
days_stale = (datetime.date.today() - datetime.date.fromisoformat(AS_OF)).days
C = 100
R = max(40, min(100, 100 - days_stale / 3))
friendly_share = comp_counts.get("Friendly", 0) / max(1, n_rows)
S = 100 * (1 - friendly_share * 0.5)
DATA_CONF = round(0.45 * C + 0.20 * R + 0.35 * S)
CONF = {"data": DATA_CONF, "C": C, "R": round(R), "S": round(S), "fs": round(friendly_share * 100)}

with open(os.path.join(OUT, "wc2026_power.json"), "w") as f:
    json.dump({"n_sims": N, "host_bump_elo": HOST_BUMP, "mode": "live",
               "as_of": AS_OF, "group_matches_played": len(played_g),
               "group_matches_total": len(grp_matches), "avg_qualifiers_per_sim": round(avg_q, 2),
               "matches_played": TOTAL_PLAYED, "matches_total": TOTAL_MATCHES, "confidence": CONF,
               "market_blend": MARKET_BLEND, "teams": power}, f, indent=1, ensure_ascii=False)

# ----------------------------------------------------------------------------- refresh dashboard embed
# Keep index.html self-contained (works offline / via file://) by splicing the compact forecast in.
import re
INDEX = os.path.join(os.path.dirname(HERE), "index.html")
if os.path.exists(INDEX):
    rows_js = [("{{t:{t},c:{c},g:{g},e:{e},e0:{e0},h:{h},pl:{pl},pts:{pts},gd:{gd},fm:{fm},fp:{fp},fgd:{fgd},mt:{mt:.4f},"
                "wg:{wg:.3f},ko:{ko:.3f},qf:{qf:.3f},sf:{sf:.3f},fn:{fn:.3f},ti:{ti:.4f}}}").format(
                t=json.dumps(t["team"], ensure_ascii=False), c=json.dumps(t["confederation"]),
                g=json.dumps(t["group"]), e=int(t["elo"]), e0=int(t["elo_pre"]), h=1 if t["host"] else 0,
                pl=t["pl"], pts=t["pts"], gd=t["gd"], fm=json.dumps(t["form"]), fp=t["form_pts"], fgd=t["form_gd"],
                mt=t["mkt_title"], wg=t["p_win_group"], ko=t["p_knockout"],
                qf=t["p_quarter"], sf=t["p_semi"], fn=t["p_final"], ti=t["p_title"]) for t in power]
    const = ("const WC2026={{sims:{s},he:{he},gb:{gb:.3f},gg:{gg:.3f},mb:{mb},asOf:{a},played:{p},total:{tot},playedAll:{pa},totalAll:{ta},"
             "conf:{{data:{cd},C:{C},R:{Rr},S:{Sr},fs:{fs}}},teams:[\n{rows}\n]}};".format(
        s=N, he=int(HOST_BUMP), gb=GOAL_BASE, gg=GOAL_GAMMA, mb=1 if MARKET_BLEND else 0,
        a=json.dumps(AS_OF), p=len(played_g), tot=len(grp_matches),
        pa=TOTAL_PLAYED, ta=TOTAL_MATCHES, cd=CONF["data"], C=CONF["C"], Rr=CONF["R"], Sr=CONF["S"], fs=CONF["fs"],
        rows=",\n".join(rows_js)))
    html = open(INDEX, encoding="utf-8").read()
    html2, nrep = re.subn(r"const WC2026=\{sims:.*?\n\]\};", const, html, count=1, flags=re.DOTALL)
    if nrep == 1:
        open(INDEX, "w", encoding="utf-8").write(html2)
        print(f"✓ {INDEX}  (embedded forecast refreshed)")

# ----------------------------------------------------------------------------- console summary
print(f"\n✓ {csv_path}  ({n_rows} rows)")
print(f"✓ {os.path.join(OUT,'coverage_report.md')}")
print(f"✓ {os.path.join(OUT,'wc2026_power.json')}  (LIVE · {N} sims · as of {AS_OF} · "
      f"{len(played_g)}/{len(grp_matches)} group games played)\n")
print(f"sanity — avg qualifiers per sim: {avg_q:.1f}  (must be 32.0 = top-2 ×12 + 8 best thirds)\n")
print("Top-12 title odds (LIVE Elo Monte-Carlo):")
for t in power[:12]:
    print(f"  {t['team']:<16} P{t['pl']} {t['pts']}pts  title {t['p_title']*100:5.1f}%  reach KO {t['p_knockout']*100:4.0f}%")
for t in power:
    if t["team"] == "Turkey":
        print(f"\n  Turkey live: P{t['pl']} {t['pts']}pts GD{t['gd']:+d}  ->  reach KO {t['p_knockout']*100:.0f}%, "
              f"win group {t['p_win_group']*100:.0f}%  (was 61% pre-tournament)")
print(f"\nDid-not-qualify (flagged in CSV): {did_not_qualify}")
print(f"Missing from brief but qualified: {qualified_not_listed}")

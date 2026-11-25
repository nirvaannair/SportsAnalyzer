# SportsAnalyzer

A personal, locally run football analytics and betting system. It pulls in data from several free sports-data APIs and from scraped injury news, reconciles all of it into one consistent model of teams, players and matches, runs statistical and machine-learning models to estimate match probabilities, compares those to bookmaker odds to find value, and places and tracks bets on Stake. Staking strategies such as fractional Kelly and automatic compounding are configurable. A clean, minimal dashboard shows the whole thing.

> **For a new chat / new developer:** start with **Project handover** below. It is kept up to date after every piece of work and says what the owner wants, how everything works, what is done, what is not, and the rules that must not be broken. The numbered sections after it are the original design brief.

---

## Project handover (last updated 2026-11-25, evening)

### What the owner wants (condensed)
- A **local** football analysis + betting system for **themselves**: the top-5 European leagues **and their second tiers** (ENG1/2, ESP1/2, ITA1/2, GER1/2, FRA1/2). Markets: **1X2, Over/Under 2.5, BTTS**.
- Data from **free API plans only** (slow multi-day collection is fine), and **scraping done by an in-app open-source tool (Scrapy)** whose activity is visible on the dashboard. Not ad-hoc scraping by the assistant.
- **Player-level analysis:** how teams play with and without each player; how players do against the kind of opponent they face next; **3D team style maps**.
- **"Crazy" ML** that **must never base predictions on bookmaker odds** (odds are only the price/payout). See §5.0. This is the owner's most important rule.
- Bets placed on **Stake** (INR wallet, ₹500 deposited) through automation, tested with **₹1 bets**. **End goal: fully automatic betting** with **compounding**. On the Overview page the owner sets **which strategies run, the % of winnings reinvested**, and each strategy's mode **paper / approve / auto**.
- **Real, trained machine-learning models** (not just statistical baselines), trained on **all** collected data **including the scraped player data**, with **visible training progress** on the dashboard. Separate models per league are fine, but **teams from different leagues meet** (European cups, domestic cups, promotion/relegation), so strength must be comparable **across leagues**. Use the laptop's **GPU (NVIDIA RTX 4050 Laptop, 6 GB, CUDA driver 610)** for training.
- **Individual player information** in the app: player pages with minutes, stats, impact with/without, form.
- **Player and squad models:** how much each player adds; **which lineup from the current squad plays best** (squad
  coordination); and **transfer what-ifs**: "if this player joins, how much do the team's win chances rise?".
- **One model family across leagues:** per-league models are fine, but **teams from different leagues meet**, so the
  models must share one cross-league strength scale (European and domestic cups, promotion and relegation).

**Betting requirements (added 2026-11-25):**
- The system **doesn't bet on every prediction.** It selects bets, and may include **low- and mid-probability
  outcomes** when Stake's price makes them good value, not only favourites. Each strategy has a confidence band
  (min/max model probability). This needs **Stake's live odds** (captured by the helper).
- **Multi bets (accumulators):** combine several selections into one Stake multi, where all legs must win for the
  combined payout.
- **Estimated total payout** of all bets currently in play (and the stake at risk), shown on the dashboard.
- **Large bets need approval even in Auto mode:** above an approval threshold (e.g. ₹1,000, set by the owner) a bet
  waits for the owner's click before it goes to Stake.
- **Cash-out:** show Stake's current cash-out value for open bets, and let the owner cash out from the dashboard.
- A polished, clean, minimal dark dashboard. The owner wants to **see the commands that run** (Terminal tabs) and **check the UI regularly**.
- The owner is new to Claude Code; explain plainly. **Keep this README current** so a fresh chat can continue.

### Hard rules
1. **Models never use odds as inputs** or blend toward the market (§5.0). Enforced by `tests/test_odds_firewall.py`. Prices live in `odds_quotes` / `stake_outcomes` and are read only by `backend/evaluation`, `backend/strategies` and `backend/execution`.
2. **Secrets never go to GitHub** (the repo is public). Keys live in `.env` (git-ignored); only `.env.example` is committed.
3. **The assistant never places real-money bets itself** and never bypasses Cloudflare or other bot protection (no cf_clearance cookies, no browser impersonation). Real bets go out only from the owner's own Stake tab via the Chrome extension, only when the owner has switched Execution on, and only within the caps in `.env`.
4. Default money limits: `STAKE_MAX_BET=1`, `STAKE_TEST_BUDGET=20`, `STAKE_MAX_BETS_PER_DAY=10`, `STAKE_APPROVAL_ABOVE=1000` (₹; bets above it always wait for a click, even in Auto). Cash-outs only happen on the owner's click.
5. Ask before spending the owner's API-Football quota (100 requests/day on the free plan; 2024/25 is the season the plan covers).

### Status
| Area | State | Where |
|---|---|---|
| Docker Postgres 17 on `localhost:5433` | ✅ working | `docker-compose.yml` |
| Results + odds 2015/16 to now, 10 leagues (43.8k matches, 1.24M quotes) | ✅ | `backend/ingestion/fdcuk.py`, CLI `import-fdcuk` |
| Upcoming fixtures (next days) | ✅ | CLI `import-fixtures` |
| Upcoming matches weeks ahead from ESPN's schedule | ✅ | `backend/scraping/loaders.py` |
| API-Football 2024/25 fixtures + team matching (199/200 automatic) | ✅ | `backend/ingestion/api_football_sync.py` |
| Identity resolution (teams matched across providers by shared results) + review page | ✅ | `backend/identity/team_resolver.py` |
| Odds-free models: Elo, Dixon-Coles, blend; weekly walk-forward backtest 2018 to now | ✅ but **not bettable yet** (blend log loss 1.024 vs bookmakers 1.006; simulated ROI −8% to −12%) | `backend/models/`, CLI `backtest`, `predict` |
| Scrapy ESPN spider: lineups, substitution minutes, events, team stats; Scraper page | ✅; **full backfill 2019 to now running (run #7, about 20 h)** | `backend/scraping/` |
| Stake Chrome extension (balance, Learn mode, places approved bets) | ✅; 2 real ₹1 bets placed automatically after approval | `extension/`, Stake page |
| Stake fixtures parsed and linked to our matches | ✅ (21/30 linked on first capture; La Liga waits for the backfill) | `backend/execution/stake_parse.py`, `stake_link.py` |
| Strategies, compounding (reinvest %), paper/approve/auto, Overview controls, Bet ledger | ✅ (3 starter strategies, all off and in paper mode) | `backend/strategies/`, `backend/api/routes_strategies.py`, Overview + Bet ledger pages |
| Automation loop in the API: every 15 min settle + strategy bets; every 6 h fixtures + predictions | ✅ | `backend/automation.py` |
| Betting upgrades: confidence band per strategy, multi strategies (2–6 legs), approval threshold, In-play card (estimated total payout), Your Stake bets with cash-out | ✅ built; **needs three Learn-mode captures** (see Known issues) | `backend/strategies/core.py`, `backend/execution/orders.py`, `routes_stake.py`, extension v0.1.2 |
| **Trained ML models** (GPU gradient boosting + neural net) with training-progress page | ⏳ **next** | |
| Cross-league strength (European cups / domestic cups data) | ⏳ | |
| Player pages + player impact model (with/without), player vs opponent style | ⏳ after the backfill finishes | |
| 3D team style maps | ⏳ | |
| Injury/news spiders | ⏳ | |

### Known issues / gaps
- Models are honest and calibrated but **weaker than the market**; the player layer and injuries are the plan to close the gap. Don't enable auto mode for real money until paper trading shows a calibrated, positive edge.
- Pinnacle closing odds stop partway through 2025/26; market-average closing odds are the comparison from then on.
- API-Football's free plan can't fetch several fixtures per request and has no current season, so per-match player data comes from ESPN via Scrapy.
- ESPN's robots.txt returns 403 to automated tools (Scrapy treats that as "no rules"). Requests stay polite: one per 2 s, cached.
- Stake GraphQL requests carry no `operationName`; names are parsed from the query text. The learned bet mutation is `BetSlipFooter_SportBet`.
- 35 ESPN teams (mostly Spain) stay unmatched until the backfill provides evidence; they show on Identity review.
- **Owner actions pending for the betting upgrades** (extension v0.1.2 must be reloaded at chrome://extensions first), each with Learn mode on: (1) open **My Bets → Sports → Active** (teaches the bet list, giving payouts and cash-out values); (2) place **one multi bet by hand** (teaches the multi-bet request, stored as `BetSlipFooter_SportBet#multi`); (3) **cash out one ₹1 bet by hand** (teaches the cash-out request). The Stake page lists which are learned.
- Multi legs are treated as independent (legs always come from different matches).

### Next steps (in order)
1. Verify the betting upgrades once the three Learn-mode captures exist (bet-list fields, multi request, cash-out request); adjust `parse_sport_bets` and `build_cashout_variables` to Stake's real field names if needed.
2. **ML training system:** a `training_runs` table with live progress (epoch, loss, validation metrics) and a
   **Training** page; GPU via PyTorch CUDA and LightGBM/XGBoost GPU. Gradient-boosted trees + a neural net on
   point-in-time features (ratings, form, schedule, **player availability/impact**); no odds as inputs. Walk-forward
   validation (§5.6). Each trained model is registered so strategies can choose it.
3. **Cross-league strength:** add European competitions and domestic cups to the ESPN spider; **one global model
   with league-level strength offsets** (hierarchical), optionally fine-tuned per league. Not fully separate
   per-league models, because teams from different leagues meet.
4. **Player layer** (when the backfill completes): player pages; regularised adjusted plus-minus (impact per 90,
   attack and defence); lineup-adjusted team strength; **best-XI search** over the current squad; **transfer
   what-if** (add a player's impact rating to the expected XI and re-predict); player vs opponent style; then the
   **3D style maps**.
5. **Injury/news spiders** (Scrapy) feeding availability features.
6. Retrain, backtest, paper-trade; compare with the market; only then consider Auto mode with real money.

### Tools and stack
Python 3.12 (`.venv`), FastAPI + uvicorn, SQLAlchemy 2 (async with asyncpg; psycopg for Scrapy), Alembic, PostgreSQL 17 in Docker, pandas/numpy/scipy/scikit-learn, Scrapy, httpx/aiohttp; React 19 + Vite + TypeScript + Tailwind v4 + TanStack Query + lucide icons; a Chrome MV3 extension; pytest + ruff. GitHub: `nirvaannair/SportsAnalyzer` (work happens on branch `claude/football-betting-ml-analyzer-e7dd8d` and is merged through PRs; `gh` is at `C:\Program Files\GitHub CLI\gh.exe`, not on PATH).

### Day-to-day: what must be running
1. **Docker Desktop** (database container `sportsanalyzer-db`).
2. **API:** `.\.venv\Scripts\uvicorn.exe backend.api.main:app --reload --port 8000`
3. **Dashboard:** `npm --prefix frontend run dev`, then open http://localhost:5173
4. For Stake: Chrome with the **SportsAnalyzer Stake Helper** extension loaded from `extension/` and a logged-in stake.com tab.

### Dashboard pages
Overview (In-play payout card; strategy controls: on/off, paper/approve/auto, reinvest %, settings incl. confidence band and multi legs) · Bet ledger · Matches (model probabilities vs prices) · Stake (helper, balance, switches, learned requests, approvals, Your Stake bets + cash-out, outcomes) · Models (backtest metrics, calibration, simulated bets) · Data sources · Scraper (runs, live log, items) · Identity review. Pages marked P2–P4 in the sidebar are not built yet.

---

## Running it locally (Windows, PowerShell)

One-time setup:

```powershell
copy .env.example .env          # then fill in keys and a POSTGRES_PASSWORD
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
npm --prefix frontend install
```

Every time (one terminal each for the API and the dashboard):

```powershell
docker compose up -d --wait db                                    # Postgres 17 on localhost:5433
.\.venv\Scripts\alembic.exe upgrade head                          # apply database migrations
.\.venv\Scripts\uvicorn.exe backend.api.main:app --reload --port 8000   # API on :8000
npm --prefix frontend run dev                                     # dashboard on http://localhost:5173
```

Data (safe to re-run; unchanged files are skipped):

```powershell
.\.venv\Scripts\python -m backend.cli import-fdcuk                      # results + odds, 2015/16 to now (~25 min first time)
.\.venv\Scripts\python -m backend.cli import-fdcuk --from 2026          # just refresh the current season
.\.venv\Scripts\python -m backend.cli sync-api-football --season 2023   # 10 API-Football requests, then team matching
.\.venv\Scripts\python -m backend.cli import-fixtures                   # upcoming matches (next few days); run daily
.\.venv\Scripts\python -m backend.cli backtest                          # walk-forward test of all models (~5 min)
.\.venv\Scripts\python -m backend.cli predict                           # predict upcoming matches
.\.venv\Scripts\python -m backend.cli resolve-teams                     # re-run team matching
.\.venv\Scripts\python -m backend.cli summary                           # what is in the database
```

Checks:

```powershell
.\.venv\Scripts\python -m pytest -q      # tests (DB tests skip if Postgres is down)
.\.venv\Scripts\ruff.exe check .         # lint
npm --prefix frontend run build          # type-check + build the dashboard
```

| Path | What lives there |
|---|---|
| `backend/api/` | FastAPI app the dashboard calls |
| `backend/cli.py` | Command line for imports and maintenance |
| `backend/core/leagues.py` | The 10 tracked leagues and each provider's league ID |
| `backend/ingestion/` | Importers: football-data.co.uk, API-Football |
| `backend/models/` | Prediction models (Elo, Dixon-Coles, blend) and walk-forward backtest. **Never sees odds** |
| `backend/evaluation/` | Scoring on real results; the only code that reads prices (as payouts) |
| `backend/integrations/` | Provider adapters, rate limiter, raw payload storage |
| `backend/identity/` | Name normalization and team matching across providers |
| `backend/database/`, `alembic/` | SQLAlchemy models and migrations |
| `frontend/` | React + Vite + Tailwind dashboard |
| `tests/` | pytest suite |

### Stake browser helper

Stake's betting API sits behind Cloudflare, which only lets real browsers through, so bets are
placed from **your own logged-in Stake tab** by a small Chrome extension in `extension/`
(install steps in `extension/README.md`). The dashboard's **Stake** page has the switches
(Learn mode, Execution; both off by default) and the approval queue. The app enforces the
limits in `.env` (`STAKE_MAX_BET`, `STAKE_TEST_BUDGET`, `STAKE_MAX_BETS_PER_DAY`) before any
bet is handed to the helper.

### Data notes

- **football-data.co.uk is the seed source.** It defines the canonical teams and matches; every other provider's teams are matched to them (by shared results first, names second). Anything uncertain goes to the dashboard's Identity review page.
- **Closing-odds coverage:** 2015/16–2018/19 have Pinnacle closing odds only; 2019/20–2024/25 have Pinnacle, Bet365 and the market average; **Pinnacle stops partway through 2025/26**. From then on, models are judged against the market-average closing price.

---

## 1. What you asked for, restated

| # | Requirement | How I read it |
|---|---|---|
| 1 | Sports analyzer, football first | The core is football-specific, but provider, identity and betting layers stay sport-agnostic so other sports can be added later. |
| 2 | Data from many API providers, **free plans only** | API-Football, TheSportsDB, football-data.org, and similar. Slow ingestion is fine: the system can spend days backfilling within daily quotas. |
| 3 | Providers use different structures and IDs | Every provider's raw response is stored as-is, then mapped onto one **canonical** set of teams, players, competitions and matches through an identity-resolution layer. |
| 4 | Scrape news for injuries to star and key players | Scheduled scrapers read news and injury pages, extract (player, status, expected return), link the player to the canonical player, and turn it into model features. |
| 5 | "Crazy" ML analysis with whatever maths is best | A layered model stack: team-strength ratings, a goals model, gradient-boosted models on rich features, calibration, and an ensemble. Details in §5. |
| 6 | Bets created and placed on Stake via "the StakeAPI" | An execution layer that turns model output into bet slips and submits them to Stake. **There are big caveats here; see §7.** |
| 7 | Monitor every bet | A full bet ledger: every proposed, placed, settled, void or failed bet, with the model's reasoning, the odds taken, the closing odds and the P&L. |
| 8 | Strategic betting, e.g. auto-compounding | A strategy engine: compounding, fractional Kelly, flat stakes and ladders, with bankroll rules and kill switches. |
| 9 | Nice dashboard, polished, clean, minimal | A local web app (FastAPI backend + React frontend) with a restrained, minimal design. |
| 10 | Runs locally | Everything runs on your machine: Postgres, the backend API, a background worker/scheduler and the frontend. Nothing is hosted. |

---

## 2. What is already in the repo

See **Project handover → Status** at the top; it is kept current.

---

## 3. Target architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Local machine (Windows)                          │
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                  │
│  │ API adapters │   │ News scrapers│   │ Odds sources │  ← scheduler     │
│  │ (free tiers) │   │ (injuries)   │   │ (Stake + API)│    (worker)      │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘                  │
│         ▼                  ▼                  ▼                          │
│  ┌────────────────────────────────────────────────────┐                  │
│  │ 1. RAW layer      raw_provider_observations (done) │                  │
│  ├────────────────────────────────────────────────────┤                  │
│  │ 2. PARSED layer   provider_* tables (per provider) │                  │
│  ├────────────────────────────────────────────────────┤                  │
│  │ 3. IDENTITY       canonical_* + provider mappings  │ ← review queue   │
│  ├────────────────────────────────────────────────────┤                  │
│  │ 4. CANONICAL      matches, teams, players, events, │                  │
│  │                   lineups, injuries, odds history  │                  │
│  └───────────────────────┬────────────────────────────┘                  │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────┐                  │
│  │ 5. FEATURES   point-in-time feature store          │                  │
│  │ 6. MODELS     ratings → goals model → GBM → ensemble│                 │
│  │ 7. PRICING    probabilities → fair odds → value     │                 │
│  └───────────────────────┬────────────────────────────┘                  │
│                          ▼                                               │
│  ┌────────────────────────────────────────────────────┐                  │
│  │ 8. STRATEGY   staking + compounding + risk limits  │                  │
│  │ 9. EXECUTION  paper broker │ Stake broker          │                  │
│  │ 10. LEDGER    bets, settlements, bankroll history  │                  │
│  └───────────────────────┬────────────────────────────┘                  │
│                          ▼                                               │
│     FastAPI (REST + WebSocket) ───────► React dashboard (localhost)      │
│     PostgreSQL                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Proposed stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Already in use; best ML ecosystem. |
| DB | PostgreSQL (already set up) + Alembic | JSONB for raw payloads, solid for time series of odds. |
| Backend API | FastAPI | Async, matches the existing async SQLAlchemy code. |
| Scheduler / worker | APScheduler in a separate worker process, jobs persisted in Postgres | No Redis needed; runs ingestion, scraping, model runs and bet settlement. |
| HTTP | `httpx` (async) | Already a natural fit for the adapters. |
| Scraping | `httpx` + `selectolax`/BeautifulSoup; Playwright only where JS rendering is needed | Lightweight first, a headless browser only as a fallback. |
| ML | `numpy`, `scipy`, `pandas`/`polars`, `scikit-learn`, `LightGBM`, `statsmodels`, optionally `PyMC` | See §5. |
| Experiment tracking | MLflow (local file store) | Compare model versions and keep artifacts. |
| Frontend | React + Vite + TypeScript, Tailwind, shadcn/ui, Recharts/visx, TanStack Query | Clean, minimal, fast to build and polish. |
| Packaging | `pyproject.toml` + a standard `.venv`; Postgres in Docker Compose | Easy local setup on Windows. |

---

## 4. Data ingestion

### 4.1 Free data sources (planned)

Free-tier limits change often. Each adapter reads the real limits from response headers or config instead of hard-coding them.

| Source | Type | Used for | Notes |
|---|---|---|---|
| **API-Football** (api-sports.io) | API, free key | Fixtures, results, lineups, events, player stats, injuries, some odds | Adapter already built. The free plan has a small daily request cap and restricted seasons, so backfill is slow but steady. |
| **football-data.org** | API, free key | Fixtures, results, standings, squads for top competitions | Per-minute limit and a limited competition list on the free tier. |
| **TheSportsDB** | API, free/test key | Team and player metadata, badges, venues, some events | Good for metadata and images; thinner on stats. |
| **football-data.co.uk** | Free CSV downloads | **Decades of results with bookmaker closing odds** | The most valuable source for ML: it gives the historical market prices needed for backtesting. No key needed. |
| **OpenLigaDB** | Free API | German leagues | No key needed. |
| **The Odds API** | API, free credits | Current odds from many bookmakers | Small monthly credit allowance, so use it sparingly. |
| **Understat / similar xG sites** | Scrape | Shot-level xG for the top leagues | Only within each site's terms and robots.txt, cached heavily. |
| **Stake** | Unofficial GraphQL | The odds you actually bet at; your balance and bet history | See §7. |

### 4.2 Ingestion principles

1. **Raw first, always.** Every response goes into `raw_provider_observations` (already built). Parsing can be re-run at any time without spending quota again.
2. **A quota-aware planner.** A job queue ranks work by value (upcoming fixtures > recent results > deep history) and spends each provider's daily budget across it. Backfilling full history over days or weeks is expected and fine.
3. **Incremental sync.** Separate cadences for upcoming fixtures, live and just-finished matches, odds snapshots, news and deep history (the `*_INTERVAL_SECONDS` settings already exist).
4. **Point-in-time correctness.** Every record keeps `received_at`, so models only ever train on what was knowable *before* kickoff. Without this, backtests are worthless.

### 4.3 Identity resolution (different IDs per provider)

This is the part that makes multi-provider work possible. The domain model is already in `backend/identity/`; what's left is persistence and a resolver.

- **Tables:** `canonical_teams`, `canonical_players`, `canonical_competitions`, `canonical_seasons`, `canonical_matches`, `provider_entity_mappings` (provider, entity type, provider ID → canonical ID, status, method, confidence, evidence) and `identity_conflicts`.
- **Resolution cascade** (the order follows the existing `ResolutionMethod` enum):
  1. Exact external identifiers, and cross-references a provider exposes (for example a provider that also lists another provider's ID).
  2. Deterministic rules (same competition + season + normalized name).
  3. Name and context: a team matches on normalized name + country + competition; a player on name + date of birth + nationality + current team; a match on date ± 1 day + both resolved teams.
  4. Fuzzy and composite scoring (token-set similarity, Jaro-Winkler, transliteration-aware normalization, alias lists such as "Man Utd" / "Manchester United FC").
  5. Anything below the confidence threshold (0.95 by default) goes to a **review queue in the dashboard**, where you approve, reject or merge with one click. That becomes a `MANUAL_OVERRIDE`, and the system learns the alias.
- **Matches anchor everything.** Once two providers' fixtures resolve to the same canonical match, their team and player IDs from that match become strong evidence for each other.

### 4.4 Injury and news scraping

- **Sources:** injury tables and team-news pages from major outlets, club official sites, league injury reports, and Reddit's API for fast-moving team news. Every scraper respects robots.txt and site terms, identifies itself honestly, caches aggressively and runs at low frequency.
- **Pipeline:**
  1. Fetch → store raw HTML/JSON in the raw layer (same table, `payload_format = html`).
  2. Extract article text and publish time.
  3. **Entity linking:** find player and team names and resolve them through the identity layer.
  4. **Status classification:** `out`, `doubtful`, `returning`, `suspended`, `fit`, plus an expected-return date and injury type. Start with rules and keyword patterns, then upgrade to a small fine-tuned classifier (or, optionally, an LLM call per article for higher accuracy).
  5. Combine with structured injury data from API-Football and de-duplicate across sources, weighting each source by its reliability.
- **"Star or key player" is computed, not hand-labelled.** Player importance comes from minutes share, xG/xA contribution, rating, and the team's results with versus without the player. A missing striker who scores 40% of the team's goals moves the model far more than a missing backup full-back.

---

## 5. The ML and maths stack

"Crazy" here means *rigorous and layered*, not just big. Football outcomes are low-scoring and noisy, so the models combine solid statistical structure with careful player-level feature engineering.

### 5.0 The core rule: the model never learns from bookmaker odds

Odds are shaped by bookmaker margins and by where the public puts its money (popular clubs, favourites, recent headlines). So **SportsAnalyzer forms its own opinion from football data only**:

| Odds are **never** used for | Odds **are** used for |
|---|---|
| Model inputs (no odds, odds movement or implied probabilities as features) | The **price** of a bet: after the model has fixed its probability, the price decides whether the payout is worth it |
| Blending or "shrinking" the model towards the market | **Stake size** (Kelly needs the payout) |
| Deciding which matches look interesting | Reporting, e.g. a "market disagrees" diagnostic shown on the dashboard, never fed back into decisions |

Why the price still matters: if the model gives a team a 50% chance, odds of 2.50 pay more than that risk is worth (a good bet) and odds of 1.60 pay less (a bad bet), even though the prediction is identical. Ignoring the price entirely would mean taking bad prices and losing to the bookmaker's margin.

This is enforced in code: a test fails if any odds-derived column reaches a model's feature set. Without the market as a safety net, the model has to be well calibrated on its own, so bets also need a minimum edge **and** low model uncertainty (§5.5).

### 5.1 Layer 1: team-strength ratings
- **Elo / pi-ratings** with home advantage and margin of victory, updated match by match.
- **Dynamic attack and defence strengths**: a time-decayed Dixon-Coles style model, refitted regularly.
- **xG-based ratings** where xG data exists (more stable than goals); shots and shots-on-target ratings for the second tiers, where xG is not available.

### 5.2 Layer 2: goals model (the core probabilistic engine)
- **Dixon-Coles (bivariate Poisson with low-score correction)** with exponential time decay. It produces a full score-line probability matrix, from which all markets follow: 1X2, over/under, BTTS, correct score.
- A **Bayesian hierarchical version** (PyMC) for proper uncertainty, which helps a lot for promoted teams and second tiers, and feeds the "low uncertainty" requirement for betting.

### 5.3 Layer 3: the player layer
How a team plays **with and without** each player, and how players perform against the kind of opponent they face next.

**Data (free, collected over days within quotas):**
- **Understat** (top-5 first divisions, 2014/15 on): per-match lineups, minutes, xG, xA, shots and key passes for every player. Scraped slowly, cached, within the site's terms.
- **API-Football** (all 10 leagues): lineups, substitutions, per-player match stats and ratings, injuries and suspensions. One request per fixture, so a quota-aware queue backfills about 90 fixtures a day; a full league-season takes about 4 days. The free plan's season limits apply.
- Injury and team news from the Phase 2 scrapers.

**Models:**
- **Player impact (with/without):** each match is split into segments between substitutions and red cards. A regularised regression (ridge / Bayesian *adjusted plus-minus*) learns each player's effect on the team's xG for and against per 90 minutes, controlling for teammates and opponents. Priors come from position and previous seasons, so new or rarely used players don't produce wild numbers.
- **Lineup-adjusted strength:** a team's rating for a match is built from its **expected XI**. When a key player is injured, the team's attack or defence rating drops by that player's measured impact, not by a guess.
- **Player vs opponent:** a player meets a specific club only about twice a season, which is far too little data to trust. So performance is modelled against **opponent style types** (below), shrunk towards the player's overall level: "how does this striker do against deep, low-block defences?"

### 5.4 Layer 4: 3D team style maps
- Every team-season, and a rolling recent-form window, becomes a **style vector**: tempo, shot volume and quality, xG for and against, set-piece share, directness, defensive line and pressing proxies, home/away splits.
- These are reduced to **3 dimensions** (PCA, then UMAP) and clustered into **style types**.
- The dashboard shows an interactive **3D map**: one point per team, trails showing how a team's style moved across seasons, colour by cluster, click a team for its page.
- The clusters are also model inputs: team-vs-style results and player-vs-style performance (Layer 3).

### 5.5 Layer 5: gradient boosting, calibration and the betting decision
- **LightGBM** on point-in-time features: layer 1–4 outputs, form, availability (lineup-adjusted strength, missing-player impact), schedule (rest days, congestion, travel, European midweek games) and context (table position, motivation, derby, manager change). **No odds.**
- **Calibrate** with isotonic regression on out-of-sample predictions. Value betting needs calibrated probabilities, not just accuracy.
- **Bet only when** `edge = p_model × price − 1` exceeds a threshold **and** the Bayesian uncertainty interval for p_model also clears it. The price is Stake's at the moment of betting.

### 5.6 Validation (the part that decides whether any of this is real)
- **Walk-forward backtesting** by season and matchweek, using only information available before kickoff.
- **Primary metrics, judged on real results:** log loss, Brier score, ranked probability score, calibration curves, and **ROI at the prices actually available**.
- **Secondary diagnostic:** closing line value (whether our price beat the closing price). It is reported, but it is not the yardstick the model is tuned on.
- A model is **promoted to live betting** only after positive, well-calibrated paper-trading results over a meaningful sample.

> Honest expectation: beating bookmakers is hard, and a model that ignores the market must be well calibrated on its own. Edges, if they exist, tend to sit in **second tiers, team news not yet priced in (injuries, lineups), and totals/BTTS**. The system is built to find out where you have an edge, and to show you clearly when you don't.

---

## 6. Strategy engine and compounding

Strategies are configurable objects in the dashboard. Each one owns a bankroll and has its own rules.

| Strategy | Behaviour |
|---|---|
| **Flat** | A fixed stake or fixed % of bankroll per bet. |
| **Fractional Kelly** | Stake = f × Kelly(p, odds), with f usually 0.1–0.33. Kelly on overconfident probabilities ruins bankrolls, so it is always fractional and capped. |
| **Auto-compounding (bankroll %)** | Each new stake is a % of the *current* strategy bankroll, so wins grow future stakes automatically and losses shrink them. |
| **Compounding ladder (rollover)** | The return of bet *n* becomes the stake of bet *n+1*, for up to *k* steps, then the profit is banked and the ladder restarts. This is your "winnings of one bet go to the next" mechanism. |
| **Accumulator builder** | Combine independent value selections (no correlated legs from the same match unless modelled). |

**Risk controls on every strategy (required, not optional):**
- Max stake per bet, per day and per match; minimum edge; minimum and maximum odds.
- A **max-drawdown kill switch**: the strategy pauses itself after an X% drop from its peak.
- A daily loss limit and a cooldown after a losing streak.
- **Profit lock:** bank a % of profits out of the compounding pot.
- A global kill switch in the dashboard header that stops all execution immediately.
- **Execution modes per strategy:** `paper` (simulated, the default) → `approve` (each bet waits for one click from you) → `auto` (fully automatic).

The ladder's risk grows exponentially: a 5-step ladder at odds of 2.0 needs five wins in a row, and its stakes double every step. The dashboard shows the probability of completing the ladder and the expected value before you enable it.

---

### 6.1 Controls on the Overview page (agreed 2026-11-25)

- **Active strategies:** pick which strategies run (flat, fractional Kelly, compounding %, ladder…), each with its own bankroll.
- **Reinvest % of winnings:** of every winning bet's profit, X% goes back into the compounding pot and the rest is banked (locked profit). 0% = flat staking, 100% = full compounding.
- **Mode per strategy:** `paper` → `approve` (you click each bet) → `auto` (bets go straight to Stake through the helper, no click).
- **Auto mode is still bounded** by per-bet cap, daily cap, bankroll %, drawdown kill switch and the global Execution switch. It is switched on by you, after paper trading shows calibrated, profitable results.

## 7. Stake integration: important findings

I read the `StakeAPI` package in your main checkout (`chipadevteam/StakeAPI`). Here is what it actually does:

1. **It is unofficial.** Stake does not publish a public betting API. The package works by replaying the browser's own GraphQL calls (`/_api/graphql`) with an `x-access-token` copied from DevTools.
2. **Only the balance query is real.** `get_user_balance()` sends a real GraphQL query (`UserBalances`). Everything else, including `place_bet()`, `get_sports_events()` and `get_bet_history()`, calls REST paths like `/api/v1/bets/place` that look invented and that Stake almost certainly doesn't serve. **As it stands, the package cannot place a sports bet.**
3. **Placing sports bets would mean reverse-engineering Stake's own sportsbook GraphQL operations** (fetching fixtures and markets, then the bet mutation) from the browser's network traffic, and keeping up when Stake changes them. It is doable but fragile. It also sits behind Cloudflare, so requests need the right headers and sometimes break.
4. **Account risk.** Automated betting with a scraped session token very likely breaks Stake's terms of service. Stake can restrict or close accounts and hold balances, and it limits accounts that win consistently. Stake.com is also not legally available in many countries. **You need to confirm that you can legally use Stake where you live and that you accept this account risk.**

### 7.1 What the StakeAPI docs add (checked 2026-11-25)

I read the documentation you pointed to (the hosted site at chipadevteam.github.io/StakeAPI and the full `docs/` folder in the repo):

- **Placing a bet:** the betting guide only shows `client.place_bet({"game_id": ..., "amount": ..., "currency": "btc", "bet_type": "single"})`. That calls the same invented REST path (`/api/v1/bets/place`) and uses a casino-style payload. **There is no sportsbook bet mutation anywhere in the docs or the code.**
- **Sports data:** a `SportsEvents` GraphQL query (`sportsEvents(first, sportSlug) → markets → outcomes { name odds }`) exists in `endpoints.py`. Its shape looks guessed rather than captured from real traffic; it needs to be checked against a live response.
- **Bet history:** a `BetHistory` query on `user.bets` exists. It selects `game { name slug }`, which suggests casino bets, so sportsbook bets may need different fields.
- **Rate limits:** the docs only cover the client's own throttling (`rate_limit=…`) and a `RateLimitError`. Stake's real limits are not documented.
- The docs actively promote betting bots. They say nothing about Stake's terms of service, so the account risk above still applies.

**Conclusion:** the docs don't change the plan. The working pieces are the token-based GraphQL transport and the balance query. Fixtures, odds and bet placement have to come from **real requests captured from your browser.**

**What you will do once (before Phase 6):** on stake.com, open DevTools → Network, filter for `graphql`, then:
1. open a football match page (captures the fixture/markets/odds query),
2. add a selection to the bet slip and place one minimum-stake INR bet (captures the bet mutation and its variables: outcome IDs, amount, currency, odds-change setting),
3. open My Bets → sports (captures the sports bet history query).

Then save each request body (**not** the headers or token) into `backend/execution/stake/operations/*.graphql`. I'll build `StakeBroker` on those exact operations and verify them read-only first.

**How I plan to build it so the rest of the system doesn't depend on it:**
- An abstract `Broker` interface with `get_balance`, `get_markets`, `quote`, `place_bet`, `get_open_bets` and `get_settled_bets`.
- `PaperBroker`: a full simulation using real odds snapshots. It is the default and is used for all validation.
- `StakeBroker`: my own small GraphQL client (I won't build on the package's invented REST endpoints), with read-only operations first (balance, markets/odds, bet history), and bet placement added only after it is verified manually against your account, in small stakes, in `approve` mode.
- **Idempotency:** each bet has a client-side key, so a retry can never place it twice. The ledger is reconciled against Stake's bet history.
- **Odds-change guard:** re-quote right before placing and reject the bet if the price dropped below the edge threshold.
- **Token handling:** the token is stored only in the local `.env` (git-ignored), never logged, and the dashboard shows when it has expired and needs replacing.

---

## 8. Dashboard

Minimal and calm: a neutral palette, one accent colour, generous whitespace, a dense data table only where it earns its place, light and dark modes.

| Page | Contents |
|---|---|
| **Overview** | Bankroll curve, today's P&L, open exposure, ROI/yield/CLV tiles, active strategies, global kill switch. |
| **Fixtures** | Upcoming matches in the 10 phase-1 leagues with model probabilities vs market, fair odds, edge, injury flags, and drill-down into the score matrix and feature contributions. |
| **Value bets** | The current opportunities ranked by edge × confidence, with approve/reject for `approve`-mode strategies. |
| **Bet ledger** | Every bet: status, stake, odds taken vs closing odds, P&L, strategy, model version and a "why" panel. Filterable and exportable. |
| **Strategies** | Create and edit strategies (type, bankroll, limits, mode), with a compounding simulator (Monte Carlo of bankroll paths) before enabling. |
| **Models** | Backtest results, calibration plots, log loss and ROI over time (CLV as a side diagnostic), model version comparison, promote/demote. |
| **Team news** | The injury and suspension feed with source, confidence and estimated impact on the next match. |
| **Data sources** | Provider health, quota used/remaining today, backfill progress, last sync, errors. |
| **Identity review** | Unresolved and conflicting provider-to-canonical mappings, with approve/merge/reject. |
| **Settings** | API keys (masked), Stake token status, schedules, thresholds. |

Live updates (new odds, bet placed, bet settled) arrive over a WebSocket.

---

## 9. Build roadmap

| Phase | Deliverable |
|---|---|
| **0. Foundations** | `pyproject.toml` + `.venv`, pytest suite, remove the broken `StakeAPI` gitlink (our own `StakeBroker` replaces it), `.env.example`, `docker-compose.yml` for Postgres, lint/test scripts. |
| **1. Data** | Parsed and canonical tables; identity resolver + review queue; adapters for football-data.org, TheSportsDB and the football-data.co.uk CSV importer; quota-aware backfill planner. |
| **2. News** | Injury scrapers, entity linking, status classification, player-importance metric. |
| **3. Models** | Feature store; Elo + Dixon-Coles; LightGBM; calibration; walk-forward backtester with historical odds; MLflow. |
| **4. Strategy + paper trading** | Strategy engine, risk controls, `PaperBroker`, ledger, settlement job. |
| **5. Dashboard** | FastAPI endpoints + React UI for every page in §8. |
| **6. Stake** | Read-only `StakeBroker` → `approve`-mode placement → `auto` mode only after positive, well-calibrated paper-trading results. |

---

## 10. Decisions (agreed 2026-11-25)

| Topic | Decision |
|---|---|
| Bookmaker | **Stake**, using your **INR wallet**. All amounts, limits and P&L are stored and shown in INR. |
| Leagues (phase 1) | **Top 5 + second tiers:** Premier League, Championship, La Liga, Segunda División, Serie A, Serie B, Bundesliga, 2. Bundesliga, Ligue 1, Ligue 2. |
| Markets | **1X2, Over/Under goals, BTTS.** All three are derived from the Dixon-Coles score matrix, plus the GBM layer. Asian handicap is out of scope for now. |
| Automation | **Paper → approve → auto.** Each strategy starts in paper mode. Approve mode unlocks once the Stake broker is verified. Auto mode unlocks only after positive, well-calibrated paper-trading results over a minimum sample. **Models never use bookmaker odds as inputs** (§5.0). |
| Default risk limits | **Conservative:** max 2% of strategy bankroll per bet, 0.25× Kelly, auto-pause at 20% drawdown from peak. Each strategy can override these in the dashboard. Hard caps stay in config. |
| Frontend | **React + Vite + TypeScript + Tailwind**, shadcn/ui, Recharts, TanStack Query. |
| Database | **PostgreSQL via Docker Compose** (`docker compose up -d db`), migrated with Alembic. |

### Still needed from you

1. **API keys in `.env`** (never in chat): API-Football (you have it), football-data.org (free sign-up), and The Odds API (optional). TheSportsDB's free test key is used unless you have your own.
2. **Captured Stake sportsbook requests** before Phase 6 (see §7.1). Not needed until then.

---

## 11. Disclaimer

This is a personal research tool. Sports betting carries a real risk of loss, and no model guarantees profit. Use only money you can afford to lose, follow the laws where you live, and set the bankroll limits above before enabling any automatic execution.

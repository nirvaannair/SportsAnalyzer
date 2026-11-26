# SportsAnalyzer

A personal, locally run football analytics and betting system. It pulls in data from several free sports-data APIs and from scraped injury news, reconciles all of it into one consistent model of teams, players and matches, runs statistical and machine-learning models to estimate match probabilities, compares those to bookmaker odds to find value, and places and tracks bets on Stake. Staking strategies such as fractional Kelly and automatic compounding are configurable. A clean, minimal dashboard shows the whole thing.

> **For a new chat / new developer:** start with **Project handover** below. It is kept up to date after every piece of work and says what the owner wants, how everything works, what is done, what is not, and the rules that must not be broken. The numbered sections after it are the original design brief.

---

## Easy guide: turning SportsAnalyzer on and off

**One click (after the one-time setup below):** double-click **SportsAnalyzer** on your desktop
(or `Start SportsAnalyzer.cmd` in this folder). It:
1. starts **Docker Desktop** if it isn't running (Docker runs the database);
2. starts the **database** and applies any database updates;
3. starts the **API server** in a minimised window called *SportsAnalyzer API*;
4. starts the **dashboard** in a minimised window called *SportsAnalyzer dashboard*;
5. opens **http://localhost:5173** in your browser.
Anything already running is left alone, so it is safe to click twice. To stop: **Stop SportsAnalyzer** on the
desktop (or `Stop SportsAnalyzer.cmd`). The database keeps running in Docker; that's fine.

**What each piece is**
| Piece | What it does | If it's off |
|---|---|---|
| Docker Desktop + database | Stores every match, player, prediction and bet | Everything shows "Database offline" |
| **API server** (port 8000) | The engine behind the dashboard. It answers the dashboard's questions and runs the background jobs: settling bets and running strategies every 15 min, re-predicting matches every 6 h, the free-API collector, the always-on scraper, and training runs | The dashboard shows "API offline" and nothing updates |
| Dashboard (port 5173) | The website you look at | The page doesn't load |
| Chrome + Stake Helper extension + logged-in stake.com tab | Reads your Stake balance/bets and places approved bets | "Stake helper offline"; no bets can be placed (everything else works) |

**One-time setup on a new computer** (already done on this laptop): install Docker Desktop, Python 3.12 and Node.js;
then in this folder: `copy .env.example .env` (fill in keys), `python -m venv .venv`,
`.venv\Scripts\python -m pip install -e ".[dev]" xgboost`,
`.venv\Scripts\python -m pip install torch==2.15.0+cu132 --index-url https://download.pytorch.org/whl/cu132`,
`npm --prefix frontend install`, and once: `powershell -ExecutionPolicy Bypass -File scripts\create-desktop-shortcut.ps1`.

**Updating to the newest version:** after a pull request is merged on GitHub, open PowerShell in this folder and run
`git pull`, then click Stop and Start.

---

## Project handover (last updated 2026-11-26)

### What the owner wants (condensed)
- A **local** football analysis + betting system for **themselves**: the top-5 European leagues **and their second tiers** (ENG1/2, ESP1/2, ITA1/2, GER1/2, FRA1/2). Markets: **1X2, Over/Under 2.5, BTTS**.
- Data from **free API plans only** (slow multi-day collection is fine), and **scraping done by an in-app open-source tool (Scrapy)** whose activity is visible on the dashboard. Not ad-hoc scraping by the assistant.
- **Import much more from the free API providers**, through a background collector the owner **switches on and off on
  the website**, per provider, always inside each free plan's limits (2026-11-26).
- **Advanced models, with different models per league considered** (2026-11-26): every model family has a global
  version and per-league versions, and the better one is used per league.
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
0. **No hard-coded values (owner's rule, 2026-11-26).** Every tunable number, date, threshold, budget, interval,
   season list, league/provider ID, URL and word list lives in **`config/settings.toml`** (commented), read through
   `backend/core/settings.py` (`cfg("section.key")`) and, in the dashboard, `frontend/src/lib/settings.ts`
   (`setting('section.key')`). Values that can be worked out from the data are derived (e.g. the default backtest start
   season, season choices on the Training page, the comparison model). The **Settings** page edits any value; edits go to
   `config/settings.local.json` (git-ignored) and override the defaults. `tests/test_settings.py` fails if a setting used
   in code is missing, or if a numeric constant or fixed date appears in backend code. Stays out of settings on purpose:
   secrets and money caps (`.env`), names (columns, features, statuses, the three markets) and maths constants.
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
| Scrapy ESPN spider: lineups, substitution minutes, events, team stats; Scraper page | ✅; backfill run #7 died part-way (8.7k items); **restarted 2026-11-26 as run #9** (resumes; pages cached) | `backend/scraping/` |
| Stake Chrome extension (balance, Learn mode, places approved bets) | ✅; 2 real ₹1 bets placed automatically after approval | `extension/`, Stake page |
| Stake fixtures parsed and linked to our matches | ✅ (21/30 linked on first capture; La Liga waits for the backfill) | `backend/execution/stake_parse.py`, `stake_link.py` |
| Strategies, compounding (reinvest %), paper/approve/auto, Overview controls, Bet ledger | ✅ (3 starter strategies, all off and in paper mode) | `backend/strategies/`, `backend/api/routes_strategies.py`, Overview + Bet ledger pages |
| Automation loop in the API: every 15 min settle + strategy bets; every 6 h fixtures + predictions | ✅ | `backend/automation.py` |
| Betting upgrades: confidence band per strategy, multi strategies (2–6 legs), approval threshold, In-play card (estimated total payout), Your Stake bets with cash-out | ✅ built; **needs three Learn-mode captures** (learned and verified: 4 own bets, ₹254.98 potential payout shown) | `backend/strategies/core.py`, `backend/execution/orders.py`, `routes_stake.py`, extension v0.1.2 |
| **Trained ML models**: XGBoost (CUDA) + residual neural net (PyTorch CUDA), each global + per-league fine-tuned + "auto" (best per league) + ensemble; Training page with live loss curves | ✅ (see "ML models" below) | `backend/models/features.py`, `backend/models/ml.py`, `backend/training.py`, Training page |
| **Free-plan API collector**: on/off switch per provider, daily budgets, quota meters, persistent queue | ✅ running: API-Football (injuries, then xG + player stats per match, 90 requests/day), OpenLigaDB, TheSportsDB, football-data.org (key added 2026-11-26) | `backend/collector/`, Data sources page |
| Cross-league strength (European cups / domestic cups data) | ⏳ partly: ratings carry across divisions; Champions League matches now collected from football-data.org | |
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
- **Learned Stake requests** (from the owner's tab, Learn mode): single bet `BetSlipFooter_SportBet`; multi `BetSlipFooter_SportBet#multi` (same mutation, several `outcomeIds`, empty `identifier` kept); own open bets `FetchActiveSportBets` (`user.activeSportBets[]` with `potentialMultiplier`, `cashoutMultiplier`, `cashoutDisabled`; re-run by the helper every minute with limit 50); cash-out `SportBetPreview_CashoutSportBet(betId, multiplier, cashoutPercent)`. **Cash-out values are computed by Stake in the browser** from streamed odds (no server endpoint; `cashoutMultiplier` in the bet list is a ceiling, not the live value). The dashboard shows availability exactly (all unsettled legs' markets active) and an *estimate* (`cashout_view`, ≈ potential ÷ Π current odds × 0.9617 per leg, calibrated on the owner's screen). **Dashboard cash-outs never send a computed multiplier**: on the owner's click the helper (extension v0.1.3) opens the bet's page in the owner's Stake tab (`?iid=sport:…&modal=bet`), presses **Stake's own Cashout button** (and Stake's confirm button if shown), and reports Stake's `cashoutSportBet` answer with the exact payout. If the button is missing or disabled it stops and reports why. This depends on Stake's page layout; if Stake redesigns it, update `runCashout` in `extension/content.js`. **Never use `BetsBoard_HighrollerSportBetsBase`**: it is the public board of *other people's* bets. `parse_sport_bets` only accepts bets under `user { }`.
- Multi legs are treated as independent (legs always come from different matches).
- **Fixed 2026-11-25 (night):** the learned "place bet" request had been picked up as the cash-out mutation (its name contains "Bet"); `is_bet_mutation` now excludes cash-out requests, so real bets use `BetSlipFooter_SportBet`. Bets that leave Stake's active list (settled or cashed out) are now marked `closed` on the next helper refresh, but only when the response really is the owner's `user.activeSportBets` list and holds fewer than 50 bets. We don't yet record whether a closed real bet won or lost; that needs Stake's settled-bets list (learn it from My Bets → Settled).
- **Owner's instruction (2026-11-25): cash-out is parked.** Don't work on it further unless asked. The main page no longer shows cash-out figures.

### ML models (built 2026-11-26)
- **Features** (`backend/models/features.py`, all point-in-time, tested): Elo; form over the last 5/10 matches (goals,
  shots, shots on target, corners, points) and exponentially weighted; venue form; rest days; matches played;
  **opponent-adjusted attack/defence ratings** on goals and on shots on target (online, carried across divisions so
  promoted/relegated teams stay on one scale); finishing rate; head-to-head; league, tier, month, season progress.
  No odds: `assert_features_odds_free`, and `tests/test_odds_firewall.py` scans the code.
- **Families** (`backend/models/ml.py`): XGBoost (5 boosters: 1X2, O/U 2.5, BTTS, home goals, away goals; CUDA) and a
  residual MLP with a head per market (Poisson goal rates; CUDA).
- **Per league:** each family trains a *global* model on all leagues, then fine-tunes a copy per league (XGBoost: extra
  trees at a lower learning rate; NN: extra epochs at a lower learning rate). **Auto** picks global or league per league
  using only earlier seasons' results. **ml_ensemble** averages XGBoost auto and NN auto.
- **Validation:** walk-forward by season from 2018/19 (each season predicted by models trained on earlier seasons; early
  stopping on the latest 15% of the training data). Results go into `model_runs` like Elo/Dixon-Coles, so the Models
  page compares everything and strategies can select `xgb`, `xgb_league`, `xgb_auto`, `nn`, `nn_league`, `nn_auto`,
  `ml_ensemble`.
- **Live:** final models are saved in `data/models/` (git-ignored); the automation loop re-predicts upcoming matches with
  them every 6 h. Train from the **Training** page (or `python -m backend.training --models xgb,nn`).
- **GPU setup:** `pip install xgboost` and
  `pip install torch==2.15.0+cu132 --index-url https://download.pytorch.org/whl/cu132`
  (plain `pip install torch` gives a CPU-only build on Windows).
- **First results (run #1, 2026-11-26, 5.5 min on the RTX 4050; 31,884 matches 2018/19 to now, 1X2 log loss, lower is
  better):** ml_ensemble **1.0221**, XGBoost global 1.0223 (auto 1.0226, per-league 1.0228), neural net 1.0259, the old
  blend 1.0244, bookmakers' closing prices 1.0062. XGBoost/ensemble are now the best models on 1X2, O/U 2.5 and BTTS,
  **but still behind the market, so not bettable yet.** Per-league fine-tuning helps in a few leagues (XGBoost: Ligue 2;
  NN: Championship, La Liga, Segunda, Bundesliga, 2. Bundesliga, Serie A) and "auto" uses it only there. The missing
  edge has to come from information the market has and we don't yet: lineups, injuries, player quality.

### Free-plan API collector (built 2026-11-26)
Data sources page: master switch, one switch per provider, daily budget box, today's usage meter, queue progress and
recent requests. Off by default. Runs inside the API server (`backend/collector/engine.py`): one request at a time per
provider, spaced below each plan's per-minute limit, stopping at the daily budget (per UTC day, table `provider_usage`).
Every response is stored untouched in `raw_provider_observations` first. Odds endpoints are refused in code.

| Provider | Free plan | Collects | Status |
|---|---|---|---|
| API-Football | 100/day, 10/min, seasons 2022–2024 | injuries per league-season, fixture lists, then **player stats per fixture** (3,788 queued for 2024/25 so far) | **on since 2026-11-26** (budget 90/day): injuries first, then xG (`fixtures/statistics`) and player stats per match |
| football-data.org | 10/min, 12 competitions incl. Champions League | squads, matches (cross-league via the CL) | **on since 2026-11-26** (key in `.env` as `FOOTBALL_DATA_API_KEY`; budget 450/day, 10/min). Euros 2026/27 returns 404 (no tournament), marked unavailable |
| OpenLigaDB | free, no key | Bundesliga + 2. Bundesliga 2015 to now with goal minutes | on |
| TheSportsDB | test key, ~30/min | team metadata | on |

Parsing: API-Football fixture lists are parsed straight away (teams and fixtures registered, per-fixture follow-ups
queued). Other responses wait in the raw store; their parsers (player stats → `match_players`, injuries → availability
features, OpenLigaDB goal minutes, football-data.org CL matches) are part of the player-layer step below.

### Player layer (started 2026-11-26)
- `backend/models/players.py`: per-player **with/without impact** = team goal difference per 90 with the player on the
  pitch minus off it, shrunk to 0 until ~8 matches of minutes each way, older matches fading (half-life 1 year).
  Point-in-time lineup features for every match: starting-XI impact, starters' recent minutes, number of regulars (11
  most-used in the last 6 matches) not starting, and their impact. Upcoming matches use the expected XI (the regulars).
  Own goals are credited from the final score. Tested in `tests/test_players.py`.
- These 8 features are part of `FEATURE_COLUMNS`, so every training run uses them (NaN where no lineups yet).
- **Players page**: players by impact (filter by league, search), team squads and a **best XI** (4-3-3, 270+ minutes).
  API: `/api/players`, `/api/players/teams`, `/api/players/teams/{id}`.
- Fixed 2026-11-26: the ESPN loader crashed when a player appears twice in one match (it stopped every load at that
  match, leaving ~4,000 scraped matches unloaded); it now keeps the entry with the most minutes.
- **Lineups load every 15 minutes while a crawl runs** (they used to load only when a crawl finished, which for a
  multi-hour backfill meant nothing for hours). A Postgres advisory lock keeps two loaders from colliding. On
  2026-11-26 this linked all 10 leagues (67 matches left waiting, down from ~2,000); 7,270 matches have lineups.
- Squads/best XI only count **current** players: played for that club within ~5 months of its latest match we hold
  (so De Bruyne leaves Man City's squad; he reappears at Napoli once Serie A lineups load).
- **First test (run #3, England only had lineups, ~16% of matches): player features did NOT help** (Premier League
  XGBoost 0.9810 → 0.9825; NN worse). So player and news features are **switches per training run** (Training page,
  "Extra inputs"; off = blanked, as if never seen; saved with each model so live predictions match). Live models were
  retrained with both off (run #4). Re-test with players on once all 10 leagues have lineups.
- Still to do: transfer what-ifs, player vs opponent style, 3D style maps, injuries (API-Football collector feeds them).

### News and team form (built 2026-11-26)
- **Scrapy spider `espn_news`** (`backend/scraping/spiders/espn_news.py`): ESPN's public news JSON, 1 request per league,
  **every hour** automatically (runs alongside the match scraper). Articles carry ESPN team/player IDs, so they link to
  our teams through the existing ESPN mappings (`backend/scraping/news_loader.py` → `news_articles`, `news_mentions`).
- **Reading the articles** (`backend/scraping/news_analysis.py`): transparent football word list; sentiment −1..+1
  (headline counts double; betting talk stripped), injury flag, manager/form/transfer flags. First run: 475 articles,
  768 team links.
- **News features** (7 days before kickoff, strictly before match day): news volume, average sentiment, injury
  stories, per side. Switch "News features" on in a training run once a few weeks of hourly news exist (ESPN's feed
  has no deep archive, so history builds up from now).
- **Team news page**: 7-day team mood (positive/mixed/negative), latest scored headlines with team tags and injury
  badges, filter by league/team/injuries.

### Always on, and waiting out rate limits (2026-11-26)
- **Scraper**: `backend/scraping/auto.py`, called by the automation loop every 15 min (switch on the Scraper page, on by
  default): resumes the 2019→now backfill until it finishes, then every 6 h scrapes the last 10 days and next 14.
- **Rate limits**: `backend/scraping/middleware.py` pauses the whole crawl on HTTP 429/503 (Retry-After, else 1 min
  doubling to 15 min) and retries the same page. The collector pauses a provider until the next UTC day when its quota
  is used and backs off 60 s on 429. Bets are capped separately (.env).

### Plain-English guide on every page (2026-11-26)
`frontend/src/components/Guide.tsx`: on screens 1536 px and wider a side column, otherwise a fold-out box, explaining each
table in plain words with a live Good / Medium / Needs-work verdict (e.g. "Behind market", "Improved", "Still filling").

### More sources: news feeds, xG, team match stats (2026-11-26)
- **RSS news** (`backend/scraping/spiders/rss_news.py`, spider `rss_news`): BBC Sport, The Guardian and Sky Sports football
  feeds, listed in settings (`[[news.rss]]`; add or remove feeds there). Robots.txt allows them. Runs with the ESPN news
  (`news.spiders`). RSS has no team tags, so teams are found **by name** in the headline/summary using every name we know
  (ours + provider labels) plus **nicknames** from settings (`news.team_names.nicknames`: Spurs, Palace, Barca...);
  ambiguous words ("united", "city", "reading"...) are skipped (`news.team_names.ambiguous`). First run: 155 articles,
  169 team links.
- **xG via API-Football**: each finished fixture now queues `fixtures/statistics` (team stats incl. expected goals) before
  `fixtures/players` (`collector.providers.api_football.followups`). Results are saved to `team_match_stats` as `af_*`
  (e.g. `af_expected_goals`). Needs the API-Football collector switched on (free plan: ~90 requests/day).
- **Team-stats feature group** (`team_stats`, Training page switch): recent average of possession, pass accuracy,
  accurate passes, tackles, interceptions, crosses, blocked shots and xG, for and against (list in
  `features.team_stats`). Sources: ESPN match stats (scraper) and API-Football xG.
  **A/B test 2026-11-26** (XGBoost global, walk-forward 2020/21 to now, 24,311 matches): without team stats 1.0214,
  with 1.0220 (England, which has the stats: 1.0259 vs 1.0276). No gain yet, so it stays **off by default**; re-test once
  API-Football xG has been collected (switch the collector on).
- **Not used, on purpose:** Understat returns an error page to non-browser clients (that is blocking automated access;
  we don't disguise ourselves as a browser). Sofascore, WhoScored, Transfermarkt, FBref and Flashscore block or forbid
  automated collection. StatsBomb open data is allowed but covers few of our league-seasons; it can be added later.

### Forward test, self-correction, automatic data selection and retraining (2026-11-26)
- **Mock bets on every upcoming match** (`backend/forward.py`, Forward test page). Inside the app only, never sent to
  Stake. Every automation cycle copies each model's live prediction for each upcoming match into `forward_predictions`
  (it keeps updating until kickoff, then it is **locked**) and records pretend 1-unit bets in `mock_bets`: the
  *favourite* and *value* picks (p × price − 1 ≥ `forward.value_min_edge`, price = Stake's captured price, else the
  pre-match market average; used only as the payout). After the match it is settled: log loss, right/wrong, mock profit.
- **The models learn from their misses:** after settling, each model gets a fitted *temperature* (T > 1 = it was
  over-confident, so probabilities are softened). Once a model has `forward.calibration_min_matches` settled matches,
  the correction is applied to its live predictions automatically. Page shows profit, rolling scores, calibration on real
  future matches, per-league results and each model's correction.
- **Training uses everything, keeps what helps:** with `training.auto_select` (default on) every run first tests each
  extra data group (players, news, team stats, injuries) with a quick XGBoost backtest on the latest seasons and keeps the
  ones that lower log loss (`training.auto_select_min_gain`). The Training page shows what was kept and why.
- **Injuries:** API-Football injury lists → players ruled out / doubtful per team per match (`injuries` group).
- **Retrains itself** every `training.retrain_every_days` (7) from the automation loop.
- **News sentiment** = weighted mix (`news.sentiment_weights`) of the football word list and **VADER** (open-source
  general sentiment model, `vaderSentiment`). Both scores are kept on each article (`signals.words_score/vader_score`).
- **Start at log-on (installed 2026-11-26, task "SportsAnalyzer", 60 s delay):** `powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1` creates a
  Windows log-on task that runs Start SportsAnalyzer.cmd (`-Remove` deletes it). With it, the app runs with no one
  touching it: scraping, collectors, news, predictions, mock bets, learning and retraining all happen on their own.

- **Training run #5 (2026-11-26, first with auto data selection, 44,091 matches, 39,860 training rows, 132 features).**
  Selection test on 2024/25 onwards (baseline log loss 1.01772): **news kept** (−0.00048), players dropped (+0.00022),
  injuries dropped (+0.00021, only 2022–24 coverage), team stats dropped (+0.0031). Backtest from 2018/19:
  XGB global 1.0222 / league 1.0229 / auto 1.0224; NN global 1.0239 / league 1.0228 / auto 1.0232;
  **ML ensemble 1.0208** (run #4: 1.0218; market 1.0062), accuracy 48.6%. Run #5's models are now live.

### Next steps (in order)
1. Nothing to do by hand: the weekly retrain re-tests players, injuries and team stats as their data grows (lineups
   now 9,983 matches). Watch the Forward test page: calibration kicks in after 200 settled matches per model.
2. First real cash-out through the dashboard (owner's click) and first strategy multi in approve mode, to confirm end to end.
2. Compare the ML models with Elo/Dixon-Coles and the market on the Models page; tune them (hyper-parameter search,
   calibration layer) and paper-trade the best one.
3. **Cross-league strength:** add European competitions and domestic cups to the ESPN spider; **one global model
   with league-level strength offsets** (hierarchical), optionally fine-tuned per league. Not fully separate
   per-league models, because teams from different leagues meet.
4. **Player layer** (when the backfill completes): player pages; regularised adjusted plus-minus (impact per 90,
   attack and defence); lineup-adjusted team strength; **best-XI search** over the current squad; **transfer
   what-if** (add a player's impact rating to the expected XI and re-predict); player vs opponent style; then the
   **3D style maps**.
5. **Parsers for the collected API data** (API-Football player stats and injuries, OpenLigaDB, football-data.org) and
   **injury/news spiders** (Scrapy) feeding availability features; then retrain from the Training page.
6. Retrain, backtest, paper-trade; compare with the market; only then consider Auto mode with real money.

### Tools and stack
Python 3.12 (`.venv`), FastAPI + uvicorn, SQLAlchemy 2 (async with asyncpg; psycopg for Scrapy), Alembic, PostgreSQL 17 in Docker, pandas/numpy/scipy/scikit-learn, **XGBoost 3.4 (CUDA) and PyTorch 2.15 (CUDA 13.2)**, Scrapy, httpx/aiohttp; React 19 + Vite + TypeScript + Tailwind v4 + TanStack Query + lucide icons; a Chrome MV3 extension; pytest + ruff. GitHub: `nirvaannair/SportsAnalyzer` (work happens on branch `claude/football-betting-ml-analyzer-e7dd8d` and is merged through PRs; `gh` is at `C:\Program Files\GitHub CLI\gh.exe`, not on PATH).

### Day-to-day: what must be running
`Start SportsAnalyzer.cmd` (desktop shortcut **SportsAnalyzer**) does steps 1–3; see the Easy guide at the top. By hand:
1. **Docker Desktop** (database container `sportsanalyzer-db`).
2. **API:** `.\.venv\Scripts\uvicorn.exe backend.api.main:app --reload --port 8000`
3. **Dashboard:** `npm --prefix frontend run dev`, then open http://localhost:5173
4. For Stake: Chrome with the **SportsAnalyzer Stake Helper** extension loaded from `extension/` and a logged-in stake.com tab.

### Dashboard pages
Players (impact ratings, squads, best XI) · Team news (7-day mood, scored headlines, injuries) · Training (start/stop runs, live loss curve per season fold, global-vs-league table, backtest scores) · Data sources (collector switches, budgets, quota meters, queue) · Overview (top row: live Stake balance, money on Stake now with payout if all win, bets sent by the system today versus caps, strategies on; System card: helper, execution, learned requests, automation, predictions, scraper; In-play payout card; strategy controls: on/off, paper/approve/auto, reinvest %, settings incl. confidence band and multi legs) · Bet ledger · Matches (model probabilities vs prices) · Stake (helper, balance, switches, learned requests, approvals, Your Stake bets + cash-out, outcomes) · Models (backtest metrics, calibration, simulated bets) · Data sources · Scraper (runs, live log, items) · Identity review. Pages marked P2–P4 in the sidebar are not built yet.

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

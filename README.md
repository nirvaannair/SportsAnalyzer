# SportsAnalyzer

SportsAnalyzer is a real-data sports betting analytics platform. It collects sports and betting data, stores it in PostgreSQL, generates historical features, and prepares training examples for future prediction models.

The project is still under development. Data ingestion and database pipelines are currently the most complete parts of the system. The ML training and inference pipelines are scaffolded but not yet operational.

## Core Principle

> Never use fake, synthetic, placeholder, or fabricated data.

All stored statistics, model features, predictions, and dashboard values must come from real provider data or calculations derived from real provider data.

## Current Architecture

```text
Stake GraphQL API
        |
        v
Upcoming fixtures, markets, odds
        |
        v
PostgreSQL canonical tables
        |
        +----------------------+
        |                      |
        v                      v
Odds snapshots          Betting history
                               |
                               v
                           Bet legs
                               |
                               v
                       Training examples


API-Football REST API
        |
        v
Leagues, teams, fixtures, statistics
        |
        v
Provider-specific database tables
        |
        +----------------------+
        |                      |
        v                      v
Historical snapshots   Fixture feature rows
```

## Data Sources

### Stake

The Stake GraphQL integration provides:

- Sports
- Tournaments
- Fixtures
- Markets
- Market groups
- Market templates
- Outcomes
- Current odds
- Betting history
- Bet legs
- Bet and fixture statuses
- Account balance information

Stake data is accessed through the integration code in `backend/integrations/stake/`.

### API-Football

The API-Football integration provides:

- Leagues
- Teams
- Historical fixtures
- Fixture scores
- Match results
- Team season statistics

API-Football data is accessed through `backend/integrations/api_football/`.

The currently configured historical synchronization includes these league IDs:

- 39: Premier League
- 40: Championship
- 78: Bundesliga
- 98: J1 League
- 99: J2 League
- 135: Serie A
- 140: La Liga

### Planned Providers

These providers have integration scaffolding or are planned for future enrichment:

- FBref
- Understat
- WhoScored
- FootyStats
- The Odds API

These sources are not yet part of a complete production feature pipeline.

## Implemented Data Pipelines

## 1. Upcoming Stake Fixture and Market Pipeline

```text
Stake GraphQL API
    |
    v
Sports
    |
    v
Tournaments
    |
    v
Fixtures
    |
    v
Market groups
    |
    v
Market templates
    |
    v
Markets
    |
    v
Outcomes and odds
    |
    v
PostgreSQL
```

The main entry point is:

```text
`sync_stake_fixtures.py`
```

The script currently synchronizes upcoming soccer total markets. It uses:

```text
`stake_fixture_sync_service.py`
`stake_market_sync_service.py`
`stake_main_market_sync_service.py`
```

The resulting data is stored in the canonical database tables for sports, tournaments, fixtures, market groups, market templates, markets, and outcomes.

This pipeline is intended to support:

- Upcoming match discovery
- Market discovery
- Current odds storage
- Odds movement tracking
- Future match analysis
- Future bet-slip generation

## 2. Stake Betting History Pipeline

```text
Stake account history
    |
    v
Bet history
    |
    v
Individual bet legs
    |
    v
PostgreSQL
```

The entry point is:

```text
`sync_bet_history.py`
```

The implementation is:

```text
`stake_bet_history_sync_service.py`
```

For each bet, the system stores:

- Stake bet ID
- Bet-slip ID
- Bet status
- Stake amount
- Payout
- Payout multiplier
- Creation and update timestamps
- Serialized outcome data

Each outcome is also stored as an individual `BetLeg` containing:

- Fixture ID and name
- Market ID and name
- Outcome ID and name
- Odds
- Leg status
- Market status
- Fixture status
- Bet status

This pipeline is the source of historical outcome labels for future machine-learning work.

## 3. API-Football Historical Fixture Pipeline

```text
API-Football
    |
    v
Leagues and seasons
    |
    v
Historical fixtures
    |
    v
API-Football fixture tables
```

The main entry point is:

```text
`sync_api_football_historical_fixtures.py`
```

The implementation is:

```text
`api_football_fixture_sync_service.py`
```

The data is written to provider-specific tables including:

- `api_football_leagues`
- `api_football_teams`
- `api_football_fixtures`

The fixtures contain:

- League
- Season
- Match date
- Home team
- Away team
- Home score
- Away score
- Match status
- Provider fixture ID

## 4. API-Football Team and League Pipeline

League and team synchronization is handled by:

```text
`sync_api_football_leagues.py`
`sync_top_api_football_leagues.py`
`sync_api_football_teams.py`
`sync_canonical_teams.py`
```

The pipeline is:

```text
API-Football leagues and teams
    |
    v
Provider team and league records
    |
    v
Canonical teams and team mappings
```

Team mappings connect an internal team to provider-specific identifiers. This allows data from Stake and API-Football to be associated with the same canonical team.

Relevant tables include:

- `teams`
- `team_mappings`
- `api_football_teams`
- `api_football_leagues`

## 5. API-Football Team Statistics Pipeline

```text
Stored API-Football fixtures
    |
    v
Discovered leagues, seasons, and teams
    |
    v
API-Football team statistics
    |
    v
api_football_team_statistics
```

The entry point is:

```text
`sync_api_football_team_statistics.py`
```

The service is:

```text
`api_football_team_statistics_sync_service.py`
```

The stored statistics include:

- Matches played
- Wins
- Draws
- Losses
- Goals for
- Goals against
- Goal difference
- Clean sheets
- Failed-to-score count
- Recent form
- Home and away performance where available

## 6. Historical Team Snapshot Pipeline

Historical snapshots prevent future feature generation from using information that was not available before a fixture.

```text
Historical API-Football fixtures
    |
    v
Previous matches for each team
    |
    v
Team record calculated before fixture date
    |
    v
historical_team_snapshots
```

The entry point is:

```text
`generate_historical_team_snapshots.py`
```

The implementation is:

```text
`historical_team_snapshot_generation_service.py`
```

For each fixture, the service creates a snapshot for both teams using only fixtures with an earlier date.

Stored values include:

- Matches played
- Wins
- Draws
- Losses
- Goals for
- Goals against
- Goal difference
- Recent form from the last ten previous matches

## 7. Football Fixture Feature Pipeline

```text
API-Football fixture
    |
    +--> Home team statistics
    |
    +--> Away team statistics
    |
    v
football_fixture_features
```

The entry point is:

```text
`generate_football_fixture_features.py`
```

The implementation is:

```text
`football_feature_generation_service.py`
```

Each feature row represents one API-Football fixture. Current features include home and away values for:

- Matches played
- Wins
- Draws
- Losses
- Goals for
- Goals against
- Goal difference
- Clean sheets
- Failed-to-score count
- Form

Feature rows are stored in:

```text
football_fixture_features
```

## 8. Training Dataset Pipeline

```text
BetLeg
    |
    v
Only settled won/lost legs
    |
    v
Market and selection normalization
    |
    v
TrainingExample
```

The entry point is:

```text
`generate_training_dataset.py`
```

The implementation is:

```text
`training_dataset_generator_service.py`
```

Only legs with these statuses become examples:

```text
won
lost
```

Pending, voided, and other unresolved statuses are skipped.

Each training example contains:

- Original bet-leg ID
- Fixture ID and name
- Sport
- Tournament
- Home team
- Away team
- Market name
- Normalized market type
- Outcome name
- Odds
- Implied probability
- Home or away selection flags
- Selected team and side
- Binary target

The target is:

```text
won  -> 1
lost -> 0
```

The implied probability is:

```text
implied_probability = 1 / odds
```

A training example is skipped when odds are missing or when an example for that bet leg already exists.

## Data Destinations

The primary destination for synchronized and generated data is PostgreSQL.

### Core canonical tables

- `sports`
- `tournaments`
- `teams`
- `team_mappings`
- `fixtures`
- `market_groups`
- `market_templates`
- `markets`
- `outcomes`
- `odds_snapshots`
- `bet_history`
- `bet_legs`
- `training_examples`
- `predictions`

### Provider-specific tables

- `api_football_leagues`
- `api_football_teams`
- `api_football_fixtures`
- `api_football_team_statistics`

### Derived tables

- `historical_team_snapshots`
- `football_fixture_features`

The `data/` directory is used for local runtime data such as raw responses, processed files, caches, exports, and models. It must not be used to commit secrets or private account data.

## Backend and Frontend Flow

The newer application layer is located under `backend/app/`.

```text
React frontend
    |
    +--> REST API
    |
    +--> WebSocket API
    |
    v
backend/app
    |
    v
Services and repositories
    |
    v
Database
```

Backend API areas include:

- Matches
- Analysis
- Bets
- Bet slips
- Settings
- Stake integration
- WebSocket updates

Frontend pages currently include:

- Dashboard
- Matches
- Analysis
- Slip builder
- Settings

The data synchronization scripts primarily use the older direct service layer under:

```text
backend/database/
backend/integrations/
backend/services/
```

The `backend/app/` layer is the application and dashboard surface that is being connected to those data services.

## Machine Learning Status

The ML service contains scaffolding for:

- Data collection
- Feature engineering
- Model training
- Inference
- Probability calculation
- Ensemble models
- Poisson models
- Expected-goals models
- Confidence models

Relevant directories include:

```text
ml-service/collectors/
ml-service/feature_engineering/
ml-service/inference/
ml-service/models/
ml-service/pipelines/
ml-service/jobs/
ml-service/training/
```

The following files currently exist as pipeline or job entry points but are not yet implemented as a complete end-to-end workflow:

```text
`data_pipeline.py`
`training_pipeline.py`
`inference_pipeline.py`
`collect_data.py`
`train_models.py`
`generate_predictions.py`
```

Therefore, the current production data flow ends at database-backed feature rows and training examples. Model training and prediction promotion still need to be implemented and validated.

## Planned Model Features

Future models may use:

- Team form
- Home and away performance
- Goals for and against
- Goal difference
- Clean sheets
- Failed-to-score rates
- Historical team snapshots
- Market type
- Selection
- Odds
- Implied probability
- Opening and closing odds
- Odds movement
- Expected goals
- Possession
- Pressing and defensive actions
- Player and match ratings

Sportsbook odds should remain contextual features. They should not simply become the model prediction.

## Planned Model Outputs

- Match-winner probabilities
- Over/under probabilities
- Both-teams-to-score probabilities
- Correct-score probabilities
- Selection win probability
- Expected value
- Confidence estimates
- Potential value bets
- Potential market disagreements

For decimal odds `O` and model probability `P`:

```text
Expected value = (P * O) - 1
```

## Model Retraining Policy

Settled outcomes should be stored immediately, but the model should not be retrained after every single bet.

A future retraining workflow should:

1. Store each settled bet leg.
2. Generate new training examples.
3. Retrain on a schedule or after a sample threshold.
4. Evaluate the candidate model against the production model.
5. Promote the candidate only when it passes predefined checks.

Evaluation should include more than accuracy:

- Calibration
- Log loss
- Precision and recall
- Return on investment
- Drawdown
- Win rate
- Expected-value performance
- Closing-line value

## Database Migrations

Database schema changes are managed with Alembic.

Migration files are located in:

```text
backend/alembic/versions/
```

The project also contains SQL schema drafts in:

```text
backend/sql/
```

Alembic migrations are the preferred source for the active database schema.

## Project Structure

```text
backend/          API, integrations, services, models, and migrations
frontend/         React and TypeScript dashboard
ml-service/       ML collectors, features, models, training, and inference
shared/           Shared types, schemas, constants, and utilities
scripts/          Synchronization and data-generation entry points
data/             Local runtime data and generated artifacts
docs/             Architecture, API, database, ML, and deployment notes
infrastructure/   Docker, PostgreSQL, Redis, monitoring, and deployment files
StakeAPI/         Stake API client library
tests/            Project-level tests
```

## Development Priorities

1. Complete Stake bet-history synchronization.
2. Link Stake bet legs to canonical fixtures.
3. Complete provider-to-canonical team matching.
4. Validate historical snapshot generation.
5. Add data-leakage-safe feature generation.
6. Complete training dataset validation.
7. Implement the ML training pipeline.
8. Implement model evaluation and calibration.
9. Implement inference and prediction persistence.
10. Connect backend API routes to live database data.
11. Connect the dashboard to backend REST and WebSocket APIs.
12. Add monitoring for synchronization and model jobs.
13. Add automated betting only after extensive validation and risk controls.

## Security and Privacy

Never commit:

- `.env` files
- API keys
- Stake authentication tokens
- Account balances
- Private betting history
- Raw provider credentials
- Local databases
- Generated model artifacts containing private data

Use `.env.example` for safe configuration templates.

## Disclaimer

Sports betting involves financial risk. Predictions are uncertain and are not guaranteed outcomes. Automated betting should remain disabled until the models, data quality, bankroll controls, exposure limits, and failure handling have been thoroughly validated.
```
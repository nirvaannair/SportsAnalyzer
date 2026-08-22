# SportsAnalyzer

## Project Overview

SportsAnalyzer is a data-driven sports betting and match prediction platform designed to ingest real-world betting slips, sportsbook odds, football statistics, historical match results, advanced analytics, and market data to build machine learning models capable of generating accurate sports predictions and identifying value betting opportunities.

The project is intentionally built around real data only.

No mock data, placeholder analytics, fake progress indicators, synthetic betting records, or fabricated model outputs are allowed anywhere in the system.

The long-term goal is to create a production-grade sports intelligence platform capable of:

* Predicting match winners
* Predicting Over/Under markets
* Predicting Both Teams To Score (BTTS)
* Predicting scorelines
* Identifying bookmaker mispricing
* Detecting value betting opportunities
* Detecting upset opportunities
* Measuring confidence and uncertainty
* Comparing model predictions against sportsbook markets

---

# Core Philosophy

The project follows several strict principles:

### 1. Real Data Only

All frontend displays, backend processing, and ML training pipelines must use actual data.

No:

* Fake statistics
* Mock odds
* Placeholder predictions
* Demo model outputs
* Hardcoded records

---

### 2. Team-Centric Learning

The model should not learn entire betting slips as a single object.

Instead it should learn:

* Team behavior
* Match behavior
* Market behavior

Each team is treated as its own entity with historical characteristics.

Example:

Liverpool

* Attack strength
* Defensive strength
* Home performance
* Away performance
* Recent form

Arsenal

* Attack strength
* Defensive strength
* Home performance
* Away performance
* Recent form

The model learns these characteristics and combines them when evaluating future fixtures.

---

### 3. Sportsbook Odds Are Features

Odds should never become the prediction itself.

Many betting models fail because they simply learn to copy bookmakers.

Instead sportsbook odds are treated as contextual features.

The model must be capable of:

* Agreeing with markets
* Disagreeing with markets
* Detecting market inefficiencies
* Identifying potential underdogs
* Finding value bets

---

### 4. Prediction Diversity

Future versions of the ML system should avoid sportsbook-bias collapse.

The model should be capable of:

* Upset prediction
* Market disagreement detection
* Probability calibration
* Confidence estimation
* Value estimation

rather than blindly selecting favorites.

---

# Current Data Sources

## Stake Betting Slips

Source:

* User betting history

Collected Information:

* Bet slips
* Bet legs
* Markets
* Odds
* Selections
* Match information
* Historical betting performance

Purpose:

* Historical betting analysis
* Market analysis
* Training data generation
* Odds behavior analysis

---

## API-Football

Current Primary Data Provider

Collected Information:

### Leagues

* League IDs
* League names
* Countries
* Seasons

### Teams

* Team names
* Team mappings
* Provider IDs

### Fixtures

* Match dates
* Home teams
* Away teams
* Final scores
* Winners
* Match status

### Team Statistics

* Matches played
* Wins
* Draws
* Losses
* Goals scored
* Goals conceded
* Goal difference
* Home performance
* Away performance
* Clean sheets
* Failed to score
* Recent form

Current leagues include:

* Premier League
* Championship
* Bundesliga
* Serie A
* La Liga
* J1 League
* J2/J3 League

---

# Planned Data Sources

## Understat

Primary purpose:

Advanced expected goals metrics.

Planned metrics:

* xG
* xGA
* NPxG
* NPxGA
* Expected points
* Shot quality metrics

Expected value:

Very high.

These are among the strongest predictive features available in football analytics.

---

## FBRef

Primary purpose:

Advanced team performance analytics.

Planned metrics:

* Possession
* Pressing
* PPDA
* Progressive passes
* Progressive carries
* Touches
* Passing statistics
* Defensive actions
* Goal creation metrics

Expected value:

Extremely high.

Provides deep team-level performance data.

---

## WhoScored

Primary purpose:

Performance ratings and player statistics.

Planned metrics:

* Team ratings
* Player ratings
* Form ratings
* Match performance ratings

Expected value:

Medium to high.

Useful as supplementary signals.

---

## FootyStats

Primary purpose:

Betting-oriented statistics.

Planned metrics:

* BTTS rates
* Over/Under rates
* Corner statistics
* Card statistics
* Goal timing statistics
* Home/Away trends

Expected value:

High for betting market predictions.

---

# Current Database Structure

## Core Entities

### Teams

Represents football teams.

Stores:

* Internal team IDs
* Team metadata

---

### Team Mappings

Maps provider IDs to internal teams.

Example:

Internal Team
↔ API-Football Team ID
↔ Understat Team ID
↔ FBRef Team ID

Purpose:

Provider-independent architecture.

---

### Leagues

Stores football competitions.

---

### Fixtures

Stores football matches.

Includes:

* Home team
* Away team
* Date
* Scores
* Winner
* Season
* League

---

### Team Statistics

Stores season-level team performance.

Includes:

* Wins
* Draws
* Losses
* Goals scored
* Goals conceded
* Goal difference
* Home records
* Away records
* Form
* Clean sheets

---

### Odds Snapshots

Stores sportsbook market information.

Includes:

* Market odds
* Market movement
* Historical pricing

Purpose:

Market intelligence and ML features.

---

### Bet Legs

Stores individual selections from betting slips.

---

### Training Examples

Stores ML-ready training rows.

Currently under development.

---

# Planned Canonical Data Model

Future provider-specific tables:

* api_football_team_statistics
* fbref_team_statistics
* understat_team_statistics
* whoscored_team_statistics
* footystats_team_statistics

Feed into canonical tables:

### team_statistics

Basic statistics.

### team_advanced_statistics

Advanced analytics.

### fixture_features

Feature vectors used for ML.

### fixture_labels

Actual outcomes used as targets.

This separates raw provider data from ML training data.

---

# Machine Learning Architecture

## Core Principle

One row should represent one fixture.

Not one betting slip.

Not one betting market.

One fixture.

Example:

Liverpool vs Arsenal

The fixture becomes a feature vector.

Labels are generated separately.

---

## Feature Categories

### Team Performance

* Wins
* Draws
* Losses
* Form
* Goal difference
* Clean sheets

---

### Offensive Strength

* Goals scored
* xG
* Shots
* Shot quality

---

### Defensive Strength

* Goals conceded
* xGA
* Clean sheets

---

### Home/Away Strength

* Home win rate
* Away win rate
* Home goals
* Away goals

---

### Market Features

* Opening odds
* Closing odds
* Odds movement
* Market disagreement

---

### Advanced Analytics

* xG
* xGA
* PPDA
* Possession
* Progressive passes
* Progressive carries

---

## Labels

Planned labels include:

### Match Winner

* Home Win
* Draw
* Away Win

### Goals Markets

* Over 1.5
* Over 2.5
* Over 3.5

### BTTS

* Yes
* No

### Scoreline

* Home goals
* Away goals

---

# Historical Stake Bet Usage

Historical Stake bets are not the training target.

Instead they become:

### Market Features

Examples:

* Odds movement
* Popular selections
* Market consensus

Used alongside football statistics.

This allows the model to learn both:

* Football performance
* Market behavior

without simply copying sportsbook pricing.

---

# Long-Term System Goals

The final platform should be capable of:

### Data Collection

* Multi-provider ingestion
* Automated synchronization
* Historical data maintenance

### Analytics

* Team analysis
* League analysis
* Market analysis
* Betting analysis

### Machine Learning

* Match outcome prediction
* Goal prediction
* BTTS prediction
* Score prediction
* Value bet detection

### Operational Monitoring

* Real-time ingestion monitoring
* Sync status tracking
* Training monitoring
* Prediction monitoring

### Prediction Engine

* Generate probabilities
* Compare against sportsbook odds
* Estimate confidence
* Identify value opportunities
* Detect potential upsets

The ultimate objective is a production-grade sports intelligence system built on real-world football data, advanced analytics, betting market information, and machine learning models capable of generating actionable predictions rather than simply replicating sportsbook expectations.

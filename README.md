Here's a README draft that reflects where the project currently stands, what has already been built, the current architecture, and the roadmap.

# SportsAnalyzer

## Overview

SportsAnalyzer is an automated sports betting analysis and execution platform designed to:

* Collect real betting market data from Stake
* Build a historical betting database
* Train machine learning models on individual betting selections
* Generate betting recommendations
* Automatically place bets through Stake
* Continuously learn from betting outcomes
* Support multiple sports and betting markets
* Provide a complete operational dashboard for monitoring performance

The system is designed around one core principle:

**Never use fake data.**

All analysis, predictions, model training, dashboards, statistics, and betting decisions must be based entirely on real-world data.

---

# Current Technology Stack

## Backend

* Python 3.12
* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* AsyncIO

## Frontend

* React
* TypeScript
* Vite

## Betting Integration

Stake GraphQL API

Current Stake integration includes:

* Fixtures
* Sports
* Tournaments
* Markets
* Outcomes
* Odds
* Bet History
* Individual Bet Legs
* Bet Statuses
* Cashouts
* Settled Bets
* Active Bets

---

# Current Database Structure

## Core Sports Data

### sports

Stores sports

Examples:

* Football
* Basketball
* Tennis
* Cricket
* MMA

---

### tournaments

Stores leagues and competitions

Examples:

* Premier League
* NBA
* IPL
* UFC

---

### fixtures

Stores matches/events

Examples:

* Arsenal vs Chelsea
* Lakers vs Celtics

---

### market_groups

Stores market categories

Examples:

* Main Markets
* Totals
* Player Props

---

### market_templates

Stores reusable market definitions

Examples:

* Winner
* Asian Total
* Over/Under

---

### markets

Stores actual markets for a fixture

Examples:

* Arsenal vs Chelsea Winner
* Arsenal vs Chelsea Over 2.5

---

### outcomes

Stores betting selections

Examples:

* Arsenal
* Chelsea
* Over 2.5
* Under 2.5

---

### odds_snapshots

Stores historical odds movement

Used for:

* Line movement analysis
* CLV tracking
* Market efficiency analysis

---

## Betting Data

### bet_history

Stores all Stake betting slips

Current count:

~1000+ real betting slips

Includes:

* Stake Bet ID
* Stake Status
* Stake Amount
* Payout
* Creation Date
* Update Date
* Outcomes JSON

---

### bet_legs

Stores every individual selection from every bet

Current count:

~12,500+ individual selections

Includes:

* Fixture
* Market
* Outcome
* Odds Taken
* Leg Status
* Bet Status

Leg statuses currently collected:

* won
* lost
* voided
* voidedWon
* voidedLost
* pending

This table is the foundation for machine learning training.

---

# Current Data Pipeline

## Fixture Sync

Stake API

↓

Sports

↓

Tournaments

↓

Fixtures

↓

Markets

↓

Outcomes

↓

PostgreSQL

---

## Historical Bet Sync

Stake API

↓

Bet History

↓

Individual Bet Legs

↓

PostgreSQL

---

## Current Result Feedback

Stake API

↓

Leg Status

↓

Bet Legs Table

↓

Training Dataset

---

# Current Stake Capabilities

The Stake integration currently provides access to:

## Betting History

* Active Bets
* Settled Bets
* Cashouts
* Bet IDs
* Bet Statuses

---

## Individual Bet Legs

For each leg:

* Fixture Name
* Market Name
* Selection
* Odds Taken
* Leg Result

Example:

Fixture:
Arsenal vs Chelsea

Market:
Winner

Selection:
Arsenal

Odds:
1.80

Result:
Won

---

## Market Data

For every fixture:

* Market IDs
* Market Names
* Outcome Names
* Current Odds

---

## Odds Tracking

Current odds snapshots can be collected and stored.

This enables:

* Closing Line Value tracking
* Market movement tracking
* Line efficiency analysis

---

# Machine Learning Strategy

## Critical Principle

The model will NEVER train on an entire betting slip.

Example:

Bad:

25-leg accumulator won

Model learns:
"25-leg accumulator = good"

This is useless.

---

Instead the model trains on every individual selection.

Example:

Arsenal Winner
Won

Target = 1

Chelsea Winner
Lost

Target = 0

Over 2.5
Won

Target = 1

Under 2.5
Lost

Target = 0

This creates thousands of usable training examples.

---

# Current Training Dataset

Current usable examples:

Won Legs:
~6500

Lost Legs:
~5800

Total:
~12,000+

These are real betting outcomes.

---

# Planned Feature Engineering

For each selection:

## Match Features

* Home Team
* Away Team
* League
* Match Date
* Team Form
* Win Rate
* Draw Rate
* Loss Rate
* Goals Scored
* Goals Conceded

---

## Market Features

* Market Type
* Odds
* Implied Probability

Implied Probability Formula:

P = 1 / Odds

---

## Odds Features

* Opening Odds
* Current Odds
* Closing Odds
* Odds Movement

---

## Historical Features

* Similar Market Win Rate
* Similar Odds Win Rate
* Team Historical Performance

---

# Planned ML Models

## Baseline

Logistic Regression

Used as benchmark.

---

## Tree Models

Random Forest

Gradient Boosting

XGBoost

LightGBM

CatBoost

---

## Neural Networks

Deep Learning Models

Used only if they outperform tree-based methods.

---

# Probability Analysis

## Implied Probability

P=\frac{1}{Odds}

---

## Expected Value

EV=(P_{model}\times Odds)-1

---

## Kelly Criterion

f^*=\frac{bp-q}{b}

Used for bankroll optimization.

---

# Continuous Learning System

Goal:

Bet

↓

Match Ends

↓

Stake Returns Result

↓

Bet Leg Updated

↓

Training Dataset Updated

↓

Model Retraining

↓

Model Improves

This creates a self-learning betting system.

---

# Automatic Betting System

Planned functionality:

Model Recommendation

↓

Risk Checks

↓

Bankroll Validation

↓

Stake Bet Placement API

↓

Bet Confirmation

↓

Bet Tracking

↓

Result Collection

↓

Model Feedback

---

# Compounding Strategy

User configurable.

Example:

Starting Bankroll

₹1000

Bet 1

Stake:
₹100

Profit:
₹40

Next Stake:
₹40

Only profit rolls forward.

Principal remains protected.

Additional strategies planned:

* Fixed Stake
* Kelly
* Fractional Kelly
* Flat Betting
* Percentage Bankroll
* Profit Compounding

---

# External Data Sources Still Required

## FBref

[https://fbref.com/en/](https://fbref.com/en/)

Planned use:

* Team Statistics
* Player Statistics
* Match Statistics

---

## Understat

[https://understat.com/](https://understat.com/)

Planned use:

* xG
* xGA
* Shot Data

---

## WhoScored

[https://www.whoscored.com/](https://www.whoscored.com/)

Planned use:

* Match Ratings
* Team Ratings
* Player Ratings

---

## FootyStats

[https://footystats.org/](https://footystats.org/)

Planned use:

* Team Form
* Goal Trends
* BTTS Trends

---

## The Odds API

[https://the-odds-api.com/](https://the-odds-api.com/)

Planned use:

* Multi-bookmaker odds
* Market comparison
* Arbitrage detection
* Line shopping

---

# Multi-Sport Expansion

The architecture must support:

* Football
* Basketball
* Tennis
* Cricket
* MMA
* Baseball
* Hockey
* Esports

Every sport should plug into the same:

Sport

↓

Tournament

↓

Fixture

↓

Market

↓

Outcome

Model

structure.

---

# Planned Frontend Dashboard

## Sports Selection

Choose:

* Football
* Basketball
* Tennis
* Cricket
* MMA

---

## Market Selection

Choose:

* Winner
* Total
* Handicap
* BTTS
* Mix

---

## Odds Filters

Minimum Odds

Maximum Odds

Target Odds Range

---

## Prediction Dashboard

Display:

* Predicted Probability
* Implied Probability
* Expected Value
* Confidence Score

---

## Betting Dashboard

Display:

* Active Bets
* Settled Bets
* Cashouts
* Open Exposure

---

## Bankroll Dashboard

Display:

* Current Bankroll
* Profit
* ROI
* Yield

---

## Model Dashboard

Display:

* Model Accuracy
* ROI
* Win Rate
* EV Performance
* CLV Performance

---

## Historical Analytics

Display:

* Market Performance
* League Performance
* Sport Performance
* Odds Range Performance
* Team Performance

---

# Immediate Next Priorities

1. Finish Stake bet history ingestion

2. Link bet legs to fixtures

3. Integrate FBref

4. Integrate Understat

5. Integrate WhoScored

6. Integrate FootyStats

7. Integrate The Odds API

8. Build feature engineering pipeline

9. Build training dataset generator

10. Train first baseline models

11. Build model evaluation system

12. Build automatic bet placement pipeline

13. Build operational frontend dashboard

14. Build realtime model monitoring

15. Build continuous retraining system

16. Launch fully automated betting workflow

One thing I would change from the plan above is the continuous retraining section. I would not retrain immediately after every single bet settles. With only one new sample, the model can become unstable. A better approach is:

* Store every settled leg immediately
* Append it to the training dataset
* Retrain after a threshold (for example every 100 new settled legs, daily, or weekly)
* Compare the new model against the current production model
* Only promote the new model if it performs better

That prevents the model from overreacting to short-term variance while still learning from new results.

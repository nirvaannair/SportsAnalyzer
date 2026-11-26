export type Health = {
  status: 'ok' | 'degraded'
  database: { ok: boolean; error: string | null }
  time: string
}

export type Provider = {
  name: string
  label: string
  configured: boolean
  observations: number
  last_received_at: string | null
}

export type Summary = {
  teams: number
  matches: number
  odds_quotes: number
  first_match: string | null
  last_match: string | null
  identity_review: number
}

export type CompetitionSeason = { start_year: number; label: string; matches: number; latest: string | null }
export type Competition = { code: string; name: string; country: string; tier: number; seasons: CompetitionSeason[] }

export type MatchRow = {
  id: number
  date: string
  kickoff_at: string | null
  status: 'finished' | 'scheduled'
  home: string
  away: string
  home_goals: number | null
  away_goals: number | null
  ht_home_goals: number | null
  ht_away_goals: number | null
  odds_1x2: { bookmaker: string; kind: 'open' | 'close'; home: number; draw: number; away: number } | null
  prediction: Prediction | null
}

export type Prediction = {
  source: 'live' | 'backtest'
  p_home: number
  p_draw: number
  p_away: number
  p_over25: number | null
  p_btts: number | null
  exp_home_goals: number | null
  exp_away_goals: number | null
}

export type Score1x2 = { logloss: number; brier: number; rps: number; accuracy: number }
export type ModelSummary = {
  model: string
  created_at: string
  default: boolean
  live_trained_until: string | null
  params: Record<string, unknown>
  metrics: {
    n: number
    '1x2': Score1x2
    baseline_1x2: Score1x2
    ou25_logloss?: number
    btts_logloss?: number
    calibration_1x2: { bucket: string; predicted: number; observed: number; count: number }[]
    by_season: ({ season: number; n: number } & Score1x2)[]
    by_league: ({ league: string; n: number } & Score1x2)[]
    market_reference_1x2?: (Score1x2 & { n: number }) | null
    simulated_bets?: { market: string; edge_threshold: number; bets: number; profit_units: number; roi: number }[]
  }
}

export type Candidate = { team_id: number; name: string; fixture_score: number | null; name_score: number }
export type PendingMapping = {
  id: number
  provider: string
  provider_id: string
  label: string
  country: string | null
  fixtures: number
  candidates: Candidate[]
}
export type IdentityReview = {
  pending: PendingMapping[]
  counts: { provider: string; status: string; method: string | null; count: number }[]
}

export type ScrapeRun = {
  id: number
  spider: string
  args: { leagues?: string; date_from?: string; date_to?: string; refetch?: string }
  status: 'queued' | 'running' | 'loading' | 'finished' | 'failed' | 'stopped'
  stats: {
    requests?: number
    responses?: number
    cached?: number
    items?: number
    items_by_type?: Record<string, number>
    errors?: number
    http_errors?: Record<string, number>
    loaded?: Record<string, number>
  }
  message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}
export type ScrapedItemRow = {
  id: number
  run_id: number | null
  spider: string
  type: string
  key: string
  url: string
  scraped_at: string
  loaded: boolean
  summary: string
}
export type ScraperTotals = {
  items_by_type: Record<string, number>
  details_waiting_for_team_links: number
  players: number
  matches_with_lineups: number
}

export type StakeStatus = {
  helper: { connected: boolean; last_seen?: string; host?: string; version?: string; token_source?: string;
            error?: string | null; hook?: { fetchSeen: number; xhrSeen: number; captured: number; unreadable: number } | null; balances?: { available: Record<string, number>; vault: Record<string, number> } | null }
  execution_enabled: boolean
  learn_mode: boolean
  limits: { max_bet: number; budget: number; max_bets_per_day: number; currency: string; approval_above: number }
  spent_total: number
  bets_today: number
  budget_left: number
  bet_request_learned: boolean
  bet_operation: string | null
  multi_request_learned: boolean
  cashout_request_learned: boolean
  bet_list_learned: boolean
  orders_by_status: Record<string, number>
}
export type StakeOutcome = { outcome_id: string; fixture: string | null; market: string | null; name: string;
                             selection: string | null; price: number | null; active: boolean | null; seen_at: string
                             league: string | null; start_time: string | null; match_id: number | null }
export type StakeOrder = {
  id: number; created_at: string; source: string; outcome_id: string; description: string; amount: number
  currency: string; min_price: number | null; status: string; status_detail: string | null
  request_preview: Record<string, unknown> | null; stake_bet_id: string | null; placed_price: number | null
  approved_at: string | null; sent_at: string | null; finished_at: string | null
}

export type StrategyRow = {
  id: number; name: string; kind: 'flat' | 'kelly' | 'multi'; mode: 'paper' | 'approve' | 'auto'; enabled: boolean
  paused_reason: string | null; model: string; bankroll_start: number; reinvest_pct: number; stake_pct: number
  kelly_fraction: number; max_stake: number; min_edge: number; min_price: number; max_price: number
  min_prob: number; max_prob: number; multi_legs: number
  markets: string[]; leagues: string[]; max_bets_per_day: number; drawdown_stop_pct: number
  bankroll: { pot: number; available: number; banked: number; open_stakes: number; profit: number;
              drawdown_pct: number; roi: number | null }
  bets: Record<string, number>
}
export type LedgerBet = {
  id: number; strategy: string; match: string; date: string; kickoff_at: string | null; score: string | null
  market: string; selection: string; mode: string; p_model: number; price: number; price_source: string
  edge: number; stake: number; status: string; profit: number | null; order_status: string | null
  created_at: string; settled_at: string | null
  legs: { match_id: number; market: string; selection: string; p: number; price: number }[] | null
}
export type Exposure = {
  real: { bets: number; stake: number; potential_payout: number; cashout_value: number }
  pending_orders: { count: number; stake: number; potential_payout: number }
  paper: { bets: number; stake: number; potential_payout: number }
}
export type StakeBetLeg = { fixture: string | null; selection: string | null; market: string | null
  odds_at_bet: number | null; current_odds: number | null; status: string | null; open: boolean }
export type StakeBetRow = { id: string; status: string | null; open: boolean; amount: number; currency: string | null
  title: string; legs: StakeBetLeg[]; placed_at: string | null; potential_payout: number | null
  cashout_available: boolean; cashout_reason: string | null; cashout_estimate: number | null }
export type Automation = {
  started_at?: string; next_cycle_at?: string
  last_cycle?: { at: string; settled: number; strategies: Record<string, { created?: number; skipped?: string }> }
  last_refresh?: { at: string; fixtures: number; predicted: Record<string, number> }
  last_error?: { at: string; error: string } | null
}

export type CollectorProvider = {
  name: string; label: string; plan: string; collects: string; signup_url: string | null
  needs_key: boolean; key_env: string | null; configured: boolean; plan_daily_limit: number | null
  enabled: boolean; daily_budget: number; used_today: number; errors_today: number; remaining_reported: number | null
  queue: Partial<Record<'pending' | 'done' | 'failed' | 'unavailable', number>>
  paused_until: string | null; reason: string | null; last_at: string | null; last_task: string | null
  recent: { label: string; status: string; items: number | null; error: string | null; done_at: string }[]
}
export type Collector = { enabled: boolean; providers: CollectorProvider[] }

export type PlayerRow = {
  id: number; name: string; team_id: number | null; team: string | null; league: string | null; position: string | null
  apps: number; starts: number; minutes: number; goals: number; assists: number
  impact: number; on_gd90: number | null; off_gd90: number | null; last_played: string; current: boolean
}
export type Squad = {
  team_id: number; team: string; league: string | null; squad: PlayerRow[]
  best_xi: (PlayerRow & { slot: string })[]; best_xi_impact: number; note: string
}

export type NewsArticleRow = {
  id: number; league: string | null; published_at: string; headline: string; summary: string | null; url: string | null
  sentiment: number; injury: boolean
  signals: { positive: string[]; negative: string[]; injury_terms: string[]; manager: boolean; form: boolean; transfer: boolean }
  teams: { id: number; name: string }[]; players: { id: number; name: string }[]
}
export type NewsTeamMood = { team_id: number; team: string; league: string | null; weight: number; sentiment: number | null; injury_stories: number; articles: number }

export type TrainingScore = { n: number; logloss_1x2: number; accuracy_1x2: number; ou25_logloss?: number | null; btts_logloss?: number | null }
export type TrainingLeague = { choice: 'global' | 'league'; global: number | null; league: number | null; n: number }
export type TrainingRun = {
  id: number
  models: string[]
  args: { first_test_season?: number; feature_groups?: Record<string, boolean> }
  status: 'queued' | 'running' | 'finished' | 'failed' | 'stopped'
  device: string | null
  message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  progress: {
    model?: string; stage?: string; message?: string; task?: string
    fold?: number; folds?: number; season?: number; step?: number; steps?: number
    train_loss?: number; val_loss?: number
    curve?: [number, number, number][]
  }
  results: {
    data?: { matches: number; training_rows: number; features: number; upcoming: number }
    ml_ensemble?: { variants: Record<string, TrainingScore> }
  } & Record<string, {
    variants?: Record<string, TrainingScore>
    leagues?: Record<string, TrainingLeague>
    fits?: { stage: string; season: number | null; task: string; steps: number; best_step: number; best_val_loss: number }[]
    live_predictions?: number
    seconds?: number
  } | undefined>
}
export type TrainingInfo = {
  gpu: string | null
  libraries: { xgboost: boolean; torch: boolean }
  models: { name: string; label: string; description: string; saved: boolean }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `${path} → HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

const patch = <T>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', 'X-Requested-By': 'sportsanalyzer' },
    body: JSON.stringify(body),
  })

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Requested-By': 'sportsanalyzer' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const api = {
  health: () => request<Health>('/api/health'),
  providers: () => request<Provider[]>('/api/providers'),
  summary: () => request<Summary>('/api/summary'),
  competitions: () => request<Competition[]>('/api/competitions'),
  matches: (league: string, season: number, limit = 50, offset = 0) =>
    request<{ total: number; items: MatchRow[] }>(
      `/api/matches?league=${league}&season=${season}&limit=${limit}&offset=${offset}`,
    ),
  models: () => request<ModelSummary[]>('/api/models'),
  scraperRuns: () => request<ScrapeRun[]>('/api/scraper/runs'),
  scraperTotals: () => request<ScraperTotals>('/api/scraper/totals'),
  scraperItems: (runId: number | null, type: string, limit = 50) =>
    request<{ total: number; items: ScrapedItemRow[] }>(
      `/api/scraper/items?limit=${limit}${runId ? `&run_id=${runId}` : ''}${type ? `&item_type=${type}` : ''}`,
    ),
  scraperItem: (id: number) => request<{ id: number; type: string; key: string; url: string; data: unknown }>(`/api/scraper/items/${id}`),
  scraperLog: (runId: number) => request<{ lines: string[] }>(`/api/scraper/runs/${runId}/log`),
  startScrape: (body: { spider: string; leagues: string[]; date_from: string; date_to: string; refetch: boolean }) =>
    post<{ id: number }>('/api/scraper/runs', body),
  stopScrape: (id: number) => post(`/api/scraper/runs/${id}/stop`),
  scraperAuto: () => request<{ enabled: boolean; last_action: { at: string; action: string } | null }>('/api/scraper/auto'),
  setScraperAuto: (enabled: boolean) => patch<{ enabled: boolean }>('/api/scraper/auto', { enabled }),
  collector: () => request<Collector>('/api/collector'),
  setCollector: (body: { enabled?: boolean; providers?: Record<string, { enabled?: boolean; daily_budget?: number }> }) =>
    patch<Collector>('/api/collector', body),
  retryCollector: (name: string) => post(`/api/collector/providers/${name}/retry-failed`),
  players: (params: { league?: string; team_id?: number; q?: string; min_minutes?: number; current?: boolean }) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)]))
    return request<{ total: number; players: PlayerRow[]; rated_players: number }>(`/api/players?${qs}`)
  },
  playerTeams: (league?: string) => request<{ team_id: number; team: string; league: string; players: number }[]>(`/api/players/teams${league ? `?league=${league}` : ''}`),
  squad: (teamId: number) => request<Squad>(`/api/players/teams/${teamId}`),
  newsTeams: (league?: string) =>
    request<{ days: number; teams: NewsTeamMood[]; total_articles: number; collecting_since: string | null }>(`/api/news/teams${league ? `?league=${league}` : ''}`),
  newsArticles: (params: { league?: string; team_id?: number; injury?: boolean }) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)]))
    return request<NewsArticleRow[]>(`/api/news/articles?${qs}`)
  },
  trainingInfo: () => request<TrainingInfo>('/api/training/info'),
  trainingRuns: () => request<TrainingRun[]>('/api/training/runs'),
  trainingRun: (id: number) => request<TrainingRun>(`/api/training/runs/${id}`),
  trainingLog: (id: number) => request<{ lines: string[] }>(`/api/training/runs/${id}/log`),
  startTraining: (body: { models: string[]; first_test_season: number; feature_groups: Record<string, boolean> }) => post<{ id: number }>('/api/training/runs', body),
  stopTraining: (id: number) => post(`/api/training/runs/${id}/stop`),
  stakeStatus: () => request<StakeStatus>('/api/stake/status'),
  stakeSettings: (body: { execution_enabled?: boolean; learn_mode?: boolean }) => post('/api/stake/settings', body),
  stakeOutcomes: (q: string, mainMarkets = true) =>
    request<StakeOutcome[]>(`/api/stake/outcomes?q=${encodeURIComponent(q)}&main_markets=${mainMarkets}`),
  stakeOperations: () => request<{ name: string; kind: string; seen: number; last_seen_at: string; is_bet: boolean }[]>('/api/stake/operations'),
  stakeOrders: () => request<StakeOrder[]>('/api/stake/orders'),
  stakeCreateOrder: (outcome_id: string, amount: number) => post<StakeOrder>('/api/stake/orders', { outcome_id, amount }),
  stakeApprove: (id: number) => post(`/api/stake/orders/${id}/approve`),
  stakeReject: (id: number) => post(`/api/stake/orders/${id}/reject`),
  strategies: () => request<StrategyRow[]>('/api/strategies'),
  exposure: () => request<Exposure>('/api/stake/exposure'),
  stakeBets: () => request<StakeBetRow[]>('/api/stake/bets'),
  cashout: (id: string) => post(`/api/stake/bets/${encodeURIComponent(id)}/cashout`),
  updateStrategy: (id: number, body: Partial<StrategyRow> & { resume?: boolean; confirm_real_money?: boolean }) =>
    patch<StrategyRow>(`/api/strategies/${id}`, body),
  runStrategies: () => post('/api/strategies/run'),
  ledger: (status = '') => request<LedgerBet[]>(`/api/strategies/bets?limit=200${status ? `&status=${status}` : ''}`),
  automation: () => request<Automation>('/api/strategies/automation'),
  identityReview: () => request<IdentityReview>('/api/identity/review'),
  resolveMapping: (id: number, teamId: number) => post(`/api/identity/${id}/resolve`, { team_id: teamId }),
  rejectMapping: (id: number) => post(`/api/identity/${id}/reject`),
}

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
  model: 'elo' | 'dixon_coles' | 'blend'
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `${path} → HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  identityReview: () => request<IdentityReview>('/api/identity/review'),
  resolveMapping: (id: number, teamId: number) => post(`/api/identity/${id}/resolve`, { team_id: teamId }),
  rejectMapping: (id: number) => post(`/api/identity/${id}/reject`),
}

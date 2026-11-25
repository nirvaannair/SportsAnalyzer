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
  identityReview: () => request<IdentityReview>('/api/identity/review'),
  resolveMapping: (id: number, teamId: number) => post(`/api/identity/${id}/resolve`, { team_id: teamId }),
  rejectMapping: (id: number) => post(`/api/identity/${id}/reject`),
}

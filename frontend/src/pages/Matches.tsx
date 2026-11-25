import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Card, CardHeader, PageHeader } from '../components/ui'
import { api, type MatchRow } from '../lib/api'

const PAGE = 50

function Select({ value, onChange, children }: {
  value: string | number
  onChange: (value: string) => void
  children: React.ReactNode
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:focus:border-zinc-600"
    >
      {children}
    </select>
  )
}

/** Implied probability with the bookmaker margin removed (proportional method). */
function fairProbabilities(o: NonNullable<MatchRow['odds_1x2']>) {
  const raw = [1 / o.home, 1 / o.draw, 1 / o.away]
  const total = raw.reduce((a, b) => a + b, 0)
  return { probs: raw.map((p) => p / total), margin: total - 1 }
}

function OddsCell({ m }: { m: MatchRow }) {
  const o = m.odds_1x2
  if (!o) return <span className="text-zinc-400">—</span>
  const { probs } = fairProbabilities(o)
  const result = outcomeOf(m)
  return (
    <div className="tabular flex justify-end gap-1">
      {[o.home, o.draw, o.away].map((price, i) => (
        <span
          key={i}
          title={`${Math.round(probs[i] * 100)}% fair probability`}
          className={`w-12 rounded-md px-1.5 py-0.5 text-center ${
            i === result
              ? 'bg-emerald-50 font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
              : 'text-zinc-600 dark:text-zinc-400'
          }`}
        >
          {price.toFixed(2)}
        </span>
      ))}
    </div>
  )
}

function outcomeOf(m: MatchRow) {
  if (m.home_goals == null || m.away_goals == null) return -1
  return m.home_goals > m.away_goals ? 0 : m.home_goals === m.away_goals ? 1 : 2
}

/** Model probabilities. An outcome is flagged when the shown price pays more than the model's fair odds (edge > 5%). */
function ModelCell({ m }: { m: MatchRow }) {
  const p = m.prediction
  if (!p) return <span className="text-zinc-400">—</span>
  const probs = [p.p_home, p.p_draw, p.p_away]
  const prices = m.odds_1x2 ? [m.odds_1x2.home, m.odds_1x2.draw, m.odds_1x2.away] : null
  const top = probs.indexOf(Math.max(...probs))
  return (
    <div className="tabular flex justify-end gap-1">
      {probs.map((prob, i) => {
        const edge = prices ? prob * prices[i] - 1 : null
        const value = edge !== null && edge > 0.05
        return (
          <span
            key={i}
            title={`Model: ${(prob * 100).toFixed(1)}% · fair odds ${(1 / prob).toFixed(2)}${
              edge !== null ? ` · edge at shown price ${(edge * 100).toFixed(1)}%` : ''
            }`}
            className={`relative w-11 rounded-md px-1 py-0.5 text-center ${
              i === top ? 'font-semibold text-zinc-900 dark:text-zinc-50' : 'text-zinc-500 dark:text-zinc-400'
            }`}
          >
            {Math.round(prob * 100)}%
            {value && <span className="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-amber-500" />}
          </span>
        )
      })}
    </div>
  )
}

function GoalsCell({ m }: { m: MatchRow }) {
  const p = m.prediction
  if (!p || p.p_over25 == null || p.p_btts == null) return <span className="text-zinc-400">—</span>
  const total = (m.home_goals ?? 0) + (m.away_goals ?? 0)
  const done = m.status === 'finished'
  const hit = (yes: boolean) => (done ? (yes ? 'text-emerald-600 dark:text-emerald-400' : '') : '')
  return (
    <div className="tabular flex justify-end gap-3 whitespace-nowrap text-xs text-zinc-500 dark:text-zinc-400"
         title={`Expected goals ${p.exp_home_goals?.toFixed(2)} – ${p.exp_away_goals?.toFixed(2)}`}>
      <span className={hit(total >= 3)}>O2.5 {Math.round(p.p_over25 * 100)}%</span>
      <span className={hit((m.home_goals ?? 0) > 0 && (m.away_goals ?? 0) > 0)}>BTTS {Math.round(p.p_btts * 100)}%</span>
    </div>
  )
}

export default function Matches() {
  const competitions = useQuery({ queryKey: ['competitions'], queryFn: api.competitions })
  const [league, setLeague] = useState('ENG1')
  const [season, setSeason] = useState<number | null>(null)
  const [page, setPage] = useState(0)

  const seasons = competitions.data?.find((c) => c.code === league)?.seasons ?? []
  const activeSeason = season ?? seasons[0]?.start_year ?? null

  useEffect(() => setPage(0), [league, activeSeason])

  const matches = useQuery({
    queryKey: ['matches', league, activeSeason, page],
    queryFn: () => api.matches(league, activeSeason!, PAGE, page * PAGE),
    enabled: activeSeason !== null,
    placeholderData: keepPreviousData,
  })

  const total = matches.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE))

  return (
    <>
      <PageHeader
        title="Matches"
        description="Model predictions (made before each match, from football data only) next to the bookmakers' prices."
        actions={
          <div className="flex gap-2">
            <Select value={league} onChange={(v) => { setLeague(v); setSeason(null) }}>
              {(competitions.data ?? []).map((c) => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </Select>
            <Select value={activeSeason ?? ''} onChange={(v) => setSeason(Number(v))}>
              {seasons.map((s) => (
                <option key={s.start_year} value={s.start_year}>{s.label}</option>
              ))}
            </Select>
          </div>
        }
      />

      <Card>
        <CardHeader
          title={`${total.toLocaleString('en-IN')} matches`}
          aside={
            <span className="flex items-center gap-1.5 text-xs text-zinc-500">
              <span className="size-1.5 rounded-full bg-amber-500" /> price beats model's fair odds by 5%+ (not a bet signal yet)
            </span>
          }
        />
        <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              <th className="px-5 py-2.5 font-medium">Date</th>
              <th className="px-5 py-2.5 text-right font-medium">Home</th>
              <th className="px-2 py-2.5 text-center font-medium">Score</th>
              <th className="px-5 py-2.5 font-medium">Away</th>
              <th className="px-3 py-2.5 text-right font-medium">Model H · D · A</th>
              <th className="px-3 py-2.5 text-right font-medium">Goals</th>
              <th className="px-5 py-2.5 text-right font-medium">Odds H · D · A</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {(matches.data?.items ?? []).map((m) => (
              <tr key={m.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
                <td className="tabular whitespace-nowrap px-5 py-2.5 text-zinc-500 dark:text-zinc-400">
                  {new Date(m.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                </td>
                <td className="px-5 py-2.5 text-right font-medium">{m.home}</td>
                <td className="tabular px-2 py-2.5 text-center">
                  {m.status === 'finished' ? (
                    <span className="rounded-md bg-zinc-100 px-2 py-0.5 font-semibold dark:bg-zinc-800">
                      {m.home_goals} – {m.away_goals}
                    </span>
                  ) : (
                    <Badge>Upcoming</Badge>
                  )}
                </td>
                <td className="px-5 py-2.5 font-medium">{m.away}</td>
                <td className="px-3 py-2.5"><ModelCell m={m} /></td>
                <td className="px-3 py-2.5"><GoalsCell m={m} /></td>
                <td className="px-5 py-2.5"><OddsCell m={m} /></td>
              </tr>
            ))}
            {(matches.isLoading || competitions.isLoading) && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-zinc-500">Loading…</td></tr>
            )}
            {!matches.isLoading && total === 0 && activeSeason !== null && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-zinc-500">No matches imported for this season.</td></tr>
            )}
          </tbody>
        </table>
        </div>
        {pages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-100 px-5 py-3 text-sm dark:border-zinc-800">
            <span className="text-zinc-500 dark:text-zinc-400">Page {page + 1} of {pages}</span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded-md p-1.5 hover:bg-zinc-100 disabled:opacity-30 dark:hover:bg-zinc-800"
                aria-label="Previous page"
              >
                <ChevronLeft className="size-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                disabled={page >= pages - 1}
                className="rounded-md p-1.5 hover:bg-zinc-100 disabled:opacity-30 dark:hover:bg-zinc-800"
                aria-label="Next page"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
          </div>
        )}
      </Card>
    </>
  )
}

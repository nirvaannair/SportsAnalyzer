import { useQuery } from '@tanstack/react-query'
import { Search, Users } from 'lucide-react'
import { useState } from 'react'
import { Guide } from '../components/Guide'
import { Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api, type PlayerRow } from '../lib/api'
import { leagues, setting } from '../lib/settings'

const POSITION: Record<string, string> = { GK: 'Goalkeeper', DEF: 'Defender', MID: 'Midfielder', FWD: 'Forward' }
const control = 'rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900'

function Impact({ value }: { value: number }) {
  const cut = setting<number>('players.impact_highlight')
  const tone = value > cut ? 'text-emerald-600 dark:text-emerald-400' : value < -cut ? 'text-rose-600 dark:text-rose-400' : ''
  return <span className={`tabular font-medium ${tone}`}>{value > 0 ? '+' : ''}{value.toFixed(2)}</span>
}

function PlayerTable({ rows, onTeam }: { rows: PlayerRow[]; onTeam?: (id: number) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            <th className="px-5 py-2 font-medium">Player</th>
            <th className="px-3 py-2 font-medium">Team</th>
            <th className="px-3 py-2 text-right font-medium">Minutes</th>
            <th className="px-3 py-2 text-right font-medium">Goals</th>
            <th className="px-3 py-2 text-right font-medium">Assists</th>
            <th className="px-3 py-2 text-right font-medium" title="Team goal difference per 90 with him on / off the pitch">On / off GD per 90</th>
            <th className="px-5 py-2 text-right font-medium" title="With-minus-without, shrunk towards 0 until there are enough minutes">Impact</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rows.map((p) => (
            <tr key={p.id}>
              <td className="px-5 py-2">
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                  {p.position ? POSITION[p.position] : '—'} · {p.starts}/{p.apps} starts{!p.current && ` · last played ${p.last_played}`}
                </div>
              </td>
              <td className="px-3 py-2">
                {p.team_id && onTeam ? (
                  <button onClick={() => onTeam(p.team_id!)} className="text-left hover:underline">{p.team}</button>
                ) : p.team}
              </td>
              <td className="tabular px-3 py-2 text-right">{p.minutes.toLocaleString('en-IN')}</td>
              <td className="tabular px-3 py-2 text-right">{p.goals}</td>
              <td className="tabular px-3 py-2 text-right">{p.assists}</td>
              <td className="tabular px-3 py-2 text-right text-zinc-500 dark:text-zinc-400">
                {p.on_gd90 === null ? '—' : p.on_gd90.toFixed(2)} / {p.off_gd90 === null ? '—' : p.off_gd90.toFixed(2)}
              </td>
              <td className="px-5 py-2 text-right"><Impact value={p.impact} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TeamView({ teamId, onBack }: { teamId: number; onBack: () => void }) {
  const squad = useQuery({ queryKey: ['squad', teamId], queryFn: () => api.squad(teamId) })
  const s = squad.data
  if (!s) return <Card><p className="px-5 py-6 text-sm text-zinc-500">{squad.isError ? (squad.error as Error).message : 'Loading…'}</p></Card>
  const groups = ['FWD', 'MID', 'DEF', 'GK']
  return (
    <>
      <button onClick={onBack} className="mb-4 text-sm text-zinc-500 hover:underline">← All players</button>
      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title={`Best XI · ${s.team}`} aside={<span className="text-xs text-zinc-500">XI impact <Impact value={s.best_xi_impact} /></span>} />
          <div className="space-y-3 bg-emerald-950/5 px-5 py-4 dark:bg-emerald-400/5">
            {groups.map((g) => (
              <div key={g} className="flex flex-wrap justify-center gap-2">
                {s.best_xi.filter((p) => p.slot === g).map((p) => (
                  <div key={p.id} className="w-28 rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-center dark:border-zinc-700 dark:bg-zinc-900">
                    <div className="truncate text-xs font-medium" title={p.name}>{p.name}</div>
                    <div className="text-[11px]"><Impact value={p.impact} /></div>
                  </div>
                ))}
              </div>
            ))}
            {s.best_xi.length < 11 && <p className="text-center text-xs text-zinc-500">Not enough rated players yet for a full XI.</p>}
          </div>
          <p className="px-5 py-3 text-xs text-zinc-500 dark:text-zinc-400">{s.note}</p>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title="Squad" aside={<span className="text-xs text-zinc-500">{s.squad.length} players with data</span>} />
          <PlayerTable rows={s.squad} />
        </Card>
      </div>
    </>
  )
}

export default function Players() {
  const [league, setLeague] = useState('')
  const [q, setQ] = useState('')
  const [team, setTeam] = useState<number | null>(null)
  const [current, setCurrent] = useState(true)
  const players = useQuery({ queryKey: ['players', league, q, current], queryFn: () => api.players({ league, q, current }) })
  const lineups = useQuery({ queryKey: ['scraper', 'totals'], queryFn: api.scraperTotals })
  const n = lineups.data?.matches_with_lineups ?? 0

  return (
    <>
      <PageHeader title="Players" description="How much each player changes his team: goal difference with him on the pitch versus off it." />
      <Guide items={[
        {
          title: 'Impact (with / without)',
          body: 'Team goal difference per 90 minutes with the player on the pitch, minus with him off it. +0.30 means the team is 0.3 goals a game better with him. Ratings start at 0 and only move with enough minutes, so one lucky game does not make a star.',
          verdict: 'info',
        },
        {
          title: 'On / off GD per 90',
          body: 'The two raw numbers behind impact: the team\'s goal difference per 90 minutes while he plays, and while he doesn\'t.',
          verdict: 'info',
        },
        {
          title: 'Best XI',
          body: `Click a team. The best XI is the highest-impact players per position (${Object.entries(setting<Record<string, number>>('players.formation')).map(([g, n]) => `${n} ${g}`).join(', ')}) among those with at least ${setting<number>('players.min_minutes_for_xi')} minutes.`,
          verdict: 'info',
        },
        {
          title: 'How much player data is there?',
          body: `${n.toLocaleString('en-IN')} matches have lineups so far (the history goes back to ${setting<string>('scraper.history_start').slice(0, 4)}). Ratings get more reliable as the scraper fills this in; they feed the models as "starting XI strength" and "regulars missing".`,
          verdict: n > setting<number>('verdicts.lineups_enough') ? 'good' : n > setting<number>('verdicts.lineups_some') ? 'medium' : 'bad',
          verdictLabel: n > setting<number>('verdicts.lineups_enough') ? 'Enough' : 'Still filling',
        },
      ]} />

      {team !== null ? <TeamView teamId={team} onBack={() => setTeam(null)} /> : (
        <Card>
          <div className="flex flex-wrap items-center gap-2 border-b border-zinc-100 px-5 py-3 dark:border-zinc-800">
            <select value={league} onChange={(e) => setLeague(e.target.value)} className={control} aria-label="League">
              <option value="">All leagues</option>
              {leagues().map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
            </select>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-zinc-400" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search player" className={`${control} pl-8`} />
            </div>
            <label className="flex items-center gap-1.5 text-sm text-zinc-600 dark:text-zinc-400">
              <input type="checkbox" checked={current} onChange={(e) => setCurrent(e.target.checked)} className="accent-zinc-900 dark:accent-zinc-100" />
              Current players only
            </label>
            <span className="ml-auto text-xs text-zinc-500">
              {players.data ? `${players.data.total.toLocaleString('en-IN')} players with ${setting<number>('players.list_min_minutes')}+ minutes · sorted by impact` : '…'}
            </span>
          </div>
          {players.isLoading ? (
            <p className="px-5 py-10 text-center text-sm text-zinc-500">Calculating player ratings from every lineup… the first load takes about 20 seconds.</p>
          ) : players.isError ? (
            <p className="px-5 py-10 text-center text-sm text-rose-600">{(players.error as Error).message}</p>
          ) : players.data && players.data.players.length === 0 ? (
            <EmptyState icon={<Users className="size-6" />} title="No rated players yet"
                        body="Player ratings appear as the scraper loads lineups. Check the Scraper page." />
          ) : (
            <PlayerTable rows={players.data?.players ?? []} onTeam={setTeam} />
          )}
        </Card>
      )}
    </>
  )
}

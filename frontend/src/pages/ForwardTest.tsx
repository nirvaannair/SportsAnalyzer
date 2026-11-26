import { useQuery } from '@tanstack/react-query'
import { FlaskConical } from 'lucide-react'
import { useState } from 'react'
import { Guide, VerdictBadge } from '../components/Guide'
import LineChart from '../components/LineChart'
import { Badge, Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api, type ForwardModel } from '../lib/api'
import { leagueName, refresh, setting } from '../lib/settings'

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`)
const num = (v: number | null | undefined, d = 4) => (v === null || v === undefined ? '—' : v.toFixed(d))

function Calibration({ data }: { data: ForwardModel['calibration'] }) {
  if (data.length === 0) return <p className="py-6 text-center text-sm text-zinc-500">Appears once matches are settled.</p>
  const size = 220
  const pad = 28
  const s = (v: number) => pad + v * (size - pad * 1.5)
  const y = (v: number) => size - s(v) + pad / 2
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[260px]" role="img" aria-label="Predicted vs observed">
      <line x1={s(0)} y1={y(0)} x2={s(1)} y2={y(1)} strokeDasharray="3 3" className="stroke-zinc-300 dark:stroke-zinc-600" />
      {[0, 0.5, 1].map((t) => <text key={t} x={pad - 4} y={y(t) + 3} textAnchor="end" className="fill-zinc-400 text-[9px]">{t * 100}%</text>)}
      <polyline fill="none" strokeWidth={2} className="stroke-emerald-500" points={data.map((d) => `${s(d.predicted)},${y(d.observed)}`).join(' ')} />
      {data.map((d) => <circle key={d.bucket} cx={s(d.predicted)} cy={y(d.observed)} r={3} className="fill-emerald-500" />)}
    </svg>
  )
}

export default function ForwardTest() {
  const summary = useQuery({ queryKey: ['forward', 'summary'], queryFn: api.forwardSummary, refetchInterval: refresh('minute') })
  const models = summary.data?.models ?? []
  const [chosen, setChosen] = useState<string | null>(null)
  const current = models.find((m) => m.model === (chosen ?? setting<string>('strategies.default_model'))) ?? models[0]
  const [tab, setTab] = useState<'open' | 'settled'>('open')
  const list = useQuery({
    queryKey: ['forward', 'list', current?.model, tab],
    queryFn: () => api.forwardPredictions(current!.model, tab),
    enabled: Boolean(current),
    refetchInterval: refresh('minute'),
  })
  const settledTotal = models.reduce((t, m) => Math.max(t, m.settled), 0)
  const minMatches = summary.data?.calibration_min_matches ?? 0

  return (
    <>
      <PageHeader title="Forward test" description="Mock bets on every upcoming match, inside the app only (never sent to Stake). After each match we see who was right and the models learn from their misses." />
      <Guide items={[
        { title: 'What a mock bet is', body: 'Before every match, each model\'s prediction is frozen and a pretend 1-unit bet is recorded: the outcome it thinks most likely ("favourite"), plus "value" picks where its probability beats the pre-match price. No money, no Stake: just a record to learn from.', verdict: 'info' },
        { title: 'Why this matters', body: 'Backtests replay the past; this tests the models on matches that had not happened yet when they predicted them. It is the most honest score we have.', verdict: settledTotal > minMatches ? 'good' : 'medium', verdictLabel: settledTotal > minMatches ? 'Enough results' : `${settledTotal} settled so far` },
        { title: 'Log loss and hit rate', body: 'Same scores as the Models page: lower log loss is better; hit rate is how often the favourite won.', verdict: 'info' },
        { title: 'How the models learn from this', body: `After every settled match, each model gets a correction (a "temperature"): above 1 means it was over-confident and its probabilities are softened, below 1 means it was too timid. It switches on after ${minMatches} settled matches so a few results can't swing it.`, verdict: 'info' },
        { title: 'Mock profit', body: 'Profit in units at the pre-match price (Stake\'s price when the helper captured it). It needs a price, so it can lag behind the accuracy numbers.', verdict: 'info' },
      ]} />

      {models.length === 0 ? (
        <Card><EmptyState icon={<FlaskConical className="size-6" />} title="No forward predictions yet" body="They start with the next automation cycle (every few minutes)." /></Card>
      ) : (
        <>
          <Card>
            <CardHeader title="Models on matches that hadn't happened yet" aside={<span className="text-xs text-zinc-500">since {summary.data?.first_prediction}</span>} />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    <th className="px-5 py-2 font-medium">Model</th>
                    <th className="px-3 py-2 text-right font-medium">Upcoming</th>
                    <th className="px-3 py-2 text-right font-medium">Settled</th>
                    <th className="px-3 py-2 text-right font-medium">Log loss</th>
                    <th className="px-3 py-2 text-right font-medium">Hit rate</th>
                    <th className="px-3 py-2 text-right font-medium">Favourite ROI</th>
                    <th className="px-3 py-2 text-right font-medium">Value ROI</th>
                    <th className="px-5 py-2 text-right font-medium">Correction</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {models.map((m) => (
                    <tr key={m.model} onClick={() => setChosen(m.model)}
                        className={`cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/40 ${m.model === current?.model ? 'bg-zinc-50 dark:bg-zinc-800/40' : ''}`}>
                      <td className="px-5 py-2 font-medium">{m.model}</td>
                      <td className="tabular px-3 py-2 text-right">{m.open}</td>
                      <td className="tabular px-3 py-2 text-right">{m.settled}</td>
                      <td className="tabular px-3 py-2 text-right">{num(m.logloss)}</td>
                      <td className="tabular px-3 py-2 text-right">{pct(m.accuracy)}</td>
                      <td className="tabular px-3 py-2 text-right">{pct(m.rules.favourite?.roi)}</td>
                      <td className="tabular px-3 py-2 text-right">{pct(m.rules.value?.roi)}</td>
                      <td className="px-5 py-2 text-right">
                        {m.correction ? <VerdictBadge verdict={m.correction.active ? 'good' : 'info'} label={`T ${m.correction.temperature.toFixed(2)}${m.correction.active ? ' · on' : ` · ${m.correction.n}/${minMatches}`}`} /> : <Badge>learning</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {current && (
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader title={`Mock profit · ${current.model}`} aside={<span className="text-xs text-zinc-500">units, 1 per bet</span>} />
                <div className="px-5 py-4">
                  <LineChart zeroLine format={(v) => v.toFixed(1)} series={Object.entries(current.rules).map(([rule, r], i) => ({
                    name: `${rule} (${r.priced} priced bets)`, className: i === 0 ? 'stroke-emerald-500' : 'stroke-sky-500',
                    points: r.cumulative.map((p) => ({ x: p.t, y: p.profit })),
                  }))} />
                </div>
              </Card>
              <Card>
                <CardHeader title={`Rolling scores · last ${setting<number>('forward.rolling_window')} matches`} />
                <div className="px-5 py-4">
                  <LineChart series={[
                    { name: 'Log loss (lower = better)', className: 'stroke-rose-500', points: current.rolling.map((p) => ({ x: p.t, y: p.logloss })) },
                    { name: 'Hit rate', className: 'stroke-emerald-500', points: current.rolling.map((p) => ({ x: p.t, y: p.accuracy })) },
                  ]} />
                </div>
              </Card>
              <Card>
                <CardHeader title="Calibration on real future matches" aside={<span className="text-xs text-zinc-500">dashed = honest</span>} />
                <div className="flex flex-wrap items-center gap-6 px-5 py-4">
                  <Calibration data={current.calibration} />
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">
                    {current.correction ? (
                      <>Learned correction T = <b>{current.correction.temperature.toFixed(3)}</b> from {current.correction.n} matches:
                        log loss {num(current.correction.logloss_before)} → {num(current.correction.logloss_after)}.
                        {current.correction.active ? ' Applied to this model\'s live predictions.' : ` Applied after ${minMatches} matches.`}</>
                    ) : 'The correction is fitted once matches are settled.'}
                  </div>
                </div>
              </Card>
              <Card>
                <CardHeader title="By league (settled)" />
                <table className="w-full text-sm">
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                    {current.by_league.map((l) => (
                      <tr key={l.league}>
                        <td className="px-5 py-2">{leagueName(l.league)}</td>
                        <td className="tabular px-3 py-2 text-right">{l.n}</td>
                        <td className="tabular px-3 py-2 text-right">{num(l.logloss)}</td>
                        <td className="tabular px-5 py-2 text-right">{pct(l.accuracy)}</td>
                      </tr>
                    ))}
                    {current.by_league.length === 0 && <tr><td className="px-5 py-6 text-center text-zinc-500">Appears once matches are settled.</td></tr>}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          {current && (
            <Card className="mt-6">
              <CardHeader title={`${current.model}: predictions`} aside={
                <div className="flex gap-1">
                  {(['open', 'settled'] as const).map((t) => (
                    <button key={t} onClick={() => setTab(t)} className={`rounded-md px-2 py-1 text-xs ${tab === t ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900' : 'text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`}>
                      {t === 'open' ? 'Upcoming' : 'Settled'}
                    </button>
                  ))}
                </div>
              } />
              <div className="max-h-[520px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white dark:bg-zinc-900">
                    <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                      <th className="px-5 py-2 font-medium">Match</th>
                      <th className="px-3 py-2 text-right font-medium">Home</th>
                      <th className="px-3 py-2 text-right font-medium">Draw</th>
                      <th className="px-3 py-2 text-right font-medium">Away</th>
                      <th className="px-3 py-2 font-medium">Mock bets</th>
                      <th className="px-5 py-2 text-right font-medium">{tab === 'open' ? 'Kick-off' : 'Result'}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                    {(list.data ?? []).map((p) => (
                      <tr key={p.id}>
                        <td className="px-5 py-2"><div className="font-medium">{p.home} – {p.away}</div><div className="text-xs text-zinc-500">{leagueName(p.league)}</div></td>
                        {(['home', 'draw', 'away'] as const).map((o) => (
                          <td key={o} className={`tabular px-3 py-2 text-right ${p.outcome === o ? 'font-semibold text-emerald-600 dark:text-emerald-400' : ''}`}>{pct(p[`p_${o}`])}</td>
                        ))}
                        <td className="px-3 py-2 text-xs">
                          {p.bets.map((b) => (
                            <span key={`${b.rule}${b.market}${b.selection}`} className="mr-1 inline-flex items-center gap-1">
                              <Badge tone={b.status === 'won' ? 'accent' : b.status === 'lost' ? 'warn' : 'neutral'}>{b.rule}: {b.selection}{b.price ? ` @ ${b.price.toFixed(2)}` : ''}</Badge>
                            </span>
                          ))}
                        </td>
                        <td className="tabular px-5 py-2 text-right text-xs">{tab === 'open' ? new Date(p.kickoff_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : p.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </>
  )
}

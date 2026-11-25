import { useQuery } from '@tanstack/react-query'
import InPlay from '../components/InPlay'
import StrategyControls from '../components/StrategyControls'
import { Badge, Card, CardHeader, PageHeader, Stat, StatusDot } from '../components/ui'
import { api } from '../lib/api'

const ROADMAP = [
  { phase: 0, title: 'Foundations', detail: 'Project setup, Docker Postgres, tests, API and dashboard', done: true },
  { phase: 1, title: 'Data', detail: 'Results, stats and fixtures for 10 leagues; team identity matching; ESPN scraper', done: true },
  { phase: 2, title: 'Players & news', detail: 'Player pages, impact with/without, best XI, injuries' },
  { phase: 3, title: 'Models', detail: 'Elo + Dixon-Coles done; GPU-trained ML models next' },
  { phase: 4, title: 'Strategies', detail: 'Staking, compounding, value bands, multis, ledger', done: true },
  { phase: 5, title: 'Dashboard', detail: 'Every page filled with live data' },
  { phase: 6, title: 'Stake', detail: 'Helper connected; ₹1 bets, own-bets tracking, approval above limit', done: true },
]

const rs = (v: number, digits = 2) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: digits })}`

function ago(iso?: string | null) {
  if (!iso) return 'never'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${Math.round(s)} s ago`
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} d ago`
}

function until(iso?: string | null) {
  if (!iso) return '—'
  const m = Math.round((new Date(iso).getTime() - Date.now()) / 60000)
  return m <= 0 ? 'now' : `in ${m} min`
}

type Tone = 'ok' | 'warn' | 'off' | 'bad'

export default function Overview() {
  const providers = useQuery({ queryKey: ['providers'], queryFn: api.providers })
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary })
  const strategies = useQuery({ queryKey: ['strategies'], queryFn: api.strategies, refetchInterval: 10000 })
  const stake = useQuery({ queryKey: ['stake', 'status'], queryFn: api.stakeStatus, refetchInterval: 5000 })
  const exposure = useQuery({ queryKey: ['exposure'], queryFn: api.exposure, refetchInterval: 15000 })
  const automation = useQuery({ queryKey: ['automation'], queryFn: api.automation, refetchInterval: 30000 })
  const scrapes = useQuery({ queryKey: ['scraper', 'runs'], queryFn: api.scraperRuns, refetchInterval: 30000 })

  const all = strategies.data ?? []
  const live = all.filter((x) => x.enabled)
  const realModes = live.filter((x) => x.mode !== 'paper')
  const pnl = all.reduce((t, x) => t + x.bankroll.profit, 0)
  const n = (v: number | undefined) => (v === undefined ? '…' : v.toLocaleString('en-IN'))
  const configured = providers.data?.filter((p) => p.configured).length ?? 0
  const observations = providers.data?.reduce((sum, p) => sum + p.observations, 0) ?? 0

  const st = stake.data
  const helper = st?.helper
  const currency = st?.limits.currency ?? 'inr'
  const balance = helper?.balances?.available?.[currency]
  const real = exposure.data?.real
  const auto = automation.data
  const lastRun = scrapes.data?.[0]
  const running = scrapes.data?.find((r) => r.status === 'running' || r.status === 'loading')

  const badge = !st ? null
    : st.execution_enabled && realModes.length ? <Badge tone="warn">Real betting on · {realModes.length} strategies</Badge>
    : st.execution_enabled ? <Badge tone="accent">Execution on · no real strategy</Badge>
    : <Badge>Real betting off</Badge>

  const system: [string, Tone, string][] = [
    ['Stake helper', helper?.connected ? 'ok' : 'bad',
      helper?.connected ? `Connected · v${helper.version ?? '?'}` : `Offline · last seen ${ago(helper?.last_seen)}`],
    ['Real-money execution', st?.execution_enabled ? 'warn' : 'off',
      st ? (st.execution_enabled ? 'On' : 'Off · nothing is sent') : '…'],
    ['Requests learned', st?.bet_request_learned && st?.multi_request_learned && st?.bet_list_learned ? 'ok' : 'warn',
      st ? `Single ${st.bet_request_learned ? '✓' : '✗'} · Multi ${st.multi_request_learned ? '✓' : '✗'} · My Bets ${st.bet_list_learned ? '✓' : '✗'}` : '…'],
    ['Automation', auto?.last_error ? 'bad' : auto?.last_cycle ? 'ok' : 'off',
      auto?.last_cycle ? `Ran ${ago(auto.last_cycle.at)} · next ${until(auto.next_cycle_at)}` : 'Not run yet'],
    ['Predictions', auto?.last_refresh ? 'ok' : 'off',
      auto?.last_refresh ? `${auto.last_refresh.predicted.blend ?? 0} matches · ${ago(auto.last_refresh.at)}` : 'Not run yet'],
    ['Scraper', running ? 'ok' : lastRun?.status === 'failed' ? 'bad' : 'off',
      running ? `Run #${running.id} · ${(running.stats.items ?? 0).toLocaleString('en-IN')} items`
        : lastRun ? `Run #${lastRun.id} ${lastRun.status}` : 'No runs yet'],
  ]

  return (
    <>
      <PageHeader title="Overview" description="Your money on Stake, your strategies and the system at a glance." actions={badge} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Stake balance" value={balance === undefined ? '—' : rs(balance)}
          hint={helper?.connected ? `Live from your Stake tab · ${ago(helper.last_seen)}` : `Last known · helper offline since ${ago(helper?.last_seen)}`} />
        <Stat label="On Stake now" value={real ? rs(real.stake) : '…'}
          hint={real ? `${real.bets} open bets · pays ${rs(real.potential_payout)} if all win` : undefined} />
        <Stat label="Sent by the system today" value={st ? `${st.bets_today} / ${st.limits.max_bets_per_day}` : '…'}
          hint={st ? `${rs(st.budget_left, 0)} of ${rs(st.limits.budget, 0)} test budget left · max ${rs(st.limits.max_bet, 0)} a bet` : undefined} />
        <Stat label="Strategies on" value={strategies.data ? `${live.length} / ${all.length}` : '…'}
          hint={live.length ? `${realModes.length} real · ${live.length - realModes.length} paper · P&L ${pnl >= 0 ? '+' : ''}${rs(pnl)}` : 'None switched on yet'} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <InPlay />
          <StrategyControls />
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="System" />
            <ul className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
              {system.map(([label, tone, value]) => (
                <li key={label} className="flex items-start gap-3 px-5 py-2.5">
                  <span className="pt-1.5"><StatusDot tone={tone} /></span>
                  <div className="min-w-0">
                    <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
                    <div className="font-medium">{value}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Data" />
            <dl className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
              {[
                ['Matches', n(summary.data?.matches)],
                ['Odds quotes (price only)', n(summary.data?.odds_quotes)],
                ['Teams', n(summary.data?.teams)],
                ['Seasons covered', summary.data?.first_match ? `${summary.data.first_match.slice(0, 4)} – ${summary.data.last_match?.slice(0, 4)}` : '…'],
                ['Providers with keys', providers.isLoading ? '…' : `${configured} / ${providers.data?.length ?? 0}`],
                ['Raw observations', providers.isLoading ? '…' : observations.toLocaleString('en-IN')],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between px-5 py-3">
                  <dt className="text-zinc-500 dark:text-zinc-400">{label}</dt>
                  <dd className="tabular font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader title="Build progress" />
        <ol className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {ROADMAP.map((step) => (
            <li key={step.phase} className="flex items-center gap-4 px-5 py-3 text-sm">
              <StatusDot tone={step.done ? 'ok' : 'off'} />
              <span className="tabular w-6 text-zinc-400">P{step.phase}</span>
              <span className="w-48 font-medium">{step.title}</span>
              <span className="text-zinc-500 dark:text-zinc-400">{step.detail}</span>
            </li>
          ))}
        </ol>
      </Card>
    </>
  )
}

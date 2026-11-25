import { useQuery } from '@tanstack/react-query'
import { LineChart } from 'lucide-react'
import { Badge, Card, CardHeader, EmptyState, PageHeader, Stat, StatusDot } from '../components/ui'
import { api } from '../lib/api'

const ROADMAP = [
  { phase: 0, title: 'Foundations', detail: 'Project setup, Docker Postgres, tests, API and dashboard shell', done: true },
  { phase: 1, title: 'Data', detail: 'Canonical teams and matches, identity matching, more providers, backfill planner', done: true },
  { phase: 2, title: 'News', detail: 'Injury scrapers and player importance' },
  { phase: 3, title: 'Models', detail: 'Ratings, Dixon-Coles, LightGBM, backtesting' },
  { phase: 4, title: 'Strategy + paper trading', detail: 'Staking, compounding, risk limits, bet ledger' },
  { phase: 5, title: 'Dashboard', detail: 'Every page filled with live data' },
  { phase: 6, title: 'Stake', detail: 'Read-only, then approve mode, then auto' },
]

export default function Overview() {
  const providers = useQuery({ queryKey: ['providers'], queryFn: api.providers })
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary })
  const n = (v: number | undefined) => (v === undefined ? '…' : v.toLocaleString('en-IN'))
  const configured = providers.data?.filter((p) => p.configured).length ?? 0
  const observations = providers.data?.reduce((sum, p) => sum + p.observations, 0) ?? 0

  return (
    <>
      <PageHeader
        title="Overview"
        description="Bankroll, performance and system state at a glance."
        actions={<Badge tone="accent">Paper mode</Badge>}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Bankroll" value="₹0" hint="No strategies yet" />
        <Stat label="P&L · 30d" value="—" hint="No settled bets" />
        <Stat label="Yield" value="—" hint="Profit ÷ total staked" />
        <Stat label="Closing line value" value="—" hint="Avg. odds taken vs close" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Bankroll" aside={<span className="text-xs text-zinc-500">INR</span>} />
          <EmptyState
            icon={<LineChart className="size-6" />}
            title="No bankroll history yet"
            body="Once paper trading starts in Phase 4, the bankroll curve for every strategy appears here."
          />
        </Card>

        <Card>
          <CardHeader title="Data" />
          <dl className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
            {[
              ['Matches', n(summary.data?.matches)],
              ['Odds quotes', n(summary.data?.odds_quotes)],
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

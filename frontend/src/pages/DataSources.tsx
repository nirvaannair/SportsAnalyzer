import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Guide } from '../components/Guide'
import { Badge, Card, CardHeader, PageHeader, StatusDot } from '../components/ui'
import { api, type Collector, type CollectorProvider } from '../lib/api'

function relative(iso: string | null) {
  if (!iso) return 'Never'
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h ago`
  return `${Math.round(minutes / 1440)} d ago`
}

function Switch({ on, onChange, disabled, label }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${
        on ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-700'}`}>
      <span className={`inline-block size-4 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
    </button>
  )
}

function Meter({ used, budget }: { used: number; budget: number }) {
  const share = budget > 0 ? Math.min(1, used / budget) : 0
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
      <div className={`h-full rounded-full ${share >= 1 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${share * 100}%` }} />
    </div>
  )
}

function ProviderCard({ p, masterOn, onChange }: {
  p: CollectorProvider
  masterOn: boolean
  onChange: (body: { enabled?: boolean; daily_budget?: number }) => void
}) {
  const queryClient = useQueryClient()
  const [budget, setBudget] = useState(String(p.daily_budget))
  useEffect(() => setBudget(String(p.daily_budget)), [p.daily_budget])
  const retry = useMutation({
    mutationFn: () => api.retryCollector(p.name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collector'] }),
  })
  const q = p.queue
  const total = (q.pending ?? 0) + (q.done ?? 0) + (q.failed ?? 0) + (q.unavailable ?? 0)
  const running = masterOn && p.enabled && p.configured
  const paused = p.paused_until && new Date(p.paused_until) > new Date()
  const tone = !p.configured ? 'off' : running ? (paused ? 'warn' : 'ok') : 'off'
  const status = !p.configured
    ? `Needs ${p.key_env} in .env`
    : !p.enabled ? 'Off'
    : !masterOn ? 'On, waiting for the collector switch'
    : paused ? `${p.reason ?? 'Paused'} · resumes ${new Date(p.paused_until!).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`
    : p.reason ?? (p.last_task ? `Last: ${p.last_task} · ${relative(p.last_at)}` : 'Starting…')

  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-zinc-100 px-5 py-3.5 dark:border-zinc-800">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-medium"><StatusDot tone={tone} /> {p.label}</div>
          <div className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{p.plan}</div>
        </div>
        <Switch on={p.enabled} disabled={!p.configured} label={`Collect from ${p.label}`} onChange={(v) => onChange({ enabled: v })} />
      </div>
      <div className="flex-1 space-y-3 px-5 py-4 text-sm">
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{p.collects}</p>
        <div>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-zinc-500 dark:text-zinc-400">Today (UTC)</span>
            <span className="tabular">{p.used_today} / {p.daily_budget} requests{p.remaining_reported !== null ? ` · provider says ${p.remaining_reported} left` : ''}</span>
          </div>
          <Meter used={p.used_today} budget={p.daily_budget} />
        </div>
        <div>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-zinc-500 dark:text-zinc-400">Queue</span>
            <span className="tabular">{(q.done ?? 0).toLocaleString('en-IN')} of {total.toLocaleString('en-IN')} collected</span>
          </div>
          <Meter used={q.done ?? 0} budget={total} />
          <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
            <Badge>{(q.pending ?? 0).toLocaleString('en-IN')} waiting</Badge>
            {(q.unavailable ?? 0) > 0 && <Badge>{q.unavailable} not in free plan</Badge>}
            {(q.failed ?? 0) > 0 && (
              <button onClick={() => retry.mutate()} className="inline-flex items-center gap-1 rounded-md bg-rose-50 px-2 py-0.5 font-medium text-rose-700 hover:bg-rose-100 dark:bg-rose-950 dark:text-rose-300">
                {q.failed} failed <RotateCcw className="size-3" />
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label htmlFor={`budget-${p.name}`} className="text-zinc-500 dark:text-zinc-400">Daily budget</label>
          <input id={`budget-${p.name}`} type="number" min={0} max={p.plan_daily_limit ?? undefined} value={budget}
                 onChange={(e) => setBudget(e.target.value)}
                 onBlur={() => { const n = Number(budget); if (Number.isFinite(n) && n !== p.daily_budget) onChange({ daily_budget: n }) }}
                 className="tabular w-20 rounded-md border border-zinc-200 bg-white px-2 py-1 dark:border-zinc-800 dark:bg-zinc-900" />
          {p.plan_daily_limit !== null && <span className="text-zinc-400">max {p.plan_daily_limit} on the free plan</span>}
        </div>
        <div className="text-xs text-zinc-500 dark:text-zinc-400">{status}</div>
        {!p.configured && p.signup_url && (
          <a href={p.signup_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline dark:text-emerald-400">
            Get a free key <ExternalLink className="size-3" />
          </a>
        )}
      </div>
      {p.recent.length > 0 && (
        <ul className="divide-y divide-zinc-100 border-t border-zinc-100 text-xs dark:divide-zinc-800 dark:border-zinc-800">
          {p.recent.map((t) => (
            <li key={t.label + t.done_at} className="flex items-center gap-2 px-5 py-1.5">
              <StatusDot tone={t.status === 'done' ? 'ok' : t.status === 'unavailable' ? 'off' : 'bad'} />
              <span className="min-w-0 flex-1 truncate" title={t.error ?? undefined}>{t.label}</span>
              <span className="tabular text-zinc-500">{t.items ?? '—'} items</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function CollectorPanel() {
  const queryClient = useQueryClient()
  const collector = useQuery({ queryKey: ['collector'], queryFn: api.collector, refetchInterval: 5000 })
  const change = useMutation({
    mutationFn: api.setCollector,
    onSuccess: (data: Collector) => {
      queryClient.setQueryData(['collector'], data)
      queryClient.invalidateQueries({ queryKey: ['providers'] })
    },
  })
  const c = collector.data
  if (collector.isError) return null

  return (
    <div className="mb-8">
      <Card className="mb-4">
        <div className="flex items-center justify-between gap-4 px-5 py-4">
          <div>
            <div className="text-sm font-medium">Background collector</div>
            <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
              Slowly downloads more data from free APIs, staying under each free plan's limits. Responses are stored
              untouched first. Odds are never requested.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-500 dark:text-zinc-400">{c?.enabled ? 'Running' : 'Off'}</span>
            <Switch on={Boolean(c?.enabled)} disabled={!c || change.isPending} label="Background collector"
                    onChange={(v) => change.mutate({ enabled: v })} />
          </div>
        </div>
        {change.error && <p className="px-5 pb-3 text-sm text-rose-600">{(change.error as Error).message}</p>}
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        {(c?.providers ?? []).map((p) => (
          <ProviderCard key={p.name} p={p} masterOn={Boolean(c?.enabled)}
                        onChange={(body) => change.mutate({ providers: { [p.name]: body } })} />
        ))}
      </div>
    </div>
  )
}

export default function DataSources() {
  const providers = useQuery({ queryKey: ['providers'], queryFn: api.providers, refetchInterval: 15000 })
  const collector = useQuery({ queryKey: ['collector'], queryFn: api.collector, refetchInterval: 5000 })
  const c = collector.data
  const on = c?.providers.filter((p) => c.enabled && p.enabled && p.configured) ?? []
  const missingKeys = c?.providers.filter((p) => !p.configured) ?? []
  const af = c?.providers.find((p) => p.name === 'api_football')

  return (
    <>
      <PageHeader title="Data sources" description="Free-plan API collection, keys and stored data for each provider." />
      <Guide items={[
        {
          title: 'Background collector',
          body: 'Downloads extra data from free football APIs a little at a time, all day. Each provider has its own switch. It never goes over a free plan: it spaces requests out and stops at the daily budget, then carries on after midnight (UTC).',
          verdict: on.length ? 'good' : 'medium',
          verdictLabel: on.length ? `${on.length} collecting` : 'Off',
        },
        {
          title: 'Daily budget and the meter',
          body: 'How many requests a provider may get today. The bar fills as they are used. When it is full the provider waits until tomorrow; nothing breaks.',
          verdict: 'info',
        },
        {
          title: 'API-Football',
          body: 'The richest source: injuries and per-match player stats. Its free plan allows 100 requests a day, so the queue takes weeks. That is expected and fine.',
          verdict: af?.enabled && c?.enabled ? 'good' : 'medium',
          verdictLabel: af?.enabled && c?.enabled ? 'Collecting' : 'Off: switch on to start',
        },
        {
          title: 'Keys',
          body: missingKeys.length
            ? `${missingKeys.map((p) => p.label).join(', ')} need a free key in the .env file (use "Get a free key"), then restart the app.`
            : 'Every provider that needs a key has one.',
          verdict: missingKeys.length ? 'medium' : 'good',
          verdictLabel: missingKeys.length ? `${missingKeys.length} key missing` : 'All set',
        },
        {
          title: 'Stored raw data',
          body: 'Every answer from a provider is saved untouched first, so it can be re-read later without spending quota again.',
          verdict: 'info',
        },
      ]} />
      <CollectorPanel />
      <Card>
        <CardHeader title="Stored raw data" aside={<span className="text-xs text-zinc-500">Refreshes every 15 s</span>} />
        {providers.isError ? (
          <p className="px-5 py-6 text-sm text-rose-600">Could not reach the API. Is the backend running on port 8000?</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                <th className="px-5 py-2.5 font-medium">Provider</th>
                <th className="px-5 py-2.5 font-medium">Key</th>
                <th className="px-5 py-2.5 text-right font-medium">Observations</th>
                <th className="px-5 py-2.5 text-right font-medium">Last received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {(providers.data ?? []).map((p) => (
                <tr key={p.name}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2.5">
                      <StatusDot tone={p.configured ? 'ok' : 'off'} />
                      <span className="font-medium">{p.label}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    {p.configured ? <Badge tone="accent">Configured</Badge> : <Badge>Missing</Badge>}
                  </td>
                  <td className="tabular px-5 py-3 text-right">{p.observations.toLocaleString('en-IN')}</td>
                  <td className="px-5 py-3 text-right text-zinc-500 dark:text-zinc-400">{relative(p.last_received_at)}</td>
                </tr>
              ))}
              {providers.isLoading && (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-zinc-500">Loading…</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}

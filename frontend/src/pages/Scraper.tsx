import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bug, Play, Square, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Guide } from '../components/Guide'
import { Badge, Card, CardHeader, EmptyState, PageHeader, StatusDot } from '../components/ui'
import { api, type ScrapeRun } from '../lib/api'

const LEAGUES = [
  ['ENG1', 'Premier League'], ['ENG2', 'Championship'], ['ESP1', 'La Liga'], ['ESP2', 'Segunda'],
  ['ITA1', 'Serie A'], ['ITA2', 'Serie B'], ['GER1', 'Bundesliga'], ['GER2', '2. Bundesliga'],
  ['FRA1', 'Ligue 1'], ['FRA2', 'Ligue 2'],
] as const

const STATUS_TONE: Record<ScrapeRun['status'], 'ok' | 'warn' | 'off' | 'bad'> = {
  queued: 'off', running: 'warn', loading: 'warn', finished: 'ok', failed: 'bad', stopped: 'off',
}
const isActive = (r: ScrapeRun) => ['queued', 'running', 'loading'].includes(r.status)
const iso = (d: Date) => d.toISOString().slice(0, 10)

function duration(run: ScrapeRun) {
  if (!run.started_at) return '—'
  const end = run.finished_at ? new Date(run.finished_at) : new Date()
  const s = Math.max(0, Math.round((end.getTime() - new Date(run.started_at).getTime()) / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

const input = 'rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900'

function NewRun({ disabled }: { disabled: boolean }) {
  const queryClient = useQueryClient()
  const today = new Date()
  const [leagues, setLeagues] = useState<string[]>(['ENG1'])
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 14 * 864e5)))
  const [to, setTo] = useState(iso(today))
  const start = useMutation({
    mutationFn: () => api.startScrape({ spider: 'espn_matches', leagues, date_from: from, date_to: to, refetch: false }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scraper'] }),
  })
  const toggle = (code: string) =>
    setLeagues((l) => (l.includes(code) ? l.filter((c) => c !== code) : [...l, code]))

  return (
    <Card>
      <CardHeader title="New scrape" aside={<span className="whitespace-nowrap text-xs text-zinc-500">ESPN · 1 request / 2 s</span>} />
      <div className="space-y-4 px-5 py-4">
        <div className="flex flex-wrap gap-1.5">
          {LEAGUES.map(([code, name]) => (
            <button key={code} onClick={() => toggle(code)}
              className={`rounded-md border px-2.5 py-1 text-xs ${leagues.includes(code)
                ? 'border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900'
                : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800'}`}>
              {name}
            </button>
          ))}
          <button onClick={() => setLeagues(LEAGUES.map(([c]) => c))} className="px-2 text-xs text-zinc-500 underline-offset-2 hover:underline">all</button>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={input} />
          <span className="text-zinc-400">to</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={input} />
          <button
            onClick={() => start.mutate()}
            disabled={disabled || leagues.length === 0 || start.isPending}
            className="ml-auto flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            <Play className="size-3.5" /> Start
          </button>
        </div>
        {disabled && <p className="text-xs text-zinc-500">A scrape is running. Stop it or wait for it to finish.</p>}
        {start.error && <p className="text-sm text-rose-600">{(start.error as Error).message}</p>}
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Matches already scraped are skipped, and each page is cached, so re-running a range is quick. After the crawl,
          teams and matches are linked and lineups loaded automatically.
        </p>
      </div>
    </Card>
  )
}

function AutoScrape() {
  const queryClient = useQueryClient()
  const auto = useQuery({ queryKey: ['scraper', 'auto'], queryFn: api.scraperAuto, refetchInterval: 15000 })
  const change = useMutation({
    mutationFn: (enabled: boolean) => api.setScraperAuto(enabled),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scraper'] }),
  })
  const on = Boolean(auto.data?.enabled)
  return (
    <Card>
      <div className="flex items-center justify-between gap-4 px-5 py-4">
        <div className="min-w-0">
          <div className="text-sm font-medium">Keep scraping automatically</div>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            Finishes the 2019 to now history first, then every 6 hours fetches the last 10 days and next 14. If ESPN says
            "too many requests", the crawl pauses and carries on by itself.
          </p>
          {auto.data?.last_action && (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Last: {auto.data.last_action.action} · {new Date(auto.data.last_action.at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
            </p>
          )}
        </div>
        <button role="switch" aria-checked={on} aria-label="Keep scraping automatically" disabled={!auto.data || change.isPending}
          onClick={() => change.mutate(!on)}
          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${on ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-700'}`}>
          <span className={`inline-block size-4 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
        </button>
      </div>
    </Card>
  )
}

function ItemDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const item = useQuery({ queryKey: ['scraper', 'item', id], queryFn: () => api.scraperItem(id) })
  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-black/30" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-auto border-l border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
           onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-sm font-medium">{item.data?.type} · {item.data?.key}</div>
            <div className="break-all text-xs text-zinc-500">{item.data?.url}</div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800" aria-label="Close"><X className="size-4" /></button>
        </div>
        <pre className="overflow-auto rounded-lg bg-zinc-50 p-3 text-xs leading-relaxed dark:bg-zinc-900">
          {item.isLoading ? 'Loading…' : JSON.stringify(item.data?.data, null, 2)}
        </pre>
      </div>
    </div>
  )
}

export default function Scraper() {
  const queryClient = useQueryClient()
  const runs = useQuery({ queryKey: ['scraper', 'runs'], queryFn: api.scraperRuns, refetchInterval: 3000 })
  const totals = useQuery({ queryKey: ['scraper', 'totals'], queryFn: api.scraperTotals, refetchInterval: 5000 })
  const list = runs.data ?? []
  const active = list.find(isActive)
  const [selected, setSelected] = useState<number | null>(null)
  const runId = selected ?? active?.id ?? list[0]?.id ?? null
  const run = list.find((r) => r.id === runId)
  const [type, setType] = useState('')
  const [open, setOpen] = useState<number | null>(null)

  useEffect(() => { if (active) setSelected(null) }, [active?.id]) // follow a newly started run

  const items = useQuery({
    queryKey: ['scraper', 'items', runId, type],
    queryFn: () => api.scraperItems(runId, type),
    enabled: runId !== null,
    refetchInterval: run && isActive(run) ? 3000 : false,
  })
  const log = useQuery({
    queryKey: ['scraper', 'log', runId],
    queryFn: () => api.scraperLog(runId!),
    enabled: runId !== null,
    refetchInterval: run && isActive(run) ? 3000 : false,
  })
  const logRef = useRef<HTMLPreElement>(null)
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log.data])
  const stop = useMutation({
    mutationFn: (id: number) => api.stopScrape(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scraper'] }),
  })

  const t = totals.data
  return (
    <>
      <PageHeader
        title="Scraper"
        description="Scrapy spiders that collect match lineups, substitutions and stats. Everything they fetch is listed here."
        actions={active ? <Badge tone="warn">Run #{active.id} {active.status}</Badge> : <Badge>Idle</Badge>}
      />

      <Guide items={[
        {
          title: 'What the scraper does',
          body: 'Scrapy (an open-source scraping tool) reads ESPN match pages: starting XIs, substitutions with minutes, goals, cards and player stats. This is what the player features are built from.',
          verdict: active ? 'good' : 'medium', verdictLabel: active ? 'Collecting' : 'Idle',
        },
        {
          title: 'Matches with lineups',
          body: 'How many matches have their players loaded. Player features need most of the ~20,000 matches since 2019; until then the models use team data only.',
          verdict: (t?.matches_with_lineups ?? 0) > 15000 ? 'good' : (t?.matches_with_lineups ?? 0) > 3000 ? 'medium' : 'bad',
          verdictLabel: (t?.matches_with_lineups ?? 0) > 15000 ? 'Enough' : 'Still filling',
        },
        {
          title: 'Rate limits',
          body: 'It asks for one page every 2 seconds. If ESPN says "too many requests", the crawl pauses (1 minute, then longer) and continues by itself. Pages are cached, so a restart never downloads twice.',
          verdict: 'info',
        },
        {
          title: 'Runs, log and items',
          body: 'Each run is one crawl. The log shows what it is doing right now; items are everything it saved. Click an item to see the raw data.',
          verdict: 'info',
        },
      ]} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ['Matches listed', t?.items_by_type.fixture],
          ['Match details', t?.items_by_type.match_detail],
          ['Players', t?.players],
          ['Matches with lineups', t?.matches_with_lineups],
        ].map(([label, value]) => (
          <Card key={label as string} className="px-5 py-4">
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
            <div className="tabular mt-2 text-2xl font-semibold">{value === undefined ? '…' : Number(value).toLocaleString('en-IN')}</div>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <AutoScrape />
          <NewRun disabled={Boolean(active)} />
          <Card>
            <CardHeader title="Runs" />
            {list.length === 0 ? (
              <EmptyState icon={<Bug className="size-6" />} title="No runs yet" body="Pick leagues and dates above, then Start." />
            ) : (
              <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {list.map((r) => (
                  <li key={r.id}>
                    <button onClick={() => setSelected(r.id)}
                      className={`flex w-full items-center gap-3 px-5 py-3 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800/40 ${r.id === runId ? 'bg-zinc-50 dark:bg-zinc-800/40' : ''}`}>
                      <StatusDot tone={STATUS_TONE[r.status]} />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">#{r.id} · {r.args.leagues || 'All leagues'}</div>
                        <div className="text-xs text-zinc-500 dark:text-zinc-400">
                          {r.args.date_from} → {r.args.date_to} · {r.status} · {duration(r)}
                        </div>
                      </div>
                      <div className="tabular text-right text-xs text-zinc-500 dark:text-zinc-400">
                        {r.stats.items ?? 0} items<br />{r.stats.requests ?? 0} requests
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-3">
          {run && (
            <Card>
              <CardHeader
                title={`Run #${run.id}`}
                aside={isActive(run) ? (
                  <button onClick={() => stop.mutate(run.id)}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950">
                    <Square className="size-3" /> Stop
                  </button>
                ) : <Badge tone={run.status === 'finished' ? 'accent' : run.status === 'failed' ? 'warn' : 'neutral'}>{run.status}</Badge>}
              />
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 px-5 py-4 text-sm sm:grid-cols-4">
                {[
                  ['Requests', run.stats.requests ?? 0],
                  ['From cache', run.stats.cached ?? 0],
                  ['Items', run.stats.items ?? 0],
                  ['Errors', run.stats.errors ?? 0],
                  ['Matches listed', run.stats.items_by_type?.fixture ?? 0],
                  ['Match details', run.stats.items_by_type?.match_detail ?? 0],
                  ['Lineups loaded', run.stats.loaded?.loaded ?? '—'],
                  ['Teams linked', run.stats.loaded?.teams_resolved ?? '—'],
                ].map(([k, v]) => (
                  <div key={k as string}>
                    <dt className="text-xs text-zinc-500 dark:text-zinc-400">{k}</dt>
                    <dd className="tabular font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
              {run.message && <p className="px-5 pb-3 text-sm text-rose-600">{run.message}</p>}
              <pre ref={logRef} className="mx-5 mb-5 max-h-56 overflow-auto rounded-lg bg-zinc-50 p-3 text-[11px] leading-relaxed text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                {(log.data?.lines ?? []).slice(-40).join('\n') || 'No log yet.'}
              </pre>
            </Card>
          )}

          <Card>
            <CardHeader
              title={`Items ${items.data ? `(${items.data.total.toLocaleString('en-IN')})` : ''}`}
              aside={
                <select value={type} onChange={(e) => setType(e.target.value)} className={`${input} py-1 text-xs`}>
                  <option value="">All types</option>
                  <option value="fixture">Match listings</option>
                  <option value="match_detail">Match details</option>
                </select>
              }
            />
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {(items.data?.items ?? []).map((i) => (
                <li key={i.id}>
                  <button onClick={() => setOpen(i.id)} className="flex w-full items-center gap-3 px-5 py-2.5 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
                    <Badge tone={i.type === 'match_detail' ? 'accent' : 'neutral'}>{i.type === 'match_detail' ? 'detail' : 'listing'}</Badge>
                    <span className="min-w-0 flex-1 truncate">{i.summary}</span>
                    {i.type === 'match_detail' && (
                      <span className="text-xs text-zinc-500" title={i.loaded ? 'Lineup loaded into the database' : 'Waiting until both teams are linked'}>
                        {i.loaded ? 'loaded' : 'waiting'}
                      </span>
                    )}
                  </button>
                </li>
              ))}
              {items.data?.items.length === 0 && <li className="px-5 py-6 text-center text-sm text-zinc-500">Nothing scraped in this run.</li>}
            </ul>
          </Card>
        </div>
      </div>
      {open !== null && <ItemDrawer id={open} onClose={() => setOpen(null)} />}
    </>
  )
}

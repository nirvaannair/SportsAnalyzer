import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cpu, GraduationCap, Play, ShieldCheck, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Badge, Card, CardHeader, EmptyState, PageHeader, StatusDot } from '../components/ui'
import { api, type TrainingRun, type TrainingScore } from '../lib/api'

const STATUS_TONE: Record<TrainingRun['status'], 'ok' | 'warn' | 'off' | 'bad'> = {
  queued: 'off', running: 'warn', finished: 'ok', failed: 'bad', stopped: 'off',
}
const FAMILY: Record<string, string> = { xgb: 'XGBoost', nn: 'Neural net', ml_ensemble: 'Ensemble', data: 'Data' }
const VARIANT: Record<string, string> = {
  global: 'Global (all leagues)', league: 'Per-league fine-tuned', auto: 'Auto (best per league)',
}
const LEAGUE_NAME: Record<string, string> = {
  ENG1: 'Premier League', ENG2: 'Championship', ESP1: 'La Liga', ESP2: 'Segunda', ITA1: 'Serie A',
  ITA2: 'Serie B', GER1: 'Bundesliga', GER2: '2. Bundesliga', FRA1: 'Ligue 1', FRA2: 'Ligue 2',
}
const isActive = (r?: TrainingRun) => Boolean(r && ['queued', 'running'].includes(r.status))
const num = (v: number | null | undefined, d = 4) => (v === null || v === undefined ? '—' : v.toFixed(d))

function duration(run: TrainingRun) {
  if (!run.started_at) return '—'
  const end = run.finished_at ? new Date(run.finished_at) : new Date()
  const s = Math.max(0, Math.round((end.getTime() - new Date(run.started_at).getTime()) / 1000))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

/** Training vs validation loss for the step currently being trained. */
function LossChart({ curve }: { curve: [number, number, number][] }) {
  const [hover, setHover] = useState<number | null>(null)
  const w = 560
  const h = 200
  const pad = { l: 44, r: 12, t: 10, b: 24 }
  if (curve.length < 2) {
    return <div className="flex h-[200px] items-center justify-center text-sm text-zinc-500">Waiting for the first steps…</div>
  }
  const xs = curve.map((p) => p[0])
  const ys = curve.flatMap((p) => [p[1], p[2]])
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  const [lo, hi] = [Math.min(...ys), Math.max(...ys)]
  const span = hi - lo || 1
  const sx = (v: number) => pad.l + ((v - x0) / (x1 - x0 || 1)) * (w - pad.l - pad.r)
  const sy = (v: number) => pad.t + (1 - (v - lo + span * 0.05) / (span * 1.1)) * (h - pad.t - pad.b)
  const line = (i: 1 | 2) => curve.map((p) => `${sx(p[0])},${sy(p[i])}`).join(' ')
  const ticks = [lo, lo + span / 2, hi]
  const best = curve.reduce((b, p) => (p[2] < b[2] ? p : b), curve[0])
  const point = hover === null ? null : curve[hover]

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Training and validation loss by step"
           onMouseLeave={() => setHover(null)}
           onMouseMove={(e) => {
             const box = e.currentTarget.getBoundingClientRect()
             const x = ((e.clientX - box.left) / box.width) * w
             let nearest = 0
             curve.forEach((p, i) => { if (Math.abs(sx(p[0]) - x) < Math.abs(sx(curve[nearest][0]) - x)) nearest = i })
             setHover(nearest)
           }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={sy(t)} y2={sy(t)} className="stroke-zinc-100 dark:stroke-zinc-800" />
            <text x={pad.l - 6} y={sy(t) + 3} textAnchor="end" className="fill-zinc-400 text-[10px]">{t.toFixed(3)}</text>
          </g>
        ))}
        <text x={pad.l} y={h - 6} className="fill-zinc-400 text-[10px]">{x0}</text>
        <text x={w - pad.r} y={h - 6} textAnchor="end" className="fill-zinc-400 text-[10px]">step {x1}</text>
        <polyline fill="none" strokeWidth={1.5} className="stroke-zinc-400 dark:stroke-zinc-500" points={line(1)} />
        <polyline fill="none" strokeWidth={2} className="stroke-emerald-500" points={line(2)} />
        <circle cx={sx(best[0])} cy={sy(best[2])} r={3.5} className="fill-emerald-500 stroke-white dark:stroke-zinc-900" strokeWidth={1.5} />
        {point && <line x1={sx(point[0])} x2={sx(point[0])} y1={pad.t} y2={h - pad.b} className="stroke-zinc-300 dark:stroke-zinc-600" strokeDasharray="3 3" />}
      </svg>
      <div className="mt-1 flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-zinc-400" /> Training loss</span>
        <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-emerald-500" /> Validation loss (unseen, later matches)</span>
      </div>
      {point && (
        <div className="pointer-events-none absolute right-2 top-0 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
          <div className="font-medium">Step {point[0]}</div>
          <div className="text-zinc-500 dark:text-zinc-400">Training {point[1].toFixed(4)}</div>
          <div className="text-emerald-600 dark:text-emerald-400">Validation {point[2].toFixed(4)}</div>
        </div>
      )}
    </div>
  )
}

function NewRun({ disabled }: { disabled: boolean }) {
  const queryClient = useQueryClient()
  const info = useQuery({ queryKey: ['training', 'info'], queryFn: api.trainingInfo })
  const [models, setModels] = useState<string[]>(['xgb', 'nn'])
  const [first, setFirst] = useState(2018)
  const start = useMutation({
    mutationFn: () => api.startTraining({ models, first_test_season: first }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['training'] }),
  })
  const missing = info.data && (!info.data.libraries.xgboost || !info.data.libraries.torch)

  return (
    <Card>
      <CardHeader title="New training run" />
      <div className="space-y-4 px-5 py-4">
        <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
          <Cpu className="size-3.5 shrink-0" />
          <span className="truncate">{info.data ? info.data.gpu ?? 'No CUDA GPU found: training will use the CPU' : '…'}</span>
        </div>
        <div className="space-y-2">
          {(info.data?.models ?? []).map((m) => (
            <label key={m.name} className="flex cursor-pointer items-start gap-3 rounded-lg border border-zinc-200 p-3 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
              <input type="checkbox" className="mt-0.5 accent-zinc-900 dark:accent-zinc-100" checked={models.includes(m.name)}
                     onChange={() => setModels((l) => (l.includes(m.name) ? l.filter((x) => x !== m.name) : [...l, m.name]))} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm font-medium">
                  {m.label} {m.saved && <Badge tone="accent">trained</Badge>}
                </div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400">{m.description}</div>
              </div>
            </label>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-zinc-500 dark:text-zinc-400">Backtest from season</span>
          <select value={first} onChange={(e) => setFirst(Number(e.target.value))}
                  className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-sm dark:border-zinc-800 dark:bg-zinc-900">
            {[2017, 2018, 2019, 2020, 2021, 2022, 2023].map((y) => <option key={y} value={y}>{y}/{String((y + 1) % 100).padStart(2, '0')}</option>)}
          </select>
          <button
            onClick={() => start.mutate()}
            disabled={disabled || models.length === 0 || start.isPending || Boolean(missing)}
            className="ml-auto flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            <Play className="size-3.5" /> Train
          </button>
        </div>
        {missing && <p className="text-xs text-rose-600">XGBoost or PyTorch is not installed in the API's Python environment.</p>}
        {disabled && <p className="text-xs text-zinc-500">A training run is going. Stop it or wait for it to finish.</p>}
        {start.error && <p className="text-sm text-rose-600">{(start.error as Error).message}</p>}
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          For every season from the one chosen, each model is trained only on earlier seasons and then predicts that
          season, so the scores are what you would really have got. Each model is trained once globally (all leagues
          share one strength scale) and fine-tuned per league; "auto" uses whichever was better in that league in
          earlier seasons. Finally every model is refit on all results and predicts the upcoming matches.
        </p>
      </div>
    </Card>
  )
}

function Progress({ run }: { run: TrainingRun }) {
  const p = run.progress
  const foldShare = p.fold && p.folds ? (p.fold - 1) / p.folds : 0
  const stepShare = p.step && p.steps ? Math.min(1, p.step / p.steps) : 0
  const familyIdx = Math.max(0, run.models.indexOf(p.model ?? ''))
  const perFamily = 1 / run.models.length
  let overall = familyIdx * perFamily
  if (p.stage === 'backtest') overall += perFamily * 0.85 * (foldShare + stepShare / (p.folds || 1))
  if (p.stage === 'final') overall += perFamily * (0.85 + 0.15 * stepShare)
  if (p.stage === 'done') overall += perFamily
  if (run.status === 'finished') overall = 1

  return (
    <Card>
      <CardHeader title={`Run #${run.id} · ${run.models.map((m) => FAMILY[m] ?? m).join(' + ')}`}
                  aside={<span className="text-xs text-zinc-500">{run.device ?? ''} · {duration(run)}</span>} />
      <div className="space-y-4 px-5 py-4">
        <div>
          <div className="mb-1.5 flex justify-between text-xs text-zinc-500 dark:text-zinc-400">
            <span>{isActive(run) ? p.message ?? 'Starting…' : run.message}</span>
            <span className="tabular">{Math.round(overall * 100)}%</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div className={`h-full rounded-full transition-all ${run.status === 'failed' ? 'bg-rose-500' : 'bg-emerald-500'}`}
                 style={{ width: `${overall * 100}%` }} />
          </div>
        </div>
        {isActive(run) && p.task && (
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><div className="text-xs text-zinc-500">Model</div><div className="font-medium">{FAMILY[p.model ?? ''] ?? p.model}</div></div>
            <div><div className="text-xs text-zinc-500">{p.stage === 'final' ? 'Stage' : 'Season fold'}</div>
              <div className="tabular font-medium">{p.stage === 'final' ? 'Final fit' : p.season ? `${p.season}/${String((p.season + 1) % 100).padStart(2, '0')} (${p.fold}/${p.folds})` : '—'}</div></div>
            <div><div className="text-xs text-zinc-500">Training</div><div className="font-medium">{p.task}</div></div>
            <div><div className="text-xs text-zinc-500">{p.model === 'nn' ? 'Epoch' : 'Round'}</div><div className="tabular font-medium">{p.step} / {p.steps}</div></div>
          </div>
        )}
        {isActive(run) && <LossChart curve={p.curve ?? []} />}
      </div>
    </Card>
  )
}

function ScoreRow({ label, sub, s, best }: { label: string; sub?: string; s: TrainingScore; best: boolean }) {
  return (
    <tr>
      <td className="px-5 py-2.5">
        <div className="font-medium">{label}</div>
        {sub && <div className="text-xs text-zinc-500 dark:text-zinc-400">{sub}</div>}
      </td>
      <td className="tabular px-3 py-2.5 text-right">{s.n.toLocaleString('en-IN')}</td>
      <td className={`tabular px-3 py-2.5 text-right ${best ? 'font-semibold text-emerald-600 dark:text-emerald-400' : ''}`}>{num(s.logloss_1x2)}</td>
      <td className="tabular px-3 py-2.5 text-right">{(s.accuracy_1x2 * 100).toFixed(1)}%</td>
      <td className="tabular px-3 py-2.5 text-right">{num(s.ou25_logloss)}</td>
      <td className="tabular px-5 py-2.5 text-right">{num(s.btts_logloss)}</td>
    </tr>
  )
}

function Results({ run }: { run: TrainingRun }) {
  const rows: { key: string; label: string; sub?: string; s: TrainingScore }[] = []
  for (const family of [...run.models, 'ml_ensemble']) {
    const variants = run.results[family]?.variants
    if (!variants) continue
    for (const [variant, s] of Object.entries(variants)) {
      rows.push({ key: `${family}-${variant}`, label: family === 'ml_ensemble' ? 'Ensemble (XGBoost + neural net)' : `${FAMILY[family]} · ${VARIANT[variant]}`, s })
    }
  }
  if (rows.length === 0) return null
  const best = Math.min(...rows.map((r) => r.s.logloss_1x2))
  const leagueFamilies = run.models.filter((m) => run.results[m]?.leagues)

  return (
    <>
      <Card className="mt-6">
        <CardHeader title="Backtest scores" aside={<span className="text-xs text-zinc-500">Real results · lower log loss = better · compare with Models page</span>} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                <th className="px-5 py-2 font-medium">Model</th>
                <th className="px-3 py-2 text-right font-medium">Matches</th>
                <th className="px-3 py-2 text-right font-medium">1X2 log loss</th>
                <th className="px-3 py-2 text-right font-medium">Favourite won</th>
                <th className="px-3 py-2 text-right font-medium">O/U 2.5</th>
                <th className="px-5 py-2 text-right font-medium">BTTS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {rows.map((r) => <ScoreRow key={r.key} label={r.label} sub={r.sub} s={r.s} best={r.s.logloss_1x2 === best} />)}
            </tbody>
          </table>
        </div>
      </Card>

      {leagueFamilies.length > 0 && (
        <Card className="mt-6">
          <CardHeader title="Global or per-league, by league" aside={<span className="text-xs text-zinc-500">1X2 log loss in the backtest</span>} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  <th className="px-5 py-2 font-medium">League</th>
                  {leagueFamilies.map((f) => (
                    <th key={f} colSpan={3} className="px-3 py-2 text-center font-medium">{FAMILY[f]}: global · league · using</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {Object.keys(LEAGUE_NAME).filter((lg) => leagueFamilies.some((f) => run.results[f]?.leagues?.[lg])).map((lg) => (
                  <tr key={lg}>
                    <td className="px-5 py-2">{LEAGUE_NAME[lg]}</td>
                    {leagueFamilies.map((f) => {
                      const r = run.results[f]?.leagues?.[lg]
                      return [
                        <td key={`${f}g`} className={`tabular px-3 py-2 text-right ${r?.choice === 'global' ? 'font-medium' : 'text-zinc-500'}`}>{num(r?.global)}</td>,
                        <td key={`${f}l`} className={`tabular px-3 py-2 text-right ${r?.choice === 'league' ? 'font-medium' : 'text-zinc-500'}`}>{num(r?.league)}</td>,
                        <td key={`${f}c`} className="px-3 py-2 text-center">{r ? <Badge tone={r.choice === 'league' ? 'accent' : 'neutral'}>{r.choice}</Badge> : '—'}</td>,
                      ]
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-5 py-3 text-xs text-zinc-500 dark:text-zinc-400">
            "Using" is what live predictions use for that league: the per-league model only takes over where it beat the
            global one over the whole backtest.
          </p>
        </Card>
      )}
    </>
  )
}

export default function Training() {
  const queryClient = useQueryClient()
  const runs = useQuery({ queryKey: ['training', 'runs'], queryFn: api.trainingRuns, refetchInterval: 3000 })
  const list = runs.data ?? []
  const active = list.find(isActive)
  const [selected, setSelected] = useState<number | null>(null)
  const runId = selected ?? active?.id ?? list[0]?.id ?? null
  useEffect(() => { if (active) setSelected(null) }, [active?.id])

  const detail = useQuery({
    queryKey: ['training', 'run', runId],
    queryFn: () => api.trainingRun(runId!),
    enabled: runId !== null,
    refetchInterval: (q) => (isActive(q.state.data) ? 1500 : false),
  })
  const run = detail.data
  const log = useQuery({
    queryKey: ['training', 'log', runId],
    queryFn: () => api.trainingLog(runId!),
    enabled: runId !== null,
    refetchInterval: isActive(run) ? 3000 : false,
  })
  const logRef = useRef<HTMLPreElement>(null)
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log.data])
  const stop = useMutation({
    mutationFn: (id: number) => api.stopTraining(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['training'] }),
  })

  return (
    <>
      <PageHeader
        title="Training"
        description="Train the machine-learning models on your GPU and watch them learn. Scores are walk-forward backtests on real results."
        actions={
          <div className="flex items-center gap-2">
            <Badge tone="accent"><ShieldCheck className="mr-1 size-3.5" /> No odds as inputs</Badge>
            {active ? <Badge tone="warn">Run #{active.id} {active.status}</Badge> : <Badge>Idle</Badge>}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <NewRun disabled={Boolean(active)} />
          <Card>
            <CardHeader title="Runs" />
            {list.length === 0 ? (
              <EmptyState icon={<GraduationCap className="size-6" />} title="No training runs yet" body="Pick the models above, then Train." />
            ) : (
              <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {list.map((r) => (
                  <li key={r.id}>
                    <button onClick={() => setSelected(r.id)}
                      className={`flex w-full items-center gap-3 px-5 py-3 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800/40 ${r.id === runId ? 'bg-zinc-50 dark:bg-zinc-800/40' : ''}`}>
                      <StatusDot tone={STATUS_TONE[r.status]} />
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">#{r.id} · {r.models.map((m) => FAMILY[m] ?? m).join(' + ')}</div>
                        <div className="truncate text-xs text-zinc-500 dark:text-zinc-400">{r.status} · {duration(r)}{r.device ? ` · ${r.device}` : ''}</div>
                      </div>
                      {isActive(r) && (
                        <span role="button" onClick={(e) => { e.stopPropagation(); stop.mutate(r.id) }}
                              className="flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800">
                          <Square className="size-3" /> Stop
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-3">
          {run ? <Progress run={run} /> : (
            <Card><EmptyState icon={<GraduationCap className="size-6" />} title="Nothing selected" body="Start a run or pick one from the list." /></Card>
          )}
          {run && (
            <Card>
              <CardHeader title="Log" />
              <pre ref={logRef} className="max-h-64 overflow-auto whitespace-pre-wrap break-words px-5 py-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                {(log.data?.lines ?? []).join('\n') || 'No output yet.'}
              </pre>
            </Card>
          )}
        </div>
      </div>

      {run && <Results run={run} />}
    </>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Brain, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Guide, type GuideItem } from '../components/Guide'
import { Badge, Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api, type ModelSummary } from '../lib/api'
import { setting } from '../lib/settings'

const LABEL: Record<string, string> = {
  elo: 'Elo', dixon_coles: 'Dixon-Coles', blend: 'Blend (Elo + Dixon-Coles)',
  xgb: 'XGBoost · global', xgb_league: 'XGBoost · per league', xgb_auto: 'XGBoost · auto',
  nn: 'Neural net · global', nn_league: 'Neural net · per league', nn_auto: 'Neural net · auto',
  ml_ensemble: 'ML ensemble',
}
const ABOUT: Record<string, string> = {
  elo: 'One rating per team, updated after every match. Predicts home/draw/away from the rating gap.',
  dixon_coles: 'Attack and defence strength per team, recent matches weighted more. Gives every scoreline, so also Over/Under 2.5 and BTTS.',
  blend: 'Average of the Elo and Dixon-Coles home/draw/away probabilities; goal markets from Dixon-Coles.',
  xgb: 'Gradient-boosted trees on form, ratings, shots, rest and head-to-head features; one model for all leagues.',
  xgb_league: 'The global XGBoost model with extra trees fine-tuned on each league.',
  xgb_auto: 'Per league, whichever of global / per-league XGBoost did better in earlier seasons.',
  nn: 'Residual neural net with a head per market, trained on all leagues.',
  nn_league: 'The global neural net fine-tuned on each league.',
  nn_auto: 'Per league, whichever of global / per-league neural net did better in earlier seasons.',
  ml_ensemble: 'Average of XGBoost auto and neural net auto.',
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`
const num = (v: number | undefined, d = 4) => (v === undefined ? '—' : v.toFixed(d))

/** Predicted vs observed frequency per probability bucket. Points on the diagonal = well calibrated. */
function CalibrationChart({ data }: { data: ModelSummary['metrics']['calibration_1x2'] }) {
  const [hover, setHover] = useState<number | null>(null)
  const size = 260
  const pad = 32
  const scale = (v: number) => pad + v * (size - pad * 1.5)
  const y = (v: number) => size - scale(v) + pad / 2
  const maxCount = Math.max(...data.map((d) => d.count))

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[320px]" role="img"
           aria-label="Calibration: predicted probability against how often it happened">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={scale(0)} x2={scale(1)} y1={y(t)} y2={y(t)} className="stroke-zinc-100 dark:stroke-zinc-800" />
            <text x={pad - 6} y={y(t) + 3} textAnchor="end" className="fill-zinc-400 text-[9px]">{t * 100}%</text>
            <text x={scale(t)} y={size - 6} textAnchor="middle" className="fill-zinc-400 text-[9px]">{t * 100}%</text>
          </g>
        ))}
        <line x1={scale(0)} y1={y(0)} x2={scale(1)} y2={y(1)} strokeDasharray="3 3"
              className="stroke-zinc-300 dark:stroke-zinc-600" strokeWidth={1} />
        <polyline fill="none" strokeWidth={2} className="stroke-emerald-500"
                  points={data.map((d) => `${scale(d.predicted)},${y(d.observed)}`).join(' ')} />
        {data.map((d, i) => (
          <g key={d.bucket} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <circle cx={scale(d.predicted)} cy={y(d.observed)} r={12} fill="transparent" />
            <circle cx={scale(d.predicted)} cy={y(d.observed)} r={3 + 3 * Math.sqrt(d.count / maxCount)}
                    className="fill-emerald-500 stroke-white dark:stroke-zinc-900" strokeWidth={2} />
          </g>
        ))}
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute left-10 top-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
          <div className="font-medium">Model said {pct(data[hover].predicted)}</div>
          <div className="text-zinc-500 dark:text-zinc-400">It happened {pct(data[hover].observed)} of the time</div>
          <div className="text-zinc-500 dark:text-zinc-400">{data[hover].count.toLocaleString('en-IN')} outcomes</div>
        </div>
      )}
    </div>
  )
}

function Row({ label, sub, s, ou, btts, n, muted }: {
  label: string
  sub?: string
  s: ModelSummary['metrics']['1x2']
  ou?: number
  btts?: number
  n?: number
  muted?: boolean
}) {
  return (
    <tr className={muted ? 'text-zinc-500 dark:text-zinc-400' : ''}>
      <td className="px-5 py-3">
        <div className={muted ? '' : 'font-medium'}>{label}</div>
        {sub && <div className="text-xs text-zinc-500 dark:text-zinc-400">{sub}</div>}
      </td>
      <td className="tabular px-3 py-3 text-right">{n?.toLocaleString('en-IN') ?? ''}</td>
      <td className="tabular px-3 py-3 text-right">{num(s.logloss)}</td>
      <td className="tabular px-3 py-3 text-right">{pct(s.accuracy)}</td>
      <td className="tabular px-3 py-3 text-right">{num(s.rps)}</td>
      <td className="tabular px-3 py-3 text-right">{num(ou)}</td>
      <td className="tabular px-5 py-3 text-right">{num(btts)}</td>
    </tr>
  )
}

function ModelsGuide({ list, current }: { list: ModelSummary[]; current?: ModelSummary }) {
  const ref = list[0]?.metrics
  const market = ref?.market_reference_1x2?.logloss
  const best = [...list].sort((a, b) => a.metrics['1x2'].logloss - b.metrics['1x2'].logloss)[0]
  const gap = best && market !== undefined ? best.metrics['1x2'].logloss - market : undefined
  const cal = current?.metrics.calibration_1x2 ?? []
  const calErr = cal.length
    ? cal.reduce((t, b) => t + Math.abs(b.predicted - b.observed) * b.count, 0) / cal.reduce((t, b) => t + b.count, 0)
    : undefined
  const bets = current?.metrics.simulated_bets ?? []
  const bestRoi = bets.length ? Math.max(...bets.map((b) => b.roi)) : undefined
  const items: GuideItem[] = [
    {
      title: 'The accuracy table',
      body: "Every model is scored on the same matches it had never seen. Log loss and RPS: lower is better. 'Always predict the average' is the floor any model must beat; the bookmakers' closing prices are the target.",
      verdict: 'info',
    },
    {
      title: `Best model: ${best ? LABEL[best.model] ?? best.model : '…'}`,
      body: gap === undefined ? '' : gap < 0
        ? "It beats the bookmakers' closing prices: a real edge."
        : `It is ${gap.toFixed(4)} behind the bookmakers. Good enough to learn from, not yet to bet real money with.`,
      verdict: gap === undefined ? 'info' : gap < 0 ? 'good' : gap < setting<number>('verdicts.market_gap_medium') ? 'medium' : 'bad',
      verdictLabel: gap === undefined ? undefined : gap < 0 ? 'Beating market' : 'Behind market',
    },
    {
      title: 'Calibration chart',
      body: <>When the model says 40%, does it happen about 40% of the time? Dots on the dashed line = honest probabilities, which value
        betting depends on.{calErr !== undefined && ` The selected model is off by ${(calErr * 100).toFixed(1)} percentage points on average.`}</>,
      verdict: calErr === undefined ? 'info' : calErr < setting<number>('verdicts.calibration_good') ? 'good' : calErr < setting<number>('verdicts.calibration_medium') ? 'medium' : 'bad',
      verdictLabel: calErr === undefined ? undefined : calErr < setting<number>('verdicts.calibration_good') ? 'Well calibrated' : undefined,
    },
    {
      title: 'By season',
      body: 'The same score split by season. Steady numbers mean the model is not just lucky in one year; a sudden jump means something changed (rules, data gaps).',
      verdict: 'info',
    },
    {
      title: 'Simulated flat bets',
      body: <>What would have happened betting 1 unit whenever the model saw an edge, at the bookmakers' prices. ROI above 0 = profit.
        {bestRoi !== undefined && ` Best setting for the selected model: ${bestRoi > 0 ? '+' : ''}${(bestRoi * 100).toFixed(1)}%.`}</>,
      verdict: bestRoi === undefined ? 'info' : bestRoi > setting<number>('verdicts.roi_good') ? 'good' : bestRoi > setting<number>('verdicts.roi_medium') ? 'medium' : 'bad',
      verdictLabel: bestRoi === undefined ? undefined : bestRoi > setting<number>('verdicts.roi_good') ? 'Profitable' : bestRoi > setting<number>('verdicts.roi_medium') ? 'Break-even-ish' : 'Losing',
    },
  ]
  return <Guide items={items} />
}

export default function Models() {
  const models = useQuery({ queryKey: ['models'], queryFn: api.models })
  const list = models.data ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const current = list.find((m) => m.model === (selected ?? list.find((x) => x.default)?.model ?? list[0]?.model))

  if (!models.isLoading && list.length === 0) {
    return (
      <>
        <PageHeader title="Models" />
        <Card>
          <EmptyState icon={<Brain className="size-6" />} title="No backtest yet"
                      body="Run: .venv\Scripts\python -m backend.cli backtest" />
        </Card>
      </>
    )
  }

  const ref = list[0]?.metrics
  return (
    <>
      <PageHeader
        title="Models"
        description="Every number here is a walk-forward backtest: each week the models only knew results from before that week."
        actions={<Badge tone="accent"><ShieldCheck className="mr-1 size-3.5" /> Odds-free models</Badge>}
      />
      <ModelsGuide list={list} current={current} />

      <Card>
        <CardHeader title="How accurate are the predictions?" aside={<span className="text-xs text-zinc-500">Lower log loss and RPS = better</span>} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                <th className="px-5 py-2.5 font-medium">Model</th>
                <th className="px-3 py-2.5 text-right font-medium">Matches</th>
                <th className="px-3 py-2.5 text-right font-medium">1X2 log loss</th>
                <th className="px-3 py-2.5 text-right font-medium">Favourite won</th>
                <th className="px-3 py-2.5 text-right font-medium">1X2 RPS</th>
                <th className="px-3 py-2.5 text-right font-medium">O/U 2.5 log loss</th>
                <th className="px-5 py-2.5 text-right font-medium">BTTS log loss</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {list.map((m) => (
                <Row key={m.model} label={LABEL[m.model] ?? m.model} sub={m.default ? 'Shown on the Matches page' : undefined}
                     s={m.metrics['1x2']} ou={m.metrics.ou25_logloss} btts={m.metrics.btts_logloss} n={m.metrics.n} />
              ))}
              {ref && (
                <Row muted label="Always predict the average" sub="Baseline a model must beat"
                     s={ref.baseline_1x2} n={ref.n} />
              )}
              {ref?.market_reference_1x2 && (
                <Row muted label="Bookmakers' closing prices"
                     sub="For comparison only. Never used by the models."
                     s={ref.market_reference_1x2} n={ref.market_reference_1x2.n} />
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {current && (
        <>
          <div className="mb-3 mt-8 flex flex-wrap items-center gap-2">
            {list.map((m) => (
              <button
                key={m.model}
                onClick={() => setSelected(m.model)}
                className={`rounded-lg px-3 py-1.5 text-sm ${
                  m.model === current.model
                    ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                    : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800'
                }`}
              >
                {LABEL[m.model] ?? m.model}
              </button>
            ))}
            <span className="ml-2 text-sm text-zinc-500 dark:text-zinc-400">{ABOUT[current.model]}</span>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="lg:col-span-2">
              <CardHeader title="Calibration" aside={<span className="whitespace-nowrap text-xs text-zinc-500">Dashed line = honest</span>} />
              <div className="px-5 py-4">
                <CalibrationChart data={current.metrics.calibration_1x2} />
                <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                  When the model says 40%, does it happen about 40% of the time? Value betting depends on this.
                </p>
              </div>
            </Card>

            <Card className="lg:col-span-3">
              <CardHeader title="By season" />
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    <th className="px-5 py-2 font-medium">Season</th>
                    <th className="px-3 py-2 text-right font-medium">Matches</th>
                    <th className="px-3 py-2 text-right font-medium">Log loss</th>
                    <th className="px-5 py-2 text-right font-medium">Favourite won</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {current.metrics.by_season.map((s) => (
                    <tr key={s.season}>
                      <td className="px-5 py-2">{s.season}/{String((s.season + 1) % 100).padStart(2, '0')}</td>
                      <td className="tabular px-3 py-2 text-right">{s.n.toLocaleString('en-IN')}</td>
                      <td className="tabular px-3 py-2 text-right">{num(s.logloss)}</td>
                      <td className="tabular px-5 py-2 text-right">{pct(s.accuracy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>

          {current.metrics.simulated_bets && current.metrics.simulated_bets.length > 0 && (
            <Card className="mt-6">
              <CardHeader title="Simulated flat bets" aside={<span className="text-xs text-zinc-500">1 unit per bet</span>} />
              <p className="px-5 pt-3 text-xs text-zinc-500 dark:text-zinc-400">
                A bet is placed when the model's probability × price − 1 exceeds the edge threshold. The price (market-average closing,
                standing in for Stake) is used only as the payout; it never changes the model's probability.
              </p>
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    <th className="px-5 py-2 font-medium">Market</th>
                    <th className="px-3 py-2 text-right font-medium">Edge needed</th>
                    <th className="px-3 py-2 text-right font-medium">Bets</th>
                    <th className="px-3 py-2 text-right font-medium">Profit (units)</th>
                    <th className="px-5 py-2 text-right font-medium">ROI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {current.metrics.simulated_bets.map((b) => (
                    <tr key={`${b.market}-${b.edge_threshold}`}>
                      <td className="px-5 py-2">{b.market === '1x2' ? 'Home / draw / away' : 'Over / under 2.5'}</td>
                      <td className="tabular px-3 py-2 text-right">{Math.round(b.edge_threshold * 100)}%</td>
                      <td className="tabular px-3 py-2 text-right">{b.bets.toLocaleString('en-IN')}</td>
                      <td className="tabular px-3 py-2 text-right">{b.profit_units > 0 ? '+' : ''}{b.profit_units.toFixed(1)}</td>
                      <td className={`tabular px-5 py-2 text-right font-medium ${b.roi >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {b.roi > 0 ? '+' : ''}{(b.roi * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </>
  )
}

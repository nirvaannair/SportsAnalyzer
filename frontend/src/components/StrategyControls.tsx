import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type StrategyRow } from '../lib/api'
import { Badge, Card, CardHeader } from './ui'

const rupees = (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
const MODES: { value: StrategyRow['mode']; label: string; hint: string }[] = [
  { value: 'paper', label: 'Paper', hint: 'Simulated bets only' },
  { value: 'approve', label: 'Approve', hint: 'Real bets, each waits for your click on the Stake page' },
  { value: 'auto', label: 'Auto', hint: 'Real bets sent straight to Stake (within the caps, while Execution is ON)' },
]

function Switch({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button role="switch" aria-checked={on} onClick={() => onChange(!on)}
      className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${on ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-700'}`}>
      <span className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition-all ${on ? 'left-[18px]' : 'left-0.5'}`} />
    </button>
  )
}

/** A slider that only saves when you let go. */
function ReinvestSlider({ value, onCommit }: { value: number; onCommit: (v: number) => void }) {
  const [local, setLocal] = useState(value)
  useEffect(() => setLocal(value), [value])
  return (
    <div className="flex items-center gap-3">
      <input type="range" min={0} max={100} step={5} value={local} className="w-full accent-emerald-500"
        onChange={(e) => setLocal(Number(e.target.value))}
        onMouseUp={() => onCommit(local)} onTouchEnd={() => onCommit(local)} onKeyUp={() => onCommit(local)} />
      <span className="tabular w-10 text-right text-sm font-medium">{local}%</span>
    </div>
  )
}

function StrategyRowView({ s }: { s: StrategyRow }) {
  const queryClient = useQueryClient()
  const update = useMutation({
    mutationFn: (body: Parameters<typeof api.updateStrategy>[1]) => api.updateStrategy(s.id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  })
  const setMode = (mode: StrategyRow['mode']) => {
    if (mode !== 'paper' && mode !== s.mode) {
      const ok = window.confirm(
        `Switch "${s.name}" to ${mode.toUpperCase()} mode?\n\nThis uses REAL money on Stake` +
          (mode === 'auto' ? ', with no approval click' : '') +
          '. Bets still respect the .env caps and only go out while Execution is ON on the Stake page.',
      )
      if (!ok) return
    }
    update.mutate({ mode, confirm_real_money: mode !== 'paper' })
  }
  const b = s.bankroll
  const placedCount = (s.bets.won ?? 0) + (s.bets.lost ?? 0)

  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <Switch on={s.enabled} onChange={(v) => update.mutate({ enabled: v })} />
        <div className="min-w-0 flex-1">
          <div className="font-medium">{s.name}</div>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            {s.kind === 'kelly' ? `${s.kelly_fraction}× Kelly` : s.kind === 'multi' ? `${s.multi_legs}-leg multi · ${s.stake_pct}% of pot` : `${s.stake_pct}% of pot per bet`}
            {' '}· chances {Math.round(s.min_prob * 100)}–{Math.round(s.max_prob * 100)}% · min edge {Math.round(s.min_edge * 100)}%
            · {s.markets.join(', ')} · max {s.max_bets_per_day}/day · stop at −{s.drawdown_stop_pct}%
          </div>
        </div>
        <div className="flex rounded-lg border border-zinc-200 p-0.5 text-xs dark:border-zinc-800">
          {MODES.map((m) => (
            <button key={m.value} title={m.hint} onClick={() => setMode(m.value)}
              className={`rounded-md px-2.5 py-1 ${s.mode === m.value
                ? m.value === 'paper' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900' : 'bg-amber-500 text-white'
                : 'text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1 text-xs text-zinc-500 dark:text-zinc-400">Reinvest % of winnings (rest is banked)</div>
          <ReinvestSlider value={s.reinvest_pct} onCommit={(v) => v !== s.reinvest_pct && update.mutate({ reinvest_pct: v })} />
        </div>
        <dl className="grid grid-cols-4 gap-2 text-sm">
          {[
            ['Pot', rupees(b.pot)],
            ['Banked', rupees(b.banked)],
            ['P&L', `${b.profit >= 0 ? '+' : ''}${rupees(b.profit)}`],
            ['Bets', `${placedCount}${s.bets.open ? ` +${s.bets.open} open` : ''}`],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-zinc-500 dark:text-zinc-400">{k}</dt>
              <dd className="tabular font-medium">{v}</dd>
            </div>
          ))}
        </dl>
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200">Settings</summary>
        <StrategySettings s={s} onSave={(body) => update.mutate(body)} />
      </details>

      {s.paused_reason && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {s.paused_reason}
          <button onClick={() => update.mutate({ resume: true })} className="ml-auto flex items-center gap-1 font-medium underline-offset-2 hover:underline">
            <RotateCcw className="size-3" /> Resume
          </button>
        </div>
      )}
      {update.error && <p className="mt-2 text-xs text-rose-600">{(update.error as Error).message}</p>}
    </li>
  )
}

function NumberField({ label, value, step, onSave, suffix }: {
  label: string; value: number; step: number; onSave: (v: number) => void; suffix?: string
}) {
  const [local, setLocal] = useState(String(value))
  useEffect(() => setLocal(String(value)), [value])
  return (
    <label className="block">
      <span className="text-xs text-zinc-500 dark:text-zinc-400">{label}</span>
      <div className="mt-0.5 flex items-center gap-1">
        <input type="number" step={step} value={local} onChange={(e) => setLocal(e.target.value)}
          onBlur={() => { const v = Number(local); if (!Number.isNaN(v) && v !== value) onSave(v) }}
          className="tabular w-20 rounded-md border border-zinc-200 bg-transparent px-2 py-1 text-sm dark:border-zinc-800" />
        {suffix && <span className="text-xs text-zinc-500">{suffix}</span>}
      </div>
    </label>
  )
}

const MARKET_LABEL: Record<string, string> = { '1x2': 'Home/Draw/Away', ou25: 'Over/Under 2.5', btts: 'Both teams score' }

function StrategySettings({ s, onSave }: { s: StrategyRow; onSave: (body: Partial<StrategyRow>) => void }) {
  const pct = (v: number) => Math.round(v * 1000) / 10
  return (
    <div className="mt-2 grid grid-cols-2 gap-3 rounded-lg bg-zinc-50 p-3 sm:grid-cols-4 dark:bg-zinc-900/60">
      <NumberField label="Min chance" value={pct(s.min_prob)} step={5} suffix="%" onSave={(v) => onSave({ min_prob: v / 100 })} />
      <NumberField label="Max chance" value={pct(s.max_prob)} step={5} suffix="%" onSave={(v) => onSave({ max_prob: v / 100 })} />
      <NumberField label="Min edge" value={pct(s.min_edge)} step={1} suffix="%" onSave={(v) => onSave({ min_edge: v / 100 })} />
      {s.kind === 'kelly'
        ? <NumberField label="Kelly fraction" value={s.kelly_fraction} step={0.05} onSave={(v) => onSave({ kelly_fraction: v })} />
        : <NumberField label="Stake per bet" value={s.stake_pct} step={0.5} suffix="% of pot" onSave={(v) => onSave({ stake_pct: v })} />}
      <NumberField label="Max stake" value={s.max_stake} step={1} suffix="₹" onSave={(v) => onSave({ max_stake: v })} />
      <NumberField label="Bets per day" value={s.max_bets_per_day} step={1} onSave={(v) => onSave({ max_bets_per_day: v })} />
      <NumberField label="Drawdown stop" value={s.drawdown_stop_pct} step={5} suffix="%" onSave={(v) => onSave({ drawdown_stop_pct: v })} />
      {s.kind === 'multi' && <NumberField label="Legs" value={s.multi_legs} step={1} onSave={(v) => onSave({ multi_legs: v })} />}
      <NumberField label="Starting bankroll" value={s.bankroll_start} step={50} suffix="₹" onSave={(v) => onSave({ bankroll_start: v })} />
      <div className="col-span-2 sm:col-span-4">
        <span className="text-xs text-zinc-500 dark:text-zinc-400">Markets</span>
        <div className="mt-1 flex flex-wrap gap-3">
          {Object.entries(MARKET_LABEL).map(([key, label]) => (
            <label key={key} className="flex items-center gap-1.5 text-xs">
              <input type="checkbox" checked={s.markets.includes(key)}
                onChange={(e) => {
                  const next = e.target.checked ? [...s.markets, key] : s.markets.filter((m) => m !== key)
                  if (next.length) onSave({ markets: next })
                }} />
              {label}
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function StrategyControls() {
  const queryClient = useQueryClient()
  const strategies = useQuery({ queryKey: ['strategies'], queryFn: api.strategies, refetchInterval: 10000 })
  const automation = useQuery({ queryKey: ['automation'], queryFn: api.automation, refetchInterval: 15000 })
  const run = useMutation({
    mutationFn: api.runStrategies,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] })
      queryClient.invalidateQueries({ queryKey: ['ledger'] })
    },
  })
  const a = automation.data
  const live = (strategies.data ?? []).filter((s) => s.enabled && s.mode !== 'paper')

  return (
    <Card>
      <CardHeader
        title="Strategies"
        aside={
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            {live.length > 0 && <Badge tone="warn">{live.length} on real money</Badge>}
            <span title={a?.last_error ? a.last_error.error : undefined}>
              {a?.last_cycle ? `Last run ${new Date(a.last_cycle.at).toLocaleTimeString()}` : 'Automation starting…'}
              {a?.last_error ? ' · error' : ''}
            </span>
            <button onClick={() => run.mutate()} disabled={run.isPending}
              className="flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:hover:bg-zinc-800">
              <Play className="size-3" /> Run now
            </button>
          </div>
        }
      />
      <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {(strategies.data ?? []).map((s) => <StrategyRowView key={s.id} s={s} />)}
      </ul>
      <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        Every 15 minutes the app settles finished bets and lets switched-on strategies pick new ones from the model's
        predictions. Paper bets are simulated. Approve and Auto use real money on Stake and stay within your .env caps.
      </p>
    </Card>
  )
}

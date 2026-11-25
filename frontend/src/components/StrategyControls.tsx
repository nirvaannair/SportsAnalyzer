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
            {s.kind === 'kelly' ? `${s.kelly_fraction}× Kelly` : `${s.stake_pct}% of pot per bet`} · min edge {Math.round(s.min_edge * 100)}%
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

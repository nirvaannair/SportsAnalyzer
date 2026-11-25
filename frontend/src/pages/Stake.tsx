import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CircleDot, GraduationCap, Plug, Power, Search, X } from 'lucide-react'
import { useState } from 'react'
import { Badge, Card, CardHeader, EmptyState, PageHeader, StatusDot } from '../components/ui'
import StakeBets from '../components/StakeBets'
import { api, type StakeOrder } from '../lib/api'

const ORDER_TONE: Record<string, 'ok' | 'warn' | 'off' | 'bad'> = {
  pending_approval: 'warn', approved: 'warn', sent: 'warn', placed: 'ok', failed: 'bad', blocked: 'bad', rejected: 'off',
}
const ORDER_LABEL: Record<string, string> = {
  pending_approval: 'Needs your approval', approved: 'Approved, waiting for helper', sent: 'Sent to Stake',
  placed: 'Placed', failed: 'Failed', blocked: 'Blocked by a limit', rejected: 'Rejected',
}
const rupees = (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-40 ${on ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-700'}`}
    >
      <span className={`absolute top-0.5 size-5 rounded-full bg-white shadow transition-all ${on ? 'left-[22px]' : 'left-0.5'}`} />
    </button>
  )
}

function OrderRow({ o }: { o: StakeOrder }) {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['stake'] })
  const approve = useMutation({ mutationFn: () => api.stakeApprove(o.id), onSuccess: refresh })
  const reject = useMutation({ mutationFn: () => api.stakeReject(o.id), onSuccess: refresh })
  return (
    <li className="px-5 py-3 text-sm">
      <div className="flex items-start gap-3">
        <span className="mt-1.5"><StatusDot tone={ORDER_TONE[o.status] ?? 'off'} /></span>
        <div className="min-w-0 flex-1">
          <div className="font-medium">{o.description}</div>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            #{o.id} · {rupees(o.amount)} · {ORDER_LABEL[o.status] ?? o.status}
            {o.stake_bet_id && ` · Stake bet ${o.stake_bet_id}`}
          </div>
          {o.status_detail && <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{o.status_detail}</div>}
        </div>
        {o.status === 'pending_approval' && (
          <div className="flex gap-1.5">
            <button onClick={() => approve.mutate()} disabled={approve.isPending}
              className="flex items-center gap-1 rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-700">
              <Check className="size-3.5" /> Approve
            </button>
            <button onClick={() => reject.mutate()} className="rounded-md px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800">
              <X className="size-3.5" />
            </button>
          </div>
        )}
        {o.status === 'approved' && (
          <button onClick={() => reject.mutate()} className="rounded-md px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800">Cancel</button>
        )}
      </div>
    </li>
  )
}

export default function Stake() {
  const queryClient = useQueryClient()
  const status = useQuery({ queryKey: ['stake', 'status'], queryFn: api.stakeStatus, refetchInterval: 3000 })
  const orders = useQuery({ queryKey: ['stake', 'orders'], queryFn: api.stakeOrders, refetchInterval: 3000 })
  const [q, setQ] = useState('')
  const [allMarkets, setAllMarkets] = useState(false)
  const outcomes = useQuery({
    queryKey: ['stake', 'outcomes', q, allMarkets],
    queryFn: () => api.stakeOutcomes(q, !allMarkets),
    refetchInterval: 5000,
  })
  const settings = useMutation({
    mutationFn: api.stakeSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stake'] }),
  })
  const create = useMutation({
    mutationFn: (outcomeId: string) => api.stakeCreateOrder(outcomeId, s?.limits.max_bet ?? 1),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stake'] }),
  })

  const s = status.data
  const h = s?.helper
  const inr = h?.balances?.available?.[s?.limits.currency ?? 'inr']

  return (
    <>
      <PageHeader
        title="Stake"
        description="Real-money bets go out only from your own Stake tab through the helper, only when you approve them, and never past the limits below."
        actions={s?.execution_enabled ? <Badge tone="warn">Execution ON</Badge> : <Badge>Execution off</Badge>}
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <Card className="px-5 py-4">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            <Plug className="size-3.5" /> Helper
          </div>
          <div className="mt-2 flex items-center gap-2 text-lg font-semibold">
            <StatusDot tone={h?.connected ? 'ok' : 'off'} /> {h?.connected ? 'Connected' : 'Not connected'}
          </div>
          <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {h?.connected ? `${h.host} · v${h.version}` : 'Open stake.com in Chrome with the helper installed'}
          </div>
        </Card>
        <Card className="px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Stake balance</div>
          <div className="tabular mt-2 text-2xl font-semibold">{inr === undefined ? '—' : rupees(inr)}</div>
          <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{h?.error ? h.error.slice(0, 80) : 'Read from your Stake tab'}</div>
        </Card>
        <Card className="px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Test budget left</div>
          <div className="tabular mt-2 text-2xl font-semibold">{s ? rupees(s.budget_left) : '…'}</div>
          <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {s ? `${rupees(s.spent_total)} of ${rupees(s.limits.budget)} used` : ''}
          </div>
        </Card>
        <Card className="px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Limits</div>
          <div className="tabular mt-2 text-sm">
            {s ? `${rupees(s.limits.max_bet)} per bet · ${s.limits.max_bets_per_day}/day · approval above ${rupees(s.limits.approval_above)}` : '…'}
          </div>
          <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{s ? `${s.bets_today} sent today · change in .env` : ''}</div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Switches" />
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            <div className="flex items-start gap-4 px-5 py-4">
              <GraduationCap className="mt-0.5 size-5 text-zinc-400" />
              <div className="flex-1 text-sm">
                <div className="font-medium">Learn mode</div>
                <p className="mt-0.5 text-zinc-500 dark:text-zinc-400">
                  The helper copies the shape of Stake's requests and the markets on pages you open. To teach it how
                  betting works, place <b>one ₹1 bet by hand</b> on Stake while this is on.
                </p>
                {s?.learn_mode && h?.connected && (
                  <div className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                    {h.hook
                      ? `Listener: saw ${h.hook.fetchSeen + h.hook.xhrSeen} Stake requests in this tab · learned ${h.hook.captured}` +
                        (h.hook.unreadable ? ` · ${h.hook.unreadable} unreadable` : '')
                      : 'Listener not reporting. Reload the extension, then the Stake tab.'}
                  </div>
                )}
                <div className="mt-2 space-y-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                  <div>{s?.multi_request_learned ? '✓ Multi bets learned' : '○ Multi bets: place one multi by hand'}</div>
                  <div>{s?.bet_list_learned ? '✓ My Bets list learned' : '○ My Bets: open My Bets → Sports → Active'}</div>
                  <div>{s?.cashout_request_learned ? '✓ Cash-out learned' : '○ Cash-out: cash out one bet by hand'}</div>
                </div>
                <div className="mt-2 text-xs">
                  {s?.bet_request_learned
                    ? <span className="text-emerald-600 dark:text-emerald-400">✓ Bet request learned ({s.bet_operation})</span>
                    : <span className="text-amber-600 dark:text-amber-400">Bet request not learned yet</span>}
                </div>
              </div>
              <Toggle on={Boolean(s?.learn_mode)} onChange={(v) => settings.mutate({ learn_mode: v })} />
            </div>
            <div className="flex items-start gap-4 px-5 py-4">
              <Power className="mt-0.5 size-5 text-zinc-400" />
              <div className="flex-1 text-sm">
                <div className="font-medium">Execution</div>
                <p className="mt-0.5 text-zinc-500 dark:text-zinc-400">
                  When on, the helper places bets you <b>approved</b>, within the limits. Turn off at any time to stop
                  immediately; approved bets then wait.
                </p>
              </div>
              <Toggle on={Boolean(s?.execution_enabled)} onChange={(v) => settings.mutate({ execution_enabled: v })} />
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Bets" aside={<span className="text-xs text-zinc-500">Newest first</span>} />
          {(orders.data ?? []).length === 0 ? (
            <EmptyState icon={<CircleDot className="size-6" />} title="No bets yet"
              body="Pick an outcome below to create a ₹1 test bet. It waits for your approval." />
          ) : (
            <ul className="max-h-[420px] divide-y divide-zinc-100 overflow-auto dark:divide-zinc-800">
              {(orders.data ?? []).map((o) => <OrderRow key={o.id} o={o} />)}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <StakeBets listLearned={Boolean(s?.bet_list_learned)} />
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Outcomes seen on Stake"
          aside={
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs text-zinc-500">
                <input type="checkbox" checked={allMarkets} onChange={(e) => setAllMarkets(e.target.checked)} /> All markets &amp; sports
              </label>
              <label className="flex items-center gap-2 rounded-lg border border-zinc-200 px-2 py-1 text-xs dark:border-zinc-800">
                <Search className="size-3.5 text-zinc-400" />
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Team or market" className="w-36 bg-transparent outline-none" />
              </label>
            </div>
          }
        />
        <p className="px-5 pt-3 text-xs text-zinc-500 dark:text-zinc-400">
          With Learn mode on, open a match on Stake and its markets appear here. Prices are Stake's, used only as the
          bet's payout, never by the prediction models.
        </p>
        {create.error && <p className="px-5 pt-2 text-sm text-rose-600">{(create.error as Error).message}</p>}
        {(outcomes.data ?? []).length === 0 ? (
          <EmptyState icon={<Search className="size-6" />} title="Nothing yet" body="Turn on Learn mode, then open any football match on Stake." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  <th className="px-5 py-2 font-medium">Match</th>
                  <th className="px-3 py-2 font-medium">Kickoff</th>
                  <th className="px-3 py-2 font-medium">Market</th>
                  <th className="px-3 py-2 font-medium">Outcome</th>
                  <th className="px-3 py-2 text-right font-medium">Price</th>
                  <th className="px-5 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {(outcomes.data ?? []).map((o) => (
                  <tr key={o.outcome_id}>
                    <td className="px-5 py-2">
                      <div className="flex items-center gap-2">
                        {o.league && <Badge>{o.league}</Badge>}
                        <span>{o.fixture ?? '—'}</span>
                        {o.match_id && <span title="Linked to our match: predictions can be compared" className="text-emerald-600 dark:text-emerald-400">●</span>}
                      </div>
                    </td>
                    <td className="tabular whitespace-nowrap px-3 py-2 text-zinc-500 dark:text-zinc-400">
                      {o.start_time ? new Date(o.start_time).toLocaleString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-zinc-500 dark:text-zinc-400">{o.market ?? "—"}</td>
                    <td className="px-3 py-2 font-medium">{o.name}</td>
                    <td className="tabular px-3 py-2 text-right">{o.price?.toFixed(2) ?? '—'}</td>
                    <td className="px-5 py-2 text-right">
                      <button onClick={() => create.mutate(o.outcome_id)} disabled={create.isPending || o.active === false}
                        className="whitespace-nowrap rounded-md border border-zinc-200 px-2.5 py-1 text-xs hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:hover:bg-zinc-800">
                        {rupees(s?.limits.max_bet ?? 1)} test bet
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

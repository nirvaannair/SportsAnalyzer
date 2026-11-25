import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ticket } from 'lucide-react'
import { api } from '../lib/api'
import { Card, CardHeader, EmptyState } from './ui'

const rupees = (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

/** Your open bets as Stake reports them: legs, potential payout, and cash-out availability. */
export default function StakeBets({ listLearned }: { listLearned: boolean }) {
  const queryClient = useQueryClient()
  const bets = useQuery({ queryKey: ['stake', 'bets'], queryFn: api.stakeBets, refetchInterval: 15000 })
  const cashout = useMutation({
    mutationFn: (id: string) => api.cashout(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stake'] }),
  })
  const rows = bets.data ?? []

  return (
    <Card>
      <CardHeader title="Your Stake bets" aside={<span className="text-xs text-zinc-500">Open bets · refreshed every minute</span>} />
      {!listLearned ? (
        <EmptyState icon={<Ticket className="size-6" />} title="Not connected to My Bets yet"
          body="With Learn mode on, open My Bets → Sports → Active on Stake once. The helper then keeps this list up to date." />
      ) : rows.length === 0 ? (
        <EmptyState icon={<Ticket className="size-6" />} title="No open bets" body="Open sports bets on Stake appear here." />
      ) : (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rows.map((b) => (
            <li key={b.id} className="flex gap-4 px-5 py-3 text-sm">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{b.title}</div>
                <div className="tabular text-xs text-zinc-500 dark:text-zinc-400">
                  Staked {rupees(b.amount)} · pays {b.potential_payout == null ? '—' : rupees(b.potential_payout)}
                </div>
                <ul className="mt-1.5 space-y-0.5 text-xs text-zinc-600 dark:text-zinc-300">
                  {b.legs.map((leg, i) => (
                    <li key={i} className="flex gap-2">
                      <span className={leg.open ? 'text-emerald-500' : 'text-zinc-400'} title={leg.open ? 'Market open' : 'Market suspended'}>●</span>
                      <span className="min-w-0 truncate">
                        <span className="font-medium">{leg.selection}</span>
                        <span className="text-zinc-500 dark:text-zinc-400"> · {leg.market} · {leg.fixture}</span>
                      </span>
                      <span className="tabular ml-auto whitespace-nowrap text-zinc-500">
                        @ {leg.odds_at_bet?.toFixed(2)}{leg.current_odds && leg.current_odds !== leg.odds_at_bet ? ` → ${leg.current_odds.toFixed(2)} now` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="w-36 shrink-0 text-right">
                {b.cashout_available ? (
                  <>
                    <div className="tabular font-medium">≈ {b.cashout_estimate == null ? '—' : rupees(b.cashout_estimate)}</div>
                    <div className="text-xs text-zinc-500">cash-out estimate</div>
                    <button
                      disabled={cashout.isPending}
                      onClick={() => {
                        const msg = `Cash out "${b.title}"?

The helper opens this bet in your Stake tab and presses Stake's own ` +
                          `Cashout button, so you get Stake's exact amount at that moment` +
                          (b.cashout_estimate == null ? '.' : ` (estimate ≈ ${rupees(b.cashout_estimate)}).`)
                        if (window.confirm(msg)) cashout.mutate(b.id)
                      }}
                      className="mt-1.5 rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:hover:bg-zinc-800"
                    >
                      Cash out
                    </button>
                  </>
                ) : (
                  <>
                    <div className="text-zinc-400">Not available</div>
                    <div className="text-xs text-zinc-500">{b.cashout_reason}</div>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {cashout.error && <p className="px-5 pb-3 text-sm text-rose-600">{(cashout.error as Error).message}</p>}
      <p className="border-t border-zinc-100 px-5 py-2.5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        The figure here is an estimate; Stake calculates the exact amount live on its own page. Cash out opens the bet in
        your Stake tab and presses Stake's own Cashout button, so the exact amount is always Stake's. The result appears
        under Bets.
      </p>
    </Card>
  )
}

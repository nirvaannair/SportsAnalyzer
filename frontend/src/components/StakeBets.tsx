import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ticket } from 'lucide-react'
import { api } from '../lib/api'
import { Card, CardHeader, EmptyState } from './ui'

const rupees = (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

/** Your open bets as Stake reports them, with live cash-out values and a Cash out button. */
export default function StakeBets({ listLearned, cashoutLearned }: { listLearned: boolean; cashoutLearned: boolean }) {
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
          body="With Learn mode on, open My Bets → Sports → Active on Stake once. The helper then keeps this list (stakes, potential payouts, cash-out values) up to date." />
      ) : rows.length === 0 ? (
        <EmptyState icon={<Ticket className="size-6" />} title="No open bets" body="Open sports bets on Stake appear here." />
      ) : (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rows.map((b) => (
            <li key={b.id} className="flex items-center gap-4 px-5 py-3 text-sm">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{b.description ?? b.id}</div>
                <div className="tabular text-xs text-zinc-500 dark:text-zinc-400">
                  Staked {rupees(b.amount)} · pays {b.potential_payout == null ? '—' : rupees(b.potential_payout)}
                </div>
              </div>
              <div className="text-right">
                <div className="tabular font-medium">{b.cashout_value == null ? '—' : rupees(b.cashout_value)}</div>
                <div className="text-xs text-zinc-500">cash-out now</div>
              </div>
              <button
                disabled={!b.cashout_available || !cashoutLearned || cashout.isPending}
                title={!cashoutLearned ? 'Cash out one bet by hand on Stake with Learn mode on first' : undefined}
                onClick={() => {
                  if (window.confirm(`Cash out "${b.description ?? b.id}" for about ${b.cashout_value == null ? '?' : rupees(b.cashout_value)}?`)) {
                    cashout.mutate(b.id)
                  }
                }}
                className="whitespace-nowrap rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-800 dark:hover:bg-zinc-800"
              >
                Cash out
              </button>
            </li>
          ))}
        </ul>
      )}
      {cashout.error && <p className="px-5 pb-3 text-sm text-rose-600">{(cashout.error as Error).message}</p>}
    </Card>
  )
}

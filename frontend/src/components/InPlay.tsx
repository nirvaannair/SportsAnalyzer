import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Card, CardHeader } from './ui'
import { refresh } from '../lib/settings'

const rupees = (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

/** What's riding right now, and what it would pay if everything wins. */
export default function InPlay() {
  const exposure = useQuery({ queryKey: ['exposure'], queryFn: api.exposure, refetchInterval: refresh('normal') })
  const e = exposure.data
  const rows: [string, string, number, number][] = e
    ? [
        ['On Stake now', `${e.real.bets} bets`, e.real.stake, e.real.potential_payout],
        ['Waiting to go out', `${e.pending_orders.count} orders`, e.pending_orders.stake, e.pending_orders.potential_payout],
        ['Paper (simulated)', `${e.paper.bets} bets`, e.paper.stake, e.paper.potential_payout],
      ]
    : []
  return (
    <Card>
      <CardHeader title="In play" aside={<span className="text-xs text-zinc-500">If every bet wins</span>} />
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            <th className="px-5 py-2 font-medium" />
            <th className="px-3 py-2 text-right font-medium">Staked</th>
            <th className="px-5 py-2 text-right font-medium">Est. payout</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rows.map(([label, sub, stake, payout]) => (
            <tr key={label}>
              <td className="px-5 py-2.5">
                <div className="font-medium">{label}</div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400">{sub}</div>
              </td>
              <td className="tabular px-3 py-2.5 text-right">{rupees(stake)}</td>
              <td className="tabular px-5 py-2.5 text-right font-medium">{rupees(payout)}</td>
            </tr>
          ))}
          {!e && <tr><td colSpan={3} className="px-5 py-4 text-center text-zinc-500">Loading…</td></tr>}
        </tbody>
      </table>
      <p className="border-t border-zinc-100 px-5 py-2.5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        "On Stake now" is read from your own My Bets list by the helper every minute; settled bets drop off automatically.
      </p>
    </Card>
  )
}

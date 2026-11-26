import { useQuery } from '@tanstack/react-query'
import { Receipt } from 'lucide-react'
import { useState } from 'react'
import { Badge, Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { refresh } from '../lib/settings'

const STATUS_TONE: Record<string, 'neutral' | 'accent' | 'warn'> = { open: 'warn', won: 'accent', lost: 'neutral', void: 'neutral' }
const SELECTION_LABEL: Record<string, string> = {
  home: 'Home', draw: 'Draw', away: 'Away', over: 'Over 2.5', under: 'Under 2.5', yes: 'BTTS yes', no: 'BTTS no',
}
const rupees = (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`

export default function Ledger() {
  const [status, setStatus] = useState('')
  const bets = useQuery({ queryKey: ['ledger', status], queryFn: () => api.ledger(status), refetchInterval: refresh('normal') })
  const rows = bets.data ?? []
  const settled = rows.filter((b) => b.status === 'won' || b.status === 'lost')
  const profit = settled.reduce((sum, b) => sum + (b.profit ?? 0), 0)
  const staked = settled.reduce((sum, b) => sum + b.stake, 0)

  return (
    <>
      <PageHeader
        title="Bet ledger"
        description="Every bet a strategy made: the model's probability, the price it took and the result. Paper bets are simulated."
        actions={
          <select value={status} onChange={(e) => setStatus(e.target.value)}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm dark:border-zinc-800 dark:bg-zinc-900">
            <option value="">All bets</option>
            <option value="open">Open</option>
            <option value="won">Won</option>
            <option value="lost">Lost</option>
            <option value="void">Void</option>
          </select>
        }
      />
      <Card>
        <CardHeader
          title={`${rows.length} bets`}
          aside={settled.length > 0 && (
            <span className="tabular text-xs text-zinc-500">
              Settled P&L {profit >= 0 ? '+' : ''}{rupees(profit)} · ROI {staked ? ((profit / staked) * 100).toFixed(1) : '0'}%
            </span>
          )}
        />
        {rows.length === 0 ? (
          <EmptyState icon={<Receipt className="size-6" />} title="No bets yet"
            body="Switch a strategy on in the Overview page (Paper mode is simulated). New bets appear here within 15 minutes, or click Run now." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  <th className="px-5 py-2.5 font-medium">Match</th>
                  <th className="px-3 py-2.5 font-medium">Bet</th>
                  <th className="px-3 py-2.5 text-right font-medium">Model</th>
                  <th className="px-3 py-2.5 text-right font-medium">Price</th>
                  <th className="px-3 py-2.5 text-right font-medium">Edge</th>
                  <th className="px-3 py-2.5 text-right font-medium">Stake</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="px-5 py-2.5 text-right font-medium">P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {rows.map((b) => (
                  <tr key={b.id}>
                    <td className="px-5 py-2.5">
                      <div className="font-medium">{b.match}{b.score && <span className="ml-2 text-zinc-500">{b.score}</span>}</div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">
                        {new Date(b.kickoff_at ?? b.date).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })} · {b.strategy}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="whitespace-nowrap">
                        {b.market === 'multi' ? `Multi · ${b.selection}` : SELECTION_LABEL[b.selection] ?? b.selection}
                        <span className="ml-2 text-xs text-zinc-500">{b.mode}</span>
                      </div>
                      {b.legs && (
                        <ul className="mt-1 space-y-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                          {b.legs.map((leg, i) => (
                            <li key={i}>match #{leg.match_id} · {SELECTION_LABEL[leg.selection] ?? leg.selection} @ {leg.price.toFixed(2)}</li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right">{Math.round(b.p_model * 100)}%</td>
                    <td className="tabular px-3 py-2.5 text-right" title={b.price_source === 'stake' ? "Stake's price" : 'Market average (paper only)'}>
                      {b.price.toFixed(2)}{b.price_source === 'stake' ? '' : '*'}
                    </td>
                    <td className="tabular px-3 py-2.5 text-right">{(b.edge * 100).toFixed(0)}%</td>
                    <td className="tabular px-3 py-2.5 text-right">{rupees(b.stake)}</td>
                    <td className="px-3 py-2.5">
                      <Badge tone={STATUS_TONE[b.status] ?? 'neutral'}>{b.status}</Badge>
                      {b.order_status && <span className="ml-2 text-xs text-zinc-500">Stake: {b.order_status}</span>}
                    </td>
                    <td className={`tabular px-5 py-2.5 text-right font-medium ${b.profit == null ? 'text-zinc-400' : b.profit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                      {b.profit == null ? '—' : `${b.profit >= 0 ? '+' : ''}${rupees(b.profit)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          * market-average price (paper bets on matches not yet linked to Stake). Prices are payouts only; the model never sees them.
        </p>
      </Card>
    </>
  )
}

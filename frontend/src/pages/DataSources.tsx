import { useQuery } from '@tanstack/react-query'
import { Badge, Card, CardHeader, PageHeader, StatusDot } from '../components/ui'
import { api } from '../lib/api'

function relative(iso: string | null) {
  if (!iso) return 'Never'
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h ago`
  return `${Math.round(minutes / 1440)} d ago`
}

export default function DataSources() {
  const providers = useQuery({ queryKey: ['providers'], queryFn: api.providers })

  return (
    <>
      <PageHeader title="Data sources" description="API keys, stored data and sync state for each provider." />
      <Card>
        <CardHeader title="Providers" aside={<span className="text-xs text-zinc-500">Refreshes every 15 s</span>} />
        {providers.isError ? (
          <p className="px-5 py-6 text-sm text-rose-600">Could not reach the API. Is the backend running on port 8000?</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                <th className="px-5 py-2.5 font-medium">Provider</th>
                <th className="px-5 py-2.5 font-medium">Key</th>
                <th className="px-5 py-2.5 text-right font-medium">Observations</th>
                <th className="px-5 py-2.5 text-right font-medium">Last received</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {(providers.data ?? []).map((p) => (
                <tr key={p.name}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2.5">
                      <StatusDot tone={p.configured ? 'ok' : 'off'} />
                      <span className="font-medium">{p.label}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    {p.configured ? <Badge tone="accent">Configured</Badge> : <Badge>Missing</Badge>}
                  </td>
                  <td className="tabular px-5 py-3 text-right">{p.observations.toLocaleString('en-IN')}</td>
                  <td className="px-5 py-3 text-right text-zinc-500 dark:text-zinc-400">{relative(p.last_received_at)}</td>
                </tr>
              ))}
              {providers.isLoading && (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-zinc-500">Loading…</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}

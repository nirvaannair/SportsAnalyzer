import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, GitMerge, X } from 'lucide-react'
import { Badge, Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api, type PendingMapping } from '../lib/api'

const PROVIDER_LABEL: Record<string, string> = {
  fdcuk: 'football-data.co.uk',
  api_football: 'API-Football',
  football_data: 'football-data.org',
  thesportsdb: 'TheSportsDB',
}

const METHOD_LABEL: Record<string, string> = {
  deterministic_rule: 'Seed source',
  composite_score: 'Matched by results',
  name_and_context: 'Matched by name',
  manual_override: 'Matched by you',
}

function pct(value: number | null) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}

function PendingRow({ item }: { item: PendingMapping }) {
  const queryClient = useQueryClient()
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['identity'] })
    queryClient.invalidateQueries({ queryKey: ['summary'] })
  }
  const resolve = useMutation({ mutationFn: (teamId: number) => api.resolveMapping(item.id, teamId), onSuccess: refresh })
  const reject = useMutation({ mutationFn: () => api.rejectMapping(item.id), onSuccess: refresh })
  const error = (resolve.error ?? reject.error) as Error | null

  return (
    <li className="px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-medium">{item.label}</div>
          <div className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            {PROVIDER_LABEL[item.provider] ?? item.provider} · id {item.provider_id} · {item.country} · {item.fixtures} fixtures as evidence
          </div>
        </div>
        <button
          onClick={() => reject.mutate()}
          disabled={reject.isPending}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          title="Not one of our teams (for example a cup opponent)"
        >
          <X className="size-3.5" /> Not ours
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {item.candidates.map((c) => (
          <button
            key={c.team_id}
            onClick={() => resolve.mutate(c.team_id)}
            disabled={resolve.isPending}
            className="group flex items-center gap-2 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm hover:border-emerald-500 hover:bg-emerald-50 dark:border-zinc-800 dark:hover:border-emerald-700 dark:hover:bg-emerald-950"
          >
            <Check className="size-3.5 text-zinc-300 group-hover:text-emerald-600 dark:text-zinc-600" />
            <span className="font-medium">{c.name}</span>
            <span className="tabular text-xs text-zinc-500" title="Share of this team's results that line up · name similarity">
              {pct(c.fixture_score)} · {pct(c.name_score)}
            </span>
          </button>
        ))}
        {item.candidates.length === 0 && (
          <span className="text-sm text-zinc-500">No candidate teams in {item.country} yet.</span>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-rose-600">{error.message}</p>}
    </li>
  )
}

export default function IdentityReview() {
  const review = useQuery({ queryKey: ['identity'], queryFn: api.identityReview })
  const pending = review.data?.pending ?? []
  const resolvedCounts = (review.data?.counts ?? []).filter((c) => c.status === 'active')

  return (
    <>
      <PageHeader
        title="Identity review"
        description="Each provider names and numbers teams differently. Teams that could not be matched automatically wait here."
        actions={pending.length > 0 ? <Badge tone="warn">{pending.length} to review</Badge> : <Badge tone="accent">All matched</Badge>}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Needs review"
            aside={<span className="text-xs text-zinc-500">Click the right team · scores: results matched · name</span>}
          />
          {pending.length === 0 ? (
            <EmptyState
              icon={<GitMerge className="size-6" />}
              title={review.isLoading ? 'Loading…' : 'Nothing to review'}
              body="Teams from new providers appear here when results and names are not enough to match them with confidence."
            />
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {pending.map((item) => <PendingRow key={item.id} item={item} />)}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Matched teams" />
          <dl className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
            {resolvedCounts.map((c) => (
              <div key={`${c.provider}-${c.method}`} className="flex justify-between gap-3 px-5 py-3">
                <dt>
                  <div>{PROVIDER_LABEL[c.provider] ?? c.provider}</div>
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">{METHOD_LABEL[c.method ?? ''] ?? c.method}</div>
                </dt>
                <dd className="tabular font-medium">{c.count}</dd>
              </div>
            ))}
            {resolvedCounts.length === 0 && <div className="px-5 py-3 text-zinc-500">None yet</div>}
          </dl>
        </Card>
      </div>
    </>
  )
}

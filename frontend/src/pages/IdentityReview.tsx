import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, GitMerge, Info, X } from 'lucide-react'
import { Badge, Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api, type Candidate, type PendingMapping } from '../lib/api'

const PROVIDER_LABEL: Record<string, string> = {
  fdcuk: 'football-data.co.uk',
  api_football: 'API-Football',
  football_data: 'football-data.org',
  thesportsdb: 'TheSportsDB',
}

const METHOD_LABEL: Record<string, string> = {
  deterministic_rule: 'Our reference list of teams',
  composite_score: 'Matched by shared results',
  name_and_context: 'Matched by identical name',
  manual_override: 'Matched by you',
}

/** How many of the provider team's results also appear for this candidate. */
function resultsMatched(c: Candidate, fixtures: number) {
  if (c.fixture_score == null || fixtures === 0) return 'no results to compare'
  return `${Math.round(c.fixture_score * fixtures)} of ${fixtures} results match`
}

function verdict(item: PendingMapping) {
  const best = item.candidates[0]
  if (!best) return { text: `There are no teams from ${item.country} in our leagues to compare it with.`, likelyOutside: true }
  if (item.fixtures > 0 && (best.fixture_score ?? 0) === 0) {
    return {
      text: `None of its ${item.fixtures} matches appear in our data, so it is most likely a club from outside our 10 leagues (for example a play-off or cup opponent).`,
      likelyOutside: true,
    }
  }
  return {
    text: 'Its results partly line up with a team below, but not clearly enough to decide automatically.',
    likelyOutside: false,
  }
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
  const { text, likelyOutside } = verdict(item)
  const provider = PROVIDER_LABEL[item.provider] ?? item.provider

  return (
    <li className="space-y-4 px-5 py-5">
      <div>
        <div className="text-[15px] font-semibold">{item.label}</div>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">
          {provider} has a team called <span className="font-medium">{item.label}</span> ({item.country}) that
          SportsAnalyzer could not match to any team it knows.
        </p>
        <p className="mt-2 flex gap-2 text-sm text-zinc-500 dark:text-zinc-400">
          <Info className="mt-0.5 size-4 shrink-0" /> {text}
        </p>
      </div>

      <div>
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Your answer
        </div>
        <button
          onClick={() => reject.mutate()}
          disabled={reject.isPending}
          className={`mb-2 flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm ${
            likelyOutside
              ? 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 dark:hover:bg-emerald-900'
              : 'border-zinc-200 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/50'
          }`}
        >
          <X className="size-4" />
          <span className="font-medium">It isn't one of our teams. Ignore it.</span>
          {likelyOutside && <span className="ml-auto text-xs">Suggested</span>}
        </button>

        <div className="mb-1.5 mt-3 text-xs text-zinc-500 dark:text-zinc-400">Or it's the same club as:</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {item.candidates.map((c) => (
            <button
              key={c.team_id}
              onClick={() => resolve.mutate(c.team_id)}
              disabled={resolve.isPending}
              className="group flex items-center gap-2.5 rounded-lg border border-zinc-200 px-3 py-2 text-left text-sm hover:border-emerald-500 hover:bg-emerald-50 dark:border-zinc-800 dark:hover:border-emerald-700 dark:hover:bg-emerald-950"
            >
              <Check className="size-4 shrink-0 text-zinc-300 group-hover:text-emerald-600 dark:text-zinc-600" />
              <span>
                <span className="block font-medium">{c.name}</span>
                <span className="block text-xs text-zinc-500 dark:text-zinc-400">
                  {resultsMatched(c, item.fixtures)} · name {Math.round(c.name_score * 100)}% similar
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-sm text-rose-600">{error.message}</p>}
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
        description="Data providers use different names and IDs for the same club (“Man United”, “Manchester United FC”, id 33). SportsAnalyzer links them automatically by comparing results; when it can't be sure, it asks you here."
        actions={pending.length > 0 ? <Badge tone="warn">{pending.length} to review</Badge> : <Badge tone="accent">All matched</Badge>}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Needs your answer" />
          {pending.length === 0 ? (
            <EmptyState
              icon={<GitMerge className="size-6" />}
              title={review.isLoading ? 'Loading…' : 'Nothing to review'}
              body="When a new provider mentions a club that can't be matched with confidence, it appears here."
            />
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {pending.map((item) => <PendingRow key={item.id} item={item} />)}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Already linked" />
          <dl className="divide-y divide-zinc-100 text-sm dark:divide-zinc-800">
            {resolvedCounts.map((c) => (
              <div key={`${c.provider}-${c.method}`} className="flex justify-between gap-3 px-5 py-3">
                <dt>
                  <div>{PROVIDER_LABEL[c.provider] ?? c.provider}</div>
                  <div className="text-xs text-zinc-500 dark:text-zinc-400">{METHOD_LABEL[c.method ?? ''] ?? c.method}</div>
                </dt>
                <dd className="tabular whitespace-nowrap font-medium">{c.count} {c.count === 1 ? 'team' : 'teams'}</dd>
              </div>
            ))}
            {resolvedCounts.length === 0 && <div className="px-5 py-3 text-zinc-500">None yet</div>}
          </dl>
        </Card>
      </div>
    </>
  )
}

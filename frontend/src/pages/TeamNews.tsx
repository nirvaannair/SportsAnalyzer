import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Newspaper } from 'lucide-react'
import { useState } from 'react'
import { Guide, VerdictBadge } from '../components/Guide'
import { Card, CardHeader, EmptyState, PageHeader } from '../components/ui'
import { api } from '../lib/api'

const LEAGUES = [
  ['', 'All leagues'], ['ENG1', 'Premier League'], ['ENG2', 'Championship'], ['ESP1', 'La Liga'], ['ESP2', 'Segunda'],
  ['ITA1', 'Serie A'], ['ITA2', 'Serie B'], ['GER1', 'Bundesliga'], ['GER2', '2. Bundesliga'], ['FRA1', 'Ligue 1'], ['FRA2', 'Ligue 2'],
] as const
const control = 'rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900'

function Mood({ value }: { value: number | null }) {
  if (value === null) return <span className="text-zinc-400">—</span>
  const verdict = value > 0.15 ? 'good' : value < -0.15 ? 'bad' : 'medium'
  const label = value > 0.15 ? 'Positive' : value < -0.15 ? 'Negative' : 'Mixed'
  return <span className="inline-flex items-center gap-2"><span className="tabular text-xs text-zinc-500">{value > 0 ? '+' : ''}{value.toFixed(2)}</span><VerdictBadge verdict={verdict} label={label} /></span>
}

function ago(iso: string) {
  const h = Math.round((Date.now() - new Date(iso).getTime()) / 3_600_000)
  return h < 1 ? 'just now' : h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`
}

export default function TeamNews() {
  const [league, setLeague] = useState('')
  const [team, setTeam] = useState<{ id: number; name: string } | null>(null)
  const [injuryOnly, setInjuryOnly] = useState(false)
  const mood = useQuery({ queryKey: ['news', 'teams', league], queryFn: () => api.newsTeams(league), refetchInterval: 60000 })
  const articles = useQuery({
    queryKey: ['news', 'articles', league, team?.id, injuryOnly],
    queryFn: () => api.newsArticles({ league, team_id: team?.id, injury: injuryOnly || undefined }),
    refetchInterval: 60000,
  })
  const total = mood.data?.total_articles ?? 0
  const since = mood.data?.collecting_since

  return (
    <>
      <PageHeader title="Team news" description="Football news for the 10 leagues, read automatically every hour: good or bad news for each team, and injuries." />
      <Guide items={[
        {
          title: 'News mood (last 7 days)',
          body: 'Every headline and summary is scored from −1 (bad news: defeats, crisis, injuries, sackings) to +1 (good news: wins, players returning, winning runs). A team\'s mood is the average over its articles this week; stories about two clubs count half for each.',
          verdict: 'info',
        },
        {
          title: 'Injury stories',
          body: 'Articles that mention injuries, players ruled out or fitness doubts for that team this week. A key player ruled out matters more than the mood score.',
          verdict: 'info',
        },
        {
          title: 'Does this feed the predictions?',
          body: `Yes, as "news features" you can switch on per training run (Training page). The models can only learn from news once there is history to compare against results: ${total.toLocaleString('en-IN')} articles so far${since ? `, the oldest from ${new Date(since).toLocaleDateString('en-IN', { dateStyle: 'medium' })}` : ''}. Give it a few weeks of hourly collection, then compare a run with and without news.`,
          verdict: total > 5000 ? 'good' : 'medium',
          verdictLabel: total > 5000 ? 'Enough history' : 'Building history',
        },
        {
          title: 'How the scoring works',
          body: 'A transparent football word list (no black box): "thrash", "unbeaten", "returns" count as good; "slump", "sacked", "ruled out" as bad; the headline counts double. Betting talk is ignored. Hover a headline to see the words it found.',
          verdict: 'info',
        },
      ]} />

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Team mood · last 7 days" aside={
            <select value={league} onChange={(e) => { setLeague(e.target.value); setTeam(null) }} className={`${control} py-1 text-xs`} aria-label="League">
              {LEAGUES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          } />
          {mood.data && mood.data.teams.length === 0 ? (
            <EmptyState icon={<Newspaper className="size-6" />} title="No news yet" body="The news scraper runs every hour; check back soon." />
          ) : (
            <ul className="max-h-[640px] divide-y divide-zinc-100 overflow-y-auto dark:divide-zinc-800">
              {(mood.data?.teams ?? []).map((t) => (
                <li key={t.team_id}>
                  <button onClick={() => setTeam(team?.id === t.team_id ? null : { id: t.team_id, name: t.team })}
                    className={`flex w-full items-center gap-3 px-5 py-2.5 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800/40 ${team?.id === t.team_id ? 'bg-zinc-50 dark:bg-zinc-800/40' : ''}`}>
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{t.team}</div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">
                        {t.articles} articles{t.injury_stories > 0 ? ` · ${t.injury_stories.toFixed(1)} injury stories` : ''}
                      </div>
                    </div>
                    <Mood value={t.sentiment} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader title={team ? `News · ${team.name}` : 'Latest news'} aside={
            <label className="flex items-center gap-1.5 text-xs text-zinc-500">
              <input type="checkbox" checked={injuryOnly} onChange={(e) => setInjuryOnly(e.target.checked)} className="accent-zinc-900 dark:accent-zinc-100" />
              Injuries only
            </label>
          } />
          <ul className="max-h-[640px] divide-y divide-zinc-100 overflow-y-auto dark:divide-zinc-800">
            {(articles.data ?? []).map((a) => (
              <li key={a.id} className="px-5 py-3">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium" title={[...a.signals.positive.map((w) => `+ ${w}`), ...a.signals.negative.map((w) => `− ${w}`)].join(', ') || 'No scoring words'}>
                      {a.headline}
                    </div>
                    {a.summary && <p className="mt-0.5 line-clamp-2 text-xs text-zinc-500 dark:text-zinc-400">{a.summary}</p>}
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-500">
                      <span>{ago(a.published_at)} · {a.league}</span>
                      {a.teams.map((t) => <span key={t.name} className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">{t.name}</span>)}
                      {a.injury && <VerdictBadge verdict="bad" label="Injury" />}
                      {a.url && <a href={a.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 hover:underline">ESPN <ExternalLink className="size-3" /></a>}
                    </div>
                  </div>
                  <Mood value={a.sentiment} />
                </div>
              </li>
            ))}
            {articles.data?.length === 0 && <li className="px-5 py-8 text-center text-sm text-zinc-500">No articles match.</li>}
          </ul>
        </Card>
      </div>
    </>
  )
}

import { useQuery } from '@tanstack/react-query'
import {
  Brain, Bug, CalendarDays, Database, GitMerge, GraduationCap, LayoutDashboard,
  Newspaper, Power, Receipt, Settings, Sparkles, Users, Wallet,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { GUIDE_RAIL_ID } from './components/Guide'
import { StatusDot } from './components/ui'
import { api } from './lib/api'
import DataSources from './pages/DataSources'
import IdentityReview from './pages/IdentityReview'
import Ledger from './pages/Ledger'
import Matches from './pages/Matches'
import Models from './pages/Models'
import Scraper from './pages/Scraper'
import SettingsPage from './pages/Settings'
import Stake from './pages/Stake'
import TeamNews from './pages/TeamNews'
import Training from './pages/Training'
import Overview from './pages/Overview'
import Players from './pages/Players'
import Placeholder from './pages/Placeholder'
import { refresh } from './lib/settings'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  phase?: number
  blurb?: string
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: 'Betting',
    items: [
      { to: '/', label: 'Overview', icon: LayoutDashboard },
      { to: '/matches', label: 'Matches', icon: CalendarDays },
      { to: '/value', label: 'Value bets', icon: Sparkles, phase: 4, blurb: 'Opportunities ranked by edge and confidence, with approve and reject for approve-mode strategies.' },
      { to: '/ledger', label: 'Bet ledger', icon: Receipt },
      { to: '/stake', label: 'Stake', icon: Wallet },
    ],
  },
  {
    section: 'Analysis',
    items: [
      { to: '/models', label: 'Models', icon: Brain },
      { to: '/training', label: 'Training', icon: GraduationCap },
      { to: '/players', label: 'Players', icon: Users },
      { to: '/news', label: 'Team news', icon: Newspaper },
    ],
  },
  {
    section: 'System',
    items: [
      { to: '/sources', label: 'Data sources', icon: Database },
      { to: '/scraper', label: 'Scraper', icon: Bug },
      { to: '/identity', label: 'Identity review', icon: GitMerge },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

function Sidebar() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary })
  const reviewCount = summary.data?.identity_review ?? 0
  const stake = useQuery({ queryKey: ['stake', 'status'], queryFn: api.stakeStatus, refetchInterval: refresh('medium') })
  const dbTone = health.isError ? 'bad' : health.data?.database.ok ? 'ok' : health.isLoading ? 'off' : 'bad'
  const dbLabel = health.isError
    ? 'API offline'
    : health.data?.database.ok
      ? 'API and database OK'
      : health.isLoading
        ? 'Connecting…'
        : 'Database offline'

  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-zinc-200 bg-white px-3 py-5 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-8 flex items-center gap-2.5 px-2">
        <img src="/favicon.svg" alt="" className="size-7" />
        <span className="text-[15px] font-semibold tracking-tight">SportsAnalyzer</span>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto">
        {NAV.map(({ section, items }) => (
          <div key={section}>
            <div className="mb-1.5 px-2 text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              {section}
            </div>
            <ul className="space-y-0.5">
              {items.map(({ to, label, icon: Icon, phase }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={to === '/'}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition-colors ${
                        isActive
                          ? 'bg-zinc-100 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50'
                          : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100'
                      }`
                    }
                  >
                    <Icon className="size-4" />
                    <span className="flex-1">{label}</span>
                    {phase && <span className="text-[10px] text-zinc-400 dark:text-zinc-600">P{phase}</span>}
                    {to === '/identity' && reviewCount > 0 && (
                      <span className="tabular rounded-full bg-amber-100 px-1.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">{reviewCount}</span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="mt-4 space-y-3 border-t border-zinc-100 px-2 pt-4 dark:border-zinc-800">
        <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
          <StatusDot tone={dbTone} /> {dbLabel}
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
          <StatusDot tone={stake.data?.helper.connected ? 'ok' : 'bad'} />
          {stake.data?.helper.connected ? 'Stake helper connected' : 'Stake helper offline'}
        </div>
        <NavLink
          to="/stake"
          className={`flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${
            stake.data?.execution_enabled
              ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300'
              : 'border-zinc-200 text-zinc-500 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800'
          }`}
        >
          <Power className="size-3.5" /> {stake.data?.execution_enabled ? 'Stake execution ON' : 'Stake execution off'}
        </NavLink>
      </div>
    </aside>
  )
}

export default function App() {
  const placeholders = NAV.flatMap((s) => s.items).filter((i) => i.phase)
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex min-w-0 flex-1 justify-center gap-8 px-10 py-8">
        <div className="w-full min-w-0 max-w-6xl">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/sources" element={<DataSources />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/models" element={<Models />} />
            <Route path="/training" element={<Training />} />
            <Route path="/players" element={<Players />} />
            <Route path="/news" element={<TeamNews />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/scraper" element={<Scraper />} />
            <Route path="/stake" element={<Stake />} />
            <Route path="/ledger" element={<Ledger />} />
            <Route path="/strategies" element={<Navigate to="/" replace />} />
            <Route path="/identity" element={<IdentityReview />} />
            {placeholders.map((item) => (
              <Route
                key={item.to}
                path={item.to}
                element={
                  <Placeholder
                    title={item.label}
                    icon={<item.icon className="size-6" />}
                    phase={item.phase!}
                    blurb={item.blurb!}
                  />
                }
              />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        {/* Plain-English guide column (filled by <Guide> on each page), only on very wide screens */}
        <aside id={GUIDE_RAIL_ID} className="sticky top-8 hidden h-fit max-h-[calc(100vh-4rem)] w-80 shrink-0 overflow-y-auto 2xl:block" />
      </main>
    </div>
  )
}

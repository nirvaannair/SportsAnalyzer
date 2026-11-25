import { useQuery } from '@tanstack/react-query'
import {
  Brain, CalendarDays, Database, GitMerge, Layers, LayoutDashboard,
  Newspaper, Power, Receipt, Settings, Sparkles,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { StatusDot } from './components/ui'
import { api } from './lib/api'
import DataSources from './pages/DataSources'
import IdentityReview from './pages/IdentityReview'
import Matches from './pages/Matches'
import Overview from './pages/Overview'
import Placeholder from './pages/Placeholder'

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
      { to: '/ledger', label: 'Bet ledger', icon: Receipt, phase: 4, blurb: 'Every proposed, placed and settled bet with odds taken, closing odds and P&L.' },
      { to: '/strategies', label: 'Strategies', icon: Layers, phase: 4, blurb: 'Flat, fractional Kelly and compounding strategies with bankroll limits and kill switches.' },
    ],
  },
  {
    section: 'Analysis',
    items: [
      { to: '/models', label: 'Models', icon: Brain, phase: 3, blurb: 'Backtests, calibration, log loss and closing line value per model version.' },
      { to: '/news', label: 'Team news', icon: Newspaper, phase: 2, blurb: 'Injury and suspension feed linked to players, with estimated match impact.' },
    ],
  },
  {
    section: 'System',
    items: [
      { to: '/sources', label: 'Data sources', icon: Database },
      { to: '/identity', label: 'Identity review', icon: GitMerge },
      { to: '/settings', label: 'Settings', icon: Settings, phase: 1, blurb: 'Schedules, thresholds and key status.' },
    ],
  },
]

function Sidebar() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary })
  const reviewCount = summary.data?.identity_review ?? 0
  const dbTone = health.isError ? 'bad' : health.data?.database.ok ? 'ok' : health.isLoading ? 'off' : 'bad'
  const dbLabel = health.isError
    ? 'API offline'
    : health.data?.database.ok
      ? 'All systems normal'
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
        <button
          disabled
          title="Bet execution arrives in Phase 4; nothing can be placed yet."
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-400 dark:border-zinc-800 dark:text-zinc-500"
        >
          <Power className="size-3.5" /> Execution off · Paper mode
        </button>
      </div>
    </aside>
  )
}

export default function App() {
  const placeholders = NAV.flatMap((s) => s.items).filter((i) => i.phase)
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 px-10 py-8">
        <div className="mx-auto max-w-6xl">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/sources" element={<DataSources />} />
            <Route path="/matches" element={<Matches />} />
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
      </main>
    </div>
  )
}

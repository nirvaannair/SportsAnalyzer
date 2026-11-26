import { ChevronDown, Lightbulb } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export type Verdict = 'good' | 'medium' | 'bad' | 'info'
export type GuideItem = { title: string; body: ReactNode; verdict?: Verdict; verdictLabel?: string }

const TONE: Record<Verdict, string> = {
  good: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-900',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-900',
  bad: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-900',
  info: 'bg-zinc-100 text-zinc-600 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',
}
const DEFAULT_LABEL: Record<Verdict, string> = { good: 'Good', medium: 'Medium', bad: 'Needs work', info: 'Info' }

export function VerdictBadge({ verdict, label }: { verdict: Verdict; label?: string }) {
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONE[verdict]}`}>
      {label ?? DEFAULT_LABEL[verdict]}
    </span>
  )
}

/** The rail exists in App; it is only visible on very wide screens. */
export const GUIDE_RAIL_ID = 'guide-rail'
const WIDE = '(min-width: 1536px)'

function useWide() {
  const [wide, setWide] = useState(() => typeof window !== 'undefined' && window.matchMedia(WIDE).matches)
  useEffect(() => {
    const query = window.matchMedia(WIDE)
    const update = () => setWide(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return wide
}

function Items({ items }: { items: GuideItem[] }) {
  return (
    <ul className="space-y-4">
      {items.map((item) => (
        <li key={item.title}>
          <div className="flex items-start justify-between gap-2">
            <div className="text-[13px] font-medium leading-snug">{item.title}</div>
            {item.verdict && <VerdictBadge verdict={item.verdict} label={item.verdictLabel} />}
          </div>
          <div className="mt-1 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{item.body}</div>
        </li>
      ))}
    </ul>
  )
}

/** Plain-English explanations for a page: a side column on wide screens, a fold-out box otherwise. */
export function Guide({ items, title = 'What am I looking at?' }: { items: GuideItem[]; title?: string }) {
  const wide = useWide()
  const [open, setOpen] = useState(false)
  const [rail, setRail] = useState<HTMLElement | null>(null)
  useEffect(() => setRail(document.getElementById(GUIDE_RAIL_ID)), [])

  if (wide && rail) {
    return createPortal(
      <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-4 flex items-center gap-2 text-sm font-medium"><Lightbulb className="size-4 text-amber-500" /> {title}</div>
        <Items items={items} />
      </div>,
      rail,
    )
  }
  return (
    <div className="mb-6 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
              className="flex w-full items-center gap-2 px-5 py-3 text-left text-sm font-medium">
        <Lightbulb className="size-4 text-amber-500" /> {title}
        <span className="ml-auto flex items-center gap-1.5">
          {items.filter((i) => i.verdict && i.verdict !== 'info').slice(0, 4).map((i) => (
            <VerdictBadge key={i.title} verdict={i.verdict!} label={i.verdictLabel} />
          ))}
          <ChevronDown className={`size-4 text-zinc-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open && <div className="border-t border-zinc-100 px-5 py-4 dark:border-zinc-800"><Items items={items} /></div>}
    </div>
  )
}

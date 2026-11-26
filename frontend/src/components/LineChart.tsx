import { useState } from 'react'

export type Series = { name: string; className: string; points: { x: string; y: number }[] }

/** Simple line chart over time (x = date strings in order). Hover shows the values. */
export default function LineChart({ series, height = 200, format = (v: number) => v.toFixed(3), zeroLine = false }: {
  series: Series[]
  height?: number
  format?: (v: number) => string
  zeroLine?: boolean
}) {
  const [hover, setHover] = useState<number | null>(null)
  const all = series.flatMap((s) => s.points)
  if (all.length < 2) return <div className="flex h-[120px] items-center justify-center text-sm text-zinc-500">Not enough settled matches yet.</div>
  const w = 560
  const pad = { l: 48, r: 12, t: 10, b: 22 }
  const longest = Math.max(...series.map((s) => s.points.length))
  const ys = all.map((p) => p.y).concat(zeroLine ? [0] : [])
  const [lo, hi] = [Math.min(...ys), Math.max(...ys)]
  const span = hi - lo || 1
  const sx = (i: number, n: number) => pad.l + (n <= 1 ? 0 : (i / (n - 1)) * (w - pad.l - pad.r))
  const sy = (v: number) => pad.t + (1 - (v - lo) / span) * (height - pad.t - pad.b)
  const ref = series.find((s) => s.points.length === longest)!.points

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full" role="img" onMouseLeave={() => setHover(null)}
           onMouseMove={(e) => {
             const box = e.currentTarget.getBoundingClientRect()
             const x = ((e.clientX - box.left) / box.width) * w
             setHover(Math.max(0, Math.min(longest - 1, Math.round(((x - pad.l) / (w - pad.l - pad.r)) * (longest - 1)))))
           }}>
        {[lo, lo + span / 2, hi].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={sy(t)} y2={sy(t)} className="stroke-zinc-100 dark:stroke-zinc-800" />
            <text x={pad.l - 6} y={sy(t) + 3} textAnchor="end" className="fill-zinc-400 text-[10px]">{format(t)}</text>
          </g>
        ))}
        {zeroLine && lo < 0 && hi > 0 && <line x1={pad.l} x2={w - pad.r} y1={sy(0)} y2={sy(0)} className="stroke-zinc-400" strokeDasharray="3 3" />}
        <text x={pad.l} y={height - 6} className="fill-zinc-400 text-[10px]">{ref[0].x}</text>
        <text x={w - pad.r} y={height - 6} textAnchor="end" className="fill-zinc-400 text-[10px]">{ref[ref.length - 1].x}</text>
        {series.map((s) => (
          <polyline key={s.name} fill="none" strokeWidth={2} className={s.className}
                    points={s.points.map((p, i) => `${sx(i, s.points.length)},${sy(p.y)}`).join(' ')} />
        ))}
        {hover !== null && <line x1={sx(hover, longest)} x2={sx(hover, longest)} y1={pad.t} y2={height - pad.b} className="stroke-zinc-300 dark:stroke-zinc-600" strokeDasharray="3 3" />}
      </svg>
      <div className="mt-1 flex flex-wrap gap-4 text-xs text-zinc-500 dark:text-zinc-400">
        {series.map((s) => <span key={s.name} className="flex items-center gap-1.5"><svg className="h-1 w-4"><line x1="0" x2="16" y1="2" y2="2" strokeWidth={3} className={s.className} /></svg>{s.name}</span>)}
      </div>
      {hover !== null && (
        <div className="pointer-events-none absolute right-2 top-0 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
          <div className="font-medium">{ref[Math.min(hover, ref.length - 1)]?.x}</div>
          {series.map((s) => s.points[hover] && <div key={s.name}>{s.name}: {format(s.points[hover].y)}</div>)}
        </div>
      )}
    </div>
  )
}

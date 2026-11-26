import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RotateCcw, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Guide } from '../components/Guide'
import { Badge, Card, CardHeader, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { replaceSettings } from '../lib/settings'

type Tree = Record<string, unknown>
const isTree = (v: unknown): v is Tree => v !== null && typeof v === 'object' && !Array.isArray(v)
const control = 'w-full rounded-md border border-zinc-200 bg-white px-2 py-1 text-sm dark:border-zinc-800 dark:bg-zinc-900'

/** One value: number, text, true/false, or a list/table shown as JSON. */
function Field({ value, onChange }: { value: unknown; onChange: (v: unknown) => void }) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 1))
  const [bad, setBad] = useState(false)
  useEffect(() => setText(JSON.stringify(value, null, 1)), [value])
  if (typeof value === 'boolean') {
    return <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} className="accent-zinc-900 dark:accent-zinc-100" />
  }
  if (typeof value === 'number') {
    return <input type="number" step="any" value={value} onChange={(e) => onChange(Number(e.target.value))} className={`${control} tabular max-w-40`} />
  }
  if (typeof value === 'string') {
    return <input value={value} onChange={(e) => onChange(e.target.value)} className={control} />
  }
  return (
    <textarea value={text} rows={Math.min(10, text.split('\n').length)} spellCheck={false}
      className={`${control} font-mono text-xs ${bad ? 'border-rose-400' : ''}`}
      onChange={(e) => {
        setText(e.target.value)
        try { onChange(JSON.parse(e.target.value)); setBad(false) } catch { setBad(true) }
      }} />
  )
}

function Group({ path, value, defaults, onChange }: {
  path: string; value: Tree; defaults: Tree; onChange: (key: string, v: unknown) => void
}) {
  return (
    <dl className="divide-y divide-zinc-100 dark:divide-zinc-800">
      {Object.entries(value).map(([key, v]) => (
        isTree(v) && !Object.keys(v).every((k) => /^\d+$/.test(k)) ? (
          <div key={key} className="py-3">
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">{key.replaceAll('_', ' ')}</div>
            <div className="border-l border-zinc-200 pl-3 dark:border-zinc-800">
              <Group path={`${path}.${key}`} value={v} defaults={(defaults[key] as Tree) ?? {}}
                     onChange={(k, nv) => onChange(key, { ...v, [k]: nv })} />
            </div>
          </div>
        ) : (
          <div key={key} className="grid grid-cols-1 items-start gap-2 py-2.5 sm:grid-cols-[minmax(0,14rem)_1fr]">
            <dt className="text-sm">
              <div className="flex items-center gap-1.5">
                {key.replaceAll('_', ' ')}
                {JSON.stringify(v) !== JSON.stringify(defaults[key]) && <Badge tone="warn">changed</Badge>}
              </div>
              <div className="font-mono text-[10px] text-zinc-400">{path}.{key}</div>
            </dt>
            <dd><Field value={v} onChange={(nv) => onChange(key, nv)} /></dd>
          </div>
        )
      ))}
    </dl>
  )
}

export default function Settings() {
  const queryClient = useQueryClient()
  const data = useQuery({ queryKey: ['settings'], queryFn: api.settings, refetchInterval: false })
  const [section, setSection] = useState<string | null>(null)
  const [draft, setDraft] = useState<unknown>(null)
  const effective = data.data?.effective ?? {}
  const sections = Object.keys(effective)
  const current = section ?? sections[0] ?? null
  useEffect(() => { if (current) setDraft(effective[current]) }, [current, data.data])  // eslint-disable-line react-hooks/exhaustive-deps

  const onSaved = (fresh: Awaited<ReturnType<typeof api.settings>>) => {
    replaceSettings(fresh.effective)
    queryClient.setQueryData(['settings'], fresh)
    queryClient.invalidateQueries()
  }
  const save = useMutation({ mutationFn: () => api.saveSettings({ [current!]: draft }), onSuccess: onSaved })
  const reset = useMutation({ mutationFn: () => api.resetSettings(current!), onSuccess: onSaved })
  const changed = current && JSON.stringify(draft) !== JSON.stringify(effective[current])
  const overridden = current && data.data?.overrides && current in data.data.overrides
  const needsRestart = current && data.data?.restart_sections.includes(current)

  return (
    <>
      <PageHeader title="Settings" description="Every adjustable number, date, list and threshold the app uses. Nothing is fixed in the code." />
      <Guide items={[
        { title: 'Where these live', body: 'Defaults are in config/settings.toml. What you change here is saved to config/settings.local.json and overrides the defaults; "Reset" puts a section back.', verdict: 'info' },
        { title: 'When changes apply', body: 'Most settings apply straight away. Leagues and the API collector are read at start-up, so Stop and Start the app after changing them.', verdict: 'info' },
        { title: 'Not here on purpose', body: 'API keys and money limits stay in the .env file (personal and secret). Names (database columns, market names) are part of the program, not settings.', verdict: 'info' },
      ]} />
      <div className="grid gap-6 lg:grid-cols-4">
        <Card className="h-fit lg:col-span-1">
          <ul className="py-2">
            {sections.map((s) => (
              <li key={s}>
                <button onClick={() => setSection(s)}
                  className={`flex w-full items-center justify-between px-5 py-1.5 text-left text-sm ${s === current ? 'bg-zinc-100 font-medium dark:bg-zinc-800' : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/40'}`}>
                  {s.replaceAll('_', ' ')}
                  {data.data?.overrides && s in data.data.overrides && <span className="size-1.5 rounded-full bg-amber-500" />}
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title={current ? current.replaceAll('_', ' ') : 'Loading…'} aside={
            <div className="flex items-center gap-2">
              {needsRestart && <Badge tone="warn">applies after restart</Badge>}
              {overridden && (
                <button onClick={() => reset.mutate()} className="flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800">
                  <RotateCcw className="size-3" /> Reset
                </button>
              )}
              <button onClick={() => save.mutate()} disabled={!changed || save.isPending}
                className="flex items-center gap-1 rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900">
                <Save className="size-3" /> Save
              </button>
            </div>
          } />
          {(save.error || reset.error) && <p className="px-5 pt-3 text-sm text-rose-600">{((save.error || reset.error) as Error).message}</p>}
          <div className="px-5 py-2">
            {current && draft !== null && (isTree(draft) ? (
              <Group path={current} value={draft} defaults={(data.data?.defaults[current] as Tree) ?? {}}
                     onChange={(k, v) => setDraft({ ...(draft as Tree), [k]: v })} />
            ) : (
              <div className="py-3"><Field value={draft} onChange={setDraft} /></div>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}

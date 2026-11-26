// Settings from config/settings.toml (via the API). Loaded once before the dashboard renders,
// so any component can read a value synchronously. Nothing tunable is typed into the dashboard.

type Tree = Record<string, unknown>
let current: Tree = {}

export async function loadSettings(): Promise<void> {
  const response = await fetch('/api/settings')
  if (!response.ok) throw new Error(`settings: HTTP ${response.status}`)
  current = (await response.json()).effective as Tree
}

export function replaceSettings(effective: Tree) {
  current = effective
}

/** Dotted lookup, e.g. setting<number>('verdicts.lineups_enough'). */
export function setting<T = unknown>(path: string): T {
  let node: unknown = current
  for (const part of path.split('.')) {
    if (node === null || typeof node !== 'object' || !(part in (node as Tree))) {
      throw new Error(`Setting "${path}" is missing from config/settings.toml`)
    }
    node = (node as Tree)[part]
  }
  return node as T
}

/** Milliseconds for a refresh speed name in [ui.refresh_seconds]. */
export const refresh = (speed: 'live' | 'fast' | 'medium' | 'normal' | 'slow' | 'minute' | 'training_live') =>
  setting<number>(`ui.refresh_seconds.${speed}`) * 1000

export type LeagueSetting = { code: string; name: string; country: string; tier: number }
export const leagues = () => setting<LeagueSetting[]>('leagues')
export const leagueName = (code: string | null | undefined) => leagues().find((l) => l.code === code)?.name ?? code ?? ''

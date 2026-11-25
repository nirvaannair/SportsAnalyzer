export type Health = {
  status: 'ok' | 'degraded'
  database: { ok: boolean; error: string | null }
  time: string
}

export type Provider = {
  name: string
  label: string
  configured: boolean
  observations: number
  last_received_at: string | null
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${path} → HTTP ${response.status}`)
  return response.json() as Promise<T>
}

export const api = {
  health: () => get<Health>('/api/health'),
  providers: () => get<Provider[]>('/api/providers'),
}

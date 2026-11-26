import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'

/** Ports come from [startup] in config/settings.toml (start.ps1 also passes them as SA_* variables). */
function startupPort(name: 'api_port' | 'dashboard_port', env: string | undefined): number {
  if (env) return Number(env)
  const toml = readFileSync(new URL('../config/settings.toml', import.meta.url), 'utf-8')
  const section = toml.split(/^\[startup\]\s*$/m)[1]?.split(/^\[/m)[0] ?? ''
  const match = section.match(new RegExp(`^${name}\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`[startup] ${name} is missing from config/settings.toml`)
  return Number(match[1])
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: startupPort('dashboard_port', process.env.SA_DASHBOARD_PORT),
    strictPort: true,
    // The dashboard calls /api/...; Vite forwards those to the FastAPI backend.
    proxy: { '/api': `http://127.0.0.1:${startupPort('api_port', process.env.SA_API_PORT)}` },
  },
})

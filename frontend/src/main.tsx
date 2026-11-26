import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { loadSettings, refresh } from './lib/settings'

const root = createRoot(document.getElementById('root')!)

function waiting(message: string) {
  root.render(
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-sm text-zinc-400">{message}</div>,
  )
}

async function start() {
  waiting('Connecting to the SportsAnalyzer API…')
  for (;;) {
    try {
      await loadSettings()
      break
    } catch {
      waiting('Waiting for the SportsAnalyzer API to start… (it retries by itself)')
      // The API's settings aren't available yet, so this delay comes from frontend/.env.
      await new Promise((resolve) => setTimeout(resolve, Number(import.meta.env.VITE_STARTUP_RETRY_SECONDS) * 1000))
    }
  }
  const queryClient = new QueryClient({
    defaultOptions: { queries: { refetchInterval: refresh('normal'), retry: 1 } },
  })
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

void start()

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient } from '@tanstack/react-query'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { AuthProvider } from '@/auth/AuthProvider'
import { ConfirmProvider, ToastProvider } from '@/components/ui'
import { BUSTER, MAX_AGE, persister, shouldPersist } from '@/lib/offline/persist'
import { registerOffline } from '@/lib/offline/register'
import { ErrorBoundary, initMonitoring } from '@/lib/monitoring'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { App } from './App'
import { FatalError } from './components/FatalError'
import './fonts.css'
import './index.css'

initMonitoring()
registerOffline()

const queryClient = new QueryClient({
  defaultOptions: {
    // Sem internet o React Query PAUSA as mutações (a ação nunca rodava e o gol não era registrado). As nossas ações já
    // tratam a falta de rede: guardam na fila e enviam depois.
    mutations: { networkMode: 'always' },
    queries: {
      staleTime: 30_000,
      gcTime: MAX_AGE, // o cache precisa viver o bastante para ser guardado no IndexedDB
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary fallback={<FatalError />}>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister, maxAge: MAX_AGE, buster: BUSTER, dehydrateOptions: { shouldDehydrateQuery: shouldPersist } }}
    >
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <ToastProvider>
              <ConfirmProvider>
                <App />
              </ConfirmProvider>
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </PersistQueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)

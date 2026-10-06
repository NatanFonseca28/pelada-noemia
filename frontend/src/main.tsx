import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { AuthProvider } from '@/auth/AuthProvider'
import { ConfirmProvider, ToastProvider } from '@/components/ui'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { App } from './App'
import './fonts.css'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  </StrictMode>,
)

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, json, refreshSession, tokenStore } from '@/api/client'
import type { TokenResponse, User, UserRole } from '@/api/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasRole: (...roles: UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const queryClient = useQueryClient()

  useEffect(() => {
    tokenStore.onSessionLost(() => {
      setUser(null)
      queryClient.clear()
    })
    // Restaura a sessão a partir do cookie de refresh
    refreshSession()
      .then((data) => setUser(data?.user ?? null))
      .finally(() => setLoading(false))
  }, [queryClient])

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<TokenResponse>('/auth/login', { method: 'POST', body: json({ email, password }) })
    tokenStore.set(data.access_token)
    setUser(data.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST' })
    } finally {
      tokenStore.set(null)
      setUser(null)
      queryClient.clear()
    }
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, logout, hasRole: (...roles) => !!user && roles.includes(user.role) }),
    [user, loading, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth fora do AuthProvider')
  return ctx
}

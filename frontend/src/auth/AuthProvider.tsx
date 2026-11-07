import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, json, refreshSessionDetailed, tokenStore } from '@/api/client'
import { persister } from '@/lib/offline/persist'
import type { TokenResponse, User, UserRole } from '@/api/types'

const USER_KEY = 'pelada-user'

/** Perfil guardado só para abrir o app sem internet (sem tokens: o servidor continua mandando em tudo). */
const storedUser = (): User | null => {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) ?? 'null') as User | null
  } catch {
    return null
  }
}
const keepUser = (u: User | null) => {
  try {
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u))
    else localStorage.removeItem(USER_KEY)
  } catch {
    /* armazenamento indisponível */
  }
}

interface AuthContextValue {
  /** sem internet ou servidor dormindo: o usuário é o último que entrou neste celular, e a sessão renova quando der */
  offline: boolean
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
  const [offline, setOffline] = useState(false)
  const queryClient = useQueryClient()

  const forget = useCallback(() => {
    keepUser(null)
    void persister.removeClient()
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    tokenStore.onSessionLost(() => {
      setUser(null)
      forget()
    })
    // Restaura a sessão a partir do cookie de refresh
    refreshSessionDetailed()
      .then((r) => {
        if (r.status === 'ok') {
          setUser(r.data.user)
          keepUser(r.data.user)
        } else if (r.status === 'unreachable') {
          // sem internet ou Render acordando: segue com o último usuário deste celular
          const u = storedUser()
          setUser(u)
          setOffline(!!u)
        } else {
          setUser(null)
          keepUser(null)
        }
      })
      .finally(() => setLoading(false))
  }, [forget])

  // Em modo offline, tenta renovar a sessão ao voltar a internet, ao abrir o app de novo e a cada 20 s
  useEffect(() => {
    if (!offline) return
    const retry = () =>
      void refreshSessionDetailed().then((r) => {
        if (r.status === 'ok') {
          setUser(r.data.user)
          keepUser(r.data.user)
          setOffline(false)
          void queryClient.invalidateQueries()
        } else if (r.status === 'rejected') {
          setUser(null)
          setOffline(false)
          forget()
        }
      })
    window.addEventListener('online', retry)
    document.addEventListener('visibilitychange', retry)
    const timer = window.setInterval(retry, 20_000)
    return () => {
      window.removeEventListener('online', retry)
      document.removeEventListener('visibilitychange', retry)
      window.clearInterval(timer)
    }
  }, [offline, queryClient, forget])

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<TokenResponse>('/auth/login', { method: 'POST', body: json({ email, password }) })
    tokenStore.set(data.access_token)
    setUser(data.user)
    keepUser(data.user)
    setOffline(false)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST' })
    } finally {
      tokenStore.set(null)
      setUser(null)
      forget()
    }
  }, [forget])

  const value = useMemo<AuthContextValue>(
    () => ({ offline, user, loading, login, logout, hasRole: (...roles) => !!user && roles.includes(user.role) }),
    [offline, user, loading, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth fora do AuthProvider')
  return ctx
}

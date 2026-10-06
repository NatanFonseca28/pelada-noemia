import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './client'
import type { AuditLog, Player, PlayerInput, Settings, User, UserRole, UserStatus } from './types'

export const keys = {
  players: (filters?: object) => ['players', filters ?? {}] as const,
  users: (status?: UserStatus) => ['users', status ?? 'all'] as const,
  settings: ['settings'] as const,
  audit: (entity?: string) => ['audit', entity ?? 'all'] as const,
}

// ---------- Jogadores ----------
export function usePlayers(filters: { active?: boolean; q?: string } = {}) {
  const params = new URLSearchParams()
  if (filters.active !== undefined) params.set('active', String(filters.active))
  if (filters.q) params.set('q', filters.q)
  return useQuery({ queryKey: keys.players(filters), queryFn: () => api<Player[]>(`/players?${params}`) })
}

export function useSavePlayer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<PlayerInput> }) =>
      id
        ? api<Player>(`/players/${id}`, { method: 'PATCH', body: json(data) })
        : api<Player>('/players', { method: 'POST', body: json(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['players'] }),
  })
}

export function useDeletePlayer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api(`/players/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['players'] }),
  })
}

export function usePlayerPhoto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, file }: { id: number; file: File | null }) => {
      if (!file) return api<Player>(`/players/${id}/photo`, { method: 'DELETE' })
      const body = new FormData()
      body.append('file', file)
      return api<Player>(`/players/${id}/photo`, { method: 'PUT', body })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['players'] }),
  })
}

// ---------- Usuários ----------
export function useUsers(status?: UserStatus) {
  return useQuery({
    queryKey: keys.users(status),
    queryFn: () => api<User[]>(`/users${status ? `?status=${status}` : ''}`),
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { email: string; name: string; password: string; role: UserRole; player_id: number | null }) =>
      api<User>('/users', { method: 'POST', body: json(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      api<User>(`/users/${id}`, { method: 'PATCH', body: json(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useApproveUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, role, player_id }: { id: number; role: UserRole; player_id: number | null }) =>
      api<User>(`/users/${id}/approve`, { method: 'POST', body: json({ role, player_id }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useRejectUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api(`/users/${id}/reject`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

// ---------- Configurações ----------
export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => api<Settings>('/settings') })
}

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Settings) => api<Settings>('/settings', { method: 'PUT', body: json(data) }),
    onSuccess: (data) => qc.setQueryData(keys.settings, data),
  })
}

// ---------- Auditoria ----------
export function useAudit(entity?: string) {
  return useQuery({
    queryKey: keys.audit(entity),
    queryFn: () => api<AuditLog[]>(`/audit?limit=200${entity ? `&entity=${entity}` : ''}`),
  })
}

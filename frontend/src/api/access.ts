import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './client'
import type { AccessEvent, AccessLogEntry, PageVisibility, UserRole } from './types'

export function usePageVisibility() {
  return useQuery({ queryKey: ['access', 'pages'], queryFn: () => api<PageVisibility>('/access/pages') })
}

export function useSavePageVisibility() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (hidden: Record<UserRole, string[]>) =>
      api<PageVisibility>('/access/pages', { method: 'PUT', body: json({ hidden }) }),
    onSuccess: (data) => qc.setQueryData(['access', 'pages'], data),
  })
}

export function useAccessLog(filters: { email?: string; event?: AccessEvent | '' ; limit: number }) {
  const params = new URLSearchParams({ limit: String(filters.limit) })
  if (filters.email) params.set('email', filters.email)
  if (filters.event) params.set('event', filters.event)
  return useQuery({
    queryKey: ['access', 'log', filters],
    queryFn: () => api<AccessLogEntry[]>(`/access/log?${params}`),
    placeholderData: (prev) => prev,
  })
}

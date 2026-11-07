import { useMemo } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './client'
import { usePendingOps } from '@/hooks/useSheetQueue'
import { enqueue, isRetryable, withPending } from '@/lib/offlineQueue'
import { uuid } from '@/lib/uuid'
import type { EventType, MatchSheet, PlayerStats, RoundHistory, TournamentSummary } from './types'

export function usePlayerStats(year: number | null) {
  return useQuery({
    queryKey: ['stats', 'players', year ?? 'all'],
    queryFn: () => api<PlayerStats[]>(`/stats/players${year ? `?year=${year}` : ''}`),
  })
}

export function usePlayerProfile(id: number) {
  return useQuery({
    queryKey: ['stats', 'player', id],
    queryFn: () => api<{ stats: PlayerStats; history: RoundHistory[] }>(`/stats/players/${id}`),
  })
}

export function useTournamentSummary(id: number) {
  return useQuery({ queryKey: ['tournament', id, 'summary'], queryFn: () => api<TournamentSummary>(`/tournaments/${id}/summary`) })
}

/**
 * "Pronto para offline": com internet, baixa a súmula de todas as partidas do campeonato para este celular.
 * Devolve se todas já estão guardadas e quando foi a última atualização.
 */
export function useOfflineReady(matchIds: number[]) {
  const queries = useQueries({
    queries: matchIds.map((id) => ({
      queryKey: ['sheet', id],
      queryFn: () => api<MatchSheet>(`/matches/${id}/events`),
      staleTime: 60_000,
      enabled: id > 0, // partidas criadas sem internet (id provisório) ainda não existem no servidor
    })),
  })
  const real = queries.filter((_, i) => matchIds[i] > 0)
  const ready = real.length > 0 && real.every((q) => q.data !== undefined)
  const updatedAt = real.length ? Math.min(...real.map((q) => q.dataUpdatedAt || Infinity)) : 0
  return { ready, updatedAt: Number.isFinite(updatedAt) ? updatedAt : 0 }
}

export function useMatchSheet(matchId: number) {
  const pending = usePendingOps(matchId)
  const query = useQuery({ queryKey: ['sheet', matchId], queryFn: () => api<MatchSheet>(`/matches/${matchId}/events`) })
  // o que está na tela = servidor + lances guardados neste celular
  const data = useMemo(() => (query.data ? withPending(query.data, pending) : undefined), [query.data, pending])
  return { ...query, data, pendingCount: pending.length }
}

export function useSheetActions(matchId: number) {
  const qc = useQueryClient()
  const onSuccess = (data: MatchSheet | null) => {
    if (!data) return // guardado na fila: a tela já mostra pelo usePendingOps
    qc.setQueryData(['sheet', matchId], data)
    qc.invalidateQueries({ queryKey: ['tournament'] })
    qc.invalidateQueries({ queryKey: ['stats'] })
  }
  return {
    add: useMutation({
      mutationFn: async (body: { type: EventType; team_id: number; player_id: number | null; assist_player_id?: number | null }) => {
        const full = { client_event_id: uuid(), ...body }
        try {
          return await api<MatchSheet>(`/matches/${matchId}/events`, { method: 'POST', body: json(full) })
        } catch (err) {
          if (!isRetryable(err)) throw err
          enqueue({ kind: 'add', matchId, body: full, queuedAt: Date.now() })
          return null
        }
      },
      onSuccess,
    }),
    remove: useMutation({
      mutationFn: async (eventId: number) => {
        if (eventId < 0) {
          enqueue({ kind: 'remove', matchId, eventId, queuedAt: Date.now() }) // ainda não enviado: só sai da fila
          return null
        }
        try {
          return await api<MatchSheet>(`/events/${eventId}`, { method: 'DELETE' })
        } catch (err) {
          if (!isRetryable(err)) throw err
          enqueue({ kind: 'remove', matchId, eventId, queuedAt: Date.now() })
          return null
        }
      },
      onSuccess,
    }),
  }
}

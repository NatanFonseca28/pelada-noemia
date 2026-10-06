import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './client'
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

export function useMatchSheet(matchId: number) {
  return useQuery({ queryKey: ['sheet', matchId], queryFn: () => api<MatchSheet>(`/matches/${matchId}/events`) })
}

export function useSheetActions(matchId: number) {
  const qc = useQueryClient()
  const onSuccess = (data: MatchSheet) => {
    qc.setQueryData(['sheet', matchId], data)
    qc.invalidateQueries({ queryKey: ['tournament'] })
    qc.invalidateQueries({ queryKey: ['stats'] })
  }
  return {
    add: useMutation({
      mutationFn: (body: { type: EventType; team_id: number; player_id: number | null; assist_player_id?: number | null }) =>
        api<MatchSheet>(`/matches/${matchId}/events`, {
          method: 'POST',
          body: json({ client_event_id: uuid(), ...body }),
        }),
      onSuccess,
    }),
    remove: useMutation({
      mutationFn: (eventId: number) => api<MatchSheet>(`/events/${eventId}`, { method: 'DELETE' }),
      onSuccess,
    }),
  }
}

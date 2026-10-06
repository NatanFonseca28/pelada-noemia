import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { ApiError, api, json } from './client'
import type { FormatsResponse, Tournament } from './types'

export function useFormats(roundId: number, finalWeight: string, enabled: boolean) {
  return useQuery({
    queryKey: ['formats', roundId, finalWeight],
    queryFn: () => api<FormatsResponse>(`/rounds/${roundId}/tournament/formats?final_weight=${finalWeight}`),
    enabled,
  })
}

export function useRoundTournament(roundId: number) {
  return useQuery({
    queryKey: ['tournament', 'round', roundId],
    queryFn: async () => {
      try {
        return await api<Tournament>(`/rounds/${roundId}/tournament`)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
  })
}

export function useTournament(id: number) {
  return useQuery({ queryKey: ['tournament', id], queryFn: () => api<Tournament>(`/tournaments/${id}`) })
}

function useTournamentMutation<V>(fn: (v: V) => Promise<Tournament | void>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      if (data) {
        qc.setQueryData(['tournament', data.id], data)
        qc.setQueryData(['tournament', 'round', data.round_id], data)
      }
      qc.invalidateQueries({ queryKey: ['tournament'] })
      qc.invalidateQueries({ queryKey: ['rounds'] })
    },
  })
}

export function useCreateTournament(roundId: number) {
  return useTournamentMutation((body: { format_code: string; legs: number; final_weight: string }) =>
    api<Tournament>(`/rounds/${roundId}/tournament`, { method: 'POST', body: json(body) }),
  )
}

export function useTournamentActions(tournamentId: number) {
  return {
    result: useTournamentMutation(
      ({ matchId, ...body }: { matchId: number; home_score: number; away_score: number; home_penalties?: number; away_penalties?: number }) =>
        api<Tournament>(`/matches/${matchId}/result`, { method: 'POST', body: json(body) }),
    ),
    reopen: useTournamentMutation((matchId: number) => api<Tournament>(`/matches/${matchId}/reopen`, { method: 'POST' })),
    addMatch: useTournamentMutation(() => api<Tournament>(`/tournaments/${tournamentId}/matches`, { method: 'POST' })),
    finish: useTournamentMutation(() => api<Tournament>(`/tournaments/${tournamentId}/finish`, { method: 'POST' })),
    remove: useTournamentMutation(() => api(`/tournaments/${tournamentId}`, { method: 'DELETE' }).then(() => undefined)),
  }
}

/** Envia o resultado de uma partida (mesmo endpoint do "Resultado"); usado pelo "Finalizar súmula". */
export function useMatchResult() {
  return useTournamentMutation(
    ({ matchId, ...body }: {
      matchId: number
      home_score: number
      away_score: number
      home_penalties?: number
      away_penalties?: number
      started_at?: string
      ended_at?: string
      played_seconds?: number
    }) => api<Tournament>(`/matches/${matchId}/result`, { method: 'POST', body: json(body) }),
  )
}

/**
 * Reabre uma partida fora do ciclo de vida de um componente (ex.: ação "Desfazer" de um toast,
 * que continua na tela depois que a súmula fecha).
 */
export async function reopenMatch(qc: QueryClient, matchId: number): Promise<Tournament> {
  const data = await api<Tournament>(`/matches/${matchId}/reopen`, { method: 'POST' })
  qc.setQueryData(['tournament', data.id], data)
  qc.setQueryData(['tournament', 'round', data.round_id], data)
  qc.invalidateQueries({ queryKey: ['tournament'] })
  qc.invalidateQueries({ queryKey: ['rounds'] })
  qc.invalidateQueries({ queryKey: ['stats'] })
  return data
}

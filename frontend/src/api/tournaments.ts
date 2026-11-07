import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { ApiError, api, json } from './client'
import type { FormatsResponse, Tournament } from './types'
import { usePendingTournamentOps } from '@/hooks/useSheetQueue'
import { applyAddMatch, applyFinish, applyReopen, applyResult, OfflineRuleError } from '@/lib/offline/tournament'
import { enqueue, isRetryable, readQueue, withPendingTournament, type ResultBody, type SheetOp } from '@/lib/offlineQueue'

export function useFormats(roundId: number, finalWeight: string, enabled: boolean) {
  return useQuery({
    queryKey: ['formats', roundId, finalWeight],
    queryFn: () => api<FormatsResponse>(`/rounds/${roundId}/tournament/formats?final_weight=${finalWeight}`),
    enabled,
  })
}

/** Campeonato do servidor + ações guardadas neste celular (resultado, reabertura, próxima partida…). */
function usePendingMerged<T extends Tournament | null | undefined>(data: T): T {
  const pending = usePendingTournamentOps(data ? data.id : undefined, data ? data.matches.map((m) => m.id) : [])
  return useMemo(() => (data && pending.length ? (withPendingTournament(data, pending) as T) : data), [data, pending])
}

/** Procura no cache o campeonato a que a partida pertence. */
function findTournament(qc: QueryClient, matchId: number): Tournament | undefined {
  for (const [, t] of qc.getQueriesData<Tournament | null>({ queryKey: ['tournament'] })) {
    if (t && Array.isArray(t.matches) && t.matches.some((m) => m.id === matchId)) return t
  }
  return undefined
}

/**
 * Envia agora; sem internet ou com o servidor dormindo, valida no celular e guarda na fila (o resultado aparece na tela
 * na hora e sobe sozinho depois). Regra inválida (ex.: pênaltis faltando) falha como o servidor falharia.
 */
async function sendOrQueue(qc: QueryClient, op: SheetOp & { tournamentId: number }, send: () => Promise<Tournament>): Promise<Tournament | null> {
  const queue = (): null => {
    const base = qc.getQueryData<Tournament>(['tournament', op.tournamentId])
    if (base) {
      try {
        const now = withPendingTournament(base, readQueue())
        if (op.kind === 'result') applyResult(now, op.matchId, op.body)
        else if (op.kind === 'reopen') applyReopen(now, op.matchId)
        else if (op.kind === 'add_match') applyAddMatch(now, op.seq)
        else if (op.kind === 'finish_casual') applyFinish(now)
      } catch (e) {
        if (e instanceof OfflineRuleError) throw new ApiError(422, e.message)
        throw e
      }
    }
    enqueue(op)
    return null
  }
  if (!navigator.onLine) return queue()
  try {
    return await send()
  } catch (err) {
    if (!isRetryable(err)) throw err
    return queue()
  }
}

export function useRoundTournament(roundId: number) {
  const q = useQuery({
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
  return { ...q, data: usePendingMerged(q.data) }
}

export function useTournament(id: number) {
  const q = useQuery({ queryKey: ['tournament', id], queryFn: () => api<Tournament>(`/tournaments/${id}`) })
  return { ...q, data: usePendingMerged(q.data) }
}

function useTournamentMutation<V>(fn: (v: V) => Promise<Tournament | null | void>) {
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
  const qc = useQueryClient()
  const tid = (matchId: number) => findTournament(qc, matchId)?.id ?? tournamentId
  const nextSeq = () => {
    const base = qc.getQueryData<Tournament>(['tournament', tournamentId])
    return (base ? withPendingTournament(base, readQueue()) : undefined)?.matches.reduce((n, m) => Math.max(n, m.seq), 0) ?? 0
  }
  return {
    result: useTournamentMutation(
      ({ matchId, ...body }: { matchId: number } & ResultBody) => {
        const t = findTournament(qc, matchId)
        const m = t?.matches.find((x) => x.id === matchId)
        const full: ResultBody = { ...body, expected_home_team_id: m?.home?.id ?? null, expected_away_team_id: m?.away?.id ?? null }
        return sendOrQueue(qc, { kind: 'result', tournamentId: tid(matchId), matchId, body: full, queuedAt: Date.now() },
          () => api<Tournament>(`/matches/${matchId}/result`, { method: 'POST', body: json(full) }))
      },
    ),
    reopen: useTournamentMutation((matchId: number) =>
      sendOrQueue(qc, { kind: 'reopen', tournamentId: tid(matchId), matchId, queuedAt: Date.now() },
        () => api<Tournament>(`/matches/${matchId}/reopen`, { method: 'POST' })),
    ),
    addMatch: useTournamentMutation(() => {
      const seq = nextSeq() + 1
      return sendOrQueue(qc, { kind: 'add_match', tournamentId, seq, queuedAt: Date.now() },
        () => api<Tournament>(`/tournaments/${tournamentId}/matches`, { method: 'POST', body: json({ expected_seq: seq }) }))
    }),
    finish: useTournamentMutation(() =>
      sendOrQueue(qc, { kind: 'finish_casual', tournamentId, queuedAt: Date.now() },
        () => api<Tournament>(`/tournaments/${tournamentId}/finish`, { method: 'POST' })),
    ),
    remove: useTournamentMutation(() => api(`/tournaments/${tournamentId}`, { method: 'DELETE' }).then(() => undefined)),
  }
}

/** Envia o resultado de uma partida (mesmo endpoint do "Resultado"); usado pelo "Finalizar súmula". */
export function useMatchResult() {
  return useTournamentActions(0).result
}

/**
 * Reabre uma partida fora do ciclo de vida de um componente (ex.: ação "Desfazer" de um toast,
 * que continua na tela depois que a súmula fecha).
 */
export async function reopenMatch(qc: QueryClient, matchId: number): Promise<Tournament | null> {
  const tournamentId = findTournament(qc, matchId)?.id ?? 0
  const data = await sendOrQueue(qc, { kind: 'reopen', tournamentId, matchId, queuedAt: Date.now() },
    () => api<Tournament>(`/matches/${matchId}/reopen`, { method: 'POST' }))
  if (data) {
    qc.setQueryData(['tournament', data.id], data)
    qc.setQueryData(['tournament', 'round', data.round_id], data)
  }
  qc.invalidateQueries({ queryKey: ['tournament'] })
  qc.invalidateQueries({ queryKey: ['rounds'] })
  qc.invalidateQueries({ queryKey: ['stats'] })
  return data
}

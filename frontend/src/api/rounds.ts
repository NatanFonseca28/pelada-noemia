import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, json } from './client'
import { enqueue, isRetryable } from '@/lib/offlineQueue'
import type { DrawPreview, RoundDetail, RoundSummary, TeamRole } from './types'

export function useRounds() {
  return useQuery({ queryKey: ['rounds'], queryFn: () => api<RoundSummary[]>('/rounds') })
}

export function useRound(id: number) {
  return useQuery({ queryKey: ['rounds', id], queryFn: () => api<RoundDetail>(`/rounds/${id}`) })
}

/** Situação da lista de confirmados antes de sortear (só admin). Atualiza quando a presença muda. */
export function useDrawPreview(roundId: number, allowShort: boolean, enabled = true) {
  return useQuery({
    queryKey: ['rounds', roundId, 'preview', allowShort],
    queryFn: () => api<DrawPreview>(`/rounds/${roundId}/draw-preview?allow_short_team=${allowShort}`),
    enabled,
  })
}

export function useCurrentRound() {
  return useQuery({
    queryKey: ['rounds', 'current'],
    queryFn: async () => {
      try {
        return await api<RoundDetail>('/rounds/current')
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
  })
}

/** Todas as ações de rodada devolvem o detalhe atualizado; gravamos direto no cache. */
function useRoundAction<V>(roundId: number, fn: (vars: V) => Promise<RoundDetail>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      qc.setQueryData(['rounds', roundId], data)
      qc.invalidateQueries({ queryKey: ['rounds', roundId, 'preview'] })
      qc.invalidateQueries({ queryKey: ['rounds'], exact: true })
      qc.invalidateQueries({ queryKey: ['rounds', 'current'] })
      qc.invalidateQueries({ queryKey: ['tournament'] }) // empréstimos aparecem nas partidas
    },
  })
}

/** Aplica a marcação da chamada no cache da rodada (enquanto a ação não chega ao servidor). */
function markCheckin(
  qc: ReturnType<typeof useQueryClient>,
  roundId: number,
  pick: (a: RoundDetail['attendances'][number]) => 'PRESENTE' | 'FALTOU' | null | undefined,
): RoundDetail {
  const cur = qc.getQueryData<RoundDetail>(['rounds', roundId])
  if (!cur) throw new TypeError('Sem dados da rodada neste celular')
  return { ...cur, attendances: cur.attendances.map((a) => { const v = pick(a); return v === undefined ? a : { ...a, checkin: v } }) }
}

export function useRoundActions(roundId: number) {
  const qc = useQueryClient()
  const base = `/rounds/${roundId}`
  return {
    status: useRoundAction(roundId, (action: 'open' | 'close' | 'lock' | 'unlock') =>
      api<RoundDetail>(`${base}/${action}`, { method: 'POST' }),
    ),
    attendance: useRoundAction(roundId, ({ playerId, confirmed, role }: { playerId: number; confirmed: boolean; role?: 'LINHA' | 'GOLEIRO' }) =>
      api<RoundDetail>(`${base}/attendances/${playerId}`, { method: 'PUT', body: json({ confirmed, role }) }),
    ),
    paid: useRoundAction(roundId, ({ playerId, paid }: { playerId: number; paid: boolean }) =>
      api<RoundDetail>(`${base}/attendances/${playerId}/paid`, { method: 'PUT', body: json({ paid }) }),
    ),
    clearAttendance: useRoundAction(roundId, (playerId: number) =>
      api<RoundDetail>(`${base}/attendances/${playerId}`, { method: 'DELETE' }),
    ),
    draw: useRoundAction(roundId, (body: { num_teams?: number; seed?: number; allow_short_team?: boolean; competition?: string | null }) =>
      api<RoundDetail>(`${base}/draw`, { method: 'POST', body: json(body) }),
    ),
    // Chamada sem internet: marca no celular na hora e envia quando der (mesma lógica da súmula)
    checkin: useRoundAction(roundId, async ({ playerId, status }: { playerId: number; status: 'PRESENTE' | 'FALTOU' | null }) => {
      try {
        if (!navigator.onLine) throw new TypeError('offline')
        return await api<RoundDetail>(`${base}/checkin/${playerId}`, { method: 'PUT', body: json({ status }) })
      } catch (err) {
        if (!isRetryable(err)) throw err
        enqueue({ kind: 'checkin', roundId, playerId, status, queuedAt: Date.now() })
        return markCheckin(qc, roundId, (a) => (a.player_id === playerId ? status : undefined))
      }
    }),
    allPresent: useRoundAction(roundId, async () => {
      try {
        if (!navigator.onLine) throw new TypeError('offline')
        return await api<RoundDetail>(`${base}/checkin/all-present`, { method: 'POST' })
      } catch (err) {
        if (!isRetryable(err)) throw err
        enqueue({ kind: 'checkin_all', roundId, queuedAt: Date.now() })
        return markCheckin(qc, roundId, (a) => (a.checkin ? undefined : 'PRESENTE'))
      }
    }),
    move: useRoundAction(roundId, (body: { player_id: number; team_id: number | null; role?: TeamRole }) =>
      api<RoundDetail>(`${base}/move`, { method: 'POST', body: json(body) }),
    ),
  }
}

export function useCreateRound() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { date: string; notes?: string }) => api<RoundDetail>('/rounds', { method: 'POST', body: json(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rounds'] }),
  })
}

export function useDeleteRound() {
  const qc = useQueryClient()
  return useMutation({
    // force: rodada já jogada (times travados/encerrada) — apaga também campeonato e súmula
    mutationFn: ({ id, force = false }: { id: number; force?: boolean }) =>
      api(`/rounds/${id}${force ? '?force=true' : ''}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useMyAttendance(roundId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ confirmed, role }: { confirmed: boolean; role?: 'LINHA' | 'GOLEIRO' }) =>
      api<RoundDetail>(`/rounds/${roundId}/attendance/me`, { method: 'PUT', body: json({ confirmed, role }) }),
    onSuccess: (data) => {
      qc.setQueryData(['rounds', 'current'], data)
      qc.invalidateQueries({ queryKey: ['rounds'], exact: true })
    },
  })
}

import { api, json } from '@/api/client'
import type { MatchSheet, RoundDetail, Tournament } from '@/api/types'
import type { SheetOp } from '@/lib/offlineQueue'

/** Envia uma ação guardada ao servidor. Devolve o dado novo (súmula, campeonato ou rodada) para atualizar o cache. */
export async function sendOp(op: SheetOp): Promise<{ sheet?: MatchSheet; tournament?: Tournament; round?: RoundDetail }> {
  switch (op.kind) {
    case 'add':
      return { sheet: await api<MatchSheet>(`/matches/${op.matchId}/events`, { method: 'POST', body: json(op.body) }) }
    case 'remove':
      return { sheet: await api<MatchSheet>(`/events/${op.eventId}`, { method: 'DELETE' }) }
    case 'result':
      return { tournament: await api<Tournament>(`/matches/${op.matchId}/result`, { method: 'POST', body: json(op.body) }) }
    case 'reopen':
      return { tournament: await api<Tournament>(`/matches/${op.matchId}/reopen`, { method: 'POST' }) }
    case 'add_match':
      return { tournament: await api<Tournament>(`/tournaments/${op.tournamentId}/matches`, { method: 'POST', body: json({ expected_seq: op.seq }) }) }
    case 'finish_casual':
      return { tournament: await api<Tournament>(`/tournaments/${op.tournamentId}/finish`, { method: 'POST' }) }
    case 'checkin':
      return { round: await api<RoundDetail>(`/rounds/${op.roundId}/checkin/${op.playerId}`, { method: 'PUT', body: json({ status: op.status }) }) }
    case 'checkin_all':
      return { round: await api<RoundDetail>(`/rounds/${op.roundId}/checkin/all-present`, { method: 'POST' }) }
  }
}

/** Acorda o servidor (Render grátis dorme): espera até 90 s por uma resposta do /health. */
export async function wakeServer(): Promise<boolean> {
  try {
    const r = await fetch('/api/health', { signal: AbortSignal.timeout(90_000), cache: 'no-store' })
    return r.ok
  } catch {
    return false
  }
}

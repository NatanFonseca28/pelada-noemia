/**
 * Fila de ações do campo sem internet. Lances têm client_event_id (o servidor ignora reenvios), a próxima partida
 * leva o nº esperado (reenviar não cria outra) e o resultado leva os times esperados (se mudaram, o servidor recusa
 * com 409). A fila fica no localStorage (sobrevive a recarregar/fechar o app) e é enviada em ordem quando a conexão
 * volta. O que o servidor recusar vai para a lista "não aceitas" (nunca é descartado em silêncio).
 */
import { ApiError } from '@/api/client'
import type { EventType, MatchEventItem, MatchSheet, Tournament } from '@/api/types'
import { applyAddMatch, applyFinish, applyReopen, applyResult, OfflineRuleError } from '@/lib/offline/tournament'

export interface ResultBody {
  home_score: number
  away_score: number
  home_penalties?: number | null
  away_penalties?: number | null
  started_at?: string
  ended_at?: string
  played_seconds?: number
  expected_home_team_id?: number | null
  expected_away_team_id?: number | null
}

export type SheetOp =
  | { kind: 'result'; tournamentId: number; matchId: number; body: ResultBody; queuedAt: number }
  | { kind: 'reopen'; tournamentId: number; matchId: number; queuedAt: number }
  | { kind: 'add_match'; tournamentId: number; seq: number; queuedAt: number }
  | { kind: 'finish_casual'; tournamentId: number; queuedAt: number }
  | { kind: 'checkin'; roundId: number; playerId: number; status: 'PRESENTE' | 'FALTOU' | null; queuedAt: number }
  | { kind: 'checkin_all'; roundId: number; queuedAt: number }
  | {
      kind: 'add'
      matchId: number
      body: { client_event_id: string; type: EventType; team_id: number; player_id: number | null; assist_player_id?: number | null }
      queuedAt: number
    }
  | { kind: 'remove'; matchId: number; eventId: number; queuedAt: number }

/** Número da partida a que a ação se refere (só lances e resultado), para mostrar pendências por partida. */
export const opMatchId = (o: SheetOp): number | null => ('matchId' in o ? o.matchId : null)

const KEY = 'pelada-sheet-queue'
const EVENT = 'pelada-sheet-queue'

export function readQueue(): SheetOp[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as SheetOp[]
  } catch {
    return []
  }
}

function write(ops: SheetOp[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(ops))
  } catch {
    /* armazenamento indisponível: a fila fica só na memória desta aba */
  }
  window.dispatchEvent(new Event(EVENT))
}

export function enqueue(op: SheetOp) {
  const ops = readQueue()
  // excluir um lance que ainda nem foi enviado = só tirar da fila
  if (op.kind === 'remove' && op.eventId < 0) {
    write(ops.filter((o) => !(o.kind === 'add' && localEventId(o.body.client_event_id) === op.eventId)))
    return
  }
  // chamada: só vale a última marcação do mesmo jogador
  if (op.kind === 'checkin') write(ops.filter((o) => !(o.kind === 'checkin' && o.roundId === op.roundId && o.playerId === op.playerId)))
  write([...ops, op])
}

export function dropFirst() {
  write(readQueue().slice(1))
}

export const pendingFor = (matchId: number) => readQueue().filter((o) => opMatchId(o) === matchId)

export function onQueueChange(listener: () => void) {
  window.addEventListener(EVENT, listener)
  window.addEventListener('storage', listener)
  return () => {
    window.removeEventListener(EVENT, listener)
    window.removeEventListener('storage', listener)
  }
}

/** Id negativo e estável para mostrar o lance pendente na lista (derivado do client_event_id). */
export function localEventId(clientEventId: string): number {
  let h = 0
  for (const ch of clientEventId) h = (h * 31 + ch.charCodeAt(0)) | 0
  return -Math.abs(h || 1)
}

/** Vale tentar de novo depois: sem rede/timeout, ou servidor/banco acordando (500/502/503/504) ou ocupado (408/425/429). */
export const isRetryable = (err: unknown) =>
  err instanceof TypeError ||
  (err instanceof DOMException && (err.name === 'AbortError' || err.name === 'TimeoutError')) ||
  (err instanceof ApiError && [408, 425, 429, 500, 502, 503, 504].includes(err.status))

/** Súmula como o mesário vê: a do servidor + lances guardados neste celular (pendentes têm id negativo). */
export function withPending(sheet: MatchSheet, ops: SheetOp[]): MatchSheet {
  if (!ops.length) return sheet
  const removed = new Set(ops.flatMap((o) => (o.kind === 'remove' ? [o.eventId] : [])))
  const known = new Set(sheet.events.map((e) => e.client_event_id))
  const nameOf = (id: number | null | undefined) =>
    id == null ? null : Object.values(sheet.rosters).flat().find((p) => p.player_id === id)?.name ?? null
  const pending: MatchEventItem[] = ops.flatMap((o) =>
    o.kind === 'add' && !known.has(o.body.client_event_id)
      ? [{
          id: localEventId(o.body.client_event_id),
          client_event_id: o.body.client_event_id,
          type: o.body.type,
          team_id: o.body.team_id,
          player_id: o.body.player_id,
          player_name: nameOf(o.body.player_id),
          assist_player_id: o.body.assist_player_id ?? null,
          assist_name: nameOf(o.body.assist_player_id),
          minute: null,
          second: null,
          created_at: new Date(o.queuedAt).toISOString(),
        }]
      : [],
  )
  const events = [...sheet.events.filter((e) => !removed.has(e.id)), ...pending]
  let home = 0
  let away = 0
  for (const e of events) {
    if (e.type === 'GOL') {
      home += Number(e.team_id === sheet.home_team_id)
      away += Number(e.team_id === sheet.away_team_id)
    } else if (e.type === 'GOL_CONTRA') {
      home += Number(e.team_id === sheet.away_team_id)
      away += Number(e.team_id === sheet.home_team_id)
    }
  }
  return { ...sheet, events, home_score: home, away_score: away }
}


// ---------------------------------------------------------------- ações não aceitas

export interface FailedOp {
  op: SheetOp
  reason: string
  failedAt: number
}

const FAILED_KEY = 'pelada-sheet-failed'

export function readFailed(): FailedOp[] {
  try {
    return JSON.parse(localStorage.getItem(FAILED_KEY) ?? '[]') as FailedOp[]
  } catch {
    return []
  }
}

function writeFailed(list: FailedOp[]) {
  try {
    localStorage.setItem(FAILED_KEY, JSON.stringify(list))
  } catch {
    /* sem armazenamento: a lista fica só em memória */
  }
  window.dispatchEvent(new Event(EVENT))
}

/** O servidor recusou a ação: guarda com o motivo em vez de apagar. */
export function moveToFailed(op: SheetOp, reason: string) {
  writeFailed([...readFailed(), { op, reason, failedAt: Date.now() }])
}

export const discardFailed = (index: number) => writeFailed(readFailed().filter((_, i) => i !== index))

/** Cópia de segurança (fila + não aceitas), para guardar caso o navegador limpe os dados do app. */
export const backupJson = () => JSON.stringify({ exportedAt: new Date().toISOString(), queue: readQueue(), failed: readFailed() }, null, 2)

// ---------------------------------------------------------------- campeonato com as ações pendentes


/** Campeonato como o mesário vê: o do servidor + resultados, reaberturas e partidas guardados neste celular. */
export function withPendingTournament(t: Tournament, ops: SheetOp[]): Tournament {
  let out = t
  for (const o of ops) {
    // gols guardados contam no placar da partida em andamento (a partida encerrada usa o placar do resultado)
    if (o.kind === 'add' && (o.body.type === 'GOL' || o.body.type === 'GOL_CONTRA')) {
      const m = out.matches.find((x) => x.id === o.matchId)
      if (m && m.status !== 'ENCERRADA') {
        const forHome = (o.body.team_id === m.home?.id) === (o.body.type === 'GOL')
        out = { ...out, matches: out.matches.map((x) => x.id !== m.id ? x : forHome ? { ...x, home_score: x.home_score + 1 } : { ...x, away_score: x.away_score + 1 }) }
      }
      continue
    }
    if (!('tournamentId' in o) || o.tournamentId !== t.id) continue
    try {
      if (o.kind === 'result') out = applyResult(out, o.matchId, o.body)
      else if (o.kind === 'reopen') out = applyReopen(out, o.matchId)
      else if (o.kind === 'add_match') out = applyAddMatch(out, o.seq)
      else if (o.kind === 'finish_casual') out = applyFinish(out)
    } catch (e) {
      if (!(e instanceof OfflineRuleError)) throw e
    }
  }
  return out
}

export const tournamentOps = (ops: SheetOp[], tournamentId: number) =>
  ops.filter((o) => 'tournamentId' in o && o.tournamentId === tournamentId)

/** Ranking de jogadores com os lances guardados neste celular (gol, assistência e cartões que ainda não subiram). */
export function withPendingStats<T extends { player_id: number; goals: number; own_goals: number; assists: number; yellows: number; reds: number }>(
  rows: T[],
  ops: SheetOp[],
): T[] {
  const adds = ops.filter((o): o is Extract<SheetOp, { kind: 'add' }> => o.kind === 'add')
  if (!adds.length) return rows
  const bump = new Map<number, { goals: number; own_goals: number; assists: number; yellows: number; reds: number }>()
  const at = (id: number) => {
    let b = bump.get(id)
    if (!b) bump.set(id, (b = { goals: 0, own_goals: 0, assists: 0, yellows: 0, reds: 0 }))
    return b
  }
  for (const o of adds) {
    const { type, player_id, assist_player_id } = o.body
    if (player_id != null) {
      if (type === 'GOL') at(player_id).goals++
      else if (type === 'GOL_CONTRA') at(player_id).own_goals++
      else if (type === 'AMARELO') at(player_id).yellows++
      else if (type === 'VERMELHO') at(player_id).reds++
    }
    if (assist_player_id != null && type === 'GOL') at(assist_player_id).assists++
  }
  return rows.map((r) => {
    const b = bump.get(r.player_id)
    return b ? { ...r, goals: r.goals + b.goals, own_goals: r.own_goals + b.own_goals, assists: r.assists + b.assists, yellows: r.yellows + b.yellows, reds: r.reds + b.reds } : r
  })
}

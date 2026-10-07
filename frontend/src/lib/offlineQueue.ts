/**
 * Fila da súmula sem internet. Cada lance tem um client_event_id: o servidor ignora reenvios repetidos, então
 * reenviar até dar certo é seguro. A fila fica no localStorage (sobrevive a recarregar/fechar o app) e é enviada
 * em ordem quando a conexão volta.
 */
import { ApiError } from '@/api/client'
import type { EventType, MatchEventItem, MatchSheet } from '@/api/types'

export type SheetOp =
  | {
      kind: 'add'
      matchId: number
      body: { client_event_id: string; type: EventType; team_id: number; player_id: number | null; assist_player_id?: number | null }
      queuedAt: number
    }
  | { kind: 'remove'; matchId: number; eventId: number; queuedAt: number }

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
  write([...ops, op])
}

export function dropFirst() {
  write(readQueue().slice(1))
}

export const pendingFor = (matchId: number) => readQueue().filter((o) => o.matchId === matchId)

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

/** Vale tentar de novo depois: sem rede, ou servidor fora do ar/acordando (502/503/504). */
export const isRetryable = (err: unknown) =>
  err instanceof TypeError || (err instanceof ApiError && [502, 503, 504].includes(err.status))

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

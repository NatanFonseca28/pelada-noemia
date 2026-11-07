import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { useToast } from '@/contexts/feedback'
import { sendOp, wakeServer } from '@/lib/offline/sendOp'
import { setSyncKick, setSyncState } from '@/lib/offline/syncStore'
import { dropFirst, isRetryable, moveToFailed, onQueueChange, opMatchId, readQueue, type SheetOp } from '@/lib/offlineQueue'

const snapshot = () => localStorage.getItem('pelada-sheet-queue') ?? '[]'

function useRawQueue(): SheetOp[] {
  const raw = useSyncExternalStore(onQueueChange, () => {
    try {
      return snapshot()
    } catch {
      return '[]'
    }
  })
  return useMemo(() => JSON.parse(raw) as SheetOp[], [raw])
}

/** Ações desta partida ainda guardadas neste celular. */
export function usePendingOps(matchId: number): SheetOp[] {
  const all = useRawQueue()
  return useMemo(() => all.filter((o) => opMatchId(o) === matchId), [all, matchId])
}

/** Ações guardadas deste campeonato (resultados, reaberturas, partidas novas). */
export function usePendingTournamentOps(tournamentId: number | undefined): SheetOp[] {
  const all = useRawQueue()
  return useMemo(
    () => all.filter((o) => 'tournamentId' in o && o.tournamentId === tournamentId),
    [all, tournamentId],
  )
}

/** Quantas ações aguardam envio (faixa do topo). */
export const usePendingCount = () => useRawQueue().length

export function useOnline() {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

/** Espera entre tentativas quando o servidor não responde (s): 5, 10, 20, 40, 60 e depois de 2 em 2 minutos. */
const BACKOFF = [5, 10, 20, 40, 60, 120]
/** Erro 500 repetido mais que isso vira "não aceita" (pode ser o banco acordando, mas não para sempre). */
const MAX_500 = 6

/**
 * Envia a fila de ações em ordem: ao abrir, ao voltar a internet, ao reabrir o app e com espera crescente quando o servidor
 * não responde (Render grátis dorme). Nada se perde: o que o servidor recusar vai para "não aceitas".
 * Fica no Layout, então funciona em qualquer tela (inclusive depois de recarregar o app).
 */
export function useSheetQueueFlusher() {
  const qc = useQueryClient()
  const toast = useToast()
  const attempt = useRef(0)
  const errors500 = useRef(0)
  const timer = useRef<number | undefined>(undefined)
  const busy = useRef(false)

  const flush = useCallback(async (): Promise<'empty' | 'done' | 'retry' | 'login'> => {
    if (!readQueue().length) return 'empty'
    setSyncState({ phase: navigator.onLine ? 'waking' : 'waiting' })
    if (!navigator.onLine || !(await wakeServer())) return 'retry'
    setSyncState({ phase: 'syncing' })
    let sent = 0
    let refused = 0
    for (let op = readQueue()[0]; op; op = readQueue()[0]) {
      try {
        const r = await sendOp(op)
        if (r.sheet && 'matchId' in op) qc.setQueryData(['sheet', op.matchId], r.sheet)
        if (r.tournament) {
          qc.setQueryData(['tournament', r.tournament.id], r.tournament)
          qc.setQueryData(['tournament', 'round', r.tournament.round_id], r.tournament)
        }
        if (r.round && 'roundId' in op) qc.setQueryData(['rounds', op.roundId], r.round)
        dropFirst()
        errors500.current = 0
        sent++
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return 'login' // sessão perdida: a fila espera o login
        if (isRetryable(err)) {
          if (err instanceof ApiError && err.status === 500 && ++errors500.current <= MAX_500) return 'retry'
          if (!(err instanceof ApiError && err.status === 500)) return 'retry'
        }
        // recusado pelo servidor (ex.: partida já encerrada, times mudaram): guarda com o motivo, não apaga
        errors500.current = 0
        moveToFailed(op, err instanceof ApiError ? err.message : 'erro desconhecido')
        dropFirst()
        refused++
      }
    }
    if (sent || refused) {
      qc.invalidateQueries({ queryKey: ['tournament'] })
      qc.invalidateQueries({ queryKey: ['sheet'] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      qc.invalidateQueries({ queryKey: ['rounds'] })
    }
    if (sent) toast({ message: `${sent} ${sent > 1 ? 'ações guardadas enviadas' : 'ação guardada enviada'}`, tone: 'success' })
    if (refused) toast({ message: `${refused} ${refused > 1 ? 'ações não foram aceitas' : 'ação não foi aceita'} pelo servidor. Veja os detalhes no topo.`, tone: 'error' })
    return 'done'
  }, [qc, toast])

  useEffect(() => {
    const run = async () => {
      window.clearTimeout(timer.current)
      if (busy.current) return
      busy.current = true
      try {
        const result = await flush()
        if (result === 'retry') {
          const wait = BACKOFF[Math.min(attempt.current++, BACKOFF.length - 1)]
          setSyncState({ phase: 'waiting', nextTryAt: Date.now() + wait * 1000 })
          timer.current = window.setTimeout(run, wait * 1000)
        } else {
          attempt.current = 0
          setSyncState({ phase: result === 'login' ? 'login' : 'idle', nextTryAt: null })
        }
      } finally {
        busy.current = false
      }
    }
    const reset = () => {
      attempt.current = 0
      void run()
    }
    setSyncKick(reset)
    void run()
    const onVisible = () => document.visibilityState === 'visible' && readQueue().length && reset()
    window.addEventListener('online', reset)
    document.addEventListener('visibilitychange', onVisible)
    const offChange = onQueueChange(() => {
      if (readQueue().length && !busy.current && attempt.current === 0) void run()
    })
    return () => {
      setSyncKick(null)
      window.clearTimeout(timer.current)
      window.removeEventListener('online', reset)
      document.removeEventListener('visibilitychange', onVisible)
      offChange()
    }
  }, [flush])
}

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError, json } from '@/api/client'
import type { MatchSheet } from '@/api/types'
import { useToast } from '@/contexts/feedback'
import { dropFirst, isRetryable, onQueueChange, readQueue, type SheetOp } from '@/lib/offlineQueue'

const snapshot = () => localStorage.getItem('pelada-sheet-queue') ?? '[]'

/** Lances desta partida ainda guardados neste celular. */
export function usePendingOps(matchId: number): SheetOp[] {
  const raw = useSyncExternalStore(onQueueChange, () => {
    try {
      return snapshot()
    } catch {
      return '[]'
    }
  })
  return useMemo(() => (JSON.parse(raw) as SheetOp[]).filter((o) => o.matchId === matchId), [raw, matchId])
}

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

/**
 * Envia a fila da súmula em ordem: ao montar, quando a conexão volta e a cada 15 s enquanto houver pendências.
 * Fica no Layout, então funciona em qualquer tela (inclusive depois de recarregar o app).
 */
export function useSheetQueueFlusher() {
  const qc = useQueryClient()
  const toast = useToast()

  const flush = useCallback(async () => {
    let sent = 0
    for (let op = readQueue()[0]; op; op = readQueue()[0]) {
      try {
        const sheet =
          op.kind === 'add'
            ? await api<MatchSheet>(`/matches/${op.matchId}/events`, { method: 'POST', body: json(op.body) })
            : await api<MatchSheet>(`/events/${op.eventId}`, { method: 'DELETE' })
        qc.setQueryData(['sheet', op.matchId], sheet)
        dropFirst()
        sent++
      } catch (err) {
        if (isRetryable(err)) break
        // recusado pelo servidor (ex.: partida já encerrada): descarta e avisa
        dropFirst()
        toast({ message: `Um lance guardado não pôde ser enviado: ${err instanceof ApiError ? err.message : 'erro'}`, tone: 'error' })
      }
    }
    if (sent) {
      qc.invalidateQueries({ queryKey: ['tournament'] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      toast({ message: `${sent} lance${sent > 1 ? 's' : ''} guardado${sent > 1 ? 's' : ''} enviado${sent > 1 ? 's' : ''}`, tone: 'success' })
    }
  }, [qc, toast])

  useEffect(() => {
    let busy = false
    const run = async () => {
      if (busy || !readQueue().length) return
      busy = true
      try {
        await flush()
      } finally {
        busy = false
      }
    }
    void run()
    window.addEventListener('online', run)
    const timer = window.setInterval(run, 15_000)
    return () => {
      window.removeEventListener('online', run)
      window.clearInterval(timer)
    }
  }, [flush])
}

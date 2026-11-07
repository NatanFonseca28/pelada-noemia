import { useSyncExternalStore } from 'react'

/** Situação da sincronização, mostrada na faixa do topo. */
export type SyncPhase = 'idle' | 'syncing' | 'waking' | 'waiting' | 'login'

export interface SyncState {
  phase: SyncPhase
  /** quando a próxima tentativa automática acontece (ms desde 1970) */
  nextTryAt: number | null
}

let state: SyncState = { phase: 'idle', nextTryAt: null }
const listeners = new Set<() => void>()

export function setSyncState(next: Partial<SyncState>) {
  state = { ...state, ...next }
  listeners.forEach((l) => l())
}

export const useSyncState = () =>
  useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => state,
  )

/** Pedido de "Enviar agora" vindo da faixa. */
let kick: (() => void) | null = null
export const setSyncKick = (fn: (() => void) | null) => {
  kick = fn
}
export const syncNow = () => kick?.()

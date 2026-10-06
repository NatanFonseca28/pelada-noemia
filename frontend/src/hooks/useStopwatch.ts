import { useCallback, useEffect, useRef, useState } from 'react'

interface State {
  running: boolean
  startedAt: number | null // epoch ms do "iniciar/retomar" atual
  elapsed: number // ms jogados acumulados antes do segmento atual (sem pausas)
  finished: boolean
  firstStartedAt: number | null // 1º "iniciar" (para o tempo com pausas)
  finishedAt: number | null // momento do "finalizar"
}

const EMPTY: State = { running: false, startedAt: null, elapsed: 0, finished: false, firstStartedAt: null, finishedAt: null }
const EVENT = 'pelada:stopwatch'

const storageKey = (id: string) => `stopwatch:${id}`

function load(key: string): State {
  try {
    const raw = localStorage.getItem(key)
    return raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<State>) } : EMPTY
  } catch {
    return EMPTY
  }
}

/** Grava e avisa as outras instâncias (ex.: card do jogo e súmula abertos ao mesmo tempo). */
function write(key: string, state: State) {
  try {
    localStorage.setItem(key, JSON.stringify(state))
  } catch {
    /* armazenamento indisponível: segue só em memória */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: key }))
}

/** Volta um cronômetro finalizado para "pausado" (usado ao reabrir/desfazer uma partida). */
export function unfinishStopwatch(id: string) {
  const key = storageKey(id)
  const s = load(key)
  if (s.finished) write(key, { ...s, finished: false, running: false, startedAt: null, finishedAt: null })
}

export interface StopwatchController {
  /** tempo jogado, sem as pausas */
  elapsedMs: number
  /** tempo total desde o 1º "iniciar", com as pausas */
  wallMs: number
  firstStartedAt: number | null
  running: boolean
  finished: boolean
  started: boolean
  start: () => void
  pause: () => void
  finish: () => void
  reset: () => void
}

/**
 * Cronômetro local do mesário (não sincroniza com o servidor). Persiste no aparelho por chave —
 * recarregar a página não zera — e todas as instâncias com o mesmo id ficam em sincronia.
 */
export function useStopwatch(id: string): StopwatchController {
  const key = storageKey(id)
  const [state, setState] = useState<State>(() => load(key))
  const ref = useRef(state)
  const [now, setNow] = useState(() => Date.now())

  // Sincroniza com outras instâncias (mesma aba) e outras abas
  useEffect(() => {
    const sync = (e: Event) => {
      const changed = e instanceof StorageEvent ? e.key === key : (e as CustomEvent<string>).detail === key
      if (!changed) return
      const next = load(key)
      if (JSON.stringify(next) !== JSON.stringify(ref.current)) {
        ref.current = next
        setState(next)
        setNow(Date.now())
      }
    }
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [key])

  useEffect(() => {
    if (!state.running) return
    const tick = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(tick)
  }, [state.running])

  const update = useCallback(
    (fn: (s: State) => State) => {
      const next = fn(ref.current)
      if (next === ref.current) return
      ref.current = next
      setState(next)
      setNow(Date.now())
      write(key, next)
    },
    [key],
  )

  const start = useCallback(
    () =>
      update((s) => {
        if (s.running) return s
        const t = Date.now()
        return { ...s, running: true, finished: false, finishedAt: null, startedAt: t, firstStartedAt: s.firstStartedAt ?? t }
      }),
    [update],
  )
  const pause = useCallback(
    () => update((s) => (s.running && s.startedAt ? { ...s, running: false, startedAt: null, elapsed: s.elapsed + Date.now() - s.startedAt } : s)),
    [update],
  )
  const finish = useCallback(
    () =>
      update((s) => {
        const t = Date.now()
        return { ...s, running: false, startedAt: null, finished: true, finishedAt: t, elapsed: s.elapsed + (s.running && s.startedAt ? t - s.startedAt : 0) }
      }),
    [update],
  )
  const reset = useCallback(() => update(() => EMPTY), [update])

  const elapsedMs = state.elapsed + (state.running && state.startedAt ? now - state.startedAt : 0)
  const wallMs = state.firstStartedAt ? (state.finishedAt ?? now) - state.firstStartedAt : 0
  return {
    elapsedMs,
    wallMs,
    firstStartedAt: state.firstStartedAt,
    running: state.running,
    finished: state.finished,
    started: state.elapsed > 0 || state.running,
    start,
    pause,
    finish,
    reset,
  }
}

export const formatClock = (ms: number) => {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const sec = total % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

import { useEffect, useState } from 'react'

/**
 * Mantém a tela ligada enquanto `active` (Screen Wake Lock API, igual a um vídeo tocando).
 * O navegador solta a trava quando a aba sai de foco; ao voltar, pedimos de novo.
 * Sem suporte (iOS < 16.4, navegadores antigos) ou recusado (ex.: economia de bateria): `locked` fica false.
 */
export function useWakeLock(active: boolean) {
  const supported = typeof navigator !== 'undefined' && 'wakeLock' in navigator
  const [locked, setLocked] = useState(false)

  useEffect(() => {
    if (!active || !supported) return
    let sentinel: WakeLockSentinel | null = null
    let disposed = false

    const request = async () => {
      if (disposed || document.visibilityState !== 'visible' || (sentinel && !sentinel.released)) return
      try {
        sentinel = await navigator.wakeLock.request('screen')
        if (disposed) {
          void sentinel.release()
          return
        }
        setLocked(true)
        sentinel.addEventListener('release', () => setLocked(false))
      } catch {
        setLocked(false)
      }
    }
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void request()
    }

    void request()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      disposed = true
      document.removeEventListener('visibilitychange', onVisibility)
      void sentinel?.release()
      setLocked(false)
    }
  }, [active, supported])

  return { supported, locked }
}

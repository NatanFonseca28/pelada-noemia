import { useEffect, useRef, useState } from 'react'

const reduceMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Anima um número até `value` (400ms, ease-out). Sem animação com prefers-reduced-motion. */
export function useCountUp(value: number, duration = 400): number {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    const start = from.current
    if (start === value || reduceMotion()) {
      from.current = value
      setShown(value)
      return
    }
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration)
      const eased = 1 - (1 - p) ** 3
      setShown(start + (value - start) * eased)
      if (p < 1) raf = requestAnimationFrame(tick)
      else from.current = value
    }
    raf = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(raf)
      from.current = value
    }
  }, [value, duration])
  return shown
}

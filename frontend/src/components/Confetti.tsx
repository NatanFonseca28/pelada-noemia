import type { CSSProperties } from 'react'
import { TEAM_COLORS } from '@/lib/teamColors'

const COLORS = Object.values(TEAM_COLORS)
const PIECES = 14

/** Confetes em CSS: 14 partículas nas cores dos times, 1,5s, uma única vez (some em reduced-motion). */
export function Confetti() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {Array.from({ length: PIECES }, (_, i) => {
        const left = 6 + ((i * 89) % 88)
        const style = {
          left: `${left}%`,
          top: '-8px',
          width: i % 3 ? 7 : 5,
          height: i % 3 ? 11 : 7,
          background: COLORS[i % COLORS.length],
          borderRadius: i % 4 === 0 ? 999 : 2,
          '--dx': `${(i % 2 ? 1 : -1) * (12 + ((i * 37) % 40))}px`,
          '--rot': `${(i % 2 ? 1 : -1) * (180 + ((i * 53) % 360))}deg`,
          animation: `confetti-fall 1.5s cubic-bezier(.2,.8,.2,1) ${(i % 7) * 40}ms both`,
        } as CSSProperties
        return <span key={i} className="absolute block" style={style} />
      })}
    </div>
  )
}

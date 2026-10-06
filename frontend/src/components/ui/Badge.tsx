import type { ReactNode } from 'react'
import { cx } from './cx'

const badgeColors = {
  green: 'bg-ok/15 text-primary-ink',
  blue: 'bg-accent/15 text-accent-ink',
  yellow: 'bg-soft text-ink ring-1 ring-inset ring-line', // amarelo é só de cartão: "atenção" vira neutro com contorno
  red: 'bg-danger/15 text-danger-ink',
  gray: 'bg-soft text-ink',
}
export type BadgeColor = keyof typeof badgeColors

export function Badge({ color = 'gray', children }: { color?: BadgeColor; children: ReactNode }) {
  return <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', badgeColors[color])}>{children}</span>
}

const POSITION = {
  ZAGUEIRO: { short: 'ZAG', cls: 'bg-[#2b4a3a] text-[#d9f2e3]' },
  ALA: { short: 'ALA', cls: 'bg-[#23405e] text-[#dcebff]' },
  ATACANTE: { short: 'ATA', cls: 'bg-[#4b2d5c] text-[#f2e1fb]' },
  GOLEIRO_FIXO: { short: 'GOL', cls: 'bg-board text-board-ink ring-2 ring-inset ring-board-ink/40' },
} as const
export type PositionKey = keyof typeof POSITION

/** Badge de posição: ZAG / ALA / ATA / GOL (GOL com borda dupla). Cores fixas nos dois temas, AA. */
export function PositionBadge({ position, className }: { position: string | null | undefined; className?: string }) {
  const p = position && position in POSITION ? POSITION[position as PositionKey] : null
  return (
    <span
      className={cx('inline-grid h-6 w-10 shrink-0 place-items-center rounded-[4px] font-display text-[13px] font-bold tracking-wide', p ? p.cls : 'bg-soft text-muted', className)}
      title={position ?? 'Posição a definir'}
    >
      {p ? p.short : '—'}
    </span>
  )
}

/** Cartão (glifo): retângulo preenchido. Amarelo/vermelho são exclusivos daqui. */
export function CardIcon({ color, size = 14, animate }: { color: 'yellow' | 'red'; size?: number; animate?: boolean }) {
  return (
    <span
      aria-hidden
      className={cx('inline-block shrink-0 rounded-[2px]', color === 'yellow' ? 'bg-card-yellow' : 'bg-card-red', animate && color === 'yellow' && 'anim-tilt')}
      style={{ width: size * 0.72, height: size }}
    />
  )
}

/** Indicador pulsante (ex.: partida em andamento, cronômetro rodando). */
export function LiveDot({ label = 'Em andamento' }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent-ink">
      <span className="anim-live h-2 w-2 rounded-full bg-accent" aria-hidden />
      {label}
    </span>
  )
}

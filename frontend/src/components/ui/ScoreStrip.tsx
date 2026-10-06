import type { ReactNode } from 'react'
import { teamAbbr, teamColor } from '@/lib/teamColors'
import { cx } from './cx'
import { TeamShield } from './TeamShield'

export interface StripTeam {
  name: string
  color?: string | null
}

type Size = 'sm' | 'md' | 'lg' | 'xl'

// Larguras calculadas para caber em 360px sem rolagem: abaixo de 380px o escudo some (fica a faixa de cor + sigla)
const S: Record<Size, { h: string; score: string; abbr: string; shield: number; shieldCls: string; pad: string; scoreW: string; fullName: boolean }> = {
  sm: { h: 'h-10', score: 'text-xl', abbr: 'text-base', shield: 20, shieldCls: 'hidden min-[380px]:block', pad: 'px-2', scoreW: 'w-9', fullName: false },
  md: { h: 'h-14', score: 'text-3xl', abbr: 'text-xl', shield: 24, shieldCls: 'hidden min-[380px]:block', pad: 'px-2 sm:px-3', scoreW: 'w-10 sm:w-12', fullName: true },
  lg: { h: 'h-20', score: 'text-5xl', abbr: 'text-3xl', shield: 34, shieldCls: 'hidden min-[380px]:block', pad: 'px-2 sm:px-4', scoreW: 'w-14 sm:w-20', fullName: true },
  xl: { h: 'h-24 sm:h-28', score: 'text-6xl sm:text-score-xl', abbr: 'text-3xl sm:text-4xl', shield: 40, shieldCls: 'hidden min-[420px]:block', pad: 'px-2 sm:px-4', scoreW: 'w-16 sm:w-28', fullName: true },
}

/**
 * Tarja de placar (elemento-assinatura): cor do time · escudo · sigla · placar | centro | placar · sigla · escudo · cor.
 * O bloco do placar é sempre escuro (estilo transmissão). Times ainda indefinidos mostram `homeLabel`/`awayLabel`.
 */
export function ScoreStrip({
  home,
  away,
  homeLabel,
  awayLabel,
  homeScore,
  awayScore,
  center,
  size = 'md',
  winnerSide,
  live,
  className,
}: {
  home: StripTeam | null
  away: StripTeam | null
  homeLabel?: string
  awayLabel?: string
  homeScore?: number | null
  awayScore?: number | null
  center?: ReactNode
  size?: Size
  winnerSide?: 'home' | 'away' | null
  /** anuncia mudanças de placar para leitores de tela */
  live?: boolean
  className?: string
}) {
  const s = S[size]
  const hasScore = homeScore != null && awayScore != null
  const label = `${home?.name ?? homeLabel ?? 'A definir'} ${hasScore ? homeScore : ''} × ${hasScore ? awayScore : ''} ${away?.name ?? awayLabel ?? 'A definir'}`

  const side = (team: StripTeam | null, fallback: string | undefined, right: boolean, dim: boolean) => (
    <div className={cx('flex min-w-0 flex-1 items-center gap-1.5 sm:gap-2', s.pad, right && 'flex-row-reverse text-right', dim && 'opacity-55')}>
      <span className={cx('self-stretch', size === 'sm' ? 'w-1' : 'w-1.5')} style={{ background: team ? teamColor(team.name, team.color) : 'rgb(var(--line))' }} aria-hidden />
      {team ? (
        <span className={s.shieldCls}>
          <TeamShield name={team.name} color={team.color} size={s.shield} />
        </span>
      ) : null}
      <span className={cx('min-w-0 truncate font-display font-bold uppercase tracking-wide', team ? s.abbr : 'text-sm font-medium normal-case italic text-muted')}>
        {team ? (
          <>
            {/* sigla no celular; nome completo a partir de 640px */}
            <span aria-hidden className={s.fullName ? 'sm:hidden' : undefined}>{teamAbbr(team.name)}</span>
            {s.fullName && <span aria-hidden className="hidden sm:inline">{team.name}</span>}
            <span className="sr-only">Time {team.name}</span>
          </>
        ) : (
          fallback ?? 'A definir'
        )}
      </span>
    </div>
  )

  return (
    <div
      className={cx('chamfer flex items-stretch bg-surface ring-1 ring-inset ring-line', s.h, className)}
      role="group"
      aria-label={label}
      aria-live={live ? 'polite' : undefined}
    >
      {side(home, homeLabel, false, winnerSide === 'away')}
      <div className="flex items-stretch bg-board text-board-ink">
        <span className={cx('tabular grid place-items-center font-display font-extrabold', s.score, s.scoreW)}>{hasScore ? homeScore : '–'}</span>
        {center !== undefined && <div className="grid min-w-[3rem] place-items-center border-x border-board-ink/15 px-1.5 text-center font-display text-sm font-semibold">{center}</div>}
        <span className={cx('tabular grid place-items-center font-display font-extrabold', s.score, s.scoreW)}>{hasScore ? awayScore : '–'}</span>
      </div>
      {side(away, awayLabel, true, winnerSide === 'home')}
    </div>
  )
}

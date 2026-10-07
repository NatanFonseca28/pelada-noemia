import type { MatchItem } from '@/api/types'
import { cx } from './ui'

/** "⚽ Saída: Time Azul" — quem começa com a bola (mata-mata: melhor campanha). */
export function KickoffNote({ match, className }: { match: MatchItem; className?: string }) {
  const team = match.kickoff_team_id === match.home?.id ? match.home : match.kickoff_team_id === match.away?.id ? match.away : null
  if (!team || match.status === 'ENCERRADA') return null
  const knockout = match.stage !== 'GRUPO' && match.stage !== 'AMISTOSO'
  return (
    <p className={cx('flex items-center gap-1.5 text-xs text-muted', className)}>
      <span aria-hidden>⚽</span>
      <span>
        Saída: <strong className="font-semibold text-ink">Time {team.name}</strong>
        {knockout && ' (melhor campanha)'}
      </span>
    </p>
  )
}

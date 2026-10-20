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

/** "🧤 Goleiro: Fulano joga pelo Time Azul" — goleiro fixo da pelada (sem time) em cada lado desta partida. */
export function GoalkeeperNote({ match, className }: { match: MatchItem; className?: string }) {
  if (!match.goalkeepers?.length || match.status === 'ENCERRADA') return null
  return (
    <>
      {match.goalkeepers.map((g) => {
        const team = g.team_id === match.home?.id ? match.home : g.team_id === match.away?.id ? match.away : null
        if (!team) return null
        return (
          <p key={g.player_id} className={cx('flex items-center gap-1.5 text-xs text-muted', className)}>
            <span aria-hidden>🧤</span>
            <span>
              Goleiro: <strong className="font-semibold text-ink">{g.player_name}</strong> joga pelo{' '}
              <strong className="font-semibold text-ink">Time {team.name}</strong>
            </span>
          </p>
        )
      })}
    </>
  )
}

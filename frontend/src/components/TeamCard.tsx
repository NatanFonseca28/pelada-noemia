import { useEffect, useRef, type CSSProperties, type DragEvent, type ReactNode } from 'react'
import { Hand, Shield } from 'lucide-react'
import type { TeamItem, TeamPlayerItem } from '@/api/types'
import { slotPositionShort } from '@/lib/labels'
import { teamColor, teamInk } from '@/lib/teamColors'
import { Badge, ICON_STROKE, cx } from './ui'

export const DRAG_MIME = 'application/x-pelada-player'

export function PlayerChip({
  player,
  draggable,
  onClick,
  index = 0,
  jump,
}: {
  player: TeamPlayerItem
  draggable?: boolean
  onClick?: () => void
  /** posição na lista: escalona a entrada em 30ms */
  index?: number
  /** acabou de chegar neste time: faz o "pulo" */
  jump?: boolean
}) {
  const gk = player.role === 'GOLEIRO_FIXO'
  const rot = player.role === 'REVEZAMENTO'
  const sub = player.filled_by !== 'PRIMARIA' && !rot
  return (
    <li
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData(DRAG_MIME, String(player.player_id))}
      onClick={onClick}
      style={{ '--i': index } as CSSProperties}
      className={cx(
        'flex min-h-[44px] items-center gap-2 rounded-btn px-2 py-1.5 text-sm',
        jump ? 'anim-jump' : 'anim-rise',
        onClick && 'cursor-pointer hover:bg-soft',
        draggable && 'cursor-grab active:cursor-grabbing',
      )}
    >
      <span className={cx('w-9 shrink-0 rounded-full py-0.5 text-center text-[11px] font-bold', gk ? 'bg-primary/15 text-primary-ink' : 'bg-soft text-muted')}>
        {slotPositionShort[player.position] ?? player.position}
      </span>
      <span className="min-w-0 flex-1 truncate">{player.name}</span>
      {rot && <Badge color="blue">🧤 reveza</Badge>}
      {sub && <Badge color="yellow">{player.filled_by === 'SEM_POSICAO' ? 'coringa' : 'improvisado'}</Badge>}
      {player.moved_manually && (
        <Hand size={14} strokeWidth={ICON_STROKE} className="text-muted" aria-label="Ajustado manualmente" />
      )}
    </li>
  )
}

export function TeamCard({
  team,
  editable,
  onDropPlayer,
  onPlayerClick,
  footer,
}: {
  team: TeamItem
  editable?: boolean
  onDropPlayer?: (playerId: number) => void
  onPlayerClick?: (p: TeamPlayerItem) => void
  footer?: ReactNode
}) {
  const color = teamColor(team.name, team.color)

  // Detecta quem acabou de chegar (para o "pulo"); na 1ª renderização ninguém pula
  const seen = useRef<Set<number> | null>(null)
  const ids = team.players.map((p) => p.player_id)
  const previous = seen.current
  const arrived = previous ? new Set(ids.filter((id) => !previous.has(id))) : new Set<number>()
  useEffect(() => {
    seen.current = new Set(ids)
  })

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    const id = Number(e.dataTransfer.getData(DRAG_MIME))
    if (id) onDropPlayer?.(id)
  }
  return (
    <div
      className="card overflow-hidden border-t-[3px]"
      style={{ borderTopColor: color }}
      onDragOver={editable ? (e) => e.preventDefault() : undefined}
      onDrop={editable ? onDrop : undefined}
    >
      <div className="flex items-center justify-between px-3 py-2" style={{ background: color, color: teamInk(color) }}>
        {/* 19px negrito = texto grande (AA 3:1) para a tinta #0e1a12 sobre as cores de time */}
        <span className="font-display text-[19px] font-bold leading-tight">Time {team.name}</span>
        {/* texto pequeno vai num chip claro para manter AA 4.5:1 */}
        <span className="rounded-full bg-surface/90 px-2 py-0.5 text-xs font-semibold text-ink">{team.line_count} na linha</span>
      </div>
      <ul className="space-y-0.5 p-2">
        {team.players.map((p, i) => (
          <PlayerChip
            key={p.player_id}
            player={p}
            index={i}
            jump={arrived.has(p.player_id)}
            draggable={editable}
            onClick={onPlayerClick ? () => onPlayerClick(p) : undefined}
          />
        ))}
      </ul>
      <div className="flex items-center gap-1.5 border-t border-line px-3 py-2 text-xs text-muted">
        <Shield size={14} strokeWidth={ICON_STROKE} aria-hidden />
        {team.has_fixed_gk ? 'Goleiro fixo' : team.has_rotation_gk ? 'Revezamento no gol' : team.uses_volunteer_gk ? 'Voluntário do time de fora' : 'Sem goleiro'}
        {footer}
      </div>
    </div>
  )
}

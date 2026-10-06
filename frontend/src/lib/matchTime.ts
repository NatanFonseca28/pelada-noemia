import type { MatchItem } from '@/api/types'
import { formatClock } from '@/hooks/useStopwatch'

/** Tempo da partida registrado no servidor: jogado (sem pausas) e total (com pausas). */
export function matchDuration(m: Pick<MatchItem, 'started_at' | 'ended_at' | 'elapsed_before_pause'>) {
  const played = m.elapsed_before_pause > 0 ? m.elapsed_before_pause * 1000 : null
  const wall = m.started_at && m.ended_at ? new Date(m.ended_at).getTime() - new Date(m.started_at).getTime() : null
  if (played === null && wall === null) return null
  return {
    played: played === null ? null : formatClock(played),
    wall: wall === null ? null : formatClock(wall),
  }
}

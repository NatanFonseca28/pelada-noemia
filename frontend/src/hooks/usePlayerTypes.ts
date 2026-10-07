import { useMemo } from 'react'
import { usePlayers } from '@/api/queries'

/** Mapa id → tipo (mensalista/diarista) a partir do elenco já em cache; para dados que só trazem o nome. */
export function usePlayerTypes() {
  const { data } = usePlayers()
  return useMemo(() => new Map((data ?? []).map((p) => [p.id, p.type] as const)), [data])
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { CatalogCompetition } from './types'

/** Campeonatos (football-data.org) para dar nomes de clubes aos times do sorteio. */
export function useCompetitions(enabled = true) {
  return useQuery({ queryKey: ['catalog', 'competitions'], queryFn: () => api<CatalogCompetition[]>('/catalog/competitions'), enabled })
}

/** Só o superadmin: atualiza clubes e escudos em segundo plano (~1,5 min). */
export function useSyncCatalog() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<{ message: string }>('/catalog/sync', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog'] }),
  })
}

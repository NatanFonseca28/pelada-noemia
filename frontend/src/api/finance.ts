import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './client'
import type { CashEntry, Collection, Delinquent, FeeCell, FinanceConfig, FinanceOverview, ImportResult } from './types'

const invalidateFinance = (qc: ReturnType<typeof useQueryClient>) => qc.invalidateQueries({ queryKey: ['finance'] })

export function useFinanceOverview(year: number) {
  return useQuery({
    queryKey: ['finance', 'overview', year],
    queryFn: () => api<FinanceOverview>(`/finance/overview?year=${year}`),
  })
}

/** Inadimplentes (mês atual e anterior) com contato — base da futura cobrança por WhatsApp. */
export function useDelinquents(enabled = true) {
  return useQuery({ queryKey: ['finance', 'delinquents'], queryFn: () => api<Delinquent[]>('/finance/delinquents'), enabled })
}

export function useSetFee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { player_id: number; month: string; amount: string | null; marker: string | null }) =>
      api<FeeCell | null>('/finance/fees', { method: 'PUT', body: json(data) }),
    onSuccess: () => invalidateFinance(qc),
  })
}

export function useCashEntries(year: number) {
  return useQuery({
    queryKey: ['finance', 'entries', year],
    queryFn: () => api<CashEntry[]>(`/finance/entries?year=${year}`),
  })
}

export function useSaveEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Omit<CashEntry, 'id'> }) =>
      id
        ? api<CashEntry>(`/finance/entries/${id}`, { method: 'PUT', body: json(data) })
        : api<CashEntry>('/finance/entries', { method: 'POST', body: json(data) }),
    onSuccess: () => invalidateFinance(qc),
  })
}

export function useDeleteEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api(`/finance/entries/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidateFinance(qc),
  })
}

export function useCollections() {
  return useQuery({ queryKey: ['finance', 'collections'], queryFn: () => api<Collection[]>('/finance/collections') })
}

export function useCollectionMutations() {
  const qc = useQueryClient()
  const done = { onSuccess: () => invalidateFinance(qc) }
  return {
    create: useMutation({
      mutationFn: (data: { title: string; amount_per_person: string }) =>
        api<Collection>('/finance/collections', { method: 'POST', body: json(data) }),
      ...done,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api(`/finance/collections/${id}`, { method: 'DELETE' }),
      ...done,
    }),
    addItem: useMutation({
      mutationFn: ({ collectionId, ...data }: { collectionId: number; name: string; player_id: number | null }) =>
        api<Collection>(`/finance/collections/${collectionId}/items`, { method: 'POST', body: json(data) }),
      ...done,
    }),
    updateItem: useMutation({
      mutationFn: ({ id, ...data }: { id: number; paid?: boolean; amount?: string; player_id?: number | null }) =>
        api<Collection>(`/finance/collection-items/${id}`, { method: 'PATCH', body: json(data) }),
      ...done,
    }),
    removeItem: useMutation({
      mutationFn: (id: number) => api<Collection>(`/finance/collection-items/${id}`, { method: 'DELETE' }),
      ...done,
    }),
  }
}

export function useSaveFinanceConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FinanceConfig) => api<FinanceConfig>('/finance/config', { method: 'PUT', body: json(data) }),
    onSuccess: () => invalidateFinance(qc),
  })
}

export function useImportSheet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return api<ImportResult>('/finance/import', { method: 'POST', body })
    },
    onSuccess: () => {
      invalidateFinance(qc)
      qc.invalidateQueries({ queryKey: ['players'] })
    },
  })
}

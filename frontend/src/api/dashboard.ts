import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { Dashboard, YearSummary } from './types'

export function useDashboard() {
  return useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') })
}

export function useYearSummary(year: number) {
  return useQuery({ queryKey: ['dashboard', 'year-summary', year], queryFn: () => api<YearSummary>(`/dashboard/year-summary?year=${year}`) })
}

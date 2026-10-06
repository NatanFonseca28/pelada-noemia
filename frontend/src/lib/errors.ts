import { ApiError } from '@/api/client'

/** Mensagem legível de um erro da API (ou o texto padrão). */
export const errorMessage = (err: unknown, fallback = 'Não foi possível carregar.') =>
  err instanceof ApiError ? err.message : fallback

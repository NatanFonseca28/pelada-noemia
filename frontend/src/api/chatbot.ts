import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, json } from './client'

export interface ChatbotStatus {
  enabled: boolean
  /** open = conectado; connecting; close/missing = desconectado; offline = Evolution API fora; unconfigured */
  state: string
  daily_limit: number
  charges_today: number
  pending: number
  owner_user_id: number | null
  owner_name: string | null
}

export interface ChargeReply {
  id: number
  player_id: number
  name: string
  phone: string | null
  kind: 'PAGO' | 'FORA' | 'FALAR'
  months: string[]
  amount: string
  media_url: string | null
  has_document: boolean
  note: string | null
  status: string
  created_at: string
}

const invalidate = (qc: ReturnType<typeof useQueryClient>) => {
  qc.invalidateQueries({ queryKey: ['chatbot'] })
  qc.invalidateQueries({ queryKey: ['finance'] })
}

/** Status do chatbot; enquanto há fila, atualiza a cada 5 s para mostrar o progresso. */
export function useChatbotStatus(enabled = true) {
  return useQuery({
    queryKey: ['chatbot', 'status'],
    queryFn: () => api<ChatbotStatus>('/chatbot/status'),
    enabled,
    refetchInterval: (q) => ((q.state.data?.pending ?? 0) > 0 ? 5_000 : false),
  })
}

export function useChatbotReplies(enabled = true) {
  return useQuery({
    queryKey: ['chatbot', 'replies'],
    queryFn: () => api<ChargeReply[]>('/chatbot/replies'),
    enabled,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  })
}

export function useChatbotCharge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ playerId, force = false }: { playerId?: number; force?: boolean }) =>
      api<{ queued: string[]; skipped: { name: string; reason: string }[] }>(
        playerId ? `/chatbot/charge/${playerId}` : '/chatbot/charge-all',
        { method: 'POST', body: playerId ? json({ force }) : undefined },
      ),
    onSuccess: () => invalidate(qc),
  })
}

export function useResolveReply() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, approve }: { id: number; approve: boolean }) =>
      api(`/chatbot/replies/${id}/${approve ? 'confirm' : 'reject'}`, { method: 'POST' }),
    onSuccess: () => invalidate(qc),
  })
}

/** Só o superadmin. */
export function useChatbotAdmin() {
  const qc = useQueryClient()
  const done = () => qc.invalidateQueries({ queryKey: ['chatbot'] })
  return {
    connect: useMutation({ mutationFn: () => api<ChatbotStatus & { qr: string | null }>('/chatbot/connect', { method: 'POST' }), onSuccess: done }),
    disconnect: useMutation({ mutationFn: () => api<ChatbotStatus>('/chatbot/disconnect', { method: 'POST' }), onSuccess: done }),
    save: useMutation({
      mutationFn: (data: { enabled: boolean; daily_limit: number; owner_user_id: number | null }) =>
        api<ChatbotStatus>('/chatbot/settings', { method: 'PUT', body: json(data) }),
      onSuccess: done,
    }),
  }
}

import { useState } from 'react'
import { useAccessLog } from '@/api/access'
import type { AccessEvent, AccessLogEntry } from '@/api/types'
import { Badge, Button, Card, EmptyState, PageHeader, QueryState, SkeletonList } from '@/components/ui'
import { formatDateTime } from '@/lib/labels'

const eventInfo: Record<AccessEvent, { label: string; color: 'green' | 'red' | 'yellow' | 'gray' }> = {
  LOGIN: { label: 'Entrou', color: 'green' },
  LOGOUT: { label: 'Saiu', color: 'gray' },
  LOGIN_FALHOU: { label: 'Senha errada', color: 'yellow' },
  BLOQUEADO: { label: 'Tentou com conta bloqueada', color: 'red' },
  CONTA_BLOQUEADA: { label: 'Conta bloqueada', color: 'red' },
}

/** "Mozilla/5.0 (Linux; Android 14…) Chrome/…" → "Chrome no Android". */
function device(ua: string | null): string {
  if (!ua) return '—'
  const browser = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Chrome\//.test(ua) ? 'Chrome'
    : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : ua.split('/')[0]
  const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iPhone' : /Windows/.test(ua) ? 'Windows'
    : /Mac OS X/.test(ua) ? 'Mac' : /Linux/.test(ua) ? 'Linux' : ''
  return os ? `${browser} no ${os}` : browser
}

function Row({ e }: { e: AccessLogEntry }) {
  const info = eventInfo[e.event] ?? { label: e.event, color: 'gray' as const }
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 p-3 text-sm">
      <Badge color={info.color}>{info.label}</Badge>
      <span className="min-w-0 flex-1">
        <span className="font-medium">{e.user_name ?? e.email}</span>
        {e.user_name && <span className="text-muted"> ({e.email})</span>}
      </span>
      <span className="text-xs text-muted" title={e.user_agent ?? undefined}>
        {device(e.user_agent)}{e.ip ? `, IP ${e.ip}` : ''}
      </span>
      <time className="tabular w-full text-xs text-muted sm:w-auto">{formatDateTime(e.created_at)}</time>
    </div>
  )
}

export function AccessLogPage() {
  const [email, setEmail] = useState('')
  const [event, setEvent] = useState<AccessEvent | ''>('')
  const [limit, setLimit] = useState(100)
  const query = useAccessLog({ email: email.trim() || undefined, event, limit })
  const rows = query.data ?? []

  return (
    <>
      <PageHeader title="Log de acessos" />
      <div className="mb-4 flex flex-wrap gap-3">
        <input className="input max-w-xs" placeholder="Filtrar por e-mail" aria-label="Filtrar por e-mail" value={email} onChange={(e) => setEmail(e.target.value)} />
        <select className="input max-w-xs" aria-label="Filtrar por evento" value={event} onChange={(e) => setEvent(e.target.value as AccessEvent | '')}>
          <option value="">Todos os eventos</option>
          {Object.entries(eventInfo).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <QueryState query={query} isEmpty={!rows.length} skeleton={<SkeletonList rows={8} />} empty={<EmptyState title="Nenhum acesso registrado" />}>
        <Card className="divide-y divide-line">
          {rows.map((e) => <Row key={e.id} e={e} />)}
        </Card>
        {rows.length >= limit && limit < 500 && (
          <div className="mt-3 flex justify-center">
            <Button variant="secondary" loading={query.isFetching} onClick={() => setLimit((l) => Math.min(l + 100, 500))}>Carregar mais</Button>
          </div>
        )}
      </QueryState>
    </>
  )
}

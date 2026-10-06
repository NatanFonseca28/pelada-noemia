import { useState } from 'react'
import { useAudit } from '@/api/queries'
import { Card, EmptyState, PageHeader, Spinner } from '@/components/ui'
import { actionLabel, entityLabel, formatDateTime } from '@/lib/labels'

function Diff({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])).filter(
    (k) => JSON.stringify(before?.[k]) !== JSON.stringify(after?.[k]),
  )
  if (!keys.length) return null
  const fmt = (v: unknown) => (v === undefined ? '—' : JSON.stringify(v))
  return (
    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
      {keys.map((k) => (
        <div key={k} className="contents">
          <dt className="font-mono text-muted">{k}</dt>
          <dd className="break-all">
            {before && <span className="text-danger-ink line-through">{fmt(before[k])}</span>}
            {before && after && ' → '}
            {after && <span className="text-primary-ink">{fmt(after[k])}</span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function AuditPage() {
  const [entity, setEntity] = useState('')
  const { data, isLoading } = useAudit(entity || undefined)

  return (
    <>
      <PageHeader title="Auditoria" />
      <select className="input mb-4 max-w-xs" value={entity} onChange={(e) => setEntity(e.target.value)} aria-label="Filtrar por entidade">
        <option value="">Todas as entidades</option>
        {Object.entries(entityLabel).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      {isLoading ? (
        <Spinner />
      ) : !data?.length ? (
        <EmptyState>Nenhum registro.</EmptyState>
      ) : (
        <Card className="divide-y divide-line">
          {data.map((log) => (
            <div key={log.id} className="p-3 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p>
                  <span className="font-medium">{log.user_name ?? 'Sistema'}</span>{' '}
                  {(actionLabel[log.action] ?? log.action).toLowerCase()}{' '}
                  <span className="font-medium">{entityLabel[log.entity] ?? log.entity}</span>
                  {log.entity_id && <span className="text-muted"> #{log.entity_id}</span>}
                </p>
                <time className="text-xs text-muted">{formatDateTime(log.created_at)}</time>
              </div>
              <Diff before={log.before} after={log.after} />
            </div>
          ))}
        </Card>
      )}
    </>
  )
}

import type { CSSProperties, ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { errorMessage } from '@/lib/errors'
import { cx, ICON_STROKE } from './cx'

export function Spinner({ small }: { small?: boolean }) {
  return (
    <span
      role="status"
      aria-label="Carregando"
      className={cx('inline-block animate-spin rounded-full border-2 border-current border-t-transparent', small ? 'h-4 w-4' : 'h-8 w-8 text-primary-ink')}
    />
  )
}

/** Bloco de carregamento com shimmer. */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div aria-hidden className={cx('skeleton', className)} style={style} />
}

/** Várias linhas de skeleton (listas e tabelas). */
export function SkeletonList({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="Carregando" className={cx('space-y-2', className)}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  )
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'success' | 'info'; children: ReactNode }) {
  const styles = {
    error: 'border-danger/40 bg-danger/10 text-danger-ink',
    success: 'border-ok/40 bg-ok/10 text-primary-ink',
    info: 'border-line bg-soft text-ink',
  }
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={cx('rounded-btn border px-3 py-2 text-sm', styles[kind])}>
      {children}
    </div>
  )
}

/** Estado vazio: diz o que fazer, não só que está vazio. */
export function EmptyState({ title, children, icon, action }: { title?: string; children?: ReactNode; icon?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
      {icon && <div className="mb-1 grid h-12 w-12 place-items-center rounded-full bg-soft text-muted">{icon}</div>}
      {title && <p className="font-display text-xl font-semibold text-ink">{title}</p>}
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

/** Estado de erro com ação de tentar de novo. */
export function ErrorState({ error, onRetry, title = 'Não foi possível carregar' }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 px-4 py-10 text-center">
      <div className="mb-1 grid h-12 w-12 place-items-center rounded-full bg-danger/10 text-danger-ink">
        <AlertTriangle size={22} strokeWidth={ICON_STROKE} aria-hidden />
      </div>
      <p className="font-display text-xl font-semibold text-ink">{title}</p>
      <p className="max-w-sm text-sm text-muted">{errorMessage(error, 'Verifique sua conexão e tente de novo.')}</p>
      {onRetry && (
        <button onClick={onRetry} className="press mt-2 inline-flex min-h-[44px] items-center gap-2 rounded-btn border border-line bg-surface px-4 text-sm font-medium hover:bg-soft">
          <RotateCcw size={16} strokeWidth={ICON_STROKE} aria-hidden /> Tentar de novo
        </button>
      )}
    </div>
  )
}

interface QueryLike {
  isLoading: boolean
  error: unknown
  refetch?: () => unknown
}

/**
 * Padroniza os 4 estados de uma tela: carregando (skeleton), erro (tentar de novo),
 * vazio (com orientação) e sucesso (children).
 */
export function QueryState({ query, isEmpty, empty, skeleton, children }: {
  query: QueryLike
  isEmpty?: boolean
  empty?: ReactNode
  skeleton?: ReactNode
  children: ReactNode
}) {
  if (query.isLoading) return <>{skeleton ?? <SkeletonList />}</>
  if (query.error) return <ErrorState error={query.error} onRetry={query.refetch ? () => query.refetch?.() : undefined} />
  if (isEmpty) return <>{empty ?? <EmptyState title="Nada por aqui ainda" />}</>
  return <>{children}</>
}

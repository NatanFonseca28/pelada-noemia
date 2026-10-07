import type { PlayerType } from '@/api/types'
import { usePlayerTypes } from '@/hooks/usePlayerTypes'
import { playerTypeLabel as playerTypeName } from '@/lib/labels'
import { cx } from './cx'

/**
 * Identificação do tipo de jogador, igual em todo o app:
 * mensalista = círculo cheio azul, diarista = anel laranja (forma + cor, não depende só da cor).
 */
export function TypeDot({ type, className }: { type: PlayerType | null | undefined; className?: string }) {
  if (!type) return null
  return (
    <span
      title={playerTypeName[type]}
      className={cx(
        'inline-block h-2.5 w-2.5 shrink-0 rounded-full',
        type === 'MENSALISTA' ? 'bg-mensalista' : 'border-[2.5px] border-diarista',
        className,
      )}
    >
      <span className="sr-only">{playerTypeName[type]}: </span>
    </span>
  )
}

export function TypeBadge({ type }: { type: PlayerType }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold',
        type === 'MENSALISTA' ? 'bg-mensalista/15 text-mensalista' : 'bg-diarista/15 text-diarista',
      )}
    >
      <TypeDot type={type} />
      {playerTypeName[type]}
    </span>
  )
}

/** Nome do jogador com a marca do tipo. Passe `type` quando já vier no dado; senão é buscado pelo `id`. */
export function PlayerName({ id, name, type, className }: {
  id?: number | null
  name: string
  type?: PlayerType | null
  className?: string
}) {
  const types = usePlayerTypes()
  const resolved = type ?? (id != null ? types.get(id) : undefined)
  return (
    <span className={cx('inline-flex min-w-0 items-center gap-1.5', className)}>
      <TypeDot type={resolved} />
      <span className="truncate">{name}</span>
    </span>
  )
}

/** Legenda curta para telas com muitas pessoas. */
export function TypeLegend({ className }: { className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-3 text-xs text-muted', className)}>
      <span className="inline-flex items-center gap-1.5"><TypeDot type="MENSALISTA" /> Mensalista</span>
      <span className="inline-flex items-center gap-1.5"><TypeDot type="DIARISTA" /> Diarista</span>
    </span>
  )
}

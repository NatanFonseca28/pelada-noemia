import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useSettings } from '@/api/queries'
import { Trash2 } from 'lucide-react'
import { useCreateRound, useRounds } from '@/api/rounds'
import type { RoundSummary } from '@/api/types'
import { DeleteRoundDialog } from '@/components/rounds/DeleteRoundDialog'
import { Alert, Badge, Button, Card, EmptyState, Field, ICON_STROKE, PageHeader, Spinner } from '@/components/ui'
import { formatDate, roundStatusLabel } from '@/lib/labels'

const statusColor = { ABERTA: 'green', FECHADA: 'yellow', TIMES_TRAVADOS: 'blue', ENCERRADA: 'gray' } as const

/** Próxima ocorrência do dia da semana configurado (0 = segunda). */
function nextWeekday(weekday: number): string {
  const d = new Date()
  const jsDay = (weekday + 1) % 7 // JS: 0 = domingo
  d.setDate(d.getDate() + ((jsDay - d.getDay() + 7) % 7))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function RoundsPage() {
  const { data: rounds, isLoading } = useRounds()
  const { data: settings } = useSettings()
  const create = useCreateRound()
  const navigate = useNavigate()
  const [date, setDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<RoundSummary | null>(null)

  const defaultDate = settings ? nextWeekday(settings.weekday) : ''

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const r = await create.mutateAsync({ date: date || defaultDate })
      navigate(`/gestao/rodadas/${r.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao criar rodada')
    }
  }

  return (
    <>
      <PageHeader title="Rodadas e sorteio" />
      <Card className="mb-5 p-4">
        <form onSubmit={onCreate} className="flex flex-wrap items-end gap-3">
          <div className="w-48">
            <Field label="Nova rodada">
              <input className="input" type="date" value={date || defaultDate} onChange={(e) => setDate(e.target.value)} required />
            </Field>
          </div>
          <Button type="submit" loading={create.isPending}>Criar e abrir lista</Button>
        </form>
        {error && <div className="mt-3"><Alert>{error}</Alert></div>}
      </Card>

      {isLoading ? (
        <Spinner />
      ) : !rounds?.length ? (
        <EmptyState>Nenhuma rodada ainda. Crie a primeira acima.</EmptyState>
      ) : (
        <Card className="divide-y divide-line">
          {rounds.map((r) => (
            <div key={r.id} className="flex items-center hover:bg-soft">
              <Link to={`/gestao/rodadas/${r.id}`} className="flex min-w-0 flex-1 items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="font-medium capitalize">{formatDate(r.date)}</p>
                  <p className="text-sm text-muted">
                    {r.confirmed_count} confirmado(s){r.has_teams && ', times sorteados'}
                  </p>
                </div>
                <Badge color={statusColor[r.status]}>{roundStatusLabel[r.status]}</Badge>
              </Link>
              <button
                type="button"
                onClick={() => setDeleting(r)}
                aria-label={`Excluir rodada de ${formatDate(r.date)}`}
                className="press mr-2 grid h-11 w-11 shrink-0 place-items-center rounded-btn text-muted hover:bg-danger/10 hover:text-danger-ink"
              >
                <Trash2 size={18} strokeWidth={ICON_STROKE} aria-hidden />
              </button>
            </div>
          ))}
        </Card>
      )}
      <DeleteRoundDialog round={deleting} onClose={() => setDeleting(null)} />
    </>
  )
}

import { useMemo, useState, type ReactNode } from 'react'
import { Check, HelpCircle, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { usePlayers } from '@/api/queries'
import { useCurrentRound, useRound, useRoundActions, useRounds } from '@/api/rounds'
import type { PlayerType, Position, RoundDetail } from '@/api/types'
import { Alert, Card, EmptyState, PageHeader, PlayerName, Spinner, TypeDot, TypeLegend, cx } from '@/components/ui'
import { formatDate, positionShort, roundStatusLabel } from '@/lib/labels'

const errorText = (err: unknown) => (err instanceof ApiError ? err.message : 'Algo deu errado')

type Group = 'VAI' | 'NAO_VAI' | 'SEM_RESPOSTA'

const GROUPS: { key: Group; label: string; tone: string }[] = [
  { key: 'VAI', label: 'Vão', tone: 'text-primary-ink' },
  { key: 'NAO_VAI', label: 'Não vão', tone: 'text-danger-ink' },
  { key: 'SEM_RESPOSTA', label: 'Sem resposta', tone: 'text-muted' },
]

interface Row {
  player_id: number
  name: string
  type: PlayerType
  primary_position: Position | null
  group: Group
}

const countTypes = (rows: Row[]) => ({
  total: rows.length,
  mensalistas: rows.filter((r) => r.type === 'MENSALISTA').length,
  diaristas: rows.filter((r) => r.type === 'DIARISTA').length,
})

// ---------------------------------------------------------------- Quadro

function AttendanceBoard({ round }: { round: RoundDetail }) {
  const { data: players = [], isLoading } = usePlayers()
  const { attendance, clearAttendance } = useRoundActions(round.id)
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<Group | null>(null)
  const editable = round.status === 'ABERTA' || round.status === 'FECHADA'
  const busy = attendance.isPending || clearAttendance.isPending
  const error = attendance.error ?? clearAttendance.error

  const rows = useMemo<Row[]>(() => {
    const answered = new Set([...round.attendances, ...round.absences].map((a) => a.player_id))
    return [
      ...round.attendances.map((a) => ({ ...a, group: 'VAI' as const })),
      ...round.absences.map((a) => ({ ...a, group: 'NAO_VAI' as const })),
      ...players
        .filter((p) => p.active && !answered.has(p.id))
        .map((p) => ({ player_id: p.id, name: p.display_name, type: p.type, primary_position: p.primary_position, group: 'SEM_RESPOSTA' as const })),
    ]
  }, [round.attendances, round.absences, players])

  const term = q.trim().toLowerCase()
  const visible = rows.filter((r) => (!filter || r.group === filter) && r.name.toLowerCase().includes(term))

  const set = (r: Row, target: Group) => {
    if (r.group === target) return
    if (target === 'SEM_RESPOSTA') clearAttendance.mutate(r.player_id)
    else attendance.mutate({ playerId: r.player_id, confirmed: target === 'VAI' })
  }

  return (
    <>
      <div className="mb-4 grid grid-cols-3 gap-2 sm:gap-3">
        {GROUPS.map((g) => {
          const c = countTypes(rows.filter((r) => r.group === g.key))
          const on = filter === g.key
          return (
            <button
              key={g.key}
              onClick={() => setFilter(on ? null : g.key)}
              aria-pressed={on}
              className={cx('card p-3 text-left transition sm:p-4', on ? 'ring-2 ring-primary' : 'hover:bg-soft')}
            >
              <p className={cx('text-xs font-semibold uppercase sm:text-sm', g.tone)}>{g.label}</p>
              <p className="font-display text-3xl font-bold leading-tight sm:text-4xl">{c.total}</p>
              <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                <span className="inline-flex items-center gap-1">
                  <TypeDot type="MENSALISTA" /> {c.mensalistas} <span className="hidden sm:inline">mensalista{c.mensalistas === 1 ? '' : 's'}</span>
                </span>
                <span className="inline-flex items-center gap-1">
                  <TypeDot type="DIARISTA" /> {c.diaristas} <span className="hidden sm:inline">diarista{c.diaristas === 1 ? '' : 's'}</span>
                </span>
              </p>
            </button>
          )
        })}
      </div>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <input className="input max-w-xs" placeholder="Buscar jogador" value={q} onChange={(e) => setQ(e.target.value)} />
          <TypeLegend />
        </div>
        {error && <div className="mb-2"><Alert>{errorText(error)}</Alert></div>}
        {!editable && <div className="mb-2"><Alert kind="info">Times travados: destrave a rodada para alterar a lista.</Alert></div>}
        {isLoading ? (
          <Spinner />
        ) : visible.length === 0 ? (
          <EmptyState>{term ? 'Nenhum jogador com esse nome.' : 'Ninguém neste grupo.'}</EmptyState>
        ) : (
          <div className="space-y-4">
            {GROUPS.filter((g) => !filter || g.key === filter).map((g) => {
              const list = visible.filter((r) => r.group === g.key).sort((a, b) => a.name.localeCompare(b.name))
              if (!list.length) return null
              return (
                <section key={g.key}>
                  <h2 className={cx('mb-1 text-xs font-semibold uppercase', g.tone)}>{g.label} · {list.length}</h2>
                  <ul className="divide-y divide-line">
                    {list.map((r) => (
                      <li key={r.player_id} className="flex items-center gap-2 py-1.5">
                        <PlayerName name={r.name} type={r.type} className="flex-1 text-sm" />
                        <span className="w-8 text-xs text-muted">{r.primary_position ? positionShort[r.primary_position] : '—'}</span>
                        <div className="flex overflow-hidden rounded-btn border border-line text-xs" role="group" aria-label={`Presença de ${r.name}`}>
                          <ChoiceButton active={r.group === 'VAI'} disabled={!editable || busy} onClick={() => set(r, 'VAI')}
                            activeCls="bg-primary text-primary-on" label="Vai" icon={<Check size={14} strokeWidth={2.5} aria-hidden />} />
                          <ChoiceButton active={r.group === 'NAO_VAI'} disabled={!editable || busy} onClick={() => set(r, 'NAO_VAI')}
                            activeCls="bg-danger/15 text-danger-ink" label="Não vai" icon={<X size={14} strokeWidth={2.5} aria-hidden />} />
                          <ChoiceButton active={r.group === 'SEM_RESPOSTA'} disabled={!editable || busy} onClick={() => set(r, 'SEM_RESPOSTA')}
                            activeCls="bg-soft text-ink" label="Sem resposta" icon={<HelpCircle size={14} strokeWidth={2.5} aria-hidden />} />
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )
            })}
          </div>
        )}
      </Card>
    </>
  )
}

function ChoiceButton({ active, disabled, onClick, activeCls, label, icon }: {
  active: boolean
  disabled: boolean
  onClick: () => void
  activeCls: string
  label: string
  icon: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      title={label}
      className={cx(
        'flex items-center gap-1 border-l border-line px-2 py-1.5 font-medium first:border-l-0 disabled:opacity-60',
        active ? activeCls : 'text-muted hover:bg-soft',
      )}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  )
}

// ---------------------------------------------------------------- Página

function RoundPicker({ current }: { current: RoundDetail }) {
  const { data: rounds = [] } = useRounds()
  const [, setParams] = useSearchParams()
  const options = rounds.filter((r) => r.status !== 'ENCERRADA' || r.id === current.id)
  if (options.length < 2) return null
  return (
    <select className="input w-auto" value={current.id} aria-label="Rodada" onChange={(e) => setParams({ rodada: e.target.value })}>
      {options.map((r) => <option key={r.id} value={r.id}>{formatDate(r.date)}</option>)}
    </select>
  )
}

function Shell({ round, isLoading, error }: { round: RoundDetail | null | undefined; isLoading: boolean; error: unknown }) {
  if (isLoading) return <Spinner />
  if (error) return <Alert>{errorText(error)}</Alert>
  if (!round) {
    return (
      <>
        <PageHeader title="Presença" />
        <EmptyState title="Nenhuma rodada aberta" action={<Link to="/gestao/rodadas" className="font-medium text-primary-ink underline">Criar rodada</Link>}>
          Crie a rodada da semana para começar a marcar quem vai.
        </EmptyState>
      </>
    )
  }
  return (
    <>
      <PageHeader
        title={`Presença · ${formatDate(round.date)}`}
        subtitle={roundStatusLabel[round.status]}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <RoundPicker current={round} />
            <Link to={`/gestao/rodadas/${round.id}`} className="text-sm text-primary-ink hover:underline">Ir para o sorteio ›</Link>
          </div>
        }
      />
      <AttendanceBoard round={round} />
    </>
  )
}

function ByIdPage({ id }: { id: number }) {
  const { data, isLoading, error } = useRound(id)
  return <Shell round={data} isLoading={isLoading} error={error} />
}

function CurrentPage() {
  const { data, isLoading, error } = useCurrentRound()
  return <Shell round={data} isLoading={isLoading} error={error} />
}

export function AttendancePage() {
  const [params] = useSearchParams()
  const id = Number(params.get('rodada'))
  return id ? <ByIdPage key={id} id={id} /> : <CurrentPage />
}

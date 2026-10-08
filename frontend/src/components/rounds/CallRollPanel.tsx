import { ArrowLeftRight, Check, ClipboardCheck, UserX } from 'lucide-react'
import { useRoundActions } from '@/api/rounds'
import type { RoundDetail } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { Alert, Button, Card, ICON_STROKE, cx } from '@/components/ui'
import { teamColor } from '@/lib/teamColors'

type Checkin = 'PRESENTE' | 'FALTOU' | null

const dec = (n: number) => `${n > 0 ? '+' : ''}${n.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`

function CheckinToggle({ value, disabled, onChange }: { value: Checkin; disabled: boolean; onChange: (v: Checkin) => void }) {
  // tocar de novo no botão ativo desfaz (volta para "não chamado")
  const btn = (v: 'PRESENTE' | 'FALTOU', label: string) => (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={value === v}
      onClick={() => onChange(value === v ? null : v)}
      className={cx(
        'press min-h-[40px] flex-1 rounded-btn px-2 text-xs font-semibold disabled:opacity-50',
        value === v
          ? v === 'PRESENTE' ? 'bg-ok text-primary-on' : 'bg-danger text-danger-on'
          : 'border border-line text-muted hover:bg-soft',
      )}
    >
      {label}
    </button>
  )
  return <div className="flex w-[150px] shrink-0 gap-1">{btn('PRESENTE', 'Presente')}{btn('FALTOU', 'Faltou')}</div>
}

/** Chamada no local (admin e mesário) + escala de empréstimos (todos veem). */
export function CallRollPanel({ round }: { round: RoundDetail }) {
  const { hasRole } = useAuth()
  const { checkin, allPresent } = useRoundActions(round.id)
  const staff = hasRole('ADMIN', 'MESARIO')
  const editable = staff && round.status !== 'ENCERRADA'
  const status = new Map(round.attendances.map((a) => [a.player_id, a.checkin ?? null]))
  const counts = { PRESENTE: 0, FALTOU: 0, pending: 0 }
  for (const v of status.values()) counts[v ?? 'pending'] += 1
  const loans = round.loans ?? []
  const unfilled = round.unfilled ?? []
  const inTeams = new Set(round.teams.flatMap((t) => t.players.map((p) => p.player_id)))
  const others = round.attendances.filter((a) => !inTeams.has(a.player_id))
  const busy = checkin.isPending || allPresent.isPending
  const error = checkin.error ?? allPresent.error

  if (!staff && loans.length === 0 && unfilled.length === 0) return null

  const row = (id: number, name: string, extra?: string) => (
    <li key={id} className="flex items-center gap-2 py-1.5">
      <span className={cx('min-w-0 flex-1 truncate text-sm', status.get(id) === 'FALTOU' && 'text-muted line-through')}>
        {name}{extra && <span className="ml-1 text-xs text-muted">{extra}</span>}
      </span>
      {staff && <CheckinToggle value={status.get(id) ?? null} disabled={!editable || busy} onChange={(v) => checkin.mutate({ playerId: id, status: v })} />}
    </li>
  )

  return (
    <section aria-labelledby="chamada" className="mb-8 space-y-3">
      {staff && (
        <Card className="p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 id="chamada" className="flex items-center gap-2 font-display text-2xl font-bold">
              <ClipboardCheck size={22} strokeWidth={ICON_STROKE} aria-hidden /> Chamada
            </h2>
            {editable && counts.pending > 0 && (
              <Button size="sm" variant="secondary" loading={allPresent.isPending} onClick={() => allPresent.mutate()}>
                <Check size={16} strokeWidth={ICON_STROKE} aria-hidden /> Marcar os demais como presentes
              </Button>
            )}
          </div>
          <p className="mb-3 text-sm text-muted" aria-live="polite">
            <strong className="text-ink">{counts.PRESENTE}</strong> presentes · <strong className={cx(counts.FALTOU ? 'text-danger-ink' : 'text-ink')}>{counts.FALTOU}</strong> faltas · <strong className="text-ink">{counts.pending}</strong> não chamados
          </p>
          {error && <div className="mb-3"><Alert>{error instanceof Error ? error.message : 'Erro ao salvar a chamada'}</Alert></div>}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {round.teams.map((t) => (
              <div key={t.id}>
                <p className="mb-1 flex items-center gap-2 text-sm font-semibold">
                  <span className="h-3 w-3 rounded-full" style={{ background: teamColor(t.name, t.color) }} aria-hidden /> Time {t.name}
                </p>
                <ul className="divide-y divide-line/60">
                  {t.players.map((p) => row(p.player_id, p.name, p.role === 'GOLEIRO_FIXO' ? '(goleiro)' : p.role === 'REVEZAMENTO' ? '(reveza)' : undefined))}
                </ul>
              </div>
            ))}
            {others.length > 0 && (
              <div>
                <p className="mb-1 text-sm font-semibold">{round.teams.length ? 'Fora dos times' : 'Confirmados'}</p>
                <ul className="divide-y divide-line/60">{others.map((a) => row(a.player_id, a.name))}</ul>
              </div>
            )}
          </div>
          {counts.FALTOU > 0 && round.teams.length > 0 && loans.length === 0 && unfilled.length === 0 && (
            <p className="mt-3 text-xs text-muted">
              Os empréstimos aparecem aqui quando o campeonato estiver montado e algum time ficar com menos de 5 na linha.
              Time com 6 que perde 1 não precisa de empréstimo.
            </p>
          )}
        </Card>
      )}

      {(loans.length > 0 || unfilled.length > 0) && (
        <Card className="p-4">
          <h3 className="mb-1 flex items-center gap-2 font-display text-xl font-bold">
            <ArrowLeftRight size={20} strokeWidth={ICON_STROKE} aria-hidden /> Empréstimos por jogo
          </h3>
          <p className="mb-3 text-xs text-muted">
            Quem completa vem de um time que está de fora e não joga a partida seguinte, em rodízio. Se quem faltou chegar, os próximos jogos voltam ao normal.
          </p>
          <ul className="space-y-2">
            {loans.map((x) => (
              <li key={`${x.match_id}-${x.player_id}`} className={cx('rounded-btn bg-soft/50 px-3 py-2 text-sm', x.finished && 'opacity-60')}>
                <span className="font-display font-semibold text-muted">Jogo {x.match_seq}</span> · {x.match_label}
                {x.finished && <span className="ml-1 text-xs text-muted">(encerrado)</span>}
                <span className="block">
                  <strong>Time {x.team_name}</strong> completa com <strong>{x.player_name}</strong> (do {x.from_team_name}) no lugar de {x.replaces_name}
                  {x.strength_delta != null && (
                    <span className={cx('ml-1 text-xs', Math.abs(x.strength_delta) > 0.5 ? 'text-danger-ink' : 'text-muted')}>· força {dec(x.strength_delta)}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
          {unfilled.map((u) => (
            <div key={u.match_id} className="mt-2">
              <Alert kind="info">
                <UserX size={14} strokeWidth={ICON_STROKE} className="mr-1 inline" aria-hidden />
                Jogo {u.match_seq} ({u.match_label}): não há time de fora para completar (faltou {u.missing_names.join(', ')}). Ajuste os times manualmente ou jogue com um a menos.
              </Alert>
            </div>
          ))}
        </Card>
      )}
    </section>
  )
}

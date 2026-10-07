import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { CalendarX2, Check, Settings2, Trophy, UserX, X } from 'lucide-react'
import { useCurrentRound, useMyAttendance } from '@/api/rounds'
import type { RoundDetail } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { TeamCard } from '@/components/TeamCard'
import { useToast } from '@/contexts/feedback'
import { Alert, Avatar, Badge, Button, Card, EmptyState, ICON_STROKE, PageHeader, PlayerName, PositionBadge, QueryState, Skeleton, TypeLegend, cx, errorMessage } from '@/components/ui'
import { formatDate, roundStatusLabel } from '@/lib/labels'

const statusColor = { ABERTA: 'green', FECHADA: 'gray', TIMES_TRAVADOS: 'blue', ENCERRADA: 'gray' } as const
const POS_ORDER = ['GOLEIRO_FIXO', 'ZAGUEIRO', 'ALA', 'ATACANTE', null] as const

function PresenceAction({ round }: { round: RoundDetail }) {
  const my = useMyAttendance(round.id)
  const toast = useToast()
  const confirmed = round.my_status === 'CONFIRMADO'

  if (!round.my_player_id) {
    return (
      <Alert kind="info">
        Seu usuário ainda não está ligado a um jogador do elenco. Peça ao administrador para fazer o vínculo e você poderá confirmar presença por aqui.
      </Alert>
    )
  }
  if (round.status !== 'ABERTA') {
    return (
      <p className={cx('flex items-center gap-2 text-sm font-medium', confirmed ? 'text-primary-ink' : 'text-muted')}>
        {confirmed ? <Check size={18} strokeWidth={ICON_STROKE} aria-hidden /> : <CalendarX2 size={18} strokeWidth={ICON_STROKE} aria-hidden />}
        {confirmed ? 'Você está confirmado nesta rodada.' : 'A lista de presença está fechada.'}
      </p>
    )
  }
  const toggle = () =>
    my.mutate(!confirmed, {
      onSuccess: () => toast({ message: confirmed ? 'Presença cancelada' : 'Presença confirmada', tone: 'success' }),
      onError: (err) => toast({ message: errorMessage(err, 'Não foi possível atualizar sua presença'), tone: 'error' }),
    })
  return (
    <Button size="xl" className="w-full" variant={confirmed ? 'secondary' : 'primary'} loading={my.isPending} onClick={toggle}>
      {confirmed ? <X size={22} strokeWidth={ICON_STROKE} aria-hidden /> : <Check size={22} strokeWidth={ICON_STROKE} aria-hidden />}
      {confirmed ? 'Cancelar minha presença' : 'Confirmar presença'}
    </Button>
  )
}

function RoundView({ round }: { round: RoundDetail }) {
  const { hasRole } = useAuth()
  const confirmed = round.my_status === 'CONFIRMADO'
  const byPosition = POS_ORDER.map((pos) => ({ pos, people: round.attendances.filter((a) => a.primary_position === pos) })).filter((g) => g.people.length)
  const line = round.attendances.filter((a) => a.primary_position !== 'GOLEIRO_FIXO').length
  // no celular a ação fica fixa acima da barra inferior (ao alcance do polegar)
  const stickyAction = round.status === 'ABERTA' && !!round.my_player_id

  return (
    <div className={cx(stickyAction && 'pb-24 lg:pb-0')}>
      <PageHeader
        title="Rodada"
        subtitle={formatDate(round.date)}
        actions={
          <div className="flex items-center gap-2">
            <Badge color={statusColor[round.status]}>{roundStatusLabel[round.status]}</Badge>
            {hasRole('ADMIN') && (
              <Link to={`/gestao/rodadas/${round.id}`} className="press inline-flex min-h-[44px] items-center gap-1.5 rounded-btn px-3 text-sm font-medium text-primary-ink hover:bg-soft">
                <Settings2 size={16} strokeWidth={ICON_STROKE} aria-hidden /> Gerenciar
              </Link>
            )}
          </div>
        }
      />

      {/* Placar de presença + ação principal */}
      <Card className="mb-6 overflow-hidden">
        <div className="grid grid-cols-3 divide-x divide-line">
          {[
            { label: 'confirmados', value: round.confirmed_count },
            { label: 'de linha', value: line },
            { label: 'times', value: round.teams.length || '–' },
          ].map((s) => (
            <div key={s.label} className="px-3 py-4 text-center">
              <p className="tabular font-display text-4xl font-extrabold leading-none">{s.value}</p>
              <p className="mt-1 text-xs text-muted">{s.label}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-line p-4">
          <p className="mb-3 text-sm">
            {round.my_status === null ? 'Você ainda não respondeu.' : confirmed ? 'Você está na lista.' : 'Você cancelou a presença.'}
          </p>
          {/* No celular a ação fica fixa acima da barra inferior, ao alcance do polegar */}
          <div className={cx(stickyAction && 'fixed inset-x-0 bottom-[calc(60px+env(safe-area-inset-bottom))] z-header border-t border-line bg-surface/95 p-3 backdrop-blur lg:static lg:border-0 lg:bg-transparent lg:p-0')}>
            <div className="mx-auto max-w-lg lg:max-w-none">
              <PresenceAction round={round} />
            </div>
          </div>
        </div>
      </Card>

      {round.tournament_id && (
        <Link to={`/campeonato/${round.tournament_id}`} className="card press mb-6 flex min-h-[56px] items-center gap-3 px-4 hover:bg-soft">
          <Trophy size={20} strokeWidth={ICON_STROKE} className="text-accent-ink" aria-hidden />
          <span className="flex-1 font-medium">Campeonato desta rodada</span>
          <span className="text-sm text-muted">Ver jogos e classificação</span>
        </Link>
      )}

      {round.teams.length > 0 ? (
        <section aria-labelledby="times" className="mb-8">
          <h2 id="times" className="mb-3 font-display text-2xl font-bold">
            {round.status === 'TIMES_TRAVADOS' || round.status === 'ENCERRADA' ? 'Times' : 'Times sorteados (podem mudar)'}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {round.teams.map((t) => <TeamCard key={t.id} team={t} />)}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="confirmados">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="confirmados" className="font-display text-2xl font-bold">Confirmados</h2>
          <TypeLegend />
        </div>
        {round.attendances.length === 0 ? (
          <Card>
            <EmptyState icon={<UserX size={22} strokeWidth={ICON_STROKE} />} title="Ninguém confirmou ainda">
              {round.status === 'ABERTA' ? 'Seja o primeiro: confirme sua presença acima.' : 'A lista desta rodada ficou vazia.'}
            </EmptyState>
          </Card>
        ) : (
          <div className="space-y-4">
            {byPosition.map(({ pos, people }) => (
              <div key={pos ?? 'sem'}>
                <p className="mb-2 flex items-center gap-2 text-sm text-muted">
                  <PositionBadge position={pos} /> {people.length}
                </p>
                <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                  {people.map((a, i) => (
                    <li key={a.player_id} className="anim-rise flex min-h-[48px] items-center gap-2 rounded-btn bg-surface px-2 shadow-card" style={{ '--i': i } as CSSProperties}>
                      <Avatar name={a.name} size={32} type={a.type} />
                      <PlayerName name={a.name} type={a.type} className="flex-1 text-sm font-medium" />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export function RoundViewPage() {
  const query = useCurrentRound()
  const { hasRole } = useAuth()
  return (
    <QueryState
      query={query}
      isEmpty={!query.data}
      skeleton={
        <div className="space-y-4">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-44 w-full rounded-card" />
          <Skeleton className="h-64 w-full rounded-card" />
        </div>
      }
      empty={
        <>
          <PageHeader title="Rodada" />
          <Card>
            <EmptyState
              icon={<CalendarX2 size={22} strokeWidth={ICON_STROKE} />}
              title="Nenhuma rodada aberta"
              action={hasRole('ADMIN') ? <Link to="/gestao/rodadas" className="press inline-flex min-h-[44px] items-center rounded-btn bg-primary px-4 text-sm font-medium text-primary-on">Criar a rodada</Link> : undefined}
            >
              {hasRole('ADMIN') ? 'Crie a rodada de quarta para abrir a lista de presença.' : 'Quando o administrador abrir a lista da próxima quarta, você confirma presença aqui.'}
            </EmptyState>
          </Card>
        </>
      }
    >
      {query.data && <RoundView round={query.data} />}
    </QueryState>
  )
}

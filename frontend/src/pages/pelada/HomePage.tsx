import { Link } from 'react-router-dom'
import { usePageAccess } from '@/lib/pages'
import { ApiError } from '@/api/client'
import { usePlayers, useSettings } from '@/api/queries'
import { useCurrentRound, useMyAttendance } from '@/api/rounds'
import type { RoundDetail } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { TeamCard } from '@/components/TeamCard'
import { Alert, Badge, Button, Card, PageHeader, PlayerName } from '@/components/ui'
import { formatDate, roundStatusLabel, weekdayLabel } from '@/lib/labels'

function CurrentRoundCard({ round }: { round: RoundDetail }) {
  const { hasRole } = useAuth()
  const my = useMyAttendance(round.id)
  const confirmed = round.my_status === 'CONFIRMADO'
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted">Rodada</p>
          <p className="text-xl font-semibold capitalize">{formatDate(round.date)}</p>
          <p className="text-sm text-muted">{round.confirmed_count} confirmado(s) · {roundStatusLabel[round.status]}</p>
        </div>
        {round.my_player_id ? (
          round.status === 'ABERTA' ? (
            <Button size="lg" variant={confirmed ? 'secondary' : 'primary'} loading={my.isPending} onClick={() => my.mutate(!confirmed)}>
              {confirmed ? '✕ Cancelar presença' : '✓ Confirmar presença'}
            </Button>
          ) : (
            <Badge color={confirmed ? 'green' : 'gray'}>{confirmed ? 'Você está confirmado' : 'Lista fechada'}</Badge>
          )
        ) : (
          <p className="max-w-xs text-xs text-muted">Seu usuário não está vinculado a um jogador; peça ao administrador para confirmar sua presença.</p>
        )}
      </div>
      {my.error && <div className="mt-3"><Alert>{my.error instanceof ApiError ? my.error.message : 'Erro'}</Alert></div>}
      {round.tournament_id && (
        <Link to={`/campeonato/${round.tournament_id}`} className="mr-4 mt-3 inline-block text-sm font-medium text-primary-ink hover:underline">
          🏆 Ver campeonato →
        </Link>
      )}
      {hasRole('ADMIN') && (
        <Link to={`/gestao/rodadas/${round.id}`} className="mt-3 inline-block text-sm font-medium text-primary-ink hover:underline">
          Gerenciar rodada e sorteio →
        </Link>
      )}
      {round.teams.length > 0 ? (
        <div className="mt-4">
          <h3 className="mb-2 font-semibold">Times {round.status === 'TIMES_TRAVADOS' ? 'definidos' : 'sorteados (podem mudar)'}</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {round.teams.map((t) => <TeamCard key={t.id} team={t} />)}
          </div>
        </div>
      ) : (
        round.attendances.length > 0 && (
          <details className="mt-4 text-sm">
            <summary className="cursor-pointer font-medium">Ver confirmados</summary>
            <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-muted">
              {round.attendances.map((a) => <PlayerName key={a.player_id} name={a.name} type={a.type} />)}
            </p>
          </details>
        )
      )}
    </Card>
  )
}

const SHORTCUTS = [
  { to: '/gestao/dashboard', label: 'Dashboard' },
  { to: '/gestao/rodadas', label: 'Rodadas e sorteio' },
  { to: '/gestao/jogadores', label: 'Cadastrar jogador' },
  { to: '/gestao/usuarios', label: 'Aprovar cadastros' },
  { to: '/gestao/configuracoes', label: 'Configurações' },
]

export function HomePage() {
  const { isHidden } = usePageAccess()
  const { user, hasRole } = useAuth()
  const { data: settings } = useSettings()
  const { data: players } = usePlayers({ active: true })
  const { data: round } = useCurrentRound()

  return (
    <>
      <PageHeader title={`Olá, ${user?.name.split(' ')[0]}!`} />
      {round && <div className="mb-4"><CurrentRoundCard round={round} /></div>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-5">
          <p className="text-sm text-muted">Próxima pelada</p>
          <p className="mt-1 text-xl font-semibold">
            {settings ? `${weekdayLabel[settings.weekday]}, ${settings.start_time.slice(0, 5)}` : '—'}
          </p>
          <p className="text-sm text-muted">{settings?.total_minutes} minutos de jogo</p>
        </Card>
        <Card className="p-5">
          <p className="text-sm text-muted">Jogadores ativos</p>
          <p className="mt-1 text-3xl font-bold text-primary-ink">{players?.length ?? '—'}</p>
          <Link to="/jogadores" className="text-sm text-primary-ink hover:underline">
            Ver elenco
          </Link>
        </Card>
      </div>
      {hasRole('ADMIN') && (
        <Card className="mt-6 p-5">
          <h2 className="font-semibold">Atalhos de gestão</h2>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            {SHORTCUTS.filter((l) => !isHidden(l.to)).map((l) => (
              <Link key={l.to} className="rounded-lg bg-soft px-3 py-2" to={l.to}>{l.label}</Link>
            ))}
          </div>
        </Card>
      )}
    </>
  )
}

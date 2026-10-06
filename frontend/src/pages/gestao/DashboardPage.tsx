import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CalendarDays,
  ChevronRight,
  Lock,
  MapPin,
  Phone,
  Trophy,
  UserCheck,
  UserPlus,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { useDashboard } from '@/api/dashboard'
import type { Dashboard, DashboardHighlight } from '@/api/types'
import { Badge, Card, ICON_STROKE, PageHeader, QueryState, Skeleton, TeamShield, cx } from '@/components/ui'
import { formatDate, monthAbbr, money, roundStatusLabel } from '@/lib/labels'

const statusColor = { ABERTA: 'green', FECHADA: 'yellow', TIMES_TRAVADOS: 'blue', ENCERRADA: 'gray' } as const
const monthName = (iso: string) => new Intl.DateTimeFormat('pt-BR', { month: 'long', timeZone: 'UTC' }).format(new Date(iso))
const dueLabel = (months: string[]) => months.map((m) => monthAbbr[Number(m.slice(5, 7)) - 1]).join(' e ')

function Tile({ label, value, sub, icon: Icon, tone, to }: { label: string; value: ReactNode; sub?: ReactNode; icon: LucideIcon; tone?: 'danger' | 'ok'; to?: string }) {
  const body = (
    <>
      <p className="flex items-center gap-1.5 text-sm text-muted">
        <Icon size={15} strokeWidth={ICON_STROKE} aria-hidden /> {label}
      </p>
      <p className={cx('tabular mt-1 font-display text-4xl font-extrabold leading-none', tone === 'danger' && 'text-danger-ink', tone === 'ok' && 'text-primary-ink')}>
        {value}
      </p>
      {sub && <p className="mt-1.5 text-xs text-muted">{sub}</p>}
    </>
  )
  return to ? (
    <Link to={to} className="card press block p-4 hover:bg-soft">{body}</Link>
  ) : (
    <Card className="p-4">{body}</Card>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-h-[44px] items-center justify-between gap-3 border-t border-line py-2 first:border-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="tabular text-right font-medium">{children}</span>
    </div>
  )
}

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="font-display text-xl font-bold">{title}</h2>
        {action}
      </div>
      {children}
    </Card>
  )
}

const more = (to: string, label: string) => (
  <Link to={to} className="press inline-flex min-h-[44px] items-center gap-0.5 rounded-btn px-2 text-sm font-medium text-primary-ink hover:bg-soft">
    {label} <ChevronRight size={16} strokeWidth={ICON_STROKE} aria-hidden />
  </Link>
)

const player = (h: DashboardHighlight | null) =>
  h ? (
    <Link to={`/jogadores/${h.player_id}`} className="hover:underline">
      {h.name} <span className="font-normal text-muted">({h.value})</span>
    </Link>
  ) : (
    '—'
  )

function Finance({ f }: { f: Dashboard['finance'] }) {
  const pct = f.monthly_total ? Math.round((f.monthly_paid / f.monthly_total) * 100) : 0
  return (
    <Section title={`Financeiro de ${monthName(f.month)}`} action={more('/gestao/financeiro', 'Abrir')}>
      <div className="mb-3">
        <div className="mb-1 flex items-baseline justify-between text-sm">
          <span className="text-muted">Mensalistas em dia</span>
          <span className="tabular font-semibold">
            {f.monthly_paid} de {f.monthly_total}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-soft" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Mensalistas em dia">
          <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <Row label="Entradas no mês">{money(f.month_income)}</Row>
      <Row label="Saídas no mês">{money(f.month_expenses)}</Row>
      <Row label={`Em aberto de ${dueLabel(f.reference_months)}`}>
        <span className={cx(Number(f.delinquent_amount) > 0 && 'text-danger-ink')}>{money(f.delinquent_amount)}</span>
      </Row>
      <Row label="Cobranças avulsas a receber">{money(f.collections_open)}</Row>
    </Section>
  )
}

function CurrentRound({ r }: { r: Dashboard['current_round'] }) {
  if (!r) {
    return (
      <Section title="Próxima rodada" action={more('/gestao/rodadas', 'Criar')}>
        <p className="py-3 text-sm text-muted">Nenhuma rodada aberta.</p>
      </Section>
    )
  }
  return (
    <Section title="Próxima rodada" action={more(`/gestao/rodadas/${r.id}`, 'Gerenciar')}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="font-medium capitalize">{formatDate(r.date)}</span>
        <Badge color={statusColor[r.status]}>{roundStatusLabel[r.status]}</Badge>
      </div>
      <div className="grid grid-cols-3 divide-x divide-line rounded-btn bg-soft py-3 text-center">
        {[
          { label: 'confirmados', value: r.confirmed },
          { label: 'goleiros', value: r.goalkeepers },
          { label: 'times', value: r.teams || '–' },
        ].map((s) => (
          <div key={s.label}>
            <p className="tabular font-display text-3xl font-extrabold leading-none">{s.value}</p>
            <p className="mt-1 text-xs text-muted">{s.label}</p>
          </div>
        ))}
      </div>
      {r.tournament_id && <div className="mt-2">{more(`/campeonato/${r.tournament_id}`, 'Campeonato')}</div>}
    </Section>
  )
}

function Season({ s }: { s: Dashboard['season'] }) {
  return (
    <Section title={`Temporada ${s.year}`} action={more('/estatisticas', 'Estatísticas')}>
      {s.last_champion && (
        <Link
          to={`/campeonato/${s.last_tournament_id}`}
          className="press mb-2 flex min-h-[56px] items-center gap-3 rounded-btn bg-accent/10 px-3 hover:bg-accent/15"
        >
          <TeamShield name={s.last_champion.replace(/^Time /, '')} size={36} />
          <span className="min-w-0 flex-1">
            <span className="block text-xs text-muted">Último campeão</span>
            <span className="block truncate font-semibold">{s.last_champion}</span>
          </span>
          {s.last_champion_date && <span className="tabular text-sm text-muted">{s.last_champion_date.slice(8, 10)}/{s.last_champion_date.slice(5, 7)}</span>}
          <Trophy size={18} strokeWidth={ICON_STROKE} className="text-accent-ink" aria-hidden />
        </Link>
      )}
      <Row label="Rodadas jogadas">{s.rounds_played}</Row>
      <Row label="Média de jogadores">{s.avg_players.toLocaleString('pt-BR')}</Row>
      <Row label="Gols na súmula">{s.goals}</Row>
      <Row label="Artilheiro">{player(s.top_scorer)}</Row>
      <Row label="Mais presente">{player(s.most_present)}</Row>
      <Row label="Melhor aproveitamento">{player(s.best_win_rate)}</Row>
    </Section>
  )
}

function Pending({ p }: { p: Dashboard['pending'] }) {
  const items: { n: number; label: string; to: string; icon: LucideIcon }[] = [
    { n: p.pending_users, label: 'cadastros aguardando aprovação', to: '/gestao/usuarios', icon: UserPlus },
    { n: p.locked_accounts, label: 'contas bloqueadas por senha errada', to: '/gestao/usuarios', icon: Lock },
    { n: p.players_without_position, label: 'jogadores sem posição', to: '/gestao/jogadores', icon: MapPin },
    { n: p.monthly_without_whatsapp, label: 'mensalistas sem WhatsApp', to: '/gestao/jogadores', icon: Phone },
    { n: p.monthly_without_consent, label: 'mensalistas sem consentimento de cobrança', to: '/gestao/jogadores', icon: Phone },
  ].filter((i) => i.n > 0)
  return (
    <Section title="Pendências">
      {items.length === 0 ? (
        <p className="flex items-center gap-2 py-3 text-sm text-primary-ink">
          <UserCheck size={18} strokeWidth={ICON_STROKE} aria-hidden /> Nada pendente.
        </p>
      ) : (
        <ul>
          {items.map((i) => (
            <li key={i.label} className="border-t border-line first:border-0">
              <Link to={i.to} className="press -mx-2 flex min-h-[48px] items-center gap-3 rounded-btn px-2 hover:bg-soft">
                <i.icon size={18} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
                <span className="tabular w-7 font-display text-xl font-bold">{i.n}</span>
                <span className="flex-1 text-sm">{i.label}</span>
                <ChevronRight size={16} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

function DashboardView({ d }: { d: Dashboard }) {
  const { squad, finance: f } = d
  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Saldo em caixa" icon={Wallet} value={money(f.balance)} tone={Number(f.balance) < 0 ? 'danger' : 'ok'} to="/gestao/financeiro" />
        <Tile label="Mensalistas" icon={Users} value={squad.monthly_active} sub={squad.inactive ? `${squad.inactive} inativos no cadastro` : undefined} to="/gestao/jogadores" />
        <Tile label="Diaristas" icon={CalendarDays} value={squad.daily_active} to="/gestao/jogadores" />
        <Tile
          label="Inadimplentes"
          icon={AlertTriangle}
          value={f.delinquent_count}
          tone={f.delinquent_count ? 'danger' : 'ok'}
          sub={f.delinquent_count ? `${money(f.delinquent_amount)} em aberto` : 'todos em dia'}
          to="/gestao/financeiro?inadimplentes=1"
        />
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Finance f={f} />
        <CurrentRound r={d.current_round} />
        <Season s={d.season} />
        <Pending p={d.pending} />
      </div>
    </>
  )
}

export function DashboardPage() {
  const query = useDashboard()
  return (
    <>
      <PageHeader title="Dashboard" />
      <QueryState
        query={query}
        skeleton={
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-card" />)}
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-56 rounded-card" />)}
            </div>
          </div>
        }
      >
        {query.data && <DashboardView d={query.data} />}
      </QueryState>
    </>
  )
}

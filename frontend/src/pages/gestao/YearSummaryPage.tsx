import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Trophy } from 'lucide-react'
import { useYearSummary } from '@/api/dashboard'
import type { DashboardHighlight } from '@/api/types'
import { ShareButton } from '@/components/ShareButton'
import { Alert, Badge, Card, ICON_STROKE, PageHeader, QueryState, Skeleton, cx } from '@/components/ui'
import { YearFilter } from '@/components/YearFilter'
import { money } from '@/lib/labels'

function Row({ label, children, strong }: { label: string; children: ReactNode; strong?: boolean }) {
  return (
    <div className={cx('flex min-h-[40px] items-center justify-between gap-3 border-t border-line py-2 first:border-0', strong && 'font-semibold')}>
      <span className="text-sm text-muted">{label}</span>
      <span className="tabular text-right">{children}</span>
    </div>
  )
}

const who = (h: DashboardHighlight | null) =>
  h ? (
    <Link to={`/jogadores/${h.player_id}`} className="hover:underline">{h.name} <span className="font-normal text-muted">({h.value})</span></Link>
  ) : (
    '—'
  )

/** Fechamento do ano: o que aconteceu em campo, o que entrou e saiu do caixa e o saldo que segue para o ano seguinte. */
export function YearSummaryPage() {
  const [year, setYear] = useState(new Date().getFullYear())
  const query = useYearSummary(year)
  const d = query.data

  const text = () =>
    d
      ? [
          `Fechamento ${d.year}`,
          `Rodadas jogadas: ${d.season.rounds_played} · Gols: ${d.season.goals}`,
          d.season.last_champion ? `Último campeão: ${d.season.last_champion}` : '',
          `Arrecadado: ${money(Number(d.fees_total) + Number(d.daily_total) + Number(d.other_income))} · Despesas: ${money(d.expenses)}`,
          `Saldo final de ${d.year}: ${money(d.closing_balance)} (saldo inicial de ${d.year + 1})`,
        ].filter(Boolean).join('\n')
      : ''

  return (
    <>
      <PageHeader
        title="Fechamento do ano"
        subtitle="Jogos, dinheiro e o saldo que segue para o ano seguinte"
        actions={
          <div className="flex items-center gap-2">
            <YearFilter value={year} onChange={setYear} />
            {d && <ShareButton text={text} label="Compartilhar" />}
          </div>
        }
      />
      <QueryState query={query} skeleton={<Skeleton className="h-64 rounded-card" />}>
        {d && (
          <div className="space-y-3">
            {d.partial ? (
              <Alert kind="info">{d.year} ainda está em andamento: os números são parciais e o ano fecha em 31/12.</Alert>
            ) : (
              <Badge color="gray">{d.year} fechado · somente leitura (só o superadmin corrige)</Badge>
            )}

            <Card className="p-5">
              <p className="text-sm text-muted">Saldo final de {d.year} = saldo inicial de {d.year + 1}</p>
              <p className="mt-1 flex flex-wrap items-center gap-2 font-display text-3xl font-bold leading-tight">
                {money(d.opening_balance)} <ArrowRight size={22} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden /> {money(d.closing_balance)}
              </p>
              <p className="mt-1 text-sm text-muted">Do começo ao fim de {d.year}, o caixa variou {money(d.net)}.</p>
            </Card>

            <div className="grid gap-3 lg:grid-cols-2">
              <Card className="p-4">
                <h2 className="mb-2 font-display text-xl font-bold">Dinheiro</h2>
                <Row label="Mensalidades">{money(d.fees_total)}</Row>
                <Row label="Diárias dos diaristas">{money(d.daily_total)}</Row>
                <Row label="Outras entradas">{money(d.other_income)}</Row>
                <Row label="Despesas"><span className="text-danger-ink">{money(d.expenses)}</span></Row>
                <Row label="Resultado do ano" strong>{money(d.net)}</Row>
              </Card>
              <Card className="p-4">
                <h2 className="mb-2 font-display text-xl font-bold">Em campo</h2>
                {d.season.last_champion && (
                  <Link
                    to={`/campeonato/${d.season.last_tournament_id}`}
                    className="press mb-2 flex min-h-[48px] items-center gap-2 rounded-btn bg-accent/10 px-3 hover:bg-accent/15"
                  >
                    <Trophy size={18} strokeWidth={ICON_STROKE} className="text-accent-ink" aria-hidden />
                    <span className="text-xs text-muted">Último campeão</span>
                    <span className="min-w-0 flex-1 truncate text-right font-semibold">{d.season.last_champion}</span>
                  </Link>
                )}
                <Row label="Rodadas jogadas">{d.season.rounds_played}</Row>
                <Row label="Média de jogadores">{d.season.avg_players.toLocaleString('pt-BR')}</Row>
                <Row label="Gols na súmula">{d.season.goals}</Row>
                <Row label="Artilheiro">{who(d.season.top_scorer)}</Row>
                <Row label="Mais presente">{who(d.season.most_present)}</Row>
                <Row label="Melhor aproveitamento">{who(d.season.best_win_rate)}</Row>
              </Card>
            </div>
          </div>
        )}
      </QueryState>
    </>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, CircleCheck, Copy, TriangleAlert, UserX } from 'lucide-react'
import { useMyFinance } from '@/api/finance'
import type { MyFinance, MyMonthStatus } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { useToast } from '@/contexts/feedback'
import { Button, Card, EmptyState, ICON_STROKE, PageHeader, QueryState, SkeletonList, TypeBadge, cx } from '@/components/ui'
import { monthAbbr, money } from '@/lib/labels'

const statusText: Record<MyMonthStatus, string> = {
  paid: 'pago',
  partial: 'parcial',
  open: 'em aberto',
  late: 'atrasado',
  future: '—',
  none: '—',
}

const dueText = (months: string[]) => months.map((m) => monthAbbr[Number(m.slice(5, 7)) - 1]).join(' e ')

function Situation({ d }: { d: MyFinance }) {
  const toast = useToast()
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(d.pix_key ?? '')
      toast({ message: 'Chave Pix copiada', tone: 'success' })
    } catch {
      toast({ message: 'Não foi possível copiar', tone: 'error' })
    }
  }
  if (d.type === 'ISENTO') {
    return (
      <Card className="p-4">
        <p className="font-medium">Você é goleiro fixo: isento de mensalidade e de diária.</p>
      </Card>
    )
  }
  if (d.type === 'DIARISTA') {
    return (
      <Card className="p-4">
        <p className="font-medium">Você é diarista: paga por dia de pelada, direto no caixa.</p>
      </Card>
    )
  }
  const owes = d.months_due.length > 0
  return (
    <Card className={cx('p-4', owes ? 'ring-1 ring-inset ring-danger/50' : 'ring-1 ring-inset ring-ok/50')}>
      <div className="flex items-start gap-3">
        {owes ? (
          <TriangleAlert size={24} strokeWidth={ICON_STROKE} className="shrink-0 text-danger-ink" aria-hidden />
        ) : (
          <CircleCheck size={24} strokeWidth={ICON_STROKE} className="shrink-0 text-primary-ink" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <p className="font-display text-2xl font-bold">{owes ? `${money(d.amount_due)} em aberto` : 'Mensalidade em dia'}</p>
          <p className="text-sm text-muted">{owes ? `Falta pagar ${dueText(d.months_due)}.` : `Mensalidade de ${money(d.monthly_fee)}.`}</p>
          {owes && d.pix_key && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-btn bg-soft p-2 text-sm">
              <span className="text-muted">Pix:</span>
              <span className="min-w-0 flex-1 truncate font-mono">{d.pix_key}</span>
              <Button size="sm" variant="secondary" onClick={copy}>
                <Copy size={14} strokeWidth={ICON_STROKE} aria-hidden /> Copiar
              </Button>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

function Months({ d }: { d: MyFinance }) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="font-display text-xl font-bold">Mensalidades de {d.year}</h2>
        <span className="text-sm text-muted">pago no ano: <strong className="tabular text-ink">{money(d.total_paid)}</strong></span>
      </div>
      <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
        {d.months.map((m) => (
          <li
            key={m.month}
            className={cx(
              'flex flex-col items-center rounded-btn p-2 text-center',
              m.status === 'paid' && 'bg-ok/15',
              m.status === 'partial' && 'bg-accent/15',
              m.status === 'open' && 'bg-accent/10 ring-1 ring-inset ring-accent/60',
              m.status === 'late' && 'ring-2 ring-inset ring-danger/80',
              (m.status === 'future' || m.status === 'none') && 'bg-soft/60 text-muted',
            )}
          >
            <span className="text-xs font-semibold uppercase">{monthAbbr[Number(m.month.slice(5, 7)) - 1]}</span>
            <span className="mt-1 flex h-6 items-center">
              {m.status === 'paid' ? (
                <Check size={18} strokeWidth={2.5} className="text-primary-ink" aria-hidden />
              ) : (
                <span className={cx('text-xs', m.status === 'late' && 'font-semibold text-danger-ink')}>{m.amount ? money(m.amount) : statusText[m.status]}</span>
              )}
            </span>
            <span className="sr-only">{statusText[m.status]}</span>
            {m.marker && <span className="text-[11px] text-muted">{m.marker}</span>}
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function MyAreaPage() {
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(thisYear)
  const query = useMyFinance(year)
  const { user } = useAuth()
  const d = query.data

  return (
    <>
      <PageHeader
        title="Minha área"
        actions={
          <select className="input w-auto" value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Ano">
            {[thisYear, thisYear - 1].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        }
      />
      <QueryState
        query={query}
        isEmpty={!!d && !d.has_player}
        skeleton={<SkeletonList rows={4} />}
        empty={
          <Card>
            <EmptyState icon={<UserX size={22} strokeWidth={ICON_STROKE} />} title="Seu usuário não está ligado a um jogador">
              Peça a um administrador para fazer o vínculo. Depois disso suas mensalidades aparecem aqui.
            </EmptyState>
          </Card>
        }
      >
        {d && d.has_player && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-display text-xl font-bold">{d.player_name}</span>
              {d.type && <TypeBadge type={d.type} />}
              {user?.player_id && (
                <Link to={`/jogadores/${user.player_id}`} className="ml-auto text-sm font-medium text-primary-ink hover:underline">
                  Minhas estatísticas
                </Link>
              )}
            </div>
            <Situation d={d} />
            <Months d={d} />
          </div>
        )}
      </QueryState>
    </>
  )
}

import { useState } from 'react'
import { Check, Landmark } from 'lucide-react'
import { useTransparency } from '@/api/finance'
import type { MyMonthStatus, Transparency } from '@/api/types'
import { Card, EmptyState, ICON_STROKE, PageHeader, QueryState, SkeletonList, cx } from '@/components/ui'
import { cashCategoryLabel, monthAbbr, monthLong, money } from '@/lib/labels'

const monthKey = (iso: string) => iso.slice(0, 7)
const abbr = (iso: string) => monthAbbr[Number(iso.slice(5, 7)) - 1]

const stateText: Record<MyMonthStatus, string> = {
  paid: 'pago',
  partial: 'pago parcialmente',
  out: 'fora no mês',
  open: 'em aberto',
  late: 'atrasado',
  future: 'mês futuro',
  none: 'sem cobrança',
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'danger' }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase text-muted">{label}</p>
      <p className={cx('mt-1 font-display text-2xl font-bold tabular', tone === 'ok' && 'text-primary-ink', tone === 'danger' && 'text-danger-ink')}>
        {money(value)}
      </p>
    </Card>
  )
}

function MonthByMonth({ d }: { d: Transparency }) {
  const now = new Date().toISOString().slice(0, 7)
  const rows = d.summary.filter((s) => monthKey(s.month) <= now || Number(s.fees) || Number(s.income) || Number(s.expenses))
  return (
    <Card className="overflow-x-auto">
      <h2 className="px-4 pt-4 font-display text-xl font-bold">Mês a mês</h2>
      <table className="mt-2 w-full min-w-[420px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase text-muted">
            <th className="px-4 py-2 font-medium">Mês</th>
            <th className="px-4 py-2 text-right font-medium">Entradas</th>
            <th className="px-4 py-2 text-right font-medium">Saídas</th>
            <th className="px-4 py-2 text-right font-medium">Resultado</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const net = Number(s.net)
            return (
              <tr key={s.month} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2 capitalize">{monthLong(s.month)}</td>
                <td className="px-4 py-2 text-right tabular">{money(Number(s.fees) + Number(s.income))}</td>
                <td className="px-4 py-2 text-right tabular">{money(s.expenses)}</td>
                <td className={cx('px-4 py-2 text-right font-semibold tabular', net < 0 ? 'text-danger-ink' : 'text-primary-ink')}>{money(net)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}

function Expenses({ d }: { d: Transparency }) {
  return (
    <Card>
      <h2 className="px-4 pt-4 font-display text-xl font-bold">Despesas</h2>
      {d.expenses.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">Nenhuma despesa lançada em {d.year}.</p>
      ) : (
        <ul className="mt-2 divide-y divide-line/60">
          {d.expenses.map((e, i) => (
            <li key={i} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className="w-10 shrink-0 text-xs font-semibold uppercase text-muted">{abbr(e.month)}</span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{cashCategoryLabel[e.category]}</span>
                {e.description && <span className="block truncate text-xs text-muted">{e.description}</span>}
              </span>
              <span className="tabular font-semibold">{money(e.amount)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function StateDot({ state, label }: { state: MyMonthStatus; label: string }) {
  return (
    <span
      role="img"
      aria-label={label}
      className={cx(
        'mx-auto grid h-7 w-7 place-items-center rounded-full text-[11px] font-semibold',
        state === 'paid' && 'bg-ok text-primary-on',
        state === 'partial' && 'bg-accent/30 text-ink',
        state === 'out' && 'border border-line bg-soft/60 text-muted',
        state === 'open' && 'bg-accent/20 ring-1 ring-inset ring-accent/60',
        state === 'late' && 'border-2 border-danger/80 text-danger-ink',
        (state === 'future' || state === 'none') && 'text-muted opacity-40',
      )}
    >
      {state === 'paid' ? <Check size={14} strokeWidth={3} aria-hidden /> : state === 'out' ? 'F' : state === 'partial' ? '½' : state === 'late' ? '!' : '·'}
    </span>
  )
}

function Players({ d }: { d: Transparency }) {
  return (
    <Card className="overflow-x-auto">
      <div className="flex flex-wrap items-end justify-between gap-2 px-4 pt-4">
        <h2 className="font-display text-xl font-bold">Mensalidades</h2>
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink" aria-label="Legenda">
          {(['paid', 'partial', 'out', 'open', 'late'] as const).map((s) => (
            <li key={s} className="flex items-center gap-1"><StateDot state={s} label="" /> {stateText[s]}</li>
          ))}
        </ul>
      </div>
      <table className="mt-2 w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase text-muted">
            <th className="sticky left-0 bg-surface px-4 py-2 text-left font-medium">Mensalista</th>
            {d.months.map((m) => <th key={m} className="px-1 py-2 font-medium">{abbr(m)}</th>)}
          </tr>
        </thead>
        <tbody>
          {d.players.map((p) => (
            <tr key={p.name} className="border-b border-line/60 last:border-0">
              <td className="sticky left-0 bg-surface px-4 py-1.5 font-medium">{p.name}</td>
              {d.months.map((m) => {
                const state = p.months[monthKey(m)] ?? 'none'
                return (
                  <td key={m} className="px-1 py-1.5">
                    <StateDot state={state} label={`${p.name}, ${monthLong(m)}: ${stateText[state]}`} />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

export function TransparencyPage() {
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(thisYear)
  const query = useTransparency(year)
  const d = query.data

  return (
    <>
      <PageHeader
        title="Transparência"
        subtitle="Para onde vai o dinheiro da pelada"
        actions={
          <select className="input w-auto" value={year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Ano">
            {[thisYear, thisYear - 1].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        }
      />
      <QueryState
        query={query}
        isEmpty={!!d && d.summary.every((s) => !Number(s.net) && !Number(s.expenses)) && d.players.length === 0}
        skeleton={<SkeletonList rows={4} />}
        empty={
          <Card>
            <EmptyState icon={<Landmark size={22} strokeWidth={ICON_STROKE} />} title={`Sem movimentação em ${year}`}>
              Quando houver mensalidades ou lançamentos no caixa, eles aparecem aqui.
            </EmptyState>
          </Card>
        }
      >
        {d && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Tile label="Saldo do caixa (hoje)" value={d.balance} tone={Number(d.balance) < 0 ? 'danger' : 'ok'} />
              <Tile label={`Entradas em ${d.year}`} value={d.year_income} />
              <Tile label={`Saídas em ${d.year}`} value={d.year_expenses} />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <MonthByMonth d={d} />
              <Expenses d={d} />
            </div>
            <Players d={d} />
          </div>
        )}
      </QueryState>
    </>
  )
}

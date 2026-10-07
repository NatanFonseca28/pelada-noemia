import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import {
  useCashEntries,
  useCollectionMutations,
  useCollections,
  useDeleteEntry,
  useFinanceOverview,
  useImportSheet,
  useSaveEntry,
  useSaveFinanceConfig,
  useSetFee,
} from '@/api/finance'
import { usePlayers } from '@/api/queries'
import type { CashCategory, CashEntry, CashKind, Collection, FeeRow, FinanceConfig, FinanceOverview, ImportResult } from '@/api/types'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Minus,
  RotateCcw,
  Trash2,
  TrendingDown,
  TrendingUp,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { ChargePanel } from '@/components/finance/ChargePanel'
import { FinanceChart } from '@/components/finance/FinanceChart'
import { Alert, Badge, Button, Card, EmptyState, Field, ICON_STROKE, Modal, PageHeader, PlayerName, Skeleton, Spinner, TypeLegend, cx } from '@/components/ui'
import { useCountUp } from '@/hooks/useCountUp'
import { computeFlow, tileNumbers, toQuarters } from '@/lib/finance'
import { cashCategoryLabel, monthAbbr, monthLong, monthShort, money } from '@/lib/labels'

type Tab = 'mensalidades' | 'caixa' | 'cobrancas' | 'config'
const TABS: { id: Tab; label: string }[] = [
  { id: 'mensalidades', label: 'Mensalidades' },
  { id: 'caixa', label: 'Caixa' },
  { id: 'cobrancas', label: 'Cobranças avulsas' },
  { id: 'config', label: 'Importar / Config.' },
]

const monthKey = (iso: string) => iso.slice(0, 7)
const currentMonthKey = () => new Date().toISOString().slice(0, 7)
const errorText = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback)

// ---------------------------------------------------------------- Mensalidades

interface EditingCell {
  row: FeeRow
  month: string
}

function FeeCellEditor({ cell, monthlyFee, onClose, onSaved }: { cell: EditingCell; monthlyFee: string; onClose: () => void; onSaved?: () => void }) {
  const current = cell.row.cells[monthKey(cell.month)]
  const [amount, setAmount] = useState(current?.amount ?? '')
  const [marker, setMarker] = useState(current?.marker ?? '')
  const [error, setError] = useState<string | null>(null)
  const setFee = useSetFee()

  async function save(next: { amount: string | null; marker: string | null }) {
    setError(null)
    try {
      await setFee.mutateAsync({ player_id: cell.row.player_id, month: cell.month, ...next })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(errorText(err, 'Erro ao salvar'))
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save({ amount: amount === '' ? null : String(amount).replace(',', '.'), marker: marker.trim() || null })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-sm text-muted">
        <span className="font-medium text-ink">{cell.row.name}</span> · {monthLong(cell.month)}
      </p>
      {error && <Alert>{error}</Alert>}
      <div className="grid grid-cols-2 gap-2">
        <Button type="button" size="lg" onClick={() => save({ amount: monthlyFee, marker: null })} loading={setFee.isPending}>
          Pagou {money(monthlyFee)}
        </Button>
        <Button type="button" size="lg" variant="secondary" onClick={() => save({ amount: null, marker: null })}>
          Limpar
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Outro valor (R$)">
          <input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Ex.: 35" />
        </Field>
        <Field label="Anotação" hint='Ex.: "F"'>
          <input className="input" maxLength={20} value={marker} onChange={(e) => setMarker(e.target.value)} />
        </Field>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>Cancelar</Button>
        <Button type="submit" loading={setFee.isPending}>Salvar</Button>
      </div>
    </form>
  )
}

type CellState = 'paid' | 'partial' | 'marker' | 'open' | 'late' | 'future' | 'none'

function cellState(row: FeeRow, month: string, nowKey: string, fee: number): CellState {
  const c = row.cells[monthKey(month)]
  const amount = c?.amount ? Number(c.amount) : 0
  if (amount >= fee && amount > 0) return 'paid'
  if (amount > 0) return 'partial'
  if (c?.marker) return 'marker'
  const key = monthKey(month)
  if (key > nowKey) return 'future'
  // Só cobra de mensalista ativo, a partir do 1º mês em que pagou (antes ele não era do grupo)
  const firstPaid = Object.keys(row.cells).sort()[0]
  const expected = row.type === 'MENSALISTA' && row.active && !!firstPaid && key >= firstPaid
  if (!expected) return 'none'
  return key === nowKey ? 'open' : 'late'
}

const stateText: Record<CellState, string> = {
  paid: 'pago',
  partial: 'pago parcialmente',
  marker: 'anotação',
  open: 'em aberto',
  late: 'atrasado',
  future: 'mês futuro',
  none: 'sem cobrança',
}

function FeeCell({ row, month, fee, nowKey, pop, onClick }: { row: FeeRow; month: string; fee: number; nowKey: string; pop: boolean; onClick: () => void }) {
  const c = row.cells[monthKey(month)]
  const state = cellState(row, month, nowKey, fee)
  const amount = c?.amount ? Number(c.amount) : 0
  return (
    <button
      onClick={onClick}
      className={cx(
        'press relative mx-auto grid h-11 w-11 place-items-center rounded-full text-xs font-semibold tabular hover:ring-2 hover:ring-primary/60',
        pop && 'anim-cell-pop',
        state === 'paid' && 'bg-ok text-primary-on',
        state === 'partial' && 'bg-accent/30 text-ink',
        state === 'marker' && 'bg-soft text-ink',
        state === 'open' && 'bg-accent/20 text-ink ring-1 ring-inset ring-accent/60',
        state === 'late' && 'border-2 border-danger/80 text-danger-ink',
        state === 'future' && 'text-muted opacity-30',
        state === 'none' && 'text-muted',
      )}
      aria-label={`${row.name}, ${monthLong(month)}: ${stateText[state]}${amount ? ` (${money(amount)})` : ''}${c?.marker ? ` — ${c.marker}` : ''}`}
    >
      {state === 'paid' ? (
        <>
          <Check size={18} strokeWidth={2.5} aria-hidden />
          {amount !== fee && <span className="absolute -bottom-1 -right-1 rounded-full bg-surface px-1 text-[9px] text-ink shadow-card">{amount.toLocaleString('pt-BR')}</span>}
        </>
      ) : state === 'partial' ? (
        amount.toLocaleString('pt-BR')
      ) : state === 'marker' ? (
        c?.marker
      ) : state === 'late' ? (
        '!'
      ) : (
        '·'
      )}
    </button>
  )
}

const dueLabel = (months: string[]) => months.map((m) => monthAbbr[Number(m.slice(5, 7)) - 1]).join(' e ')

function FeesGrid({ data, delinquentOnly, onDelinquentOnly }: { data: FinanceOverview; delinquentOnly: boolean; onDelinquentOnly: (v: boolean) => void }) {
  const [editing, setEditing] = useState<EditingCell | null>(null)
  const [popKey, setPopKey] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const fee = Number(data.config.monthly_fee)
  const nowKey = currentMonthKey()
  const rows = data.rows.filter((r) => r.name.toLowerCase().includes(q.toLowerCase()) && (!delinquentOnly || r.delinquent))

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input className="input max-w-xs" placeholder="Filtrar jogador" aria-label="Filtrar jogador" value={q} onChange={(e) => setQ(e.target.value)} />
        <button
          type="button"
          aria-pressed={delinquentOnly}
          onClick={() => onDelinquentOnly(!delinquentOnly)}
          disabled={data.delinquent_count === 0 && !delinquentOnly}
          className={cx(
            'press inline-flex min-h-[44px] items-center gap-1.5 rounded-full border px-3 text-sm font-medium disabled:opacity-50',
            delinquentOnly ? 'border-danger bg-danger text-danger-on' : 'border-danger/50 text-danger-ink hover:bg-danger/10',
          )}
        >
          <AlertTriangle size={15} strokeWidth={ICON_STROKE} aria-hidden />
          Só inadimplentes ({data.delinquent_count})
        </button>
        <TypeLegend />
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink" aria-label="Legenda">
          <li className="flex items-center gap-1"><span className="grid h-4 w-4 place-items-center rounded-full bg-ok text-primary-on"><Check size={10} strokeWidth={3} /></span> pago</li>
          <li className="flex items-center gap-1"><span className="h-4 w-4 rounded-full bg-accent/30" /> parcial</li>
          <li className="flex items-center gap-1"><span className="h-4 w-4 rounded-full bg-accent/20 ring-1 ring-inset ring-accent/60" /> em aberto</li>
          <li className="flex items-center gap-1"><span className="h-4 w-4 rounded-full border-2 border-danger/80" /> atrasado</li>
          <li className="flex items-center gap-1"><span className="h-4 w-4 rounded-full bg-soft" /> anotação</li>
        </ul>
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase text-muted">
              <th className="sticky left-0 z-10 bg-surface px-3 py-2 text-left">Nome</th>
              {data.months.map((m) => (
                <th key={m} className={cx('px-1 py-2 text-center font-medium', monthKey(m) === nowKey && 'text-primary-ink')}>
                {monthShort(m)}
                </th>
              ))}
              <th className="px-3 py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.player_id} className="border-b border-line">
                <td className="sticky left-0 z-10 max-w-[200px] bg-surface px-3 py-1.5 font-medium" title={row.name}>
                  <PlayerName name={row.name} type={row.type} className="flex" />
                  {row.delinquent && (
                    <span
                      className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-danger/15 px-1.5 py-0.5 text-[11px] font-semibold text-danger-ink"
                      title={`Não pagou ${dueLabel(row.months_due)}`}
                    >
                      <AlertTriangle size={11} strokeWidth={2} aria-hidden /> Inadimplente
                      <span className="sr-only">: não pagou {dueLabel(row.months_due)}</span>
                    </span>
                  )}
                </td>
                {data.months.map((m) => {
                  const k = `${row.player_id}:${monthKey(m)}`
                  return (
                    <td key={m} className="p-0.5 text-center">
                      <FeeCell
                        key={popKey?.startsWith(k) ? popKey : k}
                        row={row}
                        month={m}
                        fee={fee}
                        nowKey={nowKey}
                        pop={!!popKey?.startsWith(k)}
                        onClick={() => setEditing({ row, month: m })}
                      />
                    </td>
                  )
                })}
                <td className="px-3 py-1.5 text-right font-medium tabular-nums">{money(row.total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="text-xs">
            {(
              [
                ['Mensalidades', (s) => s.fees],
                ['Diaristas / outras entradas', (s) => s.income],
                ['Saídas', (s) => s.expenses],
                ['Total arrecadado', (s) => String(Number(s.fees) + Number(s.income))],
              ] as [string, (s: FinanceOverview['summary'][number]) => string][]
            ).map(([label, get], i) => (
              <tr key={label} className={cx('border-t border-line', i === 3 && 'font-semibold')}>
                <td className="sticky left-0 bg-surface px-3 py-1.5">{label}</td>
                {data.summary.map((s) => {
                  const v = Number(get(s))
                  return (
                    <td key={s.month} className={cx('px-1 py-1.5 text-center tabular-nums', i === 2 && v > 0 && 'text-danger-ink')}>
                    {v ? v.toLocaleString('pt-BR') : '·'}
                    </td>
                  )
                })}
                <td className="px-3 py-1.5 text-right tabular-nums">
                  {money(data.summary.reduce((acc, s) => acc + Number(get(s)), 0))}
                </td>
              </tr>
            ))}
          </tfoot>
        </table>
      </Card>
      <Modal open={!!editing} onClose={() => setEditing(null)} title="Mensalidade">
        {editing && (
          <FeeCellEditor
            key={`${editing.row.player_id}-${editing.month}`}
            cell={editing}
            monthlyFee={data.config.monthly_fee}
            onClose={() => setEditing(null)}
            onSaved={() => setPopKey(`${editing.row.player_id}:${monthKey(editing.month)}:${Date.now()}`)}
          />
        )}
      </Modal>
    </>
  )
}

// ---------------------------------------------------------------- Caixa

/**
 * Chips de categoria. A API tem 4 categorias (CAMPO, DIVERSOS, DIARISTAS_COLETE, OUTROS);
 * "Material" e "Confraternização" ainda são gravadas como DIVERSOS (pendência de API).
 */
interface CategoryChip {
  id: string
  label: string
  category: CashCategory
}
const OUT_CHIPS: CategoryChip[] = [
  { id: 'quadra', label: 'Quadra', category: 'CAMPO' },
  { id: 'material', label: 'Material', category: 'DIVERSOS' },
  { id: 'confra', label: 'Confraternização', category: 'DIVERSOS' },
  { id: 'outros', label: 'Outros', category: 'OUTROS' },
]
const IN_CHIPS: CategoryChip[] = [
  { id: 'diaristas', label: 'Diaristas / colete', category: 'DIARISTAS_COLETE' },
  { id: 'outros', label: 'Outros', category: 'OUTROS' },
]

function chipFor(kind: CashKind, category: CashCategory, description: string): string {
  const chips = kind === 'SAIDA' ? OUT_CHIPS : IN_CHIPS
  if (category === 'DIVERSOS') return /churras|confra|festa|cerveja/i.test(description) ? 'confra' : 'material'
  return chips.find((c) => c.category === category)?.id ?? 'outros'
}

function EntryForm({ entry, year, onDone }: { entry: CashEntry | null; year: number; onDone: () => void }) {
  const defaultMonth = year === new Date().getFullYear() ? currentMonthKey() : `${year}-01`
  const [form, setForm] = useState({
    month: entry ? monthKey(entry.month) : defaultMonth,
    kind: entry?.kind ?? ('SAIDA' as CashKind),
    category: entry?.category ?? ('CAMPO' as CashCategory),
    description: entry?.description ?? '',
    amount: entry?.amount ?? '',
  })
  const [chip, setChip] = useState(() => chipFor(form.kind, form.category, form.description))
  const [error, setError] = useState<string | null>(null)
  const save = useSaveEntry()
  const chips = form.kind === 'SAIDA' ? OUT_CHIPS : IN_CHIPS
  const pickChip = (c: CategoryChip) => {
    setChip(c.id)
    setForm((f) => ({ ...f, category: c.category }))
  }
  const pickKind = (k: CashKind) => {
    const first = (k === 'SAIDA' ? OUT_CHIPS : IN_CHIPS)[0]
    setChip(first.id)
    setForm((f) => ({ ...f, kind: k, category: first.category }))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await save.mutateAsync({
        id: entry?.id,
        data: { ...form, month: `${form.month}-01`, description: form.description || null, amount: String(form.amount).replace(',', '.') },
      })
      onDone()
    } catch (err) {
      setError(errorText(err, 'Erro ao salvar'))
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Tipo">
        {(['ENTRADA', 'SAIDA'] as CashKind[]).map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={form.kind === k}
            onClick={() => pickKind(k)}
            className={cx(
              'press flex min-h-[44px] items-center justify-center gap-1.5 rounded-btn border px-3 py-2 text-sm font-medium',
              form.kind === k
                ? k === 'ENTRADA'
                  ? 'border-ok bg-ok/10 text-primary-ink'
                  : 'border-danger bg-danger/10 text-danger-ink'
                : 'border-line text-muted',
            )}
          >
            {k === 'ENTRADA' ? <ArrowUpRight size={16} strokeWidth={ICON_STROKE} aria-hidden /> : <ArrowDownRight size={16} strokeWidth={ICON_STROKE} aria-hidden />}
            {k === 'ENTRADA' ? 'Entrada' : 'Saída'}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Mês">
          <input className="input" type="month" required value={form.month} onChange={(e) => setForm({ ...form, month: e.target.value })} />
        </Field>
        <Field label="Valor (R$)">
          <input className="input" inputMode="decimal" required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
        </Field>
      </div>
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-ink">Categoria</legend>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Categoria">
          {chips.map((c) => (
            <button
              key={c.id}
              type="button"
              role="radio"
              aria-checked={chip === c.id}
              onClick={() => pickChip(c)}
              className={cx(
                'press min-h-[44px] rounded-full border px-4 text-sm font-medium',
                chip === c.id ? 'border-primary bg-primary text-primary-on' : 'border-line bg-surface text-ink hover:bg-soft',
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      </fieldset>
      <Field label="Descrição">
        <input className="input" maxLength={200} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </Field>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={save.isPending}>Salvar</Button>
      </div>
    </form>
  )
}

function CashTab({ year }: { year: number }) {
  const { data, isLoading } = useCashEntries(year)
  const known = useRef<Set<number> | null>(null)
  useEffect(() => {
    if (data) known.current = new Set(data.map((e) => e.id))
  }, [data])
  const del = useDeleteEntry()
  const [editing, setEditing] = useState<CashEntry | null | undefined>(undefined)

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => setEditing(null)}>+ Lançamento</Button>
      </div>
      {isLoading ? (
        <Spinner />
      ) : !data?.length ? (
        <EmptyState>Nenhum lançamento em {year}.</EmptyState>
      ) : (
        <Card className="divide-y divide-line">
          {data.map((e) => (
            <div key={e.id} className={cx('flex items-center gap-3 p-3 text-sm', known.current && !known.current.has(e.id) && 'anim-slide-in')}>
              <span className={cx('grid h-8 w-8 shrink-0 place-items-center rounded-full', e.kind === 'ENTRADA' ? 'bg-ok/15 text-primary-ink' : 'bg-danger/15 text-danger-ink')}>
                {e.kind === 'ENTRADA' ? <ArrowUpRight size={16} strokeWidth={ICON_STROKE} aria-hidden /> : <ArrowDownRight size={16} strokeWidth={ICON_STROKE} aria-hidden />}
                <span className="sr-only">{e.kind === 'ENTRADA' ? 'Entrada' : 'Saída'}</span>
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{e.description || cashCategoryLabel[e.category]}</p>
                <p className="text-xs text-muted">
                  {monthLong(e.month)} · {cashCategoryLabel[e.category]}
                </p>
              </div>
              <span className={cx('tabular font-semibold', e.kind === 'SAIDA' ? 'text-danger-ink' : 'text-primary-ink')}>
                {e.kind === 'SAIDA' ? '−' : '+'} {money(e.amount)}
              </span>
              <Button size="sm" variant="secondary" onClick={() => setEditing(e)}>Editar</Button>
              <Button
                size="sm"
                variant="ghost"
                aria-label="Excluir lançamento"
                onClick={() => confirm('Excluir este lançamento?') && del.mutate(e.id)}
              >
                <Trash2 size={16} strokeWidth={ICON_STROKE} />
              </Button>
            </div>
          ))}
        </Card>
      )}
      <Modal open={editing !== undefined} onClose={() => setEditing(undefined)} title={editing ? 'Editar lançamento' : 'Novo lançamento'}>
        {editing !== undefined && <EntryForm key={editing?.id ?? 'new'} entry={editing} year={year} onDone={() => setEditing(undefined)} />}
      </Modal>
    </>
  )
}

// ---------------------------------------------------------------- Cobranças avulsas

function CollectionCard({ collection }: { collection: Collection }) {
  const m = useCollectionMutations()
  const { data: players = [] } = usePlayers({ active: true })
  const [adding, setAdding] = useState('')
  const paid = collection.items.filter((i) => i.paid)
  const total = collection.items.reduce((acc, i) => acc + Number(i.amount), 0)
  const received = paid.reduce((acc, i) => acc + Number(i.amount), 0)

  function addItem(e: FormEvent) {
    e.preventDefault()
    const value = adding.trim()
    if (!value) return
    const player = players.find((p) => p.display_name.toLowerCase() === value.toLowerCase())
    m.addItem.mutate({ collectionId: collection.id, name: player?.display_name ?? value, player_id: player?.id ?? null })
    setAdding('')
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{collection.title}</h3>
          <p className="text-sm text-muted">
            {money(collection.amount_per_person)} por pessoa · {paid.length}/{collection.items.length} pagaram · {money(received)} de {money(total)}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => confirm(`Excluir a cobrança "${collection.title}"?`) && m.remove.mutate(collection.id)}
        >
          Excluir
        </Button>
      </div>
      <div className="mb-3 h-2 overflow-hidden rounded-full bg-soft">
        <div className="h-full bg-primary transition-all" style={{ width: `${total ? (received / total) * 100 : 0}%` }} />
      </div>
      <ul className="divide-y divide-line">
        {collection.items.map((item) => (
          <li key={item.id} className="flex items-center gap-3 py-2 text-sm">
            <label className="flex flex-1 items-center gap-3">
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={item.paid}
                onChange={(e) => m.updateItem.mutate({ id: item.id, paid: e.target.checked })}
              />
              <span className={cx(item.paid && 'text-muted line-through')}>{item.name}</span>
            {!item.player_id && <Badge color="gray">sem cadastro</Badge>}
            </label>
            <span className="tabular-nums">{money(item.amount)}</span>
            <button className="text-muted hover:text-danger-ink" aria-label={`Remover ${item.name}`} onClick={() => m.removeItem.mutate(item.id)}>
              ✕
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={addItem} className="mt-3 flex gap-2">
        <input
          className="input"
          list={`players-${collection.id}`}
          placeholder="Adicionar pessoa"
          value={adding}
          onChange={(e) => setAdding(e.target.value)}
        />
        <datalist id={`players-${collection.id}`}>
          {players.map((p) => (
            <option key={p.id} value={p.display_name} />
          ))}
        </datalist>
        <Button type="submit" variant="secondary" loading={m.addItem.isPending}>Adicionar</Button>
      </form>
    </Card>
  )
}

function CollectionsTab() {
  const { data, isLoading } = useCollections()
  const { create } = useCollectionMutations()
  const [form, setForm] = useState({ title: '', amount_per_person: '' })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate({ title: form.title, amount_per_person: form.amount_per_person.replace(',', '.') }, { onSuccess: () => setForm({ title: '', amount_per_person: '' }) })
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[200px] flex-1">
            <Field label="Nova cobrança">
              <input className="input" required minLength={2} placeholder="Ex.: Bola nova" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </Field>
          </div>
          <div className="w-32">
            <Field label="Por pessoa (R$)">
              <input className="input" required inputMode="decimal" value={form.amount_per_person} onChange={(e) => setForm({ ...form, amount_per_person: e.target.value })} />
            </Field>
          </div>
          <Button type="submit" loading={create.isPending}>Criar</Button>
        </form>
        {create.error && <div className="mt-2"><Alert>{errorText(create.error, 'Erro ao criar')}</Alert></div>}
      </Card>
      {isLoading ? (
        <Spinner />
      ) : !data?.length ? (
        <EmptyState>Nenhuma cobrança avulsa.</EmptyState>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((c) => (
            <CollectionCard key={c.id} collection={c} />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- Importar / Config.

function ImportCard() {
  const importSheet = useImportSheet()
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    setResult(await importSheet.mutateAsync(file))
  }

  return (
    <Card className="p-5">
      <h2 className="mb-4 font-semibold">Importar planilha (.xlsx)</h2>
      <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-3">
        <input type="file" accept=".xlsx" className="text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Button type="submit" disabled={!file} loading={importSheet.isPending}>Importar</Button>
      </form>
      {importSheet.error && <div className="mt-3"><Alert>{errorText(importSheet.error, 'Erro ao importar')}</Alert></div>}
      {result && (
        <div className="mt-4 space-y-2">
          <Alert kind="success">
            Importação concluída: {result.fee_cells} mensalidades, {result.cash_entries} lançamentos de caixa e {result.collections} cobrança(s).
            {result.opening_balance && result.opening_month && (
              <> Saldo de abertura {money(result.opening_balance)} em {monthLong(result.opening_month)}.</>
            )}
          </Alert>
          {result.players_created.length > 0 && (
            <p className="text-sm">
              <span className="font-medium">Jogadores cadastrados ({result.players_created.length}):</span> {result.players_created.join(', ')}
            </p>
          )}
          {result.players_matched.length > 0 && (
            <p className="text-sm text-muted">Já existiam ({result.players_matched.length}): {result.players_matched.join(', ')}</p>
          )}
        </div>
      )}
    </Card>
  )
}

function ConfigCard({ config }: { config: FinanceConfig }) {
  const [form, setForm] = useState(config)
  const save = useSaveFinanceConfig()
  const [msg, setMsg] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  useEffect(() => setForm(config), [config])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    try {
      await save.mutateAsync({
        monthly_fee: String(form.monthly_fee).replace(',', '.'),
        finance_opening_balance: String(form.finance_opening_balance).replace(',', '.'),
        finance_opening_month: form.finance_opening_month ? `${monthKey(form.finance_opening_month)}-01` : null,
      })
      setMsg({ kind: 'success', text: 'Configuração salva.' })
    } catch (err) {
      setMsg({ kind: 'error', text: errorText(err, 'Erro ao salvar') })
    }
  }

  return (
    <Card className="p-5">
      <h2 className="mb-4 font-semibold">Configuração do caixa</h2>
      <form onSubmit={onSubmit} className="space-y-4">
        {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Mensalidade (R$)">
            <input className="input" inputMode="decimal" required value={form.monthly_fee} onChange={(e) => setForm({ ...form, monthly_fee: e.target.value })} />
          </Field>
          <Field label="Saldo de abertura (R$)">
            <input className="input" inputMode="decimal" required value={form.finance_opening_balance} onChange={(e) => setForm({ ...form, finance_opening_balance: e.target.value })} />
          </Field>
          <Field label="Mês de abertura">
            <input
              className="input"
              type="month"
              value={form.finance_opening_month ? monthKey(form.finance_opening_month) : ''}
              onChange={(e) => setForm({ ...form, finance_opening_month: e.target.value || null })}
            />
          </Field>
        </div>
        <Button type="submit" loading={save.isPending}>Salvar</Button>
      </form>
    </Card>
  )
}

// ---------------------------------------------------------------- Página

type Tone = 'ink' | 'ok' | 'red'
const toneText: Record<Tone, string> = { ink: 'text-ink', ok: 'text-primary-ink', red: 'text-danger-ink' }
const toneIconBg: Record<Tone, string> = { ink: 'bg-soft text-ink', ok: 'bg-ok/15 text-primary-ink', red: 'bg-danger/15 text-danger-ink' }

function StatTile({ label, value, icon: Icon, tone = 'ink', delta, deltaLabel, hint, invertDelta, onClick, pressed }: {
  label: string
  value: number | string
  icon: LucideIcon
  tone?: Tone
  delta?: number | null
  deltaLabel?: string | null
  hint?: string
  /** para saídas, subir é "ruim": só muda o ícone, o texto continua neutro */
  invertDelta?: boolean
  /** tile clicável (ex.: ativa um filtro) */
  onClick?: () => void
  pressed?: boolean
}) {
  const animated = useCountUp(typeof value === 'number' ? value : 0)
  const shown = typeof value === 'number' ? money(animated) : value
  return (
    <Wrapper onClick={onClick} pressed={pressed}>
      <div className="flex items-center gap-2">
        <span className={cx('grid h-7 w-7 place-items-center rounded-full', toneIconBg[tone])} aria-hidden>
          <Icon size={15} strokeWidth={ICON_STROKE} />
        </span>
        <p className="text-xs text-muted">{label}</p>
      </div>
      <p className={cx('tabular mt-2 font-display text-2xl font-bold', toneText[tone])} aria-live="polite">{shown}</p>
      {delta !== undefined && delta !== null && deltaLabel ? (
        <p className="mt-0.5 flex items-center gap-1 text-xs text-muted">
          {delta === 0 ? <Minus size={12} strokeWidth={ICON_STROKE} aria-hidden /> : (delta > 0) !== !!invertDelta ? <TrendingUp size={12} strokeWidth={ICON_STROKE} aria-hidden /> : <TrendingDown size={12} strokeWidth={ICON_STROKE} aria-hidden />}
          {delta > 0 ? '+' : delta < 0 ? '−' : ''}{money(Math.abs(delta))} vs {deltaLabel}
        </p>
      ) : (
        hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>
      )}
    </Wrapper>
  )
}

function Wrapper({ onClick, pressed, children }: { onClick?: () => void; pressed?: boolean; children: ReactNode }) {
  if (!onClick) return <Card className="p-4">{children}</Card>
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      className={cx('card press block w-full p-4 text-left hover:bg-soft', pressed && 'ring-2 ring-inset ring-danger')}
    >
      {children}
    </button>
  )
}

function CashFlowCard({ data, isLoading, error, onRetry, year }: {
  data: FinanceOverview | undefined
  isLoading: boolean
  error: unknown
  onRetry: () => void
  year: number
}) {
  const [mode, setMode] = useState<'12m' | 'tri'>('12m')
  const flow = useMemo(() => (data ? computeFlow(data) : null), [data])
  const points = flow && data ? (mode === '12m' ? flow.months : toQuarters(flow.months, data.year)) : []
  const totals = points.reduce((a, p) => ({ in: a.in + p.entradas, out: a.out + p.saidas }), { in: 0, out: 0 })
  const summary = flow
    ? `Fluxo de caixa ${year}: saldo atual ${money(flow.balance)}, entradas ${money(totals.in)}, saídas ${money(totals.out)} no ano.`
    : ''

  return (
    <Card className="mb-5 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-bold">Fluxo de caixa {year}</h2>
        <div className="flex rounded-full bg-soft p-1 text-xs" role="tablist" aria-label="Período do gráfico">
          {(['12m', 'tri'] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={cx('press min-h-[36px] rounded-full px-3 font-medium', mode === m ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink')}
            >
              {m === '12m' ? '12 meses' : 'Trimestre'}
            </button>
          ))}
        </div>
      </div>
      {isLoading ? (
        <Skeleton className="h-[260px] w-full md:h-[320px]" />
      ) : error ? (
        <div className="grid h-[260px] place-items-center text-center md:h-[320px]">
          <div className="space-y-3">
            <p className="text-sm text-danger-ink">Não foi possível carregar o fluxo de caixa.</p>
            <Button variant="secondary" onClick={onRetry}><RotateCcw size={16} strokeWidth={ICON_STROKE} aria-hidden /> Tentar de novo</Button>
          </div>
        </div>
      ) : !flow || !flow.hasData ? (
        <div className="grid h-[260px] place-items-center text-sm text-muted md:h-[320px]">Sem lançamentos em {year}</div>
      ) : (
        <FinanceChart points={points} summaryLabel={summary} animationKey={`${year}-${mode}`} />
      )}
    </Card>
  )
}

export function FinancePage() {
  // ?inadimplentes=1 (vindo do Dashboard) abre a grade já filtrada
  const [params] = useSearchParams()
  const onlyDelinquents = params.get('inadimplentes') === '1'
  const [tab, setTab] = useState<Tab>(() => {
    if (onlyDelinquents) return 'mensalidades'
    try {
      return (localStorage.getItem('finance-tab') as Tab) || 'mensalidades'
    } catch {
      return 'mensalidades'
    }
  })
  const [year, setYear] = useState(new Date().getFullYear())
  const { data, isLoading, error, refetch } = useFinanceOverview(year)

  useEffect(() => {
    try {
      localStorage.setItem('finance-tab', tab)
    } catch {
      /* armazenamento indisponível */
    }
  }, [tab])

  const nowKey = currentMonthKey()
  const thisMonth = useMemo(() => data?.summary.find((s) => monthKey(s.month) === nowKey), [data, nowKey])
  const mensalistas = data?.rows.filter((r) => r.type === 'MENSALISTA' && r.active).length ?? 0
  const tiles = useMemo(() => (data ? tileNumbers(computeFlow(data)) : null), [data])
  const [delinquentOnly, setDelinquentOnly] = useState(onlyDelinquents)

  return (
    <>
      <PageHeader
        title="Financeiro"
        actions={
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => setYear(year - 1)} aria-label="Ano anterior"><ChevronLeft size={18} strokeWidth={ICON_STROKE} /></Button>
            <span className="tabular w-14 text-center font-display font-semibold">{year}</span>
            <Button variant="ghost" size="sm" onClick={() => setYear(year + 1)} aria-label="Próximo ano"><ChevronRight size={18} strokeWidth={ICON_STROKE} /></Button>
          </div>
        }
      />

      {error && <Alert>{errorText(error, 'Erro ao carregar o financeiro')}</Alert>}
      {isLoading && (
        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-[104px] rounded-card" />)}
        </div>
      )}
      {data && tiles && (
        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatTile label="Saldo em caixa" icon={Wallet} tone="ink" value={tiles.saldo} delta={tiles.deltaSaldo} deltaLabel={tiles.prevLabel} />
          <StatTile label={tiles.refLabel ? `Entradas em ${tiles.refLabel}` : 'Entradas'} icon={ArrowUpRight} tone="ok" value={tiles.entradas} delta={tiles.deltaEntradas} deltaLabel={tiles.prevLabel} />
          <StatTile label={tiles.refLabel ? `Saídas em ${tiles.refLabel}` : 'Saídas'} icon={ArrowDownRight} tone="red" value={tiles.saidas} delta={tiles.deltaSaidas} deltaLabel={tiles.prevLabel} invertDelta />
          <StatTile label="Mensalistas em dia (mês atual)" icon={Users} value={thisMonth ? `${thisMonth.paid_count}/${mensalistas}` : '—'} />
          <StatTile
            label="Inadimplentes"
            icon={AlertTriangle}
            tone={data.delinquent_count ? 'red' : 'ok'}
            value={String(data.delinquent_count)}
            pressed={delinquentOnly}
            onClick={() => {
              setTab('mensalidades')
              setDelinquentOnly((v) => !v)
            }}
          />
        </div>
      )}

      <CashFlowCard data={data} isLoading={isLoading} error={error} onRetry={() => refetch()} year={year} />

      <div className="mb-4 flex gap-1 overflow-x-auto rounded-full bg-soft p-1" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cx('press min-h-[40px] whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium', tab === t.id ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink')}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading || !data ? (
        <Spinner />
      ) : tab === 'mensalidades' ? (
        data.rows.length ? (
          <>
            <ChargePanel count={data.to_charge_count} monthlyFee={data.config.monthly_fee} />
            <FeesGrid data={data} delinquentOnly={delinquentOnly} onDelinquentOnly={setDelinquentOnly} />
          </>
        ) : <EmptyState>Nenhuma mensalidade. Importe a planilha na aba “Importar / Config.”.</EmptyState>
      ) : tab === 'caixa' ? (
        <CashTab year={year} />
      ) : tab === 'cobrancas' ? (
        <CollectionsTab />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <ImportCard />
          <ConfigCard config={data.config} />
        </div>
      )}
    </>
  )
}

/**
 * Cálculos do fluxo de caixa a partir do /finance/overview — uma única fonte para os
 * StatTiles e para o gráfico, para que os números batam por construção.
 *
 * Saldo acumulado ao fim do mês i (a partir do mês de abertura):
 *   saldo(i) = saldo_atual − Σ líquido(k) para k > i      (líquido = entradas − saídas)
 * equivalente a: saldo_inicial + Σ líquido(k) do mês de abertura até i.
 * Meses anteriores à abertura não têm saldo conhecido (null).
 */
import type { FinanceOverview } from '@/api/types'
import { monthAbbr, monthInitial } from './labels'

export interface FlowPoint {
  key: string // YYYY-MM ou T1..T4
  label: string // J F M … ou T1 …
  name: string // nome por extenso para tooltip/tabela
  entradas: number
  saidas: number
  saldo: number | null
}

export interface FlowSummary {
  months: FlowPoint[]
  refIndex: number // mês de referência dos tiles (mês atual, ou dezembro em anos passados); -1 = nenhum
  balance: number
  opening: number
  openingIndex: number | null // índice do mês de abertura dentro do ano (null se fora do ano)
  hasData: boolean
}

const monthNames = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

export function computeFlow(data: FinanceOverview, today = new Date()): FlowSummary {
  const balance = Number(data.balance)
  const opening = Number(data.config.finance_opening_balance)
  const openKey = data.config.finance_opening_month?.slice(0, 7) ?? null
  const base = data.summary.map((s, i) => ({
    key: s.month.slice(0, 7),
    label: monthInitial[i],
    name: `${monthNames[i]} de ${data.year}`,
    entradas: Number(s.fees) + Number(s.income),
    saidas: Number(s.expenses),
  }))
  const counts = (k: string) => openKey === null || k >= openKey
  const net = base.map((m) => (counts(m.key) ? m.entradas - m.saidas : 0))

  const thisYear = today.getFullYear()
  const refIndex = data.year === thisYear ? today.getMonth() : data.year < thisYear ? 11 : -1
  const lastWithData = base.reduce((acc, m, i) => (m.entradas || m.saidas ? i : acc), -1)
  // A linha vai até o mês de referência (ou além, se já houver lançamentos futuros):
  // assim o último ponto é sempre o saldo atual do tile.
  const lineEnd = Math.max(refIndex, lastWithData)
  const allOpenBeforeYear = openKey === null || openKey < `${data.year}-01`

  const months: FlowPoint[] = base.map((m, i) => {
    const after = net.slice(i + 1).reduce((a, b) => a + b, 0)
    const known = i <= lineEnd && (allOpenBeforeYear || (openKey !== null && m.key >= openKey))
    return { ...m, saldo: known ? round2(balance - after) : null }
  })
  const openingIndex = openKey && openKey.startsWith(String(data.year)) ? Number(openKey.slice(5, 7)) - 1 : null
  return {
    months,
    refIndex,
    balance,
    opening,
    openingIndex,
    hasData: base.some((m) => m.entradas || m.saidas) || balance !== 0,
  }
}

/** Agrega por trimestre: soma entradas/saídas; saldo = último saldo conhecido do trimestre. */
export function toQuarters(points: FlowPoint[], year: number): FlowPoint[] {
  return [0, 1, 2, 3].map((q) => {
    const slice = points.slice(q * 3, q * 3 + 3)
    const saldo = [...slice].reverse().find((p) => p.saldo !== null)?.saldo ?? null
    return {
      key: `T${q + 1}`,
      label: `T${q + 1}`,
      name: `${q + 1}º trimestre de ${year}`,
      entradas: round2(slice.reduce((a, p) => a + p.entradas, 0)),
      saidas: round2(slice.reduce((a, p) => a + p.saidas, 0)),
      saldo,
    }
  })
}

export interface TileNumbers {
  saldo: number
  entradas: number
  saidas: number
  deltaSaldo: number | null
  deltaEntradas: number | null
  deltaSaidas: number | null
  refLabel: string | null // ex.: "out"
  prevLabel: string | null // ex.: "set"
}

export function tileNumbers(flow: FlowSummary): TileNumbers {
  const i = flow.refIndex
  const cur = i >= 0 ? flow.months[i] : null
  const prev = i > 0 ? flow.months[i - 1] : null
  return {
    saldo: flow.balance,
    entradas: cur?.entradas ?? 0,
    saidas: cur?.saidas ?? 0,
    deltaSaldo: cur && prev && cur.saldo !== null && prev.saldo !== null ? round2(cur.saldo - prev.saldo) : null,
    deltaEntradas: cur && prev ? round2(cur.entradas - prev.entradas) : null,
    deltaSaidas: cur && prev ? round2(cur.saidas - prev.saidas) : null,
    refLabel: i >= 0 ? monthAbbr[i] : null,
    prevLabel: i > 0 ? monthAbbr[i - 1] : null,
  }
}

const round2 = (n: number) => Math.round(n * 100) / 100

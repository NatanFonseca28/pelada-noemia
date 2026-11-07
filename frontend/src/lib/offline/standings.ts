/** Classificação e mata-mata. Porte fiel de `backend/app/domain/standings.py` (os testes comparam os dois). */
import { PyRandom } from './pyrandom'

export interface Result {
  home: number
  away: number
  homeGoals: number
  awayGoals: number
}

export interface PointsConfig {
  win: number
  draw: number
  loss: number
}

export const DEFAULT_POINTS: PointsConfig = { win: 3, draw: 1, loss: 0 }
export const DEFAULT_TIEBREAKERS = ['PONTOS', 'SALDO_GOLS', 'GOLS_PRO', 'CONFRONTO_DIRETO', 'SORTEIO']

export interface Row {
  team: number
  played: number
  wins: number
  draws: number
  losses: number
  goalsFor: number
  goalsAgainst: number
  points: number
  position: number
  tiebreakNote: string | null
}

export const goalDiff = (r: Row) => r.goalsFor - r.goalsAgainst

function table(teams: number[], results: Result[], pts: PointsConfig): Map<number, Row> {
  const rows = new Map<number, Row>()
  for (const t of teams) {
    rows.set(t, { team: t, played: 0, wins: 0, draws: 0, losses: 0, goalsFor: 0, goalsAgainst: 0, points: 0, position: 0, tiebreakNote: null })
  }
  for (const r of results) {
    const h = rows.get(r.home)
    const a = rows.get(r.away)
    if (!h || !a) continue
    h.played++
    a.played++
    h.goalsFor += r.homeGoals
    h.goalsAgainst += r.awayGoals
    a.goalsFor += r.awayGoals
    a.goalsAgainst += r.homeGoals
    if (r.homeGoals > r.awayGoals) {
      h.wins++
      a.losses++
      h.points += pts.win
      a.points += pts.loss
    } else if (r.homeGoals < r.awayGoals) {
      a.wins++
      h.losses++
      a.points += pts.win
      h.points += pts.loss
    } else {
      h.draws++
      a.draws++
      h.points += pts.draw
      a.points += pts.draw
    }
  }
  return rows
}

const LABELS: Record<string, string> = {
  PONTOS: 'pontos',
  SALDO_GOLS: 'saldo de gols',
  GOLS_PRO: 'gols pró',
  CONFRONTO_DIRETO: 'confronto direto',
  SORTEIO: 'sorteio',
}

const cmpTuple = (a: number[], b: number[]) => {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const d = (a[i] ?? 0) - (b[i] ?? 0)
    if (d) return d
  }
  return 0
}

export function computeStandings(
  teams: number[],
  results: Result[],
  points: PointsConfig = DEFAULT_POINTS,
  tiebreakers: string[] = DEFAULT_TIEBREAKERS,
  seed = 0,
): Row[] {
  const rows = table(teams, results, points)
  const lottery = new PyRandom(seed)
  const lotteryKey = new Map<number, number>()
  for (const t of [...teams].sort((a, b) => a - b)) lotteryKey.set(t, lottery.random())

  const value = (criterion: string, team: number, tied: number[]): number[] => {
    const row = rows.get(team)!
    if (criterion === 'PONTOS') return [row.points]
    if (criterion === 'SALDO_GOLS') return [goalDiff(row)]
    if (criterion === 'GOLS_PRO') return [row.goalsFor]
    if (criterion === 'CONFRONTO_DIRETO') {
      const mini = table(tied, results.filter((r) => tied.includes(r.home) && tied.includes(r.away)), points).get(team)!
      return [mini.points, goalDiff(mini)]
    }
    if (criterion === 'SORTEIO') return [lotteryKey.get(team)!]
    throw new Error(`Critério desconhecido: ${criterion}`)
  }

  const rank = (group: number[], criteria: string[]): number[] => {
    if (group.length <= 1 || criteria.length === 0) return [...group].sort((a, b) => a - b)
    const [criterion, ...rest] = criteria
    const keyed = new Map(group.map((t) => [t, value(criterion, t, group)] as const))
    const distinct = new Map<string, number[]>()
    for (const v of keyed.values()) distinct.set(v.join('|'), v)
    const ordered: number[] = []
    for (const v of [...distinct.values()].sort((a, b) => cmpTuple(b, a))) {
      const bucket = group.filter((t) => cmpTuple(keyed.get(t)!, v) === 0)
      if (bucket.length > 1) ordered.push(...rank(bucket, rest))
      else {
        ordered.push(...bucket)
        const row = rows.get(bucket[0])!
        if (group.length > 1 && criterion !== 'PONTOS') row.tiebreakNote = row.tiebreakNote ?? LABELS[criterion]
      }
    }
    return ordered
  }

  const criteria = [...tiebreakers]
  if (!criteria.includes('PONTOS')) criteria.unshift('PONTOS')
  return rank([...teams], criteria).map((t, i) => {
    const row = rows.get(t)!
    row.position = i + 1
    return row
  })
}

// ---------------------------------------------------------------- mata-mata

export interface KnockoutResult {
  home: number
  away: number
  homeGoals: number
  awayGoals: number
  homePenalties?: number | null
  awayPenalties?: number | null
}

export class TieRuleError extends Error {}

/** Vencedor de um jogo eliminatório conforme a regra de empate. */
export function knockoutWinner(r: KnockoutResult, rule: string, campaignRank: Map<number, number> = new Map()): number {
  if (r.homeGoals !== r.awayGoals) return r.homeGoals > r.awayGoals ? r.home : r.away
  if (rule === 'PENALTIS') {
    if (r.homePenalties == null || r.awayPenalties == null) throw new TieRuleError('Empate no mata-mata: informe o placar dos pênaltis')
    if (r.homePenalties === r.awayPenalties) throw new TieRuleError('Os pênaltis não podem terminar empatados')
    return r.homePenalties > r.awayPenalties ? r.home : r.away
  }
  if (rule === 'MELHOR_CAMPANHA') {
    const rank = (t: number) => campaignRank.get(t) ?? 99
    return rank(r.home) <= rank(r.away) ? r.home : r.away
  }
  if (rule === 'GOL_DE_OURO') throw new TieRuleError('Regra gol de ouro: o jogo não termina empatado; registre o gol da vitória')
  throw new TieRuleError(`Regra de empate desconhecida: ${rule}`)
}

/** "A:1" → 1º do grupo A (se o grupo terminou); "V:SF1" → vencedor da SF1; "P:SF1" → perdedor. */
export function resolveSource(
  source: string,
  tables: Record<string, Row[]>,
  complete: Record<string, boolean>,
  winners: Record<string, number>,
  losers: Record<string, number>,
): number | null {
  const i = source.indexOf(':')
  const kind = source.slice(0, i)
  const ref = source.slice(i + 1)
  if (kind === 'V') return winners[ref] ?? null
  if (kind === 'P') return losers[ref] ?? null
  if (!complete[kind]) return null
  const t = tables[kind] ?? []
  const pos = Number(ref)
  return pos > 0 && pos <= t.length ? t[pos - 1].team : null
}

/** Ranking geral por campanha (posição no grupo, pontos, saldo, gols). */
export function campaignRanking(tables: Record<string, Row[]>): Map<number, number> {
  const rows = Object.values(tables).flat()
  rows.sort((a, b) => a.position - b.position || b.points - a.points || goalDiff(b) - goalDiff(a) || b.goalsFor - a.goalsFor)
  return new Map(rows.map((r, i) => [r.team, i + 1]))
}

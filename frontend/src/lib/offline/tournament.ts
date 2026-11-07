/**
 * Campeonato calculado no celular (sem internet): aplica resultado, reabertura, próxima partida e encerramento
 * sobre o campeonato guardado, refazendo classificação, chaveamento, campeão e quem dá a saída.
 * Espelha `TournamentService.set_result/reopen/recalc` do servidor; quando a internet volta, o servidor vale.
 */
import type { MatchItem, StandingRow, TeamRef, Tournament } from '@/api/types'
import {
  DEFAULT_POINTS,
  campaignRanking,
  computeStandings,
  knockoutWinner,
  resolveSource,
  TieRuleError,
  type PointsConfig,
  type Row,
} from './standings'

const STAGE_LABEL: Record<string, string> = { SF1: 'Semifinal 1', SF2: 'Semifinal 2', R: '2º × 3º', F: 'Final' }

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return 'A definir'
  const i = source.indexOf(':')
  const kind = source.slice(0, i)
  const ref = source.slice(i + 1)
  if (kind === 'V') return `Vencedor ${STAGE_LABEL[ref] ?? ref}`
  if (kind === 'P') return `Perdedor ${STAGE_LABEL[ref] ?? ref}`
  return `${ref}º do grupo ${kind}`
}

type Cfg = Tournament['config'] & { seed?: number; points?: PointsConfig }
const cfgOf = (t: Tournament) => t.config as Cfg
const isCasual = (t: Tournament) => t.format_code === 'PELADA_NORMAL'

/** Erro que o servidor também devolveria (ex.: pênaltis faltando): a tela mostra a mesma mensagem. */
export class OfflineRuleError extends Error {}

function teamMap(t: Tournament): Map<number, TeamRef> {
  const m = new Map<number, TeamRef>()
  for (const team of t.teams) m.set(team.id, team)
  for (const g of t.groups) for (const r of g.standings) m.set(r.team.id, r.team)
  return m
}

interface Tables {
  tables: Record<string, Row[]>
  complete: Record<string, boolean>
}

function groupTables(t: Tournament): Tables {
  const points = cfgOf(t).points ?? DEFAULT_POINTS
  const seed = cfgOf(t).seed ?? 0
  const tables: Record<string, Row[]> = {}
  const complete: Record<string, boolean> = {}
  const played = t.matches.filter((m) => m.status === 'ENCERRADA' && m.home && m.away)
  for (const g of t.groups) {
    const teams = g.standings.map((r) => r.team.id)
    if (isCasual(t)) {
      const results = played.map((m) => ({ home: m.home!.id, away: m.away!.id, homeGoals: m.home_score, awayGoals: m.away_score }))
      tables[g.name] = computeStandings(teams, results, points, ['PONTOS', 'SALDO_GOLS', 'GOLS_PRO'], seed)
      complete[g.name] = t.status === 'ENCERRADO'
    } else {
      const gm = t.matches.filter((m) => m.group === g.name)
      const results = gm.filter((m) => m.status === 'ENCERRADA' && m.home && m.away)
        .map((m) => ({ home: m.home!.id, away: m.away!.id, homeGoals: m.home_score, awayGoals: m.away_score }))
      tables[g.name] = computeStandings(teams, results, points, cfgOf(t).tiebreakers, seed)
      complete[g.name] = gm.length > 0 && gm.every((m) => m.status === 'ENCERRADA')
    }
  }
  return { tables, complete }
}

/** Quem dá a saída (porte de `domain/kickoff.py`): grupos/pelada dividem igual; mata-mata = melhor campanha. */
function assignKickoffs(matches: MatchItem[], rank: Map<number, number>): Map<number, number | null> {
  const out = new Map<number, number | null>()
  const count = new Map<number, number>()
  for (const m of [...matches].sort((a, b) => a.seq - b.seq)) {
    if (!m.home || !m.away) out.set(m.id, null)
    else if (m.stage === 'GRUPO' || m.stage === 'AMISTOSO') {
      const team = (count.get(m.away.id) ?? 0) < (count.get(m.home.id) ?? 0) ? m.away.id : m.home.id
      count.set(team, (count.get(team) ?? 0) + 1)
      out.set(m.id, team)
    } else {
      const rh = rank.get(m.home.id)
      const ra = rank.get(m.away.id)
      out.set(m.id, rh === undefined && ra === undefined ? null : rh === undefined || (ra !== undefined && ra < rh) ? m.away.id : m.home.id)
    }
  }
  return out
}

/** Refaz classificação, chaveamento, campeão e saída de bola. Não muda o objeto recebido. */
export function recalc(input: Tournament): Tournament {
  const t: Tournament = structuredClone(input)
  const teams = teamMap(t)
  const { tables, complete } = groupTables(t)

  const winners: Record<string, number> = {}
  const losers: Record<string, number> = {}
  for (const m of t.matches) {
    if (m.status === 'ENCERRADA' && m.winner_team_id && m.stage !== 'GRUPO') {
      winners[m.code] = m.winner_team_id
      if (m.home && m.away) losers[m.code] = m.winner_team_id === m.home.id ? m.away.id : m.home.id
    }
  }
  for (const m of t.matches) {
    if (m.status === 'ENCERRADA' || m.stage === 'GRUPO') continue
    if (m.home_source) {
      const id = resolveSource(m.home_source, tables, complete, winners, losers)
      m.home = id != null ? teams.get(id) ?? null : null
    }
    if (m.away_source) {
      const id = resolveSource(m.away_source, tables, complete, winners, losers)
      m.away = id != null ? teams.get(id) ?? null : null
    }
  }
  for (const m of t.matches) {
    m.home_label = m.home?.name ?? sourceLabel(m.home_source ?? null)
    m.away_label = m.away?.name ?? sourceLabel(m.away_source ?? null)
  }

  const final = t.matches.find((m) => m.stage === 'FINAL')
  let champion: number | null = null
  let runnerUp: number | null = null
  if (final && final.status === 'ENCERRADA') {
    champion = final.winner_team_id
    runnerUp = final.away?.id === champion ? final.home?.id ?? null : final.away?.id ?? null
  } else if (t.format_code === 'PONTOS_CORRIDOS' && Object.values(complete).length && Object.values(complete).every(Boolean)) {
    champion = tables.A?.[0]?.team ?? null
    runnerUp = tables.A?.[1]?.team ?? null
  }
  if (!isCasual(t)) {
    t.champion = champion != null ? teams.get(champion) ?? null : null
    t.runner_up = runnerUp != null ? teams.get(runnerUp) ?? null : null
    if (champion) {
      t.status = 'ENCERRADO'
      t.finished_at = t.finished_at ?? new Date().toISOString()
    } else {
      t.status = 'EM_ANDAMENTO'
      t.finished_at = null
    }
  }

  t.groups = t.groups.map((g) => ({
    name: g.name,
    complete: complete[g.name] ?? g.complete,
    standings: (tables[g.name] ?? []).map<StandingRow>((r) => ({
      position: r.position,
      team: teams.get(r.team)!,
      played: r.played,
      wins: r.wins,
      draws: r.draws,
      losses: r.losses,
      goals_for: r.goalsFor,
      goals_against: r.goalsAgainst,
      goal_diff: r.goalsFor - r.goalsAgainst,
      points: r.points,
      tiebreak_note: r.tiebreakNote,
    })),
  }))

  const kick = assignKickoffs(t.matches, isCasual(t) ? new Map() : campaignRanking(tables))
  for (const m of t.matches) m.kickoff_team_id = kick.get(m.id) ?? null
  t.next_match_id = t.matches.find((m) => m.status !== 'ENCERRADA')?.id ?? null
  return t
}

export interface ResultInput {
  home_score: number
  away_score: number
  home_penalties?: number | null
  away_penalties?: number | null
  started_at?: string
  ended_at?: string
  played_seconds?: number
}

const findMatch = (t: Tournament, matchId: number) => {
  const m = t.matches.find((x) => x.id === matchId)
  if (!m) throw new OfflineRuleError('Partida não encontrada')
  return m
}

/** Encerra a partida com o placar e refaz o campeonato. */
export function applyResult(input: Tournament, matchId: number, r: ResultInput): Tournament {
  const t = structuredClone(input)
  const m = findMatch(t, matchId)
  if (!m.home || !m.away) throw new OfflineRuleError('Os times desta partida ainda não estão definidos')
  const isKo = m.stage === 'SEMIFINAL' || m.stage === 'FINAL'
  m.home_score = r.home_score
  m.away_score = r.away_score
  if (isKo) {
    const { tables } = groupTables(t)
    try {
      m.winner_team_id = knockoutWinner(
        { home: m.home.id, away: m.away.id, homeGoals: r.home_score, awayGoals: r.away_score, homePenalties: r.home_penalties, awayPenalties: r.away_penalties },
        cfgOf(t).knockout_tie_rule,
        campaignRanking(tables),
      )
    } catch (e) {
      if (e instanceof TieRuleError) throw new OfflineRuleError(e.message)
      throw e
    }
    const draw = r.home_score === r.away_score
    m.home_penalties = draw ? r.home_penalties ?? null : null
    m.away_penalties = draw ? r.away_penalties ?? null : null
  } else {
    m.home_penalties = m.away_penalties = null
    m.winner_team_id = r.home_score > r.away_score ? m.home.id : r.away_score > r.home_score ? m.away.id : null
  }
  m.status = 'ENCERRADA'
  m.started_at = r.started_at ?? m.started_at
  m.ended_at = r.ended_at ?? m.ended_at ?? new Date().toISOString()
  if (r.played_seconds != null) m.elapsed_before_pause = r.played_seconds
  m.version += 1
  return recalc(t)
}

/** Desfaz o encerramento da partida (o placar da súmula fica). */
export function applyReopen(input: Tournament, matchId: number): Tournament {
  const t = structuredClone(input)
  const m = findMatch(t, matchId)
  m.status = 'AGENDADA'
  m.home_penalties = m.away_penalties = null
  m.winner_team_id = null
  m.started_at = m.ended_at = null
  m.elapsed_before_pause = 0
  m.version += 1
  return recalc(t)
}

/** Pelada normal: cria a próxima partida entre os dois times. `seq` é o número esperado (idempotência no servidor). */
export function applyAddMatch(input: Tournament, seq: number): Tournament {
  const t = structuredClone(input)
  if (t.matches.some((m) => m.seq >= seq)) return t
  const last = [...t.matches].sort((a, b) => a.seq - b.seq).at(-1)
  if (!last) throw new OfflineRuleError('Sem partida de referência para criar a próxima')
  t.matches.push({
    ...last,
    id: -seq, // id provisório: o servidor devolve o definitivo ao sincronizar
    seq,
    code: `J${seq}`,
    status: 'AGENDADA',
    home_score: 0,
    away_score: 0,
    home_penalties: null,
    away_penalties: null,
    winner_team_id: null,
    started_at: null,
    ended_at: null,
    elapsed_before_pause: 0,
    version: 1,
    goalkeepers: [],
    loans: [],
  })
  return recalc(t)
}

/** Encerra a noite (pelada normal): descarta partidas não jogadas. */
export function applyFinish(input: Tournament): Tournament {
  const t = structuredClone(input)
  t.matches = t.matches.filter((m) => m.status === 'ENCERRADA')
  t.status = 'ENCERRADO'
  t.finished_at = new Date().toISOString()
  return recalc(t)
}

import { describe, expect, it } from 'vitest'
import type { MatchItem, TeamRef, Tournament } from '@/api/types'
import { applyAddMatch, applyFinish, applyReopen, applyResult, OfflineRuleError } from './tournament'

const team = (id: number): TeamRef => ({ id, name: `T${id}`, color: '#000' })
const T = [team(1), team(2), team(3)]

function match(p: Partial<MatchItem> & { id: number; seq: number; code: string; stage: MatchItem['stage'] }): MatchItem {
  return {
    leg: 1, group: null, home: null, away: null, home_source: null, away_source: null, home_label: '', away_label: '',
    planned_seconds: 480, goal_limit: null, status: 'AGENDADA', home_score: 0, away_score: 0, home_penalties: null,
    away_penalties: null, winner_team_id: null, kickoff_team_id: null, started_at: null, ended_at: null,
    elapsed_before_pause: 0, version: 1, ...p,
  }
}

/** 3 times: todos contra todos + 2º×3º + final contra o 1º. */
function repescagem(): Tournament {
  const row = (t: TeamRef) => ({ position: 1, team: t, played: 0, wins: 0, draws: 0, losses: 0, goals_for: 0, goals_against: 0, goal_diff: 0, points: 0, tiebreak_note: null })
  return {
    id: 1, round_id: 1, round_date: '2026-11-04', format_code: 'GRUPO_REPESCAGEM_FINAL', format_name: 'x', legs: 1, status: 'EM_ANDAMENTO',
    match_seconds: 480, knockout_seconds: 600, final_seconds: 720,
    config: { knockout_tie_rule: 'PENALTIS', tiebreakers: ['PONTOS', 'SALDO_GOLS', 'GOLS_PRO', 'CONFRONTO_DIRETO', 'SORTEIO'], final_weight: '1.5', changeover_minutes: 1, seed: 7, points: { win: 3, draw: 1, loss: 0 } } as Tournament['config'],
    teams: T,
    groups: [{ name: 'A', complete: false, standings: T.map(row) }],
    matches: [
      match({ id: 1, seq: 1, code: 'A1', stage: 'GRUPO', group: 'A', home: T[0], away: T[1] }),
      match({ id: 2, seq: 2, code: 'A2', stage: 'GRUPO', group: 'A', home: T[0], away: T[2] }),
      match({ id: 3, seq: 3, code: 'A3', stage: 'GRUPO', group: 'A', home: T[1], away: T[2] }),
      match({ id: 4, seq: 4, code: 'R', stage: 'SEMIFINAL', home_source: 'A:2', away_source: 'A:3' }),
      match({ id: 5, seq: 5, code: 'F', stage: 'FINAL', home_source: 'A:1', away_source: 'V:R' }),
    ],
    next_match_id: 1, champion: null, runner_up: null, finished_at: null,
  }
}

describe('campeonato calculado sem internet', () => {
  it('fecha o grupo, monta a repescagem e a final, e define o campeão', () => {
    let t = repescagem()
    t = applyResult(t, 1, { home_score: 2, away_score: 0 }) // T1 2x0 T2
    t = applyResult(t, 2, { home_score: 1, away_score: 0 }) // T1 1x0 T3
    expect(t.matches[3].home).toBeNull() // grupo ainda não terminou
    t = applyResult(t, 3, { home_score: 3, away_score: 1 }) // T2 3x1 T3
    expect(t.groups[0].complete).toBe(true)
    expect(t.groups[0].standings.map((r) => r.team.id)).toEqual([1, 2, 3])
    const r = t.matches[3]
    expect([r.home?.id, r.away?.id]).toEqual([2, 3]) // 2º × 3º
    expect(t.matches[4].home?.id).toBe(1) // 1º já está na final
    t = applyResult(t, 4, { home_score: 1, away_score: 1, home_penalties: 3, away_penalties: 2 })
    expect(t.matches[3].winner_team_id).toBe(2)
    expect(t.matches[4].away?.id).toBe(2)
    t = applyResult(t, 5, { home_score: 2, away_score: 0 })
    expect(t.champion?.id).toBe(1)
    expect(t.runner_up?.id).toBe(2)
    expect(t.status).toBe('ENCERRADO')
    expect(t.next_match_id).toBeNull()
  })

  it('empate no mata-mata sem pênaltis falha como o servidor', () => {
    let t = repescagem()
    t = applyResult(t, 1, { home_score: 2, away_score: 0 })
    t = applyResult(t, 2, { home_score: 1, away_score: 0 })
    t = applyResult(t, 3, { home_score: 3, away_score: 1 })
    expect(() => applyResult(t, 4, { home_score: 1, away_score: 1 })).toThrow(OfflineRuleError)
  })

  it('reabrir uma partida volta a classificação e esvazia o que dependia dela', () => {
    let t = repescagem()
    t = applyResult(t, 1, { home_score: 2, away_score: 0 })
    t = applyResult(t, 2, { home_score: 1, away_score: 0 })
    t = applyResult(t, 3, { home_score: 3, away_score: 1 })
    expect(t.matches[3].home).not.toBeNull()
    t = applyReopen(t, 3)
    expect(t.groups[0].complete).toBe(false)
    expect(t.matches[3].home).toBeNull()
    expect(t.matches[2].status).toBe('AGENDADA')
  })

  it('não muda o campeonato recebido', () => {
    const t = repescagem()
    applyResult(t, 1, { home_score: 2, away_score: 0 })
    expect(t.matches[0].status).toBe('AGENDADA')
  })
})

describe('pelada normal sem internet', () => {
  const casual = (): Tournament => {
    const t = repescagem()
    return {
      ...t, format_code: 'PELADA_NORMAL', teams: [T[0], T[1]],
      groups: [{ name: 'Geral', complete: false, standings: t.groups[0].standings.slice(0, 2) }],
      matches: [match({ id: 1, seq: 1, code: 'J1', stage: 'AMISTOSO', home: T[0], away: T[1], goal_limit: 2 })],
    }
  }

  it('encerra a partida, cria a próxima e encerra a noite', () => {
    let t = casual()
    t = applyResult(t, 1, { home_score: 2, away_score: 1 })
    expect(t.groups[0].standings[0].team.id).toBe(1)
    t = applyAddMatch(t, 2)
    expect(t.matches.map((m) => m.code)).toEqual(['J1', 'J2'])
    expect(t.next_match_id).toBe(t.matches[1].id)
    expect(applyAddMatch(t, 2).matches).toHaveLength(2) // reenviar não duplica
    t = applyFinish(t)
    expect(t.matches).toHaveLength(1) // partida não jogada é descartada
    expect(t.status).toBe('ENCERRADO')
  })
})

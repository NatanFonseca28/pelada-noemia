import { describe, expect, it } from 'vitest'
import golden from './golden.json'
import { PyRandom } from './pyrandom'
import { computeStandings, knockoutWinner, TieRuleError } from './standings'

describe('PyRandom (igual ao random.Random do Python)', () => {
  it('seed 42', () => {
    const r = new PyRandom(42)
    expect(r.random()).toBeCloseTo(0.6394267984578837, 15)
    expect(r.random()).toBeCloseTo(0.025010755222666936, 15)
  })
  it('seed 0', () => {
    expect(new PyRandom(0).random()).toBeCloseTo(0.8444218515250481, 15)
  })
})

describe('classificação igual ao Python', () => {
  golden.standings.forEach((c, i) => {
    it(`caso ${i}`, () => {
      const rows = computeStandings(c.teams, c.results, c.points, c.tiebreakers, c.seed)
      expect(rows.map((r) => ({ team: r.team, position: r.position, points: r.points, played: r.played, goalsFor: r.goalsFor, goalsAgainst: r.goalsAgainst, note: r.tiebreakNote })))
        .toEqual(c.expected)
    })
  })
})

describe('vencedor do mata-mata igual ao Python', () => {
  golden.knockout.forEach((c, i) => {
    it(`caso ${i}`, () => {
      const rank = new Map(Object.entries(c.rank).map(([k, v]) => [Number(k), v as number]))
      const run = () => knockoutWinner({ home: c.home, away: c.away, homeGoals: c.homeGoals, awayGoals: c.awayGoals, homePenalties: c.homePenalties, awayPenalties: c.awayPenalties }, c.rule, rank)
      if (c.error) expect(run).toThrow(TieRuleError)
      else expect(run()).toBe(c.winner)
    })
  })
})

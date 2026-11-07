"""Gera casos de referência (JSON) da classificação para o app conferir o cálculo offline contra o Python.

Uso: python -m scripts.export_offline_golden > ../frontend/src/lib/offline/golden.json
"""
import json
import random
import sys

from app.domain.standings import (
    DEFAULT_TIEBREAKERS,
    KnockoutResult,
    PointsConfig,
    Result,
    TieRuleError,
    compute_standings,
    knockout_winner,
)


def standings_cases(rng: random.Random, n: int = 80) -> list[dict]:
    cases = []
    for i in range(n):
        teams = rng.sample(range(1, 40), rng.randint(3, 6))
        results = []
        for a in teams:
            for b in teams:
                if a < b and rng.random() < 0.85:
                    home, away = (a, b) if rng.random() < 0.5 else (b, a)
                    results.append(Result(home, away, rng.randint(0, 3), rng.randint(0, 3)))
        tie = rng.choice([DEFAULT_TIEBREAKERS, ["PONTOS", "SALDO_GOLS", "GOLS_PRO"], ["PONTOS", "CONFRONTO_DIRETO", "SORTEIO"],
                          ["SORTEIO"]])
        points = rng.choice([PointsConfig(), PointsConfig(3, 1, 0), PointsConfig(2, 1, 0)])
        seed = rng.choice([0, 1, 42, rng.randint(1, 2**31 - 1), rng.randint(1, 2**31 - 1)])
        rows = compute_standings(teams, results, points, tie, seed)
        cases.append({
            "teams": teams, "tiebreakers": tie, "seed": seed, "points": {"win": points.win, "draw": points.draw, "loss": points.loss},
            "results": [{"home": r.home, "away": r.away, "homeGoals": r.home_goals, "awayGoals": r.away_goals} for r in results],
            "expected": [{"team": r.team, "position": r.position, "points": r.points, "played": r.played,
                          "goalsFor": r.goals_for, "goalsAgainst": r.goals_against, "note": r.tiebreak_note} for r in rows],
        })
    return cases


def knockout_cases(rng: random.Random, n: int = 60) -> list[dict]:
    cases = []
    for _ in range(n):
        home, away = rng.sample(range(1, 9), 2)
        hg, ag = rng.randint(0, 3), rng.randint(0, 3)
        hp = ap = None
        if hg == ag and rng.random() < 0.8:
            hp, ap = rng.randint(0, 5), rng.randint(0, 5)
        rule = rng.choice(["PENALTIS", "MELHOR_CAMPANHA", "GOL_DE_OURO"])
        rank = {t: i + 1 for i, t in enumerate(rng.sample(range(1, 9), 8))}
        try:
            winner = knockout_winner(KnockoutResult(home, away, hg, ag, hp, ap), rule, rank)
            err = False
        except TieRuleError:
            winner, err = None, True
        cases.append({"home": home, "away": away, "homeGoals": hg, "awayGoals": ag, "homePenalties": hp, "awayPenalties": ap,
                      "rule": rule, "rank": {str(k): v for k, v in rank.items()}, "winner": winner, "error": err})
    return cases


if __name__ == "__main__":
    rng = random.Random(2026)
    json.dump({"standings": standings_cases(rng), "knockout": knockout_cases(rng)}, sys.stdout, separators=(",", ":"))

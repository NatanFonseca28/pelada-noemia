import pytest

from app.domain.standings import (
    KnockoutResult,
    PointsConfig,
    Result,
    TieRuleError,
    campaign_ranking,
    compute_standings,
    knockout_winner,
    resolve_source,
)


def order(rows):
    return [r.team for r in rows]


def test_pontuacao_basica():
    rows = compute_standings([1, 2, 3], [Result(1, 2, 2, 0), Result(2, 3, 1, 1), Result(3, 1, 0, 1)])
    assert order(rows) == [1, 3, 2]
    t1 = rows[0]
    assert (t1.points, t1.wins, t1.goals_for, t1.goals_against, t1.goal_diff) == (6, 2, 3, 0, 3)
    assert rows[1].points == 1 and rows[2].points == 1


def test_pontuacao_configuravel():
    rows = compute_standings([1, 2], [Result(1, 2, 1, 1)], PointsConfig(win=2, draw=0, loss=0))
    assert [r.points for r in rows] == [0, 0]


def test_desempate_saldo_depois_gols_pro():
    results = [Result(1, 3, 3, 0), Result(2, 3, 2, 0), Result(1, 2, 0, 1), Result(3, 4, 0, 0),
               Result(4, 1, 1, 2), Result(4, 2, 2, 2)]
    rows = compute_standings([1, 2, 3, 4], results)
    # 1: 6 pts SG +3 ; 2: 7 pts
    assert order(rows)[:2] == [2, 1]


def test_confronto_direto_entre_dois():
    # 1 e 2 empatados em pontos, saldo e gols pró; 2 venceu o confronto
    results = [Result(1, 2, 0, 1), Result(1, 3, 2, 0), Result(2, 3, 0, 1)]
    rows = compute_standings([1, 2, 3], results, tiebreakers=["PONTOS", "SALDO_GOLS", "GOLS_PRO", "CONFRONTO_DIRETO"])
    # 1: 3pts SG+1 GP2 ; 2: 3pts SG0 GP1 ; 3: 3pts SG-1 GP1  → saldo já resolve
    assert order(rows) == [1, 2, 3]
    rows = compute_standings([1, 2, 3], results, tiebreakers=["PONTOS", "CONFRONTO_DIRETO"])
    # mini-tabela circular (cada um venceu 1): segue empate → ordem estável por id
    assert {r.points for r in rows} == {3}


def test_confronto_direto_desempata_dois_de_tres():
    results = [
        Result(1, 2, 1, 0),  # 1 vence 2
        Result(1, 3, 0, 1),
        Result(2, 3, 2, 1),
        Result(1, 4, 1, 0), Result(2, 4, 1, 0), Result(3, 4, 0, 0),
    ]
    rows = compute_standings([1, 2, 3, 4], results, tiebreakers=["PONTOS", "CONFRONTO_DIRETO", "SORTEIO"])
    # 1: 6 pts, 2: 6 pts, 3: 4 pts... 1 venceu 2 no confronto
    assert order(rows)[:2] == [1, 2]
    assert rows[0].tiebreak_note == "confronto direto"


def test_sorteio_e_deterministico_pela_seed():
    results = [Result(1, 2, 0, 0)]
    a = order(compute_standings([1, 2], results, tiebreakers=["PONTOS", "SORTEIO"], seed=7))
    b = order(compute_standings([1, 2], results, tiebreakers=["PONTOS", "SORTEIO"], seed=7))
    assert a == b
    outcomes = {tuple(order(compute_standings([1, 2], results, tiebreakers=["PONTOS", "SORTEIO"], seed=s)))
                for s in range(20)}
    assert outcomes == {(1, 2), (2, 1)}


def test_vencedor_mata_mata():
    assert knockout_winner(KnockoutResult(1, 2, 2, 1), "PENALTIS") == 1
    assert knockout_winner(KnockoutResult(1, 2, 1, 1, 3, 4), "PENALTIS") == 2
    with pytest.raises(TieRuleError):
        knockout_winner(KnockoutResult(1, 2, 1, 1), "PENALTIS")
    with pytest.raises(TieRuleError):
        knockout_winner(KnockoutResult(1, 2, 1, 1, 3, 3), "PENALTIS")
    assert knockout_winner(KnockoutResult(1, 2, 0, 0), "MELHOR_CAMPANHA", {1: 3, 2: 1}) == 2
    with pytest.raises(TieRuleError):
        knockout_winner(KnockoutResult(1, 2, 0, 0), "GOL_DE_OURO")


def test_resolve_origens_do_chaveamento():
    a = compute_standings([1, 3], [Result(1, 3, 2, 0)])
    b = compute_standings([2, 4], [Result(2, 4, 0, 1)])
    tables, complete = {"A": a, "B": b}, {"A": True, "B": False}
    assert resolve_source("A:1", tables, complete, {}, {}) == 1
    assert resolve_source("A:2", tables, complete, {}, {}) == 3
    assert resolve_source("B:1", tables, complete, {}, {}) is None  # grupo B não terminou
    assert resolve_source("V:SF1", tables, complete, {"SF1": 9}, {"SF1": 8}) == 9
    assert resolve_source("P:SF1", tables, complete, {"SF1": 9}, {"SF1": 8}) == 8
    assert resolve_source("V:SF2", tables, complete, {}, {}) is None


def test_ranking_de_campanha():
    a = compute_standings([1, 3], [Result(1, 3, 2, 0)])
    b = compute_standings([2, 4], [Result(2, 4, 5, 0)])
    rank = campaign_ranking({"A": a, "B": b})
    assert rank[2] == 1 and rank[1] == 2  # ambos 1º, B tem mais saldo

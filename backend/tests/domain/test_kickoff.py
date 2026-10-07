from collections import Counter

from app.domain.kickoff import KickoffMatch, assign_kickoffs


def group(pairs, stage="GRUPO", start=1):
    return [KickoffMatch(id=i, seq=i, stage=stage, home=h, away=a) for i, (h, a) in enumerate(pairs, start=start)]


def test_grupo_de_3_cada_time_sai_uma_vez():
    k = assign_kickoffs(group([(1, 2), (1, 3), (2, 3)]), {})
    assert Counter(k.values()) == {1: 1, 2: 1, 3: 1}


def test_grupo_de_4_ida_e_volta_fica_igual():
    rr = [(1, 2), (3, 4), (1, 3), (2, 4), (1, 4), (2, 3)]
    pairs = rr + [(a, h) for h, a in rr]  # volta
    k = assign_kickoffs(group(pairs), {})
    assert set(Counter(k.values()).values()) == {3}  # 12 jogos, 4 times: 3 saídas cada


def test_grupo_de_4_so_ida_diferenca_maxima_de_um():
    k = assign_kickoffs(group([(1, 2), (3, 4), (1, 3), (2, 4), (1, 4), (2, 3)]), {})
    counts = Counter(k.values())
    assert max(counts.values()) - min(counts[t] for t in (1, 2, 3, 4)) <= 1


def test_pelada_normal_alterna():
    k = assign_kickoffs(group([(1, 2)] * 4, stage="AMISTOSO"), {})
    assert [k[i] for i in range(1, 5)] == [1, 2, 1, 2]


def test_mata_mata_melhor_campanha_sai_com_a_bola():
    rank = {7: 1, 8: 2, 9: 3}
    ko = [KickoffMatch(id=10, seq=10, stage="SEMIFINAL", home=8, away=9),
          KickoffMatch(id=11, seq=11, stage="FINAL", home=9, away=7),
          KickoffMatch(id=12, seq=12, stage="FINAL", home=None, away=7)]
    k = assign_kickoffs(ko, rank)
    assert k[10] == 8 and k[11] == 7 and k[12] is None  # mandante não importa; time indefinido → sem saída

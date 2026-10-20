from app.domain.goalkeeper_assign import GkMatch, assign_match_goalkeepers


def matches(*pairs):
    return [GkMatch(id=i + 1, seq=i + 1, home=h, away=a) for i, (h, a) in enumerate(pairs)]


def test_sem_goleiro_da_pelada_ou_sem_time_precisando_nao_ha_nada():
    ms = matches((1, 2))
    assert assign_match_goalkeepers(ms, {1, 2}, []) == {}
    assert assign_match_goalkeepers(ms, set(), [9]) == {}


def test_tres_times_de_5_rodiziam_o_goleiro():
    ms = matches((1, 2), (1, 3), (2, 3), (1, 2), (1, 3), (2, 3))
    out = assign_match_goalkeepers(ms, {1, 2, 3}, [9])
    counts = {t: sum(1 for sides in out.values() if t in sides) for t in (1, 2, 3)}
    assert all(len(sides) == 1 for sides in out.values())
    assert max(counts.values()) - min(counts.values()) <= 1
    assert out[1] == {1: 9}  # empate → mandante


def test_so_um_lado_precisa_o_goleiro_vai_para_ele():
    out = assign_match_goalkeepers(matches((1, 2), (3, 2)), {2}, [9])
    assert out == {1: {2: 9}, 2: {2: 9}}


def test_dois_goleiros_cobrem_os_dois_lados():
    out = assign_match_goalkeepers(matches((1, 2)), {1, 2}, [8, 9])
    assert out == {1: {1: 8, 2: 9}}


def test_partida_sem_times_definidos_e_ignorada():
    ms = [GkMatch(1, 1, None, 2), GkMatch(2, 2, 1, 2)]
    assert list(assign_match_goalkeepers(ms, {1, 2}, [9])) == [2]

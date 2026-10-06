from decimal import Decimal
from itertools import combinations

import pytest

from app.domain.formats import FormatCode, Stage, TimeConfig, build_matches, match_times, round_robin, suggest_formats

CFG = TimeConfig(total_minutes=90, changeover_minutes=1, final_weight=Decimal("1.5"))


def codes(n, cfg=CFG):
    return {o.code for o in suggest_formats(n, cfg)}


def option(n, code, legs=1, cfg=CFG):
    return next(o for o in suggest_formats(n, cfg) if o.code == code and o.legs == legs)


def total_used(o, cfg=CFG):
    """Duração total da noite: jogos + trocas."""
    secs = 0
    for m in o.matches:
        secs += {Stage.GRUPO: o.match_seconds, Stage.SEMIFINAL: o.knockout_seconds, Stage.FINAL: o.final_seconds}[m.stage]
    return secs + cfg.changeover_minutes * 60 * (len(o.matches) - 1)


def test_formatos_por_numero_de_times():
    assert codes(2) == {FormatCode.PELADA_NORMAL}
    assert codes(3) == {FormatCode.GRUPO_REPESCAGEM_FINAL}
    assert codes(4) == {FormatCode.GRUPO_SEMI_FINAL}
    assert codes(6) == {FormatCode.DOIS_GRUPOS_SEMI_FINAL, FormatCode.GRUPO_SEMI_FINAL, FormatCode.DOIS_GRUPOS_FINAL}


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_todos_contra_todos_sem_repetir(n):
    games = round_robin(list(range(n)))
    assert len(games) == n * (n - 1) // 2
    assert {frozenset(g) for g in games} == {frozenset(c) for c in combinations(range(n), 2)}


def test_round_robin_evita_time_jogar_3_seguidas():
    games = round_robin(list(range(4)))
    for i in range(len(games) - 2):
        assert not set(games[i]) & set(games[i + 1]) & set(games[i + 2])


def test_3_times_2o_x_3o_e_final_contra_o_1o():
    _, matches = build_matches(FormatCode.GRUPO_REPESCAGEM_FINAL, 3)
    ko = [(m.stage, m.code, m.home_source, m.away_source) for m in matches if m.stage != Stage.GRUPO]
    assert ko == [(Stage.SEMIFINAL, "R", "A:2", "A:3"), (Stage.FINAL, "F", "A:1", "V:R")]


def test_4_times_semis_1x3_e_2x4():
    _, matches = build_matches(FormatCode.GRUPO_SEMI_FINAL, 4)
    ko = [(m.code, m.home_source, m.away_source) for m in matches if m.stage != Stage.GRUPO]
    assert ko == [("SF1", "A:1", "A:3"), ("SF2", "A:2", "A:4"), ("F", "V:SF1", "V:SF2")]


@pytest.mark.parametrize("n", [3, 4, 5, 6])
@pytest.mark.parametrize("weight", ["1", "1.5", "2"])
def test_sempre_fecha_exatamente_os_90_minutos(n, weight):
    cfg = TimeConfig(total_minutes=90, changeover_minutes=1, final_weight=Decimal(weight))
    for o in suggest_formats(n, cfg):
        if o.feasible:
            assert total_used(o, cfg) == 90 * 60, (n, o.name)


def test_jogo_de_tabela_sempre_8_min_e_mata_mata_maior():
    for n in (3, 4, 5, 6):
        for o in suggest_formats(n, CFG):
            if o.code == FormatCode.PELADA_NORMAL:
                continue
            assert o.match_seconds == 480
            if o.feasible:
                assert o.final_seconds > 480
                assert o.knockout_seconds is None or o.knockout_seconds > 480


def test_3_times_ida_e_volta():
    o = option(3, FormatCode.GRUPO_REPESCAGEM_FINAL, legs=2)
    assert o.recommended and o.total_matches == 8
    # 90 − 7 trocas = 83 min; 6 × 8 = 48 na tabela; 35 min para 2º×3º (1) e final (1,5)
    assert o.match_seconds == 480 and o.knockout_seconds == 840 and o.final_seconds == 1260


def test_4_times_sem_tempo_para_ida_e_volta():
    double = option(4, FormatCode.GRUPO_SEMI_FINAL, legs=2)
    assert not double.feasible and "fase de grupos" in double.note  # 12 × 8 = 96 min só de tabela
    assert double.final_seconds is None
    single = option(4, FormatCode.GRUPO_SEMI_FINAL, legs=1)
    # 90 − 8 trocas = 82; 6 × 8 = 48; 34 min para 2 semis + final 1,5
    assert single.recommended and single.knockout_seconds == 582 and single.final_seconds == 2040 - 2 * 582


def test_mata_mata_curto_demais_e_inviavel():
    # Duas semis + final com só 20 min sobrando: 20/3,5 = 5:42 < 8 min
    t = match_times(8, 2, True, TimeConfig(total_minutes=90, changeover_minutes=0, final_weight=Decimal("1.5")))
    assert t.knockout_seconds < 480 and not t.feasible


def test_duracao_do_jogo_de_tabela_configuravel():
    o = suggest_formats(4, TimeConfig(changeover_minutes=1, group_match_minutes=7))[0]
    assert o.match_seconds == 420 and total_used(o) == 90 * 60


def test_ida_e_volta_inverte_mando():
    _, matches = build_matches(FormatCode.GRUPO_REPESCAGEM_FINAL, 3, legs=2)
    group = [m for m in matches if m.stage == Stage.GRUPO]
    assert [m.leg for m in group] == [1, 1, 1, 2, 2, 2]
    ida = {(m.home, m.away) for m in group if m.leg == 1}
    assert {(m.home, m.away) for m in group if m.leg == 2} == {(a, h) for h, a in ida}


def test_chaveamento_cruzado_dois_grupos():
    groups, matches = build_matches(FormatCode.DOIS_GRUPOS_SEMI_FINAL, 6)
    assert groups == {"A": [0, 2, 4], "B": [1, 3, 5]}
    sf = [(m.code, m.home_source, m.away_source) for m in matches if m.stage == Stage.SEMIFINAL]
    assert sf == [("SF1", "A:1", "B:2"), ("SF2", "B:1", "A:2")]
    assert [m.group for m in matches if m.stage == Stage.GRUPO][:4] == ["A", "B", "A", "B"]
    assert [m.seq for m in matches] == list(range(1, len(matches) + 1))


def test_pelada_normal_com_2_times():
    o = suggest_formats(2, TimeConfig())[0]
    assert o.code == FormatCode.PELADA_NORMAL and o.match_seconds == 600
    assert [(m.home, m.away) for m in o.matches] == [(0, 1)]

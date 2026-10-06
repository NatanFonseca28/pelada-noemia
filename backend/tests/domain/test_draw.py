"""Testes do sorteio (serviço puro)."""
from collections import Counter

import pytest

from app.domain.draw import DrawConfig, DrawError, DrawPlayer, FilledBy, Mode, Role, run_draw

CFG = DrawConfig()


def make_players(zag=0, ala=0, ata=0, gk=0, none=0, start=1, **kw) -> list[DrawPlayer]:
    players, i = [], start
    for pos, count in (("ZAGUEIRO", zag), ("ALA", ala), ("ATACANTE", ata), ("GOLEIRO_FIXO", gk), (None, none)):
        for _ in range(count):
            players.append(DrawPlayer(i, f"{pos or 'SEM'}-{i}", pos, kw.get("secondary"), kw.get("level")))
            i += 1
    return players


def line_players(team):
    return [p for p in team.players if p.role != Role.GOLEIRO_FIXO]


def all_ids(result):
    return [p.player_id for t in result.teams for p in t.players]


def assert_ideal_composition(team):
    linha = Counter(p.position for p in team.players if p.role == Role.LINHA)
    assert linha == {"ZAGUEIRO": 2, "ALA": 2, "ATACANTE": 1}


# ---------- múltiplo exato de 5 ----------

def test_multiplo_exato_de_5_sem_goleiro_campeonato_com_voluntario():
    players = make_players(zag=6, ala=6, ata=3)  # 15 de linha
    r = run_draw(players, CFG, seed=1)
    assert r.mode == Mode.CAMPEONATO and r.num_teams == 3
    for t in r.teams:
        assert_ideal_composition(t)
        assert len(t.players) == 5
    assert not r.substitutions
    data = r.to_dict()
    assert all(t["uses_volunteer_gk"] for t in data["teams"])
    assert any("voluntário" in i for i in r.infos)
    assert sorted(all_ids(r)) == [p.id for p in players]


def test_multiplo_exato_de_5_com_2_times_sem_goleiro_e_bloqueado():
    with pytest.raises(DrawError, match="mínimo 12"):
        run_draw(make_players(zag=4, ala=4, ata=2), CFG, seed=1)


def test_menos_de_10_de_linha_e_bloqueado():
    with pytest.raises(DrawError, match="ao menos 10"):
        run_draw(make_players(zag=4, ala=3, ata=2, gk=2), CFG, seed=1)


# ---------- sobras de 1 a 4 ----------

@pytest.mark.parametrize("extra", [1, 2, 3, 4])
def test_sobras_viram_revezamento_um_por_time(extra):
    players = make_players(zag=6, ala=6, ata=3 + extra)  # 15 + extra
    r = run_draw(players, CFG, seed=7)
    assert r.num_teams == 3
    rotation = [p for t in r.teams for p in t.players if p.role == Role.REVEZAMENTO]
    assert len(rotation) == extra
    per_team = sorted(sum(p.role == Role.REVEZAMENTO for p in t.players) for t in r.teams)
    assert max(per_team) - min(per_team) <= 1  # um por time antes de repetir
    assert sorted(all_ids(r)) == [p.id for p in players]


def test_pelada_normal_com_2_times_e_2_excedentes():
    r = run_draw(make_players(zag=5, ala=5, ata=2), CFG, seed=3)  # 12 de linha
    assert r.mode == Mode.PELADA_NORMAL and r.num_teams == 2
    for t in r.teams:
        assert len(t.players) == 6
        assert t.has_rotation_gk


def test_pelada_normal_com_10_de_linha_e_2_goleiros():
    r = run_draw(make_players(zag=4, ala=4, ata=2, gk=2), CFG, seed=3)
    assert r.mode == Mode.PELADA_NORMAL
    assert all(t.has_fixed_gk and t.line_count == 5 for t in r.teams)


# ---------- cenários confirmados pelo usuário ----------

def test_18_de_linha_3_times_de_6_revezando():
    r = run_draw(make_players(zag=7, ala=7, ata=4), CFG, seed=11)
    assert [t.line_count for t in r.teams] == [6, 6, 6]
    assert all(t.has_rotation_gk for t in r.teams)


def test_17_de_linha_e_1_goleiro_fixo():
    r = run_draw(make_players(zag=7, ala=6, ata=4, gk=1), CFG, seed=5)
    gk_team = next(t for t in r.teams if t.has_fixed_gk)
    others = [t for t in r.teams if not t.has_fixed_gk]
    assert gk_team.line_count == 5 and not gk_team.has_rotation_gk
    assert [t.line_count for t in others] == [6, 6]
    assert all(t.has_rotation_gk for t in others)


def test_16_de_linha_e_2_goleiros_fixos():
    r = run_draw(make_players(zag=6, ala=6, ata=4, gk=2), CFG, seed=9)
    with_gk = [t for t in r.teams if t.has_fixed_gk]
    without = [t for t in r.teams if not t.has_fixed_gk]
    assert len(with_gk) == 2 and all(t.line_count == 5 for t in with_gk)
    assert len(without) == 1 and without[0].line_count == 6 and without[0].has_rotation_gk


@pytest.mark.parametrize(
    ("line", "gks", "expected_line_sizes"),
    [(20, 0, [5, 5, 5, 5]), (24, 0, [6, 6, 6, 6]), (23, 1, [5, 6, 6, 6]), (22, 2, [5, 5, 6, 6])],
)
def test_mesma_logica_com_4_times(line, gks, expected_line_sizes):
    zag, ala = line * 2 // 5, line * 2 // 5
    players = make_players(zag=zag, ala=ala, ata=line - zag - ala, gk=gks)
    r = run_draw(players, CFG, seed=21)
    assert r.num_teams == 4
    assert sorted(t.line_count for t in r.teams) == expected_line_sizes
    for t in r.teams:
        if t.has_fixed_gk:
            assert t.line_count == 5


# ---------- goleiros fixos ----------

def test_goleiro_fixo_no_maximo_um_por_time():
    r = run_draw(make_players(zag=6, ala=6, ata=3, gk=3), CFG, seed=2)
    assert all(sum(p.role == Role.GOLEIRO_FIXO for p in t.players) == 1 for t in r.teams)


def test_mais_goleiros_que_times_gera_aviso():
    players = make_players(zag=6, ala=6, ata=3, gk=5)
    r = run_draw(players, CFG, seed=2)
    assert len(r.unassigned) == 2
    assert any("mais goleiros fixos" in w for w in r.warnings)
    assert len(all_ids(r)) == len(players) - 2


def test_excedentes_priorizam_times_sem_goleiro_fixo():
    for seed in range(20):
        r = run_draw(make_players(zag=7, ala=6, ata=3, gk=1), CFG, seed=seed)  # 16 linha: 1 excedente
        gk_team = next(t for t in r.teams if t.has_fixed_gk)
        assert not gk_team.has_rotation_gk


# ---------- falta de jogadores em uma posição ----------

def test_falta_de_atacante_preenche_com_secundaria_depois_qualquer():
    players = make_players(zag=8, ala=7) + [
        DrawPlayer(100, "Zag-que-ataca", "ZAGUEIRO", "ATACANTE"),
    ]
    r = run_draw(players, CFG, seed=4)  # 16 de linha, 0 atacantes
    subs = {s.filled_by for s in r.substitutions}
    assert FilledBy.SECUNDARIA in subs and FilledBy.QUALQUER in subs
    sec = next(s for s in r.substitutions if s.filled_by == FilledBy.SECUNDARIA)
    assert sec.player_id == 100 and sec.position == "ATACANTE"
    for t in r.teams:
        assert sum(p.position == "ATACANTE" and p.role == Role.LINHA for p in t.players) == 1


def test_jogadores_sem_posicao_completam_vagas_antes_de_qualquer():
    players = make_players(zag=6, ala=6, none=3)
    r = run_draw(players, CFG, seed=8)
    assert [s.filled_by for s in r.substitutions] == [FilledBy.SEM_POSICAO] * 3
    assert any("sem posição definida" in i for i in r.infos)


def test_todos_sem_posicao_ainda_sorteia():
    r = run_draw(make_players(none=17), CFG, seed=8)
    assert r.num_teams == 3
    assert sorted(t.line_count for t in r.teams) == [5, 6, 6]


# ---------- equilíbrio por nível ----------

def test_equilibrar_por_nivel_reduz_diferenca():
    players = [DrawPlayer(i, f"P{i}", ("ZAGUEIRO", "ALA", "ATACANTE")[i % 3] if i % 5 else "ATACANTE",
                          level=(i % 5) + 1) for i in range(1, 21)]
    spread_balanced = []
    spread_random = []
    for seed in range(30):
        b = run_draw(players, DrawConfig(balance_by_skill=True), seed=seed)
        n = run_draw(players, DrawConfig(), seed=seed)
        spread_balanced.append(max(t.level_sum for t in b.teams) - min(t.level_sum for t in b.teams))
        spread_random.append(max(t.level_sum for t in n.teams) - min(t.level_sum for t in n.teams))
    assert sum(spread_balanced) < sum(spread_random)
    assert max(spread_balanced) <= 3


# ---------- reprodutibilidade ----------

def test_mesma_seed_mesmo_resultado_independente_da_ordem():
    players = make_players(zag=7, ala=6, ata=4, gk=1)
    a = run_draw(players, CFG, seed=12345).to_dict()
    b = run_draw(list(reversed(players)), CFG, seed=12345).to_dict()
    assert a == b


def test_seeds_diferentes_mudam_o_resultado():
    players = make_players(zag=7, ala=6, ata=4)
    results = {tuple(all_ids(run_draw(players, CFG, seed=s))) for s in range(10)}
    assert len(results) > 1


# ---------- alternativas (regra 10) ----------

def test_sobra_grande_sugere_alternativas():
    r = run_draw(make_players(zag=8, ala=7, ata=4), CFG, seed=1)  # 19 de linha
    assert [(a.num_teams, a.line_sizes) for a in r.alternatives] == [(3, [7, 6, 6]), (4, [5, 5, 5, 4])]
    r4 = run_draw(make_players(zag=8, ala=7, ata=4), CFG, seed=1, num_teams=4)
    assert sorted(t.line_count for t in r4.teams) == [4, 5, 5, 5]
    assert r4.alternatives == []


def test_14_de_linha_nao_sugere_3_times():
    r = run_draw(make_players(zag=6, ala=5, ata=3), CFG, seed=1)
    assert r.mode == Mode.PELADA_NORMAL
    assert [a.num_teams for a in r.alternatives] == [2]
    with pytest.raises(DrawError, match="Campeonato exige"):
        run_draw(make_players(zag=6, ala=5, ata=3), CFG, seed=1, num_teams=3)


def test_jogador_repetido():
    p = make_players(zag=12)
    with pytest.raises(DrawError):
        run_draw(p + [p[0]], CFG, seed=1)

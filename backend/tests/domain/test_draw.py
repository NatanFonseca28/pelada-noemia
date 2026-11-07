"""Testes do sorteio (serviço puro)."""
from collections import Counter

import pytest

from app.domain.draw import (
    DrawConfig,
    DrawError,
    DrawPlayer,
    FilledBy,
    Mode,
    Role,
    preview,
    run_draw,
    suggest_alternatives,
)

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
    assert sorted(all_ids(r)) == [p.id for p in players]


def test_multiplo_exato_de_5_com_2_times_sem_goleiro_e_bloqueado():
    with pytest.raises(DrawError, match="mínimo 12"):
        run_draw(make_players(zag=4, ala=4, ata=2), CFG, seed=1)


def test_menos_de_10_de_linha_e_bloqueado():
    with pytest.raises(DrawError, match="ao menos 10"):
        run_draw(make_players(zag=4, ala=3, ata=2, gk=2), CFG, seed=1)


# ---------- sobras de 1 a 4 ----------

@pytest.mark.parametrize("extra", [1, 2, 3])
def test_sobras_viram_revezamento_um_por_time(extra):
    players = make_players(zag=6, ala=6, ata=3 + extra)  # 15 + extra
    r = run_draw(players, CFG, seed=7)
    assert r.num_teams == 3
    rotation = [p for t in r.teams for p in t.players if p.role == Role.REVEZAMENTO]
    assert len(rotation) == min(extra, 3)  # no máximo um por time
    assert r.reserves == []
    assert all(t.line_count <= 6 for t in r.teams)
    assert sorted(all_ids(r)) == [p.id for p in players]


def test_sobra_maior_que_um_por_time_e_recusada():
    with pytest.raises(DrawError, match="não existe reserva"):
        run_draw(make_players(zag=6, ala=6, ata=7), CFG, seed=7)  # 19 de linha: 3 times, 1 não cabe


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


def test_17_de_linha_e_1_goleiro_fixo_pertence_ao_unico_time_de_5():
    players = make_players(zag=7, ala=6, ata=4, gk=1)
    r = run_draw(players, CFG, seed=5)
    assert r.num_teams == 3 and r.shared_goalkeepers == []
    assert sorted(t.line_count for t in r.teams) == [5, 6, 6]
    owner = next(t for t in r.teams if t.has_fixed_gk)
    assert owner.line_count == 5 and not owner.has_rotation_gk
    assert [t.has_rotation_gk for t in r.teams if t is not owner] == [True, True]
    assert not r.warnings


def test_18_de_linha_e_1_goleiro_fixo_avisa_que_ele_sobra():
    players = make_players(zag=7, ala=7, ata=4, gk=1)
    r = run_draw(players, CFG, seed=7)
    assert [t.line_count for t in r.teams] == [6, 6, 6]
    assert not any(t.has_fixed_gk for t in r.teams)
    assert r.shared_goalkeepers == [players[-1].id]
    assert any("Faltam 2 de linha" in i and "4 times" in i and "não precisa de goleiro fixo" in i
               for i in r.infos)


@pytest.mark.parametrize(("zag", "ala", "ata", "sizes"), [(6, 6, 4, [5, 5, 6]), (6, 5, 4, [5, 5, 5])])
def test_mais_de_um_time_de_5_goleiro_fixo_fica_da_pelada(zag, ala, ata, sizes):
    players = make_players(zag=zag, ala=ala, ata=ata, gk=1)
    r = run_draw(players, CFG, seed=3)
    assert sorted(t.line_count for t in r.teams) == sizes
    assert not any(t.has_fixed_gk for t in r.teams)
    assert r.shared_goalkeepers == [players[-1].id]
    assert not any("não precisa de goleiro fixo" in i for i in r.infos)


def test_16_de_linha_e_2_goleiros_fixos_vao_para_os_2_times_de_5():
    players = make_players(zag=6, ala=6, ata=4, gk=2)
    r = run_draw(players, CFG, seed=9)
    assert sorted(t.line_count for t in r.teams) == [5, 5, 6]
    assert sum(t.has_fixed_gk for t in r.teams) == 2 and r.shared_goalkeepers == []
    assert not any(t["uses_volunteer_gk"] for t in r.to_dict()["teams"])


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


def test_mais_goleiros_que_times_sobram_como_goleiros_da_pelada():
    players = make_players(zag=6, ala=6, ata=3, gk=5)
    r = run_draw(players, CFG, seed=2)
    assert len(r.shared_goalkeepers) == 2 and not r.warnings
    assert all(t.has_fixed_gk for t in r.teams)
    assert sorted(all_ids(r) + r.shared_goalkeepers) == [p.id for p in players]


def test_um_goleiro_por_time_ninguem_reveza():
    for seed in range(20):
        r = run_draw(make_players(zag=6, ala=6, ata=3, gk=3), CFG, seed=seed)  # 15 linha, 3 times, 3 goleiros
        assert all(t.has_fixed_gk and not t.has_rotation_gk and t.line_count == 5 for t in r.teams)
        assert r.reserves == [] and r.shared_goalkeepers == []
    with pytest.raises(DrawError, match="não existe reserva"):  # 16 de linha: o 16º não caberia em time nenhum
        run_draw(make_players(zag=7, ala=6, ata=3, gk=3), CFG, seed=1)


def test_nivel_e_velocidade_de_goleiro_nao_entram_no_equilibrio():
    line = make_players(zag=6, ala=6, ata=3)
    gks = [DrawPlayer(90 + i, f"G{i}", "GOLEIRO_FIXO", level=5, speed=5) for i in range(3)]
    r = run_draw(line + gks, DrawConfig(balance_by_skill=True), seed=1)
    assert all(t.has_fixed_gk for t in r.teams)
    assert all(t.strength_sum == 5 * 6 for t in r.teams)  # só a linha: 5 jogadores com 3 + 3


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
    assert any("sem posição jogam onde faltava" in i for i in r.infos)


def test_todos_sem_posicao_ainda_sorteia():
    r = run_draw(make_players(none=17), CFG, seed=8)
    assert r.num_teams == 3
    assert sorted(t.line_count for t in r.teams) == [5, 6, 6]


# ---------- teto de 5 na linha + 1 no gol ----------

def test_16_confirmados_com_2_goleiros_e_recusado_sem_reserva():
    """14 de linha + 2 goleiros fixos: sobrariam 4, e reserva não existe → sorteio recusado com orientação."""
    players = make_players(zag=6, ala=5, ata=3, gk=2)
    with pytest.raises(DrawError) as e:
        run_draw(players, CFG, seed=1)
    msg = str(e.value)
    assert "não existe reserva" in msg and "Sobram 4" in msg
    assert "Jogar com menos 1" in msg


def test_orientacao_sugere_jogar_com_menos_1_quando_falta_um():
    """14 de linha, 2 times: com "menos 1" fecham 3 times (5/5/4)."""
    players = make_players(zag=6, ala=5, ata=3, gk=2)
    with pytest.raises(DrawError) as e:
        run_draw(players, CFG, seed=1, num_teams=2)
    assert "Jogar com menos 1" in str(e.value)
    r = run_draw(players, DrawConfig(allow_short_team=True), seed=1)
    assert r.num_teams == 3 and r.reserves == []


@pytest.mark.parametrize("line", range(10, 31))
@pytest.mark.parametrize("gks", range(0, 5))
def test_nunca_reserva_nem_time_com_7(line, gks):
    zag, ala = line * 2 // 5, line * 2 // 5
    players = make_players(zag=zag, ala=ala, ata=line - zag - ala, gk=gks)
    try:
        r = run_draw(players, CFG, seed=line * 10 + gks)
    except DrawError:
        return  # bloqueia: mínimo de goleiro, campeonato, ou sobra que não fecha time
    assert r.reserves == []
    for t in r.teams:
        assert t.line_count <= (5 if t.has_fixed_gk else 6)
        assert sum(p.role == Role.REVEZAMENTO for p in t.players) <= (0 if t.has_fixed_gk else 1)
        assert len(t.players) <= 6
    fives = sum(not t.has_rotation_gk for t in r.teams)  # times que ficam só com 5 na linha
    owned = sum(t.has_fixed_gk for t in r.teams)
    # goleiro fixo só ganha time quando os times de 5 não passam dos goleiros
    assert owned == (fives if gks and gks >= fives else 0)
    assert len(r.shared_goalkeepers) == gks - owned
    assert (fives == 0 and gks > 0) == any("não precisa de goleiro fixo" in i for i in r.infos)
    assert sorted(all_ids(r) + r.shared_goalkeepers) == [p.id for p in players]


def test_alternativas_nunca_deixam_reserva():
    for line in range(10, 31):
        for gks in range(0, 4):
            for a in suggest_alternatives(line, CFG, gks):
                assert "reserva" not in a.description


# ---------- equilíbrio por nível e velocidade ----------

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


def test_equilibrar_leva_velocidade_em_conta():
    # mesmo nível para todos: só a velocidade diferencia
    players = [DrawPlayer(i, f"P{i}", ("ZAGUEIRO", "ALA", "ATACANTE")[i % 3] if i % 5 else "ATACANTE",
                          level=3, speed=(i % 5) + 1) for i in range(1, 21)]
    spread_balanced = []
    spread_random = []
    for seed in range(30):
        b = run_draw(players, DrawConfig(balance_by_skill=True), seed=seed)
        n = run_draw(players, DrawConfig(), seed=seed)
        spread_balanced.append(max(t.speed_sum for t in b.teams) - min(t.speed_sum for t in b.teams))
        spread_random.append(max(t.speed_sum for t in n.teams) - min(t.speed_sum for t in n.teams))
    assert sum(spread_balanced) < sum(spread_random)
    assert max(spread_balanced) <= 3


def test_forca_soma_nivel_e_velocidade_com_peso_igual():
    assert DrawPlayer(1, "A", "ALA", level=5, speed=1).strength == DrawPlayer(2, "B", "ALA", level=1, speed=5).strength
    assert DrawPlayer(3, "C", "ALA").strength == 6  # não informado conta 3 + 3


@pytest.mark.parametrize("seed", range(40))
def test_equilibrio_com_posicoes_desiguais_e_goleiros(seed):
    """Vagas fora de posição e revezamento não podem desfazer o equilíbrio (refinamento por trocas)."""
    import random
    rng = random.Random(seed)
    pos = ("ZAGUEIRO", "ALA", "ATACANTE")
    players = [DrawPlayer(i, f"P{i}", pos[i % 3], level=rng.randint(1, 5), speed=rng.randint(1, 5))
               for i in range(1, 17)] + make_players(gk=2, start=100)
    r = run_draw(players, DrawConfig(balance_by_skill=True), seed=seed)
    avgs = [t.strength_avg for t in r.teams]
    assert max(avgs) - min(avgs) <= 0.6
    for t in r.teams:  # composição preservada pelas trocas
        linha = Counter(p.position for p in t.players if p.role == Role.LINHA)
        assert linha == {"ZAGUEIRO": 2, "ALA": 2, "ATACANTE": 1}
    team_of = {p.player_id: t.index for t in r.teams for p in t.players}
    assert all(team_of[s.player_id] == s.team_index for s in r.substitutions)


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
    with pytest.raises(DrawError, match="Jogar com menos 1"):  # 19 de linha: 3 times deixariam 1 de fora
        run_draw(make_players(zag=8, ala=7, ata=4), CFG, seed=1)
    assert [(a.num_teams, a.line_sizes) for a in suggest_alternatives(19, CFG)] == [(4, [5, 5, 5, 4])]
    r4 = run_draw(make_players(zag=8, ala=7, ata=4), CFG, seed=1, num_teams=4)
    assert sorted(t.line_count for t in r4.teams) == [4, 5, 5, 5]
    assert r4.alternatives == []


def test_14_de_linha_nao_sugere_3_times():
    with pytest.raises(DrawError, match="não existe reserva"):  # 14 de linha, sem goleiro: 4 não cabem em 2 times
        run_draw(make_players(zag=6, ala=5, ata=3), CFG, seed=1)
    with pytest.raises(DrawError, match="Campeonato exige"):
        run_draw(make_players(zag=6, ala=5, ata=3), CFG, seed=1, num_teams=3)


# ---------- time com um a menos (opção do sorteio) ----------

SHORT = DrawConfig(allow_short_team=True)


def test_um_a_menos_forma_3_times_com_14_de_linha_e_2_goleiros():
    players = make_players(zag=6, ala=5, ata=3, gk=2)  # 16 confirmados
    r = run_draw(players, SHORT, seed=1)
    assert r.mode == Mode.CAMPEONATO and r.num_teams == 3
    assert sorted(t.line_count for t in r.teams) == [4, 5, 5]
    assert r.reserves == []
    assert any("joga com 4 na linha" in i and "time que está de fora" in i for i in r.infos)
    assert sorted(all_ids(r) + r.shared_goalkeepers) == [p.id for p in players]
    assert [a.num_teams for a in r.alternatives] == [3]


def test_um_a_menos_com_19_de_linha_forma_4_times():
    r = run_draw(make_players(zag=8, ala=7, ata=4), SHORT, seed=1)
    assert sorted(t.line_count for t in r.teams) == [4, 5, 5, 5] and r.reserves == []


def test_um_a_menos_nao_muda_quando_falta_mais_de_um():
    # 13 de linha: 3 times exigiria 2 a menos, e 2 times deixariam 1 de fora
    with pytest.raises(DrawError, match="Confirme mais 1"):
        run_draw(make_players(zag=5, ala=5, ata=3), SHORT, seed=1)


def test_um_a_menos_nao_vale_para_2_times():
    with pytest.raises(DrawError):
        run_draw(make_players(zag=4, ala=3, ata=2, gk=2), SHORT, seed=1)  # 9 de linha


def test_sem_a_opcao_14_de_linha_e_recusado():
    with pytest.raises(DrawError, match="não existe reserva"):
        run_draw(make_players(zag=6, ala=5, ata=3, gk=2), CFG, seed=1)


def test_jogador_repetido():
    p = make_players(zag=12)
    with pytest.raises(DrawError):
        run_draw(p + [p[0]], CFG, seed=1)


# ---------- situação da lista antes de sortear ----------

def test_preview_fecha_3_times_de_6():
    r = preview(18, 0, CFG)
    assert r.status == "OK" and r.teams == 3 and r.team_sizes == [6, 6, 6]
    assert r.headline == "Fecha 3 times de 6 jogadores"


def test_preview_19_de_linha_mais_1_goleiro_sobra_1_e_sugere_menos_1():
    r = preview(19, 1, CFG)
    assert r.status == "SOBRA" and "sobra 1 jogador" in r.headline
    assert r.options[0].kind == "SHORT" and r.options[0].allow_short_team
    p = preview(19, 1, DrawConfig(allow_short_team=True))
    assert p.status == "OK" and p.teams == 4


def test_preview_falta_gente_e_diz_quantos():
    r = preview(8, 0, CFG)
    assert r.status == "FALTA" and "Faltam 4 jogadores" in r.headline
    assert preview(10, 0, CFG).status == "FALTA"  # 2 times sem goleiro nenhum
    assert preview(10, 2, CFG).status == "OK"


@pytest.mark.parametrize("line", range(8, 31))
@pytest.mark.parametrize("gks", range(0, 4))
@pytest.mark.parametrize("short", [False, True])
def test_preview_concorda_com_o_sorteio(line, gks, short):
    cfg = DrawConfig(allow_short_team=short)
    pv = preview(line, gks, cfg)
    players = make_players(zag=line * 2 // 5, ala=line * 2 // 5, ata=line - 2 * (line * 2 // 5), gk=gks)
    try:
        r = run_draw(players, cfg, seed=1)
    except DrawError:
        assert pv.status != "OK"
        return
    assert pv.status == "OK" and pv.teams == r.num_teams
    assert all(t <= 6 for t in pv.team_sizes)
